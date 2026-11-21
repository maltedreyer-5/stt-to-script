# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""LLM client and pipeline against a fake OpenAI-compatible backend."""

from __future__ import annotations

import asyncio
import logging

import httpx
import pytest
from conftest import FakeLLM, make_client, make_settings, ok, run_job

from stt_to_script.llm import FatalError, RejectedError, RetryableError, TruncatedError
from stt_to_script.pipeline import Job, JobFailed, PassDone, Progress
from stt_to_script.steps import PRESETS, plan_passes

# --- client -------------------------------------------------------------------


def complete(settings, fake, prompt="P\nAb hier kommt der zu bearbeitende Text:\nX", sleeps=None):
    async def go():
        client = make_client(settings, fake, sleeps)
        try:
            return await client.complete(prompt)
        finally:
            await client.aclose()

    return asyncio.run(go())


def test_payload_and_headers(settings):
    fake = FakeLLM()
    complete(make_settings(temperature=None, max_tokens=512, extra_body={"top_p": 0.9}), fake)
    body, headers = fake.requests[0]["body"], fake.requests[0]["headers"]
    assert body["model"] == "test-model" and body["max_tokens"] == 512 and body["top_p"] == 0.9
    assert "temperature" not in body and "authorization" not in headers
    complete(make_settings(api_key="sk-test"), fake)  # pragma: allowlist secret
    assert fake.requests[1]["headers"]["authorization"] == "Bearer sk-test"
    assert fake.requests[1]["body"]["temperature"] == 0.3


def test_reasoning_is_removed_and_reasoning_field_ignored(settings):
    body = ok("<think>Überlegung</think>Ergebnis")
    body["choices"][0]["message"]["reasoning_content"] = "ignoriert"
    fake = FakeLLM(lambda p, c, n: (200, body, {}))
    assert complete(settings, fake).text == "Ergebnis"


@pytest.mark.parametrize(
    "response, error",
    [
        ((200, ok("teil", "length"), {}), TruncatedError),
        ((200, ok("<think>endlos"), {}), TruncatedError),
        ((400, "This model's maximum context length is 8192 tokens", {}), TruncatedError),
        ((400, "invalid parameter", {}), RejectedError),
        ((401, "no", {}), FatalError),
        ((404, "model not found", {}), FatalError),
    ],
)
def test_non_retryable_errors_are_raised_once(settings, response, error):
    fake = FakeLLM(lambda p, c, n: response)
    with pytest.raises(error):
        complete(settings, fake)
    assert len(fake.requests) == 1


@pytest.mark.parametrize(
    "response", [(500, "x", {}), (503, "x", {}), (200, {"unexpected": 1}, {}), (200, ok(""), {})]
)
def test_retryable_errors_are_retried_up_to_max_attempts(settings, response):
    fake = FakeLLM(lambda p, c, n: response)
    sleeps = []
    with pytest.raises(RetryableError):
        complete(settings, fake, sleeps=sleeps)
    assert len(fake.requests) == 3 and sleeps == [5.0, 15.0]


def test_retry_after_header_is_honoured(settings):
    answers = iter([(429, "slow down", {"Retry-After": "30"}), "fertig"])
    fake = FakeLLM(lambda p, c, n: next(answers))
    sleeps = []
    assert complete(settings, fake, sleeps=sleeps).text == "fertig"
    assert sleeps == [30.0]


def test_timeouts_are_retried(settings):
    calls = []

    async def handler(request):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ReadTimeout("slow")
        return httpx.Response(200, json=ok("ok"))

    async def go():
        from stt_to_script.llm import LLMClient

        async def sleep(_):
            return None

        client = LLMClient(settings, transport=httpx.MockTransport(handler), sleep=sleep)
        try:
            return await client.complete("x")
        finally:
            await client.aclose()

    assert asyncio.run(go()).text == "ok" and len(calls) == 2


def test_api_key_never_appears_in_errors_or_logs(caplog):
    caplog.set_level(logging.DEBUG)
    fake = FakeLLM(lambda p, c, n: (500, "server error", {}))
    with pytest.raises(RetryableError) as info:
        complete(make_settings(api_key="sk-geheim-123"), fake)  # pragma: allowlist secret
    assert "sk-geheim-123" not in str(info.value)
    assert all("sk-geheim-123" not in record.getMessage() for record in caplog.records)


# --- pipeline -----------------------------------------------------------------

PARAGRAPH = "Das ist ein Satz aus der Vorlesung über Statistik und Wahrscheinlichkeit. "


def transcript(paragraphs: int, sentences: int = 12) -> str:
    return "\n\n".join((PARAGRAPH * sentences).strip() for _ in range(paragraphs)) + "\n"


def test_passes_follow_the_selected_steps():
    assert [p.name for p in plan_passes(PRESETS["formatting"])] == [
        "correct_clean",
        "style",
        "structure",
    ]
    assert [p.name for p in plan_passes(("clean", "rag", "correct"))] == ["correct_clean", "rag"]
    assert [p.name for p in plan_passes(("clean",))] == ["clean"]
    assert plan_passes(("preprocess",)) == []


def test_formatting_preset_end_to_end_in_german():
    settings = make_settings(chunk_chars=2000)
    fake = FakeLLM()
    text = transcript(5)
    done, events = run_job(settings, fake, Job(text, "de", "Statistik", PRESETS["formatting"]))
    assert all("KONTEXT UND FACHGEBIET: Statistik" in p for p in fake.prompts())
    # Each segment went through all three passes in order, and nothing was lost
    # or duplicated: removing the fake's markers gives back the input exactly.
    marker = "[structure] [style] [correct_clean] "
    segments = len(fake.requests) // 3
    assert segments > 1 and done.text.count(marker) == segments
    assert done.text.replace(marker, "") == text
    assert list(done.intermediates) == ["correct_clean", "style", "structure"]
    assert not done.issues
    progress = [e for e in events if isinstance(e, Progress)]
    assert progress[-1].done == progress[-1].total


def test_other_languages_use_the_generic_prompts():
    fake = FakeLLM()
    run_job(make_settings(), fake, Job(transcript(1), "fr", "", ("style",)))
    prompt = fake.prompts()[0]
    assert "written in French" in prompt and "Write the result in French" in prompt
    assert "General text without specific subject area" in prompt


def test_truncated_segments_are_split_and_completed():
    settings = make_settings(chunk_chars=4000)

    def respond(prompt, chunk, name):
        return (200, ok(chunk, "length"), {}) if len(chunk) > 1500 else chunk.upper()

    fake = FakeLLM(respond)
    text = transcript(2, sentences=40)
    done, _ = run_job(settings, fake, Job(text, "de", "", ("style",)))
    assert not done.issues
    assert done.text.replace("\n", " ").split() == text.upper().replace("\n", " ").split()


def test_failed_segment_keeps_previous_text_and_is_reported():
    settings = make_settings(chunk_chars=1200)

    def respond(prompt, chunk, name):
        if name == "style" and "MARKE" in chunk:
            return (500, "kaputt", {})
        return f"<{name}>{chunk}"

    fake = FakeLLM(respond)
    text = transcript(1, 12) + "\n" + "MARKE " + transcript(1, 12)
    done, _ = run_job(settings, fake, Job(text, "de", "", ("correct", "clean", "style")))
    failed = [i for i in done.issues if i.kind == "llm_unavailable"]
    assert len(failed) == 1 and failed[0].pass_name == "style"
    assert "<correct_clean>MARKE" in done.text  # previous pass result kept
    assert "kaputt" not in done.text and "Fehler" not in done.text


def test_job_fails_when_every_segment_fails():
    fake = FakeLLM(lambda p, c, n: (502, "x", {}))
    with pytest.raises(JobFailed) as info:
        run_job(make_settings(), fake, Job(transcript(1), "de", "", ("style",)))
    assert info.value.kind == "llm_unavailable"


def test_fatal_error_stops_the_job_immediately():
    fake = FakeLLM(lambda p, c, n: (401, "denied", {}))
    with pytest.raises(JobFailed) as info:
        run_job(
            make_settings(chunk_chars=1000, parallel_requests=1),
            fake,
            Job(transcript(4), "de", "", ("style",)),
        )
    assert info.value.kind == "llm_rejected"
    assert len(fake.requests) == 1


def test_structure_pass_sees_previous_headings_and_seams_become_paragraphs():
    settings = make_settings(chunk_chars=1200)
    counter = iter(range(1, 100))

    def respond(prompt, chunk, name):
        return f"## Teil {next(counter)}\n\n{chunk}" if name == "structure" else chunk

    fake = FakeLLM(respond)
    text = (PARAGRAPH * 40).strip()  # one long paragraph: seams are single spaces
    done, _ = run_job(settings, fake, Job(text, "de", "", ("structure",)))
    prompts = fake.prompts()
    assert "GLIEDERUNG" not in prompts[0]
    assert "GLIEDERUNG BIS HIERHER" in prompts[1] and "## Teil 1" in prompts[1]
    assert "## Teil 1" in prompts[2] and "## Teil 2" in prompts[2]
    assert ". ## Teil" not in done.text and "\n\n## Teil 2" in done.text


def test_consistent_headings_can_be_switched_off():
    fake = FakeLLM()
    run_job(
        make_settings(chunk_chars=1200, consistent_headings=False),
        fake,
        Job((PARAGRAPH * 40).strip(), "de", "", ("structure",)),
    )
    assert not any("GLIEDERUNG" in p for p in fake.prompts())


def test_rag_adds_front_matter_written_by_the_code():
    done, _ = run_job(
        make_settings(),
        FakeLLM(),
        Job(transcript(1), "de", "Medizin „Herz“", PRESETS["rag"], source_name="vl.srt"),
    )
    header = done.text.split("\n---\n", 1)[0]
    assert header.startswith('---\nlanguage: "de"\ncontext: "Medizin „Herz“"\nsource: "vl.srt"')
    assert 'steps: ["preprocess", "correct", "clean", "structure", "rag"]' in header


def test_subtitle_input_forces_preprocessing():
    srt = "".join(
        f"{i}\n00:00:{i:02d},000 --> 00:00:{i:02d},900\n{PARAGRAPH * 2}\n\n" for i in range(1, 6)
    )
    fake = FakeLLM()
    done, events = run_job(make_settings(), fake, Job(srt, "de", "", ("style",)))
    assert "preprocess" in done.steps and isinstance(events[0], PassDone)
    assert "-->" not in fake.prompts()[0]


def test_strong_length_change_is_reported_but_kept():
    fake = FakeLLM(lambda p, c, n: "kurz")
    done, _ = run_job(make_settings(), fake, Job(transcript(1), "de", "", ("style",)))
    assert done.text.strip() == "kurz"
    assert [i.kind for i in done.issues] == ["length_changed"]


def test_logs_contain_no_user_content(caplog):
    caplog.set_level(logging.DEBUG)
    marker = "Vertraulicher-Inhalt-4711"
    # The failing request's response body echoes the input, as some servers do.
    fake = FakeLLM(lambda p, c, n: (500, f"echo {c[-100:]}", {}) if "fail" in c else c)
    text = transcript(2) + f" {marker} fail"
    run_job(make_settings(chunk_chars=1000), fake, Job(text, "de", f"Kontext {marker}", ("style",)))
    ours = [r for r in caplog.records if r.name.startswith("stt_to_script")]
    normal = [r for r in ours if r.levelno >= logging.INFO]
    assert normal and all(marker not in r.getMessage() for r in normal)
    # DEBUG is documented to include truncated error bodies, which may echo input.
    assert any(marker in r.getMessage() for r in ours if r.levelno == logging.DEBUG)


def test_text_shorter_than_minimum_is_rejected():
    from stt_to_script.textio import InputError

    with pytest.raises(InputError):
        run_job(make_settings(), FakeLLM(), Job("zu kurz", "de", "", ("style",)))


def test_cancelling_a_job_cancels_requests_in_flight():
    started, cancelled = [], []

    async def handler(request):
        started.append(1)
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.append(1)
            raise
        return httpx.Response(200, json=ok("x"))

    async def go():
        from stt_to_script.estimate import RateTracker
        from stt_to_script.llm import LLMClient
        from stt_to_script.pipeline import Runner
        from stt_to_script.prompts import PromptLibrary

        settings = make_settings(chunk_chars=1000, parallel_requests=2)
        client = LLMClient(settings, transport=httpx.MockTransport(handler))
        runner = Runner(settings, client, PromptLibrary(), RateTracker(6.0))

        async def consume():
            async for _ in runner.run(Job(transcript(4), "de", "", ("style",))):
                pass

        task = asyncio.create_task(consume())
        for _ in range(500):
            if len(started) == 2:
                break
            await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await client.aclose()

    asyncio.run(go())
    assert len(started) == 2 and len(cancelled) == 2


def test_enclosing_code_fence_is_removed_from_answers(settings):
    fake = FakeLLM(lambda p, c, n: "```markdown\n## Teil\n\nInhalt.\n```")
    assert complete(settings, fake).text == "## Teil\n\nInhalt."


@pytest.mark.parametrize(
    "answer, kinds",
    [
        ("Hier ist der überarbeitete Text:\n\n{c}", ["possible_preface"]),
        ("{c}\n\nIch hoffe, das hilft weiter!", ["possible_closing"]),
        (
            "Gerne, hier ist das Ergebnis:\n\n{c}\n\nBei Fragen melde dich gern.",
            ["possible_preface", "possible_closing"],
        ),
        ("{c}", []),
    ],
)
def test_remarks_around_the_text_are_reported_but_kept(answer, kinds):
    text = transcript(2)
    fake = FakeLLM(lambda p, c, n: answer.format(c=c))
    done, _ = run_job(make_settings(), fake, Job(text, "de", "", ("style",)))
    assert sorted(i.kind for i in done.issues) == sorted(kinds)
    if kinds:
        assert (
            answer.split("{c}")[0].strip() in done.text
            or answer.split("{c}")[1].strip() in done.text
        )


def test_structured_paragraphs_from_the_input_are_not_reported():
    fake = FakeLLM(lambda p, c, n: "## Teil\n\n" + c.replace(". Das", ".\n\nDas", 3))
    done, _ = run_job(make_settings(), fake, Job(transcript(2), "de", "", ("structure",)))
    assert done.issues == []


def test_main_heading_in_the_structure_pass_is_reported():
    fake = FakeLLM(lambda p, c, n: "# Vorlesung\n\n## Teil\n\n" + c)
    done, _ = run_job(make_settings(), fake, Job(transcript(1), "de", "", ("structure",)))
    assert [i.kind for i in done.issues] == ["main_heading"]


def test_warnings_alone_never_fail_a_job():
    fake = FakeLLM(lambda p, c, n: "Hier ist der Text:\n\n" + c)
    done, _ = run_job(
        make_settings(chunk_chars=1000), fake, Job(transcript(3), "de", "", ("style",))
    )
    assert done.issues and all(i.kind == "possible_preface" for i in done.issues)
