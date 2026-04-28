const DATASET_PATH = "./data/dashboard_dataset.json";

const state = {
  dataset: null,
  currentView: "overview",
  rangeMode: "31",
  selectedPlatforms: new Set(["美团", "饿了么", "京东"]),
  startDate: "",
  endDate: "",
  province: "",
  city: "",
};

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

init();

async function init() {
  bindEvents();
  const response = await fetch(DATASET_PATH);
  state.dataset = await response.json();
  initializeDates();
  populateLocationOptions();
  renderAll();
}

function bindEvents() {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => {
      state.currentView = button.dataset.view;
      document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("is-active"));
      button.classList.add("is-active");
      document.querySelectorAll(".view-section").forEach((section) => section.classList.remove("is-visible"));
      document.getElementById(`view-${state.currentView}`).classList.add("is-visible");
      document.getElementById("view-title").textContent = viewTitles[state.currentView];
      toggleLocationFilters();
    });
  });

  document.querySelectorAll(".segment").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".segment").forEach((item) => item.classList.remove("is-active"));
      button.classList.add("is-active");
      state.rangeMode = button.dataset.range;
      applyDateRangeMode();
      renderAll();
    });
  });

  document.querySelectorAll(".platform-chip").forEach((button) => {
    button.addEventListener("click", () => {
      const platform = button.dataset.platform;
      if (state.selectedPlatforms.has(platform) && state.selectedPlatforms.size > 1) {
        state.selectedPlatforms.delete(platform);
        button.classList.remove("is-active");
      } else if (!state.selectedPlatforms.has(platform)) {
        state.selectedPlatforms.add(platform);
        button.classList.add("is-active");
      }
      renderAll();
    });
  });

  document.getElementById("start-date").addEventListener("change", (event) => {
    state.startDate = normalizeInputDate(event.target.value);
    state.rangeMode = "custom";
    highlightCustomRange();
    renderAll();
  });

  document.getElementById("end-date").addEventListener("change", (event) => {
    state.endDate = normalizeInputDate(event.target.value);
    state.rangeMode = "custom";
    highlightCustomRange();
    renderAll();
  });

  document.getElementById("province-filter").addEventListener("change", (event) => {
    state.province = event.target.value;
    state.city = "";
    populateLocationOptions();
    renderAll();
  });

  document.getElementById("city-filter").addEventListener("change", (event) => {
    state.city = event.target.value;
    renderAll();
  });
}

function initializeDates() {
  const { min_date: minDate, max_date: maxDate } = state.dataset.metadata;
  document.getElementById("dataset-range").textContent = `${minDate} 至 ${maxDate}`;
  state.endDate = maxDate;
  state.startDate = shiftDate(maxDate, -30);
  syncDateInputs();
  applyDateRangeMode();
}

function populateLocationOptions() {
  const provinceSelect = document.getElementById("province-filter");
  const citySelect = document.getElementById("city-filter");
  const rows = filteredStoreRows({ ignoreLocation: true });

  const provinces = uniqueValues(rows.map((row) => row.province)).sort((a, b) => a.localeCompare(b, "zh-CN"));
  provinceSelect.innerHTML = `<option value="">全部省份</option>${provinces
    .map((province) => `<option value="${province}" ${province === state.province ? "selected" : ""}>${province}</option>`)
    .join("")}`;

  const cities = uniqueValues(
    rows
      .filter((row) => !state.province || row.province === state.province)
      .map((row) => row.city),
  ).sort((a, b) => a.localeCompare(b, "zh-CN"));

  citySelect.innerHTML = `<option value="">全部城市</option>${cities
    .map((city) => `<option value="${city}" ${city === state.city ? "selected" : ""}>${city}</option>`)
    .join("")}`;
}

function toggleLocationFilters() {
  const isLocationView = state.currentView === "stores";
  document.querySelectorAll(".filter-location").forEach((node) => {
    node.style.display = isLocationView ? "grid" : "none";
  });
}

function highlightCustomRange() {
  document.querySelectorAll(".segment").forEach((item) => item.classList.remove("is-active"));
  document.querySelector('.segment[data-range="custom"]').classList.add("is-active");
}

function applyDateRangeMode() {
  const maxDate = state.dataset.metadata.max_date;
  if (state.rangeMode === "7") {
    state.endDate = maxDate;
    state.startDate = shiftDate(maxDate, -6);
  } else if (state.rangeMode === "31") {
    state.endDate = maxDate;
    state.startDate = shiftDate(maxDate, -30);
  }
  syncDateInputs();
}

function syncDateInputs() {
  document.getElementById("start-date").value = denormalizeInputDate(state.startDate);
  document.getElementById("end-date").value = denormalizeInputDate(state.endDate);
}

function filteredPlatformRows() {
  return state.dataset.platformDailySummary.filter((row) => {
    return isDateInRange(row.biz_date) && state.selectedPlatforms.has(row.platform);
  });
}

function filteredStoreRows(options = {}) {
  return state.dataset.storeDailySummary.filter((row) => {
    if (!isDateInRange(row.biz_date) || !state.selectedPlatforms.has(row.platform)) return false;
    if (!options.ignoreLocation && state.province && row.province !== state.province) return false;
    if (!options.ignoreLocation && state.city && row.city !== state.city) return false;
    return true;
  });
}

function filteredCityRows() {
  return state.dataset.cityDailySummary.filter((row) => {
    return isDateInRange(row.biz_date) && state.selectedPlatforms.has(row.platform);
  });
}

function isDateInRange(dateValue) {
  return dateValue >= state.startDate && dateValue <= state.endDate;
}

function renderAll() {
  renderOverview();
  renderTrends();
  renderStores();
  renderRegions();
  renderMappings();
  toggleLocationFilters();
}

function renderOverview() {
  const rows = filteredPlatformRows();
  const summary = aggregateOverview(rows);
  const revenueShare = aggregateByPlatform(rows, "revenue");
  const orderCompare = aggregateByPlatform(rows, "valid_orders");
  const ticketCompare = aggregateTicketByPlatform(rows);
  const coreTable = buildCoreTable(rows);

  document.getElementById("view-overview").innerHTML = `
    <div class="dashboard-grid">
      ${renderMetricCards([
        { label: "总营收", value: formatCurrency(summary.totalRevenue), sub: `统计周期 ${state.startDate} - ${state.endDate}` },
        { label: "总订单量", value: formatInteger(summary.totalOrders), sub: "三平台有效订单合计" },
        { label: "活跃门店", value: formatInteger(summary.activeStores), sub: "有效订单大于 0 的门店数" },
        { label: "覆盖省份", value: formatInteger(summary.coveredProvinces), sub: `覆盖城市 ${formatInteger(summary.coveredCities)} 个` },
      ])}

      <div class="chart-grid-2">
        <article class="panel-card">
          <div class="panel-header">
            <div>
              <h3>平台营收贡献占比</h3>
              <p class="panel-note">各平台收入占三平台总收入的比例</p>
            </div>
            <span class="mini-stat">总收入 ${formatCurrency(summary.totalRevenue)}</span>
          </div>
          <div class="donut-wrap">
            ${renderDonutChart(revenueShare)}
            <div class="legend-list">${renderRankList(revenueShare, "share", true, "share")}</div>
          </div>
        </article>

        <article class="panel-card">
          <div class="panel-header">
            <div>
              <h3>平台核心指标综合对比</h3>
              <p class="panel-note">营收、订单、占比和客单价的集中视图</p>
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
          <div class="rank-list">${renderRankList(orderCompare, "value")}</div>
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

function renderTrends() {
  const rows = filteredPlatformRows();
  const summary = aggregateOverview(rows);
  const trendMetrics = [
    { title: "营业收入趋势", key: "revenue", format: "currency" },
    { title: "订单量趋势", key: "valid_orders", format: "integer" },
    { title: "曝光量趋势", key: "exposure_users", format: "integer" },
    { title: "到手率趋势", key: "hand_rate", format: "percent" },
  ];

  document.getElementById("view-trends").innerHTML = `
    <div class="dashboard-grid">
      ${renderMetricCards([
        { label: "总营收", value: formatCurrency(summary.totalRevenue), sub: "趋势页汇总" },
        { label: "总订单量", value: formatInteger(summary.totalOrders), sub: "趋势页汇总" },
        { label: "活跃门店", value: formatInteger(summary.activeStores), sub: "趋势页汇总" },
        { label: "周期范围", value: `${state.startDate} - ${state.endDate}`, sub: "当前筛选区间" },
      ])}
      <div class="dashboard-grid">
        ${trendMetrics
          .map((metric) => {
            const series = buildTrendSeries(rows, metric.key);
            return `
              <article class="panel-card">
                <div class="panel-header">
                  <div>
                    <h3>${metric.title}</h3>
                    <p class="panel-note">统计周期内三平台按日期变化</p>
                  </div>
                </div>
                ${renderLineChart(series, metric.format)}
              </article>
            `;
          })
          .join("")}
      </div>
    </div>
  `;
}

function renderStores() {
  const rows = filteredStoreRows();
  const summary = aggregateStoreOverview(rows);
  const activeTrend = buildActiveStoreTrend(rows);
  const topRevenue = aggregateTopStores(rows, "revenue");
  const topOrders = aggregateTopStores(rows, "valid_orders");
  const topConversion = aggregateTopStores(rows, "order_conversion_rate", true);

  document.getElementById("view-stores").innerHTML = `
    <div class="dashboard-grid">
      ${renderMetricCards([
        { label: "总营收", value: formatCurrency(summary.totalRevenue), sub: locationSubtitle() },
        { label: "总订单量", value: formatInteger(summary.totalOrders), sub: locationSubtitle() },
        { label: "活跃门店", value: formatInteger(summary.activeStores), sub: "按门店明细统计" },
        { label: "统计区间", value: `${state.startDate} - ${state.endDate}`, sub: "支持省份 / 城市筛选" },
      ])}

      <article class="panel-card">
        <div class="panel-header">
          <div>
            <h3>活跃门店趋势</h3>
            <p class="panel-note">统计周期内三平台有效门店数变化</p>
          </div>
        </div>
        ${renderLineChart(activeTrend, "integer")}
      </article>

      <div class="chart-grid-3">
        <article class="panel-card">
          <div class="panel-header">
            <div>
              <h3>门店营收 Top20</h3>
              <p class="panel-note">按标准门店聚合</p>
            </div>
          </div>
          <div class="rank-list">${renderRankList(topRevenue, "value", false, "currency", true)}</div>
        </article>

        <article class="panel-card">
          <div class="panel-header">
            <div>
              <h3>门店订单量 Top20</h3>
              <p class="panel-note">按有效订单降序</p>
            </div>
          </div>
          <div class="rank-list">${renderRankList(topOrders, "value", false, "integer", true)}</div>
        </article>

        <article class="panel-card">
          <div class="panel-header">
            <div>
              <h3>门店转化率 Top20</h3>
              <p class="panel-note">按下单转化率排序</p>
            </div>
          </div>
          <div class="rank-list">${renderRankList(topConversion, "value", false, "percent", true)}</div>
        </article>
      </div>
    </div>
  `;
}

function renderRegions() {
  const rows = filteredCityRows();
  const summary = aggregateCityOverview(rows);
  const topRevenue = aggregateTopCities(rows, "revenue");
  const topOrders = aggregateTopCities(rows, "valid_orders");
  const topStoreCount = aggregateTopCities(rows, "store_count");

  document.getElementById("view-regions").innerHTML = `
    <div class="dashboard-grid">
      ${renderMetricCards([
        { label: "总营收", value: formatCurrency(summary.totalRevenue), sub: "地域分析汇总" },
        { label: "总订单量", value: formatInteger(summary.totalOrders), sub: "地域分析汇总" },
        { label: "覆盖城市", value: formatInteger(summary.coveredCities), sub: `覆盖省份 ${formatInteger(summary.coveredProvinces)} 个` },
        { label: "统计区间", value: `${state.startDate} - ${state.endDate}`, sub: "城市维度分析" },
      ])}

      <div class="chart-grid-3">
        <article class="panel-card">
          <div class="panel-header">
            <div>
              <h3>城市收入 Top20</h3>
              <p class="panel-note">按城市聚合营收</p>
            </div>
          </div>
          <div class="rank-list">${renderRankList(topRevenue, "value", false, "currency", true)}</div>
        </article>

        <article class="panel-card">
          <div class="panel-header">
            <div>
              <h3>城市订单量 Top20</h3>
              <p class="panel-note">按城市聚合订单</p>
            </div>
          </div>
          <div class="rank-list">${renderRankList(topOrders, "value", false, "integer", true)}</div>
        </article>

        <article class="panel-card">
          <div class="panel-header">
            <div>
              <h3>城市门店分布数 Top20</h3>
              <p class="panel-note">按标准门店数统计</p>
            </div>
          </div>
          <div class="rank-list">${renderRankList(topStoreCount, "value", false, "integer", true)}</div>
        </article>
      </div>
    </div>
  `;
}

function renderMappings() {
  const rows = state.dataset.storeMappings;
  const filtered = rows.filter((row) => {
    if (state.province && row.province !== state.province) return false;
    if (state.city && row.city !== state.city) return false;
    return true;
  });

  const total = filtered.length;
  const meituanOnline = filtered.filter((row) => row.meituan_store_id).length;
  const elemeOnline = filtered.filter((row) => row.eleme_store_id).length;
  const jdOnline = filtered.filter((row) => row.jd_store_id).length;

  document.getElementById("view-mappings").innerHTML = `
    <div class="dashboard-grid">
      ${renderMetricCards([
        { label: "标准门店数", value: formatInteger(total), sub: "当前筛选范围内的标准门店" },
        { label: "美团已映射", value: formatInteger(meituanOnline), sub: "门店 ID 已关联" },
        { label: "饿了么已映射", value: formatInteger(elemeOnline), sub: "门店 ID 已关联" },
        { label: "京东已映射", value: formatInteger(jdOnline), sub: "门店 ID 已关联" },
      ])}

      <article class="panel-card">
        <div class="panel-header">
          <div>
            <h3>门店映射关系表</h3>
            <p class="panel-note">展示标准门店与三平台门店 ID / 名称的对应关系</p>
          </div>
          <div class="mapping-meta">
            <span class="pill">美团 ${formatInteger(meituanOnline)}</span>
            <span class="pill">饿了么 ${formatInteger(elemeOnline)}</span>
            <span class="pill">京东 ${formatInteger(jdOnline)}</span>
          </div>
        </div>
        <div class="table-wrap">
          ${renderTable(
            ["标准门店", "省份", "城市", "运营", "美团", "饿了么", "京东"],
            filtered.slice(0, 120).map((row) => [
              row.standard_store_name || "-",
              row.province || "-",
              row.city || "-",
              row.operator_name || "-",
              formatMappingCell(row.meituan_store_id, row.meituan_store_name),
              formatMappingCell(row.eleme_store_id, row.eleme_store_name),
              formatMappingCell(row.jd_store_id, row.jd_store_name),
            ]),
          )}
        </div>
        <p class="empty-note">当前原型默认最多展示 120 行，正式版可改为分页或搜索。</p>
      </article>
    </div>
  `;
}

function renderMetricCards(items) {
  return `
    <div class="metric-grid">
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
      <text x="110" y="102" text-anchor="middle" font-size="14" fill="${"#756455"}">三平台</text>
      <text x="110" y="126" text-anchor="middle" font-size="26" font-weight="700" fill="${"#2f241c"}">${items.length}</text>
    </svg>
  `;
}

function renderRankList(items, key, showShare = false, format = "number", showPlatform = false) {
  const max = Math.max(...items.map((item) => item[key] || 0), 0);
  return items
    .map((item, index) => {
      const value = item[key] || 0;
      const width = max ? (value / max) * 100 : 0;
      const label = showPlatform ? `${index + 1}. ${item.label} · ${item.platform}` : `${index + 1}. ${item.label}`;
      return `
        <div class="rank-item">
          <div class="rank-top">
            <span>${label}</span>
            <span>${formatValue(value, format)}${showShare ? ` · ${formatPercent(item.share)}` : ""}</span>
          </div>
          <div class="bar-track"><div class="bar-fill" style="width:${width}%"></div></div>
        </div>
      `;
    })
    .join("");
}

function renderLineChart(seriesByPlatform, format) {
  const allPoints = Object.values(seriesByPlatform).flat();
  const width = 960;
  const height = 260;
  const padding = 32;
  const minValue = Math.min(...allPoints.map((point) => point.value), 0);
  const maxValue = Math.max(...allPoints.map((point) => point.value), 1);
  const dates = uniqueValues(allPoints.map((point) => point.date)).sort();

  const xForIndex = (index) => {
    if (dates.length <= 1) return padding;
    return padding + (index / (dates.length - 1)) * (width - padding * 2);
  };
  const yForValue = (value) => {
    if (maxValue === minValue) return height / 2;
    return height - padding - ((value - minValue) / (maxValue - minValue)) * (height - padding * 2);
  };

  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((step) => {
    const y = padding + step * (height - padding * 2);
    return `<line x1="${padding}" y1="${y}" x2="${width - padding}" y2="${y}" stroke="rgba(97,72,49,0.08)" stroke-dasharray="4 6"></line>`;
  });

  const polylines = Object.entries(seriesByPlatform)
    .map(([platform, points]) => {
      const pointMap = new Map(points.map((point) => [point.date, point.value]));
      const mapped = dates.map((date, index) => ({
        x: xForIndex(index),
        y: yForValue(pointMap.get(date) ?? minValue),
      }));
      const path = mapped.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
      return `
        <path d="${path}" fill="none" stroke="${chartColors[platform]}" stroke-width="3" stroke-linecap="round"></path>
        ${mapped
          .map(
            (point) =>
              `<circle cx="${point.x}" cy="${point.y}" r="3.5" fill="${chartColors[platform]}" stroke="#fff7ef" stroke-width="1.5"></circle>`,
          )
          .join("")}
      `;
    })
    .join("");

  const labels = dates
    .filter((_, index) => index === 0 || index === dates.length - 1 || index % Math.ceil(dates.length / 6) === 0)
    .map((date) => {
      const index = dates.indexOf(date);
      return `<text x="${xForIndex(index)}" y="${height - 8}" text-anchor="middle" font-size="11" fill="#756455">${date.slice(
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
      const latest = points[points.length - 1];
      return `<span class="pill" style="background:${hexToSoft(chartColors[platform])};color:${chartColors[platform]}">${platform} ${formatValue(
        latest?.value ?? 0,
        format,
      )}</span>`;
    })
    .join("");

  return `
    <div class="panel-note">${legends}</div>
    <svg class="line-chart" viewBox="0 0 ${width} ${height}">
      ${gridLines.join("")}
      ${polylines}
      ${labels}
    </svg>
    <div class="mapping-meta" style="margin-top:14px;">${latestSummary}</div>
  `;
}

function renderTable(headers, rows) {
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

function aggregateOverview(rows) {
  const storeSet = new Set();
  const provinceSet = new Set();
  const citySet = new Set();

  let totalRevenue = 0;
  let totalOrders = 0;

  rows.forEach((row) => {
    totalRevenue += Number(row.revenue || 0);
    totalOrders += Number(row.valid_orders || 0);
    if (Number(row.active_store_count || 0) > 0) storeSet.add(`${row.platform}:${row.biz_date}`);
    if (row.province_count) {
      provinceSet.add(row.biz_date);
    }
    if (row.city_count) {
      citySet.add(row.biz_date);
    }
  });

  const rawStoreRows = filteredStoreRows();
  const activeStoreIds = new Set(
    rawStoreRows.filter((row) => Number(row.valid_orders || 0) > 0).map((row) => row.standard_store_id),
  );
  const provinces = uniqueValues(rawStoreRows.map((row) => row.province));
  const cities = uniqueValues(rawStoreRows.map((row) => row.city));

  return {
    totalRevenue,
    totalOrders,
    activeStores: activeStoreIds.length,
    coveredProvinces: provinces.length,
    coveredCities: cities.length,
  };
}

function aggregateStoreOverview(rows) {
  return {
    totalRevenue: sum(rows, "revenue"),
    totalOrders: sum(rows, "valid_orders"),
    activeStores: uniqueValues(rows.filter((row) => Number(row.valid_orders || 0) > 0).map((row) => row.standard_store_id)).length,
  };
}

function aggregateCityOverview(rows) {
  return {
    totalRevenue: sum(rows, "revenue"),
    totalOrders: sum(rows, "valid_orders"),
    coveredCities: uniqueValues(rows.map((row) => row.city)).length,
    coveredProvinces: uniqueValues(rows.map((row) => row.province)).length,
  };
}

function aggregateByPlatform(rows, field) {
  const map = new Map();
  rows.forEach((row) => {
    const platform = row.platform;
    map.set(platform, (map.get(platform) || 0) + Number(row[field] || 0));
  });
  const total = [...map.values()].reduce((sum, value) => sum + value, 0);
  return [...map.entries()]
    .map(([label, value]) => ({ label, value, share: total ? value / total : 0 }))
    .sort((a, b) => b.value - a.value);
}

function aggregateTicketByPlatform(rows) {
  const map = new Map();
  rows.forEach((row) => {
    if (!map.has(row.platform)) {
      map.set(row.platform, { paid: 0, orders: 0 });
    }
    const current = map.get(row.platform);
    current.paid += Number(row.customer_paid || 0);
    current.orders += Number(row.valid_orders || 0);
  });
  return [...map.entries()]
    .map(([label, current]) => ({
      label,
      avgTicket: current.orders ? current.paid / current.orders : 0,
    }))
    .sort((a, b) => b.avgTicket - a.avgTicket);
}

function buildCoreTable(rows) {
  const revenueRows = aggregateByPlatform(rows, "revenue");
  const orderRows = aggregateByPlatform(rows, "valid_orders");
  const ticketRows = aggregateTicketByPlatform(rows);
  const orderMap = new Map(orderRows.map((row) => [row.label, row]));
  const ticketMap = new Map(ticketRows.map((row) => [row.label, row]));

  return {
    headers: ["平台", "营业收入", "收入占比", "订单量", "订单占比", "客单价"],
    rows: revenueRows.map((row) => [
      row.label,
      formatCurrency(row.value),
      formatPercent(row.share),
      formatInteger(orderMap.get(row.label)?.value || 0),
      formatPercent(orderMap.get(row.label)?.share || 0),
      formatCurrency(ticketMap.get(row.label)?.avgTicket || 0),
    ]),
  };
}

function buildTrendSeries(rows, field) {
  const grouped = new Map();
  rows.forEach((row) => {
    const key = `${row.platform}__${row.biz_date}`;
    const current = grouped.get(key) || { platform: row.platform, date: row.biz_date, value: 0, gross: 0, revenue: 0 };
    if (field === "hand_rate") {
      current.gross += Number(row.gross_amount || 0);
      current.revenue += Number(row.revenue || 0);
      current.value = current.gross ? current.revenue / current.gross : 0;
    } else {
      current.value += Number(row[field] || 0);
    }
    grouped.set(key, current);
  });

  const result = {};
  [...grouped.values()].forEach((item) => {
    if (!result[item.platform]) result[item.platform] = [];
    result[item.platform].push({ date: item.date, value: item.value });
  });

  Object.keys(result).forEach((platform) => {
    result[platform].sort((a, b) => a.date.localeCompare(b.date));
  });
  return result;
}

function buildActiveStoreTrend(rows) {
  const grouped = new Map();
  rows.forEach((row) => {
    if (!row.standard_store_id || Number(row.valid_orders || 0) <= 0) return;
    const key = `${row.platform}__${row.biz_date}`;
    if (!grouped.has(key)) {
      grouped.set(key, new Set());
    }
    grouped.get(key).add(row.standard_store_id);
  });

  const result = {};
  [...grouped.entries()].forEach(([key, stores]) => {
    const [platform, date] = key.split("__");
    if (!result[platform]) result[platform] = [];
    result[platform].push({ date, value: stores.size });
  });

  Object.keys(result).forEach((platform) => {
    result[platform].sort((a, b) => a.date.localeCompare(b.date));
  });
  return result;
}

function aggregateTopStores(rows, field, useAverage = false) {
  const grouped = new Map();
  rows.forEach((row) => {
    const label = row.standard_store_name || row.platform_store_name || "未命名门店";
    const key = `${label}__${row.platform}`;
    const current = grouped.get(key) || {
      label,
      platform: row.platform,
      province: row.province,
      city: row.city,
      total: 0,
      count: 0,
    };
    current.total += Number(row[field] || 0);
    current.count += 1;
    grouped.set(key, current);
  });

  return [...grouped.values()]
    .map((item) => ({
      label: item.label,
      platform: item.platform,
      value: useAverage ? item.total / item.count : item.total,
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 20);
}

function aggregateTopCities(rows, field) {
  const grouped = new Map();
  rows.forEach((row) => {
    const label = `${row.province || "-"} / ${row.city || "-"}`;
    const key = `${label}__${row.platform}`;
    const current = grouped.get(key) || { label, platform: row.platform, value: 0 };
    current.value += Number(row[field] || 0);
    grouped.set(key, current);
  });
  return [...grouped.values()].sort((a, b) => b.value - a.value).slice(0, 20);
}

function locationSubtitle() {
  if (state.province && state.city) return `${state.province} · ${state.city}`;
  if (state.province) return `${state.province} 范围`;
  return "全部省份 / 城市";
}

function formatMappingCell(id, name) {
  if (!id) return "未映射";
  return `${id}<br><span class="mini-stat">${name || "-"}</span>`;
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

function sum(rows, field) {
  return rows.reduce((total, row) => total + Number(row[field] || 0), 0);
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

function formatInteger(value) {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(Number(value || 0));
}

function formatPercent(value) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`;
}

function formatValue(value, format) {
  if (format === "currency") return formatCurrency(value);
  if (format === "integer") return formatInteger(value);
  if (format === "percent") return formatPercent(value);
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(Number(value || 0));
}

function hexToSoft(hex) {
  const value = hex.replace("#", "");
  const bigint = parseInt(value, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return `rgba(${r}, ${g}, ${b}, 0.14)`;
}
