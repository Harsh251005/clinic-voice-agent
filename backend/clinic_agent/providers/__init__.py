"""Vendor-specific construction, kept behind three functions.

Swapping a vendor means adding one builder to the `BUILDERS` dict in the
matching module and changing the provider name in `.env`. No other file in
the codebase imports a vendor package.
"""

from clinic_agent.providers.llm import build_llm
from clinic_agent.providers.stt import build_stt
from clinic_agent.providers.tts import build_tts

__all__ = ["build_llm", "build_stt", "build_tts"]
