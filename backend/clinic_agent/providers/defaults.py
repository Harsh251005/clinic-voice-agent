"""What each vendor uses when its setting is left blank, in one place: the
builders read it, and the dashboard shows it beside each blank field."""

SARVAM_LLM_MODEL = "sarvam-105b-conversations"
OPENAI_LLM_MODEL = "gpt-4.1-mini"  # Harsh, 2026-10-13: fastest capable model
SARVAM_STT_MODEL = "saaras:v3"
SARVAM_STT_LANGUAGE = "unknown"  # auto-detects per utterance (Hinglish)
SARVAM_TTS_MODEL = "bulbul:v3"
SARVAM_TTS_SPEAKER = "suhani"

BLANK_MEANS = {
    "sarvam_llm_model": SARVAM_LLM_MODEL,
    "openai_llm_model": OPENAI_LLM_MODEL,
    "sarvam_stt_model": SARVAM_STT_MODEL,
    "sarvam_stt_language": SARVAM_STT_LANGUAGE,
    "tts_model": SARVAM_TTS_MODEL,
    "tts_speaker": SARVAM_TTS_SPEAKER,
}
