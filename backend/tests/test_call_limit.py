"""At the time limit the receptionist says goodbye, then the call is closed."""

import asyncio
from types import SimpleNamespace

from clinic_agent.call_limit import GOODBYE, end_after


class FakeSession:
    def __init__(self):
        self.replies = []

    def generate_reply(self, **kwargs):
        self.replies.append(kwargs)
        done = asyncio.get_running_loop().create_future()
        done.set_result(None)  # the goodbye "plays out" at once
        return done


class FakeCall:
    def __init__(self, delete_fails=False):
        self.room = SimpleNamespace(name="call-test")
        self.events = []
        self._delete_fails = delete_fails

    async def delete_room(self):
        if self._delete_fails:
            raise RuntimeError("no room API in console")
        self.events.append("room deleted")

    def shutdown(self, reason=""):
        self.events.append(f"shutdown: {reason}")


async def test_goodbye_then_the_room_is_closed():
    session, call = FakeSession(), FakeCall()
    await end_after(session, call, 0)
    assert session.replies == [{"instructions": GOODBYE, "allow_interruptions": False}]
    assert call.events == ["room deleted", "shutdown: call time limit"]


async def test_the_call_ends_even_if_the_room_cannot_be_deleted():
    call = FakeCall(delete_fails=True)
    await end_after(FakeSession(), call, 0)
    assert call.events == ["shutdown: call time limit"]


async def test_a_call_that_ends_first_is_left_alone():
    session, call = FakeSession(), FakeCall()
    task = asyncio.create_task(end_after(session, call, 60))
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert session.replies == [] and call.events == []
