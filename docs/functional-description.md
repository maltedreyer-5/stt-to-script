# Functional description

## Input

A job takes either an uploaded file or pasted text. If both are present, the
file is used and the result notes say so.

| | |
|---|---|
| File types | `.txt`, `.text`, `.md`, `.markdown`, `.srt`, `.vtt` |
| Maximum file size | `STT_TO_SCRIPT_MAX_FILE_MB`, default 10 MB, enforced before the upload is stored |
| Maximum text length | `STT_TO_SCRIPT_MAX_INPUT_CHARS`, default 1,000,000 characters |
| Minimum text length | 100 characters after preprocessing |
| Encodings | UTF-8; UTF-16 and UTF-32 with byte order mark; Windows-1252 and ISO-8859-15 for Western European languages; Windows-1250 and ISO-8859-2 for Polish. The detected encoding is shown in the result notes. |

For files that are not UTF-8, the selected language of the transcript
determines the pair of code pages. Bytes in the range 0x80 to 0x9F select the
Windows code page; without them, the ISO code page is used. If neither applies,
the encoding is determined statistically.

Files containing NUL bytes without a UTF-16/32 byte order mark, or decoding
mostly to control characters, are rejected as binary data.

## Language of the transcript

The interface asks for the language of the transcript: German, English,
French, Spanish, Italian, Portuguese, Dutch or Polish. The selection defaults
to the interface language. It selects the prompts:

- **German** texts are processed with German instructions.
- **All other languages** are processed with English instructions that name
  the language and ask the model to answer in it without translating.

The interface language (English or German) is independent of this choice.

## Context

An optional free-text field for subject areas, terms and names. It is inserted
into every prompt. If the field is empty, the prompts contain a neutral
default sentence.

## Steps

| Step | What it asks for | Language model |
|---|---|---|
| 0 Preprocessing | Remove subtitle numbers, cue timings, WebVTT notes and tags; join cues into paragraphs; keep or remove speaker labels | no |
| 1 Recognition errors | Correct transcription errors, technical terms, spelling and punctuation; no rewording | one pass |
| 2 Clean-up | Remove filler words, false starts and repetitions; complete sentences from the text itself | one pass |
| 3 Style | Rewrite in a factual, academic style | one pass |
| 4 Structure | Paragraphs and Markdown headings (`##`, `###`) | one pass |
| 5 RAG | Make each section understandable on its own; spell out abbreviations once per section; add a metadata header | one pass |

The steps always run in this order, whatever order they are ticked in.

**Steps 1 and 2 together.** When both are selected, they run as a single pass
with a combined prompt. Each preset therefore requires at most three passes.

**Subtitles.** If the input contains cue timings, step 0 runs even if it is
not ticked, and the result notes say so.

**Speaker labels.** Step 0 recognises explicit forms only: `SPEAKER_00:`,
`Speaker 1:` and the equivalents in the supported languages, as well as
WebVTT voice tags. A new paragraph starts when the speaker changes or after a
pause of at least two seconds between cues.

**Structure across sections.** By default the structure pass processes
sections one after another. Each section is told which headings the previous
sections received, so that heading levels continue consistently. The pass is
not parallelised and takes longer than the others; see
`STT_TO_SCRIPT_CONSISTENT_HEADINGS`.

## Presets

| Preset | Steps |
|---|---|
| Correction | 1, 2 |
| Revision | 1, 2, 3 |
| Formatting (default) | 1, 2, 3, 4 |
| Preparation for RAG | 0, 1, 2, 4, 5 |

The RAG preset leaves out the style step, because rewording does not help
retrieval and can shift meaning. After you change ticks, the preset field
shows the matching preset, or “Custom” if none matches.

## Output

- **Preview** renders the result as Markdown; **Text** shows it as plain text
  with a copy button.
- **Downloads**
  - The final result is `<name>.stt-to-script.md`, or `.txt` if neither step 4
    nor step 5 ran.
  - Every pass except the last also gets a file, `<name>.<n>-<pass>.txt` or
    `.md`.
  - `<name>` is the name of the uploaded file, or `transcript` for pasted
    text.
- **Intermediate results** shows the text after each pass.
- **Metadata header (step 5)**: a YAML block with `language`, `context` (if
  given), `source` (file name, if any), `steps`, `created` and `generator`.
  The header is written by the program code from the job settings.
- **Code fence.** If the model returns the whole answer inside a fenced code
  block (```` ``` ````), the fence is removed.

## Notes on a result

The result text itself contains only model output and, for step 5, the
metadata header. Everything else appears in a separate list of notes:

| Note | Meaning |
|---|---|
| encoding detected | the file was not UTF-8; check special characters |
| subtitles detected | step 0 was applied automatically |
| model not reachable / no answer in time | a section failed after all attempts and kept the text of the previous pass |
| answer cut off by the length limit | the section could not be processed even after being split twice, and was left unchanged |
| section rejected | the API rejected the request for this section, which was left unchanged |
| length changed considerably | for a section of at least 500 characters, the output is shorter than 40 % or longer than 250 % of the input; check this section |
| possible introductory remark | the first paragraph of a section is short and its longer words mostly do not occur in the input; the text is kept |
| possible closing remark | the same for the last paragraph; the text is kept |
| top-level heading | the structure step produced a `#` heading although the prompt asks for `##` and below |
| language differs | the text appears to be in another language than the one selected; shown before the start and in the notes |

The remarks and the heading are reported, not removed, because the checks are
heuristics; removing text on a guess could lose content. The language check
counts frequent function words of the eight languages and reports only a clear
result.

A job stops as a whole with an error message in three cases:

- the API rejects the credentials or the model (HTTP 401, 403 or 404);
- every section of a pass failed;
- the estimated duration exceeds the limit.

## Duration

The estimate appears as soon as there is a text. It is a range from 0.75 to
1.5 times the expected duration. Until a few requests have been measured on an
installation, the estimate is marked as not yet based on measurements.

While a job runs, a progress bar shows the current step and the remaining
time. Jobs whose estimate exceeds `STT_TO_SCRIPT_MAX_ESTIMATED_MINUTES`
(default 30) are refused before they start.

**Cancel** stops a running job, and so does closing the browser tab. Requests
already sent to the model are cancelled as well.

## Limits

- **Model output is not checked.** The model can change meaning, drop details
  or add statements; the length check only catches large deviations. Results
  need human review before further use.
- **Output language.** How well a model keeps the language of the input
  depends on the model. A model may still translate. The German prompts do not
  name the output language; with German selected for a text in another
  language, a translation into German is likely. The language warning points
  this out before the start.
- **Section boundaries.** Sections are cut at paragraph and sentence
  boundaries. A transcript without punctuation has no recognisable sentence
  ends; it is cut at a space, which can fall in the middle of a sentence. Each
  section is processed without seeing its neighbours, except for the heading
  outline in step 4.
- **Speaker labels in later steps.** Step 0 keeps speaker labels on request.
  The prompts of steps 1 to 5 contain no instruction about them, so a model may
  change or remove them.
- **Step 5.** The resolution of references such as "this" or "he" is done by
  the model and can pick the wrong referent.
- **Notes on remarks.** The checks for introductory and closing remarks can
  miss a remark that reuses words of the input, and can report a short final
  sentence that the style step reworded strongly.
- **Encodings.** Other single-byte encodings, for example Mac Roman, are
  determined statistically, which can fail. A file whose language does not
  match the selected transcript language can be decoded incorrectly. UTF-8 is
  the reliable choice.
- **Speaker labels.** Only the explicit forms listed above are recognised; a
  generic `Name:` at the start of a line is treated as text.
- **Repeated captions.** A caption that repeats the previous one is dropped
  only if it is shown for less than half a second. A caption that repeats the
  whole previous one and continues it is shortened to the new words. Other
  repetitions are kept as content.
- **The browser must stay open.** Nothing is kept on the server, so a result
  that was not downloaded is lost when the tab is closed.
- **Texts of Gradio itself.** The upload area, the footer links and the
  heading of short error notices ("Error") come from Gradio and follow the
  browser's language, not the interface language of the tool. The messages
  themselves are in the interface language.
- **The estimate is approximate.** It assumes the measured speed holds for the
  whole job and does not include waiting time in the queue.
