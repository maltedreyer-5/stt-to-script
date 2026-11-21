# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Prompt templates.

Two sets ship with the package: ``de`` for German texts, and ``generic`` with
English-language instructions that name the target language, used for every
other language. The prompts are fixed files rather than settings in the
interface, so that every user of an installation gets the same, reviewed
instructions; operators can replace individual files via ``PROMPT_DIR``
(same layout: ``<set>/<name>.txt``).

Placeholders are filled in a single pass. Filling them one after another
would also replace placeholder-like text that happens to occur in the
transcript or the context.
"""

from __future__ import annotations

import re
from functools import lru_cache
from importlib import resources
from pathlib import Path

PROMPT_SETS = ("de", "generic")
PASS_PROMPTS = ("correct_clean", "correct", "clean", "style", "structure", "rag")
OTHER_FILES = ("outline_prefix", "fallback_context")
PLACEHOLDERS = ("chunk", "context", "language", "outline")
_PLACEHOLDER = re.compile(r"\{(" + "|".join(PLACEHOLDERS) + r")\}")

# English language names, used inside the generic prompts.
LANGUAGE_NAMES = {
    "de": "German",
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "pl": "Polish",
}


class PromptError(ValueError):
    pass


def prompt_set_for(language: str) -> str:
    return "de" if language == "de" else "generic"


class PromptLibrary:
    def __init__(self, override_dir: Path | None = None):
        self.override_dir = override_dir

    def raw(self, prompt_set: str, name: str) -> str:
        return _load(prompt_set, name, str(self.override_dir) if self.override_dir else None)

    def render(
        self, name: str, language: str, *, chunk: str, context: str, outline: str = ""
    ) -> str:
        prompt_set = prompt_set_for(language)
        values = {
            "chunk": chunk,
            "context": context.strip() or self.raw(prompt_set, "fallback_context").strip(),
            "language": LANGUAGE_NAMES[language],
            "outline": outline,
        }
        template = self.raw(prompt_set, name)
        if outline and name == "structure":
            template = self.raw(prompt_set, "outline_prefix") + template
        return _PLACEHOLDER.sub(lambda m: values[m.group(1)], template)

    def validate(self) -> None:
        """Fail early if a file is missing or lacks a required placeholder."""
        for prompt_set in PROMPT_SETS:
            for name in PASS_PROMPTS:
                text = self.raw(prompt_set, name)
                for required in ("{chunk}", "{context}"):
                    if required not in text:
                        raise PromptError(f"prompt {prompt_set}/{name} lacks {required}")
                if prompt_set == "generic" and "{language}" not in text:
                    raise PromptError(f"prompt {prompt_set}/{name} lacks {{language}}")
            if "{outline}" not in self.raw(prompt_set, "outline_prefix"):
                raise PromptError(f"prompt {prompt_set}/outline_prefix lacks {{outline}}")
            self.raw(prompt_set, "fallback_context")


@lru_cache(maxsize=64)
def _load(prompt_set: str, name: str, override_dir: str | None) -> str:
    if prompt_set not in PROMPT_SETS or name not in PASS_PROMPTS + OTHER_FILES:
        raise PromptError(f"unknown prompt {prompt_set}/{name}")
    if override_dir:
        candidate = Path(override_dir) / prompt_set / f"{name}.txt"
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    resource = resources.files(__package__).joinpath("prompts", prompt_set, f"{name}.txt")
    try:
        return resource.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise PromptError(f"prompt file missing: {prompt_set}/{name}.txt") from None
