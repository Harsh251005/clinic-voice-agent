# Database (`store/`)

SQLAlchemy, sync. Only this package imports SQLAlchemy/Alembic.

- `repo.py` holds every query; writes commit before returning. Callers see
  `repo.NotFound` / `repo.SlotTaken`, never SQLAlchemy errors.
- **Double booking is prevented by a partial unique index, not code.** Only
  that index's violation may become `SlotTaken` (`_is_slot_clash`).
- Visit marks (arrived/done/no-show) are their own column
  `appointments.visit`, **never a status**: any status but `booked` frees
  the slot.
- Patients are unique on (clinic, phone, name): families share phones; a
  new name must never rename an existing patient.
- Clinics have a unique `slug` (call link); change it only via
  `repo.set_slug`.
- **Schema change = an Alembic revision**
  (`uv run alembic revision --autogenerate --rev-id 000N`), read and
  committed. Only `python -m clinic_agent.store.migrations` changes a
  schema; running code calls `migrations.check()` and refuses an old one,
  never migrates.
- SQLite revisions run with foreign keys OFF (`_upgrade_sqlite`): a batch
  table rebuild with them on cascade-deletes child rows.
- `created_at` is naive UTC (`utc_now`); appointment times are clinic-local.
- Tests: the `db` fixture also runs on Postgres when `TEST_POSTGRES_URL` is
  set (local container `clinic-pg`, port 5433; see README).
