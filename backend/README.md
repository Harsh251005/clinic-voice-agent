# Clinic Voice Agent — backend

Stage 1: you speak, it answers. LiveKit Agents handles audio and turn-taking.
Default testing stack: Sarvam for speech-to-text, OpenAI for the reasoning,
ElevenLabs for the voice. Sarvam can do all three — switch in `.env`.

No tools, no database, no booking, no telephony yet — those are later stages.

## Setup

```bash
cd backend
uv sync
cp .env.example .env
```

Fill in the keys for the providers selected in `.env` — only those are
checked:

| Provider | Used for | Key | Cost |
|---|---|---|---|
| Sarvam | STT (always, for now) | `SARVAM_API_KEY` from [dashboard.sarvam.ai](https://dashboard.sarvam.ai) | paid per use |
| OpenAI | LLM | `OPENAI_API_KEY` from [platform.openai.com](https://platform.openai.com/api-keys) | paid per use |
| ElevenLabs | TTS | `ELEVENLABS_API_KEY` from [elevenlabs.io](https://elevenlabs.io/app/settings/api-keys) | free monthly quota |

A missing key for a selected provider stops startup with a one-line error.

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
uv run pytest -m live    # real API calls to the selected providers — spends credits
```

Offline tests prove the wiring, not the conversation. Live tests are evals:
an LLM judge grades each reply against a stated intent (greets first, refuses
medicine, escalates chest pain, never states a fee, never confirms a booking,
answers Hinglish in Hinglish), and a TTS → STT round trip proves both halves of
the audio path. They do not measure end-to-end latency — only a spoken
`console` call does that.

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

An unknown name fails at startup and lists what is registered. Registered
today: STT `sarvam`; LLM `sarvam`, `openai`; TTS `sarvam`, `elevenlabs`.

Each builder owns its defaults and asks for its own key with
`require_key(...)`, so an unused vendor needs nothing set. Model and voice
settings left blank in `.env` get the selected provider's default — clear them
when switching, since `TTS_SPEAKER=suhani` means nothing to ElevenLabs.

## Configuration

Every setting is in `.env.example` with a comment. The ones worth knowing:

| Setting | Default | Why you would change it |
|---|---|---|
| `STT_LANGUAGE` | `unknown` | Auto-detects per utterance. Pin to `hi-IN` or `en-IN` only to debug. |
| `STT_MODE` | `transcribe` | `transcribe` returns Hindi in Devanagari, which matches the prompt's rule that Hindi replies are written in Devanagari — the script the voice engine pronounces correctly. |
| `LLM_MODEL` | provider's | OpenAI: `gpt-4.1-mini` — no reasoning step, so replies start fast. Sarvam: `sarvam-105b-conversations` (fall back to `sarvam-105b`). |
| `TTS_MODEL` | provider's | ElevenLabs: `eleven_v3_conversational`, the most expressive; use `eleven_multilingual_v2` if your plan rejects it, or `eleven_flash_v2_5` for the lowest latency. Sarvam: `bulbul:v3`. |
| `TTS_SPEAKER` | provider's | ElevenLabs: a voice ID. The plugin default is not a Hindi voice — pick one in ElevenLabs → Voices → Voice Library (language Hindi, accent Indian), add it to My Voices, copy its ID. Sarvam: any `bulbul:v3` voice, default `suhani`; v2 names such as `anushka` are rejected. |
| `TTS_CODEC` | provider's | Raw PCM for both (`pcm_24000` / `linear16`) — compressed formats cost a decode per chunk. |
| `TTS_LANGUAGE` | provider's | ElevenLabs auto-detects, which suits mixed Hindi/English; Sarvam defaults to `en-IN`. |
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
- **`console`/`dev` do not behave exactly like `start`.** With a VAD present,
  LiveKit turns on *adaptive interruption detection* in console and dev mode —
  a LiveKit Cloud model, called with `LIVEKIT_API_KEY` — and turns it off by
  default under `start`. So interruptions you test locally are handled by a
  model production does not run.
- Sarvam credits are consumption-based and shared across STT, LLM and TTS.
  With the default testing stack only STT spends them — every second the
  mic is open in `console`.
