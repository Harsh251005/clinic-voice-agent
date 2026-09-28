"""The server: patients' call pages, the dashboard's JSON API (/api), and a
health check. One process, one origin for the dashboard's cookie."""

from __future__ import annotations

import asyncio
import html
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from string import Template
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from api import dashboard
from api.limits import RateLimiter
from api.passes import call_pass
from clinic_agent import incidents
from clinic_agent.config import ConfigError, Settings, load_settings, require_key
from clinic_agent.store import repo
from clinic_agent.store.db import Sessions, sessions_for
from clinic_agent.store.models import utc_now
from clinic_agent.store.purge import purge

logger = logging.getLogger("clinic-agent.api")

HERE = Path(__file__).parent
PAGE = Template((HERE / "templates" / "call.html").read_text())
NOT_FOUND = Template((HERE / "templates" / "not_found.html").read_text())
PAUSED = Template((HERE / "templates" / "paused.html").read_text())

# A patient rarely needs more than a couple of tries; a clinic rarely gets
# more than this many browser calls an hour at pilot scale. Tune with real use.
CALLS_PER_IP = (5, 10 * 60)
CALLS_PER_CLINIC = (30, 60 * 60)
PURGE_EVERY = 6 * 60 * 60  # seconds; transcripts expire by the day, so a few hours late is fine
WATCH_EVERY = 30  # seconds between problem checks (incidents.sync)
# What a patient's call page may report: generous for real trouble, useless for flooding.
REPORTS_PER_IP = (10, 10 * 60)
REPORTS_PER_CLINIC = (60, 60 * 60)


def create_app(cfg: Settings | None = None) -> FastAPI:
    """Fails fast, like main.py: missing LiveKit settings or an old schema
    raise here, before the server accepts a request."""
    cfg = cfg or load_settings()
    required = [
        (cfg.livekit_url, "LIVEKIT_URL"),
        (cfg.livekit_api_key, "LIVEKIT_API_KEY"),
        (cfg.livekit_api_secret, "LIVEKIT_API_SECRET"),
    ]
    if cfg.dashboard_login == "google":
        required += [
            (cfg.session_secret, "SESSION_SECRET"),
            (cfg.google_client_id, "GOOGLE_CLIENT_ID"),
            (cfg.google_client_secret, "GOOGLE_CLIENT_SECRET"),
        ]
    for value, name in required:
        require_key(value, name)
    if cfg.dashboard_login == "google" and len(cfg.session_secret) < 32:
        raise ConfigError("SESSION_SECRET is too short: use 32+ random characters (see .env.example)")
    sessions = sessions_for(cfg.database_url)
    per_ip, per_clinic = RateLimiter(*CALLS_PER_IP), RateLimiter(*CALLS_PER_CLINIC)
    reports_ip, reports_clinic = RateLimiter(*REPORTS_PER_IP), RateLimiter(*REPORTS_PER_CLINIC)
    csp = _content_security_policy(cfg.livekit_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        tasks = [
            asyncio.create_task(_purge_forever(sessions)),
            asyncio.create_task(_watch_forever(sessions, cfg.max_call_minutes)),
        ]
        yield
        for task in tasks:
            task.cancel()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.cfg, app.state.sessions = cfg, sessions
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    app.add_middleware(
        SessionMiddleware,
        # Sign-in off (local dev) needs no stable secret: nobody signs in.
        secret_key=cfg.session_secret or secrets.token_hex(32),
        session_cookie="clinic_console",
        max_age=12 * 60 * 60,  # a working day; then sign in again
        same_site="lax",
        https_only=cfg.dashboard_url.startswith("https://"),
    )
    app.include_router(dashboard.router(cfg))

    @app.exception_handler(Exception)
    async def server_error(request: Request, exc: Exception):
        """An unhandled error becomes a problem on the admin panel: the
        route and the error's type only, never the request or its message
        (either can hold patient data). The traceback still goes to the log."""
        route = getattr(request.scope.get("route"), "path", "?")
        subject = f"{request.method} {route} · {type(exc).__name__}"
        try:
            await asyncio.to_thread(_report, sessions, "server_error", subject=subject)
        except Exception:  # noqa: BLE001 - reporting must not mask the original error
            logger.exception("could not record a server error")
        return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)

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

    @app.get("/healthz/worker")
    def worker_health() -> dict:
        """Is a receptionist connected and ready? For the call page and monitors."""
        with sessions() as s:
            last = repo.last_beat(s)
        online = last is not None and utc_now() - last <= incidents.HEARTBEAT_STALE
        return {"online": online, "last_seen": last.isoformat() + "Z" if last else None}

    @app.get("/call/{slug}", response_class=HTMLResponse)
    def call_page(slug: str):
        try:
            clinic = clinic_for(slug)
        except repo.NotFound:
            return HTMLResponse(NOT_FOUND.substitute(), status_code=404)
        e = html.escape
        if not clinic.active:
            return HTMLResponse(PAUSED.substitute(name=e(clinic.name), phone=_call_the_clinic(clinic)), status_code=503)
        return PAGE.substitute(
            name=e(clinic.name), address=e(clinic.address), slug=e(clinic.slug), phone=_call_the_clinic(clinic),
        )

    @app.post("/call/{slug}/pass")
    def join_pass(slug: str, request: Request):
        try:
            clinic = clinic_for(slug)
        except repo.NotFound:
            return JSONResponse({"error": "This call link doesn't exist."}, status_code=404)
        if not clinic.active:
            return JSONResponse({"error": "This clinic isn't taking calls here right now."}, status_code=503)
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

    @app.post("/call/{slug}/report", status_code=204)
    async def report(slug: str, request: Request):
        """The call page gave up (mic blocked, no connection, nobody
        answered): a problem for the clinic and the operator to see. A fixed
        reason code and nothing else, so no patient can put anything
        personal in it. JSON only: a cross-site form can't send it."""
        if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
            return JSONResponse({"error": "Send JSON."}, status_code=415)
        try:
            reason = (await request.json()).get("reason")
        except (ValueError, AttributeError):
            reason = None
        if reason not in incidents.CONNECT_FAILURES:
            return JSONResponse({"error": "Unknown reason."}, status_code=422)
        try:
            clinic = clinic_for(slug)
        except repo.NotFound:
            return JSONResponse({"error": "This call link doesn't exist."}, status_code=404)
        if not reports_ip.allow(_client_ip(request, cfg.client_ip_header)) or not reports_clinic.allow(clinic.slug):
            return JSONResponse({"error": "Too many reports."}, status_code=429)
        await asyncio.to_thread(_report, sessions, "patients_cant_connect", clinic_id=clinic.id, subject=reason)
        return None

    return app


def _call_the_clinic(clinic) -> str:
    if not clinic.phone:
        return ""
    phone = html.escape(clinic.phone)
    return f'<a class="fallback" href="tel:{phone}">Or call the clinic: {phone}</a>'


async def _purge_forever(sessions: Sessions) -> None:
    """Delete expired call transcripts and old traces, now and every few
    hours. A failure is a problem on the admin panel: expired transcripts
    are patient data we promised to delete."""
    while True:
        try:
            await asyncio.to_thread(purge, sessions)
            await asyncio.to_thread(_clear, sessions, "purge_failed")
        except Exception:  # noqa: BLE001 - try again next round
            logger.exception("purging expired call records failed")
            try:
                await asyncio.to_thread(_report, sessions, "purge_failed")
            except Exception:  # noqa: BLE001
                logger.exception("could not record the failed purge")
        await asyncio.sleep(PURGE_EVERY)


async def _watch_forever(sessions: Sessions, max_call_minutes: int) -> None:
    """Re-check every problem condition (incidents.sync) every half minute."""
    while True:
        try:
            await asyncio.to_thread(_sync, sessions, max_call_minutes)
        except Exception:  # noqa: BLE001 - try again next round
            logger.exception("checking for problems failed")
        await asyncio.sleep(WATCH_EVERY)


def _sync(sessions: Sessions, max_call_minutes: int) -> None:
    with sessions() as s:
        incidents.sync(s, utc_now(), max_call_minutes=max_call_minutes)


def _report(sessions: Sessions, kind: str, **where) -> None:
    with sessions() as s:
        incidents.report(s, kind, utc_now(), **where)


def _clear(sessions: Sessions, kind: str) -> None:
    with sessions() as s:
        incidents.clear(s, kind, utc_now())


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
