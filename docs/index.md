# Documentation

| Chapter | For whom | Content |
|---|---|---|
| [Functional description](functional-description.md) | users, deciders | inputs, steps, presets, languages, outputs |
| [Installation](installation.md) | operators | requirements, installation, service setup, reverse proxy |
| [Configuration](configuration.md) | operators | every setting with its default |
| [Operation](operations.md) | operators | recurring tasks, each with commands to check the result |
| [System impact](system-impact.md) | operators, IT security | what the tool changes on a host, and how to undo it |
| [Architecture](architecture.md) | developers | modules, data flow, concurrency, failure handling |
| [Design decisions](design/decisions.md) | developers | why the tool works the way it does |
| [Glossary](glossary.md) | everyone | terms used in this documentation |

Security model and reporting: [SECURITY.md](../SECURITY.md). Contributing:
[CONTRIBUTING.md](../CONTRIBUTING.md).

## Limits of this documentation

The documentation describes version 1.0.0. The prompts it refers to are the
files under `src/stt_to_script/prompts/`. Wherever this documentation and the
code disagree, the code is right and the documentation is wrong; please report
it.
