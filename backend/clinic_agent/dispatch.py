"""How a call says which clinic it is for.

One worker answers for every clinic. Whatever starts a call - the browser
call link today, a dialled phone number later - dispatches this agent by
name with the clinic in the job metadata. Writer and reader share this
module, so the format lives in exactly one place.
"""

from __future__ import annotations

import json

# The worker registers under this name (explicit dispatch): it joins only
# rooms it is dispatched to, never every room in the project.
AGENT_NAME = "clinic-receptionist"


class NoClinic(ValueError):
    """The call does not say which clinic it is for."""


def metadata_for(clinic_id: int) -> str:
    return json.dumps({"clinic_id": clinic_id})


def clinic_id_from(metadata: str, fallback: int | None = None) -> int:
    """The clinic a job is for. `fallback` is for local testing only
    (console has no dispatch); production passes none, so a call that
    names no clinic is refused rather than sent to a guessed one."""
    if metadata.strip():
        try:
            value = json.loads(metadata)["clinic_id"]
        except (ValueError, TypeError, KeyError):
            raise NoClinic(f"job metadata has no clinic_id: {metadata!r}") from None
        if not isinstance(value, int) or isinstance(value, bool):
            raise NoClinic(f"clinic_id must be an integer, got {value!r}")
        return value
    if fallback is None:
        raise NoClinic("job metadata is empty: the call was not dispatched with a clinic")
    return fallback
