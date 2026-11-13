"""How the receptionist behaves, as set by the admin in the dashboard
(Harsh, 2026-11-10): what every clinic shares (the `system_settings` row)
and what each clinic sets for itself (columns on `clinics`).

One table of fields so the database defaults, the checks on save, the
one-time copy from .env and the refusal of leftover .env lines all agree.
Secrets, the database, LiveKit, sign-in, ports and URLs stay in .env
(clinic_agent/config.py): they are needed before the database opens, or
would let anyone who can write to the database take over.
"""

from __future__ import annotations

from dataclasses import dataclass

RULES_MAX_WORDS = 500  # Harsh, 2026-10-24: a long prompt costs every turn
INSTRUCTIONS_MAX_WORDS = 150
DIRECTIONS_MAX_CHARS = 300
LLM_VENDORS = ("sarvam", "openai")  # the allowed brains (repo CLAUDE.md)


@dataclass(frozen=True)
class Field:
    name: str  # column name
    kind: str  # "text" | "number" | "choice" | "flag"
    default: object
    env: str = ""  # the .env line it replaced ("" = new, never in .env)
    low: float | None = None
    high: float | None = None
    choices: tuple[str, ...] = ()
    max_words: int | None = None
    max_chars: int | None = None
    optional: bool = False  # a number that may be blank (None: the vendor's own default)


SYSTEM = (
    Field("rules", "text", "", max_words=RULES_MAX_WORDS),  # "" = the default in prompts.py
    Field("hindi_llm", "choice", "openai", env="HINDI_LLM", choices=LLM_VENDORS),
    Field("sarvam_llm_model", "text", "", env="SARVAM_LLM_MODEL", max_chars=100),
    Field("openai_llm_model", "text", "", env="OPENAI_LLM_MODEL", max_chars=100),
    Field("sarvam_stt_model", "text", "", env="SARVAM_STT_MODEL", max_chars=100),
    Field("sarvam_stt_language", "text", "", env="SARVAM_STT_LANGUAGE", max_chars=20),
    Field("sarvam_stt_mode", "text", "transcribe", env="SARVAM_STT_MODE", max_chars=30),
    Field("min_endpointing_delay", "number", 0.2, env="MIN_ENDPOINTING_DELAY", low=0.0, high=5.0),
    Field("number_endpointing_delay", "number", 1.5, env="NUMBER_ENDPOINTING_DELAY", low=0.0, high=5.0),
    Field("interrupt_min_speech", "number", 0.3, env="INTERRUPT_MIN_SPEECH", low=0.05, high=3.0),
    Field("vad_min_silence", "number", 0.6, env="VAD_MIN_SILENCE", low=0.1, high=3.0),
    Field("greeting_interruptible", "flag", False),
)

CLINIC = (
    Field("instructions", "text", "", max_words=INSTRUCTIONS_MAX_WORDS),
    Field("directions", "text", "", max_chars=DIRECTIONS_MAX_CHARS),
    # Model and speaker together (2026-11-10): a speaker only exists in some
    # models, so they are set and checked side by side, per clinic.
    Field("tts_model", "text", "", env="SARVAM_TTS_MODEL", max_chars=100),
    Field("tts_speaker", "text", "", env="SARVAM_TTS_SPEAKER", max_chars=50),
    Field("tts_pace", "number", 1.0, env="SARVAM_TTS_PACE", low=0.5, high=2.0),
    Field("tts_pitch", "number", None, env="SARVAM_TTS_PITCH", low=-0.5, high=0.5, optional=True),
    Field("max_call_minutes", "number", 10.0, env="MAX_CALL_MINUTES", low=1.0, high=60.0),
)

MOVED_ENV = tuple(f.env for f in (*SYSTEM, *CLINIC) if f.env)


def field(scope: tuple[Field, ...], name: str) -> Field:
    for f in scope:
        if f.name == name:
            return f
    raise KeyError(f"unknown setting {name!r}")


def checked(f: Field, value: object) -> object:
    """`value` as stored, or ValueError with a message for the admin."""
    if f.kind == "flag":
        if not isinstance(value, bool):
            raise ValueError(f"{f.name} must be on or off.")
        return value
    if f.kind == "number":
        if value is None or value == "":
            if f.optional:
                return None
            raise ValueError(f"{f.name} needs a number.")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{f.name} must be a number.") from None
        if not f.low <= number <= f.high:
            raise ValueError(f"{f.name} must be between {f.low:g} and {f.high:g}.")
        return round(number, 3)
    text = str(value if value is not None else "").strip()
    if f.kind == "choice":
        text = text.lower()
        if text not in f.choices:
            raise ValueError(f"{f.name} must be one of: {', '.join(f.choices)}.")
        return text
    if f.max_words is not None and len(text.split()) > f.max_words:
        raise ValueError(f"{f.name} is {len(text.split())} words; at most {f.max_words}.")
    if f.max_chars is not None and len(text) > f.max_chars:
        raise ValueError(f"{f.name} is {len(text)} characters; at most {f.max_chars}.")
    return text


def from_env(f: Field, raw: str) -> object:
    """A value copied once from its old .env line (migrations)."""
    if f.kind == "number":
        return checked(f, raw.strip() or None) if f.optional else checked(f, raw)
    return checked(f, raw)
