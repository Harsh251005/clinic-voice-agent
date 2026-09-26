"""A call's record, written by the worker: its trace and its transcript.

The trace is what happened, never what was said: per-turn timings (STT,
end of turn, LLM time to first token, TTS time to first audio, the caller's
whole wait), each tool's
name, result and duration, vendor errors by type, how the call ended and
what it changed. The operator may always see it. The transcript is what was
said, tool arguments and results included: patient data, kept apart
(models.CallTranscript) and deleted after purge.TRANSCRIPT_DAYS. No audio
is ever stored.

Recording must never break a call: every failure here is logged and
swallowed. The row is opened when the call starts, so a call the worker
never finishes (crash, kill) still shows up, left open.
"""

from __future__ import annotations

import asyncio
import logging
import time

from livekit.agents import AgentSession
from livekit.agents.voice.events import (
    CloseEvent,
    CloseReason,
    ConversationItemAddedEvent,
    ErrorEvent,
    FunctionToolsExecutedEvent,
)

from clinic_agent.store import repo
from clinic_agent.store.db import Sessions
from clinic_agent.store.models import utc_now
from clinic_agent.store.purge import transcript_expiry

logger = logging.getLogger("clinic-agent")

END_REASONS = {
    CloseReason.PARTICIPANT_DISCONNECTED: "caller_left",
    CloseReason.USER_INITIATED: "agent_ended",  # end_call shuts the session down
    CloseReason.TASK_COMPLETED: "agent_ended",
    CloseReason.JOB_SHUTDOWN: "shutdown",
    CloseReason.ERROR: "error",
}
# ChatMessage.metrics key -> trace kind. Caller turns: how long until the
# words were known (stt) and the turn judged over (eou). Agent turns: LLM
# time to first token, TTS time to first audio, and the whole wait the
# caller heard, end of their speech to the agent's voice (reply).
TURN_METRICS = {
    "user": [("transcription_delay", "stt"), ("end_of_turn_delay", "eou")],
    "assistant": [("llm_node_ttft", "llm"), ("tts_node_ttfb", "tts"), ("e2e_latency", "reply")],
}
TOOL_TEXT_MAX = 2000  # a tool result in the transcript; slot lists can run long


class CallRecorder:
    def __init__(self, sessions: Sessions, clinic_id: int, room: str, stack: str) -> None:
        self.sessions, self.clinic_id, self.room, self.stack = sessions, clinic_id, room, stack
        self.call_id: int | None = None
        self.t0 = time.time()
        self.started_at = utc_now()
        self.events: list[dict] = []
        self.transcript: list[dict] = []
        self.changes: list[dict] = []
        self.turns = 0
        self.errors = 0
        self.end_reason = ""
        self.finished = False

    # ---------- wiring ----------

    async def start(self) -> None:
        def work() -> int:
            with self.sessions() as s:
                return repo.start_call(s, self.clinic_id, self.room, self.stack, self.started_at).id

        try:
            self.call_id = await asyncio.to_thread(work)
        except Exception:  # noqa: BLE001 - the call goes on unrecorded
            logger.exception("could not open a call record for clinic %s", self.clinic_id)

    def attach(self, session: AgentSession) -> None:
        for name, handler in (
            ("conversation_item_added", self._on_item),
            ("function_tools_executed", self._on_tools),
            ("error", self._on_error),
            ("close", self._on_close),
        ):
            session.on(name, _safe(handler))

    def on_change(self, appointment_id: int, action: str) -> None:
        """An appointment a tool booked, moved or cancelled (tools.booking.ClinicLink)."""
        self.changes.append({"id": appointment_id, "action": action})

    def mark(self, end_reason: str) -> None:
        """Say why the call is ending when the session can't tell (the time limit)."""
        self.end_reason = end_reason

    async def finish(self) -> None:
        """Write the outcome, trace and transcript. Safe to call twice."""
        if self.finished or self.call_id is None:
            return
        self.finished = True
        ended_at = utc_now()
        fields = dict(
            ended_at=ended_at,
            end_reason=self.end_reason or "shutdown",
            outcome=self.outcome(),
            turn_count=self.turns,
            error_count=self.errors,
            appointments=self.changes,
            events=self.events,
            transcript=self.transcript,
            purge_after=transcript_expiry(self.started_at),
        )

        def work() -> None:
            with self.sessions() as s:
                repo.finish_call(s, self.call_id, **fields)

        try:
            await asyncio.to_thread(work)
        except Exception:  # noqa: BLE001 - the call is over either way
            logger.exception("could not save the record of call %s", self.call_id)

    def outcome(self) -> str:
        """From what the tools changed and how the call ended, never from
        what the model says it did."""
        actions = {c["action"] for c in self.changes}
        for action in ("booked", "moved", "cancelled"):
            if action in actions:
                return action
        if self.end_reason == "error":
            return "failed"
        return "info_only" if self.turns else "no_action"

    # ---------- session events ----------

    def _ms(self, at: float) -> int:
        return max(0, round((at - self.t0) * 1000))

    def _on_item(self, ev: ConversationItemAddedEvent) -> None:
        item = ev.item
        if getattr(item, "type", None) != "message" or item.role not in ("user", "assistant"):
            return
        text = item.text_content or ""
        if item.role == "user":
            self.turns += 1
        at = self._ms(ev.created_at)
        entry = {"t_ms": at, "role": "caller" if item.role == "user" else "agent", "text": text}
        if item.interrupted:
            entry["interrupted"] = True
        self.transcript.append(entry)
        # Each turn's timings, as LiveKit measured them for this message.
        for key, kind in TURN_METRICS[item.role]:
            if (seconds := item.metrics.get(key)) is not None:
                self._event(at, kind, "", seconds, detail="interrupted" if item.interrupted else "")

    def _on_tools(self, ev: FunctionToolsExecutedEvent) -> None:
        for call, out in zip(ev.function_calls, ev.function_call_outputs, strict=False):
            ok = not (out and out.is_error)
            took = (out.created_at - call.created_at) if out else None
            # The trace gets the tool's name and result, never its arguments or output.
            self._event(self._ms(call.created_at), "tool", call.name, took, ok=ok)
            self.transcript.append({
                "t_ms": self._ms(call.created_at), "role": "tool", "tool": call.name, "ok": ok,
                "args": call.arguments, "text": (out.output if out else "")[:TOOL_TEXT_MAX],
            })

    def _on_error(self, ev: ErrorEvent) -> None:
        err = ev.error
        exc = getattr(err, "error", err)
        source = ev.source
        name = f"{getattr(source, 'provider', '')}/{getattr(source, 'model', '')}".strip("/") or type(source).__name__
        # The exception's type and status only: a vendor's message can echo what was said.
        detail = type(exc).__name__
        if status := getattr(exc, "status_code", None):
            detail += f" {status}"
        recoverable = getattr(err, "recoverable", False)
        detail += ", retried" if recoverable else ", fatal"
        self.errors += 1
        self._event(self._ms(ev.created_at), "error", name, None, ok=False, detail=detail)
        self.transcript.append({"t_ms": self._ms(ev.created_at), "role": "error", "text": f"{name}: {exc}"[:TOOL_TEXT_MAX]})

    def _on_close(self, ev: CloseEvent) -> None:
        if not self.end_reason:
            self.end_reason = END_REASONS.get(ev.reason, "shutdown")
        if ev.error is not None:
            self.end_reason = "error"

    def _event(self, t_ms: int, kind: str, name: str, seconds: float | None, *, ok: bool = True, detail: str = "") -> None:
        self.events.append({
            "t_ms": t_ms, "kind": kind, "name": name[:100], "ok": ok, "detail": detail[:200],
            "duration_ms": None if seconds is None else round(seconds * 1000),
        })


def _safe(handler):
    def run(ev) -> None:
        try:
            handler(ev)
        except Exception:  # noqa: BLE001 - never let the record break the call
            logger.exception("call record: could not note a %s event", getattr(ev, "type", "?"))

    return run


def stack_of(session: AgentSession, stt: str, llm: str, tts: str, text_only: bool) -> str:
    """Which vendors and models took the call, e.g.
    "elevenlabs/scribe_v2 · openai/gpt-6-luna · elevenlabs/eleven_v3_conversational"."""
    if text_only:
        return f"text · {llm}/{session.llm.model}"
    return f"{stt}/{session.stt.model} · {llm}/{session.llm.model} · {tts}/{session.tts.model}"

