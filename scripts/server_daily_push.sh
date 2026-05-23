#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PAPERRADAR_PYTHON:-python}"
CONFIG_PATH="${PAPERRADAR_CONFIG:-config/default.json}"
BRANCH="${PAPERRADAR_BRANCH:-main}"
REMOTE="${PAPERRADAR_REMOTE:-origin}"
LOG_DIR="${PAPERRADAR_LOG_DIR:-logs/daily}"
COMMIT_PREFIX="${PAPERRADAR_COMMIT_PREFIX:-Update PaperRadar digest}"
DRY_RUN="${PAPERRADAR_DRY_RUN:-0}"
DRY_RUN_SLEEP_SECONDS="${PAPERRADAR_DRY_RUN_SLEEP_SECONDS:-0}"
PREVIOUS_DIGEST_FILE=""

usage() {
  cat <<'EOF'
Usage: scripts/server_daily_push.sh [--dry-run] [--sleep SECONDS]

Options:
  --dry-run        Write startup logs, acquire the lock, and print planned steps without
                   pulling, running PaperRadar, committing, or pushing.
  --sleep SECONDS  In dry-run mode, keep the job alive for SECONDS to test locking.
  -h, --help       Show this help message.

Environment:
  PAPERRADAR_PYTHON          Python executable. Default: python
  PAPERRADAR_CONFIG          Config file path. Default: config/default.json
  PAPERRADAR_REMOTE          Git remote. Default: origin
  PAPERRADAR_BRANCH          Git branch. Default: main
  PAPERRADAR_LOG_DIR         Log directory. Default: logs/daily
  PAPERRADAR_DRY_RUN         Set to 1 for dry-run mode.
  PAPERRADAR_DRY_RUN_SLEEP_SECONDS
                             Dry-run lock-test sleep duration.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --sleep)
      DRY_RUN_SLEEP_SECONDS="${2:?Missing value for --sleep}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/server_daily_$(date +%F).log"
LOCK_FILE="${PAPERRADAR_LOCK_FILE:-/tmp/paperradar_server_daily.lock}"
PID_FILE="${PAPERRADAR_PID_FILE:-$LOG_DIR/server_daily.pid}"
RUN_PID="${BASHPID:-$$}"

log() {
  printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

write_pid_file() {
  printf '%s\n' "$RUN_PID" > "$PID_FILE"
}

cleanup_pid_file() {
  if [[ -f "$PID_FILE" ]] && [[ "$(cat "$PID_FILE" 2>/dev/null || true)" == "$RUN_PID" ]]; then
    rm -f "$PID_FILE"
  fi
}

log_startup_info() {
  local host_name
  local fqdn
  local python_path
  local git_head
  local git_remote_url

  host_name="$(hostname 2>/dev/null || printf 'unknown')"
  fqdn="$(hostname -f 2>/dev/null || printf 'unknown')"
  python_path="$(command -v "$PYTHON_BIN" 2>/dev/null || printf '%s' "$PYTHON_BIN")"
  git_head="$(git rev-parse --short HEAD 2>/dev/null || printf 'unknown')"
  git_remote_url="$(git remote get-url "$REMOTE" 2>/dev/null || printf 'unknown')"

  log "============================================================"
  log "PaperRadar server job started"
  log "start_time=$(date --iso-8601=seconds 2>/dev/null || date '+%F %T %z')"
  log "server=$host_name fqdn=$fqdn user=${USER:-unknown} pid=$RUN_PID parent_shell_pid=$$ ppid=$PPID"
  log "root=$ROOT_DIR"
  log "python=$PYTHON_BIN python_path=$python_path"
  log "config=$CONFIG_PATH remote=$REMOTE branch=$BRANCH git_head=$git_head"
  log "remote_url=$git_remote_url"
  log "log_file=$LOG_FILE lock_file=$LOCK_FILE pid_file=$PID_FILE"
  log "dry_run=$DRY_RUN dry_run_sleep_seconds=$DRY_RUN_SLEEP_SECONDS"
  log "============================================================"
}

run_once() {
  write_pid_file
  trap cleanup_pid_file EXIT
  log_startup_info

  PREVIOUS_DIGEST_FILE="$LOG_DIR/latest_before_${RUN_PID}.json"
  if [[ -f docs/data/latest.json ]]; then
    cp docs/data/latest.json "$PREVIOUS_DIGEST_FILE"
    log "previous_digest_snapshot=$PREVIOUS_DIGEST_FILE"
  else
    PREVIOUS_DIGEST_FILE=""
    log "previous_digest_snapshot=none"
  fi

  if [[ -f .env ]]; then
    log ".env found; local secrets will be loaded by PaperRadar"
  else
    log "warning: .env not found"
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    log "dry-run: would run: git fetch $REMOTE $BRANCH"
    log "dry-run: would run: git pull --rebase --autostash $REMOTE $BRANCH"
    log "dry-run: would run: bash scripts/run_daily.sh run --config $CONFIG_PATH --python $PYTHON_BIN"
    log "dry-run: would run: git add data/daily docs"
    log "dry-run: would commit changed public outputs and push to $REMOTE/$BRANCH"
    log "dry-run: would send digest email only for new papers from the latest arXiv published day"
    if [[ "$DRY_RUN_SLEEP_SECONDS" != "0" ]]; then
      log "dry-run: sleeping for $DRY_RUN_SLEEP_SECONDS seconds to test lock behavior"
      sleep "$DRY_RUN_SLEEP_SECONDS"
    fi
    log "PaperRadar server dry-run finished"
    log "pid_file_removed=true"
    return 0
  fi

  git fetch "$REMOTE" "$BRANCH"
  git pull --rebase --autostash "$REMOTE" "$BRANCH"

  run_output="$(bash scripts/run_daily.sh run --config "$CONFIG_PATH" --python "$PYTHON_BIN")"
  printf '%s
' "$run_output"
  if [[ "$run_output" == Rendered* ]]; then
    bash scripts/run_daily.sh aggregate-local --config "$CONFIG_PATH" --python "$PYTHON_BIN"
  else
    log "no new fetched papers; skipping local aggregation"
  fi

  git add data/daily docs

  if git diff --cached --quiet; then
    log "no public digest changes to commit"
  else
    git commit -m "$COMMIT_PREFIX $(date +%F)"
    git push "$REMOTE" "HEAD:$BRANCH"
    log "changes pushed to $REMOTE/$BRANCH"
    email_args=(--input docs/data/latest.json --latest-published-day)
    if [[ -n "$PREVIOUS_DIGEST_FILE" && -f "$PREVIOUS_DIGEST_FILE" ]]; then
      email_args+=(--since "$PREVIOUS_DIGEST_FILE")
    fi
    if "$PYTHON_BIN" -m paperradar.cli email "${email_args[@]}"; then
      log "digest email step completed"
    else
      log "warning: digest email step failed; continuing"
    fi
  fi

  if [[ -n "$PREVIOUS_DIGEST_FILE" ]]; then
    rm -f "$PREVIOUS_DIGEST_FILE"
  fi

  log "PaperRadar server job finished"
  log "pid_file_removed=true"
}

(
  flock -n 9 || {
    existing_pid="unknown"
    if [[ -f "$PID_FILE" ]]; then
      existing_pid="$(cat "$PID_FILE" 2>/dev/null || printf 'unknown')"
    fi
    log "another PaperRadar server job is already running; exiting existing_pid=$existing_pid lock_file=$LOCK_FILE"
    exit 0
  }
  run_once
) 9>"$LOCK_FILE" 2>&1 | tee -a "$LOG_FILE"
