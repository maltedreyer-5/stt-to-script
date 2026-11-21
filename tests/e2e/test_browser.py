# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""End-to-end test in a headless browser, against the fake backend.

Opt-in, because it needs Playwright and a Chromium build:

    pip install -e ".[dev,e2e]" && playwright install chromium
    STT_TO_SCRIPT_E2E=1 pytest tests/e2e

It checks what unit tests cannot: that labels switch language in the real
page, that an upload is gone from the server after processing, that
downloads still work after the per-job directory was removed, and that
nothing from the transcript is kept in the browser's storage.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

if os.environ.get("STT_TO_SCRIPT_E2E") != "1":
    pytest.skip("set STT_TO_SCRIPT_E2E=1 to run browser tests", allow_module_level=True)
playwright = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parents[2]
MARKER = "Quokkastatistik"  # unusual word to search for in storage and files

SRT = "".join(
    f"{i}\n00:00:{i:02d},000 --> 00:00:{i:02d},900\n"
    f"Teil {i}: Heute sprechen wir über {MARKER} und die Auswertung von Messreihen.\n\n"
    for i in range(1, 9)
)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for(url: str, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):  # noqa: S310 - local test URL
                return
        except OSError:
            time.sleep(0.3)
    raise TimeoutError(url)


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("e2e")
    gradio_tmp, job_tmp = tmp / "gradio", tmp / "tmp"
    gradio_tmp.mkdir()
    job_tmp.mkdir()
    fake_port, app_port = free_port(), free_port()
    env = {
        **os.environ,
        "STT_TO_SCRIPT_API_BASE_URL": f"http://127.0.0.1:{fake_port}/v1",
        "STT_TO_SCRIPT_MODEL": "fake",
        "STT_TO_SCRIPT_PORT": str(app_port),
        "GRADIO_TEMP_DIR": str(gradio_tmp),
        "TMPDIR": str(job_tmp),
        "NO_PROXY": "127.0.0.1,localhost",
    }
    fake = subprocess.Popen(  # noqa: S603 - fixed local command
        [
            sys.executable,
            str(ROOT / "tests" / "fake_openai.py"),
            "--port",
            str(fake_port),
            "--delay",
            "0.3",
        ],
        env=env,
    )
    wait_for(f"http://127.0.0.1:{fake_port}/v1/models")
    app = subprocess.Popen([sys.executable, "-m", "stt_to_script"], env=env)  # noqa: S603
    try:
        wait_for(f"http://127.0.0.1:{app_port}/")
        yield {
            "url": f"http://127.0.0.1:{app_port}/",
            "gradio_tmp": gradio_tmp,
            "job_tmp": job_tmp,
            "tmp": tmp,
        }
    finally:
        for process in (app, fake):
            process.terminate()
            process.wait(timeout=10)


@pytest.fixture
def browser():
    with playwright.sync_playwright() as p:
        instance = p.chromium.launch(args=["--no-proxy-server"])
        yield instance
        instance.close()


def test_german_page_processes_subtitles_and_leaves_nothing_behind(server, browser):
    page = browser.new_page(locale="de-DE")
    page.goto(server["url"])
    start = page.get_by_role("button", name="Verarbeitung starten")
    start.wait_for(timeout=20_000)
    assert page.get_by_role("tab", name="Datei hochladen").is_visible()
    context = page.get_by_label("Fachgebiet und Kontext")
    assert context.input_value() == ""
    assert context.get_attribute("placeholder").startswith("z. B.")

    upload = server["tmp"] / "vorlesung.srt"
    upload.write_text(SRT, encoding="utf-8")
    page.locator("input[type=file]").set_input_files(str(upload))
    page.get_by_text("Geschätzte Dauer").wait_for(timeout=20_000)
    start.click()
    status = page.get_by_label("Status")
    page.wait_for_function(
        "el => el.value.startsWith('Fertig nach')", arg=status.element_handle(), timeout=60_000
    )
    assert page.locator("input[type=file]").count() == 1  # field cleared, ready for a new upload

    page.get_by_role("tab", name="Text", exact=True).click()
    page.wait_for_timeout(500)
    values = [area.input_value() for area in page.locator("textarea").all()]
    results = [v for v in values if MARKER in v]
    assert results, "the result text must be shown"
    assert all("<think>" not in v and "-->" not in v for v in results)

    links = page.locator("a[download]")
    hrefs = [links.nth(i).get_attribute("href") for i in range(links.count())]
    assert any(h.endswith("vorlesung.stt-to-script.md") for h in hrefs)
    for href in hrefs:
        response = page.request.get(href)
        assert response.ok and "<think>" not in response.text()

    leftovers = [p for p in server["gradio_tmp"].rglob("vorlesung.srt")]
    assert leftovers == [], "the uploaded file must be deleted after reading"
    assert not list(server["job_tmp"].glob("stt-to-script-*")), "per-job directory must be removed"
    storage = page.evaluate("JSON.stringify(localStorage) + JSON.stringify(sessionStorage)")
    assert MARKER not in storage, "nothing from the transcript may stay in browser storage"


def test_english_via_query_parameter(server, browser):
    page = browser.new_page(locale="de-DE")
    page.goto(server["url"] + "?lang=en")
    page.get_by_role("button", name="Start processing").wait_for(timeout=20_000)


def test_page_works_without_accept_language_header(server, browser):
    page = browser.new_page()

    def strip(route):
        headers = {k: v for k, v in route.request.headers.items() if k.lower() != "accept-language"}
        route.continue_(headers=headers)

    page.route("**/*", strip)
    page.goto(server["url"])
    page.get_by_role("button", name="Start processing").wait_for(timeout=20_000)
    assert page.locator(".toast-body").count() == 0
