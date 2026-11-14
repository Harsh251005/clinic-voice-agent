# Call pipeline (`clinic_agent/`)

One concern per module. **†** = Harsh's ruling (`docs/rulings.md`).

## Boot and calls

- `main.py` validates config before `cli.run_app`: a `ConfigError`,
  unknown provider, missing key, old schema or (console) missing clinic
  exits with one line, no traceback. One worker serves every clinic: it
  registers as `dispatch.AGENT_NAME`; each job reads clinic **and**
  language (`hi` only) from dispatch metadata (`dispatch.call_from`).
  Missing/unknown either → job refused, never guessed. Console has no
  dispatch: `--clinic N` (or the only clinic), stripped from argv before
  LiveKit's CLI; the old `--language` is refused. `console --text` sets
  `TEXT_ONLY`: LLM-only session, manual turns, speech keys not checked.
- Each job: `call_setup.prepare` (clinic off the event loop → settings →
  session → instructions → record → phrases → tools → `ClinicAgent`) →
  `call_limit.end_after` (`max_call_minutes`), cancelled on shutdown.
  **`prepare` is the only place a call is put together**: the worker and
  the admin's typed chat (`chats.py`, in the API process) both use it, so
  a chat can't drift from a call. Change call behaviour there, never in
  one caller. Chat rooms start `repo.CHAT_ROOM`: no LiveKit minutes
  (`repo.in_livekit`), not a worker's call (`patient_calls_since`). Boot tries the line; no worker checked in for it =
  critical `language_off`.
- `call_settings.merge` lays `system_settings` and the clinic's row over
  `.env` into a plain `Settings` (+ rules text, greeting switch). Read at
  job start, so dashboard changes apply from the next call.
- `lines.py`: `line_for(cfg, language)` (vendor per part, LLM from
  `cfg.hindi_llm`) and `available(cfg)`.
- `session.py` is the only place STT + LLM + TTS become an `AgentSession`.
- `agent.py` is behaviour only: instructions come from the entrypoint, tools
  attach here, speaks first in `on_enter`.
- `prompts.py`: fixed `RULES` + `clinic_facts()` built per call from the DB
  (active doctors, grouped hours, leave/holidays in the booking window, FAQ,
  clinic time). Static facts go in the prompt; tools only change data or act.
- Clinic details are data (seed or dashboard), never in `.py` files.

## Providers (`providers/{stt,llm,tts}.py`)

Each has a `BUILDERS` registry name → builder returning LiveKit's base
class; builders own vendor defaults (`None` in `Settings` when blank) and
call `require_key`. Adding a vendor = a builder + naming it in `lines.py`.
Unknown names fail listing what exists. The boot key check loops over
`LANGUAGES`, so a second line would only switch itself off.

## Fixed phrases (`voice_clips.py`)

Greeting, fillers, fixed goodbyes. `for_call` loads them once per call with
any recording for the exact voice + words (`clip_key`); `say` plays it or
speaks live. **Any clip problem = said live †.** Unreadable phrases fall
back to `BUILT_IN` (must equal migration 0014's seeds) and open
`voice_clips_unread`. Nothing records itself: `record` runs only on an
admin's click (`api/dashboard/voice.py`, page `/admin/voice`; Hindi from
`providers/hindi.translate_phrase`). A played clip asks no vendor, so counts
no usage; `CallRecorder.clip_played` adds a `kind="clip"` trace step (never
words) shown at ₹0. The greeting is never model-written, uninterruptible
unless Admin > Receptionist allows it; the prompt's Opening rule says it was
said. **No required greeting wording †**: don't add checks back.

## Tools (`tools/`) and booking rules (`booking.py`)

- Rules are plain functions in `booking.py`, raising `BookingError` with a
  caller-sayable message. `tools/` holds only `@function_tool` wrappers:
  run the rule in `asyncio.to_thread`, map `BookingError` → `ToolError`.
- **Check-then-book, in code:** `check_booking` validates and returns the
  read-back; no-argument `book_appointment` books only what was checked,
  only after the caller spoke since (the one call state kept in a wrapper).
  Cancel/reschedule **confirm by repeating**: first call checks and reads
  back, the same call again acts once the caller spoke (`confirmed`).
  Never go back to a `caller_confirmed` flag.
- **A tool that can't answer is answered by the code †** (`give_up`): a
  crash, or the same error twice with nothing new from the caller → fixed
  `sorry_cant_check` phrase, `StopResponse` (no model reply), reports
  `tools_failing`; the call's record marks the step failed. A caller
  repeating a request is a new question †: the model answers it again.
- **Right doctor for the reason †:** the model judges fit; `check_booking`
  sets reason beside specialty before the read-back (`fit_gate`);
  `reason_fits="unsure"` books with `appointments.reason_unsure` ("Check
  reason" in the dashboard). A doctor's specialty is required.
- `tools/call.py`: our own `end_call` (LiveKit's `EndCallTool` could hang
  up in silence): goodbye is a tool argument, spoken uninterruptible, then
  the room is deleted. Hidden during the greeting (`IGNORE_ON_ENTER`).
- Tests: in-memory DB for rules; a **file** DB for tools (SQLite
  `:memory:` is per-thread). Live evals use `mock_tools`.

## Records (`call_record.py`)

`CallRecorder` writes every call's **trace** (`calls` + `call_events`:
timings, tool names/ok, vendor error types, end reason, outcome) and
**transcript** (`call_transcripts`, patient data). **Never audio**
(`record=False`). **The trace never holds words from the call** (operator
sees it; transcripts only via a logged opening, `transcript_access`).
Recording failures are logged, never break a call. Tools report changes via
`ClinicLink.on_change` (booking functions return `booking.Changed`).
`store/purge.py`: transcripts 30 d, traces 180 d.

## Costs (`costs.py`)

No vendor returns a price: the recorder saves exact usage (`usage`, from
`session.usage`; never money or words) and this prices it when shown, from
the dated price tables (`prices`, `exchange_rates`, `allowances`,
`fixed_costs`, `vendor_bills`) edited on the admin Prices page, **never in
code †**. A price may only be in a unit calls count that vendor in
(`COUNTED_IN`; add a new vendor's unit there). Usage outlives its call (FKs
`SET NULL`).

## Problems (`incidents.py`)

`KINDS` defines conditions and events; `sync` (API re-checks every 30 s)
opens/updates/closes; `report` counts events. **Closes only on proof it is
fixed †** (`resolved_how="fixed"`); only what nothing retries goes "quiet"
after its spell, labelled so. A new kind needs its recovery rule. Every
accepted `/api/*` change re-checks before answering (`api/app.py`
`check_problems`, one at a time) and the dashboard refreshes after it
(`afterEveryChange`). Words in `api/dashboard/problems.py`: plain for the
clinic, technical for the admin. **Alerts stay in the website †.**
`heartbeat.py`: worker checks in every 30 s from `worker_registered` (not
console); stale 90 s = offline.
