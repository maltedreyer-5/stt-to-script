# Operation

Each task lists the commands to carry it out and the commands to check the
result. The examples assume the systemd setup from
[installation](installation.md). For a manual start, the same information
appears on the console.

## Check the configuration and the connection

The service runs this check before every start, so a restart is the usual
way to run it:

```bash
sudo systemctl restart stt-to-script
journalctl -u stt-to-script -n 10 --no-pager | grep "start-up check"
```

To run it by hand with the service's settings:

```bash
sudo -u stt-to-script sh -c 'set -a; . /etc/stt-to-script/stt-to-script.env; \
    exec /opt/stt-to-script/venv/bin/stt-to-script --check'
echo "exit status: $?"
```

**Check.**

- Exit status 0 means the configuration is valid.
- The log line `start-up check:` reports one of these:
  - `LLM endpoint reachable`
  - `... model '<name>' is not listed`
  - `... rejected the credentials`
  - `... not reachable`

## Start, stop, status

```bash
sudo systemctl start stt-to-script
sudo systemctl stop stt-to-script
systemctl status stt-to-script
```

**Check.**

```bash
journalctl -u stt-to-script -n 20 --no-pager   # "Running on local URL" after a start
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:7860/   # 200 while it runs
```

Stopping the service ends running jobs; their results are lost.

## Read the logs

```bash
journalctl -u stt-to-script --since today --no-pager
```

At the default level `INFO`, the log contains, per job:

- a short job id, the text length, the number of sections, the passes and the
  language;
- one line per request, with attempt count, duration and `finish_reason`.

Transcript text, context, file names and the API key are not logged.

`DEBUG` additionally logs response bodies of failed requests, truncated to
300 characters. These can repeat parts of the input; use `DEBUG` only for a
specific diagnosis and switch it off again.

## Update

```bash
sudo /opt/stt-to-script/venv/bin/pip install --upgrade \
    "git+https://github.com/maltedreyer-5/stt-to-script@vX.Y.Z"
sudo systemctl restart stt-to-script
```

**Check.**

```bash
/opt/stt-to-script/venv/bin/stt-to-script --version
journalctl -u stt-to-script -n 5 --no-pager
```

The version also appears at the bottom of the page. Read the
[changelog](../CHANGELOG.md) before updating; changes to environment variables
are listed there.

## Calibrate the time estimate

The estimate starts with `STT_TO_SCRIPT_ESTIMATE_SECONDS_PER_1000_CHARS`
(default 6). After three requests it switches to the average of the most
recent measurements. Each restart starts from the configured value again.
A start value close to the real speed gives useful estimates from the first
job on.

1. Process a typical transcript.
2. Read the request durations from the log:

   ```bash
   journalctl -u stt-to-script --since "15 min ago" --no-pager | grep "ok after"
   ```

3. Divide a typical duration by the section length in thousands of
   characters. With the default section size of 10,000 characters, a request
   taking 50 s gives 5.
4. Set the value in the environment file and restart the service.

**Check.** Once a few jobs have run, the estimate in the interface appears
without the remark that it is not based on measurements.

## Replace or adjust prompts

```bash
sudo install -d -m 755 /etc/stt-to-script/prompts/de
sudo cp /opt/stt-to-script/venv/lib/python3*/site-packages/stt_to_script/prompts/de/style.txt \
    /etc/stt-to-script/prompts/de/
sudo editor /etc/stt-to-script/prompts/de/style.txt
echo "STT_TO_SCRIPT_PROMPT_DIR=/etc/stt-to-script/prompts" | sudo tee -a /etc/stt-to-script/stt-to-script.env
sudo systemctl restart stt-to-script
```

**Check.** The unit runs `--check` before starting. A prompt without its
required placeholders stops the start with a message in the journal.

```bash
systemctl is-active stt-to-script && journalctl -u stt-to-script -n 5 --no-pager
```

Process a short test text and compare the result with one from the shipped
prompt.

## Add imprint, privacy notice or contact

Put `footer.en.md` and `footer.de.md` (or one `footer.md`) into a directory
and set `STT_TO_SCRIPT_FOOTER_DIR` to it. Restart the service.

**Check.** The text appears below the interface in the matching language;
switch with `?lang=en` and `?lang=de`.

## Change the shared login

Edit `STT_TO_SCRIPT_AUTH` in the environment file and restart the service.

**Check.** Log in with the new credentials in a private browser window. The
old credentials must be refused.

## Clean up temporary files

With `PrivateTmp=true` (as in the example unit), all temporary files disappear
when the service stops. Without it, look into Gradio's temporary directory:

```bash
sudo ls -la "${GRADIO_TEMP_DIR:-/tmp/gradio}"
```

Download copies older than `STT_TO_SCRIPT_DOWNLOAD_RETENTION_MINUTES` are
removed by the running service. Empty upload directories and empty files named
`tmp*` can be deleted at any time while the service is stopped.

## Try changes without a model

From a checkout:

```bash
python tests/fake_openai.py --port 8999 --delay 0.5 &
STT_TO_SCRIPT_API_BASE_URL=http://127.0.0.1:8999/v1 STT_TO_SCRIPT_MODEL=fake STT_TO_SCRIPT_PORT=7861 stt-to-script
```

The fake backend returns each section unchanged, after a reasoning block and,
for the structure step, a heading. That shows the flow of a job without any
model.

## Uninstall

```bash
sudo systemctl disable --now stt-to-script
sudo rm /etc/systemd/system/stt-to-script.service && sudo systemctl daemon-reload
sudo rm -r /opt/stt-to-script /etc/stt-to-script
sudo userdel stt-to-script
```

Remove the location block from the nginx configuration and reload nginx.

**Check.**

```bash
systemctl status stt-to-script            # "could not be found"
ss -ltnp | grep 7860 || echo "port free"
```

## Limits

- **No status page.** There is no endpoint that reports running jobs or the
  queue; the journal is the only operational record.
- **No result recovery.** Jobs cannot be recovered after a restart.
- **The calibration is not kept.** It lives in memory and starts from the
  configured value after every restart.
