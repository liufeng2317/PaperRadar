from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from paperradar.pipeline import _paper_from_dict
from paperradar.registry import (
    load_registry,
    save_registry,
    update_mineru_status,
    update_pdf_status,
)
from paperradar.storage import (
    migrate_legacy_file,
    paper_markdown_path,
    paper_mineru_dir,
    paper_pdf_path,
    safe_arxiv_id,
)


def migrate_storage(config) -> dict[str, int]:
    registry = load_registry(config.arxiv.registry_path)
    stats = {"papers": 0, "pdfs": 0, "markdown": 0, "mineru_dirs": 0, "mineru_zips": 0}
    for entry in registry.get("papers", {}).values():
        paper = _paper_from_dict(entry.get("paper", {}))
        if not paper:
            continue
        stats["papers"] += 1

        pdf_path = paper_pdf_path(
            config.arxiv.pdf_dir,
            paper,
            config.arxiv.categories,
            config.arxiv.storage_category_policy,
        )
        legacy_pdf = Path(config.arxiv.pdf_dir) / f"{safe_arxiv_id(paper.arxiv_id)}.pdf"
        if migrate_legacy_file(legacy_pdf, pdf_path):
            stats["pdfs"] += 1
        elif _move_first_match(Path(config.arxiv.pdf_dir), f"{safe_arxiv_id(paper.arxiv_id)}.pdf", pdf_path):
            stats["pdfs"] += 1
        update_pdf_status(entry, str(pdf_path) if pdf_path.exists() else None, None)

        markdown_path = paper_markdown_path(
            config.arxiv.markdown_dir,
            paper,
            config.arxiv.categories,
            config.arxiv.storage_category_policy,
        )
        legacy_markdown = Path(config.arxiv.markdown_dir) / f"{safe_arxiv_id(paper.arxiv_id)}.md"
        if migrate_legacy_file(legacy_markdown, markdown_path):
            stats["markdown"] += 1
        elif _move_first_match(Path(config.arxiv.markdown_dir), f"{safe_arxiv_id(paper.arxiv_id)}.md", markdown_path):
            stats["markdown"] += 1

        mineru_bucket = paper_mineru_dir(
            config.arxiv.mineru_output_dir,
            paper,
            config.arxiv.categories,
            config.arxiv.storage_category_policy,
        )
        legacy_mineru_dir = Path(config.arxiv.mineru_output_dir) / safe_arxiv_id(paper.arxiv_id)
        target_mineru_dir = mineru_bucket / safe_arxiv_id(paper.arxiv_id)
        if _move_path(legacy_mineru_dir, target_mineru_dir):
            stats["mineru_dirs"] += 1
        elif _move_first_match(Path(config.arxiv.mineru_output_dir), safe_arxiv_id(paper.arxiv_id), target_mineru_dir):
            stats["mineru_dirs"] += 1

        legacy_zip = Path(config.arxiv.mineru_output_dir) / f"{safe_arxiv_id(paper.arxiv_id)}.zip"
        target_zip = mineru_bucket / f"{safe_arxiv_id(paper.arxiv_id)}.zip"
        if _move_path(legacy_zip, target_zip):
            stats["mineru_zips"] += 1
        elif _move_first_match(Path(config.arxiv.mineru_output_dir), f"{safe_arxiv_id(paper.arxiv_id)}.zip", target_zip):
            stats["mineru_zips"] += 1

        mineru_markdown = target_mineru_dir / "full.md"
        if not markdown_path.exists() and mineru_markdown.exists():
            markdown_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(mineru_markdown, markdown_path)

        update_mineru_status(
            entry,
            str(markdown_path) if markdown_path.exists() else None,
            None,
            output_dir=str(mineru_bucket),
        )

    save_registry(registry, config.arxiv.registry_path)
    return stats


def _move_path(source: Path, target: Path) -> bool:
    if source == target:
        return target.exists()
    if target.exists():
        return True
    if not source.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))
    return True


def _move_first_match(root: Path, name: str, target: Path) -> bool:
    if target.exists():
        return True
    if not root.exists():
        return False
    for source in root.glob(f"**/{name}"):
        if source == target:
            continue
        if source.exists():
            return _move_path(source, target)
    return False
