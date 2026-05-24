#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

REMOTE="${PAPERRADAR_REMOTE:-origin}"
BRANCH="${PAPERRADAR_BRANCH:-main}"
LOG_DIR="${PAPERRADAR_LOG_DIR:-logs/daily}"
SCHEDULER_PID_FILE="$LOG_DIR/server_daily_scheduler.pid"
JOB_PID_FILE="$LOG_DIR/server_daily.pid"
STATUS=0

ok() { printf '[OK] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*"; STATUS=1; }
info() { printf '[INFO] %s\n' "$*"; }

check_pid() {
  local label="$1"
  local pid_file="$2"
  if [[ ! -f "$pid_file" ]]; then
    warn "$label pid file missing: $pid_file"
    return
  fi
  local pid
  pid="$(tr -d '[:space:]' < "$pid_file")"
  if [[ -z "$pid" ]]; then
    warn "$label pid file is empty: $pid_file"
    return
  fi
  if ps -p "$pid" > /dev/null 2>&1; then
    ok "$label running pid=$pid"
  else
    warn "$label pid not running pid=$pid file=$pid_file"
  fi
}

printf 'PaperRadar health check\n'
printf 'time=%s\n' "$(date --iso-8601=seconds 2>/dev/null || date '+%F %T %z')"
printf 'root=%s\n' "$ROOT_DIR"
printf '\n'

check_pid "scheduler" "$SCHEDULER_PID_FILE"
if [[ -f "$JOB_PID_FILE" ]]; then
  check_pid "active job" "$JOB_PID_FILE"
else
  info "no active job pid file; scheduler is between runs"
fi

printf '\nGit\n'
local_head="$(git rev-parse --short HEAD 2>/dev/null || true)"
remote_head="$(git ls-remote "$REMOTE" "refs/heads/$BRANCH" 2>/dev/null | awk '{print substr($1,1,7)}')"
if [[ -n "$local_head" ]]; then ok "local HEAD $local_head"; else warn "cannot read local HEAD"; fi
if [[ -n "$remote_head" ]]; then ok "$REMOTE/$BRANCH $remote_head"; else warn "cannot read remote $REMOTE/$BRANCH"; fi
if [[ -n "$local_head" && -n "$remote_head" ]]; then
  if [[ "$local_head" == "$remote_head" ]]; then ok "local and remote are aligned"; else warn "local and remote differ: local=$local_head remote=$remote_head"; fi
fi
if git diff --quiet && git diff --cached --quiet; then ok "working tree clean"; else warn "working tree has uncommitted changes"; fi

printf '\nPublic JSON\n'
python -c 'import json
from pathlib import Path
paths = [Path("docs/data/latest.json"), Path("docs/data/latest.arxiv.json"), Path("docs/data/latest.eartharxiv.json")]
for path in paths:
    if not path.exists():
        print(f"[WARN] missing {path}")
        continue
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[WARN] invalid JSON {path}: {exc}")
        continue
    papers = data.get("papers", [])
    fallback = [item.get("paper", {}).get("arxiv_id", "") for item in papers if not item.get("analysis", {}).get("llm_used")]
    markdown = sum(1 for item in papers if item.get("analysis", {}).get("source") == "markdown")
    print("[OK] {}: date={} papers={} markdown={} fallback={}".format(path, data.get("date"), len(papers), markdown, len(fallback)))
    if fallback:
        print("[WARN] fallback ids: {}".format(", ".join(fallback[:10])))'

printf '\nFailure Report\n'
failure_report="data/status/latest_failures.json"
if [[ -f "$failure_report" ]]; then
  if ! python -c 'import json, sys
from pathlib import Path
path = Path("data/status/latest_failures.json")
data = json.loads(path.read_text(encoding="utf-8"))
failure_count = int(data.get("failure_count") or 0)
print("[OK] {}: digest_date={} papers={} failures={} by_stage={}".format(path, data.get("digest_date"), data.get("paper_count"), failure_count, data.get("by_stage", {})))
for item in data.get("failures", [])[:10]:
    print("[WARN] {stage} {source}:{paper_id} {error}".format(**item))
sys.exit(1 if failure_count else 0)'
  then
    STATUS=1
  fi
else
  info "no local failure report yet: $failure_report"
fi

printf '\nLogs\n'
latest_log="$(ls -1t "$LOG_DIR"/server_daily_*.log 2>/dev/null | head -n 1)"
if [[ -n "$latest_log" ]]; then
  ok "latest job log $latest_log"
  tail -n 8 "$latest_log" | sed 's/^/[LOG] /'
else
  warn "no server_daily log found in $LOG_DIR"
fi
scheduler_log="$(ls -1t "$LOG_DIR"/server_daily_scheduler_*.log 2>/dev/null | head -n 1)"
if [[ -n "$scheduler_log" ]]; then
  ok "latest scheduler log $scheduler_log"
  grep -E 'next run|scheduled run completed|scheduler started|already running' "$scheduler_log" | tail -n 6 | sed 's/^/[SCHED] /'
else
  warn "no scheduler log found in $LOG_DIR"
fi

printf '\n'
if [[ "$STATUS" -eq 0 ]]; then
  ok "PaperRadar looks healthy"
else
  warn "PaperRadar has warnings; inspect messages above"
fi
exit "$STATUS"
