from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "warehouse" / "web_kanban.db"


@dataclass
class QueryFilters:
    start_date: str
    end_date: str
    platforms: tuple[str, ...] = ("美团", "饿了么", "京东")
    province: str | None = None
    city: str | None = None


PLATFORMS = ("美团", "饿了么", "京东")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _is_real_mapping_id(value: Any) -> bool:
    return bool(value and value != "未入驻平台")


def _where_clause(filters: QueryFilters, include_location: bool = False) -> tuple[str, list[Any]]:
    clauses = ["biz_date >= ?", "biz_date <= ?"]
    params: list[Any] = [filters.start_date, filters.end_date]

    if filters.platforms:
        placeholders = ",".join("?" for _ in filters.platforms)
        clauses.append(f"platform IN ({placeholders})")
        params.extend(filters.platforms)

    if include_location and filters.province:
        clauses.append("province = ?")
        params.append(filters.province)

    if include_location and filters.city:
        clauses.append("city = ?")
        params.append(filters.city)

    return " WHERE " + " AND ".join(clauses), params


def fetch_overview_summary(filters: QueryFilters) -> dict[str, Any]:
    where_sql, params = _where_clause(filters, include_location=True)
    sql = f"""
        SELECT
            COALESCE(SUM(revenue), 0) AS total_revenue,
            COALESCE(SUM(valid_orders), 0) AS total_orders,
            COUNT(
                DISTINCT CASE
                    WHEN active_store_flag = 1 THEN COALESCE(standard_store_id, platform || ':' || platform_store_id)
                END
            ) AS active_stores,
            COUNT(DISTINCT province) AS covered_provinces,
            COUNT(DISTINCT city) AS covered_cities
        FROM dwd_platform_daily_normalized
        {where_sql}
    """
    with _connect() as conn:
        row = conn.execute(sql, params).fetchone()
    return dict(row)


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


def fetch_trend(filters: QueryFilters, metric: str) -> list[dict[str, Any]]:
    metric_sql = {
        "revenue": "COALESCE(SUM(revenue), 0)",
        "orders": "COALESCE(SUM(valid_orders), 0)",
        "exposure_users": "COALESCE(SUM(exposure_users), 0)",
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
    sql = f"""
        SELECT
            standard_store_id,
            standard_store_name,
            province,
            city,
            platform,
            {metric_sql[metric]} AS metric_value
        FROM dwd_platform_daily_normalized
        {where_sql}
        GROUP BY standard_store_id, standard_store_name, province, city, platform
        ORDER BY metric_value DESC
        LIMIT ?
    """
    with _connect() as conn:
        return [dict(row) for row in conn.execute(sql, [*params, limit]).fetchall()]


def fetch_city_top20(filters: QueryFilters, metric: str) -> list[dict[str, Any]]:
    metric_sql = {
        "revenue": "COALESCE(SUM(revenue), 0)",
        "orders": "COALESCE(SUM(valid_orders), 0)",
        "store_count": "COUNT(DISTINCT COALESCE(standard_store_id, platform || ':' || platform_store_id))",
    }
    if metric not in metric_sql:
        raise ValueError(f"不支持的城市 Top20 指标: {metric}")

    where_sql, params = _where_clause(filters)
    sql = f"""
        SELECT
            province,
            city,
            platform,
            {metric_sql[metric]} AS metric_value
        FROM dwd_platform_daily_normalized
        {where_sql}
        GROUP BY province, city, platform
        ORDER BY metric_value DESC
        LIMIT 20
    """
    with _connect() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def fetch_store_mapping_list(limit: int | None = 200, keyword: str | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT
            s.standard_store_id,
            s.standard_store_name,
            s.province,
            s.city,
            s.district,
            s.operator_name,
            MAX(CASE WHEN m.platform = '美团' THEN m.platform_store_id END) AS meituan_store_id,
            MAX(CASE WHEN m.platform = '美团' THEN m.platform_store_name END) AS meituan_store_name,
            MAX(CASE WHEN m.platform = '饿了么' THEN m.platform_store_id END) AS eleme_store_id,
            MAX(CASE WHEN m.platform = '饿了么' THEN m.platform_store_name END) AS eleme_store_name,
            MAX(CASE WHEN m.platform = '京东' THEN m.platform_store_id END) AS jd_store_id,
            MAX(CASE WHEN m.platform = '京东' THEN m.platform_store_name END) AS jd_store_name
        FROM dim_standard_store s
        LEFT JOIN bridge_platform_store_mapping m
          ON s.standard_store_id = m.standard_store_id
        GROUP BY s.standard_store_id, s.standard_store_name, s.province, s.city, s.district, s.operator_name
        ORDER BY s.standard_store_name
    """
    with _connect() as conn:
        rows = [dict(row) for row in conn.execute(sql).fetchall()]

    if keyword:
        needle = keyword.strip().lower()
        rows = [
            row
            for row in rows
            if needle
            in " ".join(
                str(row.get(field) or "")
                for field in (
                    "standard_store_name",
                    "meituan_store_name",
                    "eleme_store_name",
                    "jd_store_name",
                )
            ).lower()
        ]

    if limit is not None:
        rows = rows[:limit]

    return rows


def fetch_store_mapping_summary(
    platforms: tuple[str, ...] = PLATFORMS,
    keyword: str | None = None,
) -> dict[str, Any]:
    rows = fetch_store_mapping_list(limit=None, keyword=keyword)
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
    with _connect() as conn:
        provinces = [
            row["province"]
            for row in conn.execute(
                """
                SELECT DISTINCT province
                FROM dwd_platform_daily_normalized
                WHERE province IS NOT NULL AND province != ''
                ORDER BY province
                """
            ).fetchall()
        ]
        location_rows = conn.execute(
            """
            SELECT DISTINCT province, city
            FROM dwd_platform_daily_normalized
            WHERE province IS NOT NULL
              AND province != ''
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

    location_map: dict[str, list[str]] = {}
    for row in location_rows:
        province = row["province"]
        city = row["city"]
        location_map.setdefault(province, []).append(city)

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
