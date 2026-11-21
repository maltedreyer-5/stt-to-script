# Configuration

All settings come from environment variables with the prefix `STT_TO_SCRIPT_`.
There is no configuration file. An empty value counts as unset.
`stt-to-script --check` validates all values and reports every problem at once.

## Reference

The table is checked against the code by the test suite: every setting must
appear here with its actual default.

| Variable | Default | Meaning |
|---|---|---|
| `STT_TO_SCRIPT_API_BASE_URL` | required | Base URL of the OpenAI-compatible API, up to and including the version segment, e.g. `http://localhost:8000/v1`. |
| `STT_TO_SCRIPT_MODEL` | required | Model name as the API expects it. |
| `STT_TO_SCRIPT_API_KEY` | unset | Bearer token. Unset means no `Authorization` header is sent. |
| `STT_TO_SCRIPT_TEMPERATURE` | 0.3 | Sampling temperature. Set it to an empty value to leave the parameter out, for APIs that reject it. |
| `STT_TO_SCRIPT_MAX_TOKENS` | unset | Output limit per request. Unset means the parameter is not sent and the API decides. |
| `STT_TO_SCRIPT_EXTRA_BODY` | unset | JSON object merged into every request body, for server-specific options. It may not set `model`, `messages`, `stream` or `n`. |
| `STT_TO_SCRIPT_REQUEST_TIMEOUT` | 300 | Seconds per request. |
| `STT_TO_SCRIPT_MAX_ATTEMPTS` | 3 | Attempts per request for transient errors (timeouts, connection errors, HTTP 429 and 5xx). |
| `STT_TO_SCRIPT_CHUNK_CHARS` | 10000 | Maximum characters per section sent to the model. |
| `STT_TO_SCRIPT_PARALLEL_REQUESTS` | 2 | Sections processed at the same time within one job. |
| `STT_TO_SCRIPT_CONSISTENT_HEADINGS` | true | Run the structure step section by section with the outline so far. `false` runs it in parallel, without the outline. |
| `STT_TO_SCRIPT_MAX_CONCURRENT_JOBS` | 2 | Jobs running at the same time; further jobs wait in the queue. |
| `STT_TO_SCRIPT_QUEUE_SIZE` | 20 | Maximum number of waiting jobs. |
| `STT_TO_SCRIPT_MAX_FILE_MB` | 10 | Maximum upload size in MB. |
| `STT_TO_SCRIPT_MAX_INPUT_CHARS` | 1000000 | Maximum text length in characters. |
| `STT_TO_SCRIPT_MAX_ESTIMATED_MINUTES` | 30 | Jobs with a longer estimated duration are refused before they start. |
| `STT_TO_SCRIPT_ESTIMATE_SECONDS_PER_1000_CHARS` | 6 | Seconds per 1,000 characters and request assumed until the installation has measured its own speed. |
| `STT_TO_SCRIPT_DOWNLOAD_RETENTION_MINUTES` | 60 | How long Gradio keeps its copies of download files. |
| `STT_TO_SCRIPT_HOST` | 127.0.0.1 | Address to listen on. `0.0.0.0` listens on all interfaces. |
| `STT_TO_SCRIPT_PORT` | 7860 | Port to listen on. |
| `STT_TO_SCRIPT_ROOT_PATH` | empty | Sub-path when served behind a reverse proxy, e.g. `/stt-to-script`. |
| `STT_TO_SCRIPT_AUTH` | unset | `user:password` for one shared login handled by Gradio. |
| `STT_TO_SCRIPT_FOOTER_DIR` | unset | Directory with `footer.en.md`, `footer.de.md` or `footer.md`, shown below the interface (imprint, privacy notice, contact). |
| `STT_TO_SCRIPT_PROMPT_DIR` | unset | Directory with prompt files that replace the shipped ones; see below. |
| `STT_TO_SCRIPT_SHOW_ERROR_DETAILS` | false | Show technical error details in the interface. Meant for single-user installations. |
| `STT_TO_SCRIPT_LOG_LEVEL` | INFO | `DEBUG`, `INFO`, `WARNING` or `ERROR`. |

Gradio's own variables apply as well. The relevant one is `GRADIO_TEMP_DIR`,
the directory for uploads and download copies. It defaults to a `gradio`
directory in the system's temporary directory.

## Server-specific options

`STT_TO_SCRIPT_EXTRA_BODY` passes options that are not part of the common API,
for example options that some servers offer to switch off a model's reasoning:

```bash
STT_TO_SCRIPT_EXTRA_BODY='{"chat_template_kwargs": {"enable_thinking": false}}'
```

Which options exist depends on the server and the model. Unknown options are
ignored or rejected by the server; check the server log after changing them.

## Replacing prompts

`STT_TO_SCRIPT_PROMPT_DIR` points to a directory with the same layout as
`src/stt_to_script/prompts/`: `de/<name>.txt` for German texts and
`generic/<name>.txt` for all other languages. Each file found there replaces
the shipped file of the same name; missing files fall back to the shipped
ones.

| Placeholder | Filled with | Required in |
|---|---|---|
| `{chunk}` | the section text | every pass prompt |
| `{context}` | the context field, or the text of `fallback_context.txt` | every pass prompt |
| `{language}` | the English name of the language | every prompt of the `generic` set |
| `{outline}` | headings of the previous sections | `outline_prefix.txt` |

Placeholders are filled in one pass, so placeholder-like text inside a
transcript stays as it is. `stt-to-script --check` refuses prompt files that
lack a required placeholder.

## Limits

- **Settings are read once at start.** Changes take effect after a restart.
- **One shared login.** `STT_TO_SCRIPT_AUTH` supports exactly one user name and
  password; there are no roles.
- **Footer files are trusted input.** They are rendered as Markdown. Gradio
  sanitises the HTML, but the files should still only be writable by the
  operator.
- **No list of models.** The tool does not know which models an API offers;
  `--check` only reports whether the configured one is listed by `/models`.
