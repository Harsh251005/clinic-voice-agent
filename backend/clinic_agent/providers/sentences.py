"""How the agent's reply is cut into pieces for the voice engine.

The LLM streams its reply a few characters at a time; the TTS voices whatever
piece it is handed as one take. A piece that ends mid-sentence makes the
voice restart with a new tone halfway through. So pieces end where a person
would pause:

1. at the end of a sentence: । ॥ . ? ! (LiveKit's own splitter doesn't know
   the Hindi full stop, so a Hindi reply went out as one long block that the
   vendor then cut at an arbitrary character count);
2. a sentence longer than MAX_PIECE is cut at its last comma, semicolon or
   dash that fits;
3. only a sentence with none of those is cut at a space.

Pieces shorter than MIN_PIECE ("जी।") are joined to the next one, so a short
opener is not voiced alone.
"""

from __future__ import annotations

import re

from livekit.agents import tokenize
from livekit.agents.tokenize import token_stream

MIN_PIECE = 20  # characters; shorter sentences are joined to the next
MAX_PIECE = 220  # characters; the vendor must be set to accept at least this
CONTEXT = 10  # characters to wait for after a stop before cutting ("5.30")

_SENTENCE_END = re.compile(r"[।॥?!]+|\.+")
_SOFT_BREAK = re.compile(r"[,;:—–]\s")
_TITLE = re.compile(r"\b(?:Dr|Mr|Mrs|Ms|Prof)$", re.IGNORECASE)


def split_sentences(text: str) -> list[tuple[str, int, int]]:
    """Pieces as (text, start, end), ends inclusive of their punctuation."""
    pieces: list[tuple[str, int, int]] = []
    start = 0
    for stop in _SENTENCE_END.finditer(text):
        if stop.group() == "." and _not_an_end(text, stop.start()):
            continue
        pieces.extend(_cap(text, start, stop.end()))
        start = stop.end()
    pieces.extend(_cap(text, start, len(text)))
    return [p for p in pieces if p[0]]


def _not_an_end(text: str, dot: int) -> bool:
    """A dot inside a title or a number: "Dr. Mehta", "5.30"."""
    before, after = text[:dot], text[dot + 1 : dot + 2]
    return bool(_TITLE.search(before)) or (before[-1:].isdigit() and after.isdigit())


def _cap(text: str, start: int, end: int) -> list[tuple[str, int, int]]:
    """One sentence, cut into pieces of at most MAX_PIECE characters."""
    out = []
    while end - start > MAX_PIECE:
        window = text[start : start + MAX_PIECE]
        soft = [m.end() for m in _SOFT_BREAK.finditer(window)]
        cut = soft[-1] if soft else window.rfind(" ") + 1
        if cut <= 0:  # one unbroken run of characters: cut it where it is
            cut = MAX_PIECE
        out.append(_piece(text, start, start + cut))
        start += cut
    out.append(_piece(text, start, end))
    return out


def _piece(text: str, start: int, end: int) -> tuple[str, int, int]:
    raw = text[start:end]
    lead = len(raw) - len(raw.lstrip())
    return raw.strip(), start + lead, start + lead + len(raw.strip())


class SentenceTokenizer(tokenize.SentenceTokenizer):
    """LiveKit's sentence-tokenizer interface over `split_sentences`."""

    def tokenize(self, text: str, *, language: str | None = None) -> list[str]:
        return [p[0] for p in split_sentences(text)]

    def stream(self, *, language: str | None = None) -> tokenize.SentenceStream:
        return token_stream.BufferedSentenceStream(
            tokenizer=split_sentences, min_token_len=MIN_PIECE, min_ctx_len=CONTEXT,
        )
