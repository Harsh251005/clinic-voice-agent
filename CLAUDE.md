# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Hindi/Hinglish voice receptionist for Indian clinics. All code lives in
`backend/`: a LiveKit Agents worker with Sarvam doing STT, LLM and TTS.

Current state is **Stage 1 — a talking loop only**. No tools, database,
booking or telephony yet; those are later stages. The system prompt
(`clinic_agent/prompts.py`) explicitly forbids inventing clinic details or
booking, so update it when a stage adds real capability.

## Commands

Run from `backend/` (Python ≥3.13, managed with `uv`, `package = false`):

```bash
uv sync                          # install
cp .env.example .env             # then set SARVAM_API_KEY
uv run python main.py console    # talk over the local mic — spends no LiveKit minutes
uv run python main.py dev        # join a LiveKit room, reloads on save
uv run python main.py start      # production worker
```

Prefer `console` for testing. `dev`/`start` need the three `LIVEKIT_*` values
and spend from LiveKit Cloud's free tier (1,000 agent-session minutes/month).
All modes spend Sarvam credits, which are shared across STT, LLM and TTS.

```bash
uv run pytest                    # offline tests: config, providers, session, boot
uv run pytest -m live            # calls real Sarvam with the .env key; spends credits
```

No linter or formatter is configured.

## Architecture

The pipeline is split so each concern lives in exactly one module:

- `main.py` — validates config *before* `cli.run_app` starts the worker
  (a `ConfigError` exits with a one-line message, not a traceback), then each
  job builds a session and starts `ClinicAgent` in the room.
- `clinic_agent/config.py` — the **only** place that reads `os.environ`.
  Frozen `Settings` dataclass; a new setting means a field, a line in
  `load_settings()`, and an entry in `.env.example`.
- `clinic_agent/session.py` — the **only** place STT + LLM + TTS are combined
  into an `AgentSession`.
- `clinic_agent/agent.py` — behaviour only (persona, and `@function_tool`
  methods from Stage 2 onward). Speaks first via `on_enter`.
- `clinic_agent/providers/{stt,llm,tts}.py` — each has a `BUILDERS` registry
  mapping a name to a builder returning LiveKit's base `STT`/`LLM`/`TTS` class.

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
- **`TTS_CODEC=linear16`.** The Sarvam plugin defaults to mp3; raw PCM avoids a
  decode per chunk.
- **`TTS_SPEAKER` must be a `bulbul:v3` voice** (default `suhani`); the plugin
  rejects v2 names such as `anushka`.
- **`STT_LANGUAGE=unknown`** auto-detects per utterance. If Hindi replies come
  out mispronounced, switch `STT_MODE` to `translit` rather than pinning a
  language.
- `LLM_MODEL` defaults to `sarvam-105b-conversations`; fall back to
  `sarvam-105b` if the plan lacks it.
