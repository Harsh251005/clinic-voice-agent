"""Wait longer for the caller while they read out a number.

A caller gives a mobile number in groups with small pauses ("89 ... 288 ...
03112"). The turn ends `MIN_ENDPOINTING_DELAY` (0.2 s) after the STT's end
of speech, so each group reached the model as its own turn and the agent
asked for the number again (2026-10-23). Waiting that long on every turn
would slow every reply, so the longer wait applies only from the moment the
receptionist asks for a number until the caller's next turn ends.
"""

from __future__ import annotations

import re

# The receptionist asking for a number, in Hindi (Devanagari) or English.
_ASKS_FOR_NUMBER = re.compile(r"नंबर|नम्बर|number|digit", re.IGNORECASE)

# EndpointingOptions.max_delay is 3 s unless set: a wait past it is cut to it.
MAX_WAIT = 3.0


def wait_for_numbers(session, normal: float, for_number: float) -> None:
    """On `session`, end the caller's turn `for_number` seconds after they
    stop while a number was just asked for, `normal` seconds otherwise."""
    longer = min(for_number, MAX_WAIT)

    def set_delay(seconds: float) -> None:
        session.update_options(endpointing_opts={"min_delay": seconds})

    def on_item(ev) -> None:
        item = ev.item
        if getattr(item, "type", None) != "message":
            return
        if item.role == "assistant" and _ASKS_FOR_NUMBER.search(item.text_content or ""):
            set_delay(longer)
        elif item.role == "user":
            set_delay(normal)

    session.on("conversation_item_added", on_item)
