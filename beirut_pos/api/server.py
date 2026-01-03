"""Minimal HTTP server for customer search."""
from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..services import customers as customers_service


class CustomerSearchHandler(BaseHTTPRequestHandler):
    """Serve lightweight API endpoints."""

    server_version = "BeirutPOSAPI/1.0"

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        parsed = urlparse(self.path)
        if parsed.path != "/customers/search":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return

        query = parse_qs(parsed.query)
        term = (query.get("q", [""])[0] or "").strip()
        if not term:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "Missing required query parameter 'q'."},
            )
            return

        try:
            results = customers_service.search_customers(term, limit=25)
        except Exception:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "Failed to search customers."},
            )
            return

        payload: dict[str, Any] = {"results": results}
        if not results:
            payload["message"] = "No customers found."

        self._send_json(HTTPStatus.OK, payload)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_api_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the built-in customer search server."""
    server = HTTPServer((host, port), CustomerSearchHandler)
    server.serve_forever()


if __name__ == "__main__":
    run_api_server()
