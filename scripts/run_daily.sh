#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PAPERRADAR_PYTHON:-python}"
CONFIG_PATH="${PAPERRADAR_CONFIG:-config/default.json}"

usage() {
  cat <<'EOF'
Usage: scripts/run_daily.sh [command] [options]

Commands:
  run              Run the full daily pipeline. Default.
  fetch            Fetch arXiv metadata only.
  registry         Show local paper registry.
  migrate-storage  Reorganize local cache into category/year folders.
  render           Render docs from an existing daily JSON.
  reanalyze        Rerun LLM summaries from an existing daily JSON.

Options:
  --date YYYY-MM-DD       Date passed to the run command.
  --limit N               Temporary max_results override for run/fetch, or first N papers for reanalyze.
  --config PATH           Config file path. Defaults to config/default.json.
  --python PATH           Python executable. Defaults to python.
  --data-dir PATH         Daily JSON output directory for run.
  --docs-dir PATH         Docs output directory for run/render.
  --query TEXT            Query for registry search.
  --input PATH            Input JSON for render/reanalyze.

Examples:
  scripts/run_daily.sh
  scripts/run_daily.sh run --limit 3
  scripts/run_daily.sh reanalyze --input data/daily/public/2026-05-21.json
  scripts/run_daily.sh registry --query seismic
  scripts/run_daily.sh migrate-storage
EOF
}

command="run"
date_arg=""
limit_arg=""
query_arg=""
input_arg=""
data_dir_arg=""
docs_dir_arg=""

if [[ $# -gt 0 && "$1" != --* ]]; then
  command="$1"
  shift
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --date)
      date_arg="${2:?Missing value for --date}"
      shift 2
      ;;
    --limit)
      limit_arg="${2:?Missing value for --limit}"
      shift 2
      ;;
    --config)
      CONFIG_PATH="${2:?Missing value for --config}"
      shift 2
      ;;
    --python)
      PYTHON_BIN="${2:?Missing value for --python}"
      shift 2
      ;;
    --data-dir)
      data_dir_arg="${2:?Missing value for --data-dir}"
      shift 2
      ;;
    --docs-dir)
      docs_dir_arg="${2:?Missing value for --docs-dir}"
      shift 2
      ;;
    --query)
      query_arg="${2:?Missing value for --query}"
      shift 2
      ;;
    --input)
      input_arg="${2:?Missing value for --input}"
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

run_config="$CONFIG_PATH"
tmp_config=""
cleanup() {
  if [[ -n "$tmp_config" && -f "$tmp_config" ]]; then
    rm -f "$tmp_config"
  fi
}
trap cleanup EXIT

if [[ -n "$limit_arg" ]]; then
  tmp_config="$(mktemp /tmp/paperradar_config.XXXXXX.json)"
  "$PYTHON_BIN" - "$CONFIG_PATH" "$tmp_config" "$limit_arg" <<'PY'
import json
import sys
from pathlib import Path

src, dst, limit = sys.argv[1], sys.argv[2], int(sys.argv[3])
data = json.loads(Path(src).read_text(encoding="utf-8"))
data["arxiv"]["max_results"] = limit
Path(dst).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
PY
  run_config="$tmp_config"
fi

case "$command" in
  run)
    args=(run --config "$run_config")
    if [[ -n "$date_arg" ]]; then
      args+=(--date "$date_arg")
    fi
    if [[ -n "$data_dir_arg" ]]; then
      args+=(--data-dir "$data_dir_arg")
    fi
    if [[ -n "$docs_dir_arg" ]]; then
      args+=(--docs-dir "$docs_dir_arg")
    fi
    echo "[PaperRadar] python=$PYTHON_BIN config=$run_config command=run" >&2
    "$PYTHON_BIN" -m paperradar.cli "${args[@]}"
    ;;
  fetch)
    args=(fetch --config "$run_config")
    if [[ -n "$date_arg" ]]; then
      args+=(--date "$date_arg")
    fi
    echo "[PaperRadar] python=$PYTHON_BIN config=$run_config command=fetch" >&2
    "$PYTHON_BIN" -m paperradar.cli "${args[@]}"
    ;;
  registry)
    args=(registry --config "$run_config")
    if [[ -n "$query_arg" ]]; then
      args+=(--query "$query_arg")
    fi
    echo "[PaperRadar] python=$PYTHON_BIN config=$run_config command=registry" >&2
    "$PYTHON_BIN" -m paperradar.cli "${args[@]}"
    ;;
  migrate-storage)
    echo "[PaperRadar] python=$PYTHON_BIN config=$run_config command=migrate-storage" >&2
    "$PYTHON_BIN" -m paperradar.cli migrate-storage --config "$run_config"
    ;;
  render)
    if [[ -z "$input_arg" ]]; then
      echo "render requires --input PATH" >&2
      exit 2
    fi
    args=(render --input "$input_arg")
    if [[ -n "$docs_dir_arg" ]]; then
      args+=(--docs-dir "$docs_dir_arg")
    fi
    echo "[PaperRadar] python=$PYTHON_BIN config=$run_config command=render" >&2
    "$PYTHON_BIN" -m paperradar.cli "${args[@]}"
    ;;
  reanalyze)
    if [[ -z "$input_arg" ]]; then
      echo "reanalyze requires --input PATH" >&2
      exit 2
    fi
    args=(reanalyze --input "$input_arg" --config "$run_config")
    if [[ -n "$docs_dir_arg" ]]; then
      args+=(--docs-dir "$docs_dir_arg")
    fi
    if [[ -n "$limit_arg" ]]; then
      args+=(--limit "$limit_arg")
    fi
    echo "[PaperRadar] python=$PYTHON_BIN config=$run_config command=reanalyze" >&2
    "$PYTHON_BIN" -m paperradar.cli "${args[@]}"
    ;;
  *)
    echo "Unknown command: $command" >&2
    usage >&2
    exit 2
    ;;
esac
