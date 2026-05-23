from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArxivConfig:
    query: str
    categories: list[str]
    extra_terms: list[str]
    keywords: list[str]
    keyword_fields: list[str]
    authors: list[str]
    match_all_authors: bool
    submitted_after: str
    submitted_before: str
    max_results: int
    lookback_days: int
    sort_by: str
    sort_order: str
    request_delay_seconds: float
    max_retries: int
    allow_cached_fetch_fallback: bool
    download_pdfs: bool
    pdf_dir: str
    storage_category_policy: str
    registry_path: str
    parse_pdfs: bool
    markdown_dir: str
    mineru_output_dir: str
    mineru_poll_timeout: int
    mineru_model_version: str
    mineru_language: str
    mineru_ocr: bool
    mineru_llm_aid: bool


@dataclass(frozen=True)
class EarthArxivConfig:
    enabled: bool
    base_url: str
    max_results: int
    lookback_days: int
    subjects: list[str]
    keywords: list[str]
    request_delay_seconds: float
    max_retries: int
    disable_proxy: bool


@dataclass(frozen=True)
class SiteConfig:
    site_title: str
    site_description: dict[str, str]
    arxiv: ArxivConfig
    eartharxiv: EarthArxivConfig
    languages: list[str]
    keywords_per_paper: int
    trending_top_n: int
    public_lookback_days: int


def load_config(path: str | Path = "config/default.json") -> SiteConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    arxiv = raw["arxiv"]
    eartharxiv = raw.get("eartharxiv", {})
    return SiteConfig(
        site_title=raw["site_title"],
        site_description=raw["site_description"],
        arxiv=ArxivConfig(
            query=str(arxiv.get("query", "")),
            categories=list(arxiv.get("categories", ["physics.geo-ph"])),
            extra_terms=list(arxiv.get("extra_terms", [])),
            keywords=list(arxiv.get("keywords", [])),
            keyword_fields=list(arxiv.get("keyword_fields", ["title", "abstract"])),
            authors=list(arxiv.get("authors", [])),
            match_all_authors=bool(arxiv.get("match_all_authors", False)),
            submitted_after=str(arxiv.get("submitted_after", "")),
            submitted_before=str(arxiv.get("submitted_before", "")),
            max_results=int(arxiv["max_results"]),
            lookback_days=int(arxiv["lookback_days"]),
            sort_by=str(arxiv.get("sort_by", "submittedDate")),
            sort_order=str(arxiv.get("sort_order", "descending")),
            request_delay_seconds=float(arxiv.get("request_delay_seconds", 3)),
            max_retries=int(arxiv.get("max_retries", 3)),
            allow_cached_fetch_fallback=bool(arxiv.get("allow_cached_fetch_fallback", False)),
            download_pdfs=bool(arxiv.get("download_pdfs", False)),
            pdf_dir=str(arxiv.get("pdf_dir", "data/pdfs")),
            storage_category_policy=str(arxiv.get("storage_category_policy", "configured")),
            registry_path=str(arxiv.get("registry_path", "data/paper_registry.json")),
            parse_pdfs=bool(arxiv.get("parse_pdfs", False)),
            markdown_dir=str(arxiv.get("markdown_dir", "data/markdown")),
            mineru_output_dir=str(arxiv.get("mineru_output_dir", "data/mineru")),
            mineru_poll_timeout=int(arxiv.get("mineru_poll_timeout", 300)),
            mineru_model_version=str(arxiv.get("mineru_model_version", "vlm")),
            mineru_language=str(arxiv.get("mineru_language", "en")),
            mineru_ocr=bool(arxiv.get("mineru_ocr", False)),
            mineru_llm_aid=bool(arxiv.get("mineru_llm_aid", False)),
        ),
        eartharxiv=EarthArxivConfig(
            enabled=bool(eartharxiv.get("enabled", False)),
            base_url=str(eartharxiv.get("base_url", "https://eartharxiv.org/api/oai/")),
            max_results=int(eartharxiv.get("max_results", 25)),
            lookback_days=int(eartharxiv.get("lookback_days", arxiv.get("lookback_days", 60))),
            subjects=list(eartharxiv.get("subjects", [])),
            keywords=list(eartharxiv.get("keywords", [])),
            request_delay_seconds=float(eartharxiv.get("request_delay_seconds", arxiv.get("request_delay_seconds", 3))),
            max_retries=int(eartharxiv.get("max_retries", arxiv.get("max_retries", 3))),
            disable_proxy=bool(eartharxiv.get("disable_proxy", True)),
        ),
        languages=list(raw.get("languages", ["en", "zh"])),
        keywords_per_paper=int(raw.get("keywords_per_paper", 5)),
        trending_top_n=int(raw.get("trending_top_n", 30)),
        public_lookback_days=int(raw.get("public_lookback_days", raw.get("arxiv", {}).get("lookback_days", 60))),
    )


def to_jsonable(config: SiteConfig) -> dict[str, Any]:
    return {
        "site_title": config.site_title,
        "site_description": config.site_description,
        "arxiv": {
            "query": config.arxiv.query,
            "categories": config.arxiv.categories,
            "extra_terms": config.arxiv.extra_terms,
            "keywords": config.arxiv.keywords,
            "keyword_fields": config.arxiv.keyword_fields,
            "authors": config.arxiv.authors,
            "match_all_authors": config.arxiv.match_all_authors,
            "submitted_after": config.arxiv.submitted_after,
            "submitted_before": config.arxiv.submitted_before,
            "max_results": config.arxiv.max_results,
            "lookback_days": config.arxiv.lookback_days,
            "sort_by": config.arxiv.sort_by,
            "sort_order": config.arxiv.sort_order,
            "request_delay_seconds": config.arxiv.request_delay_seconds,
            "max_retries": config.arxiv.max_retries,
            "allow_cached_fetch_fallback": config.arxiv.allow_cached_fetch_fallback,
            "download_pdfs": config.arxiv.download_pdfs,
            "pdf_dir": config.arxiv.pdf_dir,
            "storage_category_policy": config.arxiv.storage_category_policy,
            "registry_path": config.arxiv.registry_path,
            "parse_pdfs": config.arxiv.parse_pdfs,
            "markdown_dir": config.arxiv.markdown_dir,
            "mineru_output_dir": config.arxiv.mineru_output_dir,
            "mineru_poll_timeout": config.arxiv.mineru_poll_timeout,
            "mineru_model_version": config.arxiv.mineru_model_version,
            "mineru_language": config.arxiv.mineru_language,
            "mineru_ocr": config.arxiv.mineru_ocr,
            "mineru_llm_aid": config.arxiv.mineru_llm_aid,
        },
        "eartharxiv": {
            "enabled": config.eartharxiv.enabled,
            "base_url": config.eartharxiv.base_url,
            "max_results": config.eartharxiv.max_results,
            "lookback_days": config.eartharxiv.lookback_days,
            "subjects": config.eartharxiv.subjects,
            "keywords": config.eartharxiv.keywords,
            "request_delay_seconds": config.eartharxiv.request_delay_seconds,
            "max_retries": config.eartharxiv.max_retries,
            "disable_proxy": config.eartharxiv.disable_proxy,
        },
        "languages": config.languages,
        "keywords_per_paper": config.keywords_per_paper,
        "trending_top_n": config.trending_top_n,
        "public_lookback_days": config.public_lookback_days,
    }
