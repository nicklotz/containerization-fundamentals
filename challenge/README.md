# Challenge: a Dockerfile for gate-display

gate-display is a small Flask web application. It shows the departure gate of each flight at the hub. gunicorn serves it on port 8000.

## Your task

Write two files:

- `gate-display/Dockerfile`
- `gate-display/.dockerignore`

Then build the image from this folder and grade it:

```bash
docker build -t gate-display:challenge gate-display
./check.sh
```

## Requirements

The image must:

1. Start the application with gunicorn on port 8000: `gunicorn --bind 0.0.0.0:8000 app:app`.
2. Run as a user that is not root.
3. Have a `HEALTHCHECK` that requests `GET /health`.
4. Be 250 MB or smaller, as measured by check.sh (see below).
5. Answer `GET /health` within 20 seconds after the container starts.
6. Reach the Docker health status `healthy` within 60 seconds after the container starts.
7. Not contain the `tests` folder.
8. Have no CRITICAL vulnerabilities that have a fix available. check.sh runs this check only if trivy is installed.

## The application

| Path | Answer |
|---|---|
| `/` | An HTML table of the gates. |
| `/api/gates` | The same data as JSON. |
| `/health` | `ok` |

| File | Content |
|---|---|
| `gate-display/app.py` | The application. |
| `gate-display/gates.json` | The gate data. The application reads it for every request. |
| `gate-display/requirements.txt` | Flask and gunicorn, with fixed versions. |
| `gate-display/tests/test_app.py` | Tests. Run them on your machine. They do not belong in the image. |

To run the tests and the application on your machine:

```bash
cd gate-display
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt pytest
python -m pytest -q
gunicorn --bind 0.0.0.0:8000 app:app
```

## What check.sh does

```bash
./check.sh [IMAGE]
```

`IMAGE` defaults to `gate-display:challenge`. check.sh needs Docker, curl and tar. trivy is optional.

check.sh reads the image settings with `docker image inspect`. It starts a container with port 8000 published on 127.0.0.1, sends requests to `/health` and waits for the health status. It lists the container's files with `docker export` to look for the tests. At the end it removes the container.

It prints one `PASS`, `FAIL` or `SKIP` line per requirement and a summary. The exit code is 0 when no check failed and 1 when a check failed.

## How check.sh measures the image size

check.sh compares the `Size` field of `docker image inspect` with 250 MB (250,000,000 bytes). You can read the same number yourself:

```bash
docker image inspect --format '{{.Size}}' gate-display:challenge
```

Docker 29 uses the containerd image store on new installations. With this store, the number is the size of the compressed layers plus the size of the unpacked files. `docker image ls` shows the same number in the DISK USAGE column and the compressed part alone in the CONTENT SIZE column.

An older installation that still uses the overlay2 storage driver counts only the unpacked files, so the same image measures smaller there. check.sh prints which way your Docker counts.

For orientation, calculated from the registry data for linux/amd64 in November 2026: the `python:3.15-slim` image alone comes to about 181 MB with the containerd store (44 MB compressed plus 137 MB unpacked). Flask and gunicorn add about 10 MB.

## Hints

- Compare the official Python images before you choose one: `python:3.15`, `python:3.15-slim` and `python:3.15-alpine`.
- Copy `requirements.txt` and install the packages before you copy the application code. Then a code change does not reinstall the packages.
- `pip install --no-cache-dir` keeps pip's download cache out of the image.
- The slim and alpine images contain neither curl nor wget. Python can send the HTTP request for the health check with the `urllib.request` module.
- Every file in the folder is sent to Docker as the build context unless `.dockerignore` excludes it. Look for `tests/`, `.venv/`, `__pycache__/` and `.pytest_cache/`.
- `useradd` (Debian-based images) and `adduser` (Alpine) create a user. The `USER` instruction makes the following instructions and the container run as that user.
- gunicorn 26 creates a control socket in `$HOME/.gunicorn`. If the user has no writable home directory, gunicorn logs `Control server error: ... Permission denied` and keeps running. The gunicorn option `--no-control-socket` turns the control socket off.
- With the default `HEALTHCHECK` settings, Docker runs the first check 30 seconds after the container starts. The options `--interval`, `--timeout`, `--start-period` and `--retries` change that.
- `docker inspect --format '{{json .State.Health}}' CONTAINER` shows the results of the last health checks.
- If trivy reports vulnerabilities in the base image, pull the newest version of your base image tag and build again.
