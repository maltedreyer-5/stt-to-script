# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Client for an OpenAI-compatible ``/chat/completions`` endpoint.

Only ``choices[0].message.content`` is read. Separate reasoning fields that
some servers return (``reasoning_content``, ``reasoning``) are ignored on
purpose, and reasoning tags inside the content are removed by
:func:`reasoning.strip_reasoning`.

Errors are classified so the pipeline can react differently:

* ``retryable`` errors (timeouts, connection problems, 429, 5xx, malformed or
  empty answers) are retried here with a short back-off;
* :class:`TruncatedError` (``finish_reason == "length"``, an unclosed
  reasoning block, or a 400 that mentions the context length) is not retried
  with the same input: the pipeline splits the segment instead;
* ``fatal`` errors (401, 403, 404) stop the whole job, since every further
  request would fail the same way.

Log records and exception messages never contain the prompt, the answer or
the API key. Response bodies of failed requests are only logged at DEBUG,
truncated, because a server may echo parts of the request.
"""

from __future__ import annotations

import asyncio
import email.utils
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from .config import Settings
from .reasoning import UnclosedReasoningError, strip_reasoning, strip_wrapping_fence

log = logging.getLogger(__name__)

BACKOFF_SECONDS = (5.0, 15.0)
MAX_RETRY_AFTER_SECONDS = 120.0
_CONTEXT_HINTS = ("context", "token", "too long", "maximum")


class LLMError(Exception):
    """Base class. ``kind`` is a message key suffix used by the interface."""

    kind = "llm_failed"
    retryable = False
    fatal = False

    def __init__(self, detail: str, status: int | None = None):
        super().__init__(detail)
        self.detail = detail
        self.status = status


class RetryableError(LLMError):
    kind = "llm_unavailable"
    retryable = True
    retry_after: float | None = None  # seconds, from a Retry-After header


class TruncatedError(LLMError):
    kind = "llm_truncated"


class FatalError(LLMError):
    kind = "llm_rejected"
    fatal = True


class RejectedError(LLMError):
    kind = "llm_rejected_segment"


@dataclass(frozen=True)
class Completion:
    text: str
    finish_reason: str | None
    seconds: float
    attempts: int


Sleep = Callable[[float], Awaitable[None]]


class LLMClient:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
    ):
        self.settings = settings
        headers = {"Content-Type": "application/json"}
        if settings.api_key:
            headers["Authorization"] = f"Bearer {settings.api_key}"
        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(
                settings.request_timeout, connect=min(30.0, settings.request_timeout)
            ),
            transport=transport,
        )
        self._sleep = sleep

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> LLMClient:
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()

    def build_payload(self, prompt: str) -> dict:
        payload: dict = {"model": self.settings.model}
        if self.settings.temperature is not None:
            payload["temperature"] = self.settings.temperature
        if self.settings.max_tokens is not None:
            payload["max_tokens"] = self.settings.max_tokens
        payload.update(self.settings.extra_body)
        payload["messages"] = [{"role": "user", "content": prompt}]
        return payload

    async def complete(self, prompt: str, label: str = "") -> Completion:
        """Send one prompt; retry transient errors. ``label`` only appears in logs."""
        attempts = self.settings.max_attempts
        for attempt in range(1, attempts + 1):
            started = time.monotonic()
            try:
                text, finish_reason = await self._request(prompt)
            except RetryableError as exc:
                if attempt == attempts:
                    log.warning("%s: giving up after %d attempts (%s)", label, attempt, exc.detail)
                    raise
                delay = self._delay(attempt, exc)
                log.info(
                    "%s: attempt %d failed (%s), retrying in %.0f s",
                    label,
                    attempt,
                    exc.detail,
                    delay,
                )
                await self._sleep(delay)
                continue
            seconds = time.monotonic() - started  # successful attempt only, for the estimate
            log.info(
                "%s: ok after %d attempt(s), %.1f s, finish_reason=%s",
                label,
                attempt,
                seconds,
                finish_reason,
            )
            return Completion(text, finish_reason, seconds, attempt)
        raise AssertionError("unreachable")  # pragma: no cover

    def _delay(self, attempt: int, exc: RetryableError) -> float:
        delay = BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)]
        if exc.retry_after is not None:
            delay = max(delay, min(exc.retry_after, MAX_RETRY_AFTER_SECONDS))
        return delay

    async def _request(self, prompt: str) -> tuple[str, str | None]:
        try:
            response = await self._client.post(
                self.settings.chat_completions_url, json=self.build_payload(prompt)
            )
        except httpx.TimeoutException:
            raise RetryableError("timeout") from None
        except httpx.TransportError as exc:
            raise RetryableError(f"connection error ({type(exc).__name__})") from None

        status = response.status_code
        if status != 200:
            log.debug("HTTP %d body: %.300s", status, response.text)
            if status in (401, 403):
                raise FatalError(f"HTTP {status}: authentication or permission problem", status)
            if status == 404:
                raise FatalError("HTTP 404: endpoint or model not found", status)
            if status == 429 or status >= 500:
                error = RetryableError(f"HTTP {status}", status)
                error.retry_after = _parse_retry_after(response.headers.get("retry-after"))
                raise error
            if status in (400, 413, 422) and _mentions_context(response.text):
                raise TruncatedError(f"HTTP {status}: input too long for the model", status)
            raise RejectedError(f"HTTP {status}: request rejected", status)

        try:
            choice = response.json()["choices"][0]
            content = choice["message"].get("content")
            finish_reason = choice.get("finish_reason")
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise RetryableError("malformed response") from None
        if finish_reason == "length":
            raise TruncatedError("output limit reached (finish_reason=length)")
        if not isinstance(content, str):
            raise RetryableError("response without text content")
        try:
            text = strip_wrapping_fence(strip_reasoning(content))
        except UnclosedReasoningError:
            raise TruncatedError("output ended inside a reasoning block") from None
        if not text:
            raise RetryableError("empty response")
        return text, finish_reason

    async def check_connection(self) -> str:
        """Lightweight start-up check against ``/models``. Returns a log message."""
        try:
            response = await self._client.get(self.settings.models_url, timeout=10.0)
        except httpx.HTTPError as exc:
            return (
                f"LLM endpoint not reachable ({type(exc).__name__}); requests will fail until it is"
            )
        if response.status_code in (401, 403):
            return f"LLM endpoint rejected the credentials (HTTP {response.status_code})"
        if response.status_code != 200:
            return f"LLM endpoint reachable, /models returned HTTP {response.status_code}"
        try:
            ids = {item.get("id") for item in response.json().get("data", [])}
        except (ValueError, AttributeError):
            return "LLM endpoint reachable, /models returned no model list"
        if ids and self.settings.model not in ids:
            return f"LLM endpoint reachable, but model {self.settings.model!r} is not listed"
        return "LLM endpoint reachable"


def _mentions_context(body: str) -> bool:
    lowered = body.lower()
    return any(hint in lowered for hint in _CONTEXT_HINTS)


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, when.timestamp() - time.time())
