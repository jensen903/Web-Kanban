from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from query_service import (
    QueryFilters,
    fetch_city_top20,
    fetch_core_table,
    fetch_filter_options,
    fetch_order_compare,
    fetch_overview_summary,
    fetch_revenue_share,
    fetch_store_mapping_list,
    fetch_store_mapping_summary,
    fetch_store_top20,
    fetch_ticket_compare,
    fetch_trend,
)


BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR / "frontend"
PORT = 4180


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
        payload = None

        if parsed.path == "/api/health":
            payload = {"ok": True}
        elif parsed.path == "/api/bootstrap":
            payload = fetch_filter_options()
        elif parsed.path == "/api/overview":
            payload = {
                "summary": fetch_overview_summary(filters),
                "revenue_share": fetch_revenue_share(filters),
                "order_compare": fetch_order_compare(filters),
                "ticket_compare": fetch_ticket_compare(filters),
                "core_table": fetch_core_table(filters),
            }
        elif parsed.path == "/api/trends":
            payload = {
                "summary": fetch_overview_summary(filters),
                "revenue": fetch_trend(filters, "revenue"),
                "orders": fetch_trend(filters, "orders"),
                "exposure_users": fetch_trend(filters, "exposure_users"),
                "hand_rate": fetch_trend(filters, "hand_rate"),
                "active_stores": fetch_trend(filters, "active_stores"),
            }
        elif parsed.path == "/api/stores":
            payload = {
                "summary": fetch_overview_summary(filters),
                "active_trend": fetch_trend(filters, "active_stores"),
                "top_revenue": fetch_store_top20(filters, "revenue"),
                "top_orders": fetch_store_top20(filters, "orders"),
                "top_conversion": fetch_store_top20(filters, "order_conversion_rate"),
            }
        elif parsed.path == "/api/regions":
            payload = {
                "summary": fetch_overview_summary(filters),
                "top_revenue": fetch_city_top20(filters, "revenue"),
                "top_orders": fetch_city_top20(filters, "orders"),
                "top_store_count": fetch_city_top20(filters, "store_count"),
            }
        elif parsed.path == "/api/store-mappings":
            payload = {
                "summary": fetch_store_mapping_summary(),
                "rows": fetch_store_mapping_list(limit=200),
            }
        else:
            self._json_response({"error": "Not found"}, status=404)
            return

        self._json_response(payload)

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
