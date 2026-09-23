"""The agent's reply is voiced in pieces that end where a person pauses,
so the voice never restarts with a new tone mid-sentence."""

from clinic_agent.providers.sentences import MAX_PIECE, SentenceTokenizer, split_sentences


def texts(text):
    return [p[0] for p in split_sentences(text)]


def test_hindi_full_stop_ends_a_sentence():
    assert texts("आपका स्वागत है। मैं ऑटोमेटेड असिस्टेंट हूँ। बताइए?") == [
        "आपका स्वागत है।", "मैं ऑटोमेटेड असिस्टेंट हूँ।", "बताइए?",
    ]


def test_titles_and_decimals_are_not_sentence_ends():
    assert texts("Your appointment is with Dr. Asha Mehta at 5.30 pm. See you then!") == [
        "Your appointment is with Dr. Asha Mehta at 5.30 pm.", "See you then!",
    ]
    assert texts("The fee is 500. Anything else?") == ["The fee is 500.", "Anything else?"]


def test_a_long_sentence_is_cut_at_a_comma_before_a_space():
    sentence = "पहले आप रिसेप्शन पर पर्ची बनवाइए, " * 4 + "फिर " + "डॉक्टर साहब आपको देखेंगे " * 6 + "।"
    pieces = texts(sentence)
    assert len(pieces) > 1 and all(len(p) <= MAX_PIECE for p in pieces)
    assert pieces[0].endswith(",")  # the comma, not a word in the middle
    assert " ".join(pieces).replace(" ।", "।") == " ".join(sentence.split()).replace(" ।", "।")


def test_a_long_run_without_punctuation_is_cut_at_a_space():
    sentence = "बहुत लंबा वाक्य " * 30
    pieces = texts(sentence)
    assert all(len(p) <= MAX_PIECE for p in pieces)
    assert " ".join(pieces) == sentence.strip()  # no word split in half


def test_offsets_point_at_the_piece():
    text = "  जी।  आपका स्वागत है। "
    for piece, start, end in split_sentences(text):
        assert text[start:end] == piece


async def test_streamed_tokens_come_out_as_whole_sentences():
    # As on a call: the LLM's reply arrives a word at a time.
    reply = "नमस्ते जी, क्योर डेंटल क्लिनिक में आपका स्वागत है। मैं यहाँ की ऑटोमेटेड असिस्टेंट हूँ। बताइए, मैं क्या मदद करूँ?"
    stream = SentenceTokenizer().stream()
    for word in reply.split(" "):
        stream.push_text(word + " ")
    stream.end_input()
    pieces = [t.token async for t in stream]
    assert pieces == [
        "नमस्ते जी, क्योर डेंटल क्लिनिक में आपका स्वागत है।",
        "मैं यहाँ की ऑटोमेटेड असिस्टेंट हूँ।",
        "बताइए, मैं क्या मदद करूँ?",
    ]
