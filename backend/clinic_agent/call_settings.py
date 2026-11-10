"""A call's settings: the admin's choices from the dashboard (what every
clinic shares, and this clinic's own; clinic_agent/receptionist_settings.py)
laid over .env's secrets and plumbing. Read when the call starts, so a change
in the dashboard applies from the next call, no restart (Harsh, 2026-11-10).

The result is an ordinary `Settings`, so the vendor builders, the session
and the call limit keep their one input; only the rules text and the
greeting rule travel beside it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from clinic_agent.config import Settings


@dataclass(frozen=True)
class CallSettings:
    cfg: Settings  # .env with the dashboard's values in place of the moved lines
    rules: str  # the admin's rules text; "" = the default in prompts.py
    greeting_interruptible: bool


def _blank(text: str) -> str | None:
    """A text setting left blank: None, so the vendor's builder uses its own default."""
    return text.strip() or None


def merge(cfg: Settings, system, clinic) -> CallSettings:
    """`system` is the system_settings row, `clinic` the call's clinic (or
    None outside a call: then the clinic's own settings stay as in `cfg`)."""
    shared = replace(
        cfg,
        hindi_llm=system.hindi_llm,
        sarvam_llm_model=_blank(system.sarvam_llm_model),
        openai_llm_model=_blank(system.openai_llm_model),
        sarvam_stt_model=_blank(system.sarvam_stt_model),
        sarvam_stt_language=_blank(system.sarvam_stt_language),
        sarvam_stt_mode=system.sarvam_stt_mode.strip() or "transcribe",
        min_endpointing_delay=system.min_endpointing_delay,
        number_endpointing_delay=system.number_endpointing_delay,
        interrupt_min_speech=system.interrupt_min_speech,
        vad_min_silence=system.vad_min_silence,
    )
    if clinic is not None:
        shared = replace(
            shared,
            sarvam_tts_model=_blank(clinic.tts_model),
            sarvam_tts_speaker=_blank(clinic.tts_speaker),
            sarvam_tts_pace=clinic.tts_pace,
            sarvam_tts_pitch=clinic.tts_pitch,
            max_call_minutes=clinic.max_call_minutes,
        )
    return CallSettings(shared, system.rules, system.greeting_interruptible)
