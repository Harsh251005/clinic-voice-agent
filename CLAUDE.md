# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Hindi/Hinglish voice receptionist for Indian clinics. All code lives in
`backend/`: a LiveKit Agents worker. **Allowed vendors only:** STT and TTS
are `sarvam` or `elevenlabs`, the LLM `sarvam` or `openai` — never add others
(`test_only_the_allowed_vendors_are_registered` enforces it). Sarvam is the
production stack and the default for all three. Testing stack today:
ElevenLabs STT + OpenAI LLM + ElevenLabs TTS, to save Sarvam credits; live
tests always pin that stack. Switch with the three `*_PROVIDER` lines in
`.env`, never by commenting code out: every vendor has its own model/voice
settings (`SARVAM_TTS_SPEAKER`, `ELEVENLABS_TTS_VOICE`, …), so nothing else
changes. The old shared names (`TTS_SPEAKER`, …) are refused at startup.

Current state: **Stage 2 built** (plan:
`~/.claude/plans/distributed-munching-wall.md`); **Stage 3 production setup in
progress, no telephony** (plan: `~/.claude/plans/stage-3-production-setup.md`): clinic database, free-slot
rules, agent answering from clinic data, booking + cancel/reschedule tools,
end-call tool, `console --text`. Stage 3 so far: Postgres + Alembic, one
worker for all clinics (dispatch), browser call links (`api/`), Google
sign-in, and the **Next.js dashboard** (`frontend/`, Stage 3b; Streamlit
retired). Not yet: Docker/CI (slice 5), telephony (identity is by spoken
mobile number until caller ID exists). The
instructions (`clinic_agent/prompts.py`) may only describe what is built: no
promised checks, holds, messages or callbacks. Add a capability to them in the
same change that builds it.

## Commands

Dashboard: see `frontend/CLAUDE.md`. After any API change run
`npm run api:types` in `frontend/` (`tests/test_openapi.py` fails if stale).


Run from `backend/` (Python ≥3.13, managed with `uv`, `package = false`):

```bash
uv sync                          # install
cp .env.example .env             # then set the keys for the selected providers
uv run python -m clinic_agent.store.migrations  # schema up to date (after every pull)
uv run python main.py console    # talk over the local mic — spends no LiveKit minutes
uv run python main.py console --text  # typed, LLM-only: no STT/TTS built or billed
uv run python main.py console --clinic 2  # pick a clinic when there are several
uv run python main.py dev        # join rooms it is dispatched to, reloads on save
uv run python main.py start      # production worker
uv run python -m api             # call-link server: /call/<slug> page + join passes
```

Prefer `console` for testing. `dev`/`start` need the three `LIVEKIT_*` values
and spend from LiveKit Cloud's free tier (1,000 agent-session minutes/month).
All modes spend credits on the selected providers (ElevenLabs has a free
monthly quota; Sarvam and OpenAI are paid per use).

```bash
uv run pytest                    # offline tests: config, providers, session, boot
uv run pytest -m live            # OpenAI + ElevenLabs for real (never Sarvam); spends credits
```

No linter or formatter is configured.

## Architecture

The pipeline is split so each concern lives in exactly one module:

- `main.py` — validates config *before* `cli.run_app` starts the worker
  (a `ConfigError`, unknown provider, missing key, old schema or, in console,
  a missing clinic exits with a one-line message, not a traceback). **One
  worker serves every clinic:** it registers as `dispatch.AGENT_NAME`
  (explicit dispatch) and each job reads its clinic from the dispatch
  metadata (`dispatch.clinic_id_from`); no clinic or an unknown one → job
  refused, never guessed. Console has no dispatch: `--clinic N` (console-only;
  stripped from argv before LiveKit's CLI) or the only clinic. Each job loads
  the clinic (`context.load_clinic`, off the event loop), builds instructions,
  builds a session and starts `ClinicAgent` in the room, then starts
  `call_limit.end_after` (`MAX_CALL_MINUTES`), cancelled on job shutdown.
  The prompt's opening rule makes the agent say it is an automated assistant.
- `api/` — FastAPI call-link server (browser calls until telephony).
  `/call/<slug>` page; `POST /call/<slug>/pass` signs a LiveKit token for a
  fresh room whose `RoomConfiguration` dispatches `AGENT_NAME` with
  `dispatch.metadata_for(clinic_id)`: mic-only, 2 participants, 5-min TTL.
  In-memory rate limits (per IP, per clinic); `CLIENT_IP_HEADER` names the
  trusted proxy header (last entry used). Strict CSP; livekit-client pinned
  with SRI. Reads data only via `repo`; fails fast on missing LiveKit
  settings or old schema, like `main.py`.
- `api/dashboard/` — the dashboard JSON API for `frontend/` (plan
  `~/.claude/plans/stage-3b-nextjs-dashboard.md`). FastAPI
  owns Google sign-in (Authlib) and a signed session cookie holding only the
  email; `access.py` has `Viewer`, `current_viewer`, `open_clinic` (404 for
  clinics you can't open; admins open all), `clinic_staff` (patient data:
  members only, admin non-member → 403), `admin`, `same_site` (CSRF header
  `x-clinic-console`), `staff_errors` (ValueError→422). **Every route that
  takes a row id must go through `repo.in_clinic`** (IDOR; `/api/admin/*` is
  cross-clinic by design, admins only, and returns no patient data except the
  logged transcript opening); add an entry to
  `ATTACKS` in `tests/test_dashboard_api.py` for any new row type. Tests
  set the viewer with `dependency_overrides`, never a backdoor.
- `clinic_agent/config.py` — the **only** place that reads `os.environ`.
  Frozen `Settings` dataclass; a new setting means a field, a line in
  `load_settings()`, and an entry in `.env.example`.
- `clinic_agent/session.py` — the **only** place STT + LLM + TTS are combined
  into an `AgentSession`. `text_only=True` (from `console --text`, detected in
  `main.py` as `TEXT_ONLY`) builds an LLM-only session with manual turns; boot
  then skips the speech providers and their keys.
- `clinic_agent/agent.py` — behaviour only: takes its instructions from the
  entrypoint; tools attach here. Speaks first via `on_enter`.
- `clinic_agent/prompts.py` — fixed persona `RULES` + `clinic_facts()` generated
  from the database per call (active doctors, grouped weekly hours, leave and
  holidays in the booking window, FAQ, current clinic time). Static facts go in
  the prompt; tools are only for changing data and actions.
- `clinic_agent/context.py` — `load_clinic(cfg)` and `clinic_now(tz)`.
- `clinic_agent/call_record.py` — `CallRecorder`: every call's **trace**
  (`calls` + `call_events`: timings, tool names/ok, vendor error types,
  end reason, outcome from what tools changed) and **transcript**
  (`call_transcripts`, patient data, own table). **Never audio;** the
  session starts with `record=False`. The trace must never hold words from
  the call (operator sees it; transcripts only via a logged opening,
  `transcript_access`). Recording failures are logged, never break a call.
  Tools report changes through `ClinicLink.on_change` (booking functions
  return `booking.Changed`). `store/purge.py`: transcripts 30 d, traces 180 d.
- `clinic_agent/tools/call.py` — `end_call` via LiveKit's `beta.tools.EndCallTool`
  (`ignore_on_enter=True`; goodbye text follows the script rules).
- `clinic_agent/booking.py` — booking rules as plain functions over a session;
  raise `BookingError` with a caller-sayable message. `clinic_agent/tools/`
  holds the LiveKit `@function_tool` wrappers only: run the rule in
  `asyncio.to_thread`, map `BookingError` → `ToolError`. Put rules in
  `booking.py`, never in the wrapper. Tests: in-memory DB for rules; a file DB
  for tools (SQLite `:memory:` is per-thread, so threaded tools would see an
  empty database). Live evals use `mock_tools` so the LLM's tool choices are
  graded without a real clock. **Booking is check-then-book, enforced in
  code**: `check_booking` validates and returns the read-back; the no-argument
  `book_appointment` books only what was checked, and only after the caller
  has spoken since (`tools/booking.py`, the one piece of call state kept in a
  wrapper). Never go back to trusting a `caller_confirmed` flag for booking.
- `clinic_agent/store/` — clinic data (SQLAlchemy, sync). `repo.py` holds every
  query; writes commit before returning; callers see `repo.NotFound` /
  `repo.SlotTaken`, never SQLAlchemy errors. **Only `store/` imports
  SQLAlchemy.** Double booking is prevented by a partial unique index, not by
  code; only that index's violation may become `SlotTaken` (`_is_slot_clash`).
  Patients are unique on (clinic, phone, name): families share phones, and a
  new name must never rename an existing patient. **Schema changes = an
  Alembic revision** (`store/alembic/versions/`, `uv run alembic revision
  --autogenerate --rev-id 000N`), read and committed. Only
  `python -m clinic_agent.store.migrations` changes a schema; running code
  calls `migrations.check()` and refuses an old schema, never migrates.
  `created_at` is naive UTC (`utc_now`); appointment times are clinic-local.
  SQLite revisions run with foreign keys OFF (`_upgrade_sqlite`): a batch
  table rebuild with them on cascade-deletes child rows. Clinics have a
  unique `slug` (call link); change it only via `repo.set_slug`.
  Tests: `db` fixture also runs on Postgres when `TEST_POSTGRES_URL` is set
  (local container `clinic-pg`, port 5433; see README). Clinic details are
  data (seed or dashboard), never in `.py` files.
- `frontend/` — the dashboard (Next.js, screens only); its notes load from
  `frontend/CLAUDE.md` when working there.
- `clinic_agent/providers/{stt,llm,tts}.py` — each has a `BUILDERS` registry
  mapping a name to a builder returning LiveKit's base `STT`/`LLM`/`TTS` class.
  Builders own their vendor's defaults (model/voice settings are `None` in
  `Settings` when blank) and call `require_key(...)` for their own API key, so
  only selected vendors need keys. `main.py` builds all three at boot, which is
  what turns a missing key into a startup error.

**Invariant: only `providers/` imports a vendor package.** Everything else
works against LiveKit's base classes. Swapping a vendor = add a builder to the
matching `BUILDERS` dict + set `STT_PROVIDER` / `LLM_PROVIDER` /
`TTS_PROVIDER` in `.env`. Unknown names fail at startup listing what exists.
Both import rules (vendors → `providers/`, SQLAlchemy/Alembic → `store/`) are
enforced by `tests/test_boundaries.py`; outside `store/`, type-hint sessions
with `Session` / `Sessions` from `store/db.py`.

## Deliberate choices — don't "fix" these

- **Turn detection is `"stt"`**, set explicitly in `session.py` (omitting it
  falls back to LiveKit's own turn-detector model).
- **Local Silero VAD, interruption mode `"vad"`** (Harsh, 2026-09-25), set
  explicitly in `session.py`. The VAD handles barge-in, and for a batch STT
  (ElevenLabs `scribe_v2`, the default) it also cuts each utterance; a
  streaming STT (Sarvam) ends turns itself. The explicit mode keeps `console`/`dev` from using LiveKit Cloud's
  adaptive model, so local tests match `start`. `INTERRUPT_MIN_SPEECH` tunes it.
- **Keep `backend/README.md` current** with every behaviour, command or setup
  change, in the same commit.
- **Raw PCM TTS output** (`linear16` for Sarvam, `pcm_24000` for ElevenLabs).
  Both plugins default to mp3; PCM avoids a decode per chunk.
- **`SARVAM_TTS_SPEAKER` must be a `bulbul:v3` voice** (default `suhani`); the
  plugin rejects v2 names such as `anushka`. ElevenLabs' is `ELEVENLABS_TTS_VOICE`, a voice ID.
- **OpenAI default is `gpt-6-luna`** (Harsh's pick), a reasoning model. The
  builder forces `reasoning_effort="none"` for gpt-5-or-later and `o*` models:
  Chat Completions rejects tools otherwise (400 every turn), the plugin only
  sets it for model names it knows, and no reasoning step keeps replies fast.
- **`SARVAM_STT_LANGUAGE=unknown`** auto-detects per utterance. On
  ElevenLabs (`ELEVENLABS_STT_LANGUAGE`) blank or `unknown` means `hi` (auto-detect there breaks live calls).
  Its default `scribe_v2` is batch (VAD-cut utterances over HTTP); only
  `scribe_v2_realtime` streams, and it must keep `server_vad={}` (manual
  commits never fire on a call). Test STT the way a call feeds it: real
  time, lead-in noise, stream open, and a batch model through LiveKit's
  `StreamAdapter` (its bare `stream()` hits the realtime websocket: 1008).
- **Hindi replies are written in Devanagari** (prompt rule). The TTS pronounces
  by script; romanised Hindi ("aap kaise hain") is read with English spelling
  rules. Don't switch the prompt or `SARVAM_STT_MODE` to romanised output.
- **ElevenLabs default model is `eleven_v3_conversational`**, chosen for realism
  over latency.
- `SARVAM_LLM_MODEL` defaults to `sarvam-105b-conversations`; fall back to
  `sarvam-105b` if the plan lacks it.
