"""Error tracking (Sentry) for the worker and the API: the only place that
imports sentry_sdk. Off unless SENTRY_DSN is set.

Calls carry patient data, so an error report carries the error and where it
happened, never what was said or who said it:
- no request bodies, cookies, headers or query strings; no user;
- no local variables in stack frames (they hold transcripts and names);
- no breadcrumbs (they repeat log lines);
- log lines only at ERROR and above become reports, with their arguments
  dropped;
- what is left (exception text, log message) has phone numbers and
  Devanagari scrubbed, in case an error quotes the caller.
No performance tracing: errors only.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

from clinic_agent.config import Settings

# Seven or more digits, with the separators people write numbers with.
_NUMBER = re.compile(r"\+?\d[\d\s-]{5,}\d")
# A Hindi passage from its first Devanagari letter to its last, with any
# numbers, spaces and punctuation in between: one "[hindi]", not fragments.
_DEVANAGARI = re.compile(r"[ऀ-ॿ](?:[ऀ-ॿ\d\s,.?!।-]*[ऀ-ॿ])?")


def scrub(text: str) -> str:
    """Phone numbers and Hindi words out of a string headed for Sentry."""
    return _NUMBER.sub("[number]", _DEVANAGARI.sub("[hindi]", text))


def before_send(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    request = event.get("request") or {}
    event["request"] = {k: request[k] for k in ("method", "url") if k in request}
    for key in ("user", "extra", "breadcrumbs"):
        event.pop(key, None)
    if "message" in event and isinstance(event["message"], str):
        event["message"] = scrub(event["message"])
    entry = event.get("logentry")
    if entry:
        entry.pop("params", None)
        for key in ("message", "formatted"):
            if isinstance(entry.get(key), str):
                entry[key] = scrub(entry[key])
    for exc in (event.get("exception") or {}).get("values", []):
        if isinstance(exc.get("value"), str):
            exc["value"] = scrub(exc["value"])
        for frame in (exc.get("stacktrace") or {}).get("frames", []):
            frame.pop("vars", None)
    return event


def start(cfg: Settings, component: str, **options: Any) -> bool:
    """Turn error tracking on for this process, once. `component` is
    "worker" or "api", a tag on every report. Returns whether it is on."""
    if not cfg.sentry_dsn:
        return False
    if not sentry_sdk.is_initialized():
        sentry_sdk.init(
            dsn=cfg.sentry_dsn,
            environment=cfg.sentry_environment,
            send_default_pii=False,
            include_local_variables=False,
            max_request_body_size="never",
            max_breadcrumbs=0,
            before_send=before_send,
            integrations=[LoggingIntegration(level=None, event_level=logging.ERROR)],
            **options,
        )
        sentry_sdk.set_tag("component", component)
    return True
