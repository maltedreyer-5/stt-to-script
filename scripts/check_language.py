# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Check that the repository is in English outside the places meant for German.

German is expected in exactly three places, which are therefore skipped:

* the ``"de"`` entries of ``MESSAGES`` in ``src/stt_to_script/i18n.py``;
* the German prompt set in ``src/stt_to_script/prompts/de/``;
* string literals in ``tests/`` (sample transcripts and prompt markers).

Everything else is checked: Python comments, docstrings, identifiers and the
remaining string literals (found with ``tokenize`` and ``ast``, not by text
search), plus all Markdown, YAML, TOML, CFF and text files. The detector looks
for German letters and common German function words. It is a heuristic;
findings have to be reviewed.

Usage: python scripts/check_language.py [--verbose]
"""

from __future__ import annotations

import ast
import io
import re
import subprocess
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GERMAN = re.compile(
    r"[äöüÄÖÜß]|\b(und|der|die|das|nicht|ist|mit|für|auf|eine|einen|einer|werden|wird|oder|"
    r"wenn|dass|nach|bei|keine|kein|über|sich|auch|zum|zur|Sie|Datei|Fehler|Verarbeitung)\b"
)
TEXT_SUFFIXES = {".md", ".yml", ".yaml", ".toml", ".cff", ".txt", ".cfg", ".ini"}
SKIP_DIRS = {"prompts/de"}
NOT_CHECKED = {"RELEASE-CHECKLIST.md"}  # handover note, written in German, never committed
# Module-level constants whose value is German on purpose: (file, constant name).
ALLOWED_CONSTANTS = {
    ("scripts/check_language.py", "GERMAN"),
    ("src/stt_to_script/language.py", "_FUNCTION_WORDS"),  # function words of eight languages
}


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],  # noqa: S607
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return [ROOT / line for line in out.splitlines() if line]
    except (OSError, subprocess.CalledProcessError):
        ignored = {
            ".git",
            ".venv",
            "venv",
            "build",
            "dist",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
        }
        return [
            p
            for p in ROOT.rglob("*")
            if p.is_file() and not ignored & set(p.relative_to(ROOT).parts)
        ]


def german_de_values(tree: ast.AST) -> set[int]:
    """ids of string nodes that are the value of a "de" key in a dict literal."""
    allowed = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values, strict=True):
                if isinstance(key, ast.Constant) and key.value == "de":
                    allowed.update(id(n) for n in ast.walk(value))
    return allowed


def allowed_constants(tree: ast.AST, rel: str) -> set[int]:
    allowed = set()
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Assign):
            names = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if any((rel, name) in ALLOWED_CONSTANTS for name in names):
                allowed.update(id(n) for n in ast.walk(node.value))
    return allowed


def docstring_nodes(tree: ast.AST) -> set[int]:
    nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                nodes.add(id(body[0].value))
    return nodes


def check_python(path: Path, rel: str) -> list[tuple[int, str, str]]:
    source = path.read_text(encoding="utf-8")
    findings = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT and GERMAN.search(token.string):
            findings.append((token.start[0], "comment", token.string.strip()))
    tree = ast.parse(source)
    docstrings = docstring_nodes(tree)
    allowed = allowed_constants(tree, rel)
    if rel == "src/stt_to_script/i18n.py":
        allowed |= german_de_values(tree)
    in_tests = rel.startswith("tests/")
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Name, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.arg)
        ):
            name = (
                getattr(node, "id", None) or getattr(node, "name", None) or getattr(node, "arg", "")
            )
            if GERMAN.search(name.replace("_", " ")):
                findings.append((node.lineno, "identifier", name))
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            kind = "docstring" if id(node) in docstrings else "string"
            if kind == "string" and (in_tests or id(node) in allowed):
                continue
            match = GERMAN.search(node.value)
            if match:
                findings.append((node.lineno, kind, node.value.strip()[:80]))
    return findings


def check_text(path: Path) -> list[tuple[int, str, str]]:
    findings = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if GERMAN.search(line):
            findings.append((number, "text", line.strip()[:80]))
    return findings


def main() -> int:
    verbose = "--verbose" in sys.argv
    findings, skipped = [], []
    for path in sorted(tracked_files()):
        rel = path.relative_to(ROOT).as_posix()
        if rel in NOT_CHECKED or any(rel.startswith(f"src/stt_to_script/{d}/") for d in SKIP_DIRS):
            skipped.append(rel)
            continue
        if path.suffix == ".py":
            findings += [(rel, *f) for f in check_python(path, rel)]
        elif path.suffix in TEXT_SUFFIXES:
            findings += [(rel, *f) for f in check_text(path)]
    for rel, line, kind, text in findings:
        print(f"{rel}:{line}: German-looking {kind}: {text}")
    if verbose:
        print(f"skipped by design: {', '.join(skipped) or 'none'}")
    print(f"check_language: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
