"""Admin > Try over the API: admins chat with any clinic's receptionist
without being its staff, read the conversation with its tools as it grows,
and erase what the try left behind. Nobody else can."""

import time

import pytest
from livekit.agents import AgentSession

from clinic_agent import call_setup
from clinic_agent.config import load_settings
from clinic_agent.store import repo
from clinic_agent.store.db import sessions_for
from tests.fake_llm import FakeLLM, Reply
from tests.test_booking_readback import BOOK, CHECK, DAY
from tests.test_dashboard_api import client_as, world, world_calls  # noqa: F401

ADMIN = "boss@clinicdesk.in"  # an admin, and no clinic's staff


@pytest.fixture
def brain(monkeypatch):
    def script(*replies):
        monkeypatch.setattr(call_setup, "build_session",
                            lambda cfg, line, text_only=False: AgentSession(llm=FakeLLM(list(replies))))
    return script


def until(client, chat_id, status, after=0):
    for _ in range(400):
        state = client.get(f"/api/admin/try/chats/{chat_id}", params={"after": after}).json()
        if state["status"] == status:
            return state
        time.sleep(0.01)
    raise AssertionError(f"the chat never got to {status}: {state}")


def test_an_admin_chats_books_reads_the_tools_and_erases_it(world, brain):  # noqa: F811
    brain(Reply(calls=[CHECK]), Reply("सही है?"), Reply(calls=[BOOK]), Reply("बुक हो गया।"))
    with client_as(ADMIN, admin=True) as client:
        chat = client.post(f"/api/admin/clinics/{world['demo']}/try/chat").json()
        assert chat["status"] == "waiting" and [line["role"] for line in chat["lines"]] == ["agent"]

        said = client.post(f"/api/admin/try/chats/{chat['id']}/messages", json={"text": "पाँच बजे, रवि"})
        assert said.status_code == 202
        seen = until(client, chat["id"], "waiting", after=chat["next"])
        roles = [line["role"] for line in seen["lines"]]
        assert roles == ["caller", "tool", "agent"]  # only what is new, in order
        tool = seen["lines"][1]
        assert tool["tool"] == "check_booking" and tool["ok"] and "Asha" in tool["args"] and tool["text"]

        client.post(f"/api/admin/try/chats/{chat['id']}/messages", json={"text": "हाँ"})
        until(client, chat["id"], "waiting")
        ended = client.delete(f"/api/admin/try/chats/{chat['id']}").json()
        assert (ended["status"], ended["end_reason"]) == ("ended", "caller_left")
        assert client.post(f"/api/admin/try/chats/{chat['id']}/messages", json={"text": "हेलो"}).status_code == 409

        trace = client.get(f"/api/admin/calls/{chat['call_id']}").json()
        assert (trace["test"], trace["outcome"], trace["status"]) == (True, "booked", "ended")
        with sessions_for(load_settings().database_url)() as s:
            assert len(repo.appointments_on(s, world["demo"], DAY)) == 1

        assert client.delete(f"/api/admin/calls/{chat['call_id']}").status_code == 204
        with sessions_for(load_settings().database_url)() as s:
            assert repo.appointments_on(s, world["demo"], DAY) == []
        assert client.get(f"/api/admin/calls/{chat['call_id']}").status_code == 404
        assert client.get(f"/api/admin/try/chats/{chat['id']}").status_code == 404  # nothing left to read


def test_a_chat_still_going_cant_be_erased_but_one_lost_to_a_restart_can(world, brain):  # noqa: F811
    brain()
    with client_as(ADMIN, admin=True) as client:
        chat = client.post(f"/api/admin/clinics/{world['demo']}/try/chat").json()
        assert client.delete(f"/api/admin/calls/{chat['call_id']}").status_code == 409
        client.app.state.chats._chats.clear()  # the server restarted: the chat is gone, its record left open
        assert client.delete(f"/api/admin/calls/{chat['call_id']}").status_code == 204


def test_only_test_calls_are_erased_by_an_admin(world_calls):  # noqa: F811
    with client_as(ADMIN, admin=True) as client:
        refused = client.delete(f"/api/admin/calls/{world_calls['demo_call']}")
        assert refused.status_code == 422 and "Patients' calls are kept" in refused.json()["detail"]


def test_a_paused_or_unknown_clinic_gets_no_chat_and_blank_text_is_refused(world, brain):  # noqa: F811
    brain()
    with client_as(ADMIN, admin=True) as client:
        assert client.post("/api/admin/clinics/999/try/chat").status_code == 404
        chat = client.post(f"/api/admin/clinics/{world['demo']}/try/chat").json()
        assert client.post(f"/api/admin/try/chats/{chat['id']}/messages", json={"text": "   "}).status_code == 422
        assert client.get("/api/admin/try/chats/nope").status_code == 404
        client.put(f"/api/admin/clinics/{world['cure']}/active", json={"active": False})
        paused = client.post(f"/api/admin/clinics/{world['cure']}/try/chat")
        assert paused.status_code == 409 and "paused" in paused.json()["detail"]


@pytest.mark.parametrize(("method", "path"), [
    ("post", "/api/admin/clinics/{demo}/try/chat"),
    ("get", "/api/admin/try/chats/x"),
    ("post", "/api/admin/try/chats/x/messages"),
    ("delete", "/api/admin/try/chats/x"),
    ("delete", "/api/admin/calls/{demo_call}"),
])
def test_staff_who_are_not_admins_get_none_of_it(world_calls, method, path):  # noqa: F811
    client = client_as("doctor@demo.in")
    response = getattr(client, method)(path.format(**world_calls))
    assert response.status_code == 403
