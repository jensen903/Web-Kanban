const API_ROOT = "/api/v1";

const state = {
  bootstrap: null,
  currentView: "overview",
  rangeMode: "yesterday",
  selectedPlatforms: new Set(["美团", "饿了么", "京东"]),
  startDate: "",
  endDate: "",
  weekValue: "",
  monthValue: "",
  province: "",
  city: "",
  mappingKeyword: "",
  mappingFilter: "all",
  mappingProvince: "",
  mappingCity: "",
  mappingDistrict: "",
  mappingAdvancedOpen: false,
  editorStageOpen: false,
  activeEditor: "time",
  requestToken: 0,
};

let mappingSearchDebounceId = null;

const viewTitles = {
  overview: "大盘概览",
  trends: "趋势分析",
  stores: "门店分析",
  regions: "地域分析",
  mappings: "门店映射",
};

const chartColors = {
  美团: "#b85d31",
  饿了么: "#1f7b80",
  京东: "#ce8d2f",
};

const viewConfigs = {
  overview: {
    sectionId: "view-overview",
    load: loadOverviewData,
    render: renderOverview,
  },
  trends: {
    sectionId: "view-trends",
    load: loadTrendsData,
    render: renderTrends,
  },
  stores: {
    sectionId: "view-stores",
    load: loadStoresData,
    render: renderStores,
  },
  regions: {
    sectionId: "view-regions",
    load: loadRegionsData,
    render: renderRegions,
  },
  mappings: {
    sectionId: "view-mappings",
    load: loadMappingsData,
    render: renderMappings,
  },
};

init();

async function init() {
  bindEvents();
  try {
    setStatus("正在连接本地 API", "loading");
    state.bootstrap = await apiGet("/bootstrap");
    initializeDates();
    populateLocationOptions();
    populateMappingLocationOptions();
    toggleScopedFilters();
    await loadAndRenderCurrentView();
  } catch (error) {
    console.error(error);
    setStatus("API 初始化失败", "error");
    renderCurrentState("初始化失败，请确认 `python3 src/backend/server.py` 已启动。", true);
  }
}

function bindEvents() {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", async () => {
      state.currentView = button.dataset.view;
      document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("is-active"));
      button.classList.add("is-active");
      document.querySelectorAll(".view-section").forEach((section) => section.classList.remove("is-visible"));
      document.getElementById(viewConfigs[state.currentView].sectionId).classList.add("is-visible");
      document.getElementById("view-title").textContent = viewTitles[state.currentView];
      toggleScopedFilters();
      await loadAndRenderCurrentView();
    });
  });

  document.querySelectorAll(".time-mode-option").forEach((button) => {
    button.addEventListener("click", async () => {
      state.rangeMode = button.dataset.range;
      applyDateRangeMode();
      state.activeEditor = "time";
      state.editorStageOpen = state.rangeMode === "custom" || state.rangeMode === "week" || state.rangeMode === "month";
      syncFilterControls();
      await loadAndRenderCurrentView();
    });
  });

  document.getElementById("time-summary-trigger").addEventListener("click", (event) => {
    event.stopPropagation();
    toggleEditorStage("time");
  });

  document.getElementById("platform-summary-trigger").addEventListener("click", (event) => {
    event.stopPropagation();
    toggleEditorStage("platform");
  });

  document.getElementById("location-summary-trigger").addEventListener("click", (event) => {
    event.stopPropagation();
    toggleEditorStage("location");
  });

  document.getElementById("filter-editor-stage").addEventListener("click", (event) => {
    event.stopPropagation();
  });

  document.getElementById("filter-reset-trigger").addEventListener("click", async () => {
    resetPrimaryFilters();
    await loadAndRenderCurrentView();
  });

  document.getElementById("platform-all-toggle").addEventListener("change", async (event) => {
    const checked = event.target.checked;
    if (checked) {
      state.selectedPlatforms = new Set(["美团", "饿了么", "京东"]);
    } else {
      state.selectedPlatforms = new Set(["美团", "饿了么", "京东"]);
      event.target.checked = true;
    }
    syncPlatformFilterControls();
    await loadAndRenderCurrentView();
  });

  document.querySelectorAll(".platform-checkbox").forEach((checkbox) => {
    checkbox.addEventListener("change", async (event) => {
      const platform = event.target.value;
      if (event.target.checked) {
        state.selectedPlatforms.add(platform);
      } else {
        state.selectedPlatforms.delete(platform);
      }

      if (!state.selectedPlatforms.size) {
        state.selectedPlatforms.add(platform);
        event.target.checked = true;
      }

      syncPlatformFilterControls();
      await loadAndRenderCurrentView();
    });
  });

  document.getElementById("start-date").addEventListener("change", async (event) => {
    state.startDate = normalizeInputDate(event.target.value);
    state.rangeMode = "custom";
    syncFilterControls();
    await loadAndRenderCurrentView();
  });

  document.getElementById("end-date").addEventListener("change", async (event) => {
    state.endDate = normalizeInputDate(event.target.value);
    state.rangeMode = "custom";
    syncFilterControls();
    await loadAndRenderCurrentView();
  });

  document.getElementById("week-date").addEventListener("change", async (event) => {
    state.weekValue = event.target.value;
    state.rangeMode = "week";
    applyDateRangeMode();
    state.editorStageOpen = true;
    await loadAndRenderCurrentView();
  });

  document.getElementById("month-date").addEventListener("change", async (event) => {
    state.monthValue = event.target.value;
    state.rangeMode = "month";
    applyDateRangeMode();
    state.editorStageOpen = true;
    await loadAndRenderCurrentView();
  });

  document.addEventListener("click", () => {
    if (state.editorStageOpen) {
      state.editorStageOpen = false;
      syncFilterControls();
    }
  });

  document.getElementById("province-filter").addEventListener("change", async (event) => {
    state.province = event.target.value;
    state.city = "";
    populateLocationOptions();
    await loadAndRenderCurrentView();
  });

  document.getElementById("city-filter").addEventListener("change", async (event) => {
    state.city = event.target.value;
    await loadAndRenderCurrentView();
  });

  document.getElementById("mapping-search").addEventListener("input", (event) => {
    state.mappingKeyword = event.target.value.trim();
    if (mappingSearchDebounceId) {
      window.clearTimeout(mappingSearchDebounceId);
    }
    mappingSearchDebounceId = window.setTimeout(async () => {
      await loadAndRenderCurrentView();
    }, 180);
  });

  document.getElementById("mapping-filter").addEventListener("change", async (event) => {
    state.mappingFilter = event.target.value;
    await loadAndRenderCurrentView();
  });

  document.getElementById("mapping-more-toggle").addEventListener("click", () => {
    state.mappingAdvancedOpen = !state.mappingAdvancedOpen;
    toggleMappingAdvancedFilters();
  });

  document.getElementById("mapping-province-filter").addEventListener("change", async (event) => {
    state.mappingProvince = event.target.value;
    state.mappingCity = "";
    state.mappingDistrict = "";
    populateMappingLocationOptions();
    await loadAndRenderCurrentView();
  });

  document.getElementById("mapping-city-filter").addEventListener("change", async (event) => {
    state.mappingCity = event.target.value;
    state.mappingDistrict = "";
    populateMappingLocationOptions();
    await loadAndRenderCurrentView();
  });

  document.getElementById("mapping-district-filter").addEventListener("change", async (event) => {
    state.mappingDistrict = event.target.value;
    await loadAndRenderCurrentView();
  });
}

function initializeDates() {
  const { min_date: minDate, max_date: maxDate } = state.bootstrap;
  document.getElementById("dataset-range").textContent = `${minDate} 至 ${maxDate}`;
  state.endDate = maxDate;
  state.startDate = maxDate;
  state.weekValue = toWeekInputValue(maxDate);
  state.monthValue = toMonthInputValue(maxDate);
  applyDateRangeMode();
  syncFilterControls();
}

function populateLocationOptions() {
  const provinceSelect = document.getElementById("province-filter");
  const citySelect = document.getElementById("city-filter");
  const locations = state.bootstrap?.locations || [];

  provinceSelect.innerHTML = `<option value="">全部省份</option>${locations
    .map(
      (item) =>
        `<option value="${item.province}" ${item.province === state.province ? "selected" : ""}>${displayProvince(item.province)}</option>`,
    )
    .join("")}`;

  const selectedLocation = locations.find((item) => item.province === state.province);
  const cities = selectedLocation ? selectedLocation.cities : state.bootstrap?.cities || [];
  citySelect.innerHTML = `<option value="">全部城市</option>${cities
    .map((city) => `<option value="${city}" ${city === state.city ? "selected" : ""}>${city}</option>`)
    .join("")}`;
}

function populateMappingLocationOptions() {
  const provinceSelect = document.getElementById("mapping-province-filter");
  const citySelect = document.getElementById("mapping-city-filter");
  const districtSelect = document.getElementById("mapping-district-filter");
  const locations = state.bootstrap?.mapping_locations || [];

  provinceSelect.innerHTML = `<option value="">全部省份</option>${locations
    .map(
      (item) =>
        `<option value="${item.province}" ${item.province === state.mappingProvince ? "selected" : ""}>${displayProvince(item.province)}</option>`,
    )
    .join("")}`;

  const selectedProvince = locations.find((item) => item.province === state.mappingProvince);
  const cities = selectedProvince
    ? selectedProvince.cities
    : uniqueValues(locations.flatMap((item) => item.cities.map((cityItem) => cityItem.city)))
        .sort()
        .map((city) => ({ city, districts: collectDistrictsForCity(locations, city) }));
  citySelect.innerHTML = `<option value="">全部城市</option>${cities
    .map(
      (item) =>
        `<option value="${item.city}" ${item.city === state.mappingCity ? "selected" : ""}>${item.city}</option>`,
    )
    .join("")}`;

  const selectedCity = cities.find((item) => item.city === state.mappingCity);
  const districts = selectedCity ? selectedCity.districts : [];
  districtSelect.innerHTML = `<option value="">全部地区</option>${districts
    .map(
      (district) =>
        `<option value="${district}" ${district === state.mappingDistrict ? "selected" : ""}>${district}</option>`,
    )
    .join("")}`;
}

function collectDistrictsForCity(locations, city) {
  return uniqueValues(
    locations.flatMap((item) =>
      item.cities
        .filter((cityItem) => cityItem.city === city)
        .flatMap((cityItem) => cityItem.districts || []),
    ),
  ).sort();
}

function toggleScopedFilters() {
  const isStageView = state.currentView !== "mappings";
  const isLocationView = state.currentView === "stores";
  const isMappingView = state.currentView === "mappings";
  const filterStage = document.getElementById("filter-stage");
  const summaryBar = document.querySelector(".filter-summary-bar");
  const locationTrigger = document.getElementById("location-summary-trigger");
  const mappingShell = document.getElementById("mapping-filter-shell");
  if (filterStage) filterStage.style.display = isStageView ? "grid" : "none";
  if (summaryBar) summaryBar.classList.toggle("has-location", isLocationView);
  if (locationTrigger) locationTrigger.style.display = isLocationView ? "grid" : "none";
  if (mappingShell) mappingShell.style.display = isMappingView ? "grid" : "none";
  if (!isStageView || (!isLocationView && state.activeEditor === "location")) {
    state.editorStageOpen = false;
    if (!isLocationView && state.activeEditor === "location") state.activeEditor = "time";
  }
  toggleMappingAdvancedFilters();
  syncFilterControls();
}

function toggleMappingAdvancedFilters() {
  const isMappingView = state.currentView === "mappings";
  const advancedPanel = document.getElementById("mapping-advanced-panel");
  const toggleButton = document.getElementById("mapping-more-toggle");
  const toggleLabel = document.getElementById("mapping-more-label");
  if (!advancedPanel || !toggleButton || !toggleLabel) return;

  advancedPanel.style.display = isMappingView && state.mappingAdvancedOpen ? "grid" : "none";
  toggleButton.setAttribute("aria-expanded", String(isMappingView && state.mappingAdvancedOpen));
  toggleButton.classList.toggle("is-open", isMappingView && state.mappingAdvancedOpen);
  toggleLabel.textContent = isMappingView && state.mappingAdvancedOpen ? "收起地域筛选" : "展开地域筛选";
}

function applyDateRangeMode() {
  const maxDate = state.bootstrap.max_date;
  if (state.rangeMode === "yesterday") {
    state.endDate = maxDate;
    state.startDate = maxDate;
  } else if (state.rangeMode === "7") {
    state.endDate = maxDate;
    state.startDate = shiftDate(maxDate, -6);
  } else if (state.rangeMode === "week") {
    if (!state.weekValue) state.weekValue = toWeekInputValue(maxDate);
    const { startDate, endDate } = weekRangeFromInput(state.weekValue);
    state.startDate = startDate;
    state.endDate = clampEndDate(endDate, maxDate);
  } else if (state.rangeMode === "month") {
    if (!state.monthValue) state.monthValue = toMonthInputValue(maxDate);
    const { startDate, endDate } = monthRangeFromInput(state.monthValue);
    state.startDate = startDate;
    state.endDate = clampEndDate(endDate, maxDate);
  }
  syncDateInputs();
  syncFilterControls();
}

function syncDateInputs() {
  document.getElementById("start-date").value = denormalizeInputDate(state.startDate);
  document.getElementById("end-date").value = denormalizeInputDate(state.endDate);
  document.getElementById("week-date").value = state.weekValue;
  document.getElementById("month-date").value = state.monthValue;
}

function syncFilterControls() {
  syncDateFilterControls();
  syncPlatformFilterControls();
  syncLocationFilterControls();
}

function syncDateFilterControls() {
  const timeTrigger = document.getElementById("time-summary-trigger");
  const stage = document.getElementById("filter-editor-stage");
  const timePanel = document.getElementById("time-editor-panel");
  const timeSummary = document.getElementById("time-filter-summary");
  if (!timeTrigger || !timePanel || !timeSummary || !stage) return;

  const isOpen = state.editorStageOpen && state.activeEditor === "time";
  timeTrigger.setAttribute("aria-expanded", String(isOpen));
  timeTrigger.classList.toggle("is-active", isOpen);
  timeSummary.textContent = currentTimeFilterLabel();
  stage.classList.toggle("is-open", state.editorStageOpen);
  timePanel.classList.toggle("is-active", isOpen);

  document.querySelectorAll(".time-mode-option").forEach((item) => {
    item.classList.toggle("is-active", item.dataset.range === state.rangeMode);
  });

  const isCustom = state.rangeMode === "custom";
  const isWeek = state.rangeMode === "week";
  const isMonth = state.rangeMode === "month";

  document.querySelectorAll(".time-detail--custom").forEach((node) => {
    node.style.display = isCustom ? "grid" : "none";
  });
  document.querySelectorAll(".time-detail--week").forEach((node) => {
    node.style.display = isWeek ? "grid" : "none";
  });
  document.querySelectorAll(".time-detail--month").forEach((node) => {
    node.style.display = isMonth ? "grid" : "none";
  });
}

function syncPlatformFilterControls() {
  const platformTrigger = document.getElementById("platform-summary-trigger");
  const stage = document.getElementById("filter-editor-stage");
  const platformPanel = document.getElementById("platform-editor-panel");
  const platformSummary = document.getElementById("platform-filter-summary");
  const platformAllToggle = document.getElementById("platform-all-toggle");
  if (!platformTrigger || !platformPanel || !platformSummary || !platformAllToggle || !stage) return;

  const isOpen = state.editorStageOpen && state.activeEditor === "platform";
  platformTrigger.setAttribute("aria-expanded", String(isOpen));
  platformTrigger.classList.toggle("is-active", isOpen);
  platformSummary.textContent = currentPlatformFilterLabel();
  stage.classList.toggle("is-open", state.editorStageOpen);
  platformPanel.classList.toggle("is-active", isOpen);

  document.querySelectorAll(".platform-checkbox").forEach((checkbox) => {
    checkbox.checked = state.selectedPlatforms.has(checkbox.value);
  });
  platformAllToggle.checked = state.selectedPlatforms.size === 3;
}

function syncLocationFilterControls() {
  const locationTrigger = document.getElementById("location-summary-trigger");
  const stage = document.getElementById("filter-editor-stage");
  const locationPanel = document.getElementById("location-editor-panel");
  const locationSummary = document.getElementById("location-filter-summary");
  if (!locationTrigger || !locationPanel || !locationSummary || !stage) return;

  const isVisible = state.currentView === "stores";
  const isOpen = isVisible && state.editorStageOpen && state.activeEditor === "location";
  locationTrigger.style.display = isVisible ? "grid" : "none";
  locationTrigger.setAttribute("aria-expanded", String(isOpen));
  locationTrigger.classList.toggle("is-active", isOpen);
  locationSummary.textContent = currentLocationFilterLabel();
  locationPanel.classList.toggle("is-active", isOpen);
}

function currentTimeFilterLabel() {
  if (state.rangeMode === "yesterday") return "昨日";
  if (state.rangeMode === "7") return "近7日";
  if (state.rangeMode === "week") return formatWeekFilterLabel(state.weekValue);
  if (state.rangeMode === "month") return formatMonthFilterLabel(state.monthValue);
  return `自定义：${state.startDate.slice(5)} - ${state.endDate.slice(5)}`;
}

function currentPlatformFilterLabel() {
  const platforms = [...state.selectedPlatforms];
  if (platforms.length === 3) return "全部平台";
  if (platforms.length === 2) return `${platforms[0]} + ${platforms[1]}`;
  return platforms[0] || "全部平台";
}

function currentLocationFilterLabel() {
  if (!state.province) return "全部省份";
  const provinceLabel = displayProvince(state.province);
  if (!state.city) return provinceLabel;
  return `${provinceLabel} · ${state.city}`;
}

function toggleEditorStage(editor) {
  if (state.activeEditor === editor && state.editorStageOpen) {
    state.editorStageOpen = false;
  } else {
    state.activeEditor = editor;
    state.editorStageOpen = true;
  }
  syncFilterControls();
}

function resetPrimaryFilters() {
  state.rangeMode = "yesterday";
  state.selectedPlatforms = new Set(["美团", "饿了么", "京东"]);
  state.province = "";
  state.city = "";
  state.editorStageOpen = false;
  state.activeEditor = "time";
  state.weekValue = toWeekInputValue(state.bootstrap.max_date);
  state.monthValue = toMonthInputValue(state.bootstrap.max_date);
  applyDateRangeMode();
  populateLocationOptions();
  syncFilterControls();
}

function formatWeekFilterLabel(value) {
  if (!value) return "按周";
  const [year, week] = value.split("-W");
  return `${year}年第${Number(week)}周`;
}

function formatMonthFilterLabel(value) {
  if (!value) return "按月";
  const [year, month] = value.split("-");
  return `${year}年${Number(month)}月`;
}

async function loadAndRenderCurrentView() {
  const viewConfig = viewConfigs[state.currentView];
  const requestToken = ++state.requestToken;
  renderViewState(viewConfig.sectionId, "正在加载数据...");
  setStatus("API 数据加载中", "loading");

  try {
    const payload = await viewConfig.load();
    if (requestToken !== state.requestToken) return;
    viewConfig.render(payload);
    initializeChartTooltips();
    setStatus("已连接本地 API", "ready");
  } catch (error) {
    if (requestToken !== state.requestToken) return;
    console.error(error);
    setStatus("API 请求失败", "error");
    renderViewState(viewConfig.sectionId, "数据加载失败，请确认后端服务和数据库已准备完成。", true);
  }
}

function renderCurrentState(message, isError = false) {
  renderViewState(viewConfigs[state.currentView].sectionId, message, isError);
}

function renderViewState(sectionId, message, isError = false) {
  document.getElementById(sectionId).innerHTML = `
    <article class="panel-card state-card ${isError ? "state-card--error" : ""}">
      <h3>${isError ? "加载失败" : "正在处理中"}</h3>
      <p class="panel-note">${message}</p>
    </article>
  `;
}

function setStatus(text, status) {
  document.getElementById("data-status").textContent = text;
  const dot = document.querySelector(".status-dot");
  dot.classList.remove("is-loading", "is-error");
  if (status === "loading") dot.classList.add("is-loading");
  if (status === "error") dot.classList.add("is-error");
}

function buildQuery({ includeLocation = false } = {}) {
  const params = {
    start_date: state.startDate,
    end_date: state.endDate,
    platform: [...state.selectedPlatforms],
  };

  if (includeLocation) {
    if (state.province) params.province = state.province;
    if (state.city) params.city = state.city;
  }

  return params;
}

async function loadOverviewData() {
  const query = buildQuery();
  const [summary, revenueShare, orderCompare, ticketCompare, coreTable] = await Promise.all([
    apiGet("/overview/summary", query),
    apiGet("/overview/revenue-share", query),
    apiGet("/overview/order-compare", query),
    apiGet("/overview/ticket-compare", query),
    apiGet("/overview/core-table", query),
  ]);

  return { summary, revenueShare, orderCompare, ticketCompare, coreTable };
}

async function loadTrendsData() {
  const query = buildQuery();
  const [summary, revenue, orders, exposure, visitUsers, visitConversion, orderConversion, handRate] = await Promise.all([
    apiGet("/trends/summary", query),
    apiGet("/trends/revenue", query),
    apiGet("/trends/orders", query),
    apiGet("/trends/exposure", query),
    apiGet("/trends/visit-users", query),
    apiGet("/trends/visit-conversion", query),
    apiGet("/trends/order-conversion", query),
    apiGet("/trends/hand-rate", query),
  ]);

  return { summary, revenue, orders, exposure, visitUsers, visitConversion, orderConversion, handRate };
}

async function loadStoresData() {
  const query = {
    ...buildQuery({ includeLocation: true }),
    limit: 10,
  };
  const [summary, activeTrend, topRevenue, topOrders] = await Promise.all([
    apiGet("/stores/summary", query),
    apiGet("/stores/active-trend", query),
    apiGet("/stores/top-revenue", query),
    apiGet("/stores/top-orders", query),
  ]);

  return { summary, activeTrend, topRevenue, topOrders };
}

async function loadRegionsData() {
  const query = buildQuery();
  const [summary, topRevenue, topOrders, topStoreCount, topStoreOutput] = await Promise.all([
    apiGet("/regions/summary", query),
    apiGet("/regions/top-revenue", query),
    apiGet("/regions/top-orders", query),
    apiGet("/regions/top-store-count", query),
    apiGet("/regions/top-store-output", query),
  ]);

  return { summary, topRevenue, topOrders, topStoreCount, topStoreOutput };
}

async function loadMappingsData() {
  const [summary, rows] = await Promise.all([
    apiGet("/store-mappings/summary", {
      platform: currentSelectedPlatforms(),
      keyword: state.mappingKeyword,
      mapping_filter: state.mappingFilter,
      mapping_province: state.mappingProvince,
      mapping_city: state.mappingCity,
      mapping_district: state.mappingDistrict,
    }),
    apiGet("/store-mappings/list", {
      limit: 200,
      keyword: state.mappingKeyword,
      mapping_filter: state.mappingFilter,
      platform: currentSelectedPlatforms(),
      mapping_province: state.mappingProvince,
      mapping_city: state.mappingCity,
      mapping_district: state.mappingDistrict,
    }),
  ]);

  return { summary, rows };
}

async function apiGet(path, params = {}) {
  const url = new URL(`${API_ROOT}${path}`, window.location.origin);
  Object.entries(params).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach((item) => url.searchParams.append(key, item));
      return;
    }
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  });

  const response = await fetch(url);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API ${url.pathname} 请求失败: ${response.status} ${body}`);
  }
  return response.json();
}

function renderOverview(data) {
  const revenueShare = data.revenueShare.map((row) => ({
    label: row.platform,
    value: Number(row.revenue || 0),
    share: Number(row.share || 0),
  }));
  const orderCompare = data.orderCompare.map((row) => ({
    label: row.platform,
    value: Number(row.valid_orders || 0),
    share: 0,
  }));
  const ticketCompare = data.ticketCompare
    .map((row) => ({
      label: row.platform,
      avgTicket: Number(row.avg_ticket || 0),
    }))
    .sort((a, b) => b.avgTicket - a.avgTicket);
  const coreTable = buildCoreTableData(data.coreTable);

  document.getElementById("view-overview").innerHTML = `
    <div class="dashboard-grid">
      ${renderMetricCards([
        {
          label: "总营收",
          value: formatCurrencyInteger(data.summary.total_revenue),
          sub: `统计周期 ${state.startDate} - ${state.endDate}<span class="metric-compare ${compareClassName(data.summary.revenue_change_rate)}">${formatCompareText(data.summary.revenue_change_rate)}</span>`,
        },
        {
          label: "总订单量",
          value: formatInteger(data.summary.total_orders),
          sub: `三平台有效订单合计<span class="metric-compare ${compareClassName(data.summary.orders_change_rate)}">${formatCompareText(data.summary.orders_change_rate)}</span>`,
        },
        { label: "活跃门店", value: formatInteger(data.summary.active_stores), sub: "有效订单大于 0 的门店数" },
        {
          label: "覆盖省份",
          value: formatInteger(data.summary.covered_provinces),
          sub: `覆盖城市 ${formatInteger(data.summary.covered_cities)} 个`,
        },
      ])}

      <div class="chart-grid-2">
        <article class="panel-card">
          <div class="panel-header">
            <div>
              <h3>平台营收贡献占比</h3>
              <p class="panel-note">各平台收入占三平台总收入的比例</p>
            </div>
            <span class="mini-stat">总收入 ${formatCurrencyInteger(data.summary.total_revenue)}</span>
          </div>
          <div class="donut-wrap">
            ${renderDonutChart(revenueShare)}
            <div class="legend-list">${renderRankList(revenueShare, "share", false, "percent")}</div>
          </div>
        </article>

        <article class="panel-card">
          <div class="panel-header">
            <div>
              <h3>平台核心指标综合对比</h3>
              <p class="panel-note">结果视角，聚焦营收、订单、占比和客单价表现</p>
            </div>
          </div>
          <div class="table-wrap">${renderTable(coreTable.headers, coreTable.rows)}</div>
        </article>
      </div>

      <div class="chart-grid-2">
        <article class="panel-card">
          <div class="panel-header">
            <div>
              <h3>平台订单量对比</h3>
              <p class="panel-note">横向平台，纵向有效订单量</p>
            </div>
          </div>
          <div class="rank-list">${renderRankList(orderCompare, "value", false, "integer")}</div>
        </article>

        <article class="panel-card">
          <div class="panel-header">
            <div>
              <h3>平台客单价对比</h3>
              <p class="panel-note">顾客实付 / 有效订单</p>
            </div>
          </div>
          <div class="rank-list">${renderRankList(ticketCompare, "avgTicket", false, "currency")}</div>
        </article>
      </div>
    </div>
  `;
}

function renderTrends(data) {
  const trendMetrics = [
    { title: "营业收入趋势", metricLabel: "营业收入", series: buildTrendSeries(data.revenue), format: "currency-int", summaryMode: "sum", summaryLabel: "区间合计" },
    { title: "订单量趋势", metricLabel: "订单量", series: buildTrendSeries(data.orders), format: "integer", summaryMode: "sum", summaryLabel: "区间合计" },
    { title: "曝光量趋势", metricLabel: "曝光量", series: buildTrendSeries(data.exposure), format: "integer", summaryMode: "sum", summaryLabel: "区间合计" },
    { title: "到手率趋势", metricLabel: "到手率", series: buildTrendSeries(data.handRate), format: "percent", summaryMode: "avg", summaryLabel: "区间均值" },
  ];

  document.getElementById("view-trends").innerHTML = `
    <div class="dashboard-grid">
      ${renderMetricCards([
        { label: "总营收", value: formatCurrencyInteger(data.summary.total_revenue), sub: "趋势页汇总" },
        { label: "总订单量", value: formatInteger(data.summary.total_orders), sub: "趋势页汇总" },
        { label: "活跃门店", value: formatInteger(data.summary.active_stores), sub: "趋势页汇总" },
      ])}
      <div class="dashboard-grid">
        ${trendMetrics
          .map(
            (metric) => `
              <article class="panel-card">
                <div class="panel-header">
                  <div>
                    <h3>${metric.title}</h3>
                    <p class="panel-note">统计周期内三平台按日期变化</p>
                  </div>
                </div>
                ${renderLineChart(metric.series, metric.format, metric.metricLabel, metric.summaryMode, metric.summaryLabel)}
              </article>
            `,
          )
          .join("")}
      </div>
    </div>
  `;
}

function renderStores(data) {
  const topRevenue = buildStoreRankItems(data.topRevenue);
  const topOrders = buildStoreRankItems(data.topOrders);

  document.getElementById("view-stores").innerHTML = `
    <div class="dashboard-grid">
      ${renderMetricCards([
        { label: "总营收", value: formatCurrencyInteger(data.summary.total_revenue), sub: locationSubtitle() },
        { label: "总订单量", value: formatInteger(data.summary.total_orders), sub: locationSubtitle() },
        { label: "活跃门店", value: formatInteger(data.summary.active_stores), sub: "按门店明细统计" },
      ])}

      <article class="panel-card">
        <div class="panel-header">
          <div>
            <h3>活跃门店趋势</h3>
            <p class="panel-note">统计周期内三平台有效门店数变化</p>
          </div>
        </div>
        ${renderLineChart(buildTrendSeries(data.activeTrend), "integer", "活跃门店数")}
      </article>

      <div class="chart-grid-2">
        <article class="panel-card">
          <div class="panel-header">
            <div>
              <h3>门店营收 Top10</h3>
              <p class="panel-note">按当前平台筛选结果展示前 10 家标准门店</p>
            </div>
          </div>
          <div class="rank-list">${renderRankList(topRevenue, "value", false, "currency", false)}</div>
        </article>

        <article class="panel-card">
          <div class="panel-header">
            <div>
              <h3>门店订单量 Top10</h3>
              <p class="panel-note">按当前平台筛选结果展示前 10 家门店</p>
            </div>
          </div>
          <div class="rank-list">${renderRankList(topOrders, "value", false, "integer", false)}</div>
        </article>
      </div>
    </div>
  `;
}

function renderRegions(data) {
  const topRevenue = buildCityRankItems(data.topRevenue.slice(0, 10));
  const topOrders = buildCityRankItems(data.topOrders.slice(0, 10));
  const topStoreCount = buildCityRankItems(data.topStoreCount.slice(0, 10));
  const topStoreOutput = buildCityRankItems(data.topStoreOutput.slice(0, 10), { showStoreCount: true });

  document.getElementById("view-regions").innerHTML = `
    <div class="dashboard-grid">
      ${renderMetricCards([
        { label: "总营收", value: formatCurrencyInteger(data.summary.total_revenue), sub: "地域经营分布汇总" },
        { label: "总订单量", value: formatInteger(data.summary.total_orders), sub: "区域规模与经营分布汇总" },
        {
          label: "覆盖城市",
          value: formatInteger(data.summary.covered_cities),
          sub: `覆盖省份 ${formatInteger(data.summary.covered_provinces)} 个，便于查看区域版图`,
        },
      ])}

      <article class="panel-card">
        <div class="panel-header">
          <div>
            <h3>地域经营分布</h3>
            <p class="panel-note">这一页先聚焦区域规模、订单体量和门店分布；其中门店分布榜走标准门店静态版图口径，其余 3 张榜仍跟时间和平台筛选联动。</p>
          </div>
        </div>
      </article>

      <div class="chart-grid-2">
        <article class="panel-card">
          <div class="panel-header">
            <div>
              <h3>城市收入 Top10</h3>
              <p class="panel-note">看哪些城市当前经营规模更大</p>
            </div>
          </div>
          <div class="rank-list">${renderRankList(topRevenue, "value", false, "currency", true)}</div>
        </article>

        <article class="panel-card">
          <div class="panel-header">
            <div>
              <h3>城市订单量 Top10</h3>
              <p class="panel-note">看哪些城市当前订单体量更高</p>
            </div>
          </div>
          <div class="rank-list">${renderRankList(topOrders, "value", false, "integer", true)}</div>
        </article>
      </div>

      <div class="chart-grid-2">
        <article class="panel-card">
          <div class="panel-header">
            <div>
              <h3>城市标准门店分布 Top10</h3>
              <p class="panel-note">只按标准门店主档统计城市版图，不跟平台筛选联动</p>
            </div>
          </div>
          <div class="rank-list">${renderRankList(topStoreCount, "value", false, "integer", true)}</div>
        </article>

        <article class="panel-card">
          <div class="panel-header">
            <div>
              <h3>城市单店产出 Top10</h3>
              <p class="panel-note">城市营收 / 城市门店数，更适合观察区域经营效率</p>
            </div>
          </div>
          <div class="rank-list">${renderRankList(topStoreOutput, "value", false, "currency", true)}</div>
        </article>
      </div>
    </div>
  `;
}

function renderMappings(data) {
  const platforms = currentSelectedPlatforms();
  const headers = ["标准门店 / ID", "省份", "城市", "地区", ...platforms];
  const coverage = data.summary.standard_store_count
    ? data.summary.selected_mapped_count / data.summary.standard_store_count
    : 0;

  document.getElementById("view-mappings").innerHTML = `
    <div class="dashboard-grid">
      ${renderMetricCards([
        { label: "标准门店数", value: formatInteger(data.summary.standard_store_count), sub: "搜索结果范围内的标准门店" },
        {
          label: "已映射门店",
          value: formatInteger(data.summary.selected_mapped_count),
          sub: `${platforms.join(" / ")} 范围内至少关联 1 个真实门店 ID`,
        },
        {
          label: "未映射门店",
          value: formatInteger(data.summary.selected_unmapped_count),
          sub: `${platforms.join(" / ")} 范围内仍需补齐映射`,
        },
        { label: "映射覆盖率", value: formatPercent(coverage), sub: "按当前平台筛选口径统计" },
      ])}

      <article class="panel-card">
        <div class="panel-header">
          <div>
            <h3>门店映射关系表</h3>
            <p class="panel-note">支持按名称或门店 ID 搜索，也支持按省市区和映射状态筛选当前需要跟进的门店。</p>
          </div>
          <div class="mapping-meta">
            <span class="pill">美团 ${formatInteger(data.summary.meituan_mapped_count)}</span>
            <span class="pill">饿了么 ${formatInteger(data.summary.eleme_mapped_count)}</span>
            <span class="pill">京东 ${formatInteger(data.summary.jd_mapped_count)}</span>
          </div>
        </div>
        <div class="table-wrap">
          ${renderTable(
            headers,
            data.rows.map((row) => [
              formatStandardStoreCell(row.standard_store_name, row.standard_store_id),
              row.province || "-",
              row.city || "-",
              row.district || "-",
              ...platforms.map((platform) => formatMappingCell(...mappingCellArgs(row, platform))),
            ]),
          )}
        </div>
        <p class="empty-note">当前展示 ${formatInteger(data.rows.length)} 条结果，原型默认最多返回 200 行。</p>
      </article>
    </div>
  `;
}

function renderMetricCards(items) {
  const gridClassName = items.length === 3 ? "metric-grid metric-grid--three" : "metric-grid";
  return `
    <div class="${gridClassName}">
      ${items
        .map(
          (item) => `
            <article class="metric-card">
              <div class="metric-label">${item.label}</div>
              <div class="metric-value">${item.value}</div>
              <div class="metric-sub">${item.sub}</div>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function formatCompareText(rate) {
  const compareLabel = compareWindowLabel();
  if (rate === null || rate === undefined) {
    return `${compareLabel}暂无基准`;
  }
  const numericRate = Number(rate || 0);
  const prefix = numericRate > 0 ? "+" : "";
  return `${compareLabel} ${prefix}${formatPercent(numericRate, 1)}`;
}

function compareClassName(rate) {
  if (rate === null || rate === undefined) return "is-neutral";
  if (Number(rate) > 0) return "is-up";
  if (Number(rate) < 0) return "is-down";
  return "is-neutral";
}

function compareWindowLabel() {
  if (state.rangeMode === "yesterday") return "昨日，较前1日";
  if (state.rangeMode === "7") return "近7天，较前7天";
  if (state.rangeMode === "week") return "本周，较前1周";
  if (state.rangeMode === "month") return "本月，较前1月";
  return "自定义周期，较上一等长周期";
}

function renderDonutChart(items) {
  const total = items.reduce((sum, item) => sum + item.value, 0);
  let startAngle = -90;
  const radius = 72;
  const circumference = 2 * Math.PI * radius;
  const segments = items
    .map((item) => {
      const ratio = total ? item.value / total : 0;
      const length = ratio * circumference;
      const dashOffset = circumference * (1 - (startAngle + 90) / 360);
      startAngle += ratio * 360;
      return `<circle cx="110" cy="110" r="${radius}" fill="none" stroke="${chartColors[item.label]}" stroke-width="28" stroke-linecap="round" stroke-dasharray="${length} ${circumference - length}" stroke-dashoffset="${dashOffset}"></circle>`;
    })
    .join("");

  return `
    <svg class="donut-chart" viewBox="0 0 220 220" aria-hidden="true">
      <circle cx="110" cy="110" r="${radius}" fill="none" stroke="rgba(97,72,49,0.08)" stroke-width="28"></circle>
      <g transform="rotate(-90 110 110)">${segments}</g>
      <text x="110" y="102" text-anchor="middle" font-size="14" fill="#756455">三平台</text>
      <text x="110" y="126" text-anchor="middle" font-size="26" font-weight="700" fill="#2f241c">${items.length}</text>
    </svg>
  `;
}

function renderRankList(items, key, showShare = false, format = "number", showPlatform = false) {
  if (!items.length) {
    return `<p class="empty-note">当前筛选条件下暂无数据。</p>`;
  }

  const max = Math.max(...items.map((item) => Number(item[key] || 0)), 0);
  return items
    .map((item, index) => {
      const value = Number(item[key] || 0);
      const width = max ? (value / max) * 100 : 0;
      const label = item.displayLabel || (showPlatform ? `${index + 1}. ${item.label} · ${item.platform}` : `${index + 1}. ${item.label}`);
      const tooltip = item.tooltip ? ` title="${escapeHtml(item.tooltip)}"` : "";
      const subLabel = item.subLabel ? `<span class="rank-label-sub">${item.subLabel}</span>` : "";
      return `
        <div class="rank-item">
          <div class="rank-top">
            <span class="rank-label"${tooltip}>
              <span class="rank-label-main">${label}</span>
              ${subLabel}
            </span>
            <span>${formatValue(value, format)}${showShare ? ` · ${formatPercent(item.share)}` : ""}</span>
          </div>
          <div class="bar-track"><div class="bar-fill" style="width:${width}%"></div></div>
        </div>
      `;
    })
    .join("");
}

function renderLineChart(seriesByPlatform, format, metricLabel = "指标值", summaryMode = "latest", summaryLabel = "最新值") {
  const allPoints = Object.values(seriesByPlatform).flat();
  if (!allPoints.length) {
    return `<p class="empty-note">当前筛选条件下暂无趋势数据。</p>`;
  }

  const width = 960;
  const dates = uniqueValues(allPoints.map((point) => point.date)).sort();
  const isSinglePoint = dates.length <= 1;
  const height = isSinglePoint ? 180 : dates.length <= 3 ? 220 : 260;
  const padding = 32;
  const leftPadding = 78;
  const rightPadding = 24;
  const axis = computeChartAxis(allPoints.map((point) => point.value), format);
  const { minValue, maxValue, ticks } = axis;

  const xForIndex = (index) => {
    if (dates.length <= 1) return (leftPadding + (width - rightPadding)) / 2;
    return leftPadding + (index / (dates.length - 1)) * (width - leftPadding - rightPadding);
  };
  const yForValue = (value) => {
    if (maxValue === minValue) return height / 2;
    return height - padding - ((value - minValue) / (maxValue - minValue)) * (height - padding * 2);
  };

  const gridLines = ticks.map((tick) => {
    const y = yForValue(tick);
    return `<line x1="${leftPadding}" y1="${y}" x2="${width - rightPadding}" y2="${y}" stroke="rgba(97,72,49,0.08)" stroke-dasharray="4 6"></line>`;
  });
  const yAxisLabels = ticks
    .map((tick) => {
      const y = yForValue(tick);
      return `<text x="${leftPadding - 12}" y="${y + 5}" text-anchor="end" font-size="13" fill="#756455">${formatAxisTickValue(tick, format)}</text>`;
    })
    .join("");

  const polylines = Object.entries(seriesByPlatform)
    .map(([platform, points]) => {
      const pointMap = new Map(points.map((point) => [point.date, point.value]));
      const mapped = dates.map((date, index) => ({
        x: xForIndex(index),
        date,
        platform,
        hasValue: pointMap.has(date),
        rawValue: pointMap.get(date),
        y: yForValue(pointMap.get(date) ?? minValue),
      }));
      const path = mapped.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
      return `
        <path d="${path}" fill="none" stroke="${chartColors[platform]}" stroke-width="3" stroke-linecap="round"></path>
        ${mapped
          .map(
            (point) =>
              point.hasValue
                ? `
                  <circle cx="${point.x}" cy="${point.y}" r="3.5" fill="${chartColors[platform]}" stroke="#fff7ef" stroke-width="1.5" pointer-events="none"></circle>
                  <circle
                    class="chart-hit-point"
                    cx="${point.x}"
                    cy="${point.y}"
                    r="12"
                    fill="transparent"
                    data-tooltip="${escapeHtml(`${point.date.slice(5)} · ${platform} · ${formatValue(point.rawValue ?? 0, format)}`)}"
                  ></circle>
                `
                : "",
          )
          .join("")}
      `;
    })
    .join("");

  const labels = dates
    .filter((_, index) => index === 0 || index === dates.length - 1 || index % Math.ceil(dates.length / 6) === 0)
    .map((date) => {
      const index = dates.indexOf(date);
      return `<text x="${xForIndex(index)}" y="${height - 6}" text-anchor="middle" font-size="13" fill="#756455">${date.slice(
        5,
      )}</text>`;
    })
    .join("");

  const legends = Object.keys(seriesByPlatform)
    .map(
      (platform) => `
        <span class="pill" style="background:${hexToSoft(chartColors[platform])};color:${chartColors[platform]}">${platform}</span>
      `,
    )
    .join("");

  const latestSummary = Object.entries(seriesByPlatform)
    .map(([platform, points]) => {
      const summaryValue = summarizeSeriesPoints(points, summaryMode);
      return `<span class="pill" style="background:${hexToSoft(chartColors[platform])};color:${chartColors[platform]}">${platform} ${formatValue(
        summaryValue,
        format,
      )}</span>`;
    })
    .join("");

  return `
    <div class="panel-note line-chart-legends">${legends}</div>
    ${isSinglePoint ? `<p class="line-chart-hint">当前筛选周期仅覆盖 1 天，趋势图按单点快照展示。</p>` : ""}
    <svg class="line-chart ${isSinglePoint ? "line-chart--single" : ""}" viewBox="0 0 ${width} ${height}">
      ${gridLines.join("")}
      ${yAxisLabels}
      ${polylines}
      ${labels}
    </svg>
    <div class="panel-note line-chart-summary-label">${summaryLabel}</div>
    <div class="mapping-meta line-chart-summary">${latestSummary}</div>
  `;
}

function summarizeSeriesPoints(points, summaryMode) {
  if (!points.length) return 0;
  if (summaryMode === "sum") {
    return points.reduce((sum, point) => sum + Number(point.value || 0), 0);
  }
  if (summaryMode === "avg") {
    return points.reduce((sum, point) => sum + Number(point.value || 0), 0) / points.length;
  }
  return Number(points[points.length - 1]?.value || 0);
}

function initializeChartTooltips() {
  const existingTooltip = document.getElementById("chart-tooltip");
  const tooltip = existingTooltip || createChartTooltip();

  document.querySelectorAll(".chart-hit-point").forEach((point) => {
    point.addEventListener("mouseenter", (event) => {
      showChartTooltip(tooltip, event.currentTarget.dataset.tooltip || "", event);
    });
    point.addEventListener("mousemove", (event) => {
      showChartTooltip(tooltip, event.currentTarget.dataset.tooltip || "", event);
    });
    point.addEventListener("mouseleave", () => {
      hideChartTooltip(tooltip);
    });
  });
}

function createChartTooltip() {
  const tooltip = document.createElement("div");
  tooltip.id = "chart-tooltip";
  tooltip.className = "chart-tooltip";
  document.body.appendChild(tooltip);
  return tooltip;
}

function showChartTooltip(tooltip, text, event) {
  tooltip.textContent = text;
  tooltip.classList.add("is-visible");
  tooltip.style.left = `${event.clientX + 14}px`;
  tooltip.style.top = `${event.clientY + 14}px`;
}

function hideChartTooltip(tooltip) {
  tooltip.classList.remove("is-visible");
}

function renderTable(headers, rows) {
  if (!rows.length) {
    return `<p class="empty-note">当前筛选条件下暂无数据。</p>`;
  }

  return `
    <table>
      <thead>
        <tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr>
      </thead>
      <tbody>
        ${rows
          .map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`)
          .join("")}
      </tbody>
    </table>
  `;
}

function buildCoreTableData(rows) {
  return {
    headers: ["平台", "营业收入", "收入占比", "订单量", "订单占比", "客单价"],
    rows: rows.map((row) => [
      row.platform,
      formatCurrency(row.revenue),
      formatPercent(row.revenue_share),
      formatInteger(row.valid_orders),
      formatPercent(row.order_share),
      formatCurrency(row.avg_ticket),
    ]),
  };
}

function buildGrowthEfficiencyTableData(rows) {
  return {
    headers: ["平台", "曝光人数", "进店人数", "进店转化率", "下单转化率"],
    rows: rows.map((row) => [
      row.platform,
      formatInteger(row.exposure_users),
      formatInteger(row.visit_users),
      formatPercent(row.visit_conversion_rate),
      formatPercent(row.order_conversion_rate),
    ]),
  };
}

function buildTrendSeries(rows) {
  const result = {};
  rows.forEach((row) => {
    if (!result[row.platform]) result[row.platform] = [];
    result[row.platform].push({
      date: row.biz_date,
      value: Number(row.metric_value || 0),
    });
  });

  Object.keys(result).forEach((platform) => {
    result[platform].sort((a, b) => a.date.localeCompare(b.date));
  });

  return result;
}

function buildStoreRankItems(rows) {
  return rows.map((row) => ({
    label: row.standard_store_name || "未命名门店",
    displayLabel: buildStoreDisplayLabel(row, { includePlatform: currentSelectedPlatforms().length > 1 && Boolean(row.platform) }),
    platform: row.platform,
    city: row.city,
    tooltip: buildStoreRankTooltip(row),
    value: Number(row.metric_value || 0),
  }));
}

function buildCityRankItems(rows, options = {}) {
  const { showStoreCount = false } = options;
  return rows.map((row) => ({
    label: row.province ? `${displayProvince(row.province)} / ${row.city || "-"}` : row.city || "-",
    platform: row.platform || "",
    value: Number(row.metric_value || 0),
    subLabel: showStoreCount && row.store_count ? `门店数 ${formatInteger(row.store_count)}` : "",
  }));
}

function currentSelectedPlatforms() {
  return ["美团", "饿了么", "京东"].filter((platform) => state.selectedPlatforms.has(platform));
}

function buildStoreDisplayLabel(row, options = {}) {
  const { includePlatform = true } = options;
  const fullName = row.standard_store_name || "未命名门店";
  const shortName = shortStoreName(fullName);
  const parts = [row.city, includePlatform ? row.platform : ""].filter(Boolean).join(" · ");
  return parts ? `${shortName} · ${parts}` : shortName;
}

function buildStoreRankTooltip(row) {
  const fullName = row.standard_store_name || "未命名门店";
  const scope = row.platform_scope
    ? String(row.platform_scope).split(",").filter(Boolean).join(" / ")
    : row.platform || "";
  return scope ? `${fullName} · 汇总平台 ${scope}` : fullName;
}

function formatStandardStoreCell(name, id) {
  const safeName = escapeHtml(name || "-");
  const safeId = escapeHtml(id || "-");
  return `${safeName}<br><span class="mini-stat">${safeId}</span>`;
}

function shortStoreName(value) {
  if (!value) return "未命名门店";
  const normalized = String(value).replace(/\s+/g, " ").trim();
  const bracketMatch = normalized.match(/[（(]([^()（）]+?店)[）)]\s*$/);
  if (bracketMatch) return bracketMatch[1];

  const withoutBrand = normalized
    .replace(/^窄巷口[·・]?\s*/, "")
    .replace(/^(?:生烫牛肉米线(?:·?馄饨)?|生烫牛肉米线馄饨)/, "")
    .trim();

  return withoutBrand || normalized;
}

function mappingCellArgs(row, platform) {
  if (platform === "美团") return [row.meituan_store_id, row.meituan_store_name];
  if (platform === "饿了么") return [row.eleme_store_id, row.eleme_store_name];
  return [row.jd_store_id, row.jd_store_name];
}

function locationSubtitle() {
  if (state.province && state.city) return `${displayProvince(state.province)} · ${state.city}`;
  if (state.province) return `${displayProvince(state.province)} 范围`;
  return "全部省份 / 城市";
}

function formatMappingCell(id, name) {
  if (!isMappedStoreId(id)) return "未映射";
  return `${id}<br><span class="mini-stat">${name || "-"}</span>`;
}

function isMappedStoreId(value) {
  return Boolean(value && value !== "未入驻平台");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function displayProvince(value) {
  if (!value) return "-";
  if (value.startsWith("广西")) return "广西";
  if (value.startsWith("新疆")) return "新疆";
  if (value.startsWith("内蒙古")) return "内蒙古";
  if (value.startsWith("宁夏")) return "宁夏";
  if (value.startsWith("西藏")) return "西藏";
  return value;
}

function normalizeInputDate(value) {
  return value ? value.replaceAll("-", "/") : "";
}

function denormalizeInputDate(value) {
  return value ? value.replaceAll("/", "-") : "";
}

function shiftDate(dateString, offsetDays) {
  const date = new Date(dateString.replaceAll("/", "-"));
  date.setDate(date.getDate() + offsetDays);
  return `${date.getFullYear()}/${String(date.getMonth() + 1).padStart(2, "0")}/${String(date.getDate()).padStart(2, "0")}`;
}

function clampEndDate(endDate, maxDate) {
  return endDate > maxDate ? maxDate : endDate;
}

function toWeekInputValue(dateString) {
  const date = new Date(dateString.replaceAll("/", "-"));
  const normalized = new Date(date);
  normalized.setHours(0, 0, 0, 0);
  normalized.setDate(normalized.getDate() + 4 - ((normalized.getDay() + 6) % 7));
  const yearStart = new Date(normalized.getFullYear(), 0, 1);
  const week = Math.ceil((((normalized - yearStart) / 86400000) + yearStart.getDay() + 1) / 7);
  return `${normalized.getFullYear()}-W${String(week).padStart(2, "0")}`;
}

function toMonthInputValue(dateString) {
  const [year, month] = denormalizeInputDate(dateString).split("-");
  return `${year}-${month}`;
}

function weekRangeFromInput(value) {
  const [yearText, weekText] = value.split("-W");
  const year = Number(yearText);
  const week = Number(weekText);
  const januaryFourth = new Date(year, 0, 4);
  const monday = new Date(januaryFourth);
  monday.setDate(januaryFourth.getDate() - ((januaryFourth.getDay() + 6) % 7) + (week - 1) * 7);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  return {
    startDate: formatDateFromObject(monday),
    endDate: formatDateFromObject(sunday),
  };
}

function monthRangeFromInput(value) {
  const [yearText, monthText] = value.split("-");
  const year = Number(yearText);
  const month = Number(monthText) - 1;
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  return {
    startDate: formatDateFromObject(firstDay),
    endDate: formatDateFromObject(lastDay),
  };
}

function formatDateFromObject(date) {
  return `${date.getFullYear()}/${String(date.getMonth() + 1).padStart(2, "0")}/${String(date.getDate()).padStart(2, "0")}`;
}

function uniqueValues(values) {
  return [...new Set(values.filter(Boolean))];
}

function formatCurrency(value) {
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

function formatCurrencyInteger(value) {
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    maximumFractionDigits: 0,
  }).format(Number(value || 0));
}

function formatInteger(value) {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(Number(value || 0));
}

function formatPercent(value, digits = 1) {
  return `${(Number(value || 0) * 100).toFixed(digits)}%`;
}

function formatWanInteger(value) {
  return `${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(Math.round(Number(value || 0) / 10000))}万`;
}

function formatValue(value, format) {
  if (format === "currency") return formatCurrency(value);
  if (format === "currency-int") return formatCurrencyInteger(value);
  if (format === "integer") return formatInteger(value);
  if (format === "percent") return formatPercent(value);
  if (format === "wan-int") return formatWanInteger(value);
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(Number(value || 0));
}

function formatAxisTickValue(value, format) {
  if (format === "percent") {
    return `${(Number(value || 0) * 100).toFixed(0)}%`;
  }
  if (format === "wan-int") {
    return formatWanInteger(value);
  }
  if (format === "currency-int") {
    return formatCurrencyInteger(value);
  }
  if (format === "currency") {
    return new Intl.NumberFormat("zh-CN", {
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(Number(value || 0));
  }
  return new Intl.NumberFormat("zh-CN", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(Number(value || 0));
}

function computeChartAxis(values, format) {
  const tickCount = 5;
  const safeValues = values.filter((value) => Number.isFinite(Number(value))).map((value) => Number(value));
  if (!safeValues.length) {
    return { minValue: 0, maxValue: 1, ticks: [0, 0.25, 0.5, 0.75, 1] };
  }

  if (format === "percent") {
    return computePercentAxis(safeValues, tickCount);
  }
  return computeMagnitudeAxis(safeValues, tickCount);
}

function computePercentAxis(values, tickCount) {
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const paddedMin = Math.max(0, rawMin - 0.01);
  const paddedMax = Math.min(1, rawMax + 0.01);
  const minSpan = 0.05;
  const centeredMin = Math.max(0, Math.min(paddedMin, paddedMax - minSpan));
  const centeredMax = Math.min(1, Math.max(paddedMax, centeredMin + minSpan));
  const roughStep = (centeredMax - centeredMin) / (tickCount - 1);
  const step = choosePercentStep(roughStep);
  const minValue = Math.max(0, Math.floor(centeredMin / step) * step);
  const maxValue = Math.min(1, Math.ceil(centeredMax / step) * step);
  return {
    minValue,
    maxValue,
    ticks: buildTicks(minValue, maxValue, step),
  };
}

function computeMagnitudeAxis(values, tickCount) {
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const span = rawMax - rawMin;
  const paddedMin = Math.max(0, rawMin - span * 0.08);
  const paddedMax = rawMax + Math.max(span * 0.12, rawMax * 0.03, 1);
  const roughStep = Math.max((paddedMax - paddedMin) / (tickCount - 1), 1);
  const step = chooseNiceNumber(roughStep);
  const minValue = Math.max(0, Math.floor(paddedMin / step) * step);
  const maxValue = Math.max(step, Math.ceil(paddedMax / step) * step);
  return {
    minValue,
    maxValue,
    ticks: buildTicks(minValue, maxValue, step),
  };
}

function choosePercentStep(roughStep) {
  const percentSteps = [0.005, 0.01, 0.02, 0.05, 0.1, 0.2];
  return percentSteps.find((step) => roughStep <= step) || 0.2;
}

function chooseNiceNumber(value) {
  if (value <= 0) return 1;
  const exponent = Math.floor(Math.log10(value));
  const fraction = value / 10 ** exponent;
  let niceFraction = 10;
  if (fraction <= 1) niceFraction = 1;
  else if (fraction <= 2) niceFraction = 2;
  else if (fraction <= 5) niceFraction = 5;
  return niceFraction * 10 ** exponent;
}

function buildTicks(minValue, maxValue, step) {
  const ticks = [];
  const safeStep = step || 1;
  for (let value = minValue; value <= maxValue + safeStep / 2; value += safeStep) {
    ticks.push(Number(value.toFixed(6)));
  }
  return ticks;
}

function hexToSoft(hex) {
  const value = hex.replace("#", "");
  const bigint = parseInt(value, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return `rgba(${r}, ${g}, ${b}, 0.14)`;
}
