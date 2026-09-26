"""Who is asking, and what they may touch. Every dashboard route goes through
these dependencies; tests replace `current_viewer` with dependency_overrides.

The session cookie holds only the signed-in email. Which clinics that email
may open is read from the database on every request, so removing someone on
the Team tab takes effect at once.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request

from clinic_agent.booking import BookingError
from clinic_agent.store import repo

# State-changing requests must carry this header. A form or image on another
# site can't add custom headers, so this blocks cross-site requests riding on
# the session cookie (CSRF); SameSite=Lax on the cookie is the second layer.
CSRF_HEADER = "x-clinic-console"


@dataclass(frozen=True)
class Viewer:
    email: str  # "" when sign-in is off
    is_admin: bool
    clinic_ids: frozenset[int]  # clinics this email is a member (staff) of
    signed_out: bool = False  # sign-in is off (local testing): sees everything

    def may_open(self, clinic_id: int) -> bool:
        """Settings, doctors, hours: members, and admins (who set clinics up)."""
        return self.is_admin or clinic_id in self.clinic_ids

    def is_staff(self, clinic_id: int) -> bool:
        """Patient data (appointments, patients, call transcripts): the
        clinic's own members only. Being admin is not enough: the operator
        runs the service, not the clinic's diary. An admin who is also a
        member (their own clinic) sees it as staff."""
        return self.signed_out or clinic_id in self.clinic_ids


def current_viewer(request: Request) -> Viewer:
    cfg = request.app.state.cfg
    if cfg.dashboard_login == "off":
        return Viewer(email="", is_admin=True, clinic_ids=frozenset(), signed_out=True)
    email = request.session.get("email")
    if not email:
        raise HTTPException(401, "Sign in first.")
    with request.app.state.sessions() as s:
        ids = frozenset(repo.clinic_ids_for_email(s, email))
    return Viewer(email=email, is_admin=email in cfg.admin_emails, clinic_ids=ids)


def open_clinic(clinic_id: int, viewer: Viewer = Depends(current_viewer)) -> int:
    """The clinic in the URL, if this viewer may open it. 404 rather than 403,
    so a stranger can't tell which clinic ids exist."""
    if not viewer.may_open(clinic_id):
        raise HTTPException(404, "No such clinic.")
    return clinic_id


def clinic_staff(clinic_id: int, viewer: Viewer = Depends(current_viewer)) -> int:
    """The clinic in the URL, if this viewer is its staff. Strangers get the
    same 404 as open_clinic; an admin who isn't a member is told why."""
    open_clinic(clinic_id, viewer)
    if not viewer.is_staff(clinic_id):
        raise HTTPException(403, "Only the clinic's own staff can see its patients and calls.")
    return clinic_id


def admin(viewer: Viewer = Depends(current_viewer)) -> Viewer:
    if not viewer.is_admin:
        raise HTTPException(403, "Only admins can do that.")
    return viewer


def same_site(request: Request) -> None:
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(403, f"Missing the {CSRF_HEADER} header.")


@contextmanager
def staff_errors():
    """Rule violations become messages staff can read: a ValueError from the
    repo (bad slug, overlapping sittings...) or a BookingError (overlapping
    booking, bad mobile number) is a 422 with its message, and a row outside
    the clinic is a 404."""
    try:
        yield
    except repo.NotFound:
        raise HTTPException(404, "Not found.") from None
    except (ValueError, BookingError) as err:
        raise HTTPException(422, str(err)) from None
