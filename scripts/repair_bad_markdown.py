from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


REGISTRY_PATH = Path("data/paper_registry.json")
GOOD_ID = "2605.21437v1"
QUARANTINE_DIR = Path("data/quarantine/bad_markdown")


def main() -> int:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    good_path = Path(registry["papers"][GOOD_ID]["mineru"]["markdown_path"])
    good_hash = _sha256(good_path)
    moved = []

    for path in Path("data/markdown").glob("**/*.md"):
        if path == good_path or path.stem == GOOD_ID:
            continue
        if _sha256(path) == good_hash:
            target = QUARANTINE_DIR / path.relative_to("data/markdown")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(target))
            moved.append(str(path))

    for arxiv_id, entry in registry.get("papers", {}).items():
        mineru = entry.get("mineru", {})
        markdown_path = mineru.get("markdown_path")
        if arxiv_id == GOOD_ID or not markdown_path:
            continue
        path = Path(markdown_path)
        if not path.exists() or _sha256(path) != good_hash:
            continue

        target = QUARANTINE_DIR / path.relative_to("data/markdown")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(target))
        moved.append(str(path))

        entry["mineru"] = {
            "markdown_path": None,
            "output_dir": mineru.get("output_dir"),
            "error": "quarantined duplicated Markdown copied from another paper",
            "status": "missing",
            "checked_at": mineru.get("checked_at"),
        }
        analysis = entry.get("analysis", {})
        if analysis.get("source") == "markdown":
            entry["analysis"] = {}

    REGISTRY_PATH.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    print("moved=" + str(len(moved)))
    for path in moved:
        print(path)
    return 0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
