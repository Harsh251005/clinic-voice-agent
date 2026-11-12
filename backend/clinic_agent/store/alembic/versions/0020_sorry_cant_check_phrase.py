"""sorry, can't check: a fixed line the code says when a lookup fails

Revision ID: 0020
Revises: 0019
Created: 2026-11-10 21:00:00

Seen 2026-11-10 (call 37): every lookup failed and the model made up free
times. When a lookup crashes or fails the same way twice, the code now says
this line itself and the model says nothing. Edited and recorded on Admin,
Voice & phrases, like the other fixed lines; to be proofread.
"""

from alembic import op
import sqlalchemy as sa


revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None

# (kind, language, slot, English source, spoken text), as in 0014.
SEEDS = [
    ("sorry_cant_check", "hi", 0,
     "I am sorry, I am not able to check this right now. Please call again in a little while, or ask at the clinic directly.",
     "माफ़ कीजिए जी, अभी मैं यह चेक नहीं कर पा रही हूँ। आप थोड़ी देर बाद दोबारा कॉल कर लीजिए, या क्लिनिक में सीधे पूछ लीजिए।"),
]

_phrases = sa.table(
    'phrases', sa.column('kind'), sa.column('language'), sa.column('slot'),
    sa.column('source'), sa.column('text'), sa.column('pace'),
)


def upgrade() -> None:
    # 0.9: the speed the other recorded lines are spoken at (migration 0017).
    op.bulk_insert(_phrases, [
        {"kind": k, "language": lang, "slot": slot, "source": source, "text": text, "pace": 0.9}
        for k, lang, slot, source, text in SEEDS
    ])


def downgrade() -> None:
    op.execute("DELETE FROM phrases WHERE kind = 'sorry_cant_check'")
