"""Google sign-in for the dashboard, and /api/me.

Standard OpenID Connect via Authlib: /api/auth/login sends the browser to
Google, Google sends it back to /api/auth/callback, and a verified email is
stored in the signed session cookie. Nothing else about the person is kept.
"""

from __future__ import annotations

import logging

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from api.dashboard.access import Viewer, current_viewer, same_site
from api.dashboard.schemas import ClinicSummary, Me
from clinic_agent.config import Settings
from clinic_agent.store import repo

logger = logging.getLogger("clinic-agent.api")

GOOGLE_METADATA = "https://accounts.google.com/.well-known/openid-configuration"


def router(cfg: Settings) -> APIRouter:
    r = APIRouter()
    oauth = OAuth()
    oauth.register(
        "google",
        client_id=cfg.google_client_id,
        client_secret=cfg.google_client_secret,
        server_metadata_url=GOOGLE_METADATA,
        client_kwargs={"scope": "openid email"},
    )
    home = f"{cfg.dashboard_url}/"

    @r.get("/api/auth/login", include_in_schema=False)
    async def login(request: Request):
        if cfg.dashboard_login == "off":
            return RedirectResponse(home)
        return await oauth.google.authorize_redirect(
            request, f"{cfg.dashboard_url}/api/auth/callback", prompt="select_account"
        )

    @r.get("/api/auth/callback", include_in_schema=False)
    async def callback(request: Request):
        try:
            token = await oauth.google.authorize_access_token(request)
        except OAuthError as err:
            logger.warning("Google sign-in failed: %s", err.error)
            return RedirectResponse(f"{home}?signin=failed")
        info = token.get("userinfo") or {}
        email = str(info.get("email", "")).strip().lower()
        # An unverified address could belong to anyone.
        if not email or info.get("email_verified") is not True:
            return RedirectResponse(f"{home}?signin=unverified")
        request.session.clear()  # a fresh session: nothing carried over from before sign-in
        request.session["email"] = email
        logger.info("dashboard sign-in: %s", email)
        return RedirectResponse(home)

    @r.post("/api/auth/logout", dependencies=[Depends(same_site)])
    def logout(request: Request) -> dict:
        request.session.clear()
        return {"ok": True}

    @r.get("/api/me", response_model=Me)
    def me(request: Request, viewer: Viewer = Depends(current_viewer)) -> Me:
        with request.app.state.sessions() as s:
            clinics = [c for c in repo.list_clinics(s) if viewer.may_open(c.id)]
        return Me(
            email=viewer.email, is_admin=viewer.is_admin, login=cfg.dashboard_login,
            clinics=[ClinicSummary(id=c.id, name=c.name, slug=c.slug) for c in clinics],
        )

    return r
