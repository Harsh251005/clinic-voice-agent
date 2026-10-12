"""Every call names its clinic and language; a call that doesn't is refused, never guessed."""

from types import SimpleNamespace

import pytest

from clinic_agent.dispatch import LANGUAGES, BadDispatch, CallFor, call_from, metadata_for


@pytest.mark.parametrize("language", LANGUAGES)
def test_metadata_round_trip(language):
    assert call_from(metadata_for(7, language)) == CallFor(7, language)


def test_both_languages_exist():
    assert set(LANGUAGES) == {"en", "hi"}


def test_metadata_wins_over_the_console_fallback():
    assert call_from(metadata_for(7, "en"), fallback=CallFor(1, "hi")) == CallFor(7, "en")


def test_empty_metadata_uses_the_console_fallback():
    assert call_from("", fallback=CallFor(1, "en")) == CallFor(1, "en")


def test_empty_metadata_without_fallback_is_refused():
    with pytest.raises(BadDispatch, match="not dispatched with a clinic"):
        call_from("")


@pytest.mark.parametrize("metadata", [
    "not json", "[]", '{"clinic": 1}',
    '{"clinic_id": "1", "language": "hi"}', '{"clinic_id": true, "language": "hi"}',
    '{"clinic_id": 1}',  # a pass from before calls had a language
    '{"clinic_id": 1, "language": "ta"}', '{"clinic_id": 1, "language": "HI"}', '{"clinic_id": 1, "language": null}',
])
def test_malformed_metadata_is_refused_even_with_a_fallback(metadata):
    with pytest.raises(BadDispatch):
        call_from(metadata, fallback=CallFor(1, "hi"))


def test_a_pass_cannot_be_written_for_an_unknown_language():
    with pytest.raises(BadDispatch):
        metadata_for(1, "ta")  # type: ignore[arg-type]


class _Ctx:
    def __init__(self, metadata):
        self.job = SimpleNamespace(metadata=metadata)
        self.room = SimpleNamespace(name="call-test")
        self.shutdown_reason = None

    def shutdown(self, reason=""):
        self.shutdown_reason = reason


@pytest.mark.parametrize("metadata", ["", metadata_for(999, "hi")])
async def test_entrypoint_refuses_a_call_without_a_known_clinic(env, tmp_path, monkeypatch, metadata):
    import main
    from clinic_agent.store import migrations
    from clinic_agent.store.db import make_engine

    url = f"sqlite:///{tmp_path}/calls.db"
    migrations.upgrade(make_engine(url))
    env.setenv("DATABASE_URL", url)
    built = []
    monkeypatch.setattr(main, "build_session", lambda *a, **k: built.append(1))

    ctx = _Ctx(metadata)
    await main.entrypoint(ctx)
    assert ctx.shutdown_reason.startswith("bad dispatch")
    assert built == []  # no session, so nothing speaks for a clinic it isn't


async def test_entrypoint_refuses_a_paused_clinic(env, tmp_path, monkeypatch):
    import main
    from clinic_agent.store import migrations, repo
    from clinic_agent.store.db import make_engine, session_factory
    from seeds.demo_clinic import seed_demo

    url = f"sqlite:///{tmp_path}/calls.db"
    engine = make_engine(url)
    migrations.upgrade(engine)
    with session_factory(engine)() as s:
        clinic_id = seed_demo(s)
        repo.set_clinic_active(s, clinic_id, False)
    env.setenv("DATABASE_URL", url)
    built = []
    monkeypatch.setattr(main, "build_session", lambda *a, **k: built.append(1))

    ctx = _Ctx(metadata_for(clinic_id, "hi"))
    await main.entrypoint(ctx)
    assert ctx.shutdown_reason == "clinic paused" and built == []


@pytest.mark.parametrize("language", [None, "ta"])
async def test_entrypoint_refuses_a_real_clinics_call_without_a_known_language(env, tmp_path, monkeypatch, language):
    import json

    import main
    from clinic_agent.store import migrations
    from clinic_agent.store.db import make_engine, session_factory
    from seeds.demo_clinic import seed_demo

    url = f"sqlite:///{tmp_path}/calls.db"
    engine = make_engine(url)
    migrations.upgrade(engine)
    with session_factory(engine)() as s:
        clinic_id = seed_demo(s)
    env.setenv("DATABASE_URL", url)
    built = []
    monkeypatch.setattr(main, "build_session", lambda *a, **k: built.append(1))

    fields = {"clinic_id": clinic_id} | ({"language": language} if language else {})
    ctx = _Ctx(json.dumps(fields))
    await main.entrypoint(ctx)
    assert ctx.shutdown_reason.startswith("bad dispatch") and built == []


def test_the_worker_registers_under_the_name_call_passes_dispatch(monkeypatch):
    import main
    from clinic_agent.dispatch import AGENT_NAME

    monkeypatch.setenv("LIVEKIT_AGENT_NAME", "someone-else")  # overwritten: passes only dispatch AGENT_NAME
    monkeypatch.delenv("LIVEKIT_AGENT_NAME_OVERRIDE", raising=False)
    server = main.make_server()
    assert server._agent_name == AGENT_NAME
    assert server._agent_name_source == "env"  # not "code": LiveKit's deprecated path
