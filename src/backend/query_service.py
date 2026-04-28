from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "warehouse" / "web_kanban.db"


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
            COUNT(DISTINCT CASE WHEN active_store_flag = 1 THEN standard_store_id END) AS active_stores,
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


def fetch_trend(filters: QueryFilters, metric: str) -> list[dict[str, Any]]:
    metric_sql = {
        "revenue": "COALESCE(SUM(revenue), 0)",
        "orders": "COALESCE(SUM(valid_orders), 0)",
        "exposure_users": "COALESCE(SUM(exposure_users), 0)",
        "hand_rate": "CASE WHEN SUM(gross_amount) = 0 THEN NULL ELSE SUM(revenue) * 1.0 / SUM(gross_amount) END",
        "active_stores": "COUNT(DISTINCT CASE WHEN active_store_flag = 1 THEN standard_store_id END)",
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
        "store_count": "COUNT(DISTINCT standard_store_id)",
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
