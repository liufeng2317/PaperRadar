from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from paperradar.arxiv_client import Paper
from paperradar.llm import ANALYSIS_INPUT_VERSION, ANALYSIS_SCHEMA_VERSION


REGISTRY_VERSION = 1


def load_registry(path: str | Path) -> dict[str, Any]:
    registry_path = Path(path)
    if not registry_path.exists():
        return _empty_registry()
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup = registry_path.with_suffix(registry_path.suffix + ".broken")
        registry_path.replace(backup)
        return _empty_registry()
    registry.setdefault("version", REGISTRY_VERSION)
    registry.setdefault("papers", {})
    return registry


def save_registry(registry: dict[str, Any], path: str | Path) -> None:
    registry["updated_at"] = _now()
    registry_path = Path(path)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_paper(registry: dict[str, Any], paper: Paper, seen_date: dt.date) -> dict[str, Any]:
    papers = registry.setdefault("papers", {})
    entry = papers.setdefault(
        paper.arxiv_id,
        {
            "arxiv_id": paper.arxiv_id,
            "first_seen": seen_date.isoformat(),
            "pdf": {},
            "mineru": {},
            "analysis": {},
        },
    )
    entry["last_seen"] = seen_date.isoformat()
    entry["paper"] = paper.to_dict()
    entry.setdefault("first_seen", seen_date.isoformat())
    entry.setdefault("pdf", {})
    entry.setdefault("mineru", {})
    entry.setdefault("analysis", {})
    return entry


def update_pdf_status(
    entry: dict[str, Any],
    path: str | None,
    error: str | None,
) -> None:
    pdf = entry.setdefault("pdf", {})
    pdf["path"] = path
    pdf["error"] = error
    pdf["status"] = "ready" if path and _existing_file(path) else "error" if error else "missing"
    pdf["checked_at"] = _now()
    if path and _existing_file(path):
        pdf["size_bytes"] = Path(path).stat().st_size


def cached_markdown_path(entry: dict[str, Any]) -> str | None:
    mineru = entry.setdefault("mineru", {})
    markdown_path = mineru.get("markdown_path")
    if markdown_path and _existing_file(markdown_path):
        return markdown_path
    return None


def update_mineru_status(
    entry: dict[str, Any],
    markdown_path: str | None,
    error: str | None,
    output_dir: str,
) -> None:
    mineru = entry.setdefault("mineru", {})
    mineru["markdown_path"] = markdown_path
    mineru["output_dir"] = output_dir
    mineru["error"] = error
    mineru["status"] = "ready" if markdown_path and _existing_file(markdown_path) else "error" if error else "missing"
    mineru["checked_at"] = _now()
    if markdown_path and _existing_file(markdown_path):
        mineru["size_bytes"] = Path(markdown_path).stat().st_size


def update_analysis_status(entry: dict[str, Any], analysis: dict[str, Any]) -> None:
    entry["analysis"] = {
        "schema_version": analysis.get("schema_version", ""),
        "input_version": analysis.get("input_version", ""),
        "one_sentence_en": analysis.get("one_sentence_en", ""),
        "one_sentence_zh": analysis.get("one_sentence_zh", ""),
        "summary_en": analysis.get("summary_en", ""),
        "summary_zh": analysis.get("summary_zh", ""),
        "contribution_en": analysis.get("contribution_en", ""),
        "contribution_zh": analysis.get("contribution_zh", ""),
        "method_en": analysis.get("method_en", ""),
        "method_zh": analysis.get("method_zh", ""),
        "data_or_region_en": analysis.get("data_or_region_en", ""),
        "data_or_region_zh": analysis.get("data_or_region_zh", ""),
        "geophysics_relevance_en": analysis.get("geophysics_relevance_en", ""),
        "geophysics_relevance_zh": analysis.get("geophysics_relevance_zh", ""),
        "llm_used": analysis.get("llm_used"),
        "source": analysis.get("source"),
        "model": analysis.get("model", ""),
        "topic": analysis.get("topic"),
        "audience_level": analysis.get("audience_level", ""),
        "keywords_en": analysis.get("keywords_en", []),
        "keywords_zh": analysis.get("keywords_zh", []),
        "updated_at": _now(),
    }


def cached_analysis(entry: dict[str, Any], source: str) -> dict[str, Any] | None:
    analysis = entry.get("analysis") or {}
    if analysis.get("schema_version") != ANALYSIS_SCHEMA_VERSION:
        return None
    if analysis.get("input_version") != ANALYSIS_INPUT_VERSION:
        return None
    if analysis.get("source") != source:
        return None
    if not analysis.get("one_sentence_en") or not analysis.get("one_sentence_zh"):
        return None
    if not analysis.get("summary_en") or not analysis.get("summary_zh"):
        return None
    if not analysis.get("keywords_en") or not analysis.get("keywords_zh"):
        return None
    return dict(analysis)


def _empty_registry() -> dict[str, Any]:
    return {"version": REGISTRY_VERSION, "created_at": _now(), "updated_at": _now(), "papers": {}}


def _existing_file(path: str) -> bool:
    file_path = Path(path)
    return file_path.exists() and file_path.stat().st_size > 0


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()
