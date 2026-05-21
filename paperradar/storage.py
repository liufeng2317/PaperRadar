from __future__ import annotations

import datetime as dt
import re
import shutil
from pathlib import Path
from typing import Protocol


class PaperLike(Protocol):
    arxiv_id: str
    published: str
    categories: list[str]


def paper_bucket(
    paper: PaperLike,
    preferred_categories: list[str] | None = None,
    category_policy: str = "configured",
) -> tuple[str, str]:
    category = storage_category(
        paper.categories,
        preferred_categories=preferred_categories,
        category_policy=category_policy,
    )
    year = _published_year(paper.published)
    return category, year


def paper_pdf_path(
    pdf_dir: str | Path,
    paper: PaperLike,
    preferred_categories: list[str] | None = None,
    category_policy: str = "configured",
) -> Path:
    category, year = paper_bucket(paper, preferred_categories, category_policy)
    return Path(pdf_dir) / category / year / f"{safe_arxiv_id(paper.arxiv_id)}.pdf"


def paper_markdown_path(
    markdown_dir: str | Path,
    paper: PaperLike,
    preferred_categories: list[str] | None = None,
    category_policy: str = "configured",
) -> Path:
    category, year = paper_bucket(paper, preferred_categories, category_policy)
    return Path(markdown_dir) / category / year / f"{safe_arxiv_id(paper.arxiv_id)}.md"


def paper_mineru_dir(
    mineru_output_dir: str | Path,
    paper: PaperLike,
    preferred_categories: list[str] | None = None,
    category_policy: str = "configured",
) -> Path:
    category, year = paper_bucket(paper, preferred_categories, category_policy)
    return Path(mineru_output_dir) / category / year


def storage_category(
    paper_categories: list[str],
    preferred_categories: list[str] | None = None,
    category_policy: str = "configured",
) -> str:
    preferred_categories = preferred_categories or []
    if category_policy in {"configured", "first_configured"} and preferred_categories:
        return safe_path_part(preferred_categories[0])
    if category_policy == "matched":
        for category in preferred_categories:
            if category in paper_categories:
                return safe_path_part(category)
    return safe_path_part(paper_categories[0] if paper_categories else "uncategorized")


def migrate_legacy_file(legacy_path: Path, target_path: Path) -> bool:
    if target_path.exists() and target_path.stat().st_size > 0:
        return True
    if not legacy_path.exists() or legacy_path.stat().st_size <= 0:
        return False
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(legacy_path), str(target_path))
    return True


def safe_arxiv_id(arxiv_id: str) -> str:
    return arxiv_id.replace("/", "_")


def safe_path_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return cleaned.strip("-") or "unknown"


def _published_year(published: str) -> str:
    try:
        return str(dt.datetime.fromisoformat(published.replace("Z", "+00:00")).year)
    except ValueError:
        return "unknown-year"
