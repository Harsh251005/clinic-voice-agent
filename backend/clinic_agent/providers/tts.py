"""Text-to-speech builders.

Every builder returns a `livekit.agents.tts.TTS`.
"""

from __future__ import annotations

from collections.abc import Callable

from livekit.agents import tts
from livekit.plugins import sarvam

from clinic_agent.config import Settings, require_key
from clinic_agent.providers import defaults
from clinic_agent.providers.sentences import MAX_PIECE, SentenceTokenizer


def _sarvam(cfg: Settings) -> tts.TTS:
    # The plugin defaults to mp3, which costs a decode on every chunk;
    # linear16 hands LiveKit raw PCM instead. Speaker must be a bulbul:v3 voice.
    voice = sarvam.TTS(
        model=cfg.sarvam_tts_model or defaults.SARVAM_TTS_MODEL,
        speaker=cfg.sarvam_tts_speaker or defaults.SARVAM_TTS_SPEAKER,
        # Sarvam speaks the Hindi line, whose replies are Devanagari.
        target_language_code=cfg.sarvam_tts_language or "hi-IN",
        speech_sample_rate=cfg.sarvam_tts_sample_rate or 24000,
        output_audio_codec=cfg.sarvam_tts_codec or "linear16",
        # Blank = Sarvam's own 1.0 and 0.0. Pitch is a fixed setting, applied
        # by bulbul:v4-flash only (the plugin sends it for no other model).
        pace=cfg.sarvam_tts_pace if cfg.sarvam_tts_pace is not None else 1.0,
        pitch=cfg.sarvam_tts_pitch,
        # Sarvam re-cuts any text longer than this, wherever the count lands,
        # and voices each part as a new take. Ours arrive already cut at
        # sentence ends (sentences.py), so it must never cut them again.
        max_chunk_length=max(500, MAX_PIECE),
        api_key=require_key(cfg.sarvam_api_key, "SARVAM_API_KEY"),
    )
    # The plugin has no argument for its splitter and hard-codes LiveKit's,
    # which doesn't know the Hindi full stop "।". test_providers guards this.
    voice._opts.word_tokenizer = SentenceTokenizer()
    return voice


def identity(voice: tts.TTS) -> dict:
    """Everything about `voice` that changes how a phrase sounds, read from the
    built object so the builders stay the one home of the defaults: a recorded
    clip is only reused while all of it is the same (clinic_agent/voice_clips.py)."""
    if isinstance(voice, sarvam.TTS):
        opts = voice._opts
        return {
            "vendor": "sarvam", "model": opts.model, "voice": opts.speaker,
            "language_code": str(opts.target_language_code),
            "sample_rate": opts.speech_sample_rate, "codec": opts.output_audio_codec,
            "pace": opts.pace, "pitch": opts.pitch,
        }
    raise TypeError(f"unknown voice {type(voice).__name__}: add it to providers/tts.py identity")


# Sarvam is the only allowed TTS vendor (the Hindi line). Don't add others.
BUILDERS: dict[str, Callable[[Settings], tts.TTS]] = {
    "sarvam": _sarvam,
}


def build_tts(cfg: Settings, vendor: str) -> tts.TTS:
    """`vendor`'s TTS, as the Hindi line names it (clinic_agent/lines.py)."""
    try:
        builder = BUILDERS[vendor]
    except KeyError:
        raise ValueError(f"unknown TTS vendor {vendor!r}; available: {sorted(BUILDERS)}") from None
    return builder(cfg)
