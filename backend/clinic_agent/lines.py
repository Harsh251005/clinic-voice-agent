"""The two language lines: which vendors answer a call in each language.

The caller picks English or Hindi before the call starts (dispatch.Language)
and keeps it for the whole call: switching lines mid-call would change the
voice. Each line is its own pipeline, tuned for its language only:

- English: ElevenLabs ears, OpenAI brain, ElevenLabs voice.
- Hindi:   Sarvam ears, brain and voice.

A line whose keys are missing is unavailable, not fatal: the worker answers
on the other line, its check-in says which lines are up, the call page
offers only those, and the dashboards flag the missing one.
"""

from __future__ import annotations

from dataclasses import dataclass

from clinic_agent.config import ConfigError, Settings
from clinic_agent.dispatch import Language
from clinic_agent.providers import build_llm, build_stt, build_tts


@dataclass(frozen=True)
class Line:
    language: Language
    stt: str  # vendor names: keys into the providers' BUILDERS
    llm: str
    tts: str


LINES: dict[Language, Line] = {
    "en": Line("en", stt="elevenlabs", llm="openai", tts="elevenlabs"),
    "hi": Line("hi", stt="sarvam", llm="sarvam", tts="sarvam"),
}

NAMES: dict[Language, str] = {"en": "English", "hi": "Hindi"}


def why_unavailable(cfg: Settings, line: Line, text_only: bool = False) -> str | None:
    """None if the line can take a call; else why not (a missing key).
    Building the providers is the check: each builder asks for its own key.
    Text-only (console --text) needs only the line's LLM."""
    try:
        build_llm(cfg, line.llm)
        if not text_only:
            build_stt(cfg, line.stt)
            build_tts(cfg, line.tts)
    except ConfigError as err:
        return str(err)
    return None


def available(cfg: Settings, text_only: bool = False) -> dict[Language, str | None]:
    """Each language and why it can't take calls (None: it can)."""
    return {lang: why_unavailable(cfg, line, text_only) for lang, line in LINES.items()}
