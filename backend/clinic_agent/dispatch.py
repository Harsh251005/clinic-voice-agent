"""How a call says which clinic it is for, and in which language.

One worker answers for every clinic. Whatever starts a call - the browser
call link today, a dialled phone number later - dispatches this agent by
name with the clinic and the caller's chosen language in the job metadata.
Writer and reader share this module, so the format lives in exactly one place.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal, get_args

# The worker registers under this name (explicit dispatch): it joins only
# rooms it is dispatched to, never every room in the project.
AGENT_NAME = "clinic-receptionist"

# The caller picks one before the call starts. Each is answered by its own
# speech pipeline, so a call is never in a language it wasn't set up for.
Language = Literal["en", "hi"]
LANGUAGES: tuple[Language, ...] = get_args(Language)


class BadDispatch(ValueError):
    """The call does not say which clinic it is for, or in which language."""


@dataclass(frozen=True)
class CallFor:
    clinic_id: int
    language: Language


def language_of(value: object) -> Language:
    """`value` as a Language, or BadDispatch."""
    if value not in LANGUAGES:
        raise BadDispatch(f"language must be one of {', '.join(LANGUAGES)}, got {value!r}")
    return value  # type: ignore[return-value]


def metadata_for(clinic_id: int, language: Language) -> str:
    return json.dumps({"clinic_id": clinic_id, "language": language_of(language)})


def call_from(metadata: str, fallback: CallFor | None = None) -> CallFor:
    """The clinic and language a job is for. `fallback` is for local testing
    only (console has no dispatch); production passes none, so a call that
    names no clinic or language is refused rather than answered on a guess."""
    if not metadata.strip():
        if fallback is None:
            raise BadDispatch("job metadata is empty: the call was not dispatched with a clinic")
        return fallback
    try:
        fields = json.loads(metadata)
        clinic_id, language = fields["clinic_id"], fields["language"]
    except (ValueError, TypeError, KeyError):
        raise BadDispatch(f"job metadata needs clinic_id and language: {metadata!r}") from None
    if not isinstance(clinic_id, int) or isinstance(clinic_id, bool):
        raise BadDispatch(f"clinic_id must be an integer, got {clinic_id!r}")
    return CallFor(clinic_id, language_of(language))
