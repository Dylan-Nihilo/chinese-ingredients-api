"""Read-only local HTTP adapter. No accounts, writes, or network data fetching."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import __version__
from .catalog import Catalog, DataError, DEFAULT_DATA_DIR, ROOT, _json_bytes


@dataclass
class Response:
    status: int
    body: bytes
    content_type: str = "application/json; charset=utf-8"
    headers: dict[str, str] = field(default_factory=dict)


class APIError(ValueError):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def error(status: int, code: str, message: str) -> Response:
    return Response(status, _json_bytes({"error": {"code": code, "message": message}}))


def parse_query(raw: str, allowed: set[str]) -> dict[str, str]:
    try:
        if re.search(r"%(?![0-9a-fA-F]{2})", raw):
            raise ValueError("invalid percent encoding")
        query = parse_qs(raw, keep_blank_values=True, strict_parsing=True, encoding="utf-8", errors="strict", max_num_fields=12)
    except (ValueError, UnicodeError) as exc:
        raise APIError(400, "invalid_query", "Query must use valid UTF-8 name=value parameters.") from exc
    if set(query) - allowed:
        raise APIError(400, "unknown_parameter", f"Unknown parameter: {', '.join(sorted(set(query) - allowed))}")
    if any(len(values) != 1 for values in query.values()):
        raise APIError(400, "duplicate_parameter", "Each parameter may appear only once.")
    return {key: value[0] for key, value in query.items()}


def _integer(value: str, name: str, minimum: int, maximum: int) -> int:
    if not re.fullmatch(r"[0-9]{1,10}", value):
        raise APIError(400, "invalid_parameter", f"{name} must be an integer between {minimum} and {maximum}.")
    result = int(value)
    if not minimum <= result <= maximum:
        raise APIError(400, "invalid_parameter", f"{name} must be between {minimum} and {maximum}.")
    return result


class Application:
    def __init__(self, catalog: Catalog):
        self.catalog = catalog
        self.openapi = (ROOT / "openapi.json").read_bytes()
        self.docs = (ROOT / "docs" / "index.html").read_bytes()

    def route(self, target: str) -> Response:
        if len(target) > 4096:
            raise APIError(414, "uri_too_long", "Request target exceeds 4096 characters.")
        try:
            url = urlsplit(target)
        except ValueError as exc:
            raise APIError(400, "invalid_url", "Invalid request URL.") from exc
        if url.scheme or url.netloc or url.fragment:
            raise APIError(400, "invalid_url", "Use a relative API path without fragments.")
        path = url.path
        allowed = {"q", "category", "limit", "offset"} if path == "/v1/ingredients" else set()
        query = parse_query(url.query, allowed)
        if path == "/healthz":
            return Response(200, _json_bytes({"status": "ok", "apiVersion": __version__, "datasetVersion": self.catalog.version}))
        if path == "/":
            return Response(200, _json_bytes({"name": "Chinese Ingredient API", "version": __version__, "docs": "/docs", "openapi": "/openapi.json", "metadata": "/v1/meta", "ingredients": "/v1/ingredients", "scope": "Ingredients only. Prototype dataset; no completeness or licensing clearance claim."}))
        if path == "/docs":
            return Response(200, self.docs, "text/html; charset=utf-8", {"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'"})
        if path == "/openapi.json":
            return Response(200, self.openapi)
        if path == "/v1/meta":
            return Response(200, _json_bytes(self.catalog.metadata()))
        if path in {"/v1/categories", "/v1/sources"}:
            key = path.rsplit("/", 1)[1]
            return Response(200, _json_bytes({"data": getattr(self.catalog, key), "meta": {"datasetVersion": self.catalog.version, "total": len(getattr(self.catalog, key))}}))
        if path == "/v1/ingredients":
            q = query.get("q", "")
            if len(q) > 120 or any(ord(char) < 32 or ord(char) == 127 for char in q):
                raise APIError(400, "invalid_parameter", "q must be at most 120 characters without control characters.")
            category = query.get("category")
            if category is not None and category not in {c["id"] for c in self.catalog.categories}:
                raise APIError(400, "invalid_category", "Unknown category. See /v1/categories.")
            limit = _integer(query.get("limit", "20"), "limit", 1, 100)
            offset = _integer(query.get("offset", "0"), "offset", 0, 1000000)
            matches = self.catalog.search(q, category)
            data = matches[offset:offset + limit]
            return Response(200, _json_bytes({"data": data, "meta": {"datasetVersion": self.catalog.version, "total": len(matches), "limit": limit, "offset": offset, "nextOffset": offset + limit if offset + limit < len(matches) else None}}))
        if path.startswith("/v1/ingredients/"):
            identifier = path.removeprefix("/v1/ingredients/")
            item = self.catalog.by_id.get(identifier)
            if item is None:
                raise APIError(404, "ingredient_not_found", "Ingredient ID not found.")
            return Response(200, _json_bytes({"data": item, "meta": {"datasetVersion": self.catalog.version}}))
        if path.startswith("/v1/exports/"):
            filename = path.removeprefix("/v1/exports/")
            if filename in self.catalog.raw:
                return Response(200, self.catalog.raw[filename], headers={"Content-Disposition": f'attachment; filename="{filename}"'})
            if filename == "ingredients.csv":
                return Response(200, self.catalog.csv_bytes(), "text/csv; charset=utf-8", {"Content-Disposition": 'attachment; filename="ingredients.csv"'})
        raise APIError(404, "not_found", "Endpoint not found. See /docs or /openapi.json.")

    def handle(self, method: str, target: str, if_none_match: str | None = None) -> Response:
        try:
            if method == "OPTIONS":
                response = self.route(target)  # Validate path and parameters first.
                response = Response(204, b"", headers={"Allow": "GET, HEAD, OPTIONS"})
            elif method not in {"GET", "HEAD"}:
                response = error(405, "method_not_allowed", "This API is read-only.")
                response.headers["Allow"] = "GET, HEAD, OPTIONS"
            else:
                response = self.route(target)
        except APIError as exc:
            response = error(exc.status, exc.code, exc.message)
        response.headers.update({"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff", "X-Dataset-Version": self.catalog.version})
        if response.status == 200:
            etag = '"' + hashlib.sha256(response.body).hexdigest() + '"'
            response.headers["ETag"] = etag
            matches = [part.strip().removeprefix("W/") for part in (if_none_match or "").split(",")]
            if "*" in matches or etag in matches:
                return Response(304, b"", response.content_type, response.headers)
        return response


def make_server(host: str, port: int, application: Application) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        server_version = "ChineseIngredientAPI/" + __version__
        sys_version = ""
        protocol_version = "HTTP/1.0"

        def handle_one_request(self):
            self.connection.settimeout(10)
            super().handle_one_request()

        def dispatch(self):
            try:
                response = application.handle(self.command, self.path, self.headers.get("If-None-Match"))
            except Exception:
                # Do not expose traces or local filesystem paths to callers.
                response = error(500, "internal_error", "Internal server error.")
                print("Unexpected request failure; review local server logs.", file=sys.stderr)
            self.send_response(response.status)
            if response.status not in {204, 304}:
                self.send_header("Content-Type", response.content_type)
                self.send_header("Content-Length", str(len(response.body)))
            for key, value in response.headers.items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != "HEAD" and response.status not in {204, 304}:
                try:
                    self.wfile.write(response.body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        do_GET = dispatch
        do_HEAD = dispatch
        do_OPTIONS = dispatch
        do_POST = dispatch
        do_PUT = dispatch
        do_PATCH = dispatch
        do_DELETE = dispatch
        do_TRACE = dispatch
        do_CONNECT = dispatch

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the read-only Chinese Ingredient API locally.")
    parser.add_argument("--host", default="127.0.0.1", help="default: 127.0.0.1 (local only)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    try:
        app = Application(Catalog(args.data_dir))
        server = make_server(args.host, args.port, app)
    except (DataError, OSError) as exc:
        print(f"Startup failed: {exc}", file=sys.stderr)
        return 1
    print(f"Chinese Ingredient API: http://{args.host}:{server.server_port}/docs", flush=True)
    print(f"Dataset {app.catalog.version}; {len(app.catalog.ingredients)} ingredients. Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
