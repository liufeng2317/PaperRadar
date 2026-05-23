from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from paperradar.arxiv_client import Paper, download_pdf, fetch_recent_papers
from paperradar.config import SiteConfig, load_config, to_jsonable
from paperradar.eartharxiv_client import fetch_eartharxiv_papers
from paperradar.llm import enrich_paper
from paperradar.pdf_parse import parse_pdf_to_markdown, read_markdown_excerpt
from paperradar.query import build_arxiv_query
from paperradar.registry import (
    cached_analysis,
    cached_markdown_path,
    ensure_paper,
    load_registry,
    save_registry,
    update_analysis_status,
    update_mineru_status,
    update_pdf_status,
)
from paperradar.render import write_outputs
from paperradar.storage import migrate_legacy_file, paper_markdown_path, paper_mineru_dir, paper_pdf_path
from paperradar.trend import rank_keywords


class NoNewPapers(RuntimeError):
    """Raised when the fetched arXiv paper list is unchanged from the latest digest."""


def run_pipeline(
    config_path: str = "config/default.json",
    date: dt.date | None = None,
    data_dir: str | Path = "data/daily",
    docs_dir: str | Path = "docs",
) -> dict[str, Any]:
    config = load_config(config_path)
    today = date or dt.date.today()
    registry = load_registry(config.arxiv.registry_path)
    query = build_arxiv_query(config.arxiv, today=today)
    try:
        papers = fetch_recent_papers(
            query=query,
            max_results=config.arxiv.max_results,
            lookback_days=config.arxiv.lookback_days,
            today=today,
            polite_delay_seconds=config.arxiv.request_delay_seconds,
            retries=config.arxiv.max_retries,
            sort_by=config.arxiv.sort_by,
            sort_order=config.arxiv.sort_order,
        )
        if config.eartharxiv.enabled:
            eartharxiv_papers = fetch_eartharxiv_papers(
                base_url=config.eartharxiv.base_url,
                max_results=config.eartharxiv.max_results,
                lookback_days=config.eartharxiv.lookback_days,
                today=today,
                subjects=config.eartharxiv.subjects,
                keywords=config.eartharxiv.keywords,
                polite_delay_seconds=config.eartharxiv.request_delay_seconds,
                retries=config.eartharxiv.max_retries,
                disable_proxy=config.eartharxiv.disable_proxy,
            )
            papers = _merge_papers(papers + eartharxiv_papers)
    except RuntimeError as exc:
        registry["last_fetch_error"] = str(exc)
        registry["last_fetch_failed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        save_registry(registry, config.arxiv.registry_path)
        if not config.arxiv.allow_cached_fetch_fallback:
            raise RuntimeError(
                f"arXiv fetch failed; refusing to publish cached papers as {today.isoformat()}. "
                "Set arxiv.allow_cached_fetch_fallback=true only for manual cache fallback runs. "
                f"Fetch error: {exc}"
            ) from exc
        papers = load_cached_papers(
            registry=registry,
            data_dir=data_dir,
            today=today,
            limit=config.arxiv.max_results,
        )
        if not papers:
            raise
        registry["last_fetch_fallback_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    previous_digest = _latest_daily_digest(data_dir)
    if previous_digest and _contains_all_paper_ids(previous_digest.get("papers", []), papers):
        registry["last_no_change_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        registry["last_no_change_date"] = today.isoformat()
        save_registry(registry, config.arxiv.registry_path)
        raise NoNewPapers(
            f"No new arXiv papers since {previous_digest.get('date')}; "
            "leaving the existing published digest unchanged."
        )
    digest = build_digest(papers, config, today, registry=registry)
    save_registry(registry, config.arxiv.registry_path)
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    (data_path / f"{today.isoformat()}.json").write_text(
        json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_outputs(digest, docs_dir=docs_dir)
    return digest


def aggregate_local_digests(
    config_path: str = "config/default.json",
    date: dt.date | None = None,
    data_dir: str | Path = "data/daily",
    docs_dir: str | Path = "docs",
    lookback_days: int | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    today = date or dt.date.today()
    window_days = config.public_lookback_days if lookback_days is None else lookback_days
    cutoff = today - dt.timedelta(days=window_days)
    papers_by_id: dict[str, dict[str, Any]] = {}

    for path in sorted(Path(data_dir).glob("*.json")):
        try:
            digest = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for item in digest.get("papers", []):
            paper = item.get("paper", {})
            arxiv_id = paper.get("arxiv_id")
            published = paper.get("published", "")
            if not arxiv_id or not published:
                continue
            try:
                published_date = dt.datetime.fromisoformat(
                    published.replace("Z", "+00:00")
                ).date()
            except ValueError:
                continue
            if published_date < cutoff:
                continue
            item = _refresh_local_paths(item, config)
            previous = papers_by_id.get(arxiv_id)
            if previous is None or _item_updated_at(item) >= _item_updated_at(previous):
                papers_by_id[arxiv_id] = item

    papers = sorted(
        papers_by_id.values(),
        key=lambda item: item.get("paper", {}).get("published", ""),
        reverse=True,
    )
    digest = {
        "date": today.isoformat(),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "config": to_jsonable(config),
        "query": build_arxiv_query(config.arxiv, today=today),
        "papers": papers,
        "trending_keywords": rank_keywords(papers, top_n=config.trending_top_n),
        "source": "local_daily_aggregate",
    }
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    (data_path / f"{today.isoformat()}.json").write_text(
        json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_outputs(digest, docs_dir=docs_dir)
    return digest


def _refresh_local_paths(item: dict[str, Any], config: SiteConfig) -> dict[str, Any]:
    paper = _paper_from_dict(item.get("paper", {}))
    if not paper:
        return item
    refreshed = {"paper": dict(item.get("paper", {})), "analysis": item.get("analysis", {})}
    pdf_path = paper_pdf_path(
        config.arxiv.pdf_dir,
        paper,
        config.arxiv.categories,
        config.arxiv.storage_category_policy,
    )
    markdown_path = paper_markdown_path(
        config.arxiv.markdown_dir,
        paper,
        config.arxiv.categories,
        config.arxiv.storage_category_policy,
    )
    refreshed["paper"]["local_pdf_path"] = str(pdf_path) if pdf_path.exists() else item.get("paper", {}).get("local_pdf_path")
    refreshed["paper"]["markdown_path"] = str(markdown_path) if markdown_path.exists() else item.get("paper", {}).get("markdown_path")
    refreshed["paper"]["pdf_download_error"] = item.get("paper", {}).get("pdf_download_error")
    refreshed["paper"]["markdown_parse_error"] = item.get("paper", {}).get("markdown_parse_error")
    return refreshed


def _item_updated_at(item: dict[str, Any]) -> str:
    return str(item.get("analysis", {}).get("updated_at") or item.get("paper", {}).get("updated", ""))


def reanalyze_digest(
    input_path: str | Path,
    config_path: str = "config/default.json",
    output_path: str | Path | None = None,
    docs_dir: str | Path = "docs",
    limit: int | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    source_path = Path(input_path)
    digest = json.loads(source_path.read_text(encoding="utf-8"))
    date = dt.date.fromisoformat(digest["date"])
    registry = load_registry(config.arxiv.registry_path)

    enriched_papers = []
    paper_items = digest.get("papers", [])
    reanalyze_total = len(paper_items) if limit is None else min(limit, len(paper_items))
    for index, item in enumerate(paper_items, start=1):
        paper = _paper_from_dict(item.get("paper", {}))
        if not paper:
            enriched_papers.append(item)
            continue
        if limit is not None and index > limit:
            enriched_papers.append(item)
            continue

        _log_stage(paper, f"reanalyze {index}/{reanalyze_total}")
        registry_entry = ensure_paper(registry, paper, seen_date=date)
        paper_data = dict(item.get("paper", paper.to_dict()))

        markdown_path = (
            paper_data.get("markdown_path")
            or cached_markdown_path(registry_entry)
            or registry_entry.get("mineru", {}).get("markdown_path")
        )
        markdown_excerpt = read_markdown_excerpt(markdown_path)
        if markdown_path:
            paper_data["markdown_path"] = markdown_path

        analysis_source = "markdown" if markdown_excerpt else "abstract"
        _log_stage(paper, f"llm reanalyze source={analysis_source}")
        analysis = enrich_paper(
            paper,
            keywords_per_paper=config.keywords_per_paper,
            markdown_excerpt=markdown_excerpt,
        )
        _log_stage(
            paper,
            f"llm done used={analysis.get('llm_used')} topic={analysis.get('topic')}",
        )
        update_analysis_status(registry_entry, analysis)
        enriched_papers.append({"paper": paper_data, "analysis": analysis})

    digest = {
        "date": digest["date"],
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "config": to_jsonable(config),
        "query": digest.get("query") or build_arxiv_query(config.arxiv, today=date),
        "papers": enriched_papers,
        "trending_keywords": rank_keywords(enriched_papers, top_n=config.trending_top_n),
    }
    save_registry(registry, config.arxiv.registry_path)
    target_path = Path(output_path) if output_path else source_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_outputs(digest, docs_dir=docs_dir)
    return digest


def _merge_papers(papers: list[Paper]) -> list[Paper]:
    by_id: dict[str, Paper] = {}
    for paper in papers:
        by_id[paper.arxiv_id] = paper
    return sorted(by_id.values(), key=lambda paper: paper.published, reverse=True)


def load_cached_papers(
    registry: dict[str, Any],
    data_dir: str | Path,
    today: dt.date,
    limit: int,
) -> list[Paper]:
    papers = _papers_from_registry(registry, today=today)
    if not papers:
        papers = _papers_from_latest_daily(data_dir)
    return papers[:limit]


def build_digest(
    papers: list[Paper],
    config: SiteConfig,
    date: dt.date,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = registry if registry is not None else {"papers": {}}
    enriched_papers = []
    total = len(papers)
    for index, paper in enumerate(papers, start=1):
        _log_stage(paper, f"start {index}/{total}")
        registry_entry = ensure_paper(registry, paper, seen_date=date)
        paper_data = paper.to_dict()
        paper_data["local_pdf_path"] = None
        paper_data["pdf_download_error"] = None
        paper_data["markdown_path"] = None
        paper_data["markdown_parse_error"] = None
        if config.arxiv.download_pdfs:
            try:
                _log_stage(paper, "pdf check/download")
                paper_data["local_pdf_path"] = download_pdf(
                    paper,
                    pdf_dir=config.arxiv.pdf_dir,
                    preferred_categories=config.arxiv.categories,
                    category_policy=config.arxiv.storage_category_policy,
                )
                _log_stage(paper, f"pdf ready: {paper_data['local_pdf_path']}")
            except RuntimeError as exc:
                paper_data["pdf_download_error"] = str(exc)
                _log_stage(paper, f"pdf error: {exc}")
        update_pdf_status(
            registry_entry,
            paper_data["local_pdf_path"],
            paper_data["pdf_download_error"],
        )

        markdown_excerpt = ""
        if config.arxiv.parse_pdfs and paper_data["local_pdf_path"]:
            cached_path = cached_markdown_path(registry_entry)
            if cached_path:
                canonical_markdown_path = paper_markdown_path(
                    config.arxiv.markdown_dir,
                    paper,
                    config.arxiv.categories,
                    config.arxiv.storage_category_policy,
                )
                migrate_legacy_file(Path(cached_path), canonical_markdown_path)
                markdown_path, parse_error = str(canonical_markdown_path), None
                _log_stage(paper, f"mineru cache: {markdown_path}")
            else:
                _log_stage(paper, "mineru parse")
                markdown_path, parse_error = parse_pdf_to_markdown(
                    paper_data["local_pdf_path"], paper, config.arxiv
                )
                if markdown_path:
                    _log_stage(paper, f"mineru ready: {markdown_path}")
                if parse_error:
                    _log_stage(paper, f"mineru error: {parse_error}")
            paper_data["markdown_path"] = markdown_path
            paper_data["markdown_parse_error"] = parse_error
            update_mineru_status(
                registry_entry,
                markdown_path,
                parse_error,
                output_dir=str(
                    paper_mineru_dir(
                        config.arxiv.mineru_output_dir,
                        paper,
                        config.arxiv.categories,
                        config.arxiv.storage_category_policy,
                    )
                ),
            )
            markdown_excerpt = read_markdown_excerpt(markdown_path)

        analysis_source = "markdown" if markdown_excerpt else "abstract"
        analysis = cached_analysis(registry_entry, source=analysis_source)
        if analysis is None:
            _log_stage(paper, f"llm summarize source={analysis_source}")
            analysis = enrich_paper(
                paper,
                keywords_per_paper=config.keywords_per_paper,
                markdown_excerpt=markdown_excerpt,
            )
            _log_stage(
                paper,
                f"llm done used={analysis.get('llm_used')} topic={analysis.get('topic')}",
            )
        else:
            analysis["cache_hit"] = True
            _log_stage(paper, f"llm cache source={analysis_source} topic={analysis.get('topic')}")
        update_analysis_status(registry_entry, analysis)
        enriched_papers.append(
            {
                "paper": paper_data,
                "analysis": analysis,
            }
        )

    return {
        "date": date.isoformat(),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "config": to_jsonable(config),
        "query": build_arxiv_query(config.arxiv, today=date),
        "papers": enriched_papers,
        "trending_keywords": rank_keywords(enriched_papers, top_n=config.trending_top_n),
    }


def _papers_from_latest_daily(data_dir: str | Path) -> list[Paper]:
    digest = _latest_daily_digest(data_dir)
    if digest:
        papers = []
        for item in digest.get("papers", []):
            paper_data = item.get("paper", {})
            paper = _paper_from_dict(paper_data)
            if paper:
                papers.append(paper)
        if papers:
            return papers
    return []


def _latest_daily_digest(data_dir: str | Path) -> dict[str, Any] | None:
    daily_dir = Path(data_dir)
    if not daily_dir.exists():
        return None
    daily_files = sorted(daily_dir.glob("*.json"), reverse=True)
    for path in daily_files:
        try:
            digest = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if digest.get("papers"):
            return digest
    return None


def _same_paper_ids(previous_items: list[dict[str, Any]], papers: list[Paper]) -> bool:
    previous_ids = [item.get("paper", {}).get("arxiv_id") for item in previous_items]
    current_ids = [paper.arxiv_id for paper in papers]
    return bool(previous_ids) and previous_ids == current_ids


def _papers_from_registry(registry: dict[str, Any], today: dt.date) -> list[Paper]:
    entries = list(registry.get("papers", {}).values())
    entries.sort(key=lambda item: item.get("last_seen", ""), reverse=True)
    papers = []
    cutoff = today - dt.timedelta(days=30)
    for entry in entries:
        paper_data = entry.get("paper", {})
        paper = _paper_from_dict(paper_data)
        if not paper:
            continue
        try:
            published = dt.datetime.fromisoformat(paper.published.replace("Z", "+00:00")).date()
        except ValueError:
            published = today
        if published >= cutoff:
            papers.append(paper)
    return papers


def _paper_from_dict(data: dict[str, Any]) -> Paper | None:
    required = {
        "arxiv_id",
        "title",
        "authors",
        "abstract",
        "published",
        "updated",
        "categories",
        "pdf_url",
        "abs_url",
    }
    if not required.issubset(data):
        return None
    return Paper(
        arxiv_id=data["arxiv_id"],
        title=data["title"],
        authors=list(data["authors"]),
        abstract=data["abstract"],
        published=data["published"],
        updated=data["updated"],
        categories=list(data["categories"]),
        pdf_url=data["pdf_url"],
        abs_url=data["abs_url"],
    )


def _log_stage(paper: Paper, message: str) -> None:
    print(f"[PaperRadar] {paper.arxiv_id} | {message}", flush=True)
