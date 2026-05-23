from __future__ import annotations

import shutil
import re
from pathlib import Path

from paperradar.arxiv_client import Paper
from paperradar.config import ArxivConfig
from paperradar.storage import (
    legacy_year_markdown_path,
    legacy_year_mineru_dir,
    migrate_legacy_file,
    paper_markdown_path,
    paper_mineru_dir,
    safe_arxiv_id,
)


def parse_pdf_to_markdown(
    pdf_path: str,
    paper: Paper,
    config: ArxivConfig,
    storage_date: str | None = None,
) -> tuple[str | None, str | None]:
    if not pdf_path:
        return None, "PDF path is empty; cannot parse with MinerU."

    markdown_path = paper_markdown_path(
        config.markdown_dir,
        paper,
        config.categories,
        config.storage_category_policy,
        storage_date,
    )
    legacy_markdown = Path(config.markdown_dir) / f"{safe_arxiv_id(paper.arxiv_id)}.md"
    legacy_year_markdown = legacy_year_markdown_path(
        config.markdown_dir,
        paper,
        config.categories,
        config.storage_category_policy,
    )
    migrate_legacy_file(legacy_markdown, markdown_path)
    migrate_legacy_file(legacy_year_markdown, markdown_path)
    if markdown_path.exists() and markdown_path.stat().st_size > 0:
        return str(markdown_path), None

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        return None, f"PDF file does not exist: {pdf_path}"

    mineru_dir = paper_mineru_dir(
        config.mineru_output_dir,
        paper,
        config.categories,
        config.storage_category_policy,
        storage_date,
    )
    legacy_year_mineru = legacy_year_mineru_dir(
        config.mineru_output_dir,
        paper,
        config.categories,
        config.storage_category_policy,
    )
    existing_mineru_markdown = _find_markdown_for_pdf(mineru_dir, pdf_file.stem)
    if not existing_mineru_markdown:
        existing_mineru_markdown = _find_markdown_for_pdf(legacy_year_mineru, pdf_file.stem)
    if not existing_mineru_markdown:
        existing_mineru_markdown = _find_markdown_for_pdf(Path(config.mineru_output_dir), pdf_file.stem)
    if existing_mineru_markdown:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(existing_mineru_markdown, markdown_path)
        return str(markdown_path), None

    try:
        from paperradar.paper_parse.local_pdf_parser import parse_local_pdfs
    except Exception as exc:
        return None, f"Could not import built-in MinerU parser dependencies: {exc}"

    result_code = parse_local_pdfs(
        process_all=False,
        specific_pdf_files=[pdf_file.name],
        data_dir=str(pdf_file.parent),
        output_dir=str(mineru_dir),
        max_retries=3,
        continue_on_error=True,
        file_on_error=None,
        model_version=config.mineru_model_version,
        language=config.mineru_language,
        is_ocr=config.mineru_ocr,
        poll_timeout=config.mineru_poll_timeout,
        llm_aid=config.mineru_llm_aid,
        verbose=False,
        save_summary=False,
    )
    if result_code not in (0, None):
        return None, f"MinerU parser returned non-zero status: {result_code}"

    mineru_markdown = mineru_dir / pdf_file.stem / "full.md"
    if not mineru_markdown.exists():
        fallback = _find_markdown_for_pdf(mineru_dir, pdf_file.stem)
        if fallback:
            mineru_markdown = fallback
        else:
            return None, f"MinerU markdown not found for {pdf_file.name}"

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mineru_markdown, markdown_path)
    return str(markdown_path), None


def read_markdown_excerpt(path: str | None, max_chars: int = 24000) -> str:
    if not path:
        return ""
    md_path = Path(path)
    if not md_path.exists():
        return ""
    text = md_path.read_text(encoding="utf-8", errors="replace")
    return clean_markdown_for_llm(text)[:max_chars]


def clean_markdown_for_llm(markdown: str) -> str:
    markdown = _truncate_before_back_matter(markdown)
    markdown = _remove_markdown_images(markdown)
    markdown = _remove_html_comments(markdown)
    markdown = _collapse_repeated_blank_lines(markdown)
    return markdown.strip()


def _find_markdown_for_pdf(output_dir: Path, stem: str) -> Path | None:
    candidates = list(output_dir.glob(f"**/{stem}.md")) + list(output_dir.glob(f"**/{stem}/full.md"))
    if candidates:
        return candidates[0]
    return None


def _truncate_before_back_matter(markdown: str) -> str:
    back_matter_patterns = [
        r"references?",
        r"bibliography",
        r"acknowledg(e)?ments?",
        r"appendix|appendices",
        r"supplementary material",
        r"supporting information",
        r"data availability",
        r"code availability",
        r"author contributions?",
        r"competing interests?",
        r"conflicts? of interest",
        r"funding",
    ]
    heading_re = re.compile(
        r"(?im)^\s{0,3}#{1,6}\s*(?:\d+[\.\)]\s*)?("
        + "|".join(back_matter_patterns)
        + r")\b.*$"
    )
    match = heading_re.search(markdown)
    if not match:
        return markdown
    return markdown[: match.start()]


def _remove_markdown_images(markdown: str) -> str:
    return re.sub(r"!\[[^\]]*\]\([^)]+\)", "", markdown)


def _remove_html_comments(markdown: str) -> str:
    return re.sub(r"<!--.*?-->", "", markdown, flags=re.DOTALL)


def _collapse_repeated_blank_lines(markdown: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", markdown)
