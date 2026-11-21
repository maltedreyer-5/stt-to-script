# Installation

## Requirements

- **Python** 3.10 or newer.
- **An OpenAI-compatible API** with a `/chat/completions` endpoint, reachable
  from the host. An API key is only needed if the API requires one.
- **For use by several people:** a reverse proxy that terminates TLS and
  handles authentication.

The Python dependencies, with version ranges, are declared in
`pyproject.toml`: Gradio 6, HTTPX and charset-normalizer.

## Install

Into a virtual environment, from a release tag:

```bash
python3 -m venv /opt/stt-to-script/venv
/opt/stt-to-script/venv/bin/pip install "git+https://github.com/maltedreyer-5/stt-to-script@v1.0.0"
/opt/stt-to-script/venv/bin/stt-to-script --version
```

For development, from a checkout:

```bash
git clone https://github.com/maltedreyer-5/stt-to-script.git
cd stt-to-script
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## Minimal configuration

Two variables are required:

```bash
export STT_TO_SCRIPT_API_BASE_URL=http://localhost:8000/v1   # up to and including /v1
export STT_TO_SCRIPT_MODEL=your-model-name                   # as the API expects it
```

All other settings have defaults; see [configuration](configuration.md).

Check the configuration and the connection before the first start:

```bash
stt-to-script --check
```

The command exits with status 0 and logs the result of a request to
`<API_BASE_URL>/models`. It exits with status 2 if the configuration is
invalid; the message lists every problem. An unreachable API is logged, but
does not count as an error, because the API may start later than the tool.

Then start the interface:

```bash
stt-to-script
```

By default it serves `http://127.0.0.1:7860`.

## Running as a service (systemd)

[`examples/stt-to-script.service`](../examples/stt-to-script.service) is a
unit for a dedicated system user. It reads its settings from an environment
file, [`examples/stt-to-script.env`](../examples/stt-to-script.env), and
gives the service a private `/tmp` that is removed when the service stops.

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin stt-to-script
sudo install -d -m 750 -o root -g stt-to-script /etc/stt-to-script
sudo install -m 640 -o root -g stt-to-script examples/stt-to-script.env /etc/stt-to-script/
sudo editor /etc/stt-to-script/stt-to-script.env
sudo install -m 644 examples/stt-to-script.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stt-to-script
systemctl status stt-to-script
journalctl -u stt-to-script -n 20
```

The unit runs `stt-to-script --check` before every start. The tool needs no
home directory and writes only to its temporary directory; see
[system impact](system-impact.md).

## Behind nginx

[`examples/nginx-location.conf`](../examples/nginx-location.conf) serves the
tool under the sub-path `/stt-to-script/`. Include it in the `server` block
that terminates TLS, and set the same sub-path in the tool:

```bash
STT_TO_SCRIPT_ROOT_PATH=/stt-to-script
```

Notes on the configuration:

- `proxy_buffering off` lets progress updates through as they happen.
- `X-Forwarded-Host` and `X-Forwarded-Proto` are what Gradio builds its public
  URL from.
- **Port in links.** `$host` carries no port. If the proxy listens on a port
  other than 80 or 443, both header lines need `$http_host`; otherwise
  download links point to the wrong port.
- **Upload size.** `client_max_body_size` must be at least
  `STT_TO_SCRIPT_MAX_FILE_MB`.
- **Long requests.** `proxy_read_timeout` must cover the longest job. The
  example allows one hour.

Check after reloading nginx:

```bash
sudo nginx -t && sudo systemctl reload nginx
curl -sS -o /dev/null -w "%{http_code}\n" https://example.org/stt-to-script/
```

## Authentication

The tool has no user management. Choose one:

- **A reverse proxy with authentication** (SSO, OAuth2 proxy, HTTP basic
  authentication). This is what multi-user installations should use.
- **`STT_TO_SCRIPT_AUTH=user:password`** for a single shared login, handled by
  Gradio. Suitable for small installations; every user shares the same
  credentials.
- **Neither**, for a single person on their own machine. The default binding
  to `127.0.0.1` keeps the port unreachable from other hosts.

## Limits

- **Tested setup.** The nginx example was tested with nginx 1.24 under a
  sub-path, on a non-standard port with `$http_host`. The systemd unit passes
  `systemd-analyze verify`, but has not been run on every distribution.
- **Other proxies.** Apache httpd, Caddy and Traefik work in principle with the
  same headers, but this documentation contains no tested examples for them.
- **Python versions.** CI tests Python 3.10 to 3.13.
- **No container image.** The tool ships as a Python package only.
