# Design decisions

This chapter records the main design decisions and the reasons for them.

## Processing within the request

A job runs in the HTTP request of the browser session that started it, and
the result is returned in the same request. The deployment consists of one
process. A job queue, a mail server and a result store are not required.

Consequences:

- The browser tab must remain open until the job has finished.
- Reverse proxies must permit requests that last as long as a job.
- Jobs whose estimated duration exceeds `STT_TO_SCRIPT_MAX_ESTIMATED_MINUTES`
  are refused.

The job is implemented as an async generator. Gradio cancels a running async
generator when the client disconnects, and the cancellation propagates to the
HTTP requests in flight. Both are covered by tests.

## Section boundaries without overlap

Sections are cut at paragraph, line or sentence boundaries and do not overlap.
An overlapping passage would be edited twice, and the two edited versions
cannot be merged reliably. Because the cuts fall on boundaries, no overlap is
required to keep sentences intact.

## Handling of output limits

The available output length depends on the model, on the server and, for
reasoning models, on the length of the reasoning. The program cannot determine
it in advance. If an answer ends with `finish_reason: length`, the section is
split in two and both halves are processed again; each half may be split once
more. The default section size of 10,000 characters therefore remains usable
with models whose output limit is smaller.

## Prompt sets

German transcripts are processed with German instructions (set `de`).
Transcripts in the other supported languages share one set of English
instructions (set `generic`) that names the language of the text. A single
shared set limits the number of prompt files to be maintained. Native
instructions for each language would require a review in each language. The
German set is written in German and is not a translation of the English set.

## Combined pass for steps 1 and 2

Recognition errors and clean-up frequently concern the same passages. When
both steps are selected, one prompt covers both, and each preset requires at
most three passes.

## Sequential structure pass

The choice of headings depends on the preceding text. The structure pass
therefore processes the sections in order and passes the headings produced so
far to each following request. The pass is not parallelised.
`STT_TO_SCRIPT_CONSISTENT_HEADINGS=false` selects parallel processing without
the outline.

## Metadata header

The YAML header of step 5 contains values known to the program: language,
steps, source name, date and version. The program code writes the header; the
model is not involved.

## Content of the result text

The result text consists of model output and, for step 5, the metadata header.
Error messages and notes are listed separately next to the result. A section
whose processing fails keeps the text it had before the pass. Results are
often passed on to other systems unread; any additional content in the text
would be carried along.

## Removal of reasoning blocks

If the output contains a closing reasoning tag without a matching opening tag,
the text up to and including the first closing tag is removed. Cutting at the
last occurrence could remove answer text that contains the tag. Cutting at the
first occurrence can, in the worst case, leave reasoning text in the result,
where a reader will see it.

## Notes instead of deletions

A model sometimes adds an introductory sentence, a closing remark or a
top-level heading. These are detected with heuristics and reported next to
the result; the text itself is left as the model returned it. A false
positive then costs a glance, while a deletion on a wrong guess would lose
content without anyone noticing. A code fence around the whole answer is the
exception: it can be recognised exactly and is removed.

## Interface language

The interface language is determined once per session on the server, from the
query parameter `lang` and the `Accept-Language` header. Labels and the
messages generated during a job use the same language. Gradio's `gr.I18n`
resolves translations in the browser from the browser locale. It covers
neither messages generated on the server nor a choice of language by link.

## Identifiers and labels

Steps and presets have fixed internal identifiers. Labels are looked up from
these identifiers. A change to a label has no effect on processing.

## Defaults that affect privacy

- The program binds to `127.0.0.1`.
- Uploads are deleted after reading.
- Log output at level `INFO` contains no content.
- Gradio's run history and telemetry are switched off.

With the corresponding framework defaults, inputs and results would be kept in
the browser and usage data would be sent to the framework's developers.

## Configuration through environment variables

All settings are read from the process environment. systemd units, container
definitions and shell sessions all provide environment variables in the same
way. A second configuration source, with rules of precedence, is not used.

## Limits

- Recordings whose processing exceeds the duration limit have to be split
  before upload.
- For languages other than German, the quality of the output depends on how
  well the model follows English instructions about a text in another
  language.
- With models that have a small output limit, the splitting of sections costs
  additional requests.
