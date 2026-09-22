"""Who is looking at the dashboard, and which clinics they may open.

Staff sign in with Google (Streamlit's st.login, configured in
.streamlit/secrets.toml). Admins (ADMIN_EMAILS) see every clinic; everyone
else sees only the clinics their email was added to on the Team tab.
`google_email` is the only function that reads st.user, so tests replace it.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from clinic_agent.config import load_settings
from clinic_agent.store import repo
from dashboard import data, theme

AUTH_KEYS = ("client_id", "client_secret", "server_metadata_url", "redirect_uri", "cookie_secret")


@dataclass(frozen=True)
class Viewer:
    email: str
    is_admin: bool
    clinic_ids: frozenset[int]  # admins may open every clinic regardless

    def may_open(self, clinic_id: int) -> bool:
        return self.is_admin or clinic_id in self.clinic_ids


class Unverified(Exception):
    """Signed in, but Google hasn't verified the account's email."""


def login_configured() -> bool:
    try:
        section = st.secrets.get("auth")
    except Exception:  # noqa: BLE001 - no secrets.toml at all
        return False
    return bool(section) and all(section.get(k) for k in AUTH_KEYS)


def google_email() -> str | None:
    """The signed-in Google account's email, lowercased; None if signed out.
    Raises Unverified for an account whose email Google hasn't verified: an
    unverified address could belong to anyone."""
    if not st.user.is_logged_in:
        return None
    if st.user.get("email_verified") not in (True, "true"):
        raise Unverified(str(st.user.get("email", "")))
    return str(st.user.get("email", "")).strip().lower()


def require_viewer() -> Viewer:
    """The current viewer, or a sign-in / no-access screen and st.stop()."""
    cfg = load_settings()
    if cfg.dashboard_login == "off":
        viewer = Viewer(email="", is_admin=True, clinic_ids=frozenset())
    else:
        if not login_configured():
            _screen(
                "Sign-in isn't set up",
                "DASHBOARD_LOGIN is google, but .streamlit/secrets.toml has no complete "
                "[auth] section (client_id, client_secret, server_metadata_url, "
                "redirect_uri, cookie_secret). The README's Dashboard section has the "
                "steps. For local development only, DASHBOARD_LOGIN=off skips sign-in.",
            )
        try:
            email = google_email()
        except Unverified as err:
            _screen("Email not verified", f"Google hasn't verified {err}. Verify it, then sign in again.", sign_out=True)
        if email is None:
            _sign_in()
        with data.session() as s:
            ids = frozenset(repo.clinic_ids_for_email(s, email))
        viewer = Viewer(email=email, is_admin=email in cfg.admin_emails, clinic_ids=ids)
        if not viewer.is_admin and not ids:
            _screen(
                "No clinic yet",
                f"You're signed in as {email}, but no clinic has added this address. "
                "Ask the person who set up your clinic to add it on the Team tab.",
                sign_out=True,
            )
    st.session_state["_viewer"] = viewer
    return viewer


def viewer() -> Viewer:
    """The viewer require_viewer() set for this run (app.py always runs it first)."""
    return st.session_state["_viewer"]


def _sign_in() -> None:
    with st.columns([1, 2, 1])[1]:
        st.markdown('<p class="brand" style="text-align:center">Clinic <span>Console</span></p>', unsafe_allow_html=True)
        with theme.card("sign_in"):
            st.markdown('<p class="card-title">Sign in</p>', unsafe_allow_html=True)
            st.caption("Use the Google account your clinic added to the dashboard.")
            if st.button("Sign in with Google", type="primary", use_container_width=True):
                st.login()
    st.stop()


def _screen(title: str, message: str, sign_out: bool = False) -> None:
    with st.columns([1, 2, 1])[1]:
        st.markdown('<p class="brand" style="text-align:center">Clinic <span>Console</span></p>', unsafe_allow_html=True)
        with theme.card("gate"):
            st.markdown(f'<p class="card-title">{title}</p>', unsafe_allow_html=True)
            st.write(message)
            if sign_out and st.button("Sign out"):
                st.logout()
    st.stop()
