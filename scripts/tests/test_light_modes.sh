#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PAPERRADAR_PYTHON:-python}"
TEST_ROOT="scripts/tests/runtime"
CONFIG_DIR="$TEST_ROOT/config"
DATA_DIR="$TEST_ROOT/daily"
DOCS_DIR="$TEST_ROOT/docs"
PDF_DIR="$TEST_ROOT/pdfs"
MARKDOWN_DIR="$TEST_ROOT/markdown"
MINERU_DIR="$TEST_ROOT/mineru"
REGISTRY_DIR="$TEST_ROOT/registry"

mkdir -p "$CONFIG_DIR" "$DATA_DIR" "$DOCS_DIR" "$PDF_DIR" "$MARKDOWN_DIR" "$MINERU_DIR" "$REGISTRY_DIR"

make_config() {
  local output_path="$1"
  local download_pdfs="$2"
  "$PYTHON_BIN" - "$output_path" "$download_pdfs" <<'PYCODE'
import json
import sys
from pathlib import Path

output_path = Path(sys.argv[1])
download_pdfs = sys.argv[2].lower() == "true"

config = json.loads(Path("config/default.json").read_text(encoding="utf-8"))
config["site_description"] = {
    "en": "PaperRadar isolated light-mode smoke test.",
    "zh": "PaperRadar 轻量模式隔离测试。",
}
config["arxiv"]["max_results"] = 1
config["arxiv"]["lookback_days"] = 7
config["arxiv"]["download_pdfs"] = download_pdfs
config["arxiv"]["parse_pdfs"] = False
config["arxiv"]["pdf_dir"] = "scripts/tests/runtime/pdfs"
config["arxiv"]["markdown_dir"] = "scripts/tests/runtime/markdown"
config["arxiv"]["mineru_output_dir"] = "scripts/tests/runtime/mineru"
config["arxiv"]["registry_path"] = f"scripts/tests/runtime/registry/{output_path.stem}.json"
config["eartharxiv"]["enabled"] = False
config["public_lookback_days"] = 7

output_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PYCODE
}

run_case() {
  local name="$1"
  local download_pdfs="$2"
  local config_path="$CONFIG_DIR/$name.json"
  local case_data_dir="$DATA_DIR/$name"
  local case_docs_dir="$DOCS_DIR/$name"

  rm -rf "$case_data_dir" "$case_docs_dir"
  make_config "$config_path" "$download_pdfs"

  echo "[PaperRadar test] case=$name download_pdfs=$download_pdfs parse_pdfs=false"
  "$PYTHON_BIN" -m paperradar.cli run     --config "$config_path"     --data-dir "$case_data_dir"     --docs-dir "$case_docs_dir"

  "$PYTHON_BIN" - "$name" "$case_data_dir" "$case_docs_dir" "$download_pdfs" <<'PYCODE'
import json
import sys
from pathlib import Path

name, data_dir, docs_dir, download_pdfs = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4].lower() == "true"
latest = Path(docs_dir) / "data" / "latest.json"
if not latest.exists():
    raise SystemExit(f"{name}: missing {latest}")
digest = json.loads(latest.read_text(encoding="utf-8"))
papers = digest.get("papers", [])
if len(papers) != 1:
    raise SystemExit(f"{name}: expected 1 paper, got {len(papers)}")
paper = papers[0]["paper"]
analysis = papers[0]["analysis"]
if not paper.get("abstract"):
    raise SystemExit(f"{name}: abstract is missing")
if analysis.get("source") != "abstract":
    raise SystemExit(f"{name}: expected abstract summary source, got {analysis.get('source')}")
if paper.get("markdown_path"):
    raise SystemExit(f"{name}: markdown_path should be empty when parse_pdfs=false")
if paper.get("markdown_parse_error"):
    raise SystemExit(f"{name}: markdown_parse_error should be empty when parse_pdfs=false")
if download_pdfs and not paper.get("local_pdf_path"):
    raise SystemExit(f"{name}: expected a local PDF path")
if not download_pdfs and paper.get("local_pdf_path"):
    raise SystemExit(f"{name}: local_pdf_path should be empty when download_pdfs=false")

print(
    "[PaperRadar test] ok "
    f"case={name} id={paper.get('arxiv_id')} "
    f"abstract_chars={len(paper.get('abstract', ''))} "
    f"local_pdf={bool(paper.get('local_pdf_path'))} "
    f"summary_source={analysis.get('source')}"
)
PYCODE
}

run_case "light_with_pdf" "true"
run_case "light_without_pdf" "false"

echo "[PaperRadar test] runtime outputs kept under $TEST_ROOT"
