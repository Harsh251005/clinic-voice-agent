"""end_call: say goodbye, then hang up.

The goodbye is an argument of the tool call itself, not a second LLM reply
after it: LiveKit's EndCallTool asked the model for a goodbye *after* the
tool ran, and when that reply came back empty or the caller's voice
interrupted it, the call ended in silence. Here the model writes the goodbye
(what was done on the call, then goodbye) as it decides to hang up; the tool
speaks it with interruptions off, waits until it has played, and only then
closes the session and deletes the room, which disconnects a phone caller.
Hidden during the greeting so the agent can't hang up before anyone speaks.
"""

from __future__ import annotations

import logging

from livekit.agents import RunContext, function_tool, get_job_context
from livekit.agents.llm import ToolFlag

from clinic_agent.tools.speech import caller_speaks_hindi

logger = logging.getLogger("clinic-agent")

# Only if the model sent an empty goodbye: never hang up without one.
FALLBACK_GOODBYE = {
    True: "कॉल करने के लिए धन्यवाद जी। आपका दिन शुभ हो, नमस्ते!",
    False: "Thank you for calling. Have a good day, goodbye!",
}


def end_call_tool():
    @function_tool(flags=ToolFlag.IGNORE_ON_ENTER)
    async def end_call(ctx: RunContext, goodbye: str) -> None:
        """Say goodbye and hang up. Use when the caller is done: they say bye, "bas itna hi",
        "that's all", or say no after you ask whether there is anything else. Not when they
        only say thanks or "ठीक है" after an answer - ask if there is anything else first -
        and never when they are still deciding or ask you to wait.

        Write nothing else in the reply that calls this: the goodbye is spoken for you.

        Args:
            goodbye: The last thing you say, following the same script rules as every reply.
                One or two short sentences: first what was done on this call, if anything
                (e.g. the booked doctor, day and time), then a warm goodbye.
        """
        ctx.disallow_interruptions()
        await ctx.wait_for_playout()  # anything the model said despite the rule above
        text = goodbye.strip() or FALLBACK_GOODBYE[caller_speaks_hindi(ctx.session)]
        await ctx.session.say(text, allow_interruptions=False).wait_for_playout()
        logger.info("end_call: goodbye played, hanging up")
        hang_up(ctx.session)

    return end_call


def hang_up(session) -> None:
    """Close the session and, on a real call, delete the room (disconnecting
    the caller) and end the job. Console and tests have no room to delete."""
    try:
        job = get_job_context()
    except RuntimeError:
        job = None
    if job is not None:
        async def delete_room() -> None:
            try:
                await job.delete_room()
            except Exception:  # noqa: BLE001 - console has no real room
                logger.warning("could not delete room %s after end_call", job.room.name)

        job.add_shutdown_callback(delete_room)
        session.once("close", lambda ev: job.shutdown(reason="caller done"))
    session.shutdown()
