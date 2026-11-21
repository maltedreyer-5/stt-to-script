# Security

## Supported versions

Security fixes are made for the latest release only.

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub:
<https://github.com/maltedreyer-5/stt-to-script/security/advisories/new>.
Do not open a public issue.

Please include:

- the version (`stt-to-script --version`) and the Gradio version
  (`pip show gradio`);
- how the tool was deployed (behind a proxy or not, `STT_TO_SCRIPT_AUTH` set
  or not);
- the steps to reproduce.

Do not send real transcripts or credentials. Reports are read and answered,
but there is no guaranteed response time.

## Deployment contexts

The threat model below assumes one of two contexts:

1. **Shared installation.** For example at a university or another
   organisation: several users in an internal network, behind a reverse proxy
   that terminates TLS and authenticates users. The API is run by the same
   organisation or contracted by it.
2. **Single user.** One person on their own machine, with the default binding
   to `127.0.0.1`, using a local or hosted API.

## Assets

- **Transcripts and results.** They may contain personal data: names, health
  information, assessments.
- **The API key**, if one is configured.
- **The capacity of the API**, which costs money or compute.

## What the tool defends against

| Threat | Measure |
|---|---|
| Command execution or file access through input (text, context field, file names) | No shell is invoked and no path is derived from user input. The upload path comes from Gradio and is only read and deleted. Checked in CI with Ruff's security rules. |
| Data left behind on the server | Uploads are deleted after reading; per-job files are removed when the job ends; Gradio's download copies expire after the retention time. Logs at `INFO` contain no content. |
| Data kept in or sent from the browser | Gradio's run history (browser storage, optional upload to a Hugging Face bucket) and telemetry are switched off. |
| Leaking the API key | The key is only sent to the configured API. It does not appear in the interface, in log output or in error messages. |
| Unbounded resource use by one request | Upload size, text length, estimated duration, concurrent jobs and queue length are limited. |
| Markup injection through model output | The preview is rendered with Gradio's Markdown component, which sanitises HTML. |
| Accidental exposure | The default binding is `127.0.0.1`. |

## Out of scope

The following points concern the design or the deployment and are outside
the scope of vulnerability reports.

- **Users are not separated.** The tool has no user management. Everyone who
  can open the page has the same rights and can use the configured model.
  `STT_TO_SCRIPT_AUTH` provides a single shared login. Authentication of
  individual users is the task of the reverse proxy.
- **Exposure by configuration.** Binding to `0.0.0.0`, or publishing the port
  without authentication or TLS, is an operating error. So is running the
  tool on an untrusted network without a proxy.
- **Use of capacity by authorised users.** The limits apply per job. Quotas
  per user are not provided.
- **Prompt injection.** A transcript can contain text that the model treats as
  an instruction. Its effect is limited to the result of that same job, which
  the submitting user receives. There is no shared state through which one
  job could affect another.
- **Content produced by the model.** Wrong, invented or omitted statements in
  results are a property of language models; results need human review.
- **The configured API and its provider.** What the API logs, stores or uses
  the texts for is decided by its operator. Choosing a hosted provider means
  sending the texts there.
- **Debug logging.** At `STT_TO_SCRIPT_LOG_LEVEL=DEBUG`, truncated response
  bodies of failed requests are logged and may contain parts of the input.
  This is documented behaviour for diagnosis.
- **Operator-supplied files.** Prompt files (`STT_TO_SCRIPT_PROMPT_DIR`),
  footer files (`STT_TO_SCRIPT_FOOTER_DIR`) and the environment file are
  trusted input, writable only by the operator.
- **The host and the browser.** A compromised host, browser or browser
  extension can read everything the tool processes.
- **Vulnerabilities in Gradio or other dependencies.** Please report these to
  the respective project. Report them here as well if this tool's
  configuration makes them exploitable or worse.

## Assumptions about the environment

- **The host** is trusted, and only administrators can read the environment
  file and the temporary directory.
- **TLS** is terminated by the reverse proxy in shared installations.
- **The API** is reached over a network path the operator trusts, or over
  HTTPS.
- **The browser** of each user is the user's own.
