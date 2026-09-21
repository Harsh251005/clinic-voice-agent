"""end_call: hang up once the caller is done.

LiveKit's EndCallTool speaks the goodbye first, shuts the session down after
that speech finishes, and deletes the room, which disconnects a phone caller.
Hidden during the greeting so the agent can't hang up before anyone speaks.
"""

from __future__ import annotations

from livekit.agents.beta.tools import EndCallTool

GOODBYE = (
    "Say one short, warm goodbye in the caller's language, following the same "
    "script rules as every reply. Say nothing else."
)


def end_call_tool() -> EndCallTool:
    return EndCallTool(
        extra_description=(
            "Use when the caller says they are done, e.g. 'bas itna hi', 'thank you, bye', "
            "'ठीक है, धन्यवाद'. Not when they are still deciding or ask to wait."
        ),
        end_instructions=GOODBYE,
        ignore_on_enter=True,
    )
