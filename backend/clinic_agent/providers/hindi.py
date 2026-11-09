"""Hindi from English, so nobody types Devanagari (Harsh, 2026-10-12 and
2026-10-27): how the Hindi line should say a clinic's or doctor's name
(`suggest`), and the receptionist's fixed phrases (`translate_phrase`: the
greeting, "one moment" lines, goodbyes). Staff see the Hindi and can change it.

One short text request to OpenAI (an allowed LLM vendor; no speech, no
Sarvam credits), a fast model since staff wait on it while typing.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Callable, Mapping

import openai

from clinic_agent.config import Settings, require_key

MODEL = "gpt-4.1-mini"  # fastest of the capable models measured 2026-10-12 (~1 s)
TIMEOUT = 8.0  # seconds: a settings form, not a call
CACHE_SIZE = 512  # the same name (and spellings) always gets the same answer, and costs once

# What a request used, for the admin panel's costs: (model, tokens in, of
# them cached, tokens out). Called only when OpenAI was actually asked.
OnUsage = Callable[[str, int, int, int], None]
_cache: OrderedDict[tuple, str] = OrderedDict()

INSTRUCTIONS = (
    "You write the names of Indian clinics and doctors in Devanagari, the way a Hindi-speaking "
    "clinic receptionist says them aloud on the phone. Go by sound, not by translation: English "
    "words stay English, written as they sound in Hindi (Clinic -> क्लिनिक, Family -> फ़ैमिली, "
    "Dental -> डेंटल, Eye Care -> आई केयर); \"Dr.\" or \"Doctor\" -> \"डॉक्टर\". Indian names in "
    "their usual Hindi spelling (Mehta -> मेहता). Reply with only the Devanagari name."
)

PHRASE_INSTRUCTIONS = (
    "You turn a clinic phone receptionist's English line into the Hindi she says aloud. She is a "
    "woman: every word about herself is feminine (मैं देखती हूँ, बताती हूँ, कर सकती हूँ, असिस्टेंट हूँ), "
    "never masculine. She speaks to the caller with the respectful आप and जी, never assuming their "
    "gender. Everyday spoken Hindi of a city clinic, never bookish: ज़रा not कृपया, खाली not उपलब्ध. "
    "Keep the English words people say every day, written in Devanagari (अपॉइंटमेंट, क्लिनिक, "
    "ऑटोमेटेड असिस्टेंट, टेक्स्ट). Write numbers as Hindi words. Use only । ? and , as punctuation. "
    "Keep every {placeholder} such as {clinic} exactly as written, in English letters. "
    "Write everything else in Devanagari. Reply with only the Hindi line."
)
PHRASE_TOKENS = 400  # a 500-character English line comes back well under this

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_PLACEHOLDER = re.compile(r"\{[a-z_]+\}")


class NoSuggestion(RuntimeError):
    """The vendor failed or answered with something that isn't a Devanagari name."""


def suggest(cfg: Settings, name: str, known: Mapping[str, str] | None = None, on_usage: OnUsage | None = None) -> str:
    """`name` as the Hindi line should say it. `known`: words this clinic
    already spells ({"Dharnidharka": "धरनिधरका"}), so a surname in the clinic's
    and a doctor's name comes out the same both times. Raises ConfigError
    without an OpenAI key, NoSuggestion if the request fails or the answer
    isn't usable. `on_usage` hears what a request to OpenAI used (none for
    an answer from the cache)."""
    name = " ".join(name.split())
    if not name:
        return ""
    words = {w.lower() for w in re.findall(r"[A-Za-z]+", name)}
    used = tuple(sorted((k, v) for k, v in (known or {}).items() if k.lower() in words))
    key = (require_key(cfg.openai_api_key, "OPENAI_API_KEY"), name, used)
    asked = _with_spellings(name, used)
    return _cached(key, lambda: _name_or_none(_ask(key[0], INSTRUCTIONS, asked, 80, on_usage)))


def translate_phrase(cfg: Settings, english: str, known: Mapping[str, str] | None = None,
                     on_usage: OnUsage | None = None) -> str:
    """A fixed phrase the receptionist says (greeting, "one moment", goodbye),
    from the English an admin typed into the Hindi she speaks. Placeholders
    such as {clinic} come back unchanged. `known`: the clinic's own Hindi
    spellings of words in it. Raises like `suggest`."""
    english = " ".join(english.split())
    if not english:
        return ""
    words = {w.lower() for w in re.findall(r"[A-Za-z]+", _PLACEHOLDER.sub("", english))}
    used = tuple(sorted((k, v) for k, v in (known or {}).items() if k.lower() in words))
    key = (require_key(cfg.openai_api_key, "OPENAI_API_KEY"), "phrase", english, used)
    asked = _with_spellings(english, used)
    return _cached(key, lambda: _phrase_or_none(english, _ask(key[0], PHRASE_INSTRUCTIONS, asked, PHRASE_TOKENS, on_usage)))


def _with_spellings(text: str, used: tuple[tuple[str, str], ...]) -> str:
    if not used:
        return text
    return text + "\nSpell these words exactly as the clinic already does: " + "; ".join(f"{w} = {h}" for w, h in used)


def _cached(key: tuple, make: Callable[[], str]) -> str:
    """The same question always gets the same answer, and costs once."""
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    text = make()
    _cache[key] = text
    if len(_cache) > CACHE_SIZE:
        _cache.popitem(last=False)
    return text


def _ask(api_key: str, instructions: str, asked: str, max_tokens: int, on_usage: OnUsage | None) -> str:
    """One request to OpenAI; its answer on one line, quotes trimmed."""
    try:
        reply = openai.OpenAI(api_key=api_key, timeout=TIMEOUT, max_retries=1).chat.completions.create(
            model=MODEL, temperature=0, max_tokens=max_tokens,
            messages=[{"role": "system", "content": instructions}, {"role": "user", "content": asked}],
        )
    except openai.OpenAIError as err:
        raise NoSuggestion(type(err).__name__) from None
    if on_usage is not None and (used := getattr(reply, "usage", None)) is not None:
        details = getattr(used, "prompt_tokens_details", None)
        on_usage(MODEL, used.prompt_tokens, (getattr(details, "cached_tokens", 0) or 0), used.completion_tokens)
    return " ".join((reply.choices[0].message.content or "").strip().strip('"\'`').split())


def _name_or_none(text: str) -> str:
    if not _DEVANAGARI.search(text) or re.search(r"[A-Za-z]", text) or len(text) > 200:
        raise NoSuggestion("not a Devanagari name")
    return text


def _phrase_or_none(english: str, text: str) -> str:
    """Devanagari with the same placeholders as the English, and no other
    English letters: the voice reads Roman letters with English spelling rules."""
    if sorted(_PLACEHOLDER.findall(text)) != sorted(_PLACEHOLDER.findall(english)):
        raise NoSuggestion("placeholders changed")
    rest = _PLACEHOLDER.sub("", text)
    if not _DEVANAGARI.search(rest) or re.search(r"[A-Za-z]", rest) or len(text) > 500:
        raise NoSuggestion("not a Devanagari phrase")
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
