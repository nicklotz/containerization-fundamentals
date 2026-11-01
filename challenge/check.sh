#!/usr/bin/env bash
# Grader for the gate-display Dockerfile challenge.
#
# Usage:
#   ./check.sh [IMAGE]        IMAGE defaults to gate-display:challenge
#
# Build the image first, from this folder:
#   docker build -t gate-display:challenge gate-display
#
# The script prints one PASS, FAIL or SKIP line per check and a summary.
# Exit code: 0 when no check failed, 1 when a check failed,
# 2 when Docker or curl cannot be used.

set -uo pipefail

IMAGE="${1:-gate-display:challenge}"
MAX_SIZE_MB=250       # compared with: docker image inspect --format '{{.Size}}' (1 MB = 1,000,000 bytes)
HTTP_TIMEOUT=20       # seconds until GET /health must answer
HEALTHY_TIMEOUT=60    # seconds until Docker must report the container as healthy
CONTAINER="gate-display-check-$$"
WORK_DIR=$(mktemp -d)

PASSED=0
FAILED=0
SKIPPED=0
STARTED=no            # becomes "yes" when docker run succeeded
START_TIME=0

pass() { echo "PASS  $1"; PASSED=$((PASSED + 1)); }
fail() { echo "FAIL  $1"; FAILED=$((FAILED + 1)); }
skip() { echo "SKIP  $1"; SKIPPED=$((SKIPPED + 1)); }
indent() { sed 's/^/      /'; }   # prints extra lines under a result

# shellcheck disable=SC2329  # cleanup is called by the trap below
cleanup() {
    docker rm -f "$CONTAINER" >/dev/null 2>&1
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

summary() {
    echo
    echo "Summary: $PASSED passed, $FAILED failed, $SKIPPED skipped"
    if [ "$FAILED" -gt 0 ]; then
        exit 1
    fi
    exit 0
}

# --- Tools ----------------------------------------------------------------

if ! command -v docker >/dev/null 2>&1; then
    echo "docker is not installed." >&2
    exit 2
fi
if ! docker info >/dev/null 2>&1; then
    echo "Cannot reach the Docker daemon. Check that Docker runs and that 'docker info' works for your user." >&2
    exit 2
fi
if ! command -v curl >/dev/null 2>&1; then
    echo "curl is not installed. Install it with: sudo apt-get install -y curl" >&2
    exit 2
fi

if docker info --format '{{json .DriverStatus}}' 2>/dev/null | grep -q 'io.containerd.snapshotter'; then
    SIZE_MEANING="compressed layers plus unpacked files (containerd image store)"
else
    SIZE_MEANING="unpacked files ($(docker info --format '{{.Driver}}' 2>/dev/null) storage driver)"
fi

echo "Checking image $IMAGE with Docker $(docker version --format '{{.Server.Version}}' 2>/dev/null)"
echo

# --- 1. The image exists ---------------------------------------------------

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    fail "image exists: $IMAGE not found. Build it with: docker build -t $IMAGE gate-display"
    summary
fi
pass "image exists: $IMAGE"

# --- 2. The image runs as a non-root user ----------------------------------

user=$(docker image inspect --format '{{.Config.User}}' "$IMAGE")
user_name=${user%%:*}
if [ -z "$user" ]; then
    fail "non-root user: the image has no USER, so the container runs as root"
elif [ "$user_name" = "root" ] || [ "$user_name" = "0" ]; then
    fail "non-root user: USER is $user"
else
    pass "non-root user: USER is $user"
fi

# --- 3. The image has a HEALTHCHECK ----------------------------------------

healthcheck=$(docker image inspect --format '{{if .Config.Healthcheck}}{{join .Config.Healthcheck.Test " "}}{{end}}' "$IMAGE")
case "$healthcheck" in
    "" | NONE*) fail "HEALTHCHECK: the image has no HEALTHCHECK" ;;
    *) pass "HEALTHCHECK: $healthcheck" ;;
esac

# --- 4. The image is at most MAX_SIZE_MB ------------------------------------

size=$(docker image inspect --format '{{.Size}}' "$IMAGE")
size_mb=$(( (size + 500000) / 1000000 ))
if [ "$size" -le $((MAX_SIZE_MB * 1000000)) ]; then
    pass "size: $size_mb MB, limit $MAX_SIZE_MB MB"
else
    fail "size: $size_mb MB, limit $MAX_SIZE_MB MB"
fi
echo "Docker counts the $SIZE_MEANING." | indent

# --- 5. A container answers GET /health on port 8000 -----------------------

if docker run -d --name "$CONTAINER" -p 127.0.0.1::8000 "$IMAGE" >/dev/null 2>"$WORK_DIR/run.err"; then
    STARTED=yes
    START_TIME=$SECONDS
    port=$(docker port "$CONTAINER" 8000/tcp | head -n 1)
    port=${port##*:}
    answered=no
    stopped=no
    answer=""
    while [ $((SECONDS - START_TIME)) -lt "$HTTP_TIMEOUT" ]; do
        if answer=$(curl -fsS --max-time 2 "http://127.0.0.1:$port/health" 2>/dev/null); then
            answered=yes
            break
        fi
        if [ "$(docker inspect --format '{{.State.Running}}' "$CONTAINER")" != "true" ]; then
            stopped=yes
            break
        fi
        sleep 1
    done
    if [ "$answered" = yes ]; then
        pass "GET /health: answered \"$answer\" after $((SECONDS - START_TIME)) s"
    else
        if [ "$stopped" = yes ]; then
            fail "GET /health: the container stopped before it answered"
        else
            fail "GET /health: no answer with HTTP 200 on port 8000 within $HTTP_TIMEOUT s"
        fi
        echo "Last lines of the container log:" | indent
        docker logs --tail 15 "$CONTAINER" 2>&1 | indent
    fi
else
    fail "GET /health: docker run failed"
    indent < "$WORK_DIR/run.err"
fi

# --- 6. Docker reports the container as healthy ----------------------------

if [ "$STARTED" = yes ]; then
    status=""
    running=true
    while :; do
        status=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$CONTAINER")
        running=$(docker inspect --format '{{.State.Running}}' "$CONTAINER")
        if [ "$status" != "starting" ] || [ "$running" != "true" ] \
            || [ $((SECONDS - START_TIME)) -ge "$HEALTHY_TIMEOUT" ]; then
            break
        fi
        sleep 2
    done
    if [ "$status" = "healthy" ]; then
        pass "health status: healthy after $((SECONDS - START_TIME)) s"
    elif [ -z "$status" ]; then
        fail "health status: Docker has no health status, because the image has no HEALTHCHECK"
    elif [ "$running" != "true" ]; then
        fail "health status: the container stopped"
        docker logs --tail 15 "$CONTAINER" 2>&1 | indent
    else
        fail "health status: \"$status\" after $((SECONDS - START_TIME)) s, expected \"healthy\" within $HEALTHY_TIMEOUT s"
        results=$(docker inspect --format '{{range .State.Health.Log}}exit code {{.ExitCode}}: {{.Output}}{{println}}{{end}}' "$CONTAINER" \
            | grep -v '^$' | tail -n 3)
        if [ -n "$results" ]; then
            echo "Last health check results:" | indent
            echo "$results" | indent
        else
            echo "No health check has run yet. Docker runs the first one after --interval (30 s by default)." | indent
        fi
    fi
else
    fail "health status: the container did not start"
fi

# --- 7. The tests are not in the image -------------------------------------
# docker export writes the container's files as a tar stream. Listing it works
# for every image, also for images without a shell.

if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
    docker create --name "$CONTAINER" "$IMAGE" >/dev/null 2>&1
fi
listing="$WORK_DIR/files.txt"
if docker export "$CONTAINER" 2>/dev/null | tar -tf - > "$listing" 2>/dev/null; then
    gates=$(grep -E '(^|/)gates\.json$' "$listing" | head -n 1)
    app_dir=$(dirname "${gates:-.}")
    if [ "$app_dir" = "." ]; then
        prefix=""
    else
        prefix="${app_dir#./}/"
    fi
    found=$(grep -E '(^|/)test_app\.py$' "$listing" | head -n 3)
    if [ -n "$gates" ] && grep -qxE "(\./)?${prefix}tests/?" "$listing"; then
        found="$found"$'\n'"${prefix}tests/"
    fi
    if [ -n "$found" ]; then
        shown=$(echo "$found" | grep -v '^$' | sed 's#^\./##; s#^#/#' | tr '\n' ' ')
        fail "no tests in the image: found ${shown% }"
        echo "Keep the tests folder out of the build context with a .dockerignore file." | indent
    elif [ -z "$gates" ]; then
        pass "no tests in the image (gates.json was not found either)"
    else
        pass "no tests in the image: the app is in /${prefix%/}"
    fi
else
    fail "no tests in the image: could not export the container file system"
fi

# --- 8. No fixable critical vulnerabilities (needs trivy) ------------------

if command -v trivy >/dev/null 2>&1; then
    if trivy image --quiet --scanners vuln --severity CRITICAL --ignore-unfixed --exit-code 1 "$IMAGE" \
        > "$WORK_DIR/trivy.txt" 2>&1; then
        pass "trivy: no CRITICAL vulnerabilities with a fix available"
    else
        fail "trivy: CRITICAL vulnerabilities with a fix available, or trivy failed (output below)"
        tail -n 40 "$WORK_DIR/trivy.txt" | indent
    fi
else
    skip "trivy: not installed, so the vulnerability scan did not run"
fi

summary
