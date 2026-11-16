"""Request admission for the hosted synthetic demo."""

import hashlib
import hmac
import ipaddress
import os
import re

import psycopg
from starlette.datastructures import Headers, MutableHeaders
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from sentinel.service import token_digest

TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")
SAME_ORIGIN_ROUTES = {"/demo/session": "guest", "/iaf/ask": "iaf"}
SECURITY_HEADERS = {
    "Content-Security-Policy": "frame-ancestors 'none'; object-src 'none'; base-uri 'none'",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def visitor_address(scope, headers: Headers, *, on_vercel: bool) -> str | None:
    # Only Vercel's overwritten header is trusted on Vercel. Locally use ASGI peer info.
    values = headers.getlist("x-vercel-forwarded-for") if on_vercel else [
        scope["client"][0]] if scope.get("client") else []
    if len(values) != 1:
        return None
    try:
        address = ipaddress.ip_address(values[0])
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address):
        if address.scope_id is not None:
            return None
        if address.ipv4_mapped:
            return str(address.ipv4_mapped)
        return str(ipaddress.IPv6Network((address, 64), strict=False))
    return str(address)


def reserve(database_url: str, group: str, visitor: str, digest: str | None) -> bool:
    with psycopg.connect(database_url, connect_timeout=3) as conn:
        conn.execute("SET LOCAL statement_timeout = '1800ms'")
        conn.execute("SET LOCAL lock_timeout = '300ms'")
        cursor = conn.execute(
            "SELECT sentinel_demo.reserve_request(%s, %s, %s)", (group, visitor, digest)
        )
        result = cursor.fetchone()
        return bool(result and result[0])


class HostedGuard:
    def __init__(self, app, database_url: str):
        self.app = app
        self.database_url = database_url
        self.on_vercel = os.environ.get("VERCEL") == "1"
        # Domain separation keeps the derived key out of storage and responses.
        self.visitor_key = hmac.digest(
            database_url.encode(), b"sentinel/demo/visitor-key/v1", hashlib.sha256
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        # Starlette redirects trailing slashes. Guard both spellings before routing.
        endpoint = path.rstrip("/")
        group = SAME_ORIGIN_ROUTES.get(endpoint) if scope["method"] == "POST" else None
        if endpoint == "/v1" or endpoint.startswith("/v1/"):
            group = "api"
        sensitive = group is not None or endpoint in SAME_ORIGIN_ROUTES
        headers = Headers(scope=scope)

        async def guarded_send(message):
            if message["type"] == "http.response.start":
                response = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS.items():
                    if name not in response:
                        response[name] = value
                if sensitive:
                    response["Cache-Control"] = "private, no-store"
            await send(message)

        async def refuse(status: int, code: str, retry: str | None = None):
            body = {"kind": "bad_request"} if group == "iaf" else {"error": code}
            extra = {"Retry-After": retry} if retry else {}
            return await JSONResponse(body, status_code=status, headers=extra)(
                scope, receive, guarded_send
            )

        if group in ("guest", "iaf") and headers.get("sec-fetch-site") != "same-origin":
            return await refuse(403, "demo_same_origin_required")
        if group:
            address = visitor_address(scope, headers, on_vercel=self.on_vercel)
            if address is None:
                return await refuse(503, "demo_admission_unavailable")
            visitor = hmac.digest(self.visitor_key, address.encode(), hashlib.sha256).hex()
            scheme, _, token = headers.get("authorization", "").partition(" ")
            valid_token = scheme.lower() == "bearer" and TOKEN.fullmatch(token)
            digest = token_digest(token) if valid_token else None
            try:
                allowed = await run_in_threadpool(reserve, self.database_url, group, visitor, digest)
            except (OSError, psycopg.Error):
                return await refuse(503, "demo_admission_unavailable")
            if not allowed:
                return await refuse(429, "demo_rate_limited", "60" if group == "api" else "3600")
        return await self.app(scope, receive, guarded_send)
