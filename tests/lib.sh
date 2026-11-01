# Helpers for the hidden <!-- test --> and <!-- ui: --> markers in the labs.
# tests/run-lab.py sources this file in a subshell with `set -e`.
#   ui_*  do without a browser what a lab step asks the student to do in a UI
#         (Portainer, Harness Open Source, Headlamp). View-only steps do nothing here;
#         they mark where the screenshots go.
#   t_*   checks used by the hidden tests.
#   h_*   Harness Open Source API calls.

STATE="${STATE:-$HOME/.lab-runner}"
mkdir -p "$STATE"

# ---------------------------------------------------------------- checks
t_eq() { # ACTUAL EXPECTED MESSAGE
  if [ "$1" != "$2" ]; then echo "check failed: ${3:-values differ}: got '$1', expected '$2'" >&2; return 1; fi
}

t_contains() { # TEXT MESSAGE   (reads stdin)
  local input; input=$(cat)
  if ! grep -qF -- "$1" <<<"$input"; then
    echo "check failed: ${2:-missing text}: '$1' not found in:" >&2; tail -20 <<<"$input" >&2; return 1
  fi
}

t_get() { # URL: GET with retries (a service may still be starting)
  local i
  for i in $(seq 1 30); do curl -fsS --max-time 5 "$1" && return 0; sleep 2; done
  echo "check failed: GET $1 did not succeed" >&2; return 1
}

t_running() { # CONTAINER
  t_eq "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null)" "true" "container $1 running"
}

t_healthy() { # CONTAINER [SECONDS]: wait until Docker reports the container healthy
  local i st
  for i in $(seq 1 "${2:-60}"); do
    st=$(docker inspect -f '{{.State.Health.Status}}' "$1" 2>/dev/null || true)
    [ "$st" = healthy ] && return 0; sleep 1
  done
  echo "check failed: container $1 is '$st', expected healthy" >&2; return 1
}

t_image() { # IMAGE: the image exists locally
  docker image inspect "$1" >/dev/null 2>&1 || { echo "check failed: image $1 not found" >&2; return 1; }
}

t_tag_in_registry() { # REPO TAG: the local registry has REPO:TAG
  curl -fsS "http://localhost:5000/v2/$1/tags/list" | jq -e --arg t "$2" '.tags | index($t)' >/dev/null \
    || { echo "check failed: registry has no $1:$2" >&2; return 1; }
}

t_rollout() { # NAMESPACE DEPLOYMENT: wait for a Deployment rollout to finish
  kubectl -n "$1" rollout status "deployment/$2" --timeout=180s
}

# ---------------------------------------------------------------- screenshot run
# With SHOTS_DIR set (the screenshot run on a desktop VM), uishots.py also does each UI step in the
# real UI and saves annotated screenshots. It exits 0 when it did the step in the UI.
shots_ui() {
  [ -n "${SHOTS_DIR:-}" ] || return 1
  "${SHOTS_PY:-/opt/shots/bin/python}" "${SHOTS_TOOL:-$HOME/shots-tool/uishots.py}" "$@"
}

# ---------------------------------------------------------------- browser and view-only steps
ui_browser_open() { shots_ui browser_open "$@" || true; }
ui_portainer_view() { shots_ui portainer_view "$@" || true; }
ui_harness_view() { shots_ui harness_view "$@" || true; }
ui_view_execution() { shots_ui view_execution "$@" || true; }
ui_headlamp_view() { shots_ui headlamp_view "$@" || true; }
ui_vscode_new_file() { shots_ui vscode_new_file "$@" || true; }   # PATH SOURCE; the file: block writes the file

# ---------------------------------------------------------------- Portainer
P_URL="${P_URL:-http://localhost:9000}"
P_ADMIN="${P_ADMIN:-admin}"
P_PASSWORD="${P_PASSWORD:-Portainer-Lab-2026}"

# Create the admin user, as the first visit to Portainer does.
ui_portainer_init() {
  shots_ui portainer_init || true
  local i code token
  for i in $(seq 1 30); do curl -fs "$P_URL/api/system/status" >/dev/null && break; sleep 2; done
  token=$(docker logs portainer 2>&1 | grep -o 'setup_token=[^ ]*' | tail -1 | cut -d= -f2 || true)
  code=$(curl -sS -o "$STATE/portainer-init.json" -w '%{http_code}' -X POST "$P_URL/api/users/admin/init" \
    -H 'Content-Type: application/json' ${token:+-H "X-Setup-Token: $token"} \
    -d "{\"Username\":\"$P_ADMIN\",\"Password\":\"$P_PASSWORD\"}")
  case "$code" in
    2*|409) ;;
    *) echo "Portainer admin init returned HTTP $code: $(cat "$STATE/portainer-init.json")" >&2; return 1 ;;
  esac
  # "Get Started" in the UI adds the local Docker environment; do the same.
  local jwt
  jwt=$(curl -fsS -X POST "$P_URL/api/auth" -H 'Content-Type: application/json' \
    -d "{\"Username\":\"$P_ADMIN\",\"Password\":\"$P_PASSWORD\"}" | jq -r .jwt)
  if [ "$(curl -fsS -H "Authorization: Bearer $jwt" "$P_URL/api/endpoints" | jq length)" = 0 ]; then
    curl -fsS -X POST "$P_URL/api/endpoints" -H "Authorization: Bearer $jwt" \
      -F Name=local -F EndpointCreationType=1 >/dev/null
  fi
}

# ---------------------------------------------------------------- Headlamp (state changes go through kubectl)
ui_headlamp_scale() { # NAMESPACE DEPLOYMENT REPLICAS
  shots_ui headlamp_scale "$@" || true
  kubectl -n "$1" scale "deployment/$2" --replicas="$3"
}

ui_headlamp_delete_pod() { # NAMESPACE POD_PREFIX
  shots_ui headlamp_delete_pod "$@" && return 0
  local pod
  pod=$(kubectl -n "$1" get pods -o name | grep -m1 "^pod/$2") || { echo "no pod matching $2 in $1" >&2; return 1; }
  kubectl -n "$1" delete "$pod" --wait=false
}

# ---------------------------------------------------------------- Harness Open Source
H_URL="${H_URL:-http://localhost:3000}"
H_ADMIN="${H_ADMIN:-admin}"
H_PASSWORD="${H_PASSWORD:-Harness-Lab-2026}"

h_ref() { printf '%s' "${1//\//%2F}"; }   # bagtrack/bagtrack -> bagtrack%2Fbagtrack

h_session() {
  curl -fsS -X POST "$H_URL/api/v1/login" -H 'Content-Type: application/json' \
    -d "{\"login_identifier\":\"$H_ADMIN\",\"password\":\"$H_PASSWORD\"}" | jq -r .access_token
}

h_token() { # an API token, created once and cached
  if [ ! -s "$STATE/harness-token" ]; then
    curl -fsS -X POST "$H_URL/api/v1/user/tokens" -H "Authorization: Bearer $(h_session)" \
      -H 'Content-Type: application/json' \
      -d "{\"identifier\":\"lab-runner-$(date +%s)\",\"lifetime\":2592000000000000}" \
      | jq -r .access_token > "$STATE/harness-token"
    chmod 600 "$STATE/harness-token"
  fi
  cat "$STATE/harness-token"
}

h_api() { # METHOD PATH [JSON]
  curl -fsS -X "$1" "$H_URL$2" -H "Authorization: Bearer $(h_token)" \
    -H 'Content-Type: application/json' ${3:+-d "$3"}
}

h_create() { # METHOD PATH JSON: "already exists" (HTTP 409) counts as success
  local code
  code=$(curl -sS -o "$STATE/harness-last.json" -w '%{http_code}' -X "$1" "$H_URL$2" \
    -H "Authorization: Bearer $(h_token)" -H 'Content-Type: application/json' -d "$3")
  case "$code" in
    2*|409) return 0 ;;
    *) echo "HTTP $code from $1 $2: $(cat "$STATE/harness-last.json")" >&2; return 1 ;;
  esac
}

ui_harness_login() { shots_ui harness_login || true; h_token >/dev/null; }

ui_create_project() { shots_ui create_project "$@" || true; h_create POST /api/v1/spaces "{\"identifier\":\"$1\"}"; }

ui_create_repo() { # SPACE REPO
  shots_ui create_repo "$@" || true
  h_create POST /api/v1/repos "{\"parent_ref\":\"$1\",\"identifier\":\"$2\",\"default_branch\":\"main\"}"
}

ui_create_token() { # [NAME]: a token for git over HTTP, stored where `credential.helper store` reads it
  shots_ui create_token "$@" && return 0
  local token
  token=$(curl -fsS -X POST "$H_URL/api/v1/user/tokens" -H "Authorization: Bearer $(h_session)" \
    -H 'Content-Type: application/json' \
    -d "{\"identifier\":\"${1:-git}-$(date +%s)\",\"lifetime\":2592000000000000}" | jq -r .access_token)
  touch ~/.git-credentials && chmod 600 ~/.git-credentials
  { grep -Ev '@localhost(:|%3a|%3A)3000' ~/.git-credentials || true; \
    printf 'http://%s:%s@localhost:3000\n' "$H_ADMIN" "$token"; } > "$STATE/creds"
  cat "$STATE/creds" > ~/.git-credentials && rm -f "$STATE/creds"
}

ui_create_secret() { # SPACE NAME VALUE
  shots_ui create_secret "$@" || true
  local body
  body=$(jq -n --arg s "$1" --arg n "$2" --arg v "$3" '{space_ref:$s, identifier:$n, data:$v}')
  h_create POST /api/v1/secrets "$body"
}

ui_create_pipeline() { # REPO ID YAML_PATH
  shots_ui create_pipeline "$@" || true
  h_create POST "/api/v1/repos/$(h_ref "$1")/pipelines" \
    "{\"identifier\":\"$2\",\"config_path\":\"$3\",\"default_branch\":\"main\"}"
}

ui_add_trigger() { # REPO PIPELINE TRIGGER ACTION[,ACTION]   (push = branch_updated)
  shots_ui add_trigger "$@" || true
  local actions
  actions=$(printf '%s' "$4" | jq -Rc 'split(",")')
  h_create POST "/api/v1/repos/$(h_ref "$1")/pipelines/$2/triggers" \
    "{\"identifier\":\"$3\",\"actions\":$actions,\"disabled\":false}"
}

ui_run_pipeline() { # REPO ID [BRANCH]
  shots_ui run_pipeline "$@" && return 0
  h_api POST "/api/v1/repos/$(h_ref "$1")/pipelines/$2/executions?branch=${3:-main}" >/dev/null
}

h_steps() { # REPO PIPELINE NUMBER: one line per step
  h_api GET "/api/v1/repos/$(h_ref "$1")/pipelines/$2/executions/$3" \
    | jq -r '.stages[]?.steps[]? | "   \(.name): \(.status)"'
}

# h_wait REPO PIPELINE STATUS [--commit SHA]: wait for the newest run (of SHA, default: local HEAD), check its status.
h_wait() {
  local repo=$1 pipe=$2 want=$3 sha ex num="" st="" deadline=$((SECONDS + 900))
  if [ "${4:-}" = --commit ]; then sha=$5; else sha=$(git rev-parse HEAD); fi
  while :; do
    ex=$(h_api GET "/api/v1/repos/$(h_ref "$repo")/pipelines/$pipe/executions?limit=25" \
      | jq -c --arg s "$sha" '[.[] | select(.after == $s)] | max_by(.number) // empty')
    if [ -n "$ex" ]; then
      num=$(jq -r .number <<<"$ex"); st=$(jq -r .status <<<"$ex")
      case "$st" in success|failure|error|killed) break ;; esac
    fi
    [ $SECONDS -lt $deadline ] || { echo "timed out waiting for $pipe (last status '$st')" >&2; return 1; }
    sleep 5
  done
  echo "$pipe #$num: $st"
  h_steps "$repo" "$pipe" "$num"
  t_eq "$st" "$want" "status of $pipe #$num"
}

h_log() { # REPO PIPELINE STEP: the step's log from the newest run
  local num stepno
  num=$(h_api GET "/api/v1/repos/$(h_ref "$1")/pipelines/$2/executions?limit=1" | jq -r '.[0].number')
  stepno=$(h_api GET "/api/v1/repos/$(h_ref "$1")/pipelines/$2/executions/$num" \
    | jq -r --arg s "$3" '.stages[0].steps[] | select(.name == $s) | .number')
  [ -n "$stepno" ] || { echo "h_log: no step $3 in $2 #$num" >&2; return 1; }
  h_api GET "/api/v1/repos/$(h_ref "$1")/pipelines/$2/executions/$num/logs/1/$stepno" \
    | jq -r 'if type == "array" then .[].out else empty end'
}
