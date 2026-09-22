# Clinic Voice Agent — backend

Stage 1: you speak, it answers. LiveKit Agents handles audio and turn-taking.
Default testing stack: Sarvam for speech-to-text, OpenAI for the reasoning,
ElevenLabs for the voice. Sarvam can do all three — switch in `.env`.

Stage 2: the agent answers from each clinic's own data, books appointments
and hangs up when the caller is done; clinic staff set everything up and see
bookings in a Streamlit dashboard. No telephony yet.

## Setup

```bash
cd backend
uv sync
cp .env.example .env
```

Fill in the keys for the providers selected in `.env` — only those are
checked. Two vendors are allowed per part, and nothing else:

| Part | Sarvam (production, the default) | Alternative |
|---|---|---|
| STT | `sarvam` | `elevenlabs` |
| LLM | `sarvam` | `openai` |
| TTS | `sarvam` | `elevenlabs` |

A blank `*_PROVIDER` means Sarvam. The `.env.example` stack is the current
testing one (ElevenLabs STT + OpenAI + ElevenLabs TTS), chosen to save Sarvam
credits. Switching any part is one line in `.env`.

| Provider | Key | Cost |
|---|---|---|
| Sarvam | `SARVAM_API_KEY` from [dashboard.sarvam.ai](https://dashboard.sarvam.ai) | paid per use |
| OpenAI | `OPENAI_API_KEY` from [platform.openai.com](https://platform.openai.com/api-keys) | paid per use |
| ElevenLabs | `ELEVENLABS_API_KEY` from [elevenlabs.io](https://elevenlabs.io/app/settings/api-keys) | free monthly quota |

A missing key for a selected provider stops startup with a one-line error.

Create the database schema, then a fictional demo clinic (real clinics are
set up through the dashboard):

```bash
uv run python -m clinic_agent.store.migrations   # schema at the latest revision
uv run python -m seeds.demo_clinic               # writes data/clinic.db (gitignored)
```

Run the migrations command again after every pull that changes the schema.
The agent and dashboard refuse to start on an old schema and print that
command.

## Run

```bash
uv run python main.py console   # talk over your mic — no LiveKit minutes used
uv run python main.py console --text   # type instead: LLM only, no STT/TTS cost
uv run python main.py console --clinic 2   # which clinic, when there are several
uv run python main.py dev       # join LiveKit rooms it is dispatched to, reloads on save
uv run python main.py start     # production worker
```

**One worker answers for every clinic.** It registers as
`clinic-receptionist` (explicit dispatch), so it joins only rooms it is
dispatched to, and each dispatch carries the clinic in its metadata:
`{"clinic_id": 2}`. The format lives in `clinic_agent/dispatch.py`, and
anything that starts a call (the browser call link, later a phone number)
uses it. A call that names no clinic, or an unknown one, is refused (logged,
job ended): the agent never answers as a guessed clinic. `console` has no
dispatch, so it takes `--clinic <id>` or uses the only clinic in the
database. `--clinic` is console-only: `dev` behaves like `start`.

**Use `console --text` for testing conversations, tools and bookings.** It
builds no speech providers at all, so it spends only LLM tokens and needs no
Sarvam or ElevenLabs key; bookings it makes are real rows in the database.
Use plain `console` when you need to hear the voice.

**`console` spends no LiveKit minutes.** `dev` and `start` need the three
`LIVEKIT_*` values in `.env` and spend from the free tier's 1,000 agent-session
minutes per month. `console` spends none of them.

## Call links (browser calls)

Until there are phone numbers, patients reach the receptionist through a link
per clinic, shown on the dashboard's **Call link** tab:
`PUBLIC_BASE_URL/call/<link name>`. It needs the worker running (`dev` or
`start`) and the link server:

```bash
uv run python -m api     # serves /call/<link name> on API_HOST:API_PORT (default 127.0.0.1:8080)
```

1. The patient opens the link. The page shows the clinic and a call button.
2. Tapping it asks the server for a **join pass**. The server looks the
   clinic up by its link name and signs a short-lived LiveKit token for a new
   private room (`call-<link name>-<random>`). The token lets the caller
   publish only a microphone, allows 2 participants (caller + receptionist),
   and dispatches `clinic-receptionist` with `{"clinic_id": N}`. The
   signature is made with `LIVEKIT_API_SECRET`, so a caller can't change the
   clinic.
3. The browser joins with the pass, and LiveKit sends the receptionist in for
   that clinic. If it hasn't joined within 20 s, the page says so.

Limits against a shared or leaked link: 5 calls per caller per 10 minutes and
30 per clinic per hour (`api/app.py`, in memory). Behind a tunnel or proxy
every request looks like `127.0.0.1`, so set `CLIENT_IP_HEADER`
(`CF-Connecting-IP` for Cloudflare Tunnel), otherwise all patients share one
limit. The page pins the LiveKit client version with an integrity hash, and a
strict Content-Security-Policy only allows our own origin and our LiveKit
project.

To let someone outside your machine call (a demo, a pilot), expose port 8080
with a tunnel and set `PUBLIC_BASE_URL` to its https address. Browsers
only allow the microphone on https or `localhost`.

## Dashboard API (for the Next.js dashboard)

The same server (`uv run python -m api`) serves the dashboard's JSON API
under `/api`. The Next.js dashboard (being built, Stage 3b) is only
screens; every rule and access check lives here, in `api/dashboard/`, and
in `repo.py`.

- **Sign-in:** Google, via `/api/auth/login` → Google →
  `/api/auth/callback`. Only a verified email is kept, in a signed session
  cookie (`clinic_console`: httpOnly, SameSite=Lax, Secure on https, 12
  hours). Settings: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
  `SESSION_SECRET`, `DASHBOARD_URL`. Google's redirect URI is
  `DASHBOARD_URL/api/auth/callback`.
- **Access** is re-read from the database on every request, so removing
  someone takes effect at once. Admins (`ADMIN_EMAILS`) see every clinic;
  members see theirs; another clinic's URL is a 404.
- **Every row id is checked against the clinic in the URL**
  (`repo.in_clinic`). Without it, a member of one clinic could change
  another's data by guessing ids. `tests/test_dashboard_api.py` attacks
  every kind of row; it fails if the check is removed (verified).
- **CSRF:** changes must send the header `x-clinic-console: 1`, which a
  cross-site form can't; reading doesn't need it.
- Rule violations come back as 422 with a message staff can read (bad link
  name, overlapping sittings); rows outside the clinic as 404.

## Dashboard (Streamlit, being replaced)

Two pages for clinic staff:

- **Appointments** (the landing page) — one day at a time, grouped by doctor,
  each tagged *Call* (booked by the agent) or *Staff*. Counters for the day,
  bookings from calls, and the next seven days. Cancelling takes two clicks
  (Cancel → Yes, cancel); cancelled slots become bookable again. Lists page
  at 25 rows.
- **Clinic setup** — details, booking rules, doctors, weekly hours (split
  shifts), leave and holidays, and FAQ answers. Everything the agent knows
  about a clinic is entered here.
- **A new doctor starts with hours**, not an empty week: *Starting hours* on
  the add form defaults to Mon–Sat, 10 am–1 pm and 5–8 pm (or another
  pattern, a colleague's hours, or none). They are bookable at once, so the
  confirmation says to check them.
- **Weekly hours** is one row per day: an *Open* switch, a sitting, and an
  optional second sitting. *Fill the week* applies a pattern or a colleague's
  week, and *Copy Monday to all open days* fills the rest. Nothing is saved
  until *Save hours*: an *Unsaved changes* badge shows, and *Discard
  changes* reverts. A preview shows exactly how the receptionist will
  describe the hours. Overlapping sittings are refused, by the form and by
  `repo.set_doctor_hours`. Patterns live in `dashboard/schedules.py`.

```bash
uv run streamlit run dashboard/app.py   # run from backend/ — .streamlit/ lives here
```

- It writes through `store/repo.py`, the same functions the agent uses.
- Doctors are deactivated, never deleted, so appointment history survives.
- **Sign-in is with Google.** Admins (`ADMIN_EMAILS`) see every clinic,
  create clinics (**New clinic** in the sidebar) and, on each clinic's
  **Team** tab, add or remove the Google accounts that may open it. Everyone
  else sees only the clinics their email was added to. A signed-in account
  that no clinic added gets a "No clinic yet" screen. Adding someone sends
  no email: give them the dashboard's address yourself.
- `DASHBOARD_LOGIN=off` skips sign-in and makes everyone an admin, with a
  warning in the sidebar. Local development only.
- Views live in `dashboard/views/`, **never `pages/`**: Streamlit auto-lists
  a `pages/` folder whenever `app.py` stops at the sign-in gate, and runs
  those files without the gate. A test fails if one appears.
- After editing anything under `dashboard/`, restart Streamlit; it does not
  reliably hot-reload imported modules.

### Setting up Google sign-in

Once per deployment, in the Google account that will own the login (about
ten minutes):

1. [console.cloud.google.com](https://console.cloud.google.com) → create a
   project (e.g. "Clinic Console").
2. **Google Auth Platform** → **Branding**: app name and a support email.
   **Audience**: *External*. While the app is in *Testing*, only the Google
   accounts listed under **Test users** can sign in (up to 100): add yours and
   each clinic's. Publishing the app removes that list.
3. **Clients** → **Create client** → *Web application*. Under **Authorized
   redirect URIs** add `http://localhost:8501/oauth2callback` (and later
   `https://<dashboard address>/oauth2callback`). Copy the client ID and
   secret.
4. `cp .streamlit/secrets.toml.example .streamlit/secrets.toml` (gitignored),
   fill in `client_id`, `client_secret`, and a `cookie_secret` from
   `uv run python -c "import secrets; print(secrets.token_hex(32))"`.
5. In `.env`: `DASHBOARD_LOGIN=google` and `ADMIN_EMAILS=<your Google email>`.
   Restart Streamlit.

Google's console moves things around; if a name above has changed, the
client type is still "OAuth client ID, Web application".

## Test

```bash
uv run pytest            # offline: config, providers, session, boot, store, scheduling, dashboard
uv run pytest -m live    # real OpenAI + ElevenLabs calls — spends credits, never Sarvam's

# every database test against Postgres as well (wiped per test: never real data)
TEST_POSTGRES_URL=postgresql+psycopg://clinic:clinic-dev@127.0.0.1:5433/clinic_test uv run pytest
```

Live tests always use the testing stack (ElevenLabs STT + OpenAI + ElevenLabs
TTS, each with its default model and voice), whatever `.env` selects. Only the
two keys come from `.env`. Nothing tests the Sarvam path automatically; check
it by hand before a production release.

Offline tests prove the wiring, not the conversation. Live tests are evals:
an LLM judge grades each reply against a stated intent (greets first, refuses
medicine, escalates chest pain, never states a fee, never confirms a booking,
answers Hinglish in Hinglish), and a TTS → STT round trip, streamed as a call
streams it, proves both halves of the audio path. They do not measure end-to-end latency — only a spoken
`console` call does that.

## How it fits together

```
main.py                 entrypoint — console | dev | start
api/                    call-link server: page + signed join pass (python -m api)
├── app.py              routes, rate limits, security headers
├── passes.py           the LiveKit join pass: room, grants, clinic dispatch
├── limits.py           in-memory rate limiter
├── templates/ static/  the call page (no build step; LiveKit client from a pinned CDN)
└── clinic_agent/
    ├── config.py       every env var, read once, fails loudly at startup
    ├── prompts.py      persona rules + clinic facts built from the database per call
    ├── context.py      loads the call's clinic and its local time
    ├── dispatch.py     which clinic a call is for: the agent name + metadata format
    ├── call_limit.py   hard cap on call length: goodbye, then close the room
    ├── booking.py      booking rules: find slots, validate, book — no LiveKit
    ├── tools/booking.py  slots, book, find/cancel/reschedule as LiveKit tools
    ├── tools/call.py     end_call — LiveKit's EndCallTool, goodbye then hang up
    ├── agent.py        Agent subclass — behaviour only (tools land here)
    ├── session.py      the one place STT + LLM + TTS are combined
    ├── providers/      vendor construction, behind three functions
    │   ├── stt.py
    │   ├── llm.py
    │   └── tts.py
    └── store/          clinic data — the only package that imports SQLAlchemy
        ├── db.py       engine + sessions from DATABASE_URL
        ├── migrations.py  schema upgrades (Alembic); `python -m` runs them
        ├── alembic/    revisions, one file per schema change
        ├── models.py   clinics, FAQ, doctors, hours, time off, patients, appointments
        └── repo.py     every query the agent and dashboard make
    scheduling.py       free-slot rules — pure functions, no DB, no LiveKit
seeds/demo_clinic.py    fictional clinic for tests and a first run
dashboard/              Streamlit clinic setup (app.py → views/ → sections/, one section per file)
```

The rules: **only `providers/` imports a vendor package**, and **only `store/`
imports SQLAlchemy** (or Alembic). Everything else deals in LiveKit's base
classes and in `repo` functions; type hints use `Session` / `Sessions` from
`store/db.py`. `tests/test_boundaries.py` fails the build if either rule breaks.

## Clinic data

Clinic details are data, never code: the agent and the dashboard read and
write the same tables through `store/repo.py`.

- **What the agent knows**: at the start of every call it loads the clinic
  and writes its facts into the instructions — name, address, phone, active
  doctors with fees and weekly hours, leave and holidays inside the booking
  window, FAQ answers, and the clinic's current date and time. Anything not
  there, it says it doesn't know. Edits in the dashboard apply from the next call.
- **Booking** (two tools, rules in `booking.py`):
  - `find_available_slots(date, doctor?, part_of_day?)` returns up to the
    clinic's "slots offered" per doctor. With nothing free it says why (clinic
    closed, doctor on leave, doesn't sit that day, fully booked) and gives the
    next free day.
  - `book_appointment(...)` refuses unless `caller_confirmed` is true, which
    the instructions tie to reading every detail back first. It re-checks the
    slot, validates a 10-digit Indian mobile (+91 / 0 / spaces accepted), and
    turns a lost race into "just taken — offer these instead".
  - Database work runs in a worker thread so a slow query never stalls audio.
    Tool errors reach the LLM as plain sentences it can relay.
- **Cancelling and moving** (three more tools): `find_my_appointments` looks
  bookings up by the mobile number they were made with; `cancel_appointment`
  and `reschedule_appointment` act only on the caller's own upcoming booking
  and only with `caller_confirmed` after a read-back. A move is one database
  update: the appointment keeps its number, and the double-booking index
  still refuses a taken slot, so it is never half-moved. A wrong number, an
  unknown id and another clinic's id all get the same answer, so guessing
  reveals nothing. **The mobile number is the only proof of identity today** —
  once telephony arrives, match it against the caller's own number.
- **Ending the call**: `end_call` (LiveKit's `EndCallTool`) speaks one
  goodbye, shuts the session down after it, and deletes the room — which
  disconnects a phone caller. It is hidden during the greeting, and the
  instructions say to ask "anything else?" when unsure rather than hang up.
- **It says it is automated.** The first line names the clinic and says it
  is the clinic's automated assistant ("ऑटोमेटेड असिस्टेंट" in Hindi). The
  call page says so too.
- **Calls have a time limit** (`MAX_CALL_MINUTES`, default 10). At the limit
  the receptionist apologises, says goodbye (it can't be interrupted), and
  closes the room, which disconnects the caller.
- **`console` refuses to start** if its clinic isn't in the database (or there
  are several and no `--clinic`), naming the fix.

- **Double booking is impossible at the database level** — a partial unique
  index on (doctor, start time) for booked appointments. A second booking
  raises `repo.SlotTaken`; a cancelled slot can be rebooked.
- **Split shifts** are several `doctor_hours` rows for one weekday (e.g.
  10–1 and 5–8). **Time off** with no doctor is a whole-clinic holiday.
- **Each clinic has a link name** (`slug`, e.g. `sharma-skin-clinic`), made
  from its name when created, `-2`, `-3` if taken, and editable on the
  dashboard's **Call link** tab. Its call link is `PUBLIC_BASE_URL/call/<slug>`.
  Patients see the slug, never the database id. Renaming it breaks the old
  link.
- **A patient is a phone number plus a name**, so one phone can hold a whole
  family (a parent booking for their children). The same name in another
  case is the same person; a new name is a new person, never a rename.
- **Free slots** (`scheduling.py`): a slot must fit inside a sitting, not
  overlap any booking (ranges, so changing slot length stays safe), and start
  at least 30 minutes from now. Days in the past or beyond the clinic's
  booking window (default 30 days) are refused with a reason the agent can say.
- Appointment times are stored naive, in the clinic's timezone
  (`Asia/Kolkata`). Record-keeping timestamps (`created_at`) are naive UTC, so
  they don't depend on the server's clock. Rows made before 2026-09-22 hold
  India time there.
- **Schema changes go through Alembic** (`store/alembic/versions/`).
  `uv run python -m clinic_agent.store.migrations` is the only thing that
  changes a schema. The agent and dashboard only check it, so two processes
  never migrate one database at once. On Postgres an advisory lock makes a
  second concurrent upgrade wait. SQLite files are backed up first as
  `clinic.db.bak-<time>`.
- After changing `models.py`, write a revision, read it, and commit it:
  `uv run alembic revision --autogenerate --rev-id 0002 -m "what changed"`.
- SQLite changes a table by copying it and dropping the original, and a
  drop with foreign keys on cascades (rebuilding `clinics` would delete every
  doctor and appointment). So the migrations command turns foreign keys off
  while revisions run, runs `PRAGMA foreign_key_check` before committing, and
  turns them back on. Keep it that way.
- `tests/test_migrations.py::test_models_and_migrations_agree` fails when
  `models.py` changes without a revision.
- A database made before Alembic (by Stage 2's `create_all`) is adopted at
  revision `0001`, but only if its schema matches the baseline exactly;
  anything else is refused and left untouched.

### Postgres

Production uses Postgres, and dev can too: set `DATABASE_URL` and run the
migrations command. No code changes. A local one for development and tests:

```bash
podman run -d --name clinic-pg -e POSTGRES_USER=clinic -e POSTGRES_PASSWORD=clinic-dev \
  -e POSTGRES_DB=clinic -p 127.0.0.1:5433:5432 docker.io/library/postgres:17-alpine
podman exec clinic-pg psql -U clinic -c "create database clinic_test"
# DATABASE_URL=postgresql+psycopg://clinic:clinic-dev@127.0.0.1:5433/clinic
```

(`docker` works the same.) Double booking is still refused by the database
itself: the partial unique index exists on both engines, and the tests
prove it on both.

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

An unknown name fails at startup and lists what is registered. Registered:
STT `sarvam`, `elevenlabs`; LLM `sarvam`, `openai`; TTS `sarvam`, `elevenlabs`.
That list is deliberate: no other vendors (a test enforces it).

Each builder owns its defaults and asks for its own key with
`require_key(...)`, so an unused vendor needs nothing set. Model and voice
settings left blank in `.env` get the selected provider's default. Leave them
blank and switching is just the `*_PROVIDER` line; a value you set is
vendor-specific (`TTS_SPEAKER=suhani` means nothing to ElevenLabs), so clear it
when switching. `STT_LANGUAGE=unknown` is the one exception: it works for
both (auto-detect on Sarvam, Hindi on ElevenLabs).

## Configuration

Every setting is in `.env.example` with a comment. The ones worth knowing:

| Setting | Default | Why you would change it |
|---|---|---|
| `STT_MODEL` | provider's | Sarvam: `saaras:v4`. ElevenLabs: `scribe_v2_realtime`, its only streaming model; turn detection needs a streaming STT, so keep it. |
| `STT_LANGUAGE` | provider's | Sarvam: `unknown` auto-detects per utterance. ElevenLabs: always `hi` when blank or `unknown`. Its auto-detect locks onto the wrong language during the greeting's silence (Cyrillic, Chinese) and then commits empty transcripts, so the agent never hears the caller. Pinned `hi` still transcribes English as English and Hinglish as Hinglish. |
| `STT_MODE` | `transcribe` | Sarvam only. `transcribe` returns Hindi in Devanagari, which matches the prompt's rule that Hindi replies are written in Devanagari — the script the voice engine pronounces correctly. |
| `LLM_MODEL` | provider's | OpenAI: `gpt-4.1-mini` — no reasoning step, so replies start fast. Reasoning models (`gpt-5*`, `o*`) work too: the builder sets `reasoning_effort="none"`, which OpenAI requires for tools on Chat Completions. Sarvam: `sarvam-105b-conversations` (fall back to `sarvam-105b`). |
| `TTS_MODEL` | provider's | ElevenLabs: `eleven_v3_conversational`, the most expressive; use `eleven_multilingual_v2` if your plan rejects it, or `eleven_flash_v2_5` for the lowest latency. Sarvam: `bulbul:v3`. |
| `TTS_SPEAKER` | provider's | ElevenLabs: a voice ID. The plugin default is not a Hindi voice — pick one in ElevenLabs → Voices → Voice Library (language Hindi, accent Indian), add it to My Voices, copy its ID. Sarvam: any `bulbul:v3` voice, default `suhani`; v2 names such as `anushka` are rejected. |
| `TTS_CODEC` | provider's | Raw PCM for both (`pcm_24000` / `linear16`) — compressed formats cost a decode per chunk. |
| `TTS_LANGUAGE` | provider's | ElevenLabs auto-detects, which suits mixed Hindi/English; Sarvam defaults to `en-IN`. |
| `DATABASE_URL` | `sqlite:///data/clinic.db` | `postgresql+psycopg://user:pass@host:port/db` for production. Run the migrations command after changing it. |
| `PUBLIC_BASE_URL` | `http://localhost:8080` | Where the call-link server is reachable; the dashboard builds each clinic's link from it. Your tunnel's https address for a demo from outside. |
| `MAX_CALL_MINUTES` | `10` | Longest a call may last before a goodbye and hang-up. Guards against forgotten or abused calls spending minutes. |
| `DASHBOARD_LOGIN` | `google` | `off` skips sign-in (everyone is an admin): local development only. |
| `ADMIN_EMAILS` | blank | Comma-separated Google emails that see every clinic and manage access. |
| `API_HOST` / `API_PORT` | `127.0.0.1` / `8080` | Where the call-link server listens. `0.0.0.0` inside a container. |
| `CLIENT_IP_HEADER` | blank | The header carrying the caller's IP behind a tunnel/proxy (`CF-Connecting-IP`, `X-Forwarded-For`), so rate limits stay per caller. Never trusted unless set. |
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
  The testing stack spends none of them.
- **ElevenLabs STT ends a turn after 1.5 s of silence** (its server-side
  default), slower than Sarvam. Expected on the testing stack; production is
  Sarvam. It must run with `server_vad` (commit on silence): in its default
  manual-commit mode a sentence is only finalised when the stream is
  flushed, which LiveKit never does on a live call. The agent greeted and
  then never heard a word.
- **The live speech test feeds audio like a call**: real time, faint room
  noise first, stream left open. The old instant, silent, stream-ending
  version passed with both ElevenLabs bugs present.
