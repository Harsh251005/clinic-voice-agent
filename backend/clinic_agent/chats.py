"""An admin's typed chat with a clinic's receptionist: the brain only.

The same call a patient gets (call_setup.prepare: same rules, clinic facts,
model, tools, booking code and record), with no ears, no voice, no LiveKit
room and no worker. Each chat is a real test call: it books for real, is
marked `test`, and its record is written by the same CallRecorder, so what
the admin reads while chatting is the record itself as it grows (the words,
each tool with what the model sent and what came back, vendor errors).

Chats live in this process's memory (the API server's): a restart ends
them. Their records stay, open, and can be erased like any test call.
A chat ends on end_call, the clinic's longest call, a quiet spell, the
admin's End, or the server stopping.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time

from livekit.agents.utils import http_context

from clinic_agent.call_limit import end_after
from clinic_agent.call_setup import Prepared, prepare
from clinic_agent.config import Settings
from clinic_agent.dispatch import CallFor
from clinic_agent.store import repo

logger = logging.getLogger("clinic-agent")

MAX_CHATS = 3  # going at once: each holds a session; this is one admin's tool, not a service
IDLE_SECONDS = 10 * 60  # nothing typed for this long: the caller is taken to have left
KEEP_ENDED_SECONDS = 10 * 60  # an ended chat stays readable this long, then only its record remains
MAX_MESSAGE = 1000  # characters in one typed turn

_END, _CLOSED = object(), object()


class TooManyChats(Exception):
    """MAX_CHATS are going already."""


class NoSuchChat(LookupError):
    """Never started, forgotten after it ended, or lost to a server restart."""


class NotNow(Exception):
    """A message can't be taken: she is still answering, or the chat has ended."""


class _NoRoom:
    """What call_limit.end_after needs of a job, for a call that has no room."""

    def __init__(self, name: str, session) -> None:
        self.room = self
        self.name = name
        self._session = session

    async def delete_room(self) -> None:
        return None

    def shutdown(self, reason: str = "") -> None:
        self._session.shutdown()


class Chat:
    def __init__(self, chat_id: str, ready: Prepared, language: str) -> None:
        self.id, self.ready, self.language = chat_id, ready, language
        self.clinic_id = ready.clinic.id
        self.replying = True  # the greeting counts: nothing can be typed over it
        self.ended = False
        self.used = time.monotonic()
        self._inbox: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None

    @property
    def call_id(self) -> int | None:
        return self.ready.record.call_id

    @property
    def lines(self) -> list[dict]:
        """The call's transcript so far, as its record holds it."""
        return self.ready.record.transcript

    @property
    def end_reason(self) -> str:
        return self.ready.record.end_reason if self.ended else ""

    async def start(self) -> None:
        """Returns once she has greeted. Raises whatever stopped her."""
        greeted: asyncio.Future = asyncio.get_running_loop().create_future()
        self._task = asyncio.create_task(self._run(greeted))
        await greeted

    def send(self, text: str) -> None:
        if self.ended:
            raise NotNow("This chat has ended. Start a new one.")
        if self.replying:
            raise NotNow("She is still answering. Wait for her reply.")
        self.replying = True
        self.used = time.monotonic()
        self._inbox.put_nowait(text)

    async def end(self, reason: str = "caller_left") -> None:
        """Hang up (the admin's End, a quiet spell, the server stopping) and
        wait for the record to be written."""
        if not self.ended:
            self._inbox.put_nowait((_END, reason))
        if self._task is not None:
            await asyncio.wait({self._task})

    async def _run(self, greeted: asyncio.Future) -> None:
        """The chat's whole life in one task, so the session's own tasks all
        share the one HTTP client opened here (a vendor plugin needs it)."""
        session, record, limit = self.ready.session, self.ready.record, None
        try:
            async with http_context.open():
                session.on("close", lambda _ev: self._inbox.put_nowait(_CLOSED))
                await session.start(self.ready.agent, capture_run=True)  # she speaks first: the greeting
                limit = asyncio.create_task(end_after(
                    session, _NoRoom(record.room, session), self.ready.cfg.max_call_minutes * 60,
                    self.ready.phrases.one("goodbye_time_limit", self.language),
                    on_limit=lambda: record.mark("time_limit"),
                ))
                self.replying = False
                greeted.set_result(None)
                while True:
                    item = await self._inbox.get()
                    if item is _CLOSED:  # end_call, the time limit, or an error closed it
                        break
                    if isinstance(item, tuple):
                        record.mark(item[1])
                        break
                    try:
                        await session.run(user_input=item)
                    except Exception:  # noqa: BLE001 - the record has the error; the chat goes on or closes
                        logger.exception("chat %s: a turn failed", self.id)
                    self.replying = False
                if limit is not None:
                    limit.cancel()
                await session.aclose()
        except Exception as err:  # noqa: BLE001 - told to whoever started it, or logged
            if greeted.done():
                logger.exception("chat %s stopped", self.id)
                record.mark("error")
            else:
                greeted.set_exception(err)
        finally:
            if limit is not None:
                limit.cancel()
            await record.finish()
            self.ended, self.replying = True, False
            self.used = time.monotonic()


class Chats:
    """Every chat going in this process."""

    def __init__(self, cfg: Settings, *, most: int = MAX_CHATS, idle: float = IDLE_SECONDS, keep: float = KEEP_ENDED_SECONDS) -> None:
        self.cfg, self.most, self.idle, self.keep = cfg, most, idle, keep
        self._chats: dict[str, Chat] = {}

    async def start(self, clinic_id: int, language: str = "hi") -> Chat:
        """A new chat, already greeted. Raises repo.NotFound,
        call_setup.ClinicPaused or LineOff as a call would be refused, and
        TooManyChats."""
        self.tidy()
        if sum(1 for c in self._chats.values() if not c.ended) >= self.most:
            raise TooManyChats(f"{self.most} chats are going already. End one first.")
        room = f"{repo.CHAT_ROOM}{clinic_id}-{secrets.token_hex(4)}"
        ready = await prepare(self.cfg, CallFor(clinic_id, language, test=True), room, text_only=True)  # type: ignore[arg-type]
        chat = Chat(secrets.token_urlsafe(16), ready, language)
        self._chats[chat.id] = chat
        try:
            await chat.start()
        except Exception:
            del self._chats[chat.id]
            raise
        return chat

    def get(self, chat_id: str) -> Chat:
        try:
            return self._chats[chat_id]
        except KeyError:
            raise NoSuchChat(chat_id) from None

    def forget_call(self, call_id: int) -> None:
        """Its record was erased: nothing left to read."""
        for key in [k for k, c in self._chats.items() if c.ended and c.call_id == call_id]:
            del self._chats[key]

    def tidy(self) -> list[Chat]:
        """Forget chats that ended a while ago; return those gone quiet (to end)."""
        now = time.monotonic()
        for key in [k for k, c in self._chats.items() if c.ended and now - c.used > self.keep]:
            del self._chats[key]
        return [c for c in self._chats.values() if not c.ended and not c.replying and now - c.used > self.idle]

    async def watch(self, every: float = 15) -> None:
        """Run for the server's life: ends chats nobody is typing in."""
        while True:
            await asyncio.sleep(every)
            for chat in self.tidy():
                logger.info("chat %s: quiet for %g min, ending it", chat.id, self.idle / 60)
                await chat.end("caller_left")

    async def close(self) -> None:
        """The server is stopping: end every chat so its record is written."""
        await asyncio.gather(*(c.end("shutdown") for c in self._chats.values() if not c.ended), return_exceptions=True)
