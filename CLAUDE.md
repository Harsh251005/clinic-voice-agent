# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Hindi/Hinglish voice receptionist for Indian clinics. All code lives in
`backend/`: a LiveKit Agents worker. Testing stack: Sarvam STT, OpenAI LLM,
ElevenLabs TTS (switched from all-Sarvam to save Sarvam credits; Sarvam
builders stay registered — switch back in `.env`, don't comment code out).

Current state: **Stage 2 in progress** (plan:
`~/.claude/plans/distributed-munching-wall.md`). Done: clinic database, free-slot
rules, Streamlit setup dashboard, agent answering from clinic data, booking
tools. Next: appointments page, end-call tool. No telephony yet. The
instructions (`clinic_agent/prompts.py`) may only describe what is built: no
promised checks, holds, messages or callbacks. Add a capability to them in the
same change that builds it.

## Commands

Run from `backend/` (Python ≥3.13, managed with `uv`, `package = false`):

```bash
uv sync                          # install
cp .env.example .env             # then set the keys for the selected providers
uv run python main.py console    # talk over the local mic — spends no LiveKit minutes
uv run python main.py dev        # join a LiveKit room, reloads on save
uv run python main.py start      # production worker
```

Prefer `console` for testing. `dev`/`start` need the three `LIVEKIT_*` values
and spend from LiveKit Cloud's free tier (1,000 agent-session minutes/month).
All modes spend credits on the selected providers (ElevenLabs has a free
monthly quota; Sarvam and OpenAI are paid per use).

```bash
uv run pytest                    # offline tests: config, providers, session, boot
uv run pytest -m live            # calls the selected providers for real; spends credits
```

No linter or formatter is configured.

## Architecture

The pipeline is split so each concern lives in exactly one module:

- `main.py` — validates config *before* `cli.run_app` starts the worker
  (a `ConfigError`, unknown provider, missing key or missing `CLINIC_ID` exits
  with a one-line message, not a traceback). Each job loads the clinic
  (`context.load_clinic`, off the event loop), builds instructions, builds a
  session and starts `ClinicAgent` in the room.
- `clinic_agent/config.py` — the **only** place that reads `os.environ`.
  Frozen `Settings` dataclass; a new setting means a field, a line in
  `load_settings()`, and an entry in `.env.example`.
- `clinic_agent/session.py` — the **only** place STT + LLM + TTS are combined
  into an `AgentSession`.
- `clinic_agent/agent.py` — behaviour only: takes its instructions from the
  entrypoint; tools attach here. Speaks first via `on_enter`.
- `clinic_agent/prompts.py` — fixed persona `RULES` + `clinic_facts()` generated
  from the database per call (active doctors, grouped weekly hours, leave and
  holidays in the booking window, FAQ, current clinic time). Static facts go in
  the prompt; tools are only for changing data and actions.
- `clinic_agent/context.py` — `load_clinic(cfg)` and `clinic_now(tz)`.
- `clinic_agent/booking.py` — booking rules as plain functions over a session;
  raise `BookingError` with a caller-sayable message. `clinic_agent/tools/`
  holds the LiveKit `@function_tool` wrappers only: run the rule in
  `asyncio.to_thread`, map `BookingError` → `ToolError`. Put rules in
  `booking.py`, never in the wrapper. Tests: in-memory DB for rules; a file DB
  for tools (SQLite `:memory:` is per-thread, so threaded tools would see an
  empty database). Live evals use `mock_tools` so the LLM's tool choices are
  graded without a real clock.
- `clinic_agent/store/` — clinic data (SQLAlchemy, sync). `repo.py` holds every
  query; writes commit before returning; callers see `repo.NotFound` /
  `repo.SlotTaken`, never SQLAlchemy errors. **Only `store/` imports
  SQLAlchemy.** Double booking is prevented by a partial unique index, not by
  code. Clinic details are data (seed or dashboard), never in `.py` files.
- `dashboard/` — Streamlit clinic setup, run from `backend/` with
  `uv run streamlit run dashboard/app.py`. `app.py` → `pages/` → `sections/` (one tab per file).
  Writes only via `store/repo.py`. Styling: palette and fields in
  `.streamlit/config.toml` (Streamlit 1.64 dropped the `data-baseweb` hooks —
  use theme options, not DOM selectors); cards via `theme.card(key)`, which
  the CSS targets as `st-key-card*`. Tests drive it with
  `streamlit.testing.v1.AppTest`.
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

## Deliberate choices — don't "fix" these

- **Turn detection is `"stt"`**, set explicitly in `session.py` (omitting it
  falls back to LiveKit's own turn-detector model).
- **VAD is undecided.** LiveKit 1.8.2 attaches a local Silero VAD unless
  `vad=None` is passed, so one runs today; `test_no_local_vad` is a strict xfail
  recording that. Don't add or remove `vad=` without Harsh's decision.
- **Keep `backend/README.md` current** with every behaviour, command or setup
  change, in the same commit.
- **Raw PCM TTS output** (`linear16` for Sarvam, `pcm_24000` for ElevenLabs).
  Both plugins default to mp3; PCM avoids a decode per chunk.
- **Sarvam `TTS_SPEAKER` must be a `bulbul:v3` voice** (default `suhani`); the
  plugin rejects v2 names such as `anushka`. For ElevenLabs it is a voice ID.
- **OpenAI default is `gpt-4.1-mini`**, not the gpt-5 family: no reasoning step,
  so the first token comes fast enough for a phone call.
- **`STT_LANGUAGE=unknown`** auto-detects per utterance.
- **Hindi replies are written in Devanagari** (prompt rule). The TTS pronounces
  by script; romanised Hindi ("aap kaise hain") is read with English spelling
  rules. Don't switch the prompt or `STT_MODE` to romanised output.
- **ElevenLabs default model is `eleven_v3_conversational`**, chosen for realism
  over latency.
- Sarvam `LLM_MODEL` defaults to `sarvam-105b-conversations`; fall back to
  `sarvam-105b` if the plan lacks it.
