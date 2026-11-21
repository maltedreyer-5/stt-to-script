# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Step 0: deterministic clean-up before any LLM pass.

Handles SubRip (.srt), WebVTT (.vtt) and plain transcripts whose lines start
with timestamps (as written by Whisper and similar tools). Cue text is joined
into paragraphs; a new paragraph starts when the speaker changes or when
there is a pause of at least ``PARAGRAPH_GAP_SECONDS`` between cues.

Speaker labels are only recognised in explicit forms (``SPEAKER_00:``,
``Speaker 1:``, the equivalents in the supported languages, and WebVTT voice
tags). A generic ``Name:`` at the start of a line is left alone, because it is
indistinguishable from ordinary text such as ``Note:``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

PARAGRAPH_GAP_SECONDS = 2.0
TRANSITION_CUE_SECONDS = 0.5
ROLLING_MIN_WORDS = 3

_TS = r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?:[.,](\d{1,3}))?"
_TIMING_LINE = re.compile(rf"^\s*{_TS}\s*-->\s*{_TS}(?:\s+.*)?$")
_LEADING_TIMESTAMP = re.compile(rf"^\s*[\[(]?{_TS}(?:\s*-->\s*{_TS})?[\])]?(?=\s|$)\s*")
_SPEAKER_WORDS = (
    "SPEAKER|Speaker|Sprecher|Sprecherin|Locuteur|Locutrice|Intervenant|Hablante|"
    "Orador|Oradora|Oratore|Parlante|Falante|Spreker|Mówca"
)
_SPEAKER_LABEL = re.compile(rf"^\s*\[?((?:{_SPEAKER_WORDS})[ _]?\d+)\]?\s*:\s*")
_VOICE_TAG = re.compile(r"<v(?:\.[^\s>]*)?\s+([^>]+)>")
_ANY_TAG = re.compile(r"</?[^>\s][^>]*>")
_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u2060\ufeff"))
_VTT_SKIP_BLOCKS = ("WEBVTT", "NOTE", "STYLE", "REGION")


@dataclass
class Cue:
    text: str
    start: float | None = None
    end: float | None = None
    speaker: str | None = None


@dataclass(frozen=True)
class PreprocessResult:
    text: str
    source_format: str  # "srt", "vtt", "timestamped" or "plain"
    cues: int
    speakers: int


def detect_format(text: str) -> str:
    stripped = text.lstrip("\ufeff \n")
    if stripped.startswith("WEBVTT"):
        return "vtt"
    lines = [line for line in text.split("\n") if line.strip()]
    if not lines:
        return "plain"
    timing = sum(1 for line in lines if _TIMING_LINE.match(line))
    if timing and timing * 4 >= len(lines) and any(line.strip().isdigit() for line in lines[:3]):
        return "srt"
    if timing and timing * 4 >= len(lines):
        return "srt"  # SRT without cue numbers parses the same way
    leading = sum(1 for line in lines if _LEADING_TIMESTAMP.match(line))
    if leading * 2 >= len(lines):
        return "timestamped"
    return "plain"


def looks_like_subtitles(text: str) -> bool:
    """True if step 0 is required because the text contains cue timings."""
    return detect_format(text) != "plain"


def preprocess(text: str, keep_speakers: bool = True) -> PreprocessResult:
    text = text.translate(_INVISIBLE)
    source_format = detect_format(text)
    if source_format in ("srt", "vtt"):
        cues = _parse_blocks(text, source_format)
    elif source_format == "timestamped":
        cues = _parse_timestamped_lines(text)
    else:
        return _preprocess_plain(text, keep_speakers)
    cues = _drop_rolling_duplicates(cues)
    paragraphs = _join_cues(cues, keep_speakers)
    speakers = len({cue.speaker for cue in cues if cue.speaker})
    return PreprocessResult(_normalise("\n\n".join(paragraphs)), source_format, len(cues), speakers)


def _seconds(groups: tuple[str | None, ...]) -> float:
    hours, minutes, seconds, millis = groups
    return (
        int(hours or 0) * 3600
        + int(minutes) * 60
        + int(seconds)
        + int((millis or "0").ljust(3, "0")) / 1000
    )


def _split_speaker(line: str, speaker: str | None) -> tuple[str, str | None]:
    voice = _VOICE_TAG.search(line)
    if voice:
        speaker = voice.group(1).strip()
    line = _ANY_TAG.sub("", line)
    label = _SPEAKER_LABEL.match(line)
    if label:
        speaker = label.group(1)
        line = line[label.end() :]
    return line.strip(), speaker


def _parse_blocks(text: str, source_format: str) -> list[Cue]:
    cues: list[Cue] = []
    for block in re.split(r"\n\s*\n", text):
        lines = [line for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        if source_format == "vtt" and lines[0].strip().startswith(_VTT_SKIP_BLOCKS):
            continue
        timing_index = next((i for i, line in enumerate(lines) if _TIMING_LINE.match(line)), None)
        if timing_index is None:
            # Text without timing: continuation of the previous cue.
            content, speaker = _join_lines(lines, cues[-1].speaker if cues else None)
            if cues and content:
                cues[-1].text = f"{cues[-1].text} {content}".strip()
            elif content:
                cues.append(Cue(content, speaker=speaker))
            continue
        match = _TIMING_LINE.match(lines[timing_index])
        groups = match.groups()
        content, speaker = _join_lines(lines[timing_index + 1 :], None)
        if content:
            cues.append(Cue(content, _seconds(groups[0:4]), _seconds(groups[4:8]), speaker))
    return cues


def _join_lines(lines: list[str], speaker: str | None) -> tuple[str, str | None]:
    parts = []
    for line in lines:
        content, speaker = _split_speaker(line, speaker)
        if content:
            parts.append(content)
    return " ".join(parts), speaker


def _parse_timestamped_lines(text: str) -> list[Cue]:
    cues: list[Cue] = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        match = _LEADING_TIMESTAMP.match(line)
        if match:
            groups = match.groups()
            start = _seconds(groups[0:4])
            end = _seconds(groups[4:8]) if groups[5] is not None else None
            content, speaker = _split_speaker(line[match.end() :], None)
            cues.append(Cue(content, start, end, speaker))
        elif cues:
            content, speaker = _split_speaker(line, cues[-1].speaker)
            cues[-1].text = f"{cues[-1].text} {content}".strip()
            cues[-1].speaker = speaker
        else:
            content, speaker = _split_speaker(line, None)
            cues.append(Cue(content, speaker=speaker))
    return [cue for cue in cues if cue.text]


def _drop_rolling_duplicates(cues: list[Cue]) -> list[Cue]:
    """Undo the repetition in automatically generated "rolling" captions.

    Two patterns are removed: a cue that starts by repeating the whole previous
    cue (at least ``ROLLING_MIN_WORDS`` words), and an identical copy shown only
    for a moment (shorter than ``TRANSITION_CUE_SECONDS``). An identical cue of
    normal length is kept: speakers do repeat themselves, and dropping it would
    silently lose text.
    """
    result: list[Cue] = []
    previous: str | None = None  # text of the previous cue as it appeared on screen
    for cue in cues:
        shown = cue.text
        if previous is not None and shown == previous:
            duration = None if cue.start is None or cue.end is None else cue.end - cue.start
            if duration is not None and duration < TRANSITION_CUE_SECONDS:
                continue
        elif (
            previous is not None
            and len(previous.split()) >= ROLLING_MIN_WORDS
            and shown.startswith(previous + " ")
        ):
            cue.text = shown[len(previous) :].strip()
        previous = shown
        if cue.text:
            result.append(cue)
    return result


def _join_cues(cues: list[Cue], keep_speakers: bool) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []
    current_speaker: str | None = None
    previous_end: float | None = None
    for cue in cues:
        speaker_changed = cue.speaker is not None and cue.speaker != current_speaker
        pause = (
            previous_end is not None
            and cue.start is not None
            and cue.start - previous_end >= PARAGRAPH_GAP_SECONDS
        )
        if current and (speaker_changed or pause):
            paragraphs.append(" ".join(current))
            current = []
        if not current and keep_speakers and cue.speaker:
            current.append(f"{cue.speaker}:")
        current.append(cue.text)
        if cue.speaker is not None:
            current_speaker = cue.speaker
        previous_end = cue.end if cue.end is not None else cue.start
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


def _preprocess_plain(text: str, keep_speakers: bool) -> PreprocessResult:
    lines = []
    speakers = set()
    for line in text.split("\n"):
        label = _SPEAKER_LABEL.match(line)
        if label:
            speakers.add(label.group(1))
            if not keep_speakers:
                line = line[label.end() :]
        lines.append(line)
    return PreprocessResult(_normalise("\n".join(lines)), "plain", 0, len(speakers))


def _normalise(text: str) -> str:
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"
