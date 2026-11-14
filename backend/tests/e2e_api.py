"""The API for the dashboard's end-to-end tests (frontend/e2e/start-api.sh):
the real server, with the receptionist's brain scripted so Admin > Try can be
driven through a browser without calling a vendor. Everything else is real:
the session, the tools, the bookings, the record.

    uv run python -m tests.e2e_api

Each chat gets the same script: a booking is checked on the caller's first
turn, booked on the second, and the third says goodbye and hangs up.
"""

import runpy

from livekit.agents import AgentSession

from clinic_agent import call_setup
from tests.fake_llm import FakeLLM, Reply
from tests.test_booking_readback import BOOK, CHECK

SCRIPT = [
    Reply(calls=[CHECK]), Reply("डॉ. आशा मेहता, पाँच बजे, रवि जी के नाम से। सही है?"),
    Reply(calls=[BOOK]), Reply("आपका अपॉइंटमेंट बुक हो गया है। और कुछ?"),
    Reply(calls=[("end_call", {"goodbye": "धन्यवाद, नमस्ते।"})]),
]

# Each reply takes a moment, as a real model's does: the page has to keep
# asking until she has answered (it once stopped after the first ask).
call_setup.build_session = lambda cfg, line, text_only=False: AgentSession(llm=FakeLLM(SCRIPT, delay=0.7))
runpy.run_module("api", run_name="__main__")
