from __future__ import annotations

import json
import sqlite3
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "src" / "warehouse" / "web_kanban.db"


@dataclass
class QueryFilters:
    start_date: str
    end_date: str
    platforms: tuple[str, ...] = ("美团", "饿了么", "京东")
    province: str | None = None
    city: str | None = None


PLATFORMS = ("美团", "饿了么", "京东")
MANUAL_CITY_PROVINCE_MAP = {
    "沧州": "河北",
    "济南": "山东",
    "西安": "陕西",
    "贵港": "广西壮族",
}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _is_real_mapping_id(value: Any) -> bool:
    return bool(value and value != "未入驻平台")


@lru_cache(maxsize=1)
def _city_province_map() -> dict[str, str]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT city, MIN(province) AS province
            FROM dwd_platform_daily_normalized
            WHERE city IS NOT NULL
              AND city != ''
              AND province IS NOT NULL
              AND province != ''
            GROUP BY city
            """
        ).fetchall()

    mapping = {row["city"]: row["province"] for row in rows}
    for city, province in MANUAL_CITY_PROVINCE_MAP.items():
        mapping.setdefault(city, province)
    return mapping


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _resolved_province_sql(city_column: str = "city", province_column: str = "province") -> str:
    city_map = _city_province_map()
    cases = " ".join(
        f"WHEN {city_column} = {_sql_string(city)} THEN {_sql_string(province)}"
        for city, province in sorted(city_map.items())
    )
    return f"COALESCE(NULLIF({province_column}, ''), CASE {cases} END)"


def _where_clause(filters: QueryFilters, include_location: bool = False) -> tuple[str, list[Any]]:
    clauses = ["biz_date >= ?", "biz_date <= ?"]
    params: list[Any] = [filters.start_date, filters.end_date]

    if filters.platforms:
        placeholders = ",".join("?" for _ in filters.platforms)
        clauses.append(f"platform IN ({placeholders})")
        params.extend(filters.platforms)

    if include_location and filters.province:
        clauses.append(f"{_resolved_province_sql()} = ?")
        params.append(filters.province)

    if include_location and filters.city:
        clauses.append("city = ?")
        params.append(filters.city)

    return " WHERE " + " AND ".join(clauses), params


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y/%m/%d").date()


def _format_date(value: date) -> str:
    return value.strftime("%Y/%m/%d")


def _previous_period_filters(filters: QueryFilters) -> QueryFilters:
    start_date = _parse_date(filters.start_date)
    end_date = _parse_date(filters.end_date)
    period_days = (end_date - start_date).days + 1
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=period_days - 1)
    return QueryFilters(
        start_date=_format_date(previous_start),
        end_date=_format_date(previous_end),
        platforms=filters.platforms,
        province=filters.province,
        city=filters.city,
    )


def _compute_change_rate(current_value: float, previous_value: float) -> float | None:
    if previous_value == 0:
        return 0.0 if current_value == 0 else None
    return (current_value - previous_value) / previous_value


def fetch_overview_summary(filters: QueryFilters) -> dict[str, Any]:
    province_sql = _resolved_province_sql()
    sql_template = f"""
        SELECT
            COALESCE(SUM(revenue), 0) AS total_revenue,
            COALESCE(SUM(valid_orders), 0) AS total_orders,
            COUNT(
                DISTINCT CASE
                    WHEN active_store_flag = 1 THEN COALESCE(standard_store_id, platform || ':' || platform_store_id)
                END
            ) AS active_stores,
            COUNT(DISTINCT {province_sql}) AS covered_provinces,
            COUNT(DISTINCT city) AS covered_cities
        FROM dwd_platform_daily_normalized
        {{where_sql}}
    """
    where_sql, params = _where_clause(filters, include_location=True)
    sql = sql_template.format(where_sql=where_sql)
    with _connect() as conn:
        current_row = dict(conn.execute(sql, params).fetchone())
        previous_filters = _previous_period_filters(filters)
        previous_where_sql, previous_params = _where_clause(previous_filters, include_location=True)
        previous_sql = sql_template.format(where_sql=previous_where_sql)
        previous_row = dict(conn.execute(previous_sql, previous_params).fetchone())

    current_row["previous_total_revenue"] = previous_row["total_revenue"]
    current_row["previous_total_orders"] = previous_row["total_orders"]
    current_row["revenue_change_rate"] = _compute_change_rate(
        float(current_row["total_revenue"] or 0),
        float(previous_row["total_revenue"] or 0),
    )
    current_row["orders_change_rate"] = _compute_change_rate(
        float(current_row["total_orders"] or 0),
        float(previous_row["total_orders"] or 0),
    )
    current_row["previous_start_date"] = previous_filters.start_date
    current_row["previous_end_date"] = previous_filters.end_date
    return current_row


def fetch_revenue_share(filters: QueryFilters) -> list[dict[str, Any]]:
    where_sql, params = _where_clause(filters)
    sql = f"""
        SELECT
            platform,
            COALESCE(SUM(revenue), 0) AS revenue
        FROM dwd_platform_daily_normalized
        {where_sql}
        GROUP BY platform
        ORDER BY revenue DESC
    """
    with _connect() as conn:
        rows = [dict(row) for row in conn.execute(sql, params).fetchall()]

    total = sum(row["revenue"] for row in rows)
    for row in rows:
        row["share"] = row["revenue"] / total if total else None
    return rows


def fetch_order_compare(filters: QueryFilters) -> list[dict[str, Any]]:
    where_sql, params = _where_clause(filters)
    sql = f"""
        SELECT
            platform,
            COALESCE(SUM(valid_orders), 0) AS valid_orders
        FROM dwd_platform_daily_normalized
        {where_sql}
        GROUP BY platform
        ORDER BY valid_orders DESC
    """
    with _connect() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def fetch_ticket_compare(filters: QueryFilters) -> list[dict[str, Any]]:
    where_sql, params = _where_clause(filters)
    sql = f"""
        SELECT
            platform,
            COALESCE(SUM(customer_paid), 0) AS customer_paid,
            COALESCE(SUM(valid_orders), 0) AS valid_orders
        FROM dwd_platform_daily_normalized
        {where_sql}
        GROUP BY platform
        ORDER BY customer_paid DESC
    """
    with _connect() as conn:
        rows = [dict(row) for row in conn.execute(sql, params).fetchall()]

    for row in rows:
        row["avg_ticket"] = row["customer_paid"] / row["valid_orders"] if row["valid_orders"] else None
    return rows


def fetch_core_table(filters: QueryFilters) -> list[dict[str, Any]]:
    revenue_rows = fetch_revenue_share(filters)
    order_rows = {row["platform"]: row for row in fetch_order_compare(filters)}
    ticket_rows = {row["label"] if "label" in row else row["platform"]: row for row in fetch_ticket_compare(filters)}

    total_orders = sum(row["valid_orders"] for row in order_rows.values())
    result = []
    for row in revenue_rows:
        platform = row["platform"]
        order_item = order_rows.get(platform, {})
        ticket_item = ticket_rows.get(platform, {})
        valid_orders = order_item.get("valid_orders", 0)
        result.append(
            {
                "platform": platform,
                "revenue": row["revenue"],
                "revenue_share": row["share"],
                "valid_orders": valid_orders,
                "order_share": valid_orders / total_orders if total_orders else None,
                "avg_ticket": ticket_item.get("avg_ticket"),
            }
        )
    return result


def fetch_growth_efficiency(filters: QueryFilters) -> list[dict[str, Any]]:
    where_sql, params = _where_clause(filters)
    sql = f"""
        SELECT
            platform,
            COALESCE(SUM(exposure_users), 0) AS exposure_users,
            COALESCE(SUM(visit_users), 0) AS visit_users,
            COALESCE(SUM(valid_orders), 0) AS valid_orders,
            COALESCE(SUM(revenue), 0) AS revenue,
            AVG(visit_conversion_rate) AS visit_conversion_rate,
            AVG(order_conversion_rate) AS order_conversion_rate
        FROM dwd_platform_daily_normalized
        {where_sql}
        GROUP BY platform
        ORDER BY revenue DESC
    """
    with _connect() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def fetch_trend(filters: QueryFilters, metric: str) -> list[dict[str, Any]]:
    metric_sql = {
        "revenue": "COALESCE(SUM(revenue), 0)",
        "orders": "COALESCE(SUM(valid_orders), 0)",
        "exposure_users": "COALESCE(SUM(exposure_users), 0)",
        "visit_users": "COALESCE(SUM(visit_users), 0)",
        "visit_conversion_rate": "AVG(visit_conversion_rate)",
        "order_conversion_rate": "AVG(order_conversion_rate)",
        "hand_rate": "CASE WHEN SUM(gross_amount) = 0 THEN NULL ELSE SUM(revenue) * 1.0 / SUM(gross_amount) END",
        "active_stores": """
            COUNT(
                DISTINCT CASE
                    WHEN active_store_flag = 1 THEN COALESCE(standard_store_id, platform || ':' || platform_store_id)
                END
            )
        """,
    }
    if metric not in metric_sql:
        raise ValueError(f"不支持的趋势指标: {metric}")

    where_sql, params = _where_clause(filters, include_location=True)
    sql = f"""
        SELECT
            biz_date,
            platform,
            {metric_sql[metric]} AS metric_value
        FROM dwd_platform_daily_normalized
        {where_sql}
        GROUP BY biz_date, platform
        ORDER BY biz_date, platform
    """
    with _connect() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def fetch_store_top20(filters: QueryFilters, metric: str, limit: int = 20) -> list[dict[str, Any]]:
    metric_sql = {
        "revenue": "COALESCE(SUM(revenue), 0)",
        "orders": "COALESCE(SUM(valid_orders), 0)",
        "order_conversion_rate": "AVG(order_conversion_rate)",
    }
    if metric not in metric_sql:
        raise ValueError(f"不支持的门店 TopN 指标: {metric}")

    where_sql, params = _where_clause(filters, include_location=True)
    aggregate_across_platforms = metric in {"revenue", "orders"} and len(filters.platforms) > 1
    if aggregate_across_platforms:
        sql = f"""
            SELECT
                standard_store_id,
                standard_store_name,
                province,
                city,
                NULL AS platform,
                GROUP_CONCAT(DISTINCT platform) AS platform_scope,
                COUNT(DISTINCT platform) AS platform_count,
                {metric_sql[metric]} AS metric_value
            FROM dwd_platform_daily_normalized
            {where_sql}
            GROUP BY standard_store_id, standard_store_name, province, city
            ORDER BY metric_value DESC
            LIMIT ?
        """
    else:
        sql = f"""
            SELECT
                standard_store_id,
                standard_store_name,
                province,
                city,
                platform,
                platform AS platform_scope,
                1 AS platform_count,
                {metric_sql[metric]} AS metric_value
            FROM dwd_platform_daily_normalized
            {where_sql}
            GROUP BY standard_store_id, standard_store_name, province, city, platform
            ORDER BY metric_value DESC
            LIMIT ?
        """
    with _connect() as conn:
        return [dict(row) for row in conn.execute(sql, [*params, limit]).fetchall()]


def _fetch_store_growth_rows(filters: QueryFilters) -> list[dict[str, Any]]:
    where_sql, params = _where_clause(filters, include_location=True)
    sql = f"""
        SELECT
            standard_store_id,
            standard_store_name,
            province,
            city,
            platform,
            COALESCE(SUM(exposure_users), 0) AS exposure_users,
            COALESCE(SUM(valid_orders), 0) AS valid_orders,
            AVG(order_conversion_rate) AS order_conversion_rate
        FROM dwd_platform_daily_normalized
        {where_sql}
        GROUP BY standard_store_id, standard_store_name, province, city, platform
        HAVING standard_store_id IS NOT NULL
    """
    with _connect() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(statistics.median(values))


def fetch_store_opportunity_low_conversion(filters: QueryFilters, limit: int = 10) -> list[dict[str, Any]]:
    rows = _fetch_store_growth_rows(filters)
    if not rows:
        return []

    exposure_median = _median([float(row["exposure_users"] or 0) for row in rows])
    orders_median = _median([float(row["valid_orders"] or 0) for row in rows])
    conversion_median = _median(
        [float(row["order_conversion_rate"] or 0) for row in rows if row["order_conversion_rate"] is not None]
    )

    candidates = [
        row
        for row in rows
        if float(row["exposure_users"] or 0) >= exposure_median
        and float(row["valid_orders"] or 0) >= orders_median
        and float(row["order_conversion_rate"] or 0) <= conversion_median
    ]

    candidates.sort(
        key=lambda row: (
            -float(row["exposure_users"] or 0),
            float(row["order_conversion_rate"] or 0),
            -float(row["valid_orders"] or 0),
        )
    )
    return candidates[:limit]


def fetch_store_opportunity_low_exposure(filters: QueryFilters, limit: int = 10) -> list[dict[str, Any]]:
    rows = _fetch_store_growth_rows(filters)
    if not rows:
        return []

    exposure_median = _median([float(row["exposure_users"] or 0) for row in rows])
    orders_median = _median([float(row["valid_orders"] or 0) for row in rows])
    conversions = [float(row["order_conversion_rate"] or 0) for row in rows if row["order_conversion_rate"] is not None]
    conversion_p75 = statistics.quantiles(conversions, n=4)[2] if len(conversions) >= 4 else _median(conversions)

    candidates = [
        row
        for row in rows
        if float(row["exposure_users"] or 0) <= exposure_median
        and float(row["valid_orders"] or 0) >= orders_median
        and float(row["order_conversion_rate"] or 0) >= float(conversion_p75 or 0)
    ]

    candidates.sort(
        key=lambda row: (
            -float(row["order_conversion_rate"] or 0),
            float(row["exposure_users"] or 0),
            -float(row["valid_orders"] or 0),
        )
    )
    return candidates[:limit]


def fetch_city_top20(filters: QueryFilters, metric: str) -> list[dict[str, Any]]:
    if metric == "store_count":
        sql = """
            SELECT
                province,
                city,
                '' AS platform,
                COUNT(DISTINCT standard_store_id) AS metric_value
            FROM dim_standard_store
            WHERE standard_store_id IS NOT NULL
              AND standard_store_id != ''
              AND city IS NOT NULL
              AND city != ''
            GROUP BY province, city
            ORDER BY metric_value DESC, province, city
            LIMIT 20
        """
        with _connect() as conn:
            return [dict(row) for row in conn.execute(sql).fetchall()]

    aggregate_city = len(tuple(platform for platform in filters.platforms if platform in PLATFORMS)) > 1
    metric_sql = {
        "revenue": "COALESCE(SUM(revenue), 0)",
        "orders": "COALESCE(SUM(valid_orders), 0)",
        "revenue_per_store": "COALESCE(SUM(revenue), 0) / NULLIF(COUNT(DISTINCT COALESCE(standard_store_id, platform || ':' || platform_store_id)), 0)",
    }
    if metric not in metric_sql:
        raise ValueError(f"不支持的城市 Top20 指标: {metric}")

    where_sql, params = _where_clause(filters)
    province_sql = _resolved_province_sql()
    platform_sql = "'' AS platform," if aggregate_city else "platform,"
    group_by_sql = f"GROUP BY {province_sql}, city" if aggregate_city else f"GROUP BY {province_sql}, city, platform"
    extra_fields = ""
    if metric == "revenue_per_store":
        extra_fields = """
            COUNT(DISTINCT COALESCE(standard_store_id, platform || ':' || platform_store_id)) AS store_count,
        """
    sql = f"""
        SELECT
            {province_sql} AS province,
            city,
            {platform_sql}
            {extra_fields}
            {metric_sql[metric]} AS metric_value
        FROM dwd_platform_daily_normalized
        {where_sql}
        {group_by_sql}
        ORDER BY metric_value DESC
        LIMIT 20
    """
    with _connect() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _filter_mapping_rows(
    rows: list[dict[str, Any]],
    keyword: str | None = None,
    mapping_filter: str | None = None,
    platforms: tuple[str, ...] = PLATFORMS,
    province: str | None = None,
    city: str | None = None,
    district: str | None = None,
) -> list[dict[str, Any]]:
    if province:
        rows = [row for row in rows if (row.get("province") or "") == province]
    if city:
        rows = [row for row in rows if (row.get("city") or "") == city]
    if district:
        rows = [row for row in rows if (row.get("district") or "") == district]

    if keyword:
        needle = keyword.strip().lower()
        rows = [
            row
            for row in rows
            if needle
            in " ".join(
                str(row.get(field) or "")
                for field in (
                    "standard_store_id",
                    "standard_store_name",
                    "meituan_store_id",
                    "meituan_store_name",
                    "eleme_store_id",
                    "eleme_store_name",
                    "jd_store_id",
                    "jd_store_name",
                )
            ).lower()
        ]

    selected_platforms = tuple(platform for platform in platforms if platform in PLATFORMS) or PLATFORMS
    if mapping_filter == "fully-unmapped":
        rows = [
            row
            for row in rows
            if not any(
                _is_real_mapping_id(row.get(field))
                for field in ("meituan_store_id", "eleme_store_id", "jd_store_id")
            )
        ]
    elif mapping_filter == "selected-platform-unmapped":
        field_map = {
            "美团": "meituan_store_id",
            "饿了么": "eleme_store_id",
            "京东": "jd_store_id",
        }
        rows = [
            row
            for row in rows
            if any(not _is_real_mapping_id(row.get(field_map[platform])) for platform in selected_platforms)
        ]
    elif mapping_filter == "selected-platform-fully-mapped":
        field_map = {
            "美团": "meituan_store_id",
            "饿了么": "eleme_store_id",
            "京东": "jd_store_id",
        }
        rows = [
            row
            for row in rows
            if all(_is_real_mapping_id(row.get(field_map[platform])) for platform in selected_platforms)
        ]

    return rows


def fetch_store_mapping_list(
    limit: int | None = 200,
    keyword: str | None = None,
    mapping_filter: str | None = None,
    platforms: tuple[str, ...] = PLATFORMS,
    province: str | None = None,
    city: str | None = None,
    district: str | None = None,
) -> list[dict[str, Any]]:
    sql = """
        SELECT
            s.standard_store_id,
            s.standard_store_name,
            s.province,
            s.city,
            s.district,
            MAX(CASE WHEN m.platform = '美团' THEN m.platform_store_id END) AS meituan_store_id,
            MAX(CASE WHEN m.platform = '美团' THEN m.platform_store_name END) AS meituan_store_name,
            MAX(CASE WHEN m.platform = '饿了么' THEN m.platform_store_id END) AS eleme_store_id,
            MAX(CASE WHEN m.platform = '饿了么' THEN m.platform_store_name END) AS eleme_store_name,
            MAX(CASE WHEN m.platform = '京东' THEN m.platform_store_id END) AS jd_store_id,
            MAX(CASE WHEN m.platform = '京东' THEN m.platform_store_name END) AS jd_store_name
        FROM dim_standard_store s
        LEFT JOIN bridge_platform_store_mapping m
          ON s.standard_store_id = m.standard_store_id
        GROUP BY s.standard_store_id, s.standard_store_name, s.province, s.city, s.district
        ORDER BY s.standard_store_name
    """
    with _connect() as conn:
        rows = [dict(row) for row in conn.execute(sql).fetchall()]

    rows = _filter_mapping_rows(
        rows,
        keyword=keyword,
        mapping_filter=mapping_filter,
        platforms=platforms,
        province=province,
        city=city,
        district=district,
    )
    if limit is not None:
        rows = rows[:limit]

    return rows


def fetch_store_mapping_summary(
    platforms: tuple[str, ...] = PLATFORMS,
    keyword: str | None = None,
    mapping_filter: str | None = None,
    province: str | None = None,
    city: str | None = None,
    district: str | None = None,
) -> dict[str, Any]:
    rows = fetch_store_mapping_list(
        limit=None,
        keyword=keyword,
        mapping_filter=mapping_filter,
        platforms=platforms,
        province=province,
        city=city,
        district=district,
    )
    selected_platforms = tuple(platform for platform in platforms if platform in PLATFORMS) or PLATFORMS

    selected_mapped_count = 0
    meituan_mapped_count = 0
    eleme_mapped_count = 0
    jd_mapped_count = 0

    for row in rows:
        meituan_mapped = _is_real_mapping_id(row.get("meituan_store_id"))
        eleme_mapped = _is_real_mapping_id(row.get("eleme_store_id"))
        jd_mapped = _is_real_mapping_id(row.get("jd_store_id"))

        if meituan_mapped:
            meituan_mapped_count += 1
        if eleme_mapped:
            eleme_mapped_count += 1
        if jd_mapped:
            jd_mapped_count += 1

        selected_flags = {
            "美团": meituan_mapped,
            "饿了么": eleme_mapped,
            "京东": jd_mapped,
        }
        if any(selected_flags[platform] for platform in selected_platforms):
            selected_mapped_count += 1

    standard_store_count = len(rows)
    selected_unmapped_count = standard_store_count - selected_mapped_count

    return {
        "standard_store_count": standard_store_count,
        "selected_platforms": list(selected_platforms),
        "selected_mapped_count": selected_mapped_count,
        "selected_unmapped_count": selected_unmapped_count,
        "meituan_mapped_count": meituan_mapped_count,
        "eleme_mapped_count": eleme_mapped_count,
        "jd_mapped_count": jd_mapped_count,
    }


def fetch_filter_options() -> dict[str, Any]:
    province_sql = _resolved_province_sql()
    with _connect() as conn:
        provinces = [
            row["province"]
            for row in conn.execute(
                f"""
                SELECT DISTINCT {province_sql} AS province
                FROM dwd_platform_daily_normalized
                WHERE {province_sql} IS NOT NULL AND {province_sql} != ''
                ORDER BY province
                """
            ).fetchall()
        ]
        location_rows = conn.execute(
            f"""
            SELECT DISTINCT {province_sql} AS province, city
            FROM dwd_platform_daily_normalized
            WHERE {province_sql} IS NOT NULL
              AND {province_sql} != ''
              AND city IS NOT NULL
              AND city != ''
            ORDER BY province, city
            """
        ).fetchall()
        cities = [
            row["city"]
            for row in conn.execute(
                """
                SELECT DISTINCT city
                FROM dwd_platform_daily_normalized
                WHERE city IS NOT NULL AND city != ''
                ORDER BY city
                """
            ).fetchall()
        ]
        meta = dict(
            conn.execute(
                """
                SELECT MIN(biz_date) AS min_date, MAX(biz_date) AS max_date
                FROM dwd_platform_daily_normalized
                """
            ).fetchone()
        )
        mapping_location_rows = conn.execute(
            """
            SELECT DISTINCT province, city, district
            FROM dim_standard_store
            WHERE COALESCE(NULLIF(province, ''), NULLIF(city, ''), NULLIF(district, '')) IS NOT NULL
            ORDER BY province, city, district
            """
        ).fetchall()

    location_map: dict[str, list[str]] = {}
    for row in location_rows:
        province = row["province"]
        city = row["city"]
        location_map.setdefault(province, []).append(city)

    mapping_location_map: dict[str, dict[str, set[str]]] = {}
    for row in mapping_location_rows:
        province = (row["province"] or "").strip()
        city = (row["city"] or "").strip()
        district = (row["district"] or "").strip()
        if not province:
            continue
        city_map = mapping_location_map.setdefault(province, {})
        if city:
            city_map.setdefault(city, set())
            if district:
                city_map[city].add(district)

    return {
        "platforms": ["美团", "饿了么", "京东"],
        "provinces": provinces,
        "cities": cities,
        "locations": [
            {
                "province": province,
                "cities": sorted(set(province_cities)),
            }
            for province, province_cities in location_map.items()
        ],
        "mapping_locations": [
            {
                "province": province,
                "cities": [
                    {
                        "city": city,
                        "districts": sorted(districts),
                    }
                    for city, districts in sorted(city_map.items())
                ],
            }
            for province, city_map in sorted(mapping_location_map.items())
        ],
        **meta,
    }


def main() -> None:
    filters = QueryFilters(start_date="2026/04/01", end_date="2026/04/26")
    preview = {
        "overview_summary": fetch_overview_summary(filters),
        "revenue_share": fetch_revenue_share(filters),
        "order_compare": fetch_order_compare(filters),
        "ticket_compare": fetch_ticket_compare(filters),
        "revenue_trend_sample": fetch_trend(filters, "revenue")[:6],
        "store_top20_sample": fetch_store_top20(filters, "revenue")[:5],
        "city_top20_sample": fetch_city_top20(filters, "revenue")[:5],
    }
    print(json.dumps(preview, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
