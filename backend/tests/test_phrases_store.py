"""The fixed phrases and their recordings (store layer)."""

import pytest
from sqlalchemy.exc import IntegrityError

from clinic_agent.store import repo
from clinic_agent.store.models import PHRASE_KINDS, Phrase


def _of(phrases, kind, language="hi"):
    return [p for p in phrases if p.kind == kind and p.language == language]


def test_every_kind_is_seeded_in_hindi_only(db):
    s, _ = db
    rows = repo.list_phrases(s)
    assert {p.kind for p in rows} == set(PHRASE_KINDS)
    assert [p.slot for p in _of(rows, "filler")] == [1, 2, 3]  # the set of three
    assert {p.language for p in rows} == {"hi"}  # one line (docs/decisions.md #13)


def test_the_greeting_is_a_template_for_the_clinic_name(db):
    s, _ = db
    greeting, = _of(repo.list_phrases(s), "greeting")
    assert "{clinic}" in greeting.text and "ऑटोमेटेड असिस्टेंट" in greeting.text


def test_a_clinics_own_greeting_replaces_the_global_one_for_that_clinic_only(db):
    s, clinic_id = db
    other = repo.create_clinic(s, name="Second Clinic")
    repo.set_greeting_override(s, clinic_id, "hi", "नमस्ते जी, {clinic} में स्वागत है। मैं ऑटोमेटेड असिस्टेंट हूँ, बातचीत टेक्स्ट में सेव होती है।")
    mine, = _of(repo.phrases_for_call(s, clinic_id, "hi"), "greeting")
    assert mine.text == "नमस्ते जी, {clinic} में स्वागत है। मैं ऑटोमेटेड असिस्टेंट हूँ, बातचीत टेक्स्ट में सेव होती है।" and mine.clinic_id == clinic_id
    # the fillers and goodbyes stay the global ones
    assert len(_of(repo.phrases_for_call(s, clinic_id, "hi"), "filler")) == 3
    theirs, = _of(repo.phrases_for_call(s, other.id, "hi"), "greeting")
    assert theirs.clinic_id is None  # another clinic still hears the global one
    repo.clear_greeting_override(s, clinic_id, "hi")
    back, = _of(repo.phrases_for_call(s, clinic_id, "hi"), "greeting")
    assert back.clinic_id is None


def test_setting_the_override_again_edits_it_instead_of_adding_a_second(db):
    s, clinic_id = db
    repo.set_greeting_override(s, clinic_id, "hi", "पहला: ऑटोमेटेड, टेक्स्ट")
    repo.set_greeting_override(s, clinic_id, "hi", "दूसरा: ऑटोमेटेड, टेक्स्ट")
    assert [p.text for p in repo.list_phrases(s) if p.clinic_id == clinic_id] == ["दूसरा: ऑटोमेटेड, टेक्स्ट"]


def test_two_phrases_can_not_share_a_place(db):
    s, clinic_id = db
    s.add(Phrase(kind="filler", language="hi", slot=1, source="dup", text="duplicate"))  # a global one exists
    with pytest.raises(IntegrityError):
        s.commit()
    s.rollback()
    s.add(Phrase(kind="greeting", language="hi", slot=0, clinic_id=clinic_id, source="mine", text="mine"))
    s.commit()
    s.add(Phrase(kind="greeting", language="hi", slot=0, clinic_id=clinic_id, source="again", text="mine again"))
    with pytest.raises(IntegrityError):
        s.commit()
    s.rollback()


def test_phrase_text_is_trimmed_and_must_be_sensible(db):
    s, _ = db
    first = _of(repo.list_phrases(s), "filler")[0]
    assert repo.set_phrase_text(s, first.id, "  नमस्ते  ").text == "नमस्ते"
    for bad in ("", "   ", "x" * (repo.MAX_PHRASE_CHARS + 1)):
        with pytest.raises(ValueError):
            repo.set_phrase_text(s, first.id, bad)
    with pytest.raises(repo.NotFound):
        repo.set_phrase_text(s, 99999, "x")


def test_deleting_a_clinic_deletes_its_own_greeting(db):
    s, clinic_id = db
    repo.set_greeting_override(s, clinic_id, "hi", "मेरा: ऑटोमेटेड, टेक्स्ट")
    s.delete(repo.get_clinic(s, clinic_id))
    s.commit()
    assert not [p for p in repo.list_phrases(s) if p.clinic_id is not None]
    assert _of(repo.list_phrases(s), "greeting")  # the global one stays


def _save(s, key="k1", text="नमस्ते", pcm=b"\x01\x02" * 100):
    return repo.save_clip(s, key=key, vendor="sarvam", model="bulbul:v3", voice="suhani", language_code="hi-IN",
                          sample_rate=24000, text=text, pcm=pcm, duration_s=0.5)


def test_a_new_take_replaces_the_old_one_under_the_same_key(db):
    s, _ = db
    _save(s, pcm=b"\x01\x02")
    first = repo.clips_by_key(s, ["k1"])["k1"].recorded_at
    _save(s, pcm=b"\x03\x04\x05\x06")
    clips = repo.clips_by_key(s, ["k1", "missing"])
    assert list(clips) == ["k1"] and clips["k1"].pcm == b"\x03\x04\x05\x06" and clips["k1"].recorded_at >= first
    assert len(repo.list_clips(s)) == 1


def test_the_clip_list_leaves_the_audio_out_and_delete_says_how_many(db):
    s, _ = db
    _save(s, "a")
    _save(s, "b", text="और")
    s.expire_all()
    listed = repo.list_clips(s)
    assert {c.key for c in listed} == {"a", "b"}
    assert all("pcm" not in c.__dict__ for c in listed)  # deferred: not loaded
    assert repo.delete_clips(s, ["a", "nope"]) == 1 and repo.delete_clips(s, []) == 0
    assert [c.key for c in repo.list_clips(s)] == ["b"]


def test_every_hindi_phrase_has_its_english_source(db):
    s, _ = db
    for p in repo.list_phrases(s):
        assert p.source.isascii() and p.source.strip()  # staff only ever write English
        assert p.text != p.source  # what is spoken is the Hindi
    first_hindi = _of(repo.list_phrases(s), "filler")[0]
    repo.set_phrase_text(s, first_hindi.id, "नया हिंदी", source="New English")
    assert (first_hindi.source, first_hindi.text) == ("New English", "नया हिंदी")


def test_a_greeting_can_not_drop_what_every_caller_must_hear(db):
    # Callers must be told the receptionist is automated and the call is kept as text.
    s, clinic_id = db
    greeting, = _of(repo.list_phrases(s), "greeting")
    for bad, why in [
        ("नमस्ते, {clinic} में आपका स्वागत है। बताइए?", "automated assistant"),
        ("नमस्ते, {clinic} में स्वागत है। मैं ऑटोमेटेड असिस्टेंट हूँ।", "saved as text"),
        ("नमस्ते। मैं ऑटोमेटेड असिस्टेंट हूँ, बातचीत टेक्स्ट में सेव होती है।", "{clinic}"),  # the shared one names the clinic
    ]:
        with pytest.raises(ValueError, match=why.replace("{", r"\{").replace("}", r"\}")):
            repo.set_phrase_text(s, greeting.id, bad)
        s.rollback()
    with pytest.raises(ValueError, match="automated assistant"):
        repo.set_greeting_override(s, clinic_id, "hi", "नमस्ते जी।")
    # a clinic's own greeting may name the clinic in its own words
    own = repo.set_greeting_override(s, clinic_id, "hi", "नमस्ते, डेमो क्लिनिक। मैं ऑटोमेटेड असिस्टेंट हूँ, बातचीत टेक्स्ट में सेव होती है।")
    assert own.clinic_id == clinic_id
