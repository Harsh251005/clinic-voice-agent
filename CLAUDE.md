# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Hindi/Hinglish voice receptionist for Indian clinics. All code lives in
`backend/`: a LiveKit Agents worker. **Allowed vendors only:** STT and TTS
are `sarvam` or `elevenlabs`, the LLM `sarvam` or `openai` — never add others
(`test_only_the_allowed_vendors_are_registered` enforces it). **Two language
lines** (Harsh, 2026-10-12; `clinic_agent/lines.py`): the caller picks
English or Hindi on the call page before the call and keeps it to the end
(no mid-call switch: it would change the voice). **English** = ElevenLabs STT
+ OpenAI + ElevenLabs TTS, English only; **Hindi** = Sarvam × 3, Hindi only.
Neither is "testing" or "production": both are real. A line whose key is
missing is off, not fatal (worker warns, check-in leaves it out, call page
hides it, `language_off` problem on both dashboards). The `*_PROVIDER` lines
are gone and refused at startup. Every vendor keeps its own model/voice
settings (`SARVAM_TTS_SPEAKER`, `ELEVENLABS_TTS_VOICE`, …). Live tests use
only the English line's vendors (never Sarvam).

Current state (2026-10-12): Stages 2, 3 and 5 built, Stage 4 in progress; language lines + call-page switch built (plan `per-clinic-agent-and-language-lines.md`).
Built: clinic database (Postgres + Alembic), free-slot rules, booking +
cancel/reschedule tools with code-enforced confirmation, end-call tool,
`console --text`, one worker for all clinics (dispatch), browser call links
(`api/`), Google sign-in, the **Next.js dashboard** (`frontend/`: Today,
diary, calls, settings), call records and transcripts, the admin panel, and
problems flagged on every page. Not yet: a server deployment, telephony (identity is
by spoken mobile number until caller ID exists), vendor fallback, the
patient front door. Plans: `~/.claude/plans/` (current:
`per-clinic-agent-and-language-lines.md`; also `portfolio-ready.md`,
`stage-4-pb-fallback-and-alerts.md`). The
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
uv run python main.py console --language en  # caller's language: hi (default) or en
uv run python main.py dev        # join rooms it is dispatched to (LiveKit 1.8 dropped reload: restart after edits)
uv run python main.py start      # production worker
uv run python -m api             # call-link server: /call/<slug> page + join passes
docker compose up --build        # (repo root) Postgres + API + dashboard + demo data; --profile voice adds the worker
```

CI (`.github/workflows/ci.yml`) runs the offline suite on SQLite and
Postgres, the dashboard's typecheck/lint/build and the Playwright suite on
every push. Keep it green; it calls no vendor.

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
  (explicit dispatch) and each job reads its clinic **and language** (`en` |
  `hi`) from the dispatch metadata (`dispatch.call_from`); no clinic, an
  unknown one or no known language → job refused, never guessed. Console has
  no dispatch: `--clinic N` (or the only clinic) and `--language en|hi`
  (default `hi`), both console-only and stripped from argv before LiveKit's CLI. Each job loads
  the clinic (`context.load_clinic`, off the event loop), builds instructions,
  builds a session and starts `ClinicAgent` in the room, then starts
  `call_limit.end_after` (`MAX_CALL_MINUTES`), cancelled on job shutdown.
  The prompt's opening rule makes the agent say it is an automated assistant.
- `api/` — FastAPI call-link server (browser calls until telephony).
  `/call/<slug>` page; `POST /call/<slug>/pass` (body `{"language": "en"|"hi"}`,
  required: 400 otherwise, never a default) signs a LiveKit token for a
  fresh room whose `RoomConfiguration` dispatches `AGENT_NAME` with
  `dispatch.metadata_for(clinic_id, language)`: mic-only, 2 participants, 5-min TTL.
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
  **Staff test calls** (`calls.py`, page `talk`): a real call (books for
  real), dispatch `"test": true` signed into the pass, `calls.test`, kept out
  of counts/problems (not LiveKit minutes); `DELETE …/calls/{id}` erases a
  finished one via `repo.erase_test_call` (all or nothing; moves record
  `undo` so they can be put back). Patients' calls are never erasable.
- `clinic_agent/config.py` — the **only** place that reads `os.environ`.
  Frozen `Settings` dataclass; a new setting means a field, a line in
  `load_settings()`, and an entry in `.env.example`.
- `clinic_agent/lines.py` — the two language lines (which vendor per part
  for `en` / `hi`) and `available(cfg)`: which lines have their keys.
- `clinic_agent/session.py` — the **only** place STT + LLM + TTS are combined
  into an `AgentSession`, from the call's line. `text_only=True` (from `console --text`, detected in
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
- `clinic_agent/costs.py` — **what calls cost**: no vendor returns a price,
  so `CallRecorder` saves each call's exact usage (`usage`, from
  `session.usage`; never money, never words) and this prices it when shown:
  usage × the dated price list (`prices`, `exchange_rates`, `allowances`,
  `fixed_costs`, `vendor_bills`), all edited on the admin Prices page
  (`api/dashboard/costs.py`), never in code (Harsh, 2026-10-13). Usage
  outlives its call (FKs `SET NULL`). A new billable vendor call = record
  its usage in the same change, or its cost is silently missing.
- `clinic_agent/incidents.py` — **problems, flagged**: which conditions and
  events count (`KINDS`), `sync` (the API re-checks every 30 s: opens,
  updates, closes) and `report` (events: counted, closed after a quiet
  spell). Words live in `api/dashboard/problems.py`, in two voices: plain
  for the clinic, technical for the admin. Alerts stay **in the website**
  (Harsh, 2026-09-28): every page shows a banner, a bell and "(!)" in the
  tab, so **any new failure mode gets an incident kind in the same change**,
  never log-only. `heartbeat.py`: the worker checks in every 30 s from
  LiveKit's `worker_registered` (not console); stale for 90 s = offline.
- `clinic_agent/tools/call.py` — our own `end_call` (not LiveKit's
  `EndCallTool`, which could hang up in silence): the goodbye is an argument
  of the tool call, spoken with interruptions off, then the room is deleted.
  Hidden during the greeting (`IGNORE_ON_ENTER`).
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
  wrapper). Cancel and reschedule use the same rule, **confirm by
  repeating**: the first call is only the check and read-back, the same
  call again acts once the caller has spoken (`confirmed` in the wrapper).
  Never go back to trusting a `caller_confirmed` flag.
- `clinic_agent/store/` — clinic data (SQLAlchemy, sync). `repo.py` holds every
  query; writes commit before returning; callers see `repo.NotFound` /
  `repo.SlotTaken`, never SQLAlchemy errors. **Only `store/` imports
  SQLAlchemy.** Double booking is prevented by a partial unique index, not by
  code; only that index's violation may become `SlotTaken` (`_is_slot_clash`).
  So visit marks (arrived/done/no-show) are their own column
  `appointments.visit`, **never a status**: any status but `booked` frees
  the slot.
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
  `Settings` when blank) and call `require_key(...)` for their own API key.
  `build_x(cfg, vendor)`. `main.py` tries both lines at boot: a missing key
  turns its line off (warning + `language_off` problem); with neither line
  it exits with a one-line error.

**Invariant: only `providers/` imports a vendor package.** Everything else
works against LiveKit's base classes. Adding a vendor = a builder in the
matching `BUILDERS` dict + naming it in a line in `lines.py`. Unknown names
fail listing what exists.
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
- **OpenAI default is `gpt-4.1-mini`** (Harsh, 2026-10-13: fastest capable
  model, ~1.0 s first token vs `gpt-6-luna` 1.6 s). For any reasoning model
  set in `OPENAI_LLM_MODEL`, the builder forces `reasoning_effort="none"` for gpt-5-or-later and `o*` models:
  Chat Completions rejects tools otherwise (400 every turn), the plugin only
  sets it for model names it knows, and no reasoning step keeps replies fast.
- **`SARVAM_STT_LANGUAGE=unknown`** auto-detects per utterance (the Hindi
  line hears the English words callers mix in). ElevenLabs (the English
  line) is pinned to `en`: its auto-detect breaks live calls.
  Its default `scribe_v2` is batch (VAD-cut utterances over HTTP); only
  `scribe_v2_realtime` streams, and it must keep `server_vad={}` (manual
  commits never fire on a call). Test STT the way a call feeds it: real
  time, lead-in noise, stream open, and a batch model through LiveKit's
  `StreamAdapter` (its bare `stream()` hits the realtime websocket: 1008).
- **Instructions are one set per line** (`prompts.RULES["en" | "hi"]`, same
  core rules). The fillers and fallback goodbye follow the call's line, not
  the caller's last words.
- **Hindi replies are written in Devanagari** (prompt rule). The TTS pronounces
  by script; romanised Hindi ("aap kaise hain") is read with English spelling
  rules. Don't switch the prompt or `SARVAM_STT_MODE` to romanised output.
- **ElevenLabs default model is `eleven_v3_conversational`**, chosen for realism
  over latency.
- `SARVAM_LLM_MODEL` defaults to `sarvam-105b-conversations`; fall back to
  `sarvam-105b` if the plan lacks it.
