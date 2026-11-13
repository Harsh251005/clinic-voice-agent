# CLAUDE.md

A Hindi/Hinglish voice receptionist for Indian clinics: a LiveKit Agents
worker plus a FastAPI server in `backend/`, the Next.js dashboard in
`frontend/`. A rule marked **†** is Harsh's ruling (`docs/rulings.md`):
change it only when he asks.

Folder notes load when you work there:
`backend/clinic_agent/CLAUDE.md` (call pipeline, booking, clips, problems,
costs, records), `backend/clinic_agent/store/CLAUDE.md` (database),
`backend/api/CLAUDE.md` (call links, dashboard API, access),
`frontend/CLAUDE.md` (dashboard).

## Hard rules

- **Vendors:** STT and TTS `sarvam`; LLM `openai` (default †) or `sarvam`.
  Never add others (`test_only_the_allowed_vendors_are_registered`).
- **One language line, Hindi †** (`lines.py`). Dispatch still names the
  language (always `hi`) so a second line later is one entry. Leftover
  `ELEVENLABS_*` / `*_PROVIDER` lines in `.env` are refused at startup.
- **Behaviour lives in the database, set in the dashboard †**
  (`receptionist_settings.py`). Shared, `system_settings` (Admin >
  Receptionist): rules text, brain + model names, hearing, turn-taking,
  greeting interruptible. Per clinic, `clinics` (its Receptionist tab,
  admins only): instructions, directions, voice model + speaker, speed,
  pitch, longest call. `.env` holds only secrets and plumbing. A leftover
  moved line (`MOVED_ENV`) stops worker and API (`refuse_moved_settings`)
  once the migrations command has copied it in.
- **Import boundaries** (`tests/test_boundaries.py`): only `providers/`
  imports a vendor package; only `store/` imports SQLAlchemy/Alembic
  (elsewhere type-hint with `Session`/`Sessions` from `store/db.py`).
- **Only `config.py` reads `os.environ`.** A new secret = a `Settings`
  field + `load_settings()` line + `.env.example` entry. A behaviour setting
  = a column + migration + admin field instead, never `.env`.
- **Default rules (`prompts.RULES`) describe only what is built:** no
  promised checks, holds, messages or callbacks. Add a capability to them in
  the same change that builds it. Admin-replaced rules are the admin's
  wording; live evals grade only the default.
- **Any new failure mode gets an incident kind in the same change**, never
  log-only. **A new billable vendor call records its usage** in the same
  change. **A new row-id route goes through `repo.in_clinic`** + an
  `ATTACKS` entry.
- **Keep `backend/README.md` current** with every behaviour, command or
  setup change, in the same commit. After any API change run
  `npm run api:types` in `frontend/` (`tests/test_openapi.py` fails if stale).
- **Live tests: OpenAI only, as text, never Sarvam.** Spend no OpenAI or
  Sarvam credits without asking.

## Commands (from `backend/`, Python ≥3.13, `uv`)

```bash
uv sync && cp .env.example .env
uv run python -m clinic_agent.store.migrations  # after every pull; the only schema changer
uv run python main.py console [--text] [--clinic N]  # local mic / typed LLM-only; no LiveKit minutes
uv run python main.py dev | start  # needs the 3 LIVEKIT_* values; free tier 1,000 min/month; restart after edits
uv run python -m api               # call-link + dashboard API server
uv run pytest                      # offline suite; -m live spends OpenAI credits
docker compose up --build          # (repo root) Postgres + API + dashboard + demo; --profile voice adds worker
```

Prefer `console`. Every voice mode spends Sarvam credits. CI runs the
offline suite on SQLite and Postgres, dashboard typecheck/lint/build and
Playwright on every push, calls no vendor; keep it green. No linter.

## Deliberate choices — don't "fix" these

(Former `.env` names; now dashboard fields, defaults in
`providers/defaults.py`.)

- Turn detection `"stt"`, set explicitly in `session.py` (omitting it falls
  back to LiveKit's turn-detector model).
- Local Silero VAD, interruption mode `"vad"` †, explicit so console/dev
  match `start` (not LiveKit Cloud's adaptive model). `INTERRUPT_MIN_SPEECH`
  tunes barge-in.
- Raw PCM TTS (`linear16`), not the plugin's mp3: no decode per chunk.
- `SARVAM_TTS_SPEAKER` must be a `bulbul:v3` voice (default `suhani`);
  v2 names like `anushka` are rejected.
- OpenAI default `gpt-4.1-mini` †. For gpt-5+ and `o*` models the builder
  forces `reasoning_effort="none"` (else Chat Completions rejects tools).
- `SARVAM_STT_LANGUAGE=unknown`: per-utterance auto-detect hears mixed-in
  English. Test STT as a call feeds it: real time, lead-in noise, stream
  open, batch models via `StreamAdapter`.
- One instruction set per line (`prompts.RULES["hi"]`), **under 500 words
  †**. Fillers and fallback goodbye follow the line, not the caller. A caller
  asking for English is told kindly it's Hindi only; never promise English.
- Hindi replies in Devanagari (TTS pronounces by script; romanised Hindi is
  read as English). Don't switch prompt or `SARVAM_STT_MODE` to romanised.
- `SARVAM_LLM_MODEL` default `sarvam-105b-conversations`; fall back to
  `sarvam-105b` if the plan lacks it.

## Not built yet

Server deployment, telephony (identity is the spoken mobile number until
caller ID), vendor fallback, the patient front door. Plans live in
`~/.claude/plans/`; current status lives in project memory, not here.
