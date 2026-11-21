# System impact

This chapter lists what the tool changes on a host and how to undo each
change. Statements marked *measured* were observed with version 1.0.0 and
Gradio 6.30.0, running as an unprivileged user without a home directory, with
`/` as working directory, behind nginx.

## Summary

| Area | Change | Undo |
|---|---|---|
| Installed files | a virtual environment; optionally a unit file, an environment file, an nginx location | delete them ([uninstall](operations.md#uninstall)) |
| System users | optionally one system user, if you follow the example setup | `userdel stt-to-script` |
| Processes and ports | one process listening on `127.0.0.1:7860` by default | stop the service |
| Files at run time | temporary files in two directories, see below | automatic, or delete while stopped |
| Network | requests to the configured API only | stop the service |
| Browser | no transcript content in browser storage | not applicable |
| Logs | job metadata on standard output | your log rotation |

## Installed files

`pip install` writes only into the chosen virtual environment. The tool
changes no system configuration itself. The example files in `examples/` are
copied by the operator, if at all.

## Files written at run time

The tool writes only into the system's temporary directory (*measured*: no
writes elsewhere, with a read-only working directory and no home directory).
Two places are involved:

**Gradio's temporary directory** (`GRADIO_TEMP_DIR`, default `<tmp>/gradio`):

| Content | Lifetime |
|---|---|
| uploaded file, in a directory with a hash name | the tool deletes the file right after reading it; the empty directory remains (*measured*) |
| copies of download files | deleted by the running service once they are older than `STT_TO_SCRIPT_DOWNLOAD_RETENTION_MINUTES`; according to the Gradio documentation, the cache is also cleared when the server restarts |
| empty files named `tmp*`, two per upload | not removed by the tool (*measured*) |
| an empty directory `vibe_edit_history` | created by Gradio at start (*measured*) |

**A per-job directory** `stt-to-script-*` in the temporary directory holds the
download files while they are being handed to Gradio. It is removed when the
job ends (*measured* for completed jobs). The removal sits in a `finally`
block, so it also runs on errors and cancellation.

**Undo.**

- With `PrivateTmp=true`, as in the example unit, the whole private `/tmp`
  is removed when the service stops.
- Without it, delete `<tmp>/gradio` while the service is stopped.

## Network

**Incoming:** one TCP port, `STT_TO_SCRIPT_HOST:STT_TO_SCRIPT_PORT`.

**Outgoing from the server:** requests to
`STT_TO_SCRIPT_API_BASE_URL`:

- `/models` once at start;
- `/chat/completions` per section and pass.

Gradio's telemetry is switched off. *Measured:* during start and a complete
job, no further outgoing connection was attempted through the configured HTTP
proxy. Direct connections that bypass a proxy could not be observed in the
test environment.

**Outgoing from the browser:** *measured:* the page loads all its resources
from the tool's own address, fonts included. It makes no requests to other
hosts.

**What leaves the host:** each request contains the prompt, the context field
and the text of one section. What the API does with them is outside this
tool. If the API is a hosted service, the transcripts leave your
infrastructure.

## Browser

Gradio's run history is switched off. With it on, Gradio would keep inputs and
results in the browser and offer to upload them to a Hugging Face bucket.

*Measured:* after a complete job, no transcript content was in the page's
`localStorage` or `sessionStorage`. Gradio may keep interface settings of its
own there.

## Logs

The tool logs to standard error. At `INFO` it logs job metadata (text length,
number of sections, passes, language), one line per request (attempts,
duration, `finish_reason`), and warnings. At `DEBUG` it also logs truncated
response bodies of failed requests, which can contain parts of the input. See
[reading the logs](operations.md#read-the-logs).

## Limits

- **Measurement scope.** The measurements cover the code paths of a normal
  job and of the start. Other Gradio features that the tool does not use were
  not examined.
- **Gradio updates.** Gradio is a dependency with its own release cycle. A
  later Gradio version can write further files or make further connections.
  Repeat the checks above after updating Gradio.
- **Other components.** The tool does not control what the configured API, a
  reverse proxy or the browser log or store.
