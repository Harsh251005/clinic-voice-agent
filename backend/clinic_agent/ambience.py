"""Sound of a real front desk: a quiet office in the background for the whole
call, and keyboard typing while the receptionist is thinking (an LLM reply
or a booking lookup), so the caller never sits in dead air.

LiveKit's own clips (livekit.agents resources): local files, no vendor and
no credits. Published as a second audio track mixed in the caller's ear;
the caller's microphone (and so the STT) never hears it. Not in console,
which has no room. BACKGROUND_AUDIO=off turns it off.
"""

from __future__ import annotations

from livekit.agents import AudioConfig, BackgroundAudioPlayer, BuiltinAudioClip

# Quiet on purpose: a clinic, not a call centre. Tuned by ear, not by meter.
AMBIENT_VOLUME = 0.25
TYPING_VOLUME = 0.5


def front_desk() -> BackgroundAudioPlayer:
    return BackgroundAudioPlayer(
        ambient_sound=AudioConfig(BuiltinAudioClip.OFFICE_AMBIENCE, volume=AMBIENT_VOLUME),
        thinking_sound=[
            AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING, volume=TYPING_VOLUME, probability=0.6),
            AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING2, volume=TYPING_VOLUME, probability=0.4),
        ],
    )
