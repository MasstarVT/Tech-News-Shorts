from technews.config import VoiceConfig
from technews.voice.speech import four_digits, spoken_text, to_speech

PRON = VoiceConfig().pronunciations


def say(text: str) -> str:
    return spoken_text(to_speech(text, PRON))


def test_money_moves_currency_after_magnitude():
    assert say("Nvidia passed $5 trillion in value.") == "Nvidia passed 5 trillion dollars in value."
    assert say("A $2.5B deal") == "A 2 point 5 billion dollars deal"
    assert say("It costs $1 or €300M.") == "It costs 1 dollar or 300 million euros."


def test_multipliers_units_and_model_numbers():
    assert say("It's 3.5x faster") == "It's 3 point 5 times faster"
    assert say("A 120Hz screen and 16GB") == "A 120 hertz screen and 16 gigabytes"
    assert say("The RTX 5090 and Ryzen 9950X") == "The RTX 50 90 and Ryzen 99 50 X"


def test_four_digit_numbers_read_like_people_say_them():
    assert four_digits(2026) == "20 26"
    assert four_digits(1500) == "15 hundred"
    assert four_digits(2000) == "2000"
    assert four_digits(2005) == "2005"
    assert four_digits(1080) == "10 80"


def test_pronunciations_and_possessives():
    assert say("Apple vs. Google in the U.S.") == "Apple versus Google in the U S"
    assert say("Xiaomi's EVs") == "shao-mee's E Vees"


def test_tokens_keep_caption_text_and_punctuation():
    tokens = to_speech('He said "huge" (really).', PRON)
    assert [t.text for t in tokens] == ["He", "said", '"huge"', "(really)."]
    assert [t.spoken for t in tokens] == ["He", "said", "huge", "really."]


def test_silent_tokens():
    tokens = to_speech("Fast — really", PRON)
    assert tokens[1].text == "—"
    assert tokens[1].spoken == "—"
    assert spoken_text(tokens) == "Fast — really"
