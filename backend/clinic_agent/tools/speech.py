"""Short lines the tools speak themselves: the "one moment" before a lookup.

A tool call costs a model round before it and another after it, which is
dead air on a phone. The instructions ask the model to say a short line
("एक सेकंड, मैं चेक करके बताती हूँ") in the same reply as the tool call, so it
plays at once. When the model forgets, the tool says one for it - never both.
"""

from __future__ import annotations

import re
from itertools import count

from livekit.agents import RunContext

DEVANAGARI = re.compile(r"[ऀ-ॿ]")

FILLERS = {
    True: ["एक सेकंड जी, मैं चेक करके बताती हूँ।", "ठीक है, एक पल, मैं देख लेती हूँ।", "जी, बस एक सेकंड।"],
    False: ["One moment, let me check.", "Sure, just a second.", "Let me look that up for you."],
}
_turn = count()


def caller_speaks_hindi(session) -> bool:
    """Whether the caller's last words were Hindi (Devanagari, as the STT writes it)."""
    for item in reversed(session.history.items):
        if item.type == "message" and item.role == "user" and (text := item.text_content):
            return bool(DEVANAGARI.search(text))
    return True  # Hindi/Hinglish is the default at these clinics


def spoke_before_tool(ctx: RunContext) -> bool:
    """Whether the model said anything in the reply that called this tool.
    Only valid after `ctx.wait_for_playout()`: the reply's text is recorded
    once it has played."""
    items = ctx.speech_handle.chat_items
    mine = next(
        (i for i, it in enumerate(items)
         if it.type == "function_call" and it.call_id == ctx.function_call.call_id),
        None,
    )
    after = items[mine + 1:] if mine is not None else []
    return any(
        it.type == "message" and it.role == "assistant" and (it.text_content or "").strip()
        for it in after
    )


async def filler_unless_spoken(ctx: RunContext | None, said: set[str]) -> None:
    """Say one short "let me check" line if the model didn't say anything
    before calling the tool. `said` holds speech ids already covered, so
    several tools called in one reply say it once. No-op without a session
    (tools called directly, as in tests)."""
    if ctx is None:
        return
    await ctx.wait_for_playout()
    if spoke_before_tool(ctx) or ctx.speech_handle.id in said:
        return
    said.add(ctx.speech_handle.id)
    options = FILLERS[caller_speaks_hindi(ctx.session)]
    # Not added to the chat: the model's next reply shouldn't treat it as a turn.
    ctx.session.say(options[next(_turn) % len(options)], add_to_chat_ctx=False)
