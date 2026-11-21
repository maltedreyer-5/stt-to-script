# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Start the web interface: ``stt-to-script`` or ``python -m stt_to_script``."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from . import __version__
from .config import PREFIX, ConfigError, Settings

ENV_HELP = f"""\
Configuration is read from environment variables:

  {PREFIX}API_BASE_URL     OpenAI-compatible base URL, e.g. http://localhost:8000/v1 (required)
  {PREFIX}MODEL            model name as the API expects it (required)
  {PREFIX}API_KEY          bearer token; leave unset if the API needs none

See docs/configuration.md for all settings and their defaults.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="stt-to-script",
        description="Web interface that cleans up and structures speech-to-text transcripts.",
        epilog=ENV_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"stt-to-script {__version__}")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the configuration and test the connection, then exit",
    )
    args = parser.parse_args(argv)

    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        print("\nRun 'stt-to-script --help' for the required variables.", file=sys.stderr)
        return 2

    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # httpx logs every request URL at INFO; keep that out of normal logs.
    logging.getLogger("httpx").setLevel(
        max(logging.WARNING, logging.getLevelName(settings.log_level))
    )
    log = logging.getLogger("stt_to_script")

    from .llm import LLMClient  # imported late so --help and config errors stay fast
    from .prompts import PromptError, PromptLibrary

    try:
        PromptLibrary(settings.prompt_dir).validate()
    except PromptError as exc:
        print(f"Prompt files are not usable: {exc}", file=sys.stderr)
        return 2

    async def check() -> str:
        async with LLMClient(settings) as client:
            return await client.check_connection()

    log.info("stt-to-script %s, model %s", __version__, settings.model)
    log.info("start-up check: %s", asyncio.run(check()))
    if args.check:
        return 0

    from .ui import App

    app = App(settings)
    app.launch(app.build())
    return 0


if __name__ == "__main__":
    sys.exit(main())
