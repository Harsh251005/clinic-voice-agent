"""Voice & phrases (/api/admin/voice): the receptionist's fixed lines and
their recordings. Admins only; no patient data (clinic names only).

The admin writes English; the Hindi that is spoken is suggested from it
(providers/hindi.py) and can be edited before saving. Nothing records itself:
a phrase is recorded only when an admin asks, one take at a time, in the
voice calls use now (clinic_agent/voice_clips.py). Until then, and whenever a
recording is missing, calls say the phrase live.
"""

from __future__ import annotations

import asyncio
import io
import logging
import wave
from dataclasses import replace
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from api.dashboard import convert, costs, schemas
from api.dashboard.access import admin, staff_errors
from clinic_agent import incidents, voice_clips
from clinic_agent.call_settings import merge
from clinic_agent.config import ConfigError, Settings
from clinic_agent.lines import line_for
from clinic_agent.providers import build_tts, hindi, identity
from clinic_agent.store import repo
from clinic_agent.store.models import utc_now

logger = logging.getLogger("clinic-agent.api")
router = APIRouter(prefix="/api/admin/voice", dependencies=[Depends(admin)])

LANGUAGE = "hi"  # the one line (docs/decisions.md #13)


_KEEP = object()  # "this clinic's own" for a speaker or pitch not being tried out


def _settings(request: Request):
    with request.app.state.sessions() as s:
        return repo.system_settings(s), repo.list_clinics(s)


def clinic_voice(base: Settings, system, clinic, pace: float | None = None, speaker=_KEEP, pitch=_KEEP):
    """(TTS, its identity, why there is none) for `clinic`'s calls: the shared
    voice model with this clinic's speaker and pitch (call_settings.py). With
    `pace`, at that speed: how a phrase is recorded (Phrase.pace). `speaker`
    and `pitch` try out other values (the clinic tab's warning before a save)."""
    cfg = merge(base, system, clinic).cfg
    if speaker is not _KEEP:
        cfg = replace(cfg, sarvam_tts_speaker=speaker.strip() or None)
    if pitch is not _KEEP:
        cfg = replace(cfg, sarvam_tts_pitch=pitch)
    if pace is not None:
        cfg = replace(cfg, sarvam_tts_pace=pace)
    try:
        tts = build_tts(cfg, line_for(cfg, LANGUAGE).tts)
        return tts, identity(tts), ""
    except (ConfigError, ValueError, TypeError) as err:
        return None, None, f"No voice to record with: {err}"


def _voices(request: Request, system, clinics) -> tuple[dict[int, dict | None], str]:
    """Each clinic's voice identity (None without a voice), and why there is none."""
    out, problem = {}, ""
    for c in clinics:
        _, voice, why = clinic_voice(request.app.state.cfg, system, c)
        out[c.id] = voice
        problem = problem or why
    return out, problem


def _sound(voice: dict | None):
    """What makes two clinics' voices the same for recording (speed aside: a
    phrase records at its own)."""
    return tuple(sorted((k, v) for k, v in voice.items() if k != "pace")) if voice else None


def _takes(phrase, clinics, own: set[int], voices: dict[int, dict | None]) -> list[tuple[int | None, str, str, list]]:
    """(clinic id, clinic names, spoken words, the clinics it serves) for each
    way calls say `phrase`: the shared greeting once per clinic; any other
    phrase once per voice (Harsh, 2026-11-10: each clinic may have its own)."""
    if phrase.kind == "greeting":
        if phrase.clinic_id is not None:
            clinic = clinics[phrase.clinic_id]
            return [(clinic.id, clinic.name, voice_clips.spoken(phrase.text, clinic), [clinic])]
        return [(c.id, c.name, voice_clips.spoken(phrase.text, c), [c]) for c in clinics.values() if c.id not in own]
    groups: dict = {}
    for c in clinics.values():
        groups.setdefault(_sound(voices.get(c.id)), []).append(c)
    if len(groups) <= 1:
        return [(None, "", phrase.text, list(clinics.values()))]
    return [(served[0].id, ", ".join(c.name for c in served), phrase.text, served) for served in groups.values()]


def _page(s, request: Request, voices: dict[int, dict | None], problem: str) -> schemas.VoicePage:
    clinics = {c.id: c for c in repo.list_clinics(s)}
    phrases = [p for p in repo.list_phrases(s) if p.language == LANGUAGE]
    own = {p.clinic_id for p in phrases if p.clinic_id is not None}
    takes = {p.id: _takes(p, clinics, own, voices) for p in phrases}

    def key(phrase, served, words):
        voice = voices.get(served[0].id) if served else None
        return voice_clips.clip_key(voice_clips.at_pace(voice, phrase.pace), words) if voice else None

    keys = {(p.id, t[0]): key(p, t[3], t[2]) for p in phrases for t in takes[p.id]}
    clips = repo.clip_dates(s, [k for k in keys.values() if k])
    out = []
    for p in phrases:
        listed = []
        for clinic_id, name, words, served in takes[p.id]:
            k = keys.get((p.id, clinic_id))
            clip = clips.get(k or "")
            listed.append(schemas.Take(
                clinic_id=clinic_id, clinic_name=name, spoken=words, key=k,
                recorded_at=convert.utc(clip.recorded_at) if clip else None, duration_s=clip.duration_s if clip else None,
                live_pace=served[0].tts_pace if served else None))
        out.append(schemas.PhraseOut(
            id=p.id, kind=p.kind, language=p.language, slot=p.slot, clinic_id=p.clinic_id,
            clinic_name=clinics[p.clinic_id].name if p.clinic_id else "", source=p.source, text=p.text,
            pace=p.pace, takes=listed))
    first = next((v for v in voices.values() if v), None)
    return schemas.VoicePage(
        voice=schemas.VoiceOut(vendor=first["vendor"], model=first["model"], voice=first["voice"], pace=first["pace"],
                               pitch=first["pitch"], sample_rate=first["sample_rate"]) if first else None,
        voice_problem="" if first else (problem or "No clinics yet."),
        voices_differ=len({_sound(v) for v in voices.values()}) > 1,
        rupees_per_1000_chars=_price(s, first), max_chars=repo.MAX_PHRASE_CHARS,
        pace_min=repo.PACE_RANGE[0], pace_max=repo.PACE_RANGE[1], phrases=out,
        clinics=[schemas.VoiceClinic(id=c.id, name=c.name, spoken_name=voice_clips.spoken_name(c), own_greeting=c.id in own)
                 for c in clinics.values()],
    )


def _price(s, voice: dict | None) -> float | None:
    """What 1,000 characters cost in this voice today (Prices page), or None."""
    if not voice:
        return None
    thousand = SimpleNamespace(provider=voice["vendor"], model=voice["model"], unit="characters", quantity=1000.0, at=utc_now())
    return costs.book(s).priced(thousand).rupees


def page_now(request: Request) -> schemas.VoicePage:
    system, clinics = _settings(request)
    voices, problem = _voices(request, system, clinics)
    with request.app.state.sessions() as s:
        return _page(s, request, voices, problem)


@router.get("", response_model=schemas.VoicePage)
def voice_page(request: Request):
    return page_now(request)


@router.put("/phrases/{phrase_id}", response_model=schemas.VoicePage)
def edit_phrase(phrase_id: int, body: schemas.PhraseIn, request: Request):
    """New words for a phrase. Its old recording stays (for going back) but no
    longer plays: the phrase is said live until it is recorded again."""
    with staff_errors(), request.app.state.sessions() as s:
        repo.set_phrase_text(s, phrase_id, body.text, source=body.source)
    return page_now(request)


@router.put("/phrases/{phrase_id}/pace", response_model=schemas.VoicePage)
def phrase_pace(phrase_id: int, body: schemas.PaceIn, request: Request):
    """How fast this phrase's recording is spoken. Takes at the old speed stay
    but no longer play: the phrase is said live until recorded again."""
    with staff_errors(), request.app.state.sessions() as s:
        repo.set_phrase_pace(s, phrase_id, body.pace)
    return page_now(request)


@router.put("/clinics/{clinic_id}/greeting", response_model=schemas.VoicePage)
def own_greeting(clinic_id: int, body: schemas.PhraseIn, request: Request):
    """This clinic's own greeting, in place of the shared one."""
    with staff_errors(), request.app.state.sessions() as s:
        repo.set_greeting_override(s, clinic_id, LANGUAGE, body.text, source=body.source)
    return page_now(request)


@router.delete("/clinics/{clinic_id}/greeting", response_model=schemas.VoicePage)
def shared_greeting(clinic_id: int, request: Request):
    """Back to the shared greeting for this clinic."""
    with staff_errors(), request.app.state.sessions() as s:
        repo.get_clinic(s, clinic_id)
        repo.clear_greeting_override(s, clinic_id, LANGUAGE)
    return page_now(request)


@router.post("/translate", response_model=schemas.Translated)
def translate(body: schemas.TranslateIn, request: Request):
    """The Hindi for the admin's English, for them to read and edit before
    saving. Its tokens are counted on the Costs page (Other)."""
    known: dict[str, str] = {}
    if body.clinic_id is not None:
        with staff_errors(), request.app.state.sessions() as s:
            clinic = repo.get_clinic(s, body.clinic_id)
            known = {n: h for n, h in [(clinic.name, clinic.name_hi), *((d.name, d.name_hi) for d in clinic.doctors)] if h}

    def used(model: str, tokens_in: int, cached: int, tokens_out: int) -> None:
        items = [{"provider": "openai", "model": model, "unit": unit, "quantity": float(n)}
                 for unit, n in (("tokens_in", tokens_in - cached), ("tokens_cached", cached), ("tokens_out", tokens_out)) if n > 0]
        with request.app.state.sessions() as s:
            repo.add_usage(s, None, utc_now(), "voice_phrase", "other", items)

    try:
        text = hindi.translate_phrase(request.app.state.cfg, body.english, known, on_usage=used)
    except (ConfigError, hindi.NoSuggestion) as err:
        logger.warning("no Hindi for a phrase: %s", err)
        with request.app.state.sessions() as s:
            incidents.report(s, "phrase_translation_failing", utc_now(), detail=f"{type(err).__name__}: {err}"[:200])
        raise HTTPException(503, "No Hindi just now. Type it yourself, or try again.") from None
    with request.app.state.sessions() as s:
        incidents.clear(s, "phrase_translation_failing", utc_now())
    return schemas.Translated(text=text)


@router.post("/record", response_model=schemas.RecordOut)
async def record(body: schemas.RecordIn, request: Request):
    """Record the asked takes, each in the voice of the clinics it serves and
    at its phrase's own speed, one after another (a take already recorded is
    recorded again: a new take). Stops at the first failure: a vendor out of
    credits would fail them all."""
    system, clinics = await asyncio.to_thread(_settings, request)
    voices, problem = _voices(request, system, clinics)
    if not any(voices.values()):
        raise HTTPException(422, problem or "No clinics to record for.")
    sessions = request.app.state.sessions
    by_id = {c.id: c for c in clinics}

    def current() -> schemas.VoicePage:
        with sessions() as s:
            return _page(s, request, voices, problem)

    page = await asyncio.to_thread(current)
    by_phrase = {p.id: p for p in page.phrases}
    wanted: dict[str, tuple[str, float, object]] = {}  # key -> (words, speed, a clinic it serves), each once
    for ref in body.takes:
        phrase = by_phrase.get(ref.phrase_id)
        take = next((t for t in phrase.takes if t.clinic_id == ref.clinic_id), None) if phrase else None
        if take is None or take.key is None:
            raise HTTPException(404, "That phrase (or that clinic's greeting) is not there any more. Reload the page.")
        clinic = by_id.get(take.clinic_id) if take.clinic_id is not None else (clinics[0] if clinics else None)
        wanted[take.key] = (take.spoken, phrase.pace, clinic)
    done, failed = 0, ""
    for words, pace, clinic in wanted.values():
        paced, paced_identity, why = clinic_voice(request.app.state.cfg, system, clinic, pace)
        if paced is None:
            failed = why
            break
        try:
            await voice_clips.record(sessions, paced, paced_identity, words)
            done += 1
        except voice_clips.RecordFailed as err:
            failed = str(err)
            break
    return schemas.RecordOut(recorded=done, failed=failed, page=await asyncio.to_thread(current))


@router.get("/impact", response_model=schemas.VoiceImpact)
def impact(request: Request, clinic_id: int, speaker: str = "", pitch: float | None = None):
    """Before a clinic's voice is changed (its Receptionist tab): how many of
    its lines are recorded in its voice now, and how many would be in the one
    tried out. The others are said live until recorded."""
    system, clinics = _settings(request)
    clinic = next((c for c in clinics if c.id == clinic_id), None)
    if clinic is None:
        raise HTTPException(404, "No such clinic.")
    _, now, _ = clinic_voice(request.app.state.cfg, system, clinic)
    _, after, _ = clinic_voice(request.app.state.cfg, system, clinic, speaker=speaker, pitch=pitch)
    with request.app.state.sessions() as s:
        lines = [(p, voice_clips.spoken(p.text, clinic)) for p in repo.phrases_for_call(s, clinic.id, LANGUAGE)]

        def recorded(voice) -> int:
            if not voice:
                return 0
            keys = [voice_clips.clip_key(voice_clips.at_pace(voice, p.pace), words) for p, words in lines]
            return len(repo.clip_dates(s, keys))

        return schemas.VoiceImpact(lines=len(lines), recorded_now=recorded(now), recorded_after=recorded(after))


@router.get("/clips/{key}.wav")
def play(key: str, request: Request):
    """A recording as WAV, for the page's Play button."""
    with request.app.state.sessions() as s:
        clip = repo.clips_by_key(s, [key]).get(key)
        if clip is None:
            raise HTTPException(404, "Not recorded.")
        out = io.BytesIO()
        with wave.open(out, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(clip.sample_rate)
            w.writeframes(clip.pcm)
    return Response(out.getvalue(), media_type="audio/wav", headers={"Cache-Control": "private, max-age=3600"})


def voice_of(base: Settings):
    """Each clinic's voice identity for the problems check (incidents.sync):
    recordings that no longer match it."""
    def of(system, clinic):
        return clinic_voice(base, system, clinic)[1]
    return of
