from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any


def build_failure_report(digest: dict[str, Any]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    for item in digest.get("papers", []):
        paper = item.get("paper", {})
        analysis = item.get("analysis", {})
        base = {
            "source": paper.get("source") or "arxiv",
            "paper_id": paper.get("arxiv_id") or paper.get("source_id") or "",
            "title": paper.get("title", ""),
            "published": str(paper.get("published", ""))[:10],
            "categories": paper.get("categories", []),
        }
        pdf_error = paper.get("pdf_download_error")
        if pdf_error:
            failures.append({**base, "stage": "pdf", "error": str(pdf_error)})
        markdown_error = paper.get("markdown_parse_error")
        if markdown_error:
            failures.append({**base, "stage": "mineru", "error": str(markdown_error)})
        if analysis and not analysis.get("llm_used"):
            failures.append(
                {
                    **base,
                    "stage": "llm",
                    "error": str(analysis.get("llm_error") or "LLM was not used; fallback summary generated"),
                }
            )
    by_stage = Counter(item["stage"] for item in failures)
    by_source = Counter(item["source"] for item in failures)
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "digest_date": digest.get("date", ""),
        "paper_count": len(digest.get("papers", [])),
        "failure_count": len(failures),
        "by_stage": dict(sorted(by_stage.items())),
        "by_source": dict(sorted(by_source.items())),
        "failures": failures,
    }


def write_failure_report(input_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    source = Path(input_path)
    digest = json.loads(source.read_text(encoding="utf-8"))
    report = build_failure_report(digest)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
