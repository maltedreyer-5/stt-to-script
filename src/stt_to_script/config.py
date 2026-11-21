# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Settings, read once from environment variables with the prefix ``STT_TO_SCRIPT_``.

There is deliberately no configuration file and no ``.env`` loader: the
process environment is the single source, so that systemd units, container
definitions and shells all configure the tool the same way.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

PREFIX = "STT_TO_SCRIPT_"

# Keys that EXTRA_BODY may not override, because the pipeline relies on them.
_PROTECTED_BODY_KEYS = frozenset({"model", "messages", "stream", "n"})


class ConfigError(ValueError):
    """Raised when the environment does not describe a usable configuration."""


@dataclass(frozen=True)
class Settings:
    """All runtime settings. Field names match the variable names without prefix."""

    api_base_url: str
    model: str
    api_key: str | None = None
    temperature: float | None = 0.3
    max_tokens: int | None = None
    extra_body: Mapping[str, object] = field(default_factory=dict)
    request_timeout: float = 300.0
    max_attempts: int = 3
    chunk_chars: int = 10_000
    parallel_requests: int = 2
    consistent_headings: bool = True
    max_concurrent_jobs: int = 2
    queue_size: int = 20
    max_file_mb: int = 10
    max_input_chars: int = 1_000_000
    max_estimated_minutes: float = 30.0
    estimate_seconds_per_1000_chars: float = 6.0
    download_retention_minutes: int = 60
    host: str = "127.0.0.1"
    port: int = 7860
    root_path: str = ""
    auth: tuple[str, str] | None = None
    footer_dir: Path | None = None
    prompt_dir: Path | None = None
    show_error_details: bool = False
    log_level: str = "INFO"

    @property
    def chat_completions_url(self) -> str:
        return f"{self.api_base_url}/chat/completions"

    @property
    def models_url(self) -> str:
        return f"{self.api_base_url}/models"

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Build settings from ``environ`` (default: ``os.environ``).

        Empty values count as unset, so ``STT_TO_SCRIPT_TEMPERATURE=`` switches
        the parameter off instead of failing to parse.
        """
        env = os.environ if environ is None else environ
        reader = _Reader(env)
        base_url = reader.required("API_BASE_URL").rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            reader.errors.append(f"{PREFIX}API_BASE_URL must start with http:// or https://")
        settings = cls(
            api_base_url=base_url,
            model=reader.required("MODEL"),
            api_key=reader.text("API_KEY"),
            temperature=reader.number("TEMPERATURE", 0.3, low=0.0, high=2.0, optional=True),
            max_tokens=reader.integer("MAX_TOKENS", None, low=1, optional=True),
            extra_body=reader.json_object("EXTRA_BODY"),
            request_timeout=reader.number("REQUEST_TIMEOUT", 300.0, low=1.0),
            max_attempts=reader.integer("MAX_ATTEMPTS", 3, low=1, high=10),
            chunk_chars=reader.integer("CHUNK_CHARS", 10_000, low=1_000),
            parallel_requests=reader.integer("PARALLEL_REQUESTS", 2, low=1, high=64),
            consistent_headings=reader.boolean("CONSISTENT_HEADINGS", True),
            max_concurrent_jobs=reader.integer("MAX_CONCURRENT_JOBS", 2, low=1, high=64),
            queue_size=reader.integer("QUEUE_SIZE", 20, low=1),
            max_file_mb=reader.integer("MAX_FILE_MB", 10, low=1, high=1_000),
            max_input_chars=reader.integer("MAX_INPUT_CHARS", 1_000_000, low=1_000),
            max_estimated_minutes=reader.number("MAX_ESTIMATED_MINUTES", 30.0, low=1.0),
            estimate_seconds_per_1000_chars=reader.number(
                "ESTIMATE_SECONDS_PER_1000_CHARS", 6.0, low=0.1
            ),
            download_retention_minutes=reader.integer("DOWNLOAD_RETENTION_MINUTES", 60, low=1),
            host=reader.text("HOST") or "127.0.0.1",
            port=reader.integer("PORT", 7860, low=1, high=65_535),
            root_path=(reader.text("ROOT_PATH") or "").rstrip("/"),
            auth=reader.auth("AUTH"),
            footer_dir=reader.directory("FOOTER_DIR"),
            prompt_dir=reader.directory("PROMPT_DIR"),
            show_error_details=reader.boolean("SHOW_ERROR_DETAILS", False),
            log_level=(reader.text("LOG_LEVEL") or "INFO").upper(),
        )
        if settings.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            reader.errors.append(f"{PREFIX}LOG_LEVEL must be DEBUG, INFO, WARNING or ERROR")
        if reader.errors:
            raise ConfigError("Invalid configuration:\n  - " + "\n  - ".join(reader.errors))
        return settings


class _Reader:
    """Collects all problems instead of stopping at the first one."""

    def __init__(self, env: Mapping[str, str]):
        self.env = env
        self.errors: list[str] = []

    def text(self, name: str) -> str | None:
        value = self.env.get(PREFIX + name, "").strip()
        return value or None

    def required(self, name: str) -> str:
        value = self.text(name)
        if value is None:
            self.errors.append(f"{PREFIX}{name} is required")
            return ""
        return value

    def integer(self, name, default, *, low=None, high=None, optional=False):
        raw = self.text(name)
        if raw is None:
            # An explicitly empty optional value means "do not send".
            return None if optional and (PREFIX + name) in self.env else default
        try:
            value = int(raw)
        except ValueError:
            self.errors.append(f"{PREFIX}{name} must be an integer, got {raw!r}")
            return default
        return self._check_range(name, value, low, high, default)

    def number(self, name, default, *, low=None, high=None, optional=False):
        raw = self.text(name)
        if raw is None:
            return None if optional and (PREFIX + name) in self.env else default
        try:
            value = float(raw)
        except ValueError:
            self.errors.append(f"{PREFIX}{name} must be a number, got {raw!r}")
            return default
        return self._check_range(name, value, low, high, default)

    def _check_range(self, name, value, low, high, default):
        if (low is not None and value < low) or (high is not None and value > high):
            bounds = f"between {low} and {high}" if high is not None else f"at least {low}"
            self.errors.append(f"{PREFIX}{name} must be {bounds}, got {value}")
            return default
        return value

    def boolean(self, name: str, default: bool) -> bool:
        raw = self.text(name)
        if raw is None:
            return default
        lowered = raw.lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        self.errors.append(f"{PREFIX}{name} must be true or false, got {raw!r}")
        return default

    def json_object(self, name: str) -> dict:
        raw = self.text(name)
        if raw is None:
            return {}
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            self.errors.append(f"{PREFIX}{name} is not valid JSON: {exc.msg}")
            return {}
        if not isinstance(value, dict):
            self.errors.append(f"{PREFIX}{name} must be a JSON object")
            return {}
        protected = sorted(_PROTECTED_BODY_KEYS & value.keys())
        if protected:
            self.errors.append(f"{PREFIX}{name} must not set {', '.join(protected)}")
        return value

    def auth(self, name: str) -> tuple[str, str] | None:
        raw = self.text(name)
        if raw is None:
            return None
        user, sep, password = raw.partition(":")
        if not sep or not user or not password:
            # Never echo the value: it contains a password.
            self.errors.append(f"{PREFIX}{name} must have the form user:password")
            return None
        return user, password

    def directory(self, name: str) -> Path | None:
        raw = self.text(name)
        if raw is None:
            return None
        path = Path(raw).expanduser()
        if not path.is_dir():
            self.errors.append(f"{PREFIX}{name} is not a directory: {raw}")
            return None
        return path
