# Clinic Voice Agent — backend

A Hindi/Hinglish voice receptionist for Indian clinics. A caller talks to it
from a browser link (no phone numbers yet); it answers from the clinic's own
data, books, moves and cancels appointments, and hangs up when the caller is
done. Clinic staff run their day in the dashboard (Next.js, `../frontend/`,
over the API here); the operator watches every clinic from its admin panel.

LiveKit Agents handles the audio and turn-taking. Every call is in Hindi:
Sarvam hears and speaks, and the language model is Sarvam's or, to compare
the two, OpenAI's (`HINDI_LLM` in `.env`).

## Setup

```bash
cd backend
uv sync
cp .env.example .env
```

**One language line: Hindi** (2026-11-08: Hindi first, made reliable
before anything else). Set in `clinic_agent/lines.py`:

| Line | STT | LLM | TTS |
|---|---|---|---|
| Hindi | Sarvam | `HINDI_LLM`: `sarvam` (default) or `openai` | Sarvam |

`HINDI_LLM=openai` swaps only the brain, to compare OpenAI's replies with
Sarvam's on the same voice; restart the worker after changing it. A missing
key for the line stops the worker with a one-line error. Settings that no
longer do anything are refused at startup, named so you can remove them:
the old `STT_PROVIDER` / `LLM_PROVIDER` / `TTS_PROVIDER` lines, and any line
left over from the removed English line's vendor (blank ones are harmless).

| Provider | Key | Cost |
|---|---|---|
| Sarvam | `SARVAM_API_KEY` from [dashboard.sarvam.ai](https://dashboard.sarvam.ai) | paid per use |
| OpenAI | `OPENAI_API_KEY` from [platform.openai.com](https://platform.openai.com/api-keys) | paid per use; needed for `HINDI_LLM=openai`, the live tests and Hindi name suggestions |

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
uv run python main.py dev       # join LiveKit rooms it is dispatched to; restart it after a code change
uv run python main.py start     # production worker
```

**One worker answers for every clinic.** It registers as
`clinic-receptionist` (explicit dispatch; set through `LIVEKIT_AGENT_NAME`
at boot, not `livekit.toml`, which `dev` ignores), so it joins only rooms it is
dispatched to, and each dispatch carries the clinic and the call's
language in its metadata: `{"clinic_id": 2, "language": "hi"}` (Hindi is
the only one; the field stays so a second line later is one more entry). The format lives in `clinic_agent/dispatch.py`, and anything that
starts a call (the browser call link, later a phone number) uses it. A call
that names no clinic, an unknown one, or no known language is refused
(logged, job ended): the agent never answers on a guess. `console` has no
dispatch, so it takes `--clinic <id>` (or uses the only clinic in the
database), console-only: `dev` behaves like `start`. The old `--language`
flag is refused with a one-line message.

**Use `console --text` for testing conversations, tools and bookings.** It
builds no speech providers at all, so it spends only LLM tokens and needs
only the brain's key; bookings it makes are real rows in the database.
Use plain `console` when you need to hear the voice.

**`console` spends no LiveKit minutes.** `dev` and `start` need the three
`LIVEKIT_*` values in `.env` and spend from the free tier's 1,000 agent-session
minutes per month. `console` spends none of them.

## Docker

`docker compose up --build` (repo root) runs Postgres, the API on :8080
and the dashboard on :3000. A one-shot `setup` container brings the schema
up to date and, into an empty database only, seeds the fictional demo
clinic (`seeds.demo_clinic --if-empty`) and a lived-in day
(`seeds.demo_day`: today's bookings, visit marks, leave, a holiday, two
calls with transcripts, all relative to now). `--profile voice` adds the
agent worker, which needs `LIVEKIT_*` and the vendor keys in
`backend/.env`. That file overrides the placeholders in `compose.demo.env`,
which exist only so the dashboard starts with no keys at all.

- One image (`backend/Dockerfile`, uv + Python 3.13, non-root) runs as
  the API, the worker or the migrations, by command. The dashboard image
  (`frontend/Dockerfile`) serves Next's standalone build, with `/api`
  forwarded to `http://api:8080`, fixed at build time.
- **Sign-in is off in this stack** (`DASHBOARD_LOGIN=off`): it's for
  running on your own machine. A server deployment also needs Google
  sign-in, HTTPS (Caddy) and real secrets: that's the deploy slice, not
  this file.
- `.dockerignore` keeps `.env`, `data/` and the tests out of the image.

## Call links (browser calls)

Until there are phone numbers, patients reach the receptionist through a link
per clinic, shown on the dashboard's **Receptionist link** tab:
`PUBLIC_BASE_URL/call/<link name>`. It needs the worker running (`dev` or
`start`) and the link server:

```bash
uv run python -m api     # serves /call/<link name> on API_HOST:API_PORT (default 127.0.0.1:8080)
```

1. The patient opens the link. The page shows the clinic, "Call in Hindi"
   and a call button: there is no language to choose.
2. Tapping it asks the server for a **join pass**. The server looks the
   clinic up by its link name and signs a short-lived LiveKit token for a new
   private room (`call-<link name>-<random>`). The token lets the caller
   publish only a microphone, allows 2 participants (caller + receptionist),
   and dispatches `clinic-receptionist` with `{"clinic_id": N, "language":
   "hi"}`. The request needs no body (one from an old tab is ignored: its
   caller still gets a Hindi call); if the live worker can't answer Hindi
   it gets a 503. The page's
   CSS and script URLs carry a content hash, so a returning patient never
   gets a cached old copy after an update. The signature is made with
   `LIVEKIT_API_SECRET`, so a caller can't change the clinic.
3. The browser joins with the pass, and LiveKit sends the receptionist in for
   that clinic. If it hasn't joined within 20 s, the page says so.

**If the page gives up, it says why and tells us.** Microphone blocked, no
microphone, couldn't connect, the receptionist didn't answer within 20 s,
or the line dropped mid-call: the page shows the patient what to do and
posts a fixed reason code to `POST /call/<link name>/report` (JSON only,
rate-limited, nothing about the patient). The clinic and the admin panel
see it as a problem (see *Problems*). A dropped line no longer says "Call
ended. Thank you!". `GET /healthz/worker` says whether a receptionist is
connected.

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
under `/api`. The Next.js dashboard (`../frontend/`, see its README) is only
screens; every rule and access check lives here, in `api/dashboard/`, and
in `repo.py`.

- **Sign-in:** Google, via `/api/auth/login` → Google →
  `/api/auth/callback`. Only a verified email is kept, in a signed session
  cookie (`clinic_console`: httpOnly, SameSite=Lax, Secure on https, 12
  hours). Settings: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
  `SESSION_SECRET`, `DASHBOARD_URL`. Google's redirect URI is
  `DASHBOARD_URL/api/auth/callback`.
- **Access** is re-read from the database on every request, so removing
  someone takes effect at once. Admins (`ADMIN_EMAILS`) open every clinic's
  settings; members open theirs; another clinic's URL is a 404. **Patient
  data (appointments and calls) is for members only**
  (`access.clinic_staff`): an admin who isn't on a clinic's team gets a 403
  there, even though they can set it up. `/api/me` marks each clinic `staff`.
- **Every row id is checked against the clinic in the URL**
  (`repo.in_clinic`). Without it, a member of one clinic could change
  another's data by guessing ids. `tests/test_dashboard_api.py` attacks
  every kind of row; it fails if the check is removed (verified).
- **CSRF:** changes must send the header `x-clinic-console: 1`, which a
  cross-site form can't; reading doesn't need it.
- Rule violations come back as 422 with a message staff can read (bad link
  name, overlapping sittings); rows outside the clinic as 404.

### Sounding like a person (Hindi first)

- **Everyday spoken Hindi**, not written Hindi: the Hindi rules name the
  common words to use and the bookish ones to avoid ("कृपया", "विवरण",
  "उपलब्ध"…), start replies with a short "जी" / "अच्छा", never repeat a
  confirmed detail, and use no dashes, semicolons or brackets (the voice
  reads them oddly). The English rules share the last three.
- **Doctors by first name:** the receptionist says "डॉक्टर हर्ष", never the
  full name unless the caller asks for it (also in the booking read-back). A
  one-word name stays as it is; two doctors with the same first name both
  keep their full names.
- **Names said one way:** the clinic and each doctor have a *Name in Hindi*
  (Devanagari), **filled in from the English name** as staff type
  (`POST /api/clinics/{id}/hindi-name`: one short OpenAI text request,
  `gpt-4.1-mini`, `clinic_agent/providers/hindi.py`), reusing words the
  clinic already spells so a surname comes out the same everywhere. Staff
  can change it; their own text is never overwritten. Saving with the box
  blank fills it in the same way. A failed suggestion never blocks a save
  (the Hindi line then spells the name itself) and raises the admin's
  `hindi_names_failing` problem. The Hindi line says the name exactly as written.

### Test calls (staff calling their own receptionist)

Staff call their own receptionist from the dashboard, in Hindi, exactly as
a patient would: `POST /api/clinics/{id}/calls/test` (no body, staff only;
409 if the live worker can't answer Hindi) returns a LiveKit pass for a `test-<link name>-…` room whose
dispatch is marked `"test": true`. **It is a real call**: it books, moves
and cancels for real, and is recorded like any other. It is marked as a
test (`calls.test`, rev 0010) and kept out of the clinic's call counts and
problems, but not the LiveKit minutes it spends.

`GET …/calls/by-room/{room}` finds it once the worker has answered.
`DELETE …/calls/{id}` **erases** a finished test call: every change it made
is undone, newest first (a booking deleted, with its patient if they have
no other appointment; a cancellation put back; a move returned to where it
was, which each move now records), then the call, its trace and its
transcript are deleted. All or nothing: if an undo needs a slot someone
has booked since, it says which and nothing changes. A patient's call can
never be erased, and a test call can't be while it's still going.
`GET …/calls/tests` counts the clinic's test calls on record, and
`DELETE …/calls/tests` erases every finished one at once, newest first
(a later test call may have moved what an earlier one booked), in one
transaction: all or none. The Talk to receptionist tab shows "N test calls
on record" with that button whenever there are any.

## Admin panel (the operator)

`/admin` in the dashboard, for `ADMIN_EMAILS` only (`/api/admin/*`,
`api/dashboard/admin.py`). It answers "is the receptionist working, for
every clinic?" and never shows patients:

- **Health**: calls and how they ended, dropped calls (a record the worker
  never finished, past `MAX_CALL_MINUTES` + 2 minutes), calls with vendor
  errors, typical (p50) and slow (p95) time for each step per vendor stack
  (hearing, end of turn, thinking, voice, the caller's whole wait), vendor
  errors, and a "needs a look" list (dropped or failed calls, erroring
  vendors, an active clinic with no calls for 3 days).
- **Calls**: every call to every clinic, filterable; each opens to its
  trace (every step, tool and error in order, how it ended, which
  appointments it changed by number). **Its words are hidden.** "Open for
  debugging" asks for a reason, logs it (`transcript_access`) and only then
  shows the transcript; the clinic's Calls page shows it was opened by
  ClinicDesk support, when and why (not the operator's email).
- **Errors**: vendor errors grouped by vendor and type, linked to their calls.
- **Clinics**: add one, see its calls, manage its team (moved here from
  clinic settings), **pause** it (the call page says it isn't taking calls,
  the pass endpoint and the worker refuse its calls; data untouched), and
  **delete** it: only once paused and with its exact name typed; removes
  everything of it. A SQLite database is copied first
  (`clinic.db.bak-…`); on Postgres that relies on your own backups.
- **Costs**: what every call cost you, in rupees (below).
- **Admins** (bottom of `/admin/clinics`, `GET /api/admin/admins`): who has
  admin access, **read-only on purpose** (Harsh, 2026-11-10). Admins are only
  `ADMIN_EMAILS` in the server's `.env` (comma-separated, any number; restart
  the API), so nobody can make themselves admin from the dashboard or the
  database. An admin sees every clinic, including transcripts (each opening
  is logged).
- **Receptionist** (`/admin/receptionist`, `api/dashboard/receptionist.py`):
  how she behaves on every clinic's calls. The main rules (editable, a
  live word count, at most 500 words, **Reset to default**; blank = the
  rules in `prompts.py`, so code updates still reach it; an edited text is
  marked, because the live evals only grade the default), the brain
  (vendor, Sarvam and OpenAI model names), hearing and voice model (a blank
  field shows what it falls back to), the turn-taking timings with their
  ranges, and whether callers can talk over the greeting. Saved changes
  apply from the next call. Admins only.
- **A clinic's Receptionist tab** (Clinic settings, admins only;
  `/api/admin/clinics/{id}/receptionist`): its own instructions (added after
  the main rules, at most 150 words: every word is sent on every turn),
  directions (said when a caller asks the way, instead of the postal
  address), its voice (speaker, live speed, pitch) and longest call. Before a
  voice change is saved, it says how many of the clinic's recorded lines the
  new voice leaves said live (`GET /api/admin/voice/impact`).
- **Voice & phrases** (`/admin/voice`, `api/dashboard/voice.py`): the
  receptionist's fixed lines: the greeting (shared, with `{clinic}` for each
  clinic's spoken name, or a clinic's own), the three "one moment" fillers
  and the two fixed goodbyes. You write English; **Suggest Hindi** asks
  OpenAI for the Hindi she says (tokens counted as other costs), which you
  can edit before saving. The greeting's words are entirely yours (Harsh,
  2026-11-09: no required wording; what callers are told is the admin's
  call). Each line shows,
  per clinic for the greeting, whether it is **recorded in the current
  voice** (vendor, model, speaker, pitch) at **its own speed** and its exact
  words; **Play**
  a recording, **Record** one, a line, or everything not yet recorded (the
  estimated characters and price are shown first, from the Prices page).
  Each clinic may have its own voice: a shared line is then recorded once
  per voice (each take names the clinics it serves) and only plays in that
  voice. A take recorded at a speed more than 0.05× from the clinic's live
  voice is flagged ("it may sound different from her replies").
  Each line has its own **Speed** (0.70× to 1.30×; migration 0017 set the
  existing ones to 0.90×, the speed they were recorded at), apart from the
  live voice's `SARVAM_TTS_PACE`: changing either never un-records the
  other. A line at a new speed is said live until recorded again.
  Nothing records by itself, and recording stops at the first failure
  (problem "Recording a voice clip failed"). Edited words or a new voice
  are said live until recorded; old takes stay, so going back to an old
  voice plays them again.

### Costs: what each call cost (`/admin/costs`)

No vendor returns the price of a call; every one reports exact usage. So
at hang-up the worker saves what the call used (`usage` table, from
LiveKit's own count for the session: LLM tokens in / cached / out, seconds
heard, characters spoken, plus the call's LiveKit minutes; console calls
spend no minutes), and the admin panel prices it **when shown**:
`clinic_agent/costs.py`, usage × the price valid on the call's day.
Hindi-name suggestions are counted too, as *other costs*.

- **Costs page**: the month's full price, what you actually pay after free
  allowances plus monthly fees, calls and the average call, each day, where
  the money goes (listening, thinking, speaking, call line, other), by
  vendor, language and clinic, the most expensive calls, and each vendor's
  bill next to ours. Each call's trace page shows its cost part by part.
- **Prices page** (`/admin/costs/prices`): everything it is worked out from,
  edited there, never in code. Vendor prices, **one row per model** (or
  blank for any model of that vendor): a language model's input, cached and
  output prices (per million tokens) are one row and one form, saved
  together in one step (`/api/admin/cost-settings/model-prices`), so a model
  is never half-priced. Each price applies **from a date**: a vendor's new
  price is a new row, so the past keeps its own; fixing a wrong one is
  editing it, and every call it covers is priced again. Also the
  dollar-to-rupee rate (set by hand to what your card is charged, dated),
  free monthly allowances (LiveKit minutes: the LiveKit-minutes problem uses
  this allowance), monthly fees (plan subscriptions) and each month's real
  bills. **A price must match how calls are counted**: Sarvam in seconds
  heard, characters or tokens, OpenAI in tokens, LiveKit in call minutes
  (`costs.COUNTED_IN`); the form offers only those units, the API refuses
  others, and the model box suggests the names calls actually used. A row
  that can never match says so in amber; one priced ahead of use says "No
  call has used this model yet". A "price missing" problem's **Open** goes
  straight to the Add form, filled in (vendor, model, unit, first day used):
  only the amount is left to type.
- Starts with the official prices as checked on 2026-10-13 (migration
  0012). Migration 0013 (Hindi only, 2026-11-08) then deletes everything
  ElevenLabs and the English line left behind: their prices and allowance,
  every call that ran on them (with its events, transcript, costs and the
  appointments it booked), their problems. It can't be undone; the
  migrations command copies a SQLite file first.
- Usage outlives its call: erasing a test call, the 180-day trace purge or
  deleting a clinic keeps what was spent (the call link just goes).
- **The limits:** usage is LiveKit's per-session total, so a vendor's own
  rounding per request (Sarvam bills listening by the second) can leave
  paise of difference; a call the worker never finished (crash) records no
  usage; whether a free allowance is per product or one shared pool depends
  on the plan. The bill check catches all of these.

## Problems: every failure flagged, in the website

Nothing is only in a log. `clinic_agent/incidents.py` decides what counts
and `api/dashboard/problems.py` words it twice: plain words and what to do
for the clinic, technical detail for the operator. **A problem closes on
proof that it's fixed** (Harsh, 2026-11-09), never because someone clicked:
the same thing working again closes it. Only what nothing retries closes
after a quiet spell, and the bell's history says so ("Last happened 3:12 PM,
not tried again since") instead of "fixed".

| Problem | Opens when | Clinic sees | Closes when |
|---|---|---|---|
| Receptionist offline (urgent) | no worker has checked in for 90 s | yes | a worker checks in |
| Hindi line off (urgent) | the live worker can't answer Hindi (a key missing): no calls at all | yes | it checks in able to |
| A vendor failing | 3+ errors from one vendor in 15 minutes; the operator reads what the error means and what to do (401/403 key rejected, 402 out of credits, 429 rate limited, 5xx the vendor's outage, timeout, unreachable) and which part (hearing, thinking, voice) | yes, in plain words ("trouble speaking to callers"), no vendor names; it can't be put away | a later call shows it working (it heard, replied or spoke with no error from it; a staff test call counts) |
| Calls failing | 2+ failed or dropped patient calls in an hour, with their times in the clinic's time ("1:12 PM and 1:20 PM") | yes | the clinic's next call ends well (a staff test call counts), or an hour without |
| Patients couldn't get through | the call page reports it (by reason) | yes | a call connects at that clinic, or 2 quiet hours |
| Server error | an unhandled API error (route and error type only) | no | that same page answers without an error, or 15 quiet minutes |
| Callers can't book | no active doctor, or one without weekly hours | yes | it's fixed |
| A doctor has no specialty | an active doctor saved without one (it is required now) | yes | the specialty is filled in |
| Clinic paused | paused in the admin panel | yes | turned back on |
| Bookings need a call | upcoming bookings flagged (leave, holiday...) | yes | none left |
| LiveKit minutes | 80% (urgent at 95%) of the monthly allowance (Prices page; 1,000 by default) | no | next month |
| Price missing | a call in the last 35 days used a model with no price that day, or a dollar price with no rate; Open fills in the missing price | no | the price or rate is added (at once: the save re-checks) |
| Expired transcripts not deleted | the purge fails | no | the next purge works |
| Recording a voice clip failed | an admin's Record fails (vendor error, timeout) | no | a recording works, or a quiet day |
| Recorded lines no longer match a clinic's voice | lines recorded in an earlier voice of that clinic (speaker, pitch or voice model changed); calls say them live | no | they are recorded again, or the voice switches back |
| Hindi name suggestions failing | a name's Hindi suggestion fails (OpenAI) | no | the next suggestion works, or a quiet hour |
| Phrase translation failing | Suggest Hindi fails (OpenAI) | no | a suggestion works, or a quiet hour |
| Fixed phrases unreadable | a call can't read its phrases: it says the built-in words live | no | the clinic's next call reads them, or a quiet hour |

- **A fix made in the dashboard shows at once.** Every change the API
  accepts (adding a price, setting hours, adding or turning on a doctor,
  resuming a clinic...) re-checks problems before it answers, and the
  dashboard asks for them again right after: the problem is gone (or
  there) within about a second, not at the next half-minute check.
- **The worker checks in** every 30 s (`clinic_agent/heartbeat.py`), from
  the moment LiveKit registers it (connected and ready for calls). Console
  doesn't. The API re-checks every condition every 30 s.
- **On every page** of both dashboards: a red banner for urgent problems
  that can't be put away while they last; amber ones until *Seen*; a bell
  with every open problem and the last week's fixed ones; "(!)" in the
  browser tab and a red tab icon; and desktop alerts (*Alert me on this
  computer* in the bell) for new problems. The admin Health page lists them
  all, and the Clinics list puts a dot by each clinic with one. Today's
  receptionist card says *Offline* rather than *Ready* when it is.
- The clinic's "Seen" and the operator's are separate. A system-wide
  problem (offline) can't be marked seen by a clinic.
- Console calls (room `console`) are a developer's tests: they never count
  as a clinic's failing calls or LiveKit minutes.
- **The limit:** alerts reach you only while a dashboard is open in some
  tab, and a server that is completely down can't show anything. Outside
  alerting (Healthchecks.io or email) was considered and left out for now.
- Resolved problems are deleted after 90 days.

## Dashboard (what staff can do)

The dashboard is called **ClinicDesk** (one constant,
`frontend/src/lib/product.ts`). The screens are in `../frontend/` (run
instructions in its README); every action below is an `/api` endpoint here.

- **Today** is the home page: whether the clinic is open right now (from the
  doctors' hours, leave and holidays), the next patient, each doctor's day
  with the patient in the chair marked, bookings that need a call to the
  patient and today's callers who may not have been helped (cut off, or the
  call failed: *Read the call*), today's calls (how many, bookings made or
  changed, questions answered; `/calls/today`, in the clinic's timezone),
  and the receptionist's setup checklist (address and phone, doctors, their
  hours, common questions, a test call) with *Try a call* and *Copy link*.
  All times are shown as 12-hour clock times.
- **Appointments** is the diary. **Day**: a column per doctor, time running
  down; working hours white, the rest shaded, leave and holidays labelled
  with the reason, a red line at the clinic's current time. **Free slots are
  drawn and clickable**: the booking form opens with that doctor and time
  filled in. Each booking is a block (a phone icon: booked by the
  receptionist; a warning icon: call the patient; a key under the grid
  explains them); clicking it opens its menu: call the patient, mark the
  visit, edit, cancel. On a phone the day is one doctor at a time, as a list with
  the free times as tap targets. **Week** (Mon–Sun): per doctor per day who
  is booked, how many slots are free, or why the doctor isn't in; any day
  opens as its diary page. **Find a patient** by part of the name or 3+
  digits of the number, upcoming first, then past ones, cancelled included
  (`/appointments/search`, 50 at most). Counters for the day (with how many
  arrived, done, no-show), bookings from calls, and the next seven days.
  View, day and search are in the URL.
- **Visit marks: Arrived, Done, No-show**, from a booking's menu, on its day
  or later (not ahead of time); tapping the mark again clears it. They are
  `appointments.visit`, **not a status**: the double-booking index and every
  slot query look at `status = 'booked'`, so a patient in the waiting room
  still holds their slot. Cancelling or moving a booking clears its mark.
  The receptionist doesn't list a visit already marked and refuses to cancel
  or move it on a call ("the front desk can help").
- **Calls** (`api/dashboard/calls.py`, members only): every call newest
  first, in plain words ("Booked Riya Sharma with Dr. Asha Mehta · Sun, 27
  Sept, 10:00 am", "The caller asked a question", "The call was cut off").
  A call opens to **what was said**, the caller and the receptionist only:
  the tools it used, vendors and errors are left out by the API, not just
  hidden, since they are the operator's. The words are deleted after 30
  days; the call's line stays. Each time ClinicDesk support opened the
  transcript is listed with the reason given.
- **Staff have the final say.** *New appointment* books a walk-in or a
  booking taken on the clinic's own phone; *Edit* on any booking changes the
  doctor, day, time, patient's name and number, or the reason; *Cancel*
  frees the slot at once and offers **Undo** for 8 seconds instead of
  asking first. Undo (`/restore`) puts the booking back at the same doctor
  and time, unless someone (a caller, say) booked that time meanwhile: then
  it says so and the booking stays cancelled. The form offers the doctor's free times as
  quick picks **and accepts any time typed in** — outside hours, on leave,
  off the slot grid — because a clinic squeezes people in. The only thing
  refused is overlapping another booking of the same doctor, and the
  message names who holds the time. A cancelled booking can't be moved
  (book a new one), but its details can still be corrected. The patient is
  never told automatically.
- **The reason for the visit** is asked for on the call and filed in short
  English, whatever language the caller used ("आँखों से धुंधला दिखता है" →
  "Blurred vision"), since the dashboard is English only. It is shown on the row; staff can add or change it. It is health
  information: shown to the clinic, never written to logs.
- **The right doctor for the reason.** The receptionist asks why the caller
  is coming before it looks for times, and matches it to the doctors'
  specialties. A reason clearly outside all of them (fever, with only an eye
  specialist) is declined kindly and nothing is booked; it may suggest the
  obvious type of doctor ("general physician"), never a named doctor or
  clinic elsewhere, and never guesses the illness. With several doctors it
  picks the one who fits. When unsure it books, marked **Check reason** on
  Today and in the diary ("The receptionist wasn't sure this doctor sees
  this"); staff clear it from the appointment's menu, *Reason checked*. A
  caller who won't say why is still booked, unmarked. The slot search can't
  run without the model's verdict on the reason (`reason_fits`): "outside"
  returns no times at all, only the decline. Before every read-back,
  `check_booking` sets the reason beside the doctor's specialty for a second
  look. The model makes the call, so it is graded by live evals
  (`tests/test_live.py`, "the right doctor for the reason").
- **Every doctor has a specialty** ("General Physician" counts): the form and
  the API refuse a blank one, and a doctor saved blank before is a problem
  until it is filled in.
- **Clinic settings**: details, booking rules, the receptionist link, doctors, weekly
  hours (any number of sessions a day), leave and holidays, FAQ answers (each editable in place), and (admins) the
  team. Everything the agent knows about a clinic is entered here.
- **A new doctor starts with hours**, not an empty week: *Starting hours*
  defaults to Mon–Sat, 10 am–1 pm and 5–8 pm (or another pattern, a
  colleague's hours, or none). They are bookable at once, so the confirmation
  says to check them. Patterns live in `api/dashboard/patterns.py`.
- **Weekly hours** is one row per day holding any number of sittings, in
  any part of the day (evening-only is fine); a day with none is closed.
  *Add* offers Morning, Afternoon, Evening or another free hour; each day's
  menu copies it to Mon–Fri, Mon–Sat or every day, or closes it. *Fill the
  week* applies a pattern or a colleague's week. Nothing is saved until *Save
  hours*. The preview is the receptionist's own description
  (`prompts.weekly_hours`, via `/api/hours/preview`). Overlapping sittings
  are refused, by the form and by `repo.check_sittings`.
- **Deactivate or remove a doctor.** *Deactivate* stops new bookings and
  keeps their records. *Remove* deletes them for good, with their hours,
  leave and past appointments. It asks first, and it is refused while they
  have upcoming bookings (each doctor card shows how many): cancel those and
  tell the patients first.
- **Bookings that can no longer go ahead are flagged.** Existing bookings
  stay booked when staff add leave or a holiday, change a doctor's hours or
  deactivate them. The diary marks each one with a warning icon (its menu
  says *Call the patient:* with the reason), Today lists them under Needs
  attention, and
  adding leave lists the clashing bookings at once.
  The agent sees the same flag when a caller looks their bookings up, and
  offers to move or cancel.
- **Sign-in is with Google.** Admins (`ADMIN_EMAILS`) see every clinic's
  settings, create clinics and, on each clinic's **Team** tab, choose the Google
  accounts that may open it. **Admins don't see patients:** Today and
  Appointments show "For the clinic's staff only" unless the admin is also on
  that clinic's team (add yourself to your own clinic's team to see it). Everyone else sees only their clinics; an
  account no clinic added gets a "No clinic yet" screen. Adding someone sends
  no email: give them the dashboard's address yourself.
- `DASHBOARD_LOGIN=off` skips sign-in and makes everyone an admin and staff of every clinic, with a
  *Test mode* note in the sidebar. Local development only.

### Setting up Google sign-in

Once per deployment, in the Google account that will own the login (about
ten minutes):

1. [console.cloud.google.com](https://console.cloud.google.com) → create a
   project (e.g. "ClinicDesk").
2. **Google Auth Platform** → **Branding**: app name and a support email.
   **Audience**: *External*. While the app is in *Testing*, only the Google
   accounts listed under **Test users** can sign in (up to 100): add yours and
   each clinic's. Publishing the app removes that list. With only `openid email`
   it needs no full Google review, but showing the app's name and logo needs
   brand verification (minutes if automatic, about 2-3 business days if
   manual), which asks for a verified domain and a privacy policy page.
3. **Clients** → **Create client** → *Web application*. Under **Authorized
   redirect URIs** add `http://localhost:3000/api/auth/callback` (and later
   `https://<dashboard address>/api/auth/callback`): `DASHBOARD_URL` +
   `/api/auth/callback`. Copy the client ID and secret.
4. In `.env`: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, a `SESSION_SECRET`
   from `uv run python -c "import secrets; print(secrets.token_hex(32))"`,
   `DASHBOARD_URL`, `DASHBOARD_LOGIN=google` and
   `ADMIN_EMAILS=<your Google email>`. Restart `python -m api`.

Google's console moves things around; if a name above has changed, the
client type is still "OAuth client ID, Web application".

## Test

```bash
uv run pytest            # offline: config, providers, session, boot, store, scheduling, API (incl. access attacks)
uv run pytest -m live    # real OpenAI calls, as text — spends OpenAI credits, never Sarvam's

# every database test against Postgres as well (wiped per test: never real data)
TEST_POSTGRES_URL=postgresql+psycopg://clinic:clinic-dev@127.0.0.1:5433/clinic_test uv run pytest
```

Live tests use OpenAI only, as text, with its default model (2026-11-08),
so they never spend Sarvam credits. The conversation evals grade the Hindi
rules on OpenAI, the line's other brain (they check rules and tools, not
Sarvam's model). Only `OPENAI_API_KEY` comes from `.env`. Nothing tests
Sarvam's ears, voice or brain automatically; check them by hand (a spoken
`console` call) before a production release.

Offline tests prove the wiring, not the conversation. Live tests are evals:
an LLM judge (`gpt-4.1`; the agent's own mini model failed correct replies)
grades each reply against a stated intent (refuses
medicine, escalates chest pain, never states a fee, never confirms a booking,
answers Hinglish in Hinglish). They test no audio and do not measure
end-to-end latency: only a spoken `console` call does that.

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
    ├── spoken.py       clock times as Hindi words ("साढ़े बारह बजे") for the tools
    ├── context.py      loads the call's clinic and its local time
    ├── dispatch.py     which clinic and language a call is for: the agent name + metadata format
    ├── call_limit.py   hard cap on call length: goodbye, then close the room
    ├── voice_clips.py  the fixed phrases (greeting, fillers, goodbyes): recorded or said live
    ├── call_record.py  each call's trace (timings, tools, errors) + transcript
    ├── incidents.py    problems: what counts, when one opens and closes
    ├── heartbeat.py    the worker checking in while connected to LiveKit
    ├── booking.py      booking rules: find slots, validate, book — no LiveKit
    ├── tools/booking.py  slots, book, find/cancel/reschedule as LiveKit tools
    ├── tools/call.py     end_call — speaks the model's goodbye, then hangs up
    ├── tools/speech.py   the "one moment" a tool says while it works
    ├── agent.py        Agent subclass — behaviour only (tools land here)
    ├── session.py      the one place STT + LLM + TTS are combined
    ├── providers/      vendor construction, behind three functions
    │   ├── stt.py
    │   ├── llm.py
    │   └── tts.py
    └── store/          clinic data — the only package that imports SQLAlchemy
        ├── db.py       engine + sessions from DATABASE_URL
        ├── migrations.py  schema upgrades (Alembic); `python -m` runs them
        ├── purge.py    deletes expired transcripts and old calls; `python -m` runs it
        ├── alembic/    revisions, one file per schema change
        ├── models.py   clinics, FAQ, doctors, hours, time off, patients, appointments, calls, incidents
        └── repo.py     every query the agent and dashboard make
    scheduling.py       free-slot rules — pure functions, no DB, no LiveKit
seeds/demo_clinic.py    fictional clinic for tests and a first run
../frontend/            the dashboard (Next.js): screens only, over /api
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
  With only one active doctor it is told never to ask "which doctor?"; with
  several, to ask only when the caller hasn't said.
- **The rules it follows** (`prompts.RULES["hi"]`) stay **under 500 words**
  (`test_the_rules_stay_short`): a long prompt is paid for on every turn, and
  the model follows a short one better.
- **Booking** (three tools, rules in `booking.py`):
  - `find_available_slots(date, reason_fits, from_time?, doctor?)` returns
    **only the next few free times** from `from_time` (the clinic's "free
    times offered at once", default 3), one by one, per doctor, and says
    whether more are free later that day. "Evening?" is asked again from
    17:00, "after seven?" from 19:00, so the agent only ever sees the times it
    may offer (Harsh, 2026-11-10: from a whole-day list it read out 5-6).
    A refused time ("not free at 17:00") offers the next few after it the
    same way. Each time carries its Hindi words, written by code
    (`spoken.py`): "12:30 (साढ़े बारह बजे)"; left to itself the agent said
    "बारह साढ़े बजे" and "सत्रह बजे". With nothing free it says why (clinic
    closed, doctor on leave, doesn't sit that day, nothing from that time,
    no times left today, fully booked) and gives the next free day's first
    few.
  - `check_booking(doctor, date, time, name, phone, reason?)` books
    **nothing**. It checks everything a booking would (doctor, day, the time
    still free, a 10-digit Indian mobile, +91 / 0 / spaces accepted), keeps
    the details, and returns them for the read-back, written by code: doctor,
    day, time with its Hindi words, name, number digit by digit. `reason` is
    why the patient is coming, in English, for the clinic's staff.
  - `book_appointment()` takes no details: it books what `check_booking`
    last checked, so nothing can change between the read-back and the
    booking. **The code refuses it until the caller has spoken since that
    check**, so the model can't book in the same breath as the read-back
    (gpt-6-luna did, 3 of 4 live runs). It re-checks the slot and turns a
    lost race into "just taken — offer these instead".
  - Database work runs in a worker thread so a slow query never stalls audio.
    Tool errors reach the LLM as plain sentences it can relay.
- **Cancelling and moving** (three more tools): `find_my_appointments` needs
  the mobile number **and the patient's name**, and lists only that patient's
  upcoming bookings (family members sharing the number stay hidden), without
  the visit reason, and leaves out a visit already marked at the clinic.
  `cancel_appointment` and `reschedule_appointment` need both too, and
  **confirm by repeating, enforced in code**: the first call changes
  nothing and returns the read-back; the same call again acts, and only if
  the caller has spoken since (a change of time or doctor is a new
  read-back). The model's own word that the caller agreed is never enough,
  as with booking. Names are
  compared on the first name, spelling-tolerant ("Meena"/"Mina", "Ravi
  ji"/"Ravi Kumar"); tools take them in Roman letters, as booking stores them. A move is one database
  update: the appointment keeps its number, and the double-booking index
  still refuses a taken slot, so it is never half-moved. A wrong number, a wrong
  name, an unknown id and another clinic's id all get the same answer, so guessing
  reveals nothing. A booking with a doctor who has since been deactivated
  can only move to another doctor. **Number + first name is the only proof
  of identity today**, and a first name is easy to guess for someone who
  knows the family. Once telephony arrives, match the caller's own number.
- **Ending the call**: `end_call(goodbye)` takes the goodbye as its
  argument — what was done on the call (the booking's doctor, day and time),
  then goodbye — speaks it with interruptions off, waits until it has
  played, then closes the session and deletes the room, which disconnects a
  phone caller. An empty goodbye gets the fixed one (recorded when it can
  be, see below); it never hangs up
  silently. (LiveKit's `EndCallTool` asked for the goodbye in a second model
  reply after the tool, and the call ended in silence when that reply was
  empty or interrupted.) Hidden during the greeting; a caller who only says
  thanks is asked "anything else?" first.
- **The greeting is fixed text, never written by the model**, and the
  caller can't cut it off (it tells them the call is automated and saved).
  No model round runs before the caller speaks, so it can't call a tool
  either (seen live, when the model wrote it: it looked up tomorrow
  evening's slots before the caller had said a word).
- **Fixed phrases play from a recording when there is one**
  (`voice_clips.py`): the greeting, the three "one moment" fillers (one at
  random, never the same twice running) and the two fixed goodbyes (empty
  `end_call` goodbye, time limit). Each call loads them once at its start:
  a phrase recorded for the call's exact voice (vendor, model, speaker,
  pitch, sample rate), at the phrase's own speed, and exact words plays that
  recording, with no
  voice-vendor call; anything else is said live, as before. A recording is
  made only when an admin asks (admin page: coming). If the phrases can't
  be read at all, the call says them live in their built-in words and the
  admin sees a "could not read its fixed phrases" problem. The model's own
  goodbye is always live. **A line played from its recording costs
  nothing:** the voice isn't asked, so LiveKit counts no characters for it
  and Costs never charges it; the call's trace lists it as a step ("Greeting,
  from its recording") and its cost box as "Played from recordings, ₹0".
  Only making a recording (Record) is charged, once, under Other costs.
- **The voice gets whole sentences.** The reply streams from the model a few
  words at a time; Sarvam voices each piece it is handed as one take, so a
  piece cut mid-sentence changed the tone halfway through. LiveKit's own
  splitter doesn't know the Hindi full stop "।", so a Hindi reply went out
  as one block and Sarvam re-cut it every 150 characters wherever that
  landed. `providers/sentences.py` cuts at । ? ! . first ("Dr." and "5.30"
  aren't ends), a sentence over 220 characters at its last comma, and only
  then at a space; Sarvam's `max_chunk_length` is raised so it never re-cuts.
- **No dead air around a lookup.** The model says a short line ("ठीक है,
  मैं चेक करके बताती हूँ") in the same reply as a booking tool call, so it
  plays at once. If it didn't, the tool says a fixed filler itself, in the
  call's language (Hindi), once per reply,
  while the database work runs (`tools/speech.py`). If the model says it
  will check but calls no tool (seen live: "मैं कल के स्लॉट्स चेक कर लेती
  हूँ", then silence), `keep_promises` notices when that reply ends and
  makes it call a booking tool at once (`tool_choice="required"`). A
  question ("चेक करूँ?") or "चेकअप" doesn't count, and a forced follow-up is
  never forced again.
- **It says it is automated.** The default greeting names the clinic and
  says it is the clinic's automated assistant ("ऑटोमेटेड असिस्टेंट" in
  Hindi), and that the conversation is saved as text for the clinic's
  records. An admin may change those words freely (nothing enforces them).
  The call page says both, plus "for 30 days. No audio is recorded."
- **She speaks as a woman.** Every voice is female, so in Hindi everything
  she says about herself is feminine ("बात कर रही हूँ", "बताती हूँ", "की
  ऑटोमेटेड असिस्टेंट"). The caller's gender is still never assumed ("ji").
  Pick only female voices (`SARVAM_TTS_SPEAKER`).
- **Calls have a time limit** (`MAX_CALL_MINUTES`, default 10). At the limit
  the receptionist says the fixed time-limit goodbye (it can't be
  interrupted; no model round), and
  closes the room, which disconnects the caller.
- **Every call is recorded as text, never audio.** The worker writes two
  things per call (`call_record.py`):
  - the **trace**: when each turn happened and how long each step took (STT,
    end of turn, LLM first token, TTS first audio, the caller's whole wait),
    each tool's name, result and duration, vendor errors by type, how the
    call ended (`caller_left`, `agent_ended`, `time_limit`, `shutdown`,
    `error`) and its outcome (`booked`, `moved`, `cancelled`, `info_only`,
    `no_action`, `failed`, worked out from what the tools changed, not from
    what the model said). It never holds anything that was said;
  - the **transcript**: what the caller and receptionist said, with tool
    arguments and results. This is patient data and lives in its own table.

  The record opens when the call starts. A call the worker never finishes
  (a crash or kill) stays open with no end time. Recording can't break a
  call: any failure is logged and the call goes on. Transcripts are deleted
  after 30 days and traces after 180 (`clinic_agent/store/purge.py`). The API
  server purges every 6 hours; run `uv run python -m clinic_agent.store.purge`
  to do it now. The session starts with `record=False`, so nothing goes to
  LiveKit Cloud's own recording, whatever the project's setting says.
- **`console` refuses to start** if its clinic isn't in the database (or there
  are several and no `--clinic`), naming the fix.

- **Double booking is impossible at the database level** — a partial unique
  index on (doctor, start time) for booked appointments. A second booking
  raises `repo.SlotTaken`; a cancelled slot can be rebooked. That is why
  visit marks live in their own column: a status other than `booked` would
  free the slot.
- **Split shifts** are several `doctor_hours` rows for one weekday (e.g.
  10–1 and 5–8). **Time off** with no doctor is a whole-clinic holiday.
- **Each clinic has a link name** (`slug`, e.g. `sharma-skin-clinic`), made
  from its name when created, `-2`, `-3` if taken, and editable on the
  dashboard's **Receptionist link** tab. Its call link is `PUBLIC_BASE_URL/call/<slug>`.
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
   # clinic_agent/providers/llm.py
   def _openai(cfg: Settings) -> llm.LLM:
       return openai.LLM(model=cfg.openai_llm_model or "gpt-4.1-mini", api_key=...)

   BUILDERS = {"sarvam": _sarvam, "openai": _openai}
   ```

2. Name it in the line in `clinic_agent/lines.py` (or, for the brain, as a
   `HINDI_LLM` choice in `config.py`).

An unknown name fails and lists what is registered. Registered:
STT `sarvam`; LLM `sarvam`, `openai`; TTS `sarvam`.
That list is deliberate: no other vendors (a test enforces it).

Each builder owns its defaults and asks for its own key with
`require_key(...)`; a missing key switches the line off. Every vendor has
its own model and voice settings (`SARVAM_TTS_SPEAKER`, `OPENAI_LLM_MODEL`,
…).
A vendor setting left blank gets that vendor's default. The old shared names
(`STT_MODEL`, `TTS_SPEAKER`, …) are refused at startup with their new names,
rather than silently ignored.

## Configuration

**How the receptionist behaves now lives in the database, not `.env`**
(Harsh, 2026-11-10; `clinic_agent/receptionist_settings.py`). Every clinic
shares the rules text, the brain (`HINDI_LLM` and the model names), the
hearing settings, the voice model, the turn-taking timings and whether the
greeting can be talked over. Each clinic sets its own instructions,
directions, speaker, live speed, pitch and maximum call length. A call reads
them when it starts (`clinic_agent/call_settings.py`), so a change applies
from the next call without a restart. The first
`python -m clinic_agent.store.migrations` after this change copies those
lines from your `.env` into the database once (a clinic's setting goes to
every clinic) and lists them for you to delete. After that, a leftover
line stops the worker and the API with a message naming it, so nothing is
silently ignored. The table below still names those settings by their old
`.env` names for what they do; set them in the dashboard. Shared
settings are on **Admin > Receptionist**; each clinic's own on its
**Receptionist** tab in Clinic settings (admins only).

Every other setting is in `.env.example` with a comment. The ones worth knowing:

| Setting | Default | Why you would change it |
|---|---|---|
| `HINDI_LLM` | `sarvam` | `openai` gives the Hindi line OpenAI's brain (same Sarvam ears and voice), to compare the two. Restart the worker after changing it. |
| `SARVAM_STT_MODEL` | `saaras:v3` | `saaras:v4` is not available on our plan. |
| `SARVAM_STT_LANGUAGE` | `unknown` | `unknown` auto-detects per utterance, so the English words callers mix in come through as said. |
| `SARVAM_STT_MODE` | `transcribe` | `transcribe` returns Hindi in Devanagari, which matches the prompt's rule that Hindi replies are written in Devanagari — the script the voice engine pronounces correctly. |
| `SARVAM_LLM_MODEL` / `OPENAI_LLM_MODEL` | vendor's | OpenAI: `gpt-4.1-mini` (fastest capable model measured, ~1.0 s first token). For a reasoning model (`gpt-6-luna`, any gpt-5-or-later or `o*`) the builder sets `reasoning_effort="none"`, which OpenAI requires for tools on Chat Completions and which keeps replies fast. Sarvam: `sarvam-105b-conversations` (fall back to `sarvam-105b`). |
| `SARVAM_TTS_MODEL` | `bulbul:v3` | Sarvam's voice model. |
| `SARVAM_TTS_SPEAKER` | `suhani` | Any voice of the chosen model (a woman's: the prompt says so); v2 names such as `anushka` are rejected by `bulbul:v3`. |
| `SARVAM_TTS_CODEC` | `linear16` | Raw PCM: compressed formats cost a decode per chunk. |
| `SARVAM_TTS_LANGUAGE` | `hi-IN` | The replies are Devanagari. |
| `SARVAM_TTS_PACE` | `1` | Speed of the live voice, 0.5 to 2. Restart to hear a change. Recorded lines keep their own speed (Voice page). |
| `SARVAM_TTS_PITCH` | `0` | Pitch, set once for every reply: -0.5 (lower) to 0.5 (higher). Only `bulbul:v4-flash` applies it. Temperature is not a setting: v4-flash fixes it at 0.6 itself. A change in either makes new voice clips (the old ones stay for going back). |
| `DATABASE_URL` | `sqlite:///data/clinic.db` | `postgresql+psycopg://user:pass@host:port/db` for production. Run the migrations command after changing it. |
| `PUBLIC_BASE_URL` | `http://localhost:8080` | Where the call-link server is reachable; the dashboard builds each clinic's link from it. Your tunnel's https address for a demo from outside. |
| `MAX_CALL_MINUTES` | `10` | Longest a call may last before a goodbye and hang-up. Guards against forgotten or abused calls spending minutes. |
| `DASHBOARD_LOGIN` | `google` | `off` skips sign-in (everyone is an admin): local development only. |
| `ADMIN_EMAILS` | blank | Comma-separated Google emails that see every clinic and manage access. |
| `API_HOST` / `API_PORT` | `127.0.0.1` / `8080` | Where the call-link server listens. `0.0.0.0` inside a container. |
| `CLIENT_IP_HEADER` | blank | The header carrying the caller's IP behind a tunnel/proxy (`CF-Connecting-IP`, `X-Forwarded-For`), so rate limits stay per caller. Never trusted unless set. |
| `MIN_ENDPOINTING_DELAY` | `0.2` | Raise if it cuts you off mid-sentence, lower if replies feel slow. |
| `NUMBER_ENDPOINTING_DELAY` | `1.5` | The same wait as `MIN_ENDPOINTING_DELAY`, used only from the moment the receptionist asks for a number until the caller's next turn ends: callers read a mobile number in groups with small pauses, and at 0.2 s each group was its own turn. Max 3. Raise if numbers still arrive in pieces; lower if replies after a number feel slow. |
| `VAD_MIN_SILENCE` | `0.6` | Pause that ends an utterance for the VAD. At LiveKit's 0.25 s a comma pause ended the caller's turn mid-sentence (seen with a batch STT, which sends each VAD-cut utterance alone). Lower for faster replies, raise if it still cuts callers off. |
| `INTERRUPT_MIN_SPEECH` | `0.3` | Seconds of caller speech that stop the agent mid-reply. Lower if it talks over you, raise if coughs or background noise cut it off. |

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
Ctrl+C in `console`** — harmless, and a LiveKit bug (seen on 1.8.2; not
re-checked since the 1.8.11 upgrade). Ctrl+C schedules the shutdown; when the worker finishes it raises
SIGTERM, whose handler schedules a second `aclose()` onto an event loop that
has already stopped. The first shutdown has completed by then. Nothing to fix
on our side.

## Notes

- **Interruptions: local Silero VAD, same in every mode.** The VAD decides
  when the caller *cuts in*. When a turn *ends* is the STT's call
  (`turn_detection: "stt"`): Sarvam streams and ends turns itself. `session.py` passes the VAD explicitly
  and sets interruption mode `"vad"`: once the VAD hears
  `INTERRUPT_MIN_SPEECH` seconds of speech the agent stops. Without the
  explicit mode LiveKit would use its *adaptive* interruption model (LiveKit
  Cloud) in `console`/`dev` but not under `start`, so local tests would not
  match production. Two LiveKit behaviours remain: interruptions are off for
  the first 3 s of the agent's first reply (echo-cancellation warm-up), and
  a cut-in is first a *pause*: if the STT returns no words within 2 s the
  agent resumes (a "false interruption"). So a broken STT looks like "it
  doesn't stop".
- Sarvam credits are consumption-based and shared across STT, LLM and TTS.
  Every call spends them (the brain too unless `HINDI_LLM=openai`); the
  tests spend none.
- **Test an STT the way a call feeds it**: real time, faint room noise
  first, stream left open, and a batch model through LiveKit's
  `StreamAdapter` with the VAD. An instant, silent, stream-ending test once
  passed with two live-call bugs present (manual commits; language
  auto-detect locking onto the wrong language during the greeting).
