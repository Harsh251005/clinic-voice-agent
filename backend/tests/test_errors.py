"""Error tracking: off without a DSN, and when on, a report carries the
error and where it happened, never what a caller said or their number.
Reports are captured by a local transport through Sentry's real pipeline."""

import json
import logging

import pytest
import sentry_sdk
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

from clinic_agent import errors
from clinic_agent.config import load_settings

SAID = "मेरा नंबर 98765 43210 है, बुखार है"


class Capture(Transport):
    def __init__(self):
        super().__init__()
        self.events = []

    def capture_envelope(self, envelope):
        event = envelope.get_event()
        if event is not None:
            self.events.append(event)


@pytest.fixture
def sent(env):
    env.setenv("SENTRY_DSN", "https://public@o0.ingest.sentry.io/0")
    capture = Capture()
    assert errors.start(load_settings(), "worker", transport=capture)
    yield capture.events
    sentry_sdk.get_client().close()
    sentry_sdk.get_global_scope().set_client(None)


def _text(events) -> str:
    """The reports as sent, minus the source lines around each frame: those
    are our own code (here, this test file, which spells out the secrets)."""
    events = json.loads(json.dumps(events, default=str))
    for event in events:
        for exc in (event.get("exception") or {}).get("values", []):
            for frame in (exc.get("stacktrace") or {}).get("frames", []):
                for key in ("pre_context", "context_line", "post_context"):
                    frame.pop(key, None)
    return json.dumps(events, ensure_ascii=False)


def test_off_without_a_dsn(env):
    assert errors.start(load_settings(), "worker") is False
    assert not sentry_sdk.is_initialized()


def test_an_exception_is_reported_without_locals_or_what_was_said(sent):
    def book(patient_phone="9876543210", transcript=SAID):
        raise ValueError(f"no slot for {patient_phone}: {transcript}")

    try:
        book()
    except ValueError:
        sentry_sdk.capture_exception()
    (event,) = sent
    (exc,) = event["exception"]["values"]
    assert exc["type"] == "ValueError" and exc["value"] == "no slot for [number]: [hindi]"
    assert all("vars" not in f for f in exc["stacktrace"]["frames"])
    assert event["tags"]["component"] == "worker"
    for secret in ("9876543210", "बुखार", "98765 43210"):
        assert secret not in _text(sent)


def test_error_logs_are_reported_without_their_arguments(sent):
    log = logging.getLogger("clinic-agent.test")
    log.warning("slow reply for %s", "9876543210")  # below ERROR: not reported
    log.error("booking failed for %s", "9876543210")
    (event,) = sent
    assert event["logentry"]["message"] == "booking failed for %s" and "params" not in event["logentry"]
    assert "9876543210" not in _text(sent) and "breadcrumbs" not in event


def test_an_api_crash_is_reported_without_the_request_body(sent):
    app = FastAPI()

    @app.post("/api/clinics/{clinic_id}/appointments")
    def book(clinic_id: int, body: dict):
        raise RuntimeError("database gone")

    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/api/clinics/1/appointments?name=Riya", json={"patient_phone": "9876543210", "reason": SAID},
                    headers={"cookie": "clinic_console=secret-session"})
    assert r.status_code == 500
    (event,) = sent
    assert set(event["request"]) <= {"method", "url"} and event["request"]["method"] == "POST"
    for secret in ("9876543210", "बुखार", "secret-session", "Riya"):
        assert secret not in _text(sent)


def test_scrub_leaves_ordinary_error_text_alone():
    assert errors.scrub("APIStatusError 503 from sarvam/bulbul:v3, retried 2 times") == \
        "APIStatusError 503 from sarvam/bulbul:v3, retried 2 times"
    assert errors.scrub("call +91 98200-12345 ended") == "call [number] ended"


def test_scrub_turns_a_hindi_passage_into_one_marker():
    assert errors.scrub(f"caller said {SAID} then hung up") == "caller said [hindi] then hung up"
