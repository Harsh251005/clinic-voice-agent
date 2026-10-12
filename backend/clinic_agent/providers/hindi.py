"""Names in Hindi: how the Hindi line should say a clinic's or doctor's name,
suggested from the English one (Harsh, 2026-10-12: typing Devanagari by hand
is a hassle). Staff see the suggestion in the settings box and can change it.

One short text request to OpenAI (an allowed LLM vendor; no speech, no
Sarvam credits), a fast model since staff wait on it while typing.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from functools import lru_cache

import openai

from clinic_agent.config import Settings, require_key

MODEL = "gpt-4.1-mini"  # fastest of the capable models measured 2026-10-12 (~1 s)
TIMEOUT = 8.0  # seconds: a settings form, not a call

INSTRUCTIONS = (
    "You write the names of Indian clinics and doctors in Devanagari, the way a Hindi-speaking "
    "clinic receptionist says them aloud on the phone. Go by sound, not by translation: English "
    "words stay English, written as they sound in Hindi (Clinic -> क्लिनिक, Family -> फ़ैमिली, "
    "Dental -> डेंटल, Eye Care -> आई केयर); \"Dr.\" or \"Doctor\" -> \"डॉक्टर\". Indian names in "
    "their usual Hindi spelling (Mehta -> मेहता). Reply with only the Devanagari name."
)

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


class NoSuggestion(RuntimeError):
    """The vendor failed or answered with something that isn't a Devanagari name."""


def suggest(cfg: Settings, name: str, known: Mapping[str, str] | None = None) -> str:
    """`name` as the Hindi line should say it. `known`: words this clinic
    already spells ({"Dharnidharka": "धरनिधरका"}), so a surname in the clinic's
    and a doctor's name comes out the same both times. Raises ConfigError
    without an OpenAI key, NoSuggestion if the request fails or the answer
    isn't usable."""
    name = " ".join(name.split())
    if not name:
        return ""
    words = {w.lower() for w in re.findall(r"[A-Za-z]+", name)}
    used = tuple(sorted((k, v) for k, v in (known or {}).items() if k.lower() in words))
    return _suggest(require_key(cfg.openai_api_key, "OPENAI_API_KEY"), name, used)


@lru_cache(maxsize=512)  # the same name (and spellings) always gets the same answer, and costs once
def _suggest(api_key: str, name: str, known: tuple[tuple[str, str], ...]) -> str:
    asked = name if not known else (
        name + "\nSpell these words exactly as the clinic already does: "
        + "; ".join(f"{word} = {hindi_word}" for word, hindi_word in known)
    )
    try:
        reply = openai.OpenAI(api_key=api_key, timeout=TIMEOUT, max_retries=1).chat.completions.create(
            model=MODEL, temperature=0, max_tokens=80,
            messages=[{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": asked}],
        )
    except openai.OpenAIError as err:
        raise NoSuggestion(type(err).__name__) from None
    text = " ".join((reply.choices[0].message.content or "").strip().strip('"\'`').split())
    if not _DEVANAGARI.search(text) or re.search(r"[A-Za-z]", text) or len(text) > 200:
        raise NoSuggestion("not a Devanagari name")
    return text


def glossary(pairs: list[tuple[str, str]]) -> dict[str, str]:
    """Word-by-word spellings from names already written in Hindi, where the
    words line up one to one ("Dr. Harsh Dharnidharka" / "डॉक्टर हर्ष धरनिधरका")."""
    out: dict[str, str] = {}
    for name, name_hi in pairs:
        english, devanagari = re.findall(r"[A-Za-z]+", name), name_hi.split()
        if name_hi and len(english) == len(devanagari):
            out.update({w: d for w, d in zip(english, devanagari) if w.lower() not in ("dr", "doctor")})
    return out
