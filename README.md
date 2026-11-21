# STT to Script

STT to Script is a web interface for cleaning up and structuring transcripts
produced by speech-to-text (STT) systems. It sends the text in sections to a
language model behind an OpenAI-compatible chat-completions API, applies the
processing steps you select, and shows the result in the browser, ready to
download.

It runs as one Python process with a [Gradio](https://www.gradio.app/)
interface. A job is processed within the HTTP request of the browser that
started it. Apart from the language model API, no further services are
required.

## Functions

- Reads pasted text or `.txt`, `.md`, `.srt` and `.vtt` files in UTF-8, UTF-16
  or a common single-byte encoding such as Windows-1250 or Windows-1252.
- Applies the selected steps in a fixed order:
  - **0 Preprocessing** (no language model): removes subtitle numbers and
    timestamps, keeps or removes speaker labels.
  - **1 Recognition errors**: transcription errors, technical terms,
    punctuation.
  - **2 Clean-up**: filler words, false starts, repetitions.
  - **3 Style**: factual, academic wording.
  - **4 Structure**: paragraphs and Markdown headings.
  - **5 RAG**: makes each section understandable on its own and adds a
    metadata header.
- Processes transcripts in German, English, French, Spanish, Italian,
  Portuguese, Dutch and Polish. The result stays in the language of the input.
- Offers its interface in English and German.
- Estimates the duration before a job starts and shows the remaining time
  while it runs.
- Returns the result and the intermediate result of every step as downloads.

## Limitations

- It does not transcribe audio; the input is text.
- It does not keep results. If the browser tab is closed, a running job stops
  and its result is gone.
- It has no user management: everyone who can open the page can use the
  configured model.
- It does not check whether the model output is correct.

Details: [functional description](docs/functional-description.md).

## Quick start

You need Python 3.10 or newer and access to an OpenAI-compatible API, such as a
local inference server or a hosted provider.

```bash
python -m venv .venv
. .venv/bin/activate
pip install "git+https://github.com/maltedreyer-5/stt-to-script@v1.0.0"

export STT_TO_SCRIPT_API_BASE_URL=http://localhost:8000/v1
export STT_TO_SCRIPT_MODEL=your-model-name
stt-to-script --check    # validates the settings and tests the connection
stt-to-script            # serves http://127.0.0.1:7860
```

To try the interface without a model, run the fake backend from a checkout of
this repository and point the tool at it:

```bash
python tests/fake_openai.py --port 8999 &
STT_TO_SCRIPT_API_BASE_URL=http://127.0.0.1:8999/v1 STT_TO_SCRIPT_MODEL=fake stt-to-script
```

## Security note

- **Access control.** The tool has no access control of its own and listens
  on `127.0.0.1` by default. Installations for several users belong behind a
  reverse proxy that handles authentication and TLS. A single shared login is
  available through `STT_TO_SCRIPT_AUTH`.
- **Rights.** Every user who can open the page can submit jobs to the
  configured model.
- **Data flow.** Transcripts are sent to the configured API. With a hosted
  service, they leave your infrastructure.
- **Retention.** Uploads are deleted after reading. Download copies remain in
  Gradio's temporary directory for `STT_TO_SCRIPT_DOWNLOAD_RETENTION_MINUTES`.
- **Browser and telemetry.** Gradio's run history and its telemetry are
  switched off.

Threat model and reporting: [SECURITY.md](SECURITY.md). Changes to the host
system: [system impact](docs/system-impact.md).

## Documentation

The [documentation index](docs/index.md) lists every chapter:

- installation
- configuration
- operation
- architecture
- system impact
- design decisions
- glossary

## Third-party components

| Component | Use | License |
|---|---|---|
| [Gradio](https://github.com/gradio-app/gradio) | web interface | Apache-2.0 |
| [HTTPX](https://github.com/encode/httpx) | HTTP client for the language model API | BSD-3-Clause |
| [charset-normalizer](https://pypi.org/project/charset-normalizer/) | detection of non-UTF-8 encodings | MIT |
| [pytest](https://github.com/pytest-dev/pytest) | tests (development only) | MIT |
| [Ruff](https://github.com/astral-sh/ruff) | linting and formatting (development only) | MIT |
| [Playwright](https://github.com/microsoft/playwright-python) | optional browser tests (development only) | Apache-2.0 |

These packages install further dependencies of their own, each under its own
license.

## License

MIT, see [LICENSE](LICENSE). Copyright © 2026 Malte Dreyer.
