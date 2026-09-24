"""Text-to-speech builders.

Every builder returns a `livekit.agents.tts.TTS`.
"""

from __future__ import annotations

from collections.abc import Callable

from livekit.agents import tts
from livekit.plugins import elevenlabs, sarvam

from clinic_agent.config import Settings, require_key
from clinic_agent.providers.sentences import MAX_PIECE, SentenceTokenizer


def _sarvam(cfg: Settings) -> tts.TTS:
    # The plugin defaults to mp3, which costs a decode on every chunk;
    # linear16 hands LiveKit raw PCM instead. Speaker must be a bulbul:v3 voice.
    voice = sarvam.TTS(
        model=cfg.sarvam_tts_model or "bulbul:v3",
        speaker=cfg.sarvam_tts_speaker or "suhani",
        target_language_code=cfg.sarvam_tts_language or "en-IN",
        speech_sample_rate=cfg.sarvam_tts_sample_rate or 24000,
        output_audio_codec=cfg.sarvam_tts_codec or "linear16",
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


def _elevenlabs(cfg: Settings) -> tts.TTS:
    # eleven_v3_conversational is ElevenLabs' most expressive model built for
    # live dialogue; LiveKit streams it over the text-to-dialogue websocket.
    # Fallback if the plan rejects it: ELEVENLABS_TTS_MODEL=eleven_multilingual_v2
    # (most natural of the v2 models) or eleven_flash_v2_5 (fastest).
    # How real it sounds depends as much on ELEVENLABS_TTS_VOICE - pick a Hindi voice
    # ID from the Voice Library - and on the prompt writing Hindi in
    # Devanagari. pcm_24000 is raw PCM, for the same reason as Sarvam's
    # linear16. Language auto-detects, since callers mix Hindi and English.
    options = {"language": cfg.elevenlabs_tts_language} if cfg.elevenlabs_tts_language else {}
    return elevenlabs.TTS(
        model=cfg.elevenlabs_tts_model or "eleven_v3_conversational",
        voice_id=cfg.elevenlabs_tts_voice or elevenlabs.DEFAULT_VOICE_ID,
        encoding=cfg.elevenlabs_tts_codec or "pcm_24000",
        api_key=require_key(cfg.elevenlabs_api_key, "ELEVENLABS_API_KEY"),
        **options,
    )


# Allowed vendors are Sarvam (production) and ElevenLabs. Don't add others.
BUILDERS: dict[str, Callable[[Settings], tts.TTS]] = {
    "sarvam": _sarvam,
    "elevenlabs": _elevenlabs,
}


def build_tts(cfg: Settings) -> tts.TTS:
    try:
        builder = BUILDERS[cfg.tts_provider]
    except KeyError:
        raise ValueError(
            f"unknown TTS provider {cfg.tts_provider!r}; "
            f"available: {sorted(BUILDERS)}"
        ) from None
    return builder(cfg)
