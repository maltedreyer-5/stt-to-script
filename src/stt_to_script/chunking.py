# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Lossless splitting of text into segments for the LLM.

Invariant: ``"".join(s.lead + s.core + s.trail for s in split_text(t, n)) == t``.

Only ``core`` is sent to the model. The whitespace around it (``lead`` and
``trail``) is kept aside and restored when the results are joined, so seams
keep their original separator. There is no overlap between segments: an
overlap would be processed twice and appear twice in the result.

A split point is searched backwards from the size limit, in this order of
preference: paragraph break, line break, sentence end, any whitespace. Each
kind is only accepted if it leaves the segment reasonably full, otherwise the
next kind is tried. A hard cut inside a word only happens for a single
"word" longer than the limit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PARAGRAPH = re.compile(r"\n[ \t]*\n\s*")
_LINE = re.compile(r"\n\s*")
# Sentence end: terminal punctuation, optional closing quotes/brackets, whitespace.
_SENTENCE = re.compile(r"(?<=[.!?…])[\"'»«”“’)\]]*\s+")
_SPACE = re.compile(r"\s+")

# Minimum fill (fraction of max_chars) for each kind of split point.
_PREFERENCES = ((_PARAGRAPH, 0.5), (_LINE, 0.5), (_SENTENCE, 0.3), (_SPACE, 0.0))


@dataclass(frozen=True)
class Segment:
    lead: str
    core: str
    trail: str

    def with_core(self, core: str) -> Segment:
        return Segment(self.lead, core, self.trail)


def split_text(text: str, max_chars: int) -> list[Segment]:
    """Split ``text`` into segments whose core is at most ``max_chars`` long."""
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    stripped = text.strip()
    if not stripped:
        return []
    start = text.index(stripped[0])
    end = start + len(stripped)
    lead_all, trail_all = text[:start], text[end:]

    pieces: list[tuple[str, str]] = []  # (core, separator after it)
    pos = start
    while pos < end:
        if end - pos <= max_chars:
            pieces.append((text[pos:end], ""))
            break
        cut, sep_end = _find_cut(text, pos, min(pos + max_chars, end))
        pieces.append((text[pos:cut], text[cut:sep_end]))
        pos = sep_end

    segments = []
    for index, (core, sep) in enumerate(pieces):
        lead = lead_all if index == 0 else ""
        trail = trail_all if index == len(pieces) - 1 else sep
        segments.append(Segment(lead, core, trail))
    return segments


def _find_cut(text: str, pos: int, limit: int) -> tuple[int, int]:
    """Return (end of core, end of separator) for a segment starting at ``pos``."""
    size = limit - pos
    window = text[pos : limit + 1]  # +1 so whitespace right at the limit counts
    for pattern, min_fill in _PREFERENCES:
        candidates = [m.start() for m in pattern.finditer(window) if 0 < m.start() <= size]
        for relative in reversed(candidates):
            # The separator is the whitespace run at or after the match; closing
            # quotes after a full stop stay with the sentence they close.
            run = _SPACE.search(text, pos + relative)
            if run is None:
                continue
            cut = run.start()
            while cut > pos and text[cut - 1].isspace():
                cut -= 1
            if cut <= pos or cut - pos > size:
                continue
            if cut - pos < size * min_fill:
                break  # all remaining candidates of this kind are even earlier
            return cut, run.end()
    return limit, limit  # one "word" longer than the limit


def join_segments(segments: list[Segment], block_mode: bool = False) -> str:
    """Join processed segments, restoring the original separators.

    In ``block_mode`` (used after passes that add Markdown structure), a seam
    without a paragraph break gets one, so that a heading produced at the
    start of a segment never ends up glued to the previous sentence.
    """
    parts = []
    last = len(segments) - 1
    for index, segment in enumerate(segments):
        trail = segment.trail
        if block_mode and index < last and "\n\n" not in trail:
            trail = "\n\n"
        parts.append(segment.lead + segment.core + trail)
    return "".join(parts)


def halve(segment: Segment) -> list[Segment]:
    """Split one segment into two near the middle, keeping its outer whitespace.

    Returns the segment unchanged (as a one-element list) if it cannot be split.
    """
    core = segment.core
    if len(core) < 2:
        return [segment]
    cut, sep_end = _find_cut(core, 0, (len(core) + 1) // 2)
    if cut <= 0 or sep_end >= len(core):
        return [segment]
    return [
        Segment(segment.lead, core[:cut], core[cut:sep_end]),
        Segment("", core[sep_end:], segment.trail),
    ]
