# Clinic Voice Agent — backend

Stage 1: you speak, it answers. LiveKit Agents handles audio and turn-taking;
Sarvam does speech-to-text, the reasoning and the voice.

No tools, no database, no booking, no telephony yet — those are later stages.

## Setup

```bash
cd backend
uv sync
cp .env.example .env
```

Put your Sarvam key in `.env`. Get one at
[dashboard.sarvam.ai](https://dashboard.sarvam.ai) — signup includes free
credits, shared across STT, LLM and TTS.

```env
SARVAM_API_KEY=sk_...
```

That is the only value `console` mode needs.

## Run

```bash
uv run python main.py console   # talk over your mic — no LiveKit minutes used
uv run python main.py dev       # join a LiveKit room, reloads on save
uv run python main.py start     # production worker
```

**Use `console` for everyday testing.** `dev` and `start` need the three
`LIVEKIT_*` values in `.env` and spend from the free tier's 1,000 agent-session
minutes per month. `console` spends none of them.

## Test

```bash
uv run pytest            # offline: config, providers, session wiring, boot errors
uv run pytest -m live    # real Sarvam calls with the .env key — spends credits
```

Offline tests prove the wiring, not the conversation. Only live tests and
real calls say whether the agent behaves well.

## How it fits together

```
main.py                 entrypoint — console | dev | start
└── clinic_agent/
    ├── config.py       every env var, read once, fails loudly at startup
    ├── prompts.py      the persona
    ├── agent.py        Agent subclass — behaviour only (tools land here)
    ├── session.py      the one place STT + LLM + TTS are combined
    └── providers/      vendor construction, behind three functions
        ├── stt.py
        ├── llm.py
        └── tts.py
```

The rule: **only `providers/` imports a vendor package.** Everything else deals
in LiveKit's own `STT`, `LLM` and `TTS` base classes.

## Swapping a component

Two steps. Nothing else in the codebase changes.

1. Add a builder to the `BUILDERS` dict in the matching provider module:

   ```python
   # clinic_agent/providers/tts.py
   def _elevenlabs(cfg: Settings) -> tts.TTS:
       return elevenlabs.TTS(voice_id=cfg.tts_speaker)

   BUILDERS = {"sarvam": _sarvam, "elevenlabs": _elevenlabs}
   ```

2. Point `.env` at it:

   ```env
   TTS_PROVIDER=elevenlabs
   ```

An unknown name fails at startup and lists what is registered.

## Configuration

Every setting is in `.env.example` with a comment. The ones worth knowing:

| Setting | Default | Why you would change it |
|---|---|---|
| `STT_LANGUAGE` | `unknown` | Auto-detects per utterance. Pin to `hi-IN` or `en-IN` only to debug. |
| `STT_MODE` | `transcribe` | Switch to `translit` if Hindi replies are mispronounced — it romanises the transcript so the model stops replying in mixed script. |
| `LLM_MODEL` | `sarvam-105b-conversations` | Tuned for multi-turn. Fall back to `sarvam-105b` if unavailable on your plan. |
| `TTS_SPEAKER` | `suhani` | Any `bulbul:v3` voice. The plugin rejects `bulbul:v2` names such as `anushka`. |
| `TTS_CODEC` | `linear16` | Raw PCM. The plugin's `mp3` default costs a decode per chunk. |
| `MIN_ENDPOINTING_DELAY` | `0.2` | Raise if it cuts you off mid-sentence, lower if replies feel slow. |

## Troubleshooting

**`403 ... invalid_api_key_error`, or `STT WebSocket session failed: 403`** —
Sarvam rejected `SARVAM_API_KEY`. Startup cannot catch this; the session dies
on the first call. Check the key directly:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://api.sarvam.ai/text-to-speech \
  -H "api-subscription-key: $(grep ^SARVAM_API_KEY= .env | cut -d= -f2-)" \
  -H "Content-Type: application/json" \
  -d '{"text":"namaste","target_language_code":"hi-IN","model":"bulbul:v3","speaker":"suhani"}'
```

`200` means the key works; `403` means get a new one from the dashboard.

**`RuntimeWarning: coroutine 'AgentServer.aclose' was never awaited` on
Ctrl+C in `console`** — harmless, and a LiveKit bug (1.8.2, the latest
release). Ctrl+C schedules the shutdown; when the worker finishes it raises
SIGTERM, whose handler schedules a second `aclose()` onto an event loop that
has already stopped. The first shutdown has completed by then. Nothing to fix
on our side.

## Notes

- **VAD — decision pending.** Sarvam's STT does its own endpointing and
  `turn_handling={"turn_detection": "stt"}` trusts it for end of turn. But
  LiveKit 1.8.2 still attaches a local Silero VAD by default unless
  `AgentSession(vad=None)` is passed, so one is running today (tracked by the
  expected-failure test `test_no_local_vad`). Keeping it gives faster barge-in;
  removing it avoids double-triggered interruptions. To be settled on a live call.
- Sarvam credits are consumption-based and shared across all three services.
  Long `console` sessions do spend them.
