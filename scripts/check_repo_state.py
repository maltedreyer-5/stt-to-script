# SPDX-FileCopyrightText: 2026 Malte Dreyer
# SPDX-License-Identifier: MIT
"""Fail if the repository contains run-time state.

Run in a git checkout after the tests. Two checks:

1. No untracked file that is not ignored: anything a test or a local run
   writes into the checkout must either not happen or be covered by
   ``.gitignore``.
2. No tracked file that looks like run-time state or local settings.
"""

from __future__ import annotations

import fnmatch
import subprocess
import sys

FORBIDDEN = (
    "*.env",
    ".env",
    "*__pycache__*",
    "*.pyc",
    ".gradio/*",
    "gradio/*",
    "*.log",
    "RELEASE-CHECKLIST.md",
    "*.egg-info/*",
    ".idea/*",
    "*.iml",
    "*.DS_Store",
)
ALLOWED = ("examples/stt-to-script.env",)


def git(*args: str) -> list[str]:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=True)  # noqa: S603,S607
    return [line for line in result.stdout.splitlines() if line]


def main() -> int:
    try:
        untracked = git("ls-files", "--others", "--exclude-standard")
        tracked = git("ls-files")
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"check_repo_state: not a git checkout ({exc})")
        return 2
    problems = [f"untracked and not ignored: {path}" for path in untracked]
    for path in tracked:
        if path not in ALLOWED and any(fnmatch.fnmatch(path, pattern) for pattern in FORBIDDEN):
            problems.append(f"tracked run-time or settings file: {path}")
    for problem in problems:
        print(problem)
    print(f"check_repo_state: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
