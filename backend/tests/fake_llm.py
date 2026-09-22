"""A scripted LLM, so a real AgentSession can be driven offline: each chat()
call plays the next scripted reply (text, then tool calls), the way a
provider streams them. For testing what the session and tools do around the
model - what gets spoken, when the call ends - never the model's judgement
(that is tests/test_live.py)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from livekit.agents import APIConnectOptions, llm
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, NOT_GIVEN, NotGivenOr
from livekit.agents.utils import shortuuid


@dataclass
class Reply:
    text: str = ""
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)


class FakeLLM(llm.LLM):
    def __init__(self, replies: list[Reply]) -> None:
        super().__init__()
        self.replies = list(replies)
        self.requests: list[llm.ChatContext] = []

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool] | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[llm.ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
    ) -> llm.LLMStream:
        self.requests.append(chat_ctx.copy())
        reply = self.replies.pop(0) if self.replies else Reply()
        return _Stream(self, reply, chat_ctx=chat_ctx, tools=tools or [], conn_options=conn_options)


class _Stream(llm.LLMStream):
    def __init__(self, fake: FakeLLM, reply: Reply, **kwargs: Any) -> None:
        super().__init__(fake, **kwargs)
        self._reply = reply

    async def _run(self) -> None:
        rid = shortuuid()
        if self._reply.text:
            self._event_ch.send_nowait(llm.ChatChunk(
                id=rid, delta=llm.ChoiceDelta(role="assistant", content=self._reply.text)))
        if self._reply.calls:
            self._event_ch.send_nowait(llm.ChatChunk(id=rid, delta=llm.ChoiceDelta(
                role="assistant",
                tool_calls=[
                    llm.FunctionToolCall(name=name, arguments=json.dumps(args), call_id=f"call_{shortuuid()}")
                    for name, args in self._reply.calls
                ],
            )))
