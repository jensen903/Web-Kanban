from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "warehouse" / "web_kanban.db"


@dataclass
class QueryFilters:
    start_date: str
    end_date: str
    platforms: tuple[str, ...] = ("美团", "饿了么", "京东")
    province: str | None = None
    city: str | None = None


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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


def fetch_store_top20(filters: QueryFilters, metric: str) -> list[dict[str, Any]]:
    metric_sql = {
        "revenue": "COALESCE(SUM(revenue), 0)",
        "orders": "COALESCE(SUM(valid_orders), 0)",
        "order_conversion_rate": "AVG(order_conversion_rate)",
    }
    if metric not in metric_sql:
        raise ValueError(f"不支持的门店 Top20 指标: {metric}")

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
        LIMIT 20
    """
    with _connect() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


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


def fetch_store_mapping_summary() -> dict[str, Any]:
    sql = """
        SELECT
            COUNT(DISTINCT standard_store_id) AS standard_store_count,
            COUNT(DISTINCT CASE WHEN platform = '美团' THEN standard_store_id END) AS meituan_mapped_count,
            COUNT(DISTINCT CASE WHEN platform = '饿了么' THEN standard_store_id END) AS eleme_mapped_count,
            COUNT(DISTINCT CASE WHEN platform = '京东' THEN standard_store_id END) AS jd_mapped_count
        FROM bridge_platform_store_mapping
    """
    with _connect() as conn:
        row = conn.execute(sql).fetchone()
    return dict(row)


def fetch_store_mapping_list(limit: int = 200) -> list[dict[str, Any]]:
    sql = """
        SELECT
            m.standard_store_id,
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
        FROM bridge_platform_store_mapping m
        LEFT JOIN dim_standard_store s
          ON s.standard_store_id = m.standard_store_id
        GROUP BY m.standard_store_id, s.standard_store_name, s.province, s.city, s.district, s.operator_name
        ORDER BY s.standard_store_name
        LIMIT ?
    """
    with _connect() as conn:
        return [dict(row) for row in conn.execute(sql, (limit,)).fetchall()]


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
    return {
        "platforms": ["美团", "饿了么", "京东"],
        "provinces": provinces,
        "cities": cities,
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
