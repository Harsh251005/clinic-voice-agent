"""A hard cap on call length, so a forgotten or abused call can't run up
provider and LiveKit minutes. At the limit the receptionist says a short
goodbye and hangs up, the way end_call does."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

logger = logging.getLogger("clinic-agent")

GOODBYE = (
    "The call has reached its time limit. In one short sentence, in the caller's "
    "language, apologise, say they are welcome to call again, and say goodbye. "
    "Do not call any tools."
)


async def end_after(session, job_ctx, seconds: float, on_limit: Callable[[], None] | None = None) -> None:
    """Sleep, then say goodbye and close the room (which disconnects the
    caller). Cancelled by the entrypoint if the call ends first. `on_limit`
    is told as the limit is reached (the call's record notes why it ended)."""
    await asyncio.sleep(seconds)
    if on_limit:
        on_limit()
    logger.info("call reached its %g-minute limit in room %s", seconds / 60, job_ctx.room.name)
    try:
        handle = session.generate_reply(instructions=GOODBYE, allow_interruptions=False)
        await asyncio.wait_for(asyncio.ensure_future(handle), timeout=20)
    except Exception:  # noqa: BLE001 - whatever happened, the call still ends
        logger.exception("goodbye at the time limit failed; hanging up anyway")
    try:
        await job_ctx.delete_room()
    except Exception:  # noqa: BLE001 - console has no real room to delete
        logger.warning("could not delete room %s at the time limit", job_ctx.room.name)
    job_ctx.shutdown(reason="call time limit")
