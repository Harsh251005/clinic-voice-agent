"""The voices an admin may pick for a clinic, as pick-lists for the dashboard
(Harsh, 2026-11-12: nobody should have to type "bulbul:v3" and "suhani").

Read from the Sarvam plugin's own tables, so a plugin upgrade brings its new
voices and nothing here is a second list to keep in step.

Women's voices only: the receptionist is always a woman (her rules and fixed
lines say so, in feminine Hindi). bulbul:v3 marks its female speakers.
bulbul:v4-flash marks none, so of its Hindi voices only those whose first
name v3 lists as female are offered; the rest wait until someone has
confirmed them, rather than being guessed from the name.
"""

from __future__ import annotations

from dataclasses import dataclass

from livekit.plugins.sarvam.tts import MODEL_SPEAKER_COMPATIBILITY, _param_bounds

from clinic_agent.providers import defaults

LANGUAGE_TAG = "hi"  # the one line: v4-flash names carry their language (ritu_hi_medical)


@dataclass(frozen=True)
class Speaker:
    name: str  # as Sarvam takes it
    label: str  # as the dashboard shows it


@dataclass(frozen=True)
class VoiceModel:
    name: str
    speakers: tuple[Speaker, ...]
    default_speaker: str  # picked when the admin switches to this model
    pitch: bool  # the model applies a pitch setting


def _first_name(speaker: str) -> str:
    return speaker.split("_", 1)[0]


def _label(speaker: str) -> str:
    """suhani -> Suhani; ritu_hi_customer_warm -> Ritu, customer warm."""
    name, _, rest = speaker.partition("_")
    style = rest.split("_", 1)[1].replace("_", " ") if "_" in rest else ""
    return f"{name.capitalize()}, {style}" if style else name.capitalize()


def _women(model: str) -> list[str]:
    table = MODEL_SPEAKER_COMPATIBILITY[model]
    if "female" in table:
        return list(table["female"])
    known = {s for t in MODEL_SPEAKER_COMPATIBILITY.values() for s in t.get("female", ())}
    return [s for s in table["all"] if f"_{LANGUAGE_TAG}_" in s and _first_name(s) in known]


def catalogue() -> tuple[VoiceModel, ...]:
    """Every voice model with at least one voice to offer, the default first."""
    models = []
    for name in sorted(MODEL_SPEAKER_COMPATIBILITY, key=lambda m: (m != defaults.SARVAM_TTS_MODEL, m)):
        women = sorted(_women(name), key=_label)
        if not women:
            continue
        usual = defaults.SARVAM_TTS_SPEAKER
        default = usual if usual in women else next(
            (s for s in women if _first_name(s) == usual), women[0])
        models.append(VoiceModel(
            name=name, speakers=tuple(Speaker(s, _label(s)) for s in women),
            default_speaker=default, pitch=_param_bounds(name, "pitch") is not None,
        ))
    return tuple(models)


def check(model: str, speaker: str) -> None:
    """ValueError, worded for the admin, unless `speaker` is one of `model`'s
    offered voices. Blank means the default, as in a call."""
    model = model.strip() or defaults.SARVAM_TTS_MODEL
    speaker = speaker.strip() or defaults.SARVAM_TTS_SPEAKER
    found = next((m for m in catalogue() if m.name == model), None)
    if found is None:
        raise ValueError(f"{model} is not a voice model on the list. Pick one from the list.")
    if speaker not in {s.name for s in found.speakers}:
        raise ValueError(f"{speaker} is not one of {model}'s voices on the list. Pick a voice from the list.")
