# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Documentation and release metadata against the code, and project invariants."""

from __future__ import annotations

import ast
import dataclasses
import io
import re
import tokenize
from pathlib import Path

import gradio as gr
import pytest
from conftest import make_settings

from stt_to_script import __version__
from stt_to_script.config import PREFIX, Settings
from stt_to_script.steps import STEP_ORDER
from stt_to_script.ui import App

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN = sorted(
    p
    for p in ROOT.rglob("*.md")
    if not {".venv", "venv", "node_modules", ".pytest_cache"} & set(p.parts)
    and p.name != "RELEASE-CHECKLIST.md"
)
HISTORY = re.compile(
    r"(?i)\b(since version|since v\d|in version \d|fixed in|formerly|previously|used to be|"
    r"no longer|anymore|was changed|has been changed|old version|earlier version|"
    r"backwards? compatib|legacy)\b"
)


def default_text(value) -> str:
    if value is None:
        return "unset"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, dict):
        return "unset" if not value else repr(value)
    if value == "":
        return "empty"
    return str(value)


def documented_defaults() -> dict[str, str]:
    text = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| `(" + PREFIX + r"[A-Z0-9_]+)` \| ([^|]+) \|", text, re.MULTILINE)
    return {name: cell.strip() for name, cell in rows}


def test_every_setting_is_documented_with_its_default():
    documented = documented_defaults()
    required = {"api_base_url", "model"}
    for field in dataclasses.fields(Settings):
        name = PREFIX + field.name.upper()
        assert name in documented, f"{name} missing in docs/configuration.md"
        if field.name in required:
            assert documented[name] == "required"
            continue
        default = (
            field.default if field.default is not dataclasses.MISSING else field.default_factory()
        )
        assert documented[name] == default_text(default), name
    assert len(documented) == len(dataclasses.fields(Settings)), "documented setting without field"


def anchors(path: Path) -> set[str]:
    result = set()
    for heading in re.findall(r"^#+ (.+)$", path.read_text(encoding="utf-8"), re.MULTILINE):
        slug = re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")
        result.add(slug)
    return result


@pytest.mark.parametrize("path", MARKDOWN, ids=lambda p: str(p.relative_to(ROOT)))
def test_internal_links_resolve(path):
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    for target in re.findall(r"\]\(([^)\s]+)\)", text):
        if re.match(r"[a-z]+:", target) or target.startswith("?"):
            continue  # external link or query link
        file_part, _, anchor = target.partition("#")
        linked = (path.parent / file_part).resolve() if file_part else path
        assert linked.exists(), f"{path.name}: broken link {target}"
        if anchor and linked.suffix == ".md":
            assert anchor in anchors(linked), f"{path.name}: missing anchor {target}"


def comments_and_docstrings(path: Path):
    source = path.read_text(encoding="utf-8")
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            yield token.start[0], token.string
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node)
            if doc:
                yield getattr(node, "lineno", 1), doc


def test_no_references_to_unpublished_history():
    findings = []
    for path in MARKDOWN:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if HISTORY.search(line):
                findings.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    for path in sorted((ROOT / "src").rglob("*.py")) + sorted((ROOT / "scripts").rglob("*.py")):
        for number, text in comments_and_docstrings(path):
            if HISTORY.search(text):
                findings.append(f"{path.relative_to(ROOT)}:{number}: {text.strip()[:80]}")
    assert not findings, "\n".join(findings)


def test_version_is_the_same_everywhere():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    first = re.search(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE).group(1)
    citation = re.search(
        r"^version: (\S+)$", (ROOT / "CITATION.cff").read_text(encoding="utf-8"), re.MULTILINE
    ).group(1)
    assert __version__ == first == citation


def test_privacy_defaults_are_passed_to_gradio(monkeypatch):
    captured = {}
    monkeypatch.setattr(gr.Blocks, "launch", lambda self, **kwargs: captured.update(kwargs))
    app = App(make_settings())
    blocks = app.build()
    app.launch(blocks)
    assert blocks.analytics_enabled is False
    assert captured["run_history"] is False
    assert captured["server_name"] == "127.0.0.1"
    assert captured["max_file_size"] == "10mb"


def test_step_values_are_identifiers_not_labels():
    choices = {lang: App._step_choices(lang) for lang in ("en", "de")}
    assert [value for _, value in choices["en"]] == list(STEP_ORDER)
    assert [value for _, value in choices["de"]] == list(STEP_ORDER)
    assert [label for label, _ in choices["en"]] != [label for label, _ in choices["de"]]
