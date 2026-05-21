from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any


GENERIC_KEYWORDS = {
    "across",
    "analysis",
    "approach",
    "approximation",
    "based",
    "benchmarking",
    "coefficient",
    "conservative",
    "data",
    "dataset",
    "datasets",
    "field",
    "framework",
    "learning",
    "method",
    "model",
    "models",
    "network",
    "networks",
    "paper",
    "result",
    "results",
    "study",
    "system",
    "using",
}


def rank_keywords(papers: list[dict[str, Any]], top_n: int = 30) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    display_names: dict[str, str] = {}
    paper_ids: dict[str, set[str]] = defaultdict(set)

    for paper in papers:
        arxiv_id = paper["paper"]["arxiv_id"]
        for keyword in paper["analysis"].get("keywords_en", []):
            key = normalize_keyword(keyword)
            if not key:
                continue
            counts[key] += 1
            display_names.setdefault(key, keyword)
            paper_ids[key].add(arxiv_id)

    ranked = []
    for key, count in counts.most_common(top_n):
        ranked.append(
            {
                "keyword": display_names[key],
                "normalized": key,
                "score": count,
                "paper_count": len(paper_ids[key]),
                "paper_ids": sorted(paper_ids[key]),
            }
        )
    return ranked


def normalize_keyword(keyword: str) -> str:
    key = re.sub(r"\s+", " ", keyword.strip().lower())
    key = key.strip(" -–—_:;,.()[]{}")
    if not key or key in GENERIC_KEYWORDS:
        return ""
    if re.search(r"\\|[{}^_=]", key):
        return ""
    return key
