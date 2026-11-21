# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Shared fixtures: settings and a fake OpenAI-compatible backend."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import httpx
import pytest

from stt_to_script.config import Settings
from stt_to_script.estimate import RateTracker
from stt_to_script.llm import LLMClient
from stt_to_script.pipeline import Done, Runner
from stt_to_script.prompts import PromptLibrary

MARKERS = ("Ab hier kommt der zu bearbeitende Text:\n", "The text to edit follows from here:\n")


def make_settings(**overrides) -> Settings:
    base = Settings(api_base_url="http://llm.test/v1", model="test-model", max_attempts=3)
    return replace(base, **overrides)


def chunk_of(prompt: str) -> str:
    """Extract the transcript part of a rendered prompt."""
    for marker in MARKERS:
        if marker in prompt:
            return prompt.split(marker, 1)[1].rstrip("\n")
    raise AssertionError("prompt without text marker")


def pass_of(prompt: str) -> str:
    """Identify which prompt was used, from wording unique to each file."""
    probes = {  # order matters: the RAG prompt also mentions headings and Markdown
        "rag": ("RAG",),
        "structure": ("Markdown", "Überschriften"),
        "style": ("wissenschaftlich", "academic"),
        "correct_clean": (
            "Vervollständige Sätze, die unvollständig sind.",
            "Complete sentences that are incomplete.",
        ),
        "correct": ("Formuliere nichts um", "Do not rephrase"),
        "clean": ("Füllwörter", "filler words"),
    }
    for name, words in probes.items():
        if any(word in prompt for word in words):
            return name
    return "raw"  # a hand-written prompt, as in the client tests


class FakeLLM:
    """Programmable fake backend. ``respond(prompt, chunk, pass_name)`` returns
    ``(status, body_dict_or_text, headers)`` or just the answer text."""

    def __init__(self, respond=None):
        self.requests: list[dict] = []
        self.respond = respond or (lambda prompt, chunk, name: f"[{name}] {chunk}")

    def transport(self) -> httpx.MockTransport:
        async def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            self.requests.append({"body": body, "headers": dict(request.headers)})
            prompt = body["messages"][0]["content"]
            result = self.respond(prompt, chunk_of(prompt), pass_of(prompt))
            if isinstance(result, tuple):
                status, payload, headers = result
            else:
                status, payload, headers = 200, ok(result), {}
            if isinstance(payload, dict):
                return httpx.Response(status, json=payload, headers=headers)
            return httpx.Response(status, text=payload, headers=headers)

        return httpx.MockTransport(handler)

    def prompts(self) -> list[str]:
        return [r["body"]["messages"][0]["content"] for r in self.requests]


def ok(text: str, finish_reason: str = "stop") -> dict:
    return {
        "choices": [
            {"message": {"role": "assistant", "content": text}, "finish_reason": finish_reason}
        ]
    }


async def no_sleep(_seconds: float) -> None:
    return None


def make_client(settings: Settings, fake: FakeLLM, sleeps: list | None = None) -> LLMClient:
    async def sleep(seconds: float) -> None:
        if sleeps is not None:
            sleeps.append(seconds)

    return LLMClient(settings, transport=fake.transport(), sleep=sleep)


def run_job(settings: Settings, fake: FakeLLM, job) -> tuple[Done, list]:
    """Run a job to completion; return the Done event and all events."""

    async def go():
        client = make_client(settings, fake)
        runner = Runner(settings, client, PromptLibrary(), RateTracker(6.0))
        events = []
        try:
            async for event in runner.run(job):
                events.append(event)
        finally:
            await client.aclose()
        return events

    events = asyncio.run(go())
    done = events[-1]
    assert isinstance(done, Done)
    return done, events


@pytest.fixture
def settings() -> Settings:
    return make_settings()
