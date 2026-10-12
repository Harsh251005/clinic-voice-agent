from livekit.agents import BuiltinAudioClip

from clinic_agent.ambience import AMBIENT_VOLUME, front_desk


async def test_a_quiet_office_all_call_and_typing_while_it_thinks():
    player = front_desk()
    assert player._ambient_sound.source == BuiltinAudioClip.OFFICE_AMBIENCE
    assert player._ambient_sound.volume == AMBIENT_VOLUME <= 0.3  # a clinic, not a call centre
    typing = {c.source for c in player._thinking_sound}
    assert typing == {BuiltinAudioClip.KEYBOARD_TYPING, BuiltinAudioClip.KEYBOARD_TYPING2}
    assert sum(c.probability for c in player._thinking_sound) == 1  # always some typing while it thinks
