from __future__ import annotations

import collections
import json


def main() -> int:
    registry = json.load(open("data/paper_registry.json", encoding="utf-8"))
    counts = collections.Counter()
    for entry in registry.get("papers", {}).values():
        paper = entry.get("paper", {})
        categories = paper.get("categories", [])
        counts[categories[0] if categories else "uncategorized"] += 1
    print(dict(counts))
    for entry in registry.get("papers", {}).values():
        paper = entry.get("paper", {})
        print(paper.get("arxiv_id"), paper.get("categories", []), paper.get("title", "")[:100])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

