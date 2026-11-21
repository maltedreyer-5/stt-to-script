# Glossary

**Chat-completions API.** The HTTP interface `POST /v1/chat/completions`,
introduced by OpenAI and offered by many inference servers and providers. In
this documentation, "OpenAI-compatible" means an API that accepts this
request format.

**Context field.** Free text that names the subject area, terms and names. It
is inserted into every prompt.

**Cue.** One entry of a subtitle file: an optional number, a timing line and
one or more lines of text.

**finish_reason.** A field in the API answer. `stop` means the model ended
its answer itself; `length` means it hit the output limit and the answer is
incomplete.

**Front matter / metadata header.** A YAML block between two `---` lines at the
start of a Markdown file. Step 5 adds one.

**Job.** One run of the selected steps over one input.

**Pass.** One round of requests to the model, one per segment. Steps 1 and 2
together form a single pass.

**Preset.** A named selection of steps.

**Prompt set.** The prompt files for one group of languages: `de` for German,
`generic` (English instructions) for all other languages.

**RAG (retrieval-augmented generation).** A setup in which a language model
answers questions with the help of passages retrieved from a document
collection. Step 5 prepares text so that individual sections are
understandable when retrieved on their own.

**Reasoning block.** Text in which a reasoning model writes out its
intermediate steps, marked with tags such as `<think>…</think>`. The tool
removes it.

**Root path.** The sub-path under which a reverse proxy serves the tool, for
example `/stt-to-script`.

**Section / segment.** A part of the text of at most `CHUNK_CHARS` characters,
cut at a paragraph, line or sentence boundary. The interface says "section";
the code says "segment".

**Speaker label.** A marker that names who is speaking, such as `SPEAKER_00:`
or a WebVTT voice tag `<v Name>`.

**SRT (SubRip).** A subtitle format: numbered cues with timings like
`00:00:01,000 --> 00:00:03,000`.

**STT (speech-to-text).** Automatic transcription of spoken language.

**Step.** One of the processing stages 0 to 5 that can be selected in the
interface.

**WebVTT.** A subtitle format starting with `WEBVTT`, with timings like
`00:01.000 --> 00:03.000`, optional notes and voice tags.

## Limits

The glossary explains the terms in the sense used in this documentation. It
does not define them in general.
