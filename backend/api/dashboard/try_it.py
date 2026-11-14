"""Admin > Try: an admin tries any clinic's receptionist without being its
staff. A typed chat (clinic_agent/chats.py: the brain only, built by the
same code as a call, no worker and no LiveKit minutes) and the erasing of
what a try left behind.

A chat is a real test call: it books for real in that clinic's diary, is
marked `test`, and is erased with everything it changed. While it runs the
admin reads their own conversation as the record grows, tools included; the
saved transcript afterwards opens like any other (with a logged reason).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from api.dashboard import convert, schemas
from api.dashboard.access import admin, staff_errors
from api.dashboard.admin import dropped_before
from clinic_agent import booking
from clinic_agent.call_setup import ClinicPaused, LineOff
from clinic_agent.chats import Chat, Chats, NoSuchChat, NotNow, TooManyChats
from clinic_agent.store import repo
from clinic_agent.store.models import utc_now

logger = logging.getLogger("clinic-agent.api")
router = APIRouter(prefix="/api/admin", dependencies=[Depends(admin)])

GONE = "This chat is gone: it ended a while ago, or the server restarted. Start a new one."


def _chats(request: Request) -> Chats:
    return request.app.state.chats


def _find(request: Request, chat_id: str) -> Chat:
    try:
        return _chats(request).get(chat_id)
    except NoSuchChat:
        raise HTTPException(404, GONE) from None


def _state(chat: Chat, after: int = 0) -> schemas.TryChat:
    lines = list(chat.lines)  # the record grows while we read it
    return schemas.TryChat(
        id=chat.id, clinic_id=chat.clinic_id, call_id=chat.call_id,
        status="ended" if chat.ended else "replying" if chat.replying else "waiting",
        end_reason=chat.end_reason, lines=convert.transcript(lines[after:]), next=len(lines),
    )


@router.post("/clinics/{clinic_id}/try/chat", response_model=schemas.TryChat)
async def start_chat(clinic_id: int, request: Request):
    """Start a typed chat with this clinic's receptionist. She greets first."""
    try:
        chat = await _chats(request).start(clinic_id)
    except repo.NotFound:
        raise HTTPException(404, "No such clinic.") from None
    except ClinicPaused:
        raise HTTPException(409, "This clinic is paused, so its receptionist answers nobody. Resume it first.") from None
    except LineOff as err:
        raise HTTPException(409, f"The receptionist's brain can't be reached with the current settings: {err}") from None
    except TooManyChats as err:
        raise HTTPException(409, str(err)) from None
    logger.info("admin chat %s started for clinic %s (call %s)", chat.id, clinic_id, chat.call_id)
    return _state(chat)


@router.get("/try/chats/{chat_id}", response_model=schemas.TryChat)
def chat_state(chat_id: str, request: Request, after: int = 0):
    """The chat now: whether she is answering, and every line from `after`
    on (the page asks again while she answers, so tools show as they run)."""
    return _state(_find(request, chat_id), max(after, 0))


@router.post("/try/chats/{chat_id}/messages", response_model=schemas.TryChat, status_code=202)
def say(chat_id: str, body: schemas.TryChatMessage, request: Request, after: int = 0):
    """Type one caller turn. Answers at once; her reply arrives in the chat's state."""
    chat = _find(request, chat_id)
    try:
        chat.send(body.text.strip())
    except NotNow as err:
        raise HTTPException(409, str(err)) from None
    return _state(chat, max(after, 0))


@router.delete("/try/chats/{chat_id}", response_model=schemas.TryChat)
async def end_chat(chat_id: str, request: Request, after: int = 0):
    """Hang up, as a caller would. Its record is written before this answers."""
    chat = _find(request, chat_id)
    await chat.end("caller_left")
    return _state(chat, max(after, 0))


@router.delete("/calls/{call_id}", status_code=204)
def erase_test_call(call_id: int, request: Request):
    """Erase a finished test call (a typed chat, or anyone's test call) with
    every booking, cancellation and move it made. Patients' calls can't be."""
    chats = _chats(request)
    with staff_errors(), request.app.state.sessions() as s:
        call = repo.get_call(s, call_id)
        if not call.test:
            raise ValueError("Only test calls can be erased. Patients' calls are kept.")
        if repo.in_livekit(call.room):
            going = convert.call_status(call, dropped_before(request, utc_now())) == "live"
        else:  # a chat lives here: one this server no longer holds (a restart) is over, its record left open
            going = any(c.call_id == call_id and not c.ended for c in chats.all())
        if going:
            raise HTTPException(409, "This test call is still going. Erase it once it has ended.")
        booking.erase_test_call(s, call.clinic_id, call.id)
    chats.forget_call(call_id)
    logger.info("admin erased test call %s", call_id)
