#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_AT="${PAPERRADAR_RUN_AT:-11:20}"
LOG_DIR="${PAPERRADAR_LOG_DIR:-logs/daily}"
SCHEDULER_PID_FILE="${PAPERRADAR_SCHEDULER_PID_FILE:-$LOG_DIR/server_daily_scheduler.pid}"
SCHEDULER_LOCK_FILE="${PAPERRADAR_SCHEDULER_LOCK_FILE:-/tmp/paperradar_server_daily_scheduler.lock}"
SCHEDULER_LOG_FILE="$LOG_DIR/server_daily_scheduler_$(date +%F).log"
DRY_RUN="${PAPERRADAR_DRY_RUN:-0}"
RUN_ON_START="${PAPERRADAR_RUN_ON_START:-0}"
RUN_PID="${BASHPID:-$$}"
SLEEP_PID=""

usage() {
  cat <<'EOF'
Usage: scripts/server_daily_loop.sh [--run-at HH:MM] [--run-now] [--dry-run]

Runs a lightweight foreground scheduler that launches server_daily_push.sh once
per day at the configured local server time. Use this when cron is unavailable.

Options:
  --run-at HH:MM  Daily local time to run PaperRadar. Default: 11:20
  --run-now       Run server_daily_push.sh once immediately after startup.
  --dry-run       Pass --dry-run to server_daily_push.sh when the schedule fires or --run-now is used.
  -h, --help      Show this help message.

Environment:
  PAPERRADAR_RUN_AT              Same as --run-at.
  PAPERRADAR_RUN_ON_START        Set to 1 to run once immediately after startup.
  PAPERRADAR_PYTHON              Passed through to server_daily_push.sh.
  PAPERRADAR_CONFIG              Passed through to server_daily_push.sh.
  PAPERRADAR_LOG_DIR             Log directory. Default: logs/daily
  PAPERRADAR_SCHEDULER_PID_FILE  Scheduler PID file.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-at)
      RUN_AT="${2:?Missing value for --run-at}"
      shift 2
      ;;
    --run-now)
      RUN_ON_START=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
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
exec > >(tee -a "$SCHEDULER_LOG_FILE") 2>&1

log() {
  printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

cleanup() {
  if [[ -f "$SCHEDULER_PID_FILE" ]] && [[ "$(cat "$SCHEDULER_PID_FILE" 2>/dev/null || true)" == "$RUN_PID" ]]; then
    rm -f "$SCHEDULER_PID_FILE"
  fi
}

shutdown() {
  log "PaperRadar scheduler stopping"
  if [[ -n "$SLEEP_PID" ]]; then
    kill "$SLEEP_PID" 2>/dev/null || true
  fi
  cleanup
  exit 0
}


run_daily_job() {
  local label="$1"
  local status
  set +e
  if [[ "$DRY_RUN" == "1" ]]; then
    bash scripts/server_daily_push.sh --dry-run
  else
    bash scripts/server_daily_push.sh
  fi
  status=$?
  set -e
  if [[ "$status" == "0" ]]; then
    log "$label run completed"
  else
    log "$label run failed with status=$status; scheduler will continue"
  fi
  return 0
}

seconds_until_next_run() {
  python - "$RUN_AT" <<'PY'
import datetime as dt
import sys

run_at = sys.argv[1]
try:
    hour_s, minute_s = run_at.split(":", 1)
    hour, minute = int(hour_s), int(minute_s)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError
except ValueError:
    raise SystemExit(f"Invalid run time: {run_at!r}; expected HH:MM")

now = dt.datetime.now()
target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
if target <= now:
    target += dt.timedelta(days=1)
print(max(1, int((target - now).total_seconds())))
PY
}

run_scheduler() {
  RUN_PID="${BASHPID:-$$}"
  printf '%s\n' "$RUN_PID" > "$SCHEDULER_PID_FILE"
  trap cleanup EXIT
  trap shutdown INT TERM

  log "============================================================"
  log "PaperRadar scheduler started"
  log "server=$(hostname 2>/dev/null || printf unknown) user=${USER:-unknown} pid=$RUN_PID parent_shell_pid=$$ ppid=$PPID"
  log "root=$ROOT_DIR run_at=$RUN_AT run_on_start=$RUN_ON_START dry_run=$DRY_RUN"
  log "scheduler_log=$SCHEDULER_LOG_FILE scheduler_pid_file=$SCHEDULER_PID_FILE"
  log "scheduler_lock_file=$SCHEDULER_LOCK_FILE"
  log "============================================================"

  if [[ "$RUN_ON_START" == "1" ]]; then
    log "startup run triggered"
    run_daily_job "startup"
  fi

  while true; do
    sleep_seconds="$(seconds_until_next_run)"
    next_time="$(date -d "+${sleep_seconds} seconds" '+%F %T' 2>/dev/null || printf 'unknown')"
    log "next run at $next_time; sleeping ${sleep_seconds}s"
    sleep "$sleep_seconds" &
    SLEEP_PID="$!"
    wait "$SLEEP_PID"
    SLEEP_PID=""

    log "daily run triggered"
    run_daily_job "daily"
  done
}

exec 9>"$SCHEDULER_LOCK_FILE"
if ! flock -n 9; then
  existing_pid="unknown"
  if [[ -f "$SCHEDULER_PID_FILE" ]]; then
    existing_pid="$(cat "$SCHEDULER_PID_FILE" 2>/dev/null || printf 'unknown')"
  fi
  log "another PaperRadar scheduler is already running; exiting existing_pid=$existing_pid"
  exit 0
fi

run_scheduler
