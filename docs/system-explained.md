# The clinic voice agent, explained simply

A plain-language tour of the whole system: what is built, why, and how.
Written 2026-09-25 against commit `1df353d`, checked against the code, with the
offline suite at 312 passing. If the code and this file disagree, the code wins.
`CLAUDE.md` and `backend/README.md` are the maintained sources of truth.

---

## 0. The whole thing in one breath

When someone calls a clinic, a **robot receptionist** answers in Hindi, English
or a mix of both. It answers questions about the clinic and **books, cancels and
moves appointments**. The clinic staff use a **website (the dashboard)** to set
up their doctors and hours and to see every booking.

Think of it as **a toy clinic with three rooms**:

| Room | Real name | What happens there |
|---|---|---|
| 🗣️ The reception desk | **Agent worker** (`backend/main.py` + `clinic_agent/`) | The robot talks to callers |
| 🚪 The front door | **Call-link server** (`backend/api/`) | Patients click a link to reach the robot |
| 🗂️ The back office | **Dashboard** (`frontend/` + `backend/api/dashboard/`) | Staff set things up and see bookings |

All three share **one notebook**, the **database**. Everything the robot knows
and every booking it makes is written there.

---

## 1. Why build it at all?

- Indian clinics miss calls. The receptionist is busy, it's lunch, or the
  clinic is closed. A missed call is a lost patient.
- Patients speak **Hinglish**, and most English-only bots fail at that.
- So the product is a receptionist that never misses a call, speaks the way
  patients speak, and puts bookings straight into the clinic's diary.
- It is a product **to sell** to clinics, not a portfolio piece.

---

## 2. What happens on one call, step by step

A patient called Ravi wants to see a doctor tomorrow evening.

1. **Ravi opens the clinic's link**, something like `yoursite.com/call/cure-dental`.
   There's no phone number yet (see section 13), so calls happen in the browser.
2. **The front door gives Ravi a signed "pass"**, like a stamped ticket. It says
   "you may join room `call-cure-dental-a1b2`, microphone only, and the Cure
   Dental robot will join you". A secret key signs the ticket, so Ravi can't
   change which clinic answers.
3. **LiveKit** is the phone line. It's a service that carries live audio between
   two people. It sees the ticket and sends the robot into the room.
4. **The robot works out which clinic this is** from the ticket (`dispatch.py`).
   If the ticket doesn't name a clinic, or names one that doesn't exist, the
   robot **refuses the call**. It never guesses, because a wrong guess would
   mean the wrong doctors and bookings in the wrong diary.
5. **The robot reads the clinic's page in the notebook**: doctors, hours, fees,
   leave, holidays, FAQ and the current time. It turns that into its
   instruction sheet for this call.
6. **The robot speaks first**: "नमस्ते, Cure Dental Clinic में आपका स्वागत है,
   मैं यहाँ की ऑटोमेटेड असिस्टेंट हूँ…" It **always says it's a robot**. That's
   the first rule in its instructions.
7. **Ravi talks. The robot listens, thinks, looks things up, and replies.**
   This repeats (sections 3 to 6).
8. **Ravi says bye.** The robot says what was done ("your appointment is
   tomorrow at 5 with Dr. Mehta"), says goodbye, and hangs up.
9. If a call runs past **10 minutes** (`MAX_CALL_MINUTES`), the robot
   apologises, says goodbye and hangs up, so a forgotten call can't keep
   costing money.

---

## 3. The robot's body: ears, brain, mouth

The robot is three separate machines joined in a line:

```
Ravi's voice → 👂 EARS (STT) → text → 🧠 BRAIN (LLM) → text → 👄 MOUTH (TTS) → voice → Ravi
```

| Part | Job | Production vendor | Testing vendor |
|---|---|---|---|
| 👂 **STT** (speech to text) | Turns voice into written words | Sarvam `saaras:v3` | ElevenLabs `scribe_v2` |
| 🧠 **LLM** (the language model) | Decides what to say and what to do | Sarvam `sarvam-105b-conversations` | OpenAI `gpt-6-luna` |
| 👄 **TTS** (text to speech) | Turns written words into a voice | Sarvam `bulbul:v3`, voice "suhani" | ElevenLabs `eleven_v3_conversational` |

**Why two vendor sets?** Sarvam is built for Indian languages, so it's the real
product. But Sarvam costs money per use, so day-to-day testing uses ElevenLabs
and OpenAI. You switch between them by changing **three lines** in `.env`
(`STT_PROVIDER`, `LLM_PROVIDER`, `TTS_PROVIDER`). No code changes.

**The rule:** only Sarvam, ElevenLabs and OpenAI are allowed, and a test fails
if anyone adds another vendor.

**Why keep the parts separate?** Each vendor lives in its own small file
(`providers/stt.py`, `llm.py`, `tts.py`), which is the only place its code is
imported. The rest of the system only knows "an ear", "a brain" and "a mouth".
Swapping a vendor is like swapping a toy's battery: nothing else changes. A
test (`test_boundaries.py`) enforces this.

**Choices hidden inside the three parts:**

- **Hindi is written in Devanagari (देवनागरी), never "aap kaise hain".** The
  mouth pronounces by script. Given Roman letters, it reads Hindi with English
  spelling rules and sounds wrong.
- **The mouth outputs raw audio (PCM)**, not mp3, so nothing has to be decoded
  for each chunk. That saves time.
- **Replies are cut into sentences before they reach the mouth**
  (`sentences.py`). The mouth speaks each piece as a fresh take, so a piece cut
  mid-sentence changes tone halfway. LiveKit's built-in cutter didn't know the
  Hindi full stop "।", so this project has its own. It cuts at । ? ! . first,
  then commas, then spaces, with pieces of 20 to 220 characters.
- **The ElevenLabs ear is pinned to Hindi.** Its auto-detect guessed the wrong
  language (even Chinese) on live calls and the robot heard nothing. Pinned to
  Hindi, it still understands English and Hinglish.
- **gpt-6-luna is a "thinking" model, and thinking is switched off**
  (`reasoning_effort="none"`). With thinking on, OpenAI rejects tool use (an
  error on every turn), and it would also be too slow for a phone call.

---

## 4. Taking turns: how the robot knows when to talk

Humans take turns without thinking about it. The robot needs rules:

- **VAD (voice activity detection)** is a tiny local model called Silero that
  only asks one question: *is someone speaking right now?* It runs on your own
  machine, so it costs nothing per call.
- **Knowing when the caller has finished** (`turn_detection="stt"`): the ear
  decides when the caller is done. With ElevenLabs batch, the VAD waits for
  **0.6 s of silence** (`VAD_MIN_SILENCE`) before sending the sentence off. At
  0.25 s, a pause at a comma after "नमस्ते," cut the caller off mid-sentence.
- **Interrupting** (`interruption mode "vad"`): if the caller talks for
  **0.3 s** (`INTERRUPT_MIN_SPEECH`) while the robot is speaking, the robot
  stops, like a polite person. A shorter setting would let a cough cut it off.
- **Why set all of this explicitly?** Otherwise LiveKit quietly uses its own
  cloud models in test mode but not in production, so what you hear while
  testing wouldn't match a real call. Decided on 2026-09-25.

---

## 5. What the brain is told: the instruction sheet

At the start of every call the brain gets one sheet (`prompts.py`) with two
halves.

**Half 1: fixed rules (`RULES`), the same for every clinic.**

- Say you're an automated assistant.
- Reply in the caller's language, in one or two sentences, warm and a little
  informal.
- **You are a woman**, so use feminine Hindi about yourself ("बताती हूँ", not
  "बताता हूँ"). Address the caller with a neutral "आप", say "ji", and never
  "sir" or "madam".
- Say numbers as words. Use the Hindi time words that the tools provide.
- Only state facts from CLINIC FACTS. If something isn't there, say you don't
  have that information.
- No medical advice.
- **Emergencies come first**: for chest pain, trouble breathing and similar,
  tell the caller to ring 108 or 112 now.
- **Never promise what isn't built**: no "please hold", no "I'll take a
  message", no "someone will call you back". Those features don't exist, so the
  robot must not offer them. This is a hard rule for developers too: the
  instructions may only describe features that are built.

**Half 2: facts (`clinic_facts()`), freshly written from the database for this call.**

- The current date and time at the clinic, the clinic's name, address and phone.
- Each active doctor, with specialty, fee and weekly hours grouped neatly, e.g.
  "Monday to Saturday 10:00-13:00 and 17:00-20:00".
- Upcoming leave and holidays, and the clinic's FAQ answers.

**Why split it this way?** Facts that don't change during a call go into the
sheet, which is fast because nothing has to be looked up. Anything that
**changes data** or needs a **live check** (free slots) goes through **tools**.

---

## 6. The robot's hands: tools

The brain can't touch the database itself. It can only press these buttons
(`clinic_agent/tools/`):

| Button | What it does |
|---|---|
| `find_available_slots(date, doctor, part_of_day)` | Lists **every free time** that day, one by one, grouped as morning (before 12), afternoon (12 to 5) and evening (5 onwards), and marks 3 to suggest first |
| `check_booking(doctor, date, time, name, phone, reason)` | **Books nothing.** Checks that the time is still free and returns the details to read back |
| `book_appointment()` | **Takes no inputs.** Books exactly what was last checked |
| `find_my_appointments(phone, name)` | Lists that patient's upcoming bookings |
| `cancel_appointment(...)` | Cancels one booking |
| `reschedule_appointment(...)` | Moves one booking to a new free time |
| `end_call(goodbye)` | Says the goodbye, then hangs up |

**How a button works inside**, like a toy with a battery box: the **rules** live
in `booking.py` as plain functions that know nothing about LiveKit, so they're
easy to test. The **button** (`tools/booking.py`) is only a thin wrapper. It
runs the rule in a background thread, so a slow database never freezes the
audio, and turns rule errors into short messages the robot can say out loud.

**How free slots are worked out** (`scheduling.py`): take the doctor's sittings
that day and chop them into slots (default 15 minutes). Remove anything that
overlaps a booking, anything on leave or a holiday, and anything starting
**less than 30 minutes from now**, so nobody gets booked into a slot that
starts while they're still on the phone. Callers can only book up to **30
days** ahead (`booking_window_days`).

---

## 7. Safety nets: code that doesn't trust the brain

**The main idea: an LLM is clever but unreliable, so anything that matters is
enforced in code, not left to the instructions.**

| Problem seen | Safety net in code |
|---|---|
| The robot booked **before reading the details back** (gpt-6-luna did this in 3 of 4 runs) | **Check, then book.** `book_appointment` takes no inputs and only books what `check_booking` returned, and only once the caller has **spoken again since the check**. The code counts the caller's turns. |
| A stranger tries name after name on someone else's number | `find_my_appointments` needs **number and name together**, and allows **3 misses per call**, then stops |
| The robot hinted at other people's bookings | Wrong id, wrong number and wrong name all return **the same message**, so a guess reveals nothing. The visit reason (health information) is **never read out**. |
| Families share one phone | A patient is identified by **(clinic, phone, name)**, and a new name never renames an existing patient |
| "Meena" vs "Mina", "Aarav" vs "Arav" | The first name is folded, so different spellings of the same name match |
| The robot said "बारह तीस" or "सत्रह बजे" for times | **Code writes the Hindi time words** (`spoken.py`: 12:30 becomes "साढ़े बारह बजे"). The robot only copies them. |
| Showing free times as a range ("10 से 1 बजे तक") hid the booked times inside it | Times are listed **one by one**, never as ranges |
| Silence while a tool runs | If the robot didn't say "one moment" itself, the tool says one (`filler_unless_spoken`). Never both. |
| The robot said "let me check…" and then did nothing | `keep_promises` notices and **forces** it to press a button |
| The robot hung up without saying goodbye | The goodbye is **part of the `end_call` button** and plays with interruptions switched off. There's a backup goodbye if it's empty. |
| Two callers grab the same slot at the same moment | The **database itself** refuses it, using a unique rule of one booked appointment per doctor per start time. The second caller hears "just taken" plus the other free times. |
| A call that runs forever | 10-minute limit |
| A call for an unknown clinic | Refused, never guessed |

---

## 8. The notebook: the database

**Tables** (`store/models.py`):

- **clinics**: name, **slug** (the link name), address, phone, timezone,
  booking window (30 days), number of slots to suggest (3)
- **doctors**: name, specialty, fee, slot length, active on or off
- **doctor_hours**: one row per sitting. Two rows on the same day gives a split
  shift (morning and evening).
- **time_off**: leave for one doctor, or, with no doctor set, a whole-clinic
  holiday
- **patients**: unique on (clinic, phone, name)
- **appointments**: doctor, patient, start and end, status (booked or
  cancelled), source (voice or dashboard), reason (always in English, for staff)
- **clinic_faq**: question and answer pairs
- **clinic_members**: which Google emails may open which clinic

**House rules for the notebook:**

- **Only `store/` talks to the database** (SQLAlchemy), and every query lives
  in `repo.py`. Everyone else gets friendly errors (`NotFound`, `SlotTaken`),
  never raw database errors. A test enforces this.
- **SQLite** for development and **Postgres** for production, with the same code.
- **Changing the shape of a table is a written, numbered step** (Alembic
  migrations; 4 so far). Only one command applies them
  (`python -m clinic_agent.store.migrations`). Running code **refuses to
  start** on an old schema instead of quietly changing it. That's safer: no
  surprise changes to real data.
- **Time rules:** appointment times are the clinic's local wall-clock time
  ("11 o'clock" means what staff mean). Record timestamps (`created_at`) are UTC.
- **Clinic details are data, not code.** A new clinic needs no code change.

---

## 9. The front door: the call-link server (`backend/api/`)

One small web server (FastAPI) does three jobs:

1. `GET /call/<slug>` shows the clinic's call page with a big call button.
2. `POST /call/<slug>/pass` hands out the signed ticket from section 2. The
   rules on that ticket:
   - a fresh private room every time
   - microphone only, no camera or screen
   - **at most 2 people**: the caller and the robot
   - the ticket expires after 5 minutes if unused
3. It also serves the dashboard's data (section 10) from the **same address**,
   so the login cookie works.

**Guards on the door:**

- **Rate limits**: 5 calls per IP address per 10 minutes, and 30 calls per
  clinic per hour. A leaked link can't burn through the minutes. These counts
  live in memory, which is fine for one server.
- **Strict browser security rules (CSP)**: the page may only load scripts from
  this server and one fixed version of LiveKit's code, checked by its
  fingerprint (SRI). Nobody can slip in other code.
- The server **won't start** if LiveKit settings are missing or the database is
  out of date.

**Why a browser link?** There's no phone number or server yet. The link allows
a demo and a pilot today. Telephony is added later by giving the same robot a
phone line, not by rebuilding it.

---

## 10. The back office: the dashboard

**The screens** (Next.js, `frontend/`) are only screens. All logic lives in the
Python backend.

- **Today**: each doctor's day, a receptionist status, and **"Needs
  attention"**: bookings that can't go ahead as booked, because of leave, a
  holiday or changed hours, so someone should call the patient.
- **Appointments**: the diary for any day. Book, edit or cancel, with
  quick-pick free times.
- **Setup**: clinic details, doctors, hours (with preset patterns, so you don't
  type every day), time off, FAQ, team and the call link.
- The UI is branded **ClinicDesk**, English only, and works on phones with
  bottom tabs.

**Who gets in:**

- **Sign in with Google.** The cookie holds only the email, is signed so it
  can't be forged, and lasts 12 hours.
- **Admins** (listed in `ADMIN_EMAILS`) see every clinic, create clinics and
  decide who's on each clinic's team.
- **Clinic staff** see only the clinics their email was added to. Access is
  checked against the database on every request, so removing someone takes
  effect immediately.
- **Every dashboard address that includes an id** is checked to make sure the
  row belongs to this clinic (`repo.in_clinic`). Otherwise Clinic A could type
  Clinic B's appointment number and see it; this attack is called **IDOR**.
  There's a test listing every attack of that kind.
- A clinic you can't open returns **"not found"** (404), not "forbidden", so
  strangers can't even tell which clinics exist.
- **CSRF guard**: every request that changes something must carry a special
  header (`x-clinic-console`). Another website can't add that header, so it
  can't trick a browser into making changes.

**Staff rules vs caller rules. This is deliberate:**

- **Callers** can only book free slots on the grid, within hours, not on leave,
  at least 30 minutes ahead.
- **Staff have the final say.** They can book outside hours, on leave, or at
  odd times like 10:05 for a walk-in. The **only** thing refused is two
  bookings overlapping for the same doctor.
- When staff add leave, existing bookings **stay booked** and are listed back
  as "clashes" so staff can call those patients. The system never cancels
  anyone silently.

---

## 11. House rules for the code: why it's shaped like this

| Rule | Why |
|---|---|
| Only `config.py` reads settings (`.env`) | One place to see every setting. A missing key fails **at startup**, not in the middle of a call. |
| Only `providers/` imports vendor code | Swapping a vendor touches one file |
| Only `store/` imports database code | Swapping the database, or fixing a query, touches one folder |
| Only `session.py` joins ears, brain and mouth | One place to change how the voice pipeline is put together |
| Rules in `booking.py`, thin wrappers in `tools/` | Rules can be tested without any voice or LLM |
| **One robot worker for all clinics** | Cheaper and simpler. Each call's ticket says which clinic it's for. |
| Old setting names are refused at startup | A typo'd or outdated `.env` fails loudly instead of quietly misbehaving |

The goal behind all of these: keep the cost of changing something low.

---

## 12. How it's tested and run

- **312 offline tests (free):** settings, vendors, booking rules, slot maths,
  Hindi time words, sentence cutting, safety nets, database (optionally on real
  Postgres too), migrations, dashboard security attacks, the call-link server,
  and the code-boundary rules.
- **21 live tests (cost money, run only with `-m live`):** real OpenAI and
  ElevenLabs, **never Sarvam**. An AI grader checks things like: does it speak
  first, does it read back before booking, is it feminine in Hindi, does it
  reply in the caller's language, does it hang up only when the caller is done.
  The last full run passed 20 of 21, and about 1 in 10 is flaky.
- **Dashboard end-to-end tests:** Playwright drives a real Chrome against a
  fresh database.
- **By ear:** real calls tested by hand.

**Ways to run it** (all from `backend/`):

- `main.py console`: talk through the laptop mic. No LiveKit minutes used.
- `console --text`: type instead of talking. Brain only, which is the cheapest.
- `main.py dev` or `start`: the real worker on LiveKit Cloud. The free tier has
  1,000 minutes a month, roughly one pilot clinic.
- `python -m api`: the call-link and dashboard server.
- `npm run dev` in `frontend/`: the dashboard.

---

## 13. What's NOT built (as of 2026-09-25)

| Missing | What it means |
|---|---|
| **Phone numbers (telephony)** | Browser link only. No real number yet, so no caller ID. |
| **Caller ID** | So identity is "tell me your number and name", which anyone who knows both could use |
| **Cancel/reschedule are still gated by the model** | They still rely on the brain setting `caller_confirmed=true`. Booking was fixed to be enforced in code; cancel and reschedule weren't yet. |
| **Deployment** (Docker, CI, a server) | Runs on a laptop today |
| **Call records and transcripts** | Nothing is stored about a call except the bookings. 30-day transcripts are planned (Stage 4). |
| **Backup vendor if one goes down** (no FallbackAdapter) | If Sarvam is down, calls fail. No "worker is down" alert either. |
| **Error tracking** | No Sentry-style alerts |
| **DPDP** (India's data protection law) | No retention policy, backups or privacy notice yet |
| **The full Sarvam stack has never done a complete booking call with tools** | The production stack is the least tested one |
| **Messages, callbacks, transfer to a human, SMS/WhatsApp confirmations, payments, reminders** | None built, which is why the robot is forbidden to promise them |
| **Roles inside a clinic** (owner vs front desk) | Not decided yet. Every team member can do everything for that clinic. |
| **Rate limits are in memory** | Fine for one server; several servers would need a shared store |

**Known rough edges:**

- The brain spells some names differently in Devanagari each time, so
  pronunciation varies.
- Patient names are stored as the ear wrote them, which can be Devanagari, on
  an English-only dashboard.
- When a tool errors, the brain sometimes makes up a reason.
- Several recent voice settings haven't been checked by ear yet: the
  interruption threshold (0.3 s), the pause length (0.6 s) and the Sarvam
  sentence cutting.

---

## 14. Trade-offs: the "why not X?" answers

| Choice | What you gain | What you give up |
|---|---|---|
| Ear, brain and mouth as separate parts (not one speech-to-speech model) | Pick the best Hindi vendor for each part, swap them, and see the text at every step | More delay than an all-in-one voice model |
| Sarvam in production | Built for Indian languages, Indian vendor | Costs money, and it's the least tested stack here |
| Thinking switched off on the LLM | Fast replies, and tools work | A less careful brain, hence all the safety nets in code |
| ElevenLabs `eleven_v3_conversational` | Most human-sounding | Slower than its flash models |
| Batch ear (`scribe_v2`) cut by the VAD | About 1 s after speech ends, vs about 3 s for the realtime model (one measurement) | Needs a tuned pause length, or it cuts people off |
| Local Silero VAD everywhere | Tests sound like production, and it's free | Not as smart as LiveKit's paid adaptive model |
| All free times sent to the brain | It can answer "anything later?" honestly | A longer reply for the brain to read |
| Double booking stopped by the database | Holds even if two calls race each other | Needs a special partial index (handled in migrations) |
| Browser link before telephony | Can demo and pilot now, with no number or server | No caller ID, and patients must click a link |
| One worker for all clinics | Cheap and simple | One bug or outage affects every clinic |
| Staff can override the rules | Real clinics squeeze in walk-ins | Staff can book outside hours (on purpose) |
| Refuse to start on an old database | Real data is never changed by surprise | The migrate command must be run after pulling |

---

## 15. Quick answers to likely questions

- **"How do you stop double booking?"** A unique rule in the database: one
  booked appointment per doctor per start time. Code can't bypass it, and the
  second caller is offered other times.
- **"What if the AI books the wrong thing?"** It can't book without first
  checking and reading back, and without the caller speaking after that. Code
  enforces this, not the instructions.
- **"How do you prevent hallucinated clinic info?"** The facts are generated
  fresh from the database for every call, and the robot is told to say only
  those. Free times only come from tools.
- **"What about privacy?"** Lookups need both number and name, failures all
  give the same message, lookups are capped at 3 per call, the reason is never
  read out, clinics can't see each other's data (IDOR checks), and sign-in is
  Google-verified emails only. The DPDP work isn't done yet.
- **"How do you add a new clinic?"** An admin creates it in the dashboard, and
  staff fill in doctors, hours and FAQ. There's no code change, no redeploy and
  no new worker.
- **"How do you swap an AI vendor?"** Change one line in `.env`. Adding a new
  vendor means one builder function in `providers/`.
- **"Latency?"** Raw audio output, no LLM thinking step, sentence-by-sentence
  speech, database work in a background thread, and a "one moment" filler
  while tools run.
- **"Emergencies?"** The robot tells the caller to call 108 or 112 immediately
  and gives no medical advice.
- **"Why should a clinic trust it?"** It says it's a robot, never promises what
  it can't do, and staff always have the final say in the dashboard.
