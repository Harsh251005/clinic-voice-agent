from datetime import time

import pytest

from clinic_agent.spoken import hindi_time


@pytest.mark.parametrize(
    ("at", "said"),
    [
        ("09:00", "नौ बजे"),
        ("12:00", "बारह बजे"),
        ("17:00", "पाँच बजे"),  # 12-hour: never "सत्रह बजे"
        ("10:15", "सवा दस बजे"),
        ("12:30", "साढ़े बारह बजे"),  # never "बारह साढ़े बजे"
        ("13:30", "डेढ़ बजे"),
        ("14:30", "ढाई बजे"),
        ("11:45", "पौने बारह बजे"),
        ("12:45", "पौने एक बजे"),
        ("10:20", "दस बजकर बीस मिनट"),
        ("19:40", "सात बजकर चालीस मिनट"),
        ("00:05", "बारह बजकर पाँच मिनट"),
    ],
)
def test_times_are_said_the_everyday_way(at, said):
    assert hindi_time(time.fromisoformat(at)) == said
