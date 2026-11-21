# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Removing reasoning blocks and an enclosing code fence from model output.

Servers with a reasoning parser return the reasoning in a separate field,
which this tool never reads. Without such a parser the reasoning arrives
inside ``content``, wrapped in one of the tag pairs below. Three cases:

1. Complete blocks are removed.
2. A closing tag without an opening tag means the chat template opened the
   block inside the prompt; everything up to the first closing tag is
   reasoning. The first one is used, not the last: if the answer itself
   contained the tag, cutting at the last would silently delete answer text.
3. An opening tag that is never closed means the output ended inside the
   reasoning, i.e. it was truncated. That is an error, never an empty answer.

Some models also return Markdown inside a fenced code block. A fence is removed
only if it encloses the whole answer and no other fence occurs inside it.
"""

from __future__ import annotations

import re

TAG_PAIRS = (
    ("<think>", "</think>"),
    ("<thinking>", "</thinking>"),
    ("◁think▷", "◁/think▷"),
    ("[THINK]", "[/THINK]"),
)


_WRAPPING_FENCE = re.compile(r"\A```[\w+-]*[ \t]*\n(.*)\n```[ \t]*\Z", re.DOTALL)


class UnclosedReasoningError(ValueError):
    """The model output ends inside a reasoning block."""


def strip_reasoning(text: str) -> str:
    for opening, closing in TAG_PAIRS:
        if opening not in text and closing not in text:
            continue
        pattern = re.compile(re.escape(opening) + r".*?" + re.escape(closing), re.DOTALL)
        text = pattern.sub("", text)
        if closing in text:
            text = text[text.index(closing) + len(closing) :]
        if opening in text:
            raise UnclosedReasoningError(opening)
    return text.strip()


def strip_wrapping_fence(text: str) -> str:
    """Remove one code fence that encloses the whole answer."""
    match = _WRAPPING_FENCE.match(text.strip())
    if match and "```" not in match.group(1):
        return match.group(1).strip()
    return text
