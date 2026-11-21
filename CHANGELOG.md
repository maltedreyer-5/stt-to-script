# Changelog

All notable changes are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-11-21

First public release.

### Added

- Web interface that processes a transcript within the request and shows the
  result in the browser, with downloads of the result and of every
  intermediate step.
- Steps 0 to 5:
  - 0: preprocessing of SRT, WebVTT and timestamped transcripts;
  - 1: recognition errors;
  - 2: clean-up;
  - 3: style;
  - 4: structure;
  - 5: preparation for retrieval with a metadata header.
- Presets: correction, revision, formatting, preparation for RAG.
- Transcripts in German, English, French, Spanish, Italian, Portuguese, Dutch
  and Polish; interface in English and German.
- Lossless splitting at paragraph, line and sentence boundaries, without
  overlap.
- Automatic splitting of sections whose answer reaches the model's output
  limit.
- Removal of reasoning blocks and of a code fence enclosing the whole answer.
- Notes on likely introductory or closing remarks of the model and on top-level
  headings in the structure step; the text is kept.
- Warning when the text appears to be in another language than the one
  selected.
- Detection of UTF-16, UTF-32 and single-byte encodings.
- Duration estimate before a job and remaining time during a job; jobs above
  a configurable duration are refused.
- Cancellation by button or by closing the browser tab.
- Configuration through environment variables; `stt-to-script --check` for
  the configuration and the connection.
- Fake OpenAI-compatible backend for trying the interface without a model.
