from __future__ import annotations

import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from query_service import (
    QueryFilters,
    fetch_city_top20,
    fetch_core_table,
    fetch_filter_options,
    fetch_growth_efficiency,
    fetch_order_compare,
    fetch_overview_summary,
    fetch_revenue_share,
    fetch_store_mapping_list,
    fetch_store_mapping_summary,
    fetch_store_opportunity_low_conversion,
    fetch_store_opportunity_low_exposure,
    fetch_store_top20,
    fetch_ticket_compare,
    fetch_trend,
)


BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"
PORT = int(os.environ.get("PORT", "4180"))


def _parse_filters(query_string: str) -> QueryFilters:
    query = parse_qs(query_string)
    platforms = tuple(query.get("platform", ["美团", "饿了么", "京东"]))
    return QueryFilters(
        start_date=query.get("start_date", ["2026/03/27"])[0],
        end_date=query.get("end_date", ["2026/04/26"])[0],
        platforms=platforms,
        province=query.get("province", [""])[0] or None,
        city=query.get("city", [""])[0] or None,
    )


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api(parsed)
            return
        super().do_GET()

    def _handle_api(self, parsed) -> None:
        filters = _parse_filters(parsed.query)
        route = parsed.path
        query = parse_qs(parsed.query)

        if route in {"/api/health", "/api/v1/health"}:
            self._json_response({"ok": True})
            return

        if route in {"/api/bootstrap", "/api/v1/bootstrap"}:
            self._json_response(fetch_filter_options())
            return

        if route == "/api/overview":
            self._json_response(
                {
                    "summary": fetch_overview_summary(filters),
                    "revenue_share": fetch_revenue_share(filters),
                    "order_compare": fetch_order_compare(filters),
                    "ticket_compare": fetch_ticket_compare(filters),
                    "core_table": fetch_core_table(filters),
                    "growth_efficiency": fetch_growth_efficiency(filters),
                }
            )
            return

        if route == "/api/trends":
            self._json_response(
                {
                    "summary": fetch_overview_summary(filters),
                    "revenue": fetch_trend(filters, "revenue"),
                    "orders": fetch_trend(filters, "orders"),
                    "exposure_users": fetch_trend(filters, "exposure_users"),
                    "visit_users": fetch_trend(filters, "visit_users"),
                    "visit_conversion_rate": fetch_trend(filters, "visit_conversion_rate"),
                    "order_conversion_rate": fetch_trend(filters, "order_conversion_rate"),
                    "hand_rate": fetch_trend(filters, "hand_rate"),
                    "active_stores": fetch_trend(filters, "active_stores"),
                }
            )
            return

        if route == "/api/stores":
            stores_limit = int(query.get("limit", ["20"])[0] or "20")
            self._json_response(
                {
                    "summary": fetch_overview_summary(filters),
                    "active_trend": fetch_trend(filters, "active_stores"),
                    "top_revenue": fetch_store_top20(filters, "revenue", limit=stores_limit),
                    "top_orders": fetch_store_top20(filters, "orders", limit=stores_limit),
                    "top_conversion": fetch_store_top20(filters, "order_conversion_rate", limit=stores_limit),
                    "opportunity_low_conversion": fetch_store_opportunity_low_conversion(filters, limit=stores_limit),
                    "opportunity_low_exposure": fetch_store_opportunity_low_exposure(filters, limit=stores_limit),
                }
            )
            return

        if route == "/api/regions":
            self._json_response(
                {
                    "summary": fetch_overview_summary(filters),
                    "top_revenue": fetch_city_top20(filters, "revenue"),
                    "top_orders": fetch_city_top20(filters, "orders"),
                    "top_store_count": fetch_city_top20(filters, "store_count"),
                }
            )
            return

        if route == "/api/store-mappings":
            self._json_response(
                {
                    "summary": fetch_store_mapping_summary(
                        platforms=filters.platforms,
                        keyword=query.get("keyword", [""])[0] or None,
                        mapping_filter=query.get("mapping_filter", ["all"])[0] or "all",
                    ),
                    "rows": fetch_store_mapping_list(
                        limit=int(query.get("limit", ["200"])[0] or "200"),
                        keyword=query.get("keyword", [""])[0] or None,
                        mapping_filter=query.get("mapping_filter", ["all"])[0] or "all",
                        platforms=filters.platforms,
                    ),
                }
            )
            return

        payload = self._handle_v1_resource(route, filters, parsed.query)
        if payload is None:
            self._json_response({"error": "Not found"}, status=404)
            return

        self._json_response(payload)

    def _handle_v1_resource(self, route: str, filters: QueryFilters, query_string: str):
        query = parse_qs(query_string)
        if route == "/api/v1/overview/summary":
            return fetch_overview_summary(filters)
        if route == "/api/v1/overview/revenue-share":
            return fetch_revenue_share(filters)
        if route == "/api/v1/overview/order-compare":
            return fetch_order_compare(filters)
        if route == "/api/v1/overview/ticket-compare":
            return fetch_ticket_compare(filters)
        if route == "/api/v1/overview/core-table":
            return fetch_core_table(filters)
        if route == "/api/v1/overview/growth-efficiency":
            return fetch_growth_efficiency(filters)

        if route == "/api/v1/trends/summary":
            return fetch_overview_summary(filters)
        if route == "/api/v1/trends/revenue":
            return fetch_trend(filters, "revenue")
        if route == "/api/v1/trends/orders":
            return fetch_trend(filters, "orders")
        if route == "/api/v1/trends/exposure":
            return fetch_trend(filters, "exposure_users")
        if route == "/api/v1/trends/visit-users":
            return fetch_trend(filters, "visit_users")
        if route == "/api/v1/trends/visit-conversion":
            return fetch_trend(filters, "visit_conversion_rate")
        if route == "/api/v1/trends/order-conversion":
            return fetch_trend(filters, "order_conversion_rate")
        if route == "/api/v1/trends/hand-rate":
            return fetch_trend(filters, "hand_rate")

        if route == "/api/v1/stores/summary":
            return fetch_overview_summary(filters)
        if route == "/api/v1/stores/active-trend":
            return fetch_trend(filters, "active_stores")
        if route == "/api/v1/stores/top-revenue":
            return fetch_store_top20(filters, "revenue", limit=int(query.get("limit", ["20"])[0] or "20"))
        if route == "/api/v1/stores/top-orders":
            return fetch_store_top20(filters, "orders", limit=int(query.get("limit", ["20"])[0] or "20"))
        if route == "/api/v1/stores/top-conversion":
            return fetch_store_top20(
                filters,
                "order_conversion_rate",
                limit=int(query.get("limit", ["20"])[0] or "20"),
            )
        if route == "/api/v1/stores/opportunity-low-conversion":
            return fetch_store_opportunity_low_conversion(filters, limit=int(query.get("limit", ["10"])[0] or "10"))
        if route == "/api/v1/stores/opportunity-low-exposure":
            return fetch_store_opportunity_low_exposure(filters, limit=int(query.get("limit", ["10"])[0] or "10"))

        if route == "/api/v1/regions/summary":
            return fetch_overview_summary(filters)
        if route == "/api/v1/regions/top-revenue":
            return fetch_city_top20(filters, "revenue")
        if route == "/api/v1/regions/top-orders":
            return fetch_city_top20(filters, "orders")
        if route == "/api/v1/regions/top-store-count":
            return fetch_city_top20(filters, "store_count")

        if route == "/api/v1/store-mappings/summary":
            return fetch_store_mapping_summary(
                platforms=filters.platforms,
                keyword=query.get("keyword", [""])[0] or None,
                mapping_filter=query.get("mapping_filter", ["all"])[0] or "all",
            )
        if route == "/api/v1/store-mappings/list":
            limit = int(query.get("limit", ["200"])[0] or "200")
            return fetch_store_mapping_list(
                limit=limit,
                keyword=query.get("keyword", [""])[0] or None,
                mapping_filter=query.get("mapping_filter", ["all"])[0] or "all",
                platforms=filters.platforms,
            )

        return None

    def _json_response(self, payload, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), DashboardHandler)
    print(f"Dashboard server running at http://127.0.0.1:{PORT}")
    print(f"Serving frontend from: {FRONTEND_DIR}")
    server.serve_forever()


if __name__ == "__main__":
    main()
