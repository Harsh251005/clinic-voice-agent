"""The "one moment" around a lookup, and holding the model to it.

A tool call costs a model round before it and another after it, which is
dead air on a phone. The instructions ask the model to say a short line
("एक सेकंड, मैं चेक करके बताती हूँ") in the same reply as the tool call, so it
plays at once. When the model forgets the line, the tool says one for it -
never both. When it says the line but forgets the tool (seen live: "मैं कल
के स्लॉट्स चेक कर लेती हूँ", then silence), `keep_promises` makes it call one.
"""

from __future__ import annotations

import re
from itertools import count

from livekit.agents import AgentSession, RunContext
from livekit.agents.voice.events import SpeechCreatedEvent

DEVANAGARI = re.compile(r"[ऀ-ॿ]")

FILLERS = {
    True: ["एक सेकंड जी, मैं चेक करके बताती हूँ।", "ठीक है, एक पल, मैं देख लेती हूँ।", "जी, बस एक सेकंड।"],
    False: ["One moment, let me check.", "Sure, just a second.", "Let me look that up for you."],
}
_turn = count()

# Saying it will check: "चेक करके", "चेक कर लेती", "देखती हूँ", "let me check"...
# Not "चेकअप" (a check-up) and not a question ("चेक करूँ?"), which waits for the caller.
PROMISE = re.compile(
    r"चेक कर|देख(?:ती|ता) हूँ|देख (?:लेती|लेता)|पता कर(?:ती|ता|के)"
    r"|\b(?:let me|i'?ll|i will) (?:check|look)|\bchecking\b",
    re.IGNORECASE,
)
FOLLOW_THROUGH = (
    "You just told the caller you would check, but called no tool, so they are "
    "waiting in silence. Call the right tool now. Say nothing before it."
)
_nudged: set[str] = set()  # speech ids of forced follow-ups: never nudged again, no extra filler


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
    if spoke_before_tool(ctx) or ctx.speech_handle.id in said or ctx.speech_handle.id in _nudged:
        return
    said.add(ctx.speech_handle.id)
    options = FILLERS[caller_speaks_hindi(ctx.session)]
    # Not added to the chat: the model's next reply shouldn't treat it as a turn.
    ctx.session.say(options[next(_turn) % len(options)], add_to_chat_ctx=False)


def promised_without_tool(handle) -> bool:
    """A finished reply that said it would check, called no tool, and did
    not end on a question to the caller."""
    items = handle.chat_items
    if handle.interrupted or any(it.type == "function_call" for it in items):
        return False
    said = " ".join(it.text_content or "" for it in items if it.type == "message" and it.role == "assistant")
    return bool(PROMISE.search(said)) and not said.rstrip().endswith("?")


def keep_promises(session: AgentSession, tool_names: list[str]) -> None:
    """After every reply that promised a check but called nothing, make the
    model call one of `tool_names` straight away (tool_choice required, so it
    can't just talk again). A forced follow-up is never forced again."""

    def on_created(ev: SpeechCreatedEvent) -> None:
        def on_done(h) -> None:
            # checked at the end: speech_created fires inside generate_reply,
            # before the follow-up's id is known to be one
            if h.id not in _nudged and promised_without_tool(h):
                follow = session.generate_reply(
                    instructions=FOLLOW_THROUGH, tool_choice="required", tools=tool_names,
                )
                _nudged.add(follow.id)

        ev.speech_handle.add_done_callback(on_done)

    session.on("speech_created", on_created)
