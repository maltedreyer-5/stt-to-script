# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Chunking, reasoning filter and preprocessing: pure functions, no I/O."""

from __future__ import annotations

import random
from itertools import pairwise

import pytest

from stt_to_script.chunking import Segment, halve, join_segments, split_text
from stt_to_script.preprocess import detect_format, looks_like_subtitles, preprocess
from stt_to_script.reasoning import UnclosedReasoningError, strip_reasoning

# --- chunking ---------------------------------------------------------------

WORDS = "der die das Transkript Vorlesung Satz Wort äh also ja Beispiel".split()


def random_text(rng: random.Random, length: int) -> str:
    parts = []
    while sum(map(len, parts)) < length:
        roll = rng.random()
        if roll < 0.04:
            parts.append("\n\n")
        elif roll < 0.06:
            parts.append("\n")
        elif roll < 0.15:
            parts.append(rng.choice([". ", "! ", "? ", "… ", ".“ "]))
        elif roll < 0.17:
            parts.append("  ")
        else:
            parts.append(rng.choice(WORDS) + " ")
    return rng.choice(["", " ", "\n"]) + "".join(parts) + rng.choice(["", "\n", "  \n\n"])


def rebuild(segments: list[Segment]) -> str:
    return "".join(s.lead + s.core + s.trail for s in segments)


@pytest.mark.parametrize("seed", range(300))
def test_split_is_lossless_and_respects_limit(seed):
    rng = random.Random(seed)
    text = random_text(rng, rng.randint(50, 6000))
    limit = rng.randint(40, 1500)
    segments = split_text(text, limit)
    assert rebuild(segments) == text
    for segment in segments:
        assert segment.core and segment.core == segment.core.strip()
        assert len(segment.core) <= limit


@pytest.mark.parametrize("seed", range(100))
def test_split_never_cuts_inside_a_word_when_whitespace_exists(seed):
    rng = random.Random(1000 + seed)
    text = random_text(rng, 3000)
    segments = split_text(text, rng.randint(60, 600))
    for left, right in pairwise(segments):
        assert left.trail and left.trail.strip() == ""
        assert not right.lead


def test_split_prefers_paragraph_breaks():
    text = ("Satz eins ist hier. " * 20).strip() + "\n\n" + ("Satz zwei folgt. " * 20).strip()
    segments = split_text(text, len(text) - 10)
    assert segments[0].trail == "\n\n"
    assert segments[0].core.endswith("hier.")


def test_closing_quote_stays_with_its_sentence():
    text = "Er sagte: „Das ist so.“ Danach " + "ging es weiter mit vielen Worten. " * 5
    first = split_text(text, 30)[0]
    assert first.core.endswith("„Das ist so.“")


def test_word_longer_than_limit_is_hard_cut_without_loss():
    text = "kurz " + "x" * 50 + " ende"
    segments = split_text(text, 20)
    assert rebuild(segments) == text
    assert all(len(s.core) <= 20 for s in segments)


def test_empty_and_whitespace_text_gives_no_segments():
    assert split_text("", 10) == []
    assert split_text(" \n\n ", 10) == []


def test_halve_is_lossless():
    text = "Eins zwei drei. Vier fünf sechs. Sieben acht neun. Zehn elf zwölf."
    segment = Segment("\n", text, "  ")
    parts = halve(segment)
    assert len(parts) == 2
    assert rebuild(parts) == rebuild([segment])
    assert parts[0].lead == "\n" and parts[1].trail == "  "


def test_join_in_block_mode_adds_paragraph_breaks_only_at_seams():
    segments = [Segment("", "Ende eines Satzes.", " "), Segment("", "## Überschrift\nText", "\n")]
    assert join_segments(segments) == "Ende eines Satzes. ## Überschrift\nText\n"
    assert (
        join_segments(segments, block_mode=True) == "Ende eines Satzes.\n\n## Überschrift\nText\n"
    )


# --- reasoning filter ---------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Nur Antwort.", "Nur Antwort."),
        ("<think>Überlegung</think>\nAntwort.", "Antwort."),
        ("<think>a</think>Teil 1 <think>b</think>Teil 2", "Teil 1 Teil 2"),
        ("Überlegung ohne Anfangstag</think>\n\nAntwort.", "Antwort."),
        ("<thinking>x</thinking>Antwort", "Antwort"),
        ("◁think▷x◁/think▷Antwort", "Antwort"),
        ("[THINK]x[/THINK]Antwort", "Antwort"),
    ],
)
def test_strip_reasoning(raw, expected):
    assert strip_reasoning(raw) == expected


def test_closing_tag_cut_uses_first_occurrence():
    # Cutting at the last tag would delete answer text that mentions the tag.
    assert strip_reasoning("r</think>Antwort über </think> Tags") == "Antwort über </think> Tags"


@pytest.mark.parametrize("raw", ["<think>abgeschnitten mitten im", "Text <thinking>offen"])
def test_unclosed_reasoning_raises(raw):
    with pytest.raises(UnclosedReasoningError):
        strip_reasoning(raw)


# --- preprocessing ------------------------------------------------------------

SRT = """1
00:00:01,000 --> 00:00:03,000
SPEAKER_00: Guten Morgen und

2
00:00:03,100 --> 00:00:05,000
willkommen zur Vorlesung.

3
00:00:09,000 --> 00:00:11,000
SPEAKER_01: Danke schön.
"""

VTT = """WEBVTT
Kind: captions

NOTE Diese Notiz gehört nicht zum Text.

00:01.000 --> 00:03.000 align:start
<v Prof. Meier>Heute geht es um <i>Statistik</i>.

intro-2
00:03.500 --> 00:05.000
<v Prof. Meier>Fangen wir an.
"""


def test_srt_cues_become_paragraphs_with_speakers():
    result = preprocess(SRT, keep_speakers=True)
    assert result.source_format == "srt"
    assert result.text == (
        "SPEAKER_00: Guten Morgen und willkommen zur Vorlesung.\n\nSPEAKER_01: Danke schön.\n"
    )
    assert result.cues == 3 and result.speakers == 2


def test_srt_without_speakers():
    result = preprocess(SRT, keep_speakers=False)
    assert "SPEAKER" not in result.text
    assert "-->" not in result.text and "00:00" not in result.text


def test_vtt_voice_tags_notes_and_inline_tags():
    result = preprocess(VTT, keep_speakers=True)
    assert result.source_format == "vtt"
    assert result.text == "Prof. Meier: Heute geht es um Statistik. Fangen wir an.\n"


def test_whisper_style_timestamps():
    text = (
        "[00:00:00.000 --> 00:00:02.000]  Erster Teil\n"
        "[00:00:02.000 --> 00:00:04.000]  zweiter Teil.\n"
    )
    result = preprocess(text)
    assert result.source_format == "timestamped"
    assert result.text == "Erster Teil zweiter Teil.\n"


def test_rolling_captions_are_merged():
    text = (
        "00:00:01.000 --> 00:00:02.000\nwir beginnen heute mit\n\n"
        "00:00:02.000 --> 00:00:03.000\nwir beginnen heute mit der Statistik\n\n"
        "00:00:03.000 --> 00:00:03.010\nwir beginnen heute mit der Statistik\n"
    )
    assert preprocess(text).text == "wir beginnen heute mit der Statistik\n"


def test_genuine_repetitions_are_kept():
    text = (
        "00:00:01.000 --> 00:00:02.000\nJa.\n\n"
        "00:00:02.000 --> 00:00:03.000\nJa. Genau so.\n\n"
        "00:00:03.000 --> 00:00:04.000\nDas ist wichtig.\n\n"
        "00:00:04.000 --> 00:00:05.000\nDas ist wichtig.\n"
    )
    assert preprocess(text).text == "Ja. Ja. Genau so. Das ist wichtig. Das ist wichtig.\n"


def test_plain_text_keeps_content_and_generic_name_labels():
    text = "Hinweis: Das bleibt.\nSprecher 2: Das auch.\n\n\n\nEnde."
    kept = preprocess(text, keep_speakers=True)
    removed = preprocess(text, keep_speakers=False)
    assert kept.source_format == "plain"
    assert kept.text == "Hinweis: Das bleibt.\nSprecher 2: Das auch.\n\nEnde.\n"
    assert removed.text == "Hinweis: Das bleibt.\nDas auch.\n\nEnde.\n"


def test_detection():
    assert detect_format(SRT) == "srt"
    assert detect_format(VTT) == "vtt"
    assert not looks_like_subtitles("Um 10:30 Uhr begann die Sitzung.\nDann folgte der Vortrag.")


# --- enclosing code fence -----------------------------------------------------

from stt_to_script.reasoning import strip_wrapping_fence  # noqa: E402


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("```markdown\n## Teil\n\nText.\n```", "## Teil\n\nText."),
        ("```\nText.\n```\n", "Text."),
        ("Text mit ```code``` darin.", "Text mit ```code``` darin."),
        ("```\nA\n```\n\nB", "```\nA\n```\n\nB"),
        ("```python\na\n```\n```\nb\n```", "```python\na\n```\n```\nb\n```"),
    ],
)
def test_only_a_fence_around_the_whole_answer_is_removed(raw, expected):
    assert strip_wrapping_fence(raw) == expected


# --- language identification ------------------------------------------------

from stt_to_script.language import identify  # noqa: E402

SAMPLES = {
    "de": "Wir haben heute in der Vorlesung über die Messreihen gesprochen, und das ist für die Klausur nicht unwichtig. ",
    "en": "We talked about the measurements today, and it is important that you have this for the exam. ",
    "fr": "Nous avons parlé des mesures dans le cours, et il est important que ce soit clair pour l'examen. ",
    "es": "Hoy hablamos de las mediciones en la clase, y es importante que se entienda para el examen, pero con calma. ",
    "it": "Oggi abbiamo parlato delle misure, ed è importante che non si dimentichi per l'esame con la classe. ",
    "pt": "Hoje falamos das medições na aula, e é importante que isso fique claro para o exame, também em casa. ",
    "nl": "We hebben het vandaag over de metingen gehad, en het is belangrijk dat je dat voor het examen ook weet. ",
    "pl": "Dzisiaj mówiliśmy o pomiarach na wykładzie i to jest ważne, że nie można tego pominąć na egzaminie. ",
}


@pytest.mark.parametrize("lang", sorted(SAMPLES))
def test_language_of_a_transcript_is_identified(lang):
    assert identify(SAMPLES[lang] * 8) == lang


def test_short_or_mixed_text_gives_no_verdict():
    assert identify("Statistik 2026") is None
    assert identify(SAMPLES["de"] + SAMPLES["en"]) is None
