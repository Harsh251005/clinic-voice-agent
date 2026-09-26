"""Every call names its clinic; a call that doesn't is refused, never guessed."""

from types import SimpleNamespace

import pytest

from clinic_agent.dispatch import NoClinic, clinic_id_from, metadata_for


def test_metadata_round_trip():
    assert clinic_id_from(metadata_for(7)) == 7


def test_metadata_wins_over_the_console_fallback():
    assert clinic_id_from(metadata_for(7), fallback=1) == 7


def test_empty_metadata_uses_the_console_fallback():
    assert clinic_id_from("", fallback=1) == 1


def test_empty_metadata_without_fallback_is_refused():
    with pytest.raises(NoClinic, match="not dispatched with a clinic"):
        clinic_id_from("")


@pytest.mark.parametrize("metadata", ["not json", "[]", '{"clinic": 1}', '{"clinic_id": "1"}', '{"clinic_id": true}'])
def test_malformed_metadata_is_refused_even_with_a_fallback(metadata):
    with pytest.raises(NoClinic):
        clinic_id_from(metadata, fallback=1)


class _Ctx:
    def __init__(self, metadata):
        self.job = SimpleNamespace(metadata=metadata)
        self.room = SimpleNamespace(name="call-test")
        self.shutdown_reason = None

    def shutdown(self, reason=""):
        self.shutdown_reason = reason


@pytest.mark.parametrize("metadata", ["", metadata_for(999)])
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
    assert ctx.shutdown_reason.startswith("no clinic")
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

    ctx = _Ctx(metadata_for(clinic_id))
    await main.entrypoint(ctx)
    assert ctx.shutdown_reason == "clinic paused" and built == []
