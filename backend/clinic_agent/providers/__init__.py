"""Vendor-specific construction, kept behind three functions.

Each builder is one vendor; which vendors a call uses is its language line
(clinic_agent/lines.py). Adding a vendor means one builder in the matching
`BUILDERS` dict and naming it in a line. No other file in the codebase
imports a vendor package.
"""

from clinic_agent.providers.llm import build_llm
from clinic_agent.providers.stt import build_stt
from clinic_agent.providers.tts import build_tts

__all__ = ["build_llm", "build_stt", "build_tts"]
