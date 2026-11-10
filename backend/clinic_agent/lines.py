"""The language line: which vendors answer a call.

Hindi is the only line (Harsh, 2026-11-08: Hindi first, made reliable before
anything else): Sarvam ears, Sarvam voice, and a brain set by HINDI_LLM:
Sarvam by default, OpenAI to compare the two. The dispatch still names the
call's language (always "hi"), so a second line later is one more entry.

A line whose keys are missing is unavailable, not a crash: the worker says
why and exits, its check-in says which lines are up, and the dashboards flag
the missing one.
"""

from __future__ import annotations

from dataclasses import dataclass

from clinic_agent.config import ConfigError, Settings
from clinic_agent.dispatch import LANGUAGES, Language
from clinic_agent.providers import build_llm, build_stt, build_tts


@dataclass(frozen=True)
class Line:
    language: Language
    stt: str  # vendor names: keys into the providers' BUILDERS
    llm: str
    tts: str


NAMES: dict[Language, str] = {"hi": "Hindi"}


def line_for(cfg: Settings, language: Language) -> Line:
    """The vendors that answer a call in `language`."""
    return Line(language, stt="sarvam", llm=cfg.hindi_llm, tts="sarvam")


def why_unavailable(cfg: Settings, line: Line, text_only: bool = False) -> str | None:
    """None if the line can take a call; else why not: a missing key, or
    settings the vendor refuses (a speaker the voice model doesn't have).
    Building the providers is the check: each builder asks for its own key.
    Text-only (console --text) needs only the line's LLM."""
    try:
        build_llm(cfg, line.llm)
        if not text_only:
            build_stt(cfg, line.stt)
            build_tts(cfg, line.tts)
    except (ConfigError, ValueError) as err:
        return _short(str(err))
    return None


def _short(why: str) -> str:
    """A vendor's message, without its list of every allowed value."""
    return why.split(". Please choose", 1)[0].split(" Compatible speakers", 1)[0]


def available(cfg: Settings, text_only: bool = False) -> dict[Language, str | None]:
    """Each language and why it can't take calls (None: it can)."""
    return {lang: why_unavailable(cfg, line_for(cfg, lang), text_only) for lang in LANGUAGES}
