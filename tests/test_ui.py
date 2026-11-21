# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Interface logic without a browser: building, localisation, estimate, processing."""

from __future__ import annotations

import asyncio
from pathlib import Path

import gradio as gr
import pytest
from conftest import FakeLLM, make_client, make_settings

from stt_to_script.ui import App

TEXT = ("Das ist ein Satz aus der Vorlesung über Statistik. " * 30).strip()


class FakeRequest:
    def __init__(self, headers=None, query=None):
        self.headers = headers or {}
        self.query_params = query or {}


def make_app(fake=None, **overrides):
    settings = make_settings(**overrides)
    fake = fake or FakeLLM()
    return App(settings, client_factory=lambda: make_client(settings, fake)), fake


def collect(app: App, *args):
    async def go():
        updates = []
        async for update in app.on_process(*args, progress=lambda *a, **k: None):
            updates.append(update)
        return updates

    return asyncio.run(go())


def test_app_builds_without_launching():
    app, _ = make_app()
    blocks = app.build()
    assert isinstance(blocks, gr.Blocks)


@pytest.mark.parametrize(
    "request_, lang",
    [
        (FakeRequest(), "en"),
        (FakeRequest({"accept-language": "de-DE,de;q=0.9"}), "de"),
        (FakeRequest({"accept-language": "de"}, {"lang": "en"}), "en"),
    ],
)
def test_load_localises_the_interface(request_, lang):
    app, _ = make_app()
    app.build()
    updates = app.on_load(request_)
    c = app.components
    assert updates[c["lang"]] == lang
    assert updates[c["start"]]["value"] == (
        "Verarbeitung starten" if lang == "de" else "Start processing"
    )
    assert updates[c["language"]]["value"] == lang
    # The context field gets a placeholder and a hint, never a pre-filled value.
    assert "value" not in updates[c["context"]] and updates[c["context"]]["placeholder"]
    # Everything with a fixed text is localised; preview and issues only hold results.
    assert set(c.values()) - set(updates) == {c["preview"], c["issues"]}


def test_estimate_for_pasted_text_and_errors():
    app, _ = make_app()
    app.build()
    assert "Geschätzte Dauer" in app.on_estimate(None, TEXT, ["correct", "clean"], "de", "de")
    assert "estimated duration appears" in app.on_estimate(None, "", ["style"], "en", "en")
    assert "Only step 0" in app.on_estimate(None, TEXT, ["preprocess"], "de", "en")


def test_estimate_limit_is_announced_before_starting():
    app, _ = make_app(max_estimated_minutes=1.0)
    app.build()
    assert "exceeds the limit" in app.on_estimate(None, TEXT * 20, ["style"], "de", "en")
    with pytest.raises(gr.Error):
        collect(app, None, TEXT * 20, "de", "", ["style"], True, "en")


def test_processing_returns_result_and_downloads_and_cleans_up(tmp_path):
    app, fake = make_app()
    app.build()
    upload = tmp_path / "vorlesung.txt"
    upload.write_text(TEXT, encoding="utf-8")
    seen_files = []

    async def go():
        async for update in app.on_process(
            str(upload),
            "",
            "de",
            "Statistik",
            ["correct", "clean", "style"],
            True,
            "de",
            progress=lambda *a, **k: None,
        ):
            files = update.get(app.components["downloads"])
            if files:
                # Files must exist while Gradio copies them into its cache.
                seen_files.extend((f, Path(f).exists()) for f in files)

    asyncio.run(go())
    assert not upload.exists(), "upload must be deleted after reading"
    names = [Path(f).name for f, _ in seen_files]
    assert names == ["vorlesung.stt-to-script.txt", "vorlesung.1-correct_clean.txt"]
    assert all(existed for _, existed in seen_files)
    assert not any(Path(f).exists() for f, _ in seen_files), "per-job directory must be removed"
    assert len(fake.requests) == 2


def test_input_errors_become_localised_gradio_errors(tmp_path):
    app, _ = make_app()
    app.build()
    with pytest.raises(gr.Error) as info:
        collect(app, None, "", "de", "", ["style"], True, "de")
    assert "Datei hoch" in str(info.value)
    with pytest.raises(gr.Error) as info:
        collect(app, None, TEXT, "de", "", [], True, "en")
    assert "at least one step" in str(info.value)


def test_backend_errors_hide_details_unless_enabled():
    rejecting = FakeLLM(lambda p, c, n: (401, "denied", {}))
    app, _ = make_app(rejecting)
    app.build()
    with pytest.raises(gr.Error) as info:
        collect(app, None, TEXT, "de", "", ["style"], True, "en")
    assert "rejected the request" in str(info.value) and "HTTP 401" not in str(info.value)
    app, _ = make_app(rejecting, show_error_details=True)
    app.build()
    with pytest.raises(gr.Error) as info:
        collect(app, None, TEXT, "de", "", ["style"], True, "en")
    assert "HTTP 401" in str(info.value)


def test_estimate_warns_when_the_text_is_not_in_the_selected_language():
    app, _ = make_app()
    app.build()
    english = (
        "We talked about the measurements today, and it is important that you have this. " * 10
    )
    assert "sieht nach English aus, gewählt ist aber Deutsch" in app.on_estimate(
        None, english, ["style"], "de", "de"
    )
    assert "sieht nach" not in app.on_estimate(None, TEXT, ["style"], "de", "de")
