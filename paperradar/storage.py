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
    source: str


def paper_bucket(
    paper: PaperLike,
    preferred_categories: list[str] | None = None,
    category_policy: str = "configured",
    storage_date: str | dt.date | None = None,
) -> tuple[str, str, str]:
    source = storage_source(paper)
    category = storage_category(
        paper.categories,
        preferred_categories=_preferred_categories_for_source(source, preferred_categories),
        category_policy=category_policy,
    )
    day = _storage_day(storage_date) if storage_date else _published_day(paper.published)
    return source, category, day


def paper_pdf_path(
    pdf_dir: str | Path,
    paper: PaperLike,
    preferred_categories: list[str] | None = None,
    category_policy: str = "configured",
    storage_date: str | dt.date | None = None,
) -> Path:
    source, category, day = paper_bucket(paper, preferred_categories, category_policy, storage_date)
    return Path(pdf_dir) / source / category / day / f"{safe_arxiv_id(paper.arxiv_id)}.pdf"


def paper_markdown_path(
    markdown_dir: str | Path,
    paper: PaperLike,
    preferred_categories: list[str] | None = None,
    category_policy: str = "configured",
    storage_date: str | dt.date | None = None,
) -> Path:
    source, category, day = paper_bucket(paper, preferred_categories, category_policy, storage_date)
    return Path(markdown_dir) / source / category / day / f"{safe_arxiv_id(paper.arxiv_id)}.md"


def paper_mineru_dir(
    mineru_output_dir: str | Path,
    paper: PaperLike,
    preferred_categories: list[str] | None = None,
    category_policy: str = "configured",
    storage_date: str | dt.date | None = None,
) -> Path:
    source, category, day = paper_bucket(paper, preferred_categories, category_policy, storage_date)
    return Path(mineru_output_dir) / source / category / day


def legacy_year_bucket(
    paper: PaperLike,
    preferred_categories: list[str] | None = None,
    category_policy: str = "configured",
) -> tuple[str, str]:
    source = storage_source(paper)
    category = storage_category(
        paper.categories,
        preferred_categories=_preferred_categories_for_source(source, preferred_categories),
        category_policy=category_policy,
    )
    try:
        year = str(dt.datetime.fromisoformat(paper.published.replace("Z", "+00:00")).year)
    except ValueError:
        year = "unknown-year"
    return category, year


def legacy_year_pdf_path(
    pdf_dir: str | Path,
    paper: PaperLike,
    preferred_categories: list[str] | None = None,
    category_policy: str = "configured",
) -> Path:
    category, year = legacy_year_bucket(paper, preferred_categories, category_policy)
    return Path(pdf_dir) / category / year / f"{safe_arxiv_id(paper.arxiv_id)}.pdf"


def legacy_year_markdown_path(
    markdown_dir: str | Path,
    paper: PaperLike,
    preferred_categories: list[str] | None = None,
    category_policy: str = "configured",
) -> Path:
    category, year = legacy_year_bucket(paper, preferred_categories, category_policy)
    return Path(markdown_dir) / category / year / f"{safe_arxiv_id(paper.arxiv_id)}.md"


def legacy_year_mineru_dir(
    mineru_output_dir: str | Path,
    paper: PaperLike,
    preferred_categories: list[str] | None = None,
    category_policy: str = "configured",
) -> Path:
    category, year = legacy_year_bucket(paper, preferred_categories, category_policy)
    return Path(mineru_output_dir) / category / year


def storage_source(paper: PaperLike) -> str:
    return safe_path_part(getattr(paper, "source", "arxiv") or "arxiv")


def _preferred_categories_for_source(source: str, preferred_categories: list[str] | None) -> list[str]:
    if source != "arxiv":
        return []
    return preferred_categories or []


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
    return safe_path_part(arxiv_id.replace("/", "_"))


def safe_path_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return cleaned.strip("-") or "unknown"


def _storage_day(value: str | dt.date) -> str:
    if isinstance(value, dt.date):
        return value.strftime("%Y%m%d")
    return dt.date.fromisoformat(value[:10]).strftime("%Y%m%d")


def _published_day(published: str) -> str:
    try:
        return dt.datetime.fromisoformat(published.replace("Z", "+00:00")).strftime("%Y%m%d")
    except ValueError:
        return "unknown-day"
