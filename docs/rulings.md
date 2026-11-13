# Harsh's rulings

Product decisions Harsh made, with dates. In the `CLAUDE.md` files a rule
marked **†** is one of these: change it only when he asks.

| Date | Ruling | Where it lives |
|---|---|---|
| 2026-09-25 | Local Silero VAD, interruption mode `"vad"` | `session.py` |
| 2026-09-28 | Alerts stay in the website (banner, bell, "(!)" in the tab) | `incidents.py` |
| 2026-10-13 | Prices are data edited on the admin Prices page, never in code | `costs.py` |
| 2026-10-13 | OpenAI default model `gpt-4.1-mini` (≈1.0 s first token vs `gpt-6-luna` 1.6 s) | `providers/llm.py` |
| 2026-10-24 | The default rules stay under 500 words | `prompts.py`, `test_the_rules_stay_short` |
| 2026-11-08 | One language line, Hindi: reliable and production-ready before anything else | `lines.py`, decision #13 |
| 2026-11-09 | Any voice-clip problem → the phrase is said live (reliability over savings) | `voice_clips.py` |
| 2026-11-09 | No required wording in a greeting; he handles what callers are told | `voice_clips.py` |
| 2026-11-09 | A problem closes only on proof it is fixed, never by a click or timer alone | `incidents.py` |
| 2026-11-09 | The model judges whether the reason fits the doctor's specialty | `booking.py` (`fit_gate`) |
| 2026-11-10 | Receptionist behaviour lives in the database, set in the dashboard | `receptionist_settings.py` |
| 2026-11-10 | A tool that can't answer is answered by the code (`give_up`) | `tools/booking.py` |
| 2026-11-12 | The sorry line is for a stuck model, never for a caller who simply asks again | `tools/booking.py` |
| 2026-11-13 | She answers in Hindi, Hinglish or English, never any other language (replaces "a caller asking for English is told it's Hindi only"; still one line) | `prompts.py` (Language rules) |
| 2026-11-12 | A renamed clinic or doctor gets its Hindi name written again from the English one | `api/dashboard/hindi.py` (`left_behind`) |
| 2026-11-13 | The caller's gender is never guessed: wording with no gender first, else the everyday polite "चाहेंगे", never "चाहती हैं" | `prompts.py` (Language) |
