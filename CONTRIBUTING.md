# Contributing

Thank you for considering a contribution. Please open an issue before larger
changes, so that the approach can be agreed first.

## Language

- **English:** code, comments, docstrings, documentation, commit messages,
  issues and pull requests.
- **Interface texts:** `src/stt_to_script/i18n.py`, always in English *and*
  German. A text missing in one language fails the tests.
- **German prompts:** `src/stt_to_script/prompts/de/` is in German; it is the
  prompt set for German transcripts. All other prompts are in English.

`scripts/check_language.py` enforces this.

## Checked

A change counts as checked when all of these pass. CI runs exactly the same
commands:

```bash
pip install -e ".[dev]"
ruff check .
ruff format --check .
python scripts/check_language.py
pytest
python scripts/check_repo_state.py      # in a git checkout, after the tests
```

Changes to the interface also need the browser tests:

```bash
pip install -e ".[dev,e2e]" && playwright install chromium
STT_TO_SCRIPT_E2E=1 pytest tests/e2e
```

To look at a change in the browser without a model, use the fake backend; see
[operation](docs/operations.md#try-changes-without-a-model).

## Invariants

These rules protect properties that break silently, without an error message.
Each is covered by tests; keep it that way.

1. **No user input reaches a shell or a path.** Text, context and file names
   are data. The upload path comes from Gradio and is only read and deleted.
2. **Display texts are not used as keys.** Steps and presets are identified
   by fixed identifiers (`steps.STEP_ORDER`, `steps.PRESETS`). Labels are
   looked up from these identifiers.
3. **Splitting is lossless and does not overlap.** Joining unprocessed
   segments must give back the input exactly (`tests/test_text_units.py`).
4. **Only model output goes into the result text**, plus the metadata header
   written by the code. Errors, notes and markers belong in the issue list
   shown next to the result.
5. **Logs at `INFO` contain no user content and no API key.** User content
   comprises transcript, context and file names. Log calls record sizes,
   counts, identifiers and durations.
6. **Placeholders are filled in one pass** (`prompts.PromptLibrary.render`).
   Replacing them one after another alters transcripts that contain
   placeholder-like text.
7. **Repetitions are content.** Preprocessing removes only what is provably
   an artefact of the subtitle format: a caption shown for less than half a
   second, or a caption that repeats the previous one and continues it.
8. **Jobs are async generators.** Only then does Gradio cancel them, together
   with their requests, when the browser tab closes.
9. **Privacy defaults stay on.** Keep `run_history=False` and
   `analytics_enabled=False`, delete uploads after reading, and bind to
   `127.0.0.1` by default.

## Prompts

Prompt changes change results for every user. In a pull request that changes
a prompt, describe the effect on at least one example text, and say which
models you tried. Do not include confidential transcripts.

## Releases

The version is defined once, in `src/stt_to_script/__init__.py`. It must match
the first entry in `CHANGELOG.md` and `version` in `CITATION.cff`; the tests
check this.
