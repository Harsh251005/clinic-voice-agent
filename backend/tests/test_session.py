import pytest

from clinic_agent.config import load_settings
from clinic_agent.session import build_session


async def test_turn_detection_trusts_stt(env):
    env.setenv("MIN_ENDPOINTING_DELAY", "0.3")
    session = build_session(load_settings())
    opts = session.options
    assert opts.turn_handling["turn_detection"] == "stt"
    assert opts.turn_handling["endpointing"]["min_delay"] == 0.3


@pytest.mark.xfail(
    strict=True,
    reason="LiveKit adds a local Silero VAD unless vad=None is passed; "
    "CLAUDE.md claims there is none. Pending a decision.",
)
async def test_no_local_vad(env):
    assert build_session(load_settings()).vad is None
