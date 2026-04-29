from __future__ import annotations

import json
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BASE_DIR.parent
DB_PATH = BASE_DIR / "warehouse" / "web_kanban.db"
OUTPUT_PATH = PROJECT_DIR / "frontend" / "data" / "dashboard_dataset.json"


def fetch_rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        metadata = fetch_rows(
            conn,
            """
            SELECT
                MIN(biz_date) AS min_date,
                MAX(biz_date) AS max_date,
                COUNT(*) AS total_rows
            FROM dwd_platform_daily_normalized
            """,
        )[0]
        platform_daily = fetch_rows(
            conn,
            """
            SELECT
                biz_date,
                platform,
                revenue,
                gross_amount,
                customer_paid,
                valid_orders,
                exposure_users,
                active_store_count,
                city_count,
                province_count,
                avg_ticket,
                hand_rate
            FROM dws_platform_daily_summary
            ORDER BY biz_date, platform
            """,
        )
        store_daily = fetch_rows(
            conn,
            """
            SELECT
                biz_date,
                platform,
                standard_store_id,
                standard_store_name,
                province,
                city,
                revenue,
                valid_orders,
                order_conversion_rate,
                avg_ticket,
                hand_rate
            FROM dws_store_daily_summary
            ORDER BY biz_date, platform
            """,
        )
        city_daily = fetch_rows(
            conn,
            """
            SELECT
                biz_date,
                platform,
                province,
                city,
                revenue,
                valid_orders,
                store_count,
                avg_ticket,
                hand_rate
            FROM dws_city_daily_summary
            ORDER BY biz_date, platform
            """,
        )
        store_mappings = fetch_rows(
            conn,
            """
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
            """,
        )

    payload = {
        "metadata": {
            **metadata,
            "platforms": ["美团", "饿了么", "京东"],
        },
        "platformDailySummary": platform_daily,
        "storeDailySummary": store_daily,
        "cityDailySummary": city_daily,
        "storeMappings": store_mappings,
    }

    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"导出完成: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
