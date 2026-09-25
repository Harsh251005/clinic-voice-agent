"""Speech-to-text builders.

Every builder returns a `livekit.agents.stt.STT`. That ABC is the seam - the
rest of the codebase only ever sees it, never a vendor class.
"""

from __future__ import annotations

from collections.abc import Callable

from livekit.agents import stt
from livekit.plugins import elevenlabs, sarvam

from clinic_agent.config import Settings, require_key


def _sarvam(cfg: Settings) -> stt.STT:
    # sarvam.STT declares streaming=True and does its own endpointing over a
    # websocket the plugin owns, so no separate VAD is wired in.
    return sarvam.STT(
        model=cfg.sarvam_stt_model or "saaras:v3",
        # "unknown" auto-detects per utterance: callers mix Hindi and English.
        language=cfg.sarvam_stt_language or "unknown",
        mode=cfg.sarvam_stt_mode,
        sample_rate=cfg.stt_sample_rate,
        api_key=require_key(cfg.sarvam_api_key, "SARVAM_API_KEY"),
    )


def _elevenlabs(cfg: Settings) -> stt.STT:
    # scribe_v2_realtime is the only streaming Scribe model, and streaming is
    # what lets turn detection trust the STT's end of speech, as with Sarvam;
    # the batch models would leave the session with no end-of-turn signal.
    #
    # Language is pinned to Hindi. Auto-detect breaks on a live call: the
    # stream starts with the greeting's silence, detection settles on the
    # wrong language (Cyrillic, Chinese) and the commit comes back empty, so
    # the agent never hears the caller. Pinned "hi" still transcribes English
    # as English and Hinglish as Hinglish (checked with all three). Adding
    # secondary_languages=["en"] made commits empty again, so it's left off.
    # Blank or "unknown" therefore mean "hi" here.
    language = cfg.elevenlabs_stt_language
    if language in (None, "unknown"):
        language = "hi"
    # server_vad switches ElevenLabs from manual commits to committing on
    # silence. Without it, a transcript is only finalised when the stream is
    # flushed, which LiveKit never does on a live call: the agent greeted
    # and then never heard a word. Empty = ElevenLabs' own VAD defaults.
    return elevenlabs.STT(
        model=cfg.elevenlabs_stt_model or "scribe_v2_realtime",
        server_vad={},
        language_code=language,
        sample_rate=cfg.stt_sample_rate,
        api_key=require_key(cfg.elevenlabs_api_key, "ELEVENLABS_API_KEY"),
    )


# Allowed vendors are Sarvam (production) and ElevenLabs. Don't add others.
BUILDERS: dict[str, Callable[[Settings], stt.STT]] = {
    "sarvam": _sarvam,
    "elevenlabs": _elevenlabs,
}


def build_stt(cfg: Settings) -> stt.STT:
    try:
        builder = BUILDERS[cfg.stt_provider]
    except KeyError:
        raise ValueError(
            f"unknown STT provider {cfg.stt_provider!r}; "
            f"available: {sorted(BUILDERS)}"
        ) from None
    return builder(cfg)
