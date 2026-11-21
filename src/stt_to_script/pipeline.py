# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Running a job: preprocessing, splitting, LLM passes, joining.

The job is an async generator of events, so that the interface can show
progress and so that closing the browser tab cancels it: Gradio cancels a
running async generator when the client disconnects, which also cancels the
HTTP requests in flight.

Failure handling per segment: if a segment cannot be processed in a pass,
it keeps the text it had before that pass, and an :class:`Issue` records
this. Nothing is ever written into the result text itself, because the
result may be fed into other systems unread. A job only fails as a whole if
the backend rejects the credentials or the model (fatal errors), or if every
segment of a pass failed.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import re
import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass

from . import __version__
from .chunking import Segment, halve, join_segments, split_text
from .config import Settings
from .estimate import Estimate, RateTracker, estimate
from .llm import FatalError, LLMClient, LLMError, TruncatedError
from .preprocess import PreprocessResult, looks_like_subtitles, preprocess
from .prompts import PromptLibrary
from .steps import Pass, normalise_steps, plan_passes
from .textio import InputError

log = logging.getLogger(__name__)

MIN_TEXT_CHARS = 100
MAX_SPLIT_DEPTH = 2  # a truncated segment is halved, and its halves once more
LENGTH_RATIO_RANGE = (0.4, 2.5)
# Notes that do not mean a segment failed; its output was kept.
WARNING_KINDS = frozenset(
    {"length_changed", "possible_preface", "possible_closing", "main_heading"}
)
EDGE_MAX_CHARS = 200
EDGE_MIN_OVERLAP = 0.5
_EDGE_WORD = re.compile(r"[^\W\d_]{4,}")
LENGTH_CHECK_MIN_CHARS = 500
OUTLINE_MAX_LINES = 40
OUTLINE_MAX_CHARS = 2_000
_HEADING = re.compile(r"^#{1,6}[ \t]+\S.*$", re.MULTILINE)


@dataclass(frozen=True)
class Job:
    text: str
    language: str
    context: str = ""
    steps: tuple[str, ...] = ()
    keep_speakers: bool = True
    source_name: str | None = None


@dataclass(frozen=True)
class Issue:
    pass_name: str
    segment: int  # 1-based, in the numbering of the pass
    kind: str  # message key in i18n
    detail: str = ""  # technical detail without user content


@dataclass(frozen=True)
class Progress:
    done: int
    total: int
    pass_index: int  # 1-based
    pass_count: int
    pass_name: str
    remaining: Estimate | None


@dataclass(frozen=True)
class PassDone:
    pass_name: str
    text: str


@dataclass
class Done:
    text: str
    issues: list[Issue]
    intermediates: dict[str, str]
    steps: tuple[str, ...]
    preprocess_info: PreprocessResult | None = None


class JobFailed(Exception):
    def __init__(self, kind: str, detail: str = ""):
        super().__init__(kind)
        self.kind = kind
        self.detail = detail


def validate_text(text: str, settings: Settings) -> None:
    if len(text.strip()) < MIN_TEXT_CHARS:
        raise InputError("error_text_too_short", minimum=MIN_TEXT_CHARS)
    if len(text) > settings.max_input_chars:
        raise InputError("error_text_too_long", maximum=settings.max_input_chars)


def effective_steps(text: str, steps) -> tuple[str, ...]:
    """Step 0 is forced for subtitle input: timings would otherwise reach the model."""
    steps = set(normalise_steps(steps))
    if looks_like_subtitles(text):
        steps.add("preprocess")
    return normalise_steps(steps)


def lanes_for(pass_: Pass, settings: Settings) -> int:
    if pass_.name == "structure" and settings.consistent_headings:
        return 1  # sequential, so each segment can see the headings before it
    return settings.parallel_requests


def estimate_job(
    text: str, steps, settings: Settings, tracker: RateTracker
) -> tuple[Estimate, int]:
    """Estimate for a job before it starts. Returns (estimate, number of segments)."""
    steps = effective_steps(text, steps)
    if "preprocess" in steps:
        text = preprocess(text).text
    sizes = [len(s.core) for s in split_text(text, settings.chunk_chars)]
    plan = [(sizes, lanes_for(p, settings)) for p in plan_passes(steps)]
    return estimate(plan, tracker), len(sizes)


class Runner:
    def __init__(
        self, settings: Settings, client: LLMClient, prompts: PromptLibrary, tracker: RateTracker
    ):
        self.settings = settings
        self.client = client
        self.prompts = prompts
        self.tracker = tracker

    async def run(self, job: Job) -> AsyncIterator[Progress | PassDone | Done]:
        job_id = secrets.token_hex(4)
        steps = effective_steps(job.text, job.steps)
        text = job.text
        intermediates: dict[str, str] = {}
        info = None
        if "preprocess" in steps:
            info = preprocess(text, keep_speakers=job.keep_speakers)
            text = info.text
            intermediates["preprocess"] = text
            yield PassDone("preprocess", text)
        validate_text(text, self.settings)

        segments = split_text(text, self.settings.chunk_chars)
        passes = plan_passes(steps)
        log.info(
            "job %s: %d chars, %d segments, passes=%s, language=%s",
            job_id,
            len(text),
            len(segments),
            [p.name for p in passes],
            job.language,
        )
        issues: list[Issue] = []
        total = len(segments) * len(passes)
        done = 0
        for index, pass_ in enumerate(passes, start=1):
            yield Progress(
                done,
                total,
                index,
                len(passes),
                pass_.name,
                self._remaining(segments, passes[index - 1 :], 0),
            )
            results: list[list[Segment] | None] = [None] * len(segments)
            async for position, result, new_issues in self._run_pass(job, pass_, segments):
                results[position] = result
                issues.extend(new_issues)
                done += 1
                finished = sum(r is not None for r in results)
                yield Progress(
                    done,
                    total,
                    index,
                    len(passes),
                    pass_.name,
                    self._remaining(segments, passes[index - 1 :], finished),
                )
            failures = [
                i for i in issues if i.pass_name == pass_.name and i.kind not in WARNING_KINDS
            ]
            if len({i.segment for i in failures}) == len(segments):
                last = failures[-1]
                log.warning("job %s: every segment failed in pass %s", job_id, pass_.name)
                raise JobFailed(last.kind, last.detail)
            segments = [piece for result in results for piece in result]
            if pass_.block_mode:
                segments = _paragraph_seams(segments)
            intermediates[pass_.name] = join_segments(segments)
            yield PassDone(pass_.name, intermediates[pass_.name])

        result_text = join_segments(segments)
        if "rag" in steps:
            result_text = front_matter(job, steps) + result_text
        log.info("job %s: finished with %d issue(s)", job_id, len(issues))
        yield Done(result_text, issues, intermediates, steps, info)

    def _remaining(self, segments: list[Segment], passes: list[Pass], finished_in_current: int):
        sizes = sorted((len(s.core) for s in segments), reverse=True)
        plan = []
        for offset, pass_ in enumerate(passes):
            pass_sizes = sizes[finished_in_current:] if offset == 0 else sizes
            plan.append((pass_sizes, lanes_for(pass_, self.settings)))
        return estimate(plan, self.tracker)

    async def _run_pass(self, job: Job, pass_: Pass, segments: list[Segment]):
        """Yield (position, resulting segments, issues) as segments finish."""
        if lanes_for(pass_, self.settings) == 1:
            outputs: list[Segment] = []
            for position, segment in enumerate(segments):
                outline = _outline(outputs) if pass_.name == "structure" else ""
                result, issues = await self._process(job, pass_, segment, position + 1, outline)
                outputs.extend(result)
                yield position, result, issues
            return

        semaphore = asyncio.Semaphore(self.settings.parallel_requests)

        async def worker(position: int, segment: Segment):
            async with semaphore:
                return position, *await self._process(job, pass_, segment, position + 1, "")

        tasks = [asyncio.create_task(worker(i, s)) for i, s in enumerate(segments)]
        try:
            for next_done in asyncio.as_completed(tasks):
                yield await next_done
        finally:
            for task in tasks:
                task.cancel()  # no-op for finished tasks; stops the rest on abort

    async def _process(
        self, job: Job, pass_: Pass, segment: Segment, number: int, outline: str, depth: int = 0
    ) -> tuple[list[Segment], list[Issue]]:
        prompt = self.prompts.render(
            pass_.name, job.language, chunk=segment.core, context=job.context, outline=outline
        )
        label = f"{pass_.name} #{number}" + (f" (part, depth {depth})" if depth else "")
        try:
            completion = await self.client.complete(prompt, label=label)
        except FatalError as exc:
            raise JobFailed(exc.kind, exc.detail) from None
        except TruncatedError as exc:
            parts = halve(segment) if depth < MAX_SPLIT_DEPTH else [segment]
            if len(parts) < 2:
                return [segment], [Issue(pass_.name, number, exc.kind, exc.detail)]
            log.info("%s: truncated, retrying as %d parts", label, len(parts))
            result: list[Segment] = []
            issues: list[Issue] = []
            for part in parts:
                part_result, part_issues = await self._process(
                    job, pass_, part, number, outline, depth + 1
                )
                result.extend(part_result)
                issues.extend(part_issues)
            return result, issues
        except LLMError as exc:
            return [segment], [Issue(pass_.name, number, exc.kind, exc.detail)]

        self.tracker.record(len(segment.core), completion.seconds)
        issues = []
        if len(segment.core) >= LENGTH_CHECK_MIN_CHARS:
            ratio = len(completion.text) / len(segment.core)
            low, high = LENGTH_RATIO_RANGE
            if not low <= ratio <= high:
                issues.append(Issue(pass_.name, number, "length_changed", f"ratio {ratio:.2f}"))
        issues += edge_issues(pass_.name, number, segment.core, completion.text)
        return [segment.with_core(completion.text)], issues


def edge_issues(pass_name: str, number: int, source: str, output: str) -> list[Issue]:
    """Notes on text the model probably added around the edited section.

    A short first or last paragraph whose longer words mostly do not occur in
    the input is likely an introductory or closing remark of the model. It is
    reported, never removed: the check is a heuristic, and deleting text on a
    guess could lose content. A top-level heading in the structure pass is
    reported because the prompt asks for subheadings only.
    """
    issues = []
    if pass_name == "structure" and re.search(r"^# ", output, re.MULTILINE):  # noqa: S105 - a processing pass, not a password
        issues.append(Issue(pass_name, number, "main_heading"))
    paragraphs = [p.strip() for p in re.split(r"\n[ \t]*\n", output) if p.strip()]
    if len(paragraphs) < 2:
        return issues
    known = {w.lower() for w in _EDGE_WORD.findall(source)}
    for kind, paragraph in (
        ("possible_preface", paragraphs[0]),
        ("possible_closing", paragraphs[-1]),
    ):
        words = [w.lower() for w in _EDGE_WORD.findall(paragraph)]
        if paragraph.startswith("#") or len(paragraph) > EDGE_MAX_CHARS or not words:
            continue
        if sum(w in known for w in words) / len(words) < EDGE_MIN_OVERLAP:
            issues.append(Issue(pass_name, number, kind))
    return issues


def _paragraph_seams(segments: list[Segment]) -> list[Segment]:
    """After a pass that adds Markdown blocks, every seam must be a paragraph break."""
    last = len(segments) - 1
    return [
        s if i == last or "\n\n" in s.trail else Segment(s.lead, s.core, "\n\n")
        for i, s in enumerate(segments)
    ]


def _outline(previous: list[Segment]) -> str:
    headings = [m.group(0).strip() for s in previous for m in _HEADING.finditer(s.core)]
    outline = "\n".join(headings[-OUTLINE_MAX_LINES:])
    return outline[-OUTLINE_MAX_CHARS:].lstrip("\n") if outline else ""


def front_matter(job: Job, steps: tuple[str, ...]) -> str:
    """YAML header written by the code, not by the model. JSON strings are valid YAML."""
    lines = ["---", f"language: {json.dumps(job.language)}"]
    if job.context.strip():
        lines.append(f"context: {json.dumps(job.context.strip(), ensure_ascii=False)}")
    if job.source_name:
        lines.append(f"source: {json.dumps(job.source_name, ensure_ascii=False)}")
    lines.append(f"steps: {json.dumps(list(steps))}")
    lines.append(f"created: {json.dumps(dt.date.today().isoformat())}")
    lines.append(f"generator: {json.dumps('stt-to-script ' + __version__)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"
