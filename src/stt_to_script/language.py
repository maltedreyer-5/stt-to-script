# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Rough identification of the language of a transcript.

Counts frequent function words of the eight supported languages. The result
is only used for a warning when the text does not appear to be in the
language selected for it; processing always follows the selection. A result
is reported only when it is clear: enough function words, and clearly more
for one language than for the next.
"""

from __future__ import annotations

import re

_FUNCTION_WORDS = {
    "de": "der die das und ist nicht ein eine wir ich es mit auch auf für von zu den dem sich",
    "en": "the and is are of to that we it this with for not you be have was on",
    "fr": "le la les des est et une un que pas nous dans pour sur il elle ce qui",
    "es": "el la los las de que y en un una es por con para del se lo pero",
    "it": "il la le di che e un una non è per sono con della del anche si gli",
    "pt": "o a os as de que e um uma não é com para do da em mais também são",
    "nl": "de het een en van is niet dat zijn voor ook op met die we ik er",
    "pl": "i w nie się na jest to że z do jak co tak ale czy od po",
}
WORDS = {lang: frozenset(words.split()) for lang, words in _FUNCTION_WORDS.items()}
MIN_HITS = 20
MIN_RATIO = 1.5
_TOKEN = re.compile(r"[^\W\d_]+")


def identify(text: str, sample_chars: int = 20_000) -> str | None:
    """Language code of ``text`` if it is clear, else ``None``."""
    tokens = [token.lower() for token in _TOKEN.findall(text[:sample_chars])]
    scores = sorted(
        ((sum(t in words for t in tokens), lang) for lang, words in WORDS.items()), reverse=True
    )
    (best, lang), (second, _) = scores[0], scores[1]
    if best >= MIN_HITS and best >= MIN_RATIO * max(second, 1):
        return lang
    return None
