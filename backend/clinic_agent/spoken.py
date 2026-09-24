"""Clock times as a Hindi speaker says them, so the LLM never has to.

Left to itself the LLM turned 12:30 into "बारह साढ़े बजे" or "बारह तीस"
and 17:00 into "सत्रह बजे". Tool results carry these words next to each
time and the prompt tells the LLM to use them as given.
"""

from __future__ import annotations

from datetime import time

NUMBERS = (
    "", "एक", "दो", "तीन", "चार", "पाँच", "छह", "सात", "आठ", "नौ", "दस",
    "ग्यारह", "बारह", "तेरह", "चौदह", "पंद्रह", "सोलह", "सत्रह", "अठारह", "उन्नीस", "बीस",
    "इक्कीस", "बाईस", "तेईस", "चौबीस", "पच्चीस", "छब्बीस", "सत्ताईस", "अट्ठाईस", "उनतीस", "तीस",
    "इकतीस", "बत्तीस", "तैंतीस", "चौंतीस", "पैंतीस", "छत्तीस", "सैंतीस", "अड़तीस", "उनतालीस", "चालीस",
    "इकतालीस", "बयालीस", "तैंतालीस", "चवालीस", "पैंतालीस", "छियालीस", "सैंतालीस", "अड़तालीस", "उनचास", "पचास",
    "इक्यावन", "बावन", "तिरेपन", "चौवन", "पचपन", "छप्पन", "सत्तावन", "अट्ठावन", "उनसठ",
)


def hindi_time(t: time) -> str:
    """"साढ़े बारह बजे" for 12:30: the 12-hour clock with सवा / साढ़े /
    पौने, as people say it. Which part of the day is left to the caller's
    context (the tool groups times by it)."""
    hour = t.hour % 12 or 12
    nxt = hour % 12 + 1
    if t.minute == 0:
        return f"{NUMBERS[hour]} बजे"
    if t.minute == 15:
        return f"सवा {NUMBERS[hour]} बजे"
    if t.minute == 30:
        return {1: "डेढ़ बजे", 2: "ढाई बजे"}.get(hour, f"साढ़े {NUMBERS[hour]} बजे")
    if t.minute == 45:
        return f"पौने {NUMBERS[nxt]} बजे"
    return f"{NUMBERS[hour]} बजकर {NUMBERS[t.minute]} मिनट"
