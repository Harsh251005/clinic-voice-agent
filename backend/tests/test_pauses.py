"""The longer wait for the caller while they read out a number."""

from types import SimpleNamespace

from clinic_agent.pauses import MAX_WAIT, wait_for_numbers


class _Session:
    def __init__(self):
        self.delays, self.handlers = [], []

    def on(self, event, handler):
        assert event == "conversation_item_added"
        self.handlers.append(handler)

    def update_options(self, *, endpointing_opts):
        self.delays.append(endpointing_opts["min_delay"])

    def say(self, role, text, type="message"):
        for handler in self.handlers:
            handler(SimpleNamespace(item=SimpleNamespace(type=type, role=role, text_content=text)))


def test_the_wait_is_longer_only_from_asking_for_a_number_until_the_caller_has_answered():
    session = _Session()
    wait_for_numbers(session, 0.2, 1.5)
    session.say("assistant", "जी, आपका मोबाइल नंबर बताइए।")
    session.say("user", "89 288 03112")
    session.say("assistant", "Which date would you like?")  # no number asked: nothing changes
    assert session.delays == [1.5, 0.2]


def test_english_and_other_ways_of_asking_count_too():
    session = _Session()
    wait_for_numbers(session, 0.2, 1.5)
    for ask in ("What is your mobile number?", "ज़रा दस अंकों का नम्बर बताइए", "Say the ten digits slowly"):
        session.say("assistant", ask)
    assert session.delays == [1.5, 1.5, 1.5]


def test_only_messages_count_and_a_long_wait_is_capped():
    session = _Session()
    wait_for_numbers(session, 0.2, 10)
    session.say("assistant", "नंबर बताइए", type="function_call")
    assert session.delays == []
    session.say("assistant", "नंबर बताइए")
    assert session.delays == [MAX_WAIT]
