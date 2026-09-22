"""Clinics get a slug: the public name in their call link (/call/<slug>).

Existing clinics get one made from their name, made unique with -2, -3...

Revision ID: 0002
Revises: 0001
"""

import re
import unicodedata

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _slugify(name: str) -> str:
    # A frozen copy of repo.slugify: a migration must not change when app code does.
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:60].strip("-")
    return slug if len(slug) >= 3 else "clinic"


def upgrade() -> None:
    with op.batch_alter_table("clinics") as batch:
        batch.add_column(sa.Column("slug", sa.String(length=60), nullable=True))

    conn = op.get_bind()
    taken: set[str] = set()
    for clinic_id, name in conn.execute(sa.text("SELECT id, name FROM clinics ORDER BY id")):
        base = slug = _slugify(name)
        n = 2
        while slug in taken:
            slug = f"{base[:56]}-{n}"
            n += 1
        taken.add(slug)
        conn.execute(sa.text("UPDATE clinics SET slug = :slug WHERE id = :id"), {"slug": slug, "id": clinic_id})

    with op.batch_alter_table("clinics") as batch:
        batch.alter_column("slug", existing_type=sa.String(length=60), nullable=False)
        batch.create_unique_constraint(op.f("uq_clinics_slug"), ["slug"])


def downgrade() -> None:
    with op.batch_alter_table("clinics") as batch:
        batch.drop_constraint(op.f("uq_clinics_slug"), type_="unique")
        batch.drop_column("slug")
