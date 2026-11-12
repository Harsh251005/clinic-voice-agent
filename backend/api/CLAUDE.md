# API server (`api/`)

FastAPI. Reads data only via `repo`; fails fast on missing LiveKit settings
or an old schema, like `main.py`.

## Call links (browser calls until telephony)

`/call/<slug>` page (no language choice: every call is Hindi). `POST
/call/<slug>/pass` (no body; an old tab's is ignored) signs a LiveKit token
for a fresh room whose `RoomConfiguration` dispatches `AGENT_NAME` with
`dispatch.metadata_for(clinic_id, "hi")`: mic-only, 2 participants, 5-min
TTL. In-memory rate limits (per IP, per clinic); `CLIENT_IP_HEADER` names
the trusted proxy header (last entry used). Strict CSP; livekit-client
pinned with SRI.

## Dashboard API (`dashboard/`)

- FastAPI owns Google sign-in (Authlib); signed session cookie holds only
  the email.
- `access.py`: `Viewer`, `current_viewer`, `open_clinic` (404 for clinics
  you can't open; admins open all), `clinic_staff` (patient data: members
  only, admin non-member → 403), `admin`, `same_site` (CSRF header
  `x-clinic-console`), `staff_errors` (ValueError → 422).
- **Every route taking a row id goes through `repo.in_clinic`** (IDOR) and
  gets an entry in `ATTACKS` (`tests/test_dashboard_api.py`) for a new row
  type. `/api/admin/*` is cross-clinic by design, admins only, returns no
  patient data except the logged transcript opening.
- Tests set the viewer with `dependency_overrides`, never a backdoor.
- **Staff test calls** (`calls.py`, page `talk`): real calls (book for
  real), dispatch `"test": true` signed into the pass, `calls.test`, kept
  out of counts and problems (not LiveKit minutes). `DELETE
  …/calls/{id}` erases a finished one via `repo.erase_test_call` (all or
  nothing; moves record `undo`). Patients' calls are never erasable.
- Voice model + speaker are saved and checked together: a pair the vendor
  refuses is a 422.
