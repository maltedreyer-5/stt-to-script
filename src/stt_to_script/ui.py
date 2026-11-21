# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Gradio interface.

Processing runs inside the request and the result is returned to the
browser; nothing is stored on the server beyond the lifetime of the job:

* an uploaded file is deleted as soon as it has been read;
* download files are written to a per-job directory that is removed when
  the job ends; Gradio keeps its own copy in its cache, which
  ``delete_cache`` clears after ``DOWNLOAD_RETENTION_MINUTES``;
* Gradio's run history (which would keep inputs and results in the browser
  and can upload them to a Hugging Face bucket) and its telemetry are off.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import time
from pathlib import Path

import gradio as gr

from . import __version__
from .config import Settings
from .estimate import RateTracker
from .i18n import (
    DEFAULT_UI_LANGUAGE,
    PROCESSING_LANGUAGES,
    UI_LANGUAGES,
    count,
    detect_language,
    format_duration,
    format_range,
    t,
)
from .language import identify
from .llm import LLMClient
from .pipeline import (
    Done,
    Job,
    JobFailed,
    PassDone,
    Progress,
    Runner,
    effective_steps,
    estimate_job,
)
from .prompts import PromptLibrary
from .steps import DEFAULT_PRESET, PRESETS, STEP_ORDER, normalise_steps, plan_passes, preset_for
from .textio import InputError, read_upload

log = logging.getLogger(__name__)

PASS_NAMES = ("preprocess", "correct_clean", "correct", "clean", "style", "structure", "rag")
PRESET_ORDER = ("correction", "revision", "formatting", "rag", "custom")


def format_int(value: int, lang: str) -> str:
    text = f"{value:,}"
    return text.replace(",", ".") if lang == "de" else text


def _message(exc: InputError, lang: str) -> str:
    params = dict(exc.params)
    for key in ("maximum", "minimum"):
        if isinstance(params.get(key), int):
            params[key] = format_int(params[key], lang)
    return t(exc.code, lang, **params)


class App:
    def __init__(
        self,
        settings: Settings,
        client_factory=None,
        tracker: RateTracker | None = None,
        prompts: PromptLibrary | None = None,
    ):
        self.settings = settings
        self.client_factory = client_factory or (lambda: LLMClient(settings))
        self.tracker = tracker or RateTracker(settings.estimate_seconds_per_1000_chars)
        self.prompts = prompts or PromptLibrary(settings.prompt_dir)
        self.prompts.validate()
        self.footers = {lang: self._read_footer(lang) for lang in UI_LANGUAGES}

    # --- helpers ------------------------------------------------------------

    def _read_footer(self, lang: str) -> str:
        directory = self.settings.footer_dir
        if directory is None:
            return ""
        for name in (f"footer.{lang}.md", "footer.md"):
            path = directory / name
            if path.is_file():
                return path.read_text(encoding="utf-8")
        return ""

    def _footer(self, lang: str) -> str:
        parts = [t("disclaimer", lang)]
        if self.footers.get(lang):
            parts.append(self.footers[lang])
        parts.append(f"stt-to-script {__version__}")
        return "\n\n".join(parts)

    @staticmethod
    def _step_choices(lang: str):
        return [(t(f"step_{step}", lang), step) for step in STEP_ORDER]

    @staticmethod
    def _preset_choices(lang: str):
        return [(t(f"preset_{name}", lang), name) for name in PRESET_ORDER]

    def _read_input(self, file_path, pasted, language, lang, notes):
        """Return (text, source name). Deletes an uploaded file after reading it."""
        if file_path:
            try:
                decoded = read_upload(file_path, self.settings.max_file_mb * 1_048_576, language)
            finally:
                _remove_quietly(file_path)
            if pasted and pasted.strip():
                notes.append(t("input_both", lang))
            if decoded.guessed:
                notes.append(t("encoding_guessed", lang, encoding=decoded.encoding))
            return decoded.text, Path(file_path).name
        if pasted and pasted.strip():
            return pasted.replace("\r\n", "\n"), None
        raise InputError("error_no_input")

    # --- event handlers -----------------------------------------------------

    def on_load(self, request: gr.Request):
        lang = detect_language(
            request.query_params.get("lang") if request else None,
            request.headers.get("accept-language") if request else None,
        )
        default_processing = lang if lang in PROCESSING_LANGUAGES else DEFAULT_UI_LANGUAGE
        c = self.components
        return {
            c["lang"]: lang,
            c[
                "title"
            ]: f"# {t('title', lang)}\n\n{t('intro', lang)}\n\n{t('language_switch', lang)}",
            c["tab_file"]: gr.update(label=t("tab_file", lang)),
            c["tab_text"]: gr.update(label=t("tab_text", lang)),
            c["file"]: gr.update(label=t("file_label", lang)),
            c["text"]: gr.update(
                label=t("text_label", lang), placeholder=t("text_placeholder", lang)
            ),
            c["language"]: gr.update(
                label=t("language_label", lang),
                info=t("language_info", lang),
                value=default_processing,
            ),
            c["context"]: gr.update(
                label=t("context_label", lang),
                placeholder=t("context_placeholder", lang),
                info=t("context_info", lang),
            ),
            c["preset"]: gr.update(
                label=t("preset_label", lang), choices=self._preset_choices(lang)
            ),
            c["steps"]: gr.update(
                label=t("steps_label", lang),
                info=t("steps_info", lang),
                choices=self._step_choices(lang),
            ),
            c["keep_speakers"]: gr.update(
                label=t("keep_speakers_label", lang), info=t("keep_speakers_info", lang)
            ),
            c["estimate"]: t("estimate_empty", lang),
            c["notice"]: t("keep_tab_open", lang),
            c["start"]: gr.update(value=t("start_button", lang)),
            c["stop"]: gr.update(value=t("stop_button", lang)),
            c["status"]: gr.update(label=t("status_label", lang), value=t("status_waiting", lang)),
            c["tab_preview"]: gr.update(label=t("result_preview", lang)),
            c["tab_result_text"]: gr.update(label=t("result_text", lang)),
            c["result_text"]: gr.update(label=t("result_text", lang)),
            c["downloads"]: gr.update(label=t("downloads_label", lang)),
            c["intermediates"]: gr.update(label=t("intermediates_label", lang)),
            **{c[f"mid_{name}"]: gr.update(label=t(f"pass_{name}", lang)) for name in PASS_NAMES},
            c["footer"]: self._footer(lang),
        }

    def on_preset(self, preset):
        if preset in PRESETS:
            return gr.update(value=list(PRESETS[preset]))
        return gr.update()

    def on_steps(self, steps):
        return gr.update(value=preset_for(steps or ()) or "custom")

    def on_estimate(self, file_path, pasted, steps, language, lang):
        lang = lang or DEFAULT_UI_LANGUAGE
        steps = normalise_steps(steps or ())
        try:
            if file_path:
                text = read_upload(file_path, self.settings.max_file_mb * 1_048_576).text
            elif pasted and pasted.strip():
                text = pasted
            else:
                return t("estimate_empty", lang)
        except InputError as exc:
            return t("estimate_unavailable", lang, reason=_message(exc, lang))
        steps_run = effective_steps(text, steps)
        passes = plan_passes(steps_run)
        if not passes:
            return t("estimate_no_passes", lang)
        est, segments = estimate_job(text, steps_run, self.settings, self.tracker)
        line = t(
            "estimate_line",
            lang,
            range=format_range(est.low, est.high, lang),
            segments=count("sections", segments, lang),
            passes=count("passes", len(passes), lang),
        )
        if est.expected / 60 > self.settings.max_estimated_minutes:
            line = t(
                "error_estimate_too_long",
                lang,
                range=format_range(est.low, est.high, lang),
                limit=round(self.settings.max_estimated_minutes),
            )
        if not est.calibrated:
            line += t("estimate_uncalibrated", lang)
        if "preprocess" in steps_run and "preprocess" not in steps:
            line += " " + t("subtitles_detected", lang)
        mismatch = self._language_mismatch(text, language, lang)
        if mismatch:
            line += " " + mismatch
        return line

    @staticmethod
    def _language_mismatch(text, language, lang) -> str:
        detected = identify(text)
        if detected and language and detected != language:
            return t(
                "language_mismatch",
                lang,
                detected=PROCESSING_LANGUAGES[detected],
                selected=PROCESSING_LANGUAGES[language],
            )
        return ""

    async def on_process(
        self,
        file_path,
        pasted,
        language,
        context,
        steps,
        keep_speakers,
        lang,
        progress=gr.Progress(),  # noqa: B008 - Gradio injects the tracker via this default
    ):
        lang = lang or DEFAULT_UI_LANGUAGE
        c = self.components
        notes: list[str] = []
        workdir = None
        started = time.monotonic()
        try:
            if not steps:
                raise InputError("error_no_steps")
            text, source_name = self._read_input(file_path, pasted, language, lang, notes)
            if len(text) > self.settings.max_input_chars:
                raise InputError("error_text_too_long", maximum=self.settings.max_input_chars)
            selected = normalise_steps(steps)
            steps_run = effective_steps(text, selected)
            if "preprocess" in steps_run and "preprocess" not in selected:
                notes.append(t("subtitles_detected", lang))
            mismatch = self._language_mismatch(text, language, lang)
            if mismatch:
                notes.append(mismatch)
            est, _ = estimate_job(text, steps_run, self.settings, self.tracker)
            if est.expected / 60 > self.settings.max_estimated_minutes:
                raise _error(
                    lang,
                    t(
                        "error_estimate_too_long",
                        lang,
                        range=format_range(est.low, est.high, lang),
                        limit=round(self.settings.max_estimated_minutes),
                    ),
                )
            # The upload is already deleted; clearing the field shows that.
            yield {**self._reset_outputs(), c["file"]: None}
            job = Job(
                text=text,
                language=language,
                context=context or "",
                steps=steps_run,
                keep_speakers=bool(keep_speakers),
                source_name=source_name,
            )
            client = self.client_factory()
            try:
                runner = Runner(self.settings, client, self.prompts, self.tracker)
                async for event in runner.run(job):
                    if isinstance(event, Progress):
                        status = t(
                            "status_pass",
                            lang,
                            index=event.pass_index,
                            count=event.pass_count,
                            name=t(f"pass_{event.pass_name}", lang),
                            done=event.done,
                            total=event.total,
                            range=format_range(event.remaining.low, event.remaining.high, lang),
                        )
                        progress(event.done / max(event.total, 1), desc=status)
                        yield {c["status"]: status}
                    elif isinstance(event, PassDone):
                        yield {
                            c[f"mid_{event.pass_name}"]: gr.update(value=event.text, visible=True),
                            c["preview"]: event.text,
                            c["result_text"]: event.text,
                        }
                    elif isinstance(event, Done):
                        workdir = Path(tempfile.mkdtemp(prefix="stt-to-script-"))
                        files = _write_downloads(workdir, event, source_name)
                        duration = format_duration(time.monotonic() - started, lang)
                        yield {
                            c["status"]: t("status_done", lang, duration=duration),
                            c["preview"]: event.text,
                            c["result_text"]: event.text,
                            c["downloads"]: [str(f) for f in files],
                            c["issues"]: gr.update(
                                value=self._issues_markdown(event, notes, lang),
                                visible=bool(event.issues or notes),
                            ),
                        }
            finally:
                await client.aclose()
        except InputError as exc:
            raise _error(lang, _message(exc, lang)) from None
        except JobFailed as exc:
            message = t("job_failed", lang, message=t(exc.kind, lang))
            if self.settings.show_error_details and exc.detail:
                message += " " + t("error_details", lang, detail=exc.detail)
            raise _error(lang, message) from None
        except gr.Error:
            raise
        except Exception as exc:
            log.exception("unexpected error while processing a job")
            message = t("error_internal", lang)
            if self.settings.show_error_details:
                message += " " + t("error_details", lang, detail=f"{type(exc).__name__}: {exc}")
            raise _error(lang, message) from None
        finally:
            if workdir is not None:
                shutil.rmtree(workdir, ignore_errors=True)

    def _reset_outputs(self):
        c = self.components
        updates = {
            c["preview"]: "",
            c["result_text"]: "",
            c["downloads"]: None,
            c["issues"]: gr.update(value="", visible=False),
        }
        updates.update(
            {c[f"mid_{name}"]: gr.update(value="", visible=False) for name in PASS_NAMES}
        )
        return updates

    @staticmethod
    def _issues_markdown(event: Done, notes: list[str], lang: str) -> str:
        lines = [f"**{t('issues_heading', lang)}**", ""]
        lines += [f"- {note}" for note in notes]
        for issue in event.issues:
            lines.append(
                "- "
                + t(
                    "issue_line",
                    lang,
                    segment=issue.segment,
                    name=t(f"pass_{issue.pass_name}", lang),
                    message=t(issue.kind, lang),
                )
            )
        return "\n".join(lines)

    # --- layout ---------------------------------------------------------------

    def build(self) -> gr.Blocks:
        lang = DEFAULT_UI_LANGUAGE
        c: dict[str, gr.components.Component] = {}
        retention = self.settings.download_retention_minutes * 60
        with gr.Blocks(
            title=t("title", lang),
            analytics_enabled=False,
            delete_cache=(min(600, retention), retention),
        ) as app:
            c["lang"] = gr.State(lang)
            c["title"] = gr.Markdown(f"# {t('title', lang)}\n\n{t('intro', lang)}")
            with gr.Row():
                with gr.Column(scale=3):
                    with gr.Tabs():
                        with gr.Tab(t("tab_file", lang)) as c["tab_file"]:
                            c["file"] = gr.File(
                                label=t("file_label", lang),
                                type="filepath",
                                file_types=[".txt", ".text", ".md", ".markdown", ".srt", ".vtt"],
                            )
                        with gr.Tab(t("tab_text", lang)) as c["tab_text"]:
                            c["text"] = gr.Textbox(
                                label=t("text_label", lang),
                                lines=10,
                                max_lines=20,
                                placeholder=t("text_placeholder", lang),
                            )
                    with gr.Row():
                        c["language"] = gr.Dropdown(
                            choices=[(name, code) for code, name in PROCESSING_LANGUAGES.items()],
                            value=lang,
                            label=t("language_label", lang),
                            info=t("language_info", lang),
                        )
                        c["context"] = gr.Textbox(
                            label=t("context_label", lang),
                            lines=2,
                            placeholder=t("context_placeholder", lang),
                            info=t("context_info", lang),
                        )
                with gr.Column(scale=2):
                    c["preset"] = gr.Dropdown(
                        choices=self._preset_choices(lang),
                        value=DEFAULT_PRESET,
                        label=t("preset_label", lang),
                    )
                    c["steps"] = gr.CheckboxGroup(
                        choices=self._step_choices(lang),
                        value=list(PRESETS[DEFAULT_PRESET]),
                        label=t("steps_label", lang),
                        info=t("steps_info", lang),
                    )
                    c["keep_speakers"] = gr.Checkbox(
                        value=True,
                        label=t("keep_speakers_label", lang),
                        info=t("keep_speakers_info", lang),
                    )
            c["estimate"] = gr.Markdown(t("estimate_empty", lang))
            c["notice"] = gr.Markdown(t("keep_tab_open", lang))
            with gr.Row():
                c["start"] = gr.Button(t("start_button", lang), variant="primary")
                c["stop"] = gr.Button(t("stop_button", lang), variant="secondary")
            c["status"] = gr.Textbox(
                label=t("status_label", lang),
                value=t("status_waiting", lang),
                interactive=False,
                lines=1,
            )
            c["issues"] = gr.Markdown(visible=False)
            with gr.Tabs():
                with gr.Tab(t("result_preview", lang)) as c["tab_preview"]:
                    c["preview"] = gr.Markdown()
                with gr.Tab(t("result_text", lang)) as c["tab_result_text"]:
                    c["result_text"] = gr.Textbox(
                        label=t("result_text", lang),
                        lines=16,
                        max_lines=40,
                        buttons=["copy"],
                        interactive=False,
                    )
            c["downloads"] = gr.File(
                label=t("downloads_label", lang), file_count="multiple", interactive=False
            )
            with gr.Accordion(t("intermediates_label", lang), open=False) as c["intermediates"]:
                for name in PASS_NAMES:
                    c[f"mid_{name}"] = gr.Textbox(
                        label=t(f"pass_{name}", lang),
                        lines=6,
                        max_lines=20,
                        buttons=["copy"],
                        interactive=False,
                        visible=False,
                    )
            c["footer"] = gr.Markdown(self._footer(lang))
            self.components = c

            app.load(
                self.on_load,
                None,
                list(c.values()),
                api_visibility="private",
                concurrency_limit=None,
            )
            c["preset"].input(
                self.on_preset,
                c["preset"],
                c["steps"],
                api_visibility="private",
                concurrency_limit=None,
            )
            c["steps"].input(
                self.on_steps,
                c["steps"],
                c["preset"],
                api_visibility="private",
                concurrency_limit=None,
            )
            estimate_inputs = [c["file"], c["text"], c["steps"], c["language"], c["lang"]]
            for trigger in (
                c["file"].change,
                c["text"].change,
                c["steps"].change,
                c["language"].change,
            ):
                trigger(
                    self.on_estimate,
                    estimate_inputs,
                    c["estimate"],
                    api_visibility="private",
                    concurrency_limit=None,
                    show_progress="hidden",
                )
            outputs = [
                c[k] for k in ("file", "status", "preview", "result_text", "downloads", "issues")
            ]
            outputs += [c[f"mid_{name}"] for name in PASS_NAMES]
            run = c["start"].click(
                self.on_process,
                [
                    c["file"],
                    c["text"],
                    c["language"],
                    c["context"],
                    c["steps"],
                    c["keep_speakers"],
                    c["lang"],
                ],
                outputs,
                api_visibility="private",
                concurrency_limit=self.settings.max_concurrent_jobs,
                concurrency_id="process",
            )
            c["stop"].click(None, None, None, cancels=[run])
        return app

    def launch(self, app: gr.Blocks) -> None:
        app.queue(max_size=self.settings.queue_size)
        app.launch(
            server_name=self.settings.host,
            server_port=self.settings.port,
            root_path=self.settings.root_path or None,
            auth=self.settings.auth,
            max_file_size=f"{self.settings.max_file_mb}mb",
            show_error=self.settings.show_error_details,
            footer_links=["gradio", "settings"],
            run_history=False,
        )


def _write_downloads(directory: Path, event: Done, source_name: str | None) -> list[Path]:
    stem = Path(source_name).stem if source_name else "transcript"
    markdown = any(step in event.steps for step in ("structure", "rag"))
    final = directory / f"{stem}.stt-to-script.{'md' if markdown else 'txt'}"
    final.write_text(event.text, encoding="utf-8")
    files = [final]
    names = list(event.intermediates)
    for number, name in enumerate(names, start=1):
        if name == names[-1]:
            continue  # the final result already contains the last pass
        text = event.intermediates[name]
        extension = "md" if name in ("structure", "rag") else "txt"
        path = directory / f"{stem}.{number}-{name}.{extension}"
        path.write_text(text, encoding="utf-8")
        files.append(path)
    return files


def _error(lang: str, message: str) -> gr.Error:
    """A user-facing error. Expected errors need no traceback in the server log."""
    return gr.Error(message, title=t("error_title", lang), print_exception=False)


def _remove_quietly(path) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
