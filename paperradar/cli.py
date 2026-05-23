from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from paperradar.config import load_config
from paperradar.env import load_dotenv
from paperradar.migrate import migrate_storage
from paperradar.pipeline import NoNewPapers, reanalyze_digest, run_pipeline
from paperradar.query import build_arxiv_query
from paperradar.registry import load_registry
from paperradar.render import write_outputs


def main() -> None:
    load_dotenv(override=True)

    parser = argparse.ArgumentParser(description="Build the PaperRadar digest.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Fetch arXiv papers, summarize them, and render the site.")
    run.add_argument("--config", default="config/default.json")
    run.add_argument("--date", help="Digest date in YYYY-MM-DD format. Defaults to today.")
    run.add_argument("--data-dir", default="data/daily")
    run.add_argument("--docs-dir", default="docs")

    fetch = subparsers.add_parser("fetch", help="Fetch and print recent arXiv papers without rendering.")
    fetch.add_argument("--config", default="config/default.json")
    fetch.add_argument("--date", help="Fetch date in YYYY-MM-DD format. Defaults to today.")

    render = subparsers.add_parser("render", help="Render docs from an existing digest JSON file.")
    render.add_argument("--input", required=True)
    render.add_argument("--docs-dir", default="docs")

    reanalyze = subparsers.add_parser(
        "reanalyze",
        help="Rerun LLM summaries from an existing digest JSON without fetching arXiv or parsing PDFs.",
    )
    reanalyze.add_argument("--input", required=True)
    reanalyze.add_argument("--config", default="config/default.json")
    reanalyze.add_argument("--output", help="Output JSON path. Defaults to overwriting --input.")
    reanalyze.add_argument("--docs-dir", default="docs")
    reanalyze.add_argument("--limit", type=int, help="Only reanalyze the first N papers.")

    registry = subparsers.add_parser("registry", help="Show or search the local paper registry.")
    registry.add_argument("--config", default="config/default.json")
    registry.add_argument("--query", help="Search title, arXiv id, topic, or keywords.")
    registry.add_argument("--limit", type=int, default=20)

    migrate = subparsers.add_parser("migrate-storage", help="Reorganize local data into category/publication-day folders.")
    migrate.add_argument("--config", default="config/default.json")

    args = parser.parse_args()
    if args.command == "run":
        try:
            digest = run_pipeline(
                config_path=args.config,
                date=_parse_date(args.date),
                data_dir=args.data_dir,
                docs_dir=args.docs_dir,
            )
        except NoNewPapers as exc:
            print(f"No update: {exc}")
            return
        except RuntimeError as exc:
            parser.exit(1, f"error: {exc}\n")
        print(f"Rendered {len(digest['papers'])} papers for {digest['date']}")
    elif args.command == "fetch":
        from paperradar.arxiv_client import fetch_recent_papers

        config = load_config(args.config)
        fetch_date = _parse_date(args.date)
        try:
            papers = fetch_recent_papers(
                query=build_arxiv_query(config.arxiv, today=fetch_date),
                max_results=config.arxiv.max_results,
                lookback_days=config.arxiv.lookback_days,
                today=fetch_date,
                polite_delay_seconds=config.arxiv.request_delay_seconds,
                retries=config.arxiv.max_retries,
                sort_by=config.arxiv.sort_by,
                sort_order=config.arxiv.sort_order,
            )
        except RuntimeError as exc:
            parser.exit(1, f"error: {exc}\n")
        print(json.dumps([paper.to_dict() for paper in papers], ensure_ascii=False, indent=2))
    elif args.command == "render":
        digest = json.loads(Path(args.input).read_text(encoding="utf-8"))
        write_outputs(digest, docs_dir=args.docs_dir)
        print(f"Rendered docs from {args.input}")
    elif args.command == "reanalyze":
        digest = reanalyze_digest(
            input_path=args.input,
            config_path=args.config,
            output_path=args.output,
            docs_dir=args.docs_dir,
            limit=args.limit,
        )
        target = args.output or args.input
        print(f"Reanalyzed {len(digest['papers'])} papers into {target}")
    elif args.command == "registry":
        config = load_config(args.config)
        registry_data = load_registry(config.arxiv.registry_path)
        _print_registry(registry_data, query=args.query, limit=args.limit)
    elif args.command == "migrate-storage":
        config = load_config(args.config)
        stats = migrate_storage(config)
        print(json.dumps(stats, ensure_ascii=False, indent=2))


def _parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    return dt.date.fromisoformat(value)


def _print_registry(registry: dict, query: str | None = None, limit: int = 20) -> None:
    papers = list(registry.get("papers", {}).values())
    if query:
        needle = query.lower()
        papers = [entry for entry in papers if needle in _registry_search_text(entry)]
    papers.sort(key=lambda entry: entry.get("last_seen", ""), reverse=True)
    print(f"papers={len(papers)} updated_at={registry.get('updated_at')}")
    for entry in papers[:limit]:
        paper = entry.get("paper", {})
        pdf = entry.get("pdf", {})
        mineru = entry.get("mineru", {})
        analysis = entry.get("analysis", {})
        print(
            " | ".join(
                [
                    paper.get("arxiv_id", entry.get("arxiv_id", "")),
                    paper.get("published", "")[:10],
                    pdf.get("status", "missing"),
                    mineru.get("status", "missing"),
                    analysis.get("topic") or "",
                    paper.get("title", "")[:96],
                ]
            )
        )


def _registry_search_text(entry: dict) -> str:
    paper = entry.get("paper", {})
    analysis = entry.get("analysis", {})
    values = [
        entry.get("arxiv_id", ""),
        paper.get("arxiv_id", ""),
        paper.get("title", ""),
        paper.get("abstract", ""),
        analysis.get("topic", ""),
        " ".join(analysis.get("keywords_en", [])),
        " ".join(analysis.get("keywords_zh", [])),
    ]
    return " ".join(values).lower()


if __name__ == "__main__":
    main()
