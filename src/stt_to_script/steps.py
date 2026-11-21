# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Processing steps, presets, and how selected steps map to LLM passes.

Steps always run in the fixed order of :data:`STEP_ORDER`. ``correct`` and
``clean`` together run as one pass with the combined prompt: both concern the
same words of a transcript, and combining keeps the presets at three passes.
"""

from __future__ import annotations

from dataclasses import dataclass

STEP_ORDER = ("preprocess", "correct", "clean", "style", "structure", "rag")
LLM_STEPS = STEP_ORDER[1:]

PRESETS: dict[str, tuple[str, ...]] = {
    "correction": ("correct", "clean"),
    "revision": ("correct", "clean", "style"),
    "formatting": ("correct", "clean", "style", "structure"),
    # No style pass: rewording does not help retrieval and can shift meaning.
    "rag": ("preprocess", "correct", "clean", "structure", "rag"),
}
DEFAULT_PRESET = "formatting"


@dataclass(frozen=True)
class Pass:
    name: str  # prompt name and label key
    steps: tuple[str, ...]  # steps this pass covers
    block_mode: bool  # the pass may add Markdown blocks (headings, paragraphs)


def normalise_steps(selected) -> tuple[str, ...]:
    unknown = set(selected) - set(STEP_ORDER)
    if unknown:
        raise ValueError(f"unknown steps: {sorted(unknown)}")
    return tuple(step for step in STEP_ORDER if step in selected)


def plan_passes(selected) -> list[Pass]:
    steps = normalise_steps(selected)
    passes: list[Pass] = []
    if "correct" in steps and "clean" in steps:
        passes.append(Pass("correct_clean", ("correct", "clean"), block_mode=False))
    elif "correct" in steps:
        passes.append(Pass("correct", ("correct",), block_mode=False))
    elif "clean" in steps:
        passes.append(Pass("clean", ("clean",), block_mode=False))
    if "style" in steps:
        passes.append(Pass("style", ("style",), block_mode=False))
    if "structure" in steps:
        passes.append(Pass("structure", ("structure",), block_mode=True))
    if "rag" in steps:
        passes.append(Pass("rag", ("rag",), block_mode=True))
    return passes


def preset_for(selected) -> str | None:
    steps = normalise_steps(selected)
    for name, preset_steps in PRESETS.items():
        if steps == preset_steps:
            return name
    return None
