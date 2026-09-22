"""Routes: the call page, its join pass, and a health check."""

from __future__ import annotations

import html
import logging
from pathlib import Path
from string import Template
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api.limits import RateLimiter
from api.passes import call_pass
from clinic_agent.config import ConfigError, Settings, load_settings, require_key
from clinic_agent.store import repo
from clinic_agent.store.db import sessions_for

logger = logging.getLogger("clinic-agent.api")

HERE = Path(__file__).parent
PAGE = Template((HERE / "templates" / "call.html").read_text())
NOT_FOUND = Template((HERE / "templates" / "not_found.html").read_text())

# A patient rarely needs more than a couple of tries; a clinic rarely gets
# more than this many browser calls an hour at pilot scale. Tune with real use.
CALLS_PER_IP = (5, 10 * 60)
CALLS_PER_CLINIC = (30, 60 * 60)


def create_app(cfg: Settings | None = None) -> FastAPI:
    """Fails fast, like main.py: missing LiveKit settings or an old schema
    raise here, before the server accepts a request."""
    cfg = cfg or load_settings()
    for value, name in (
        (cfg.livekit_url, "LIVEKIT_URL"),
        (cfg.livekit_api_key, "LIVEKIT_API_KEY"),
        (cfg.livekit_api_secret, "LIVEKIT_API_SECRET"),
    ):
        require_key(value, name)
    sessions = sessions_for(cfg.database_url)
    per_ip, per_clinic = RateLimiter(*CALLS_PER_IP), RateLimiter(*CALLS_PER_CLINIC)
    csp = _content_security_policy(cfg.livekit_url)

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "microphone=(self), camera=()"
        return response

    def clinic_for(slug: str):
        if not repo.SLUG.fullmatch(slug):
            raise repo.NotFound(slug)
        with sessions() as s:
            return repo.get_clinic_by_slug(s, slug)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    @app.get("/call/{slug}", response_class=HTMLResponse)
    def call_page(slug: str):
        try:
            clinic = clinic_for(slug)
        except repo.NotFound:
            return HTMLResponse(NOT_FOUND.substitute(), status_code=404)
        e = html.escape
        phone = (
            f'<a class="fallback" href="tel:{e(clinic.phone)}">Or call the clinic: {e(clinic.phone)}</a>'
            if clinic.phone else ""
        )
        return PAGE.substitute(
            name=e(clinic.name), address=e(clinic.address), slug=e(clinic.slug), phone=phone,
        )

    @app.post("/call/{slug}/pass")
    def join_pass(slug: str, request: Request):
        try:
            clinic = clinic_for(slug)
        except repo.NotFound:
            return JSONResponse({"error": "This call link doesn't exist."}, status_code=404)
        ip = _client_ip(request, cfg.client_ip_header)
        if not per_ip.allow(ip) or not per_clinic.allow(clinic.slug):
            logger.warning("rate limited a call to %s from %s", clinic.slug, ip)
            return JSONResponse(
                {"error": "Too many calls just now. Please wait a few minutes and try again."},
                status_code=429,
            )
        p = call_pass(cfg, clinic.id, clinic.slug)
        logger.info("call pass for clinic %s (%s): room %s", clinic.id, clinic.slug, p.room)
        return {"url": p.url, "token": p.token}

    return app


def _client_ip(request: Request, header: str | None) -> str:
    """The caller's IP. A proxy header is trusted only when configured: anyone
    can send one, so otherwise it would let a caller dodge the per-IP limit.
    The last entry is the one our own proxy added; earlier ones in an
    X-Forwarded-For chain came from the caller and could be anything."""
    if header:
        forwarded = request.headers.get(header, "").split(",")[-1].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "unknown"


def _content_security_policy(livekit_url: str) -> str:
    """Scripts from us and the pinned LiveKit client only; network to us and
    our LiveKit project only."""
    host = urlparse(livekit_url).hostname or ""
    if not host:
        raise ConfigError(f"LIVEKIT_URL is not a URL: {livekit_url!r}")
    # LiveKit Cloud moves a call to a regional host (<project>.<region>.production.livekit.cloud).
    # CSP wildcards only cover the leftmost label, so that is *.production.livekit.cloud.
    lk = f"wss://{host} https://{host}"
    if host.endswith(".livekit.cloud"):
        lk += " wss://*.production.livekit.cloud https://*.production.livekit.cloud"
    return "; ".join([
        "default-src 'self'",
        "script-src 'self' https://cdn.jsdelivr.net",
        "style-src 'self'",
        f"connect-src 'self' {lk}",
        "media-src 'self' blob:",
        "img-src 'self' data:",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "form-action 'none'",
    ])
