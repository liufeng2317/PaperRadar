from __future__ import annotations

import datetime as dt

from paperradar.config import ArxivConfig


def build_arxiv_query(config: ArxivConfig, today: dt.date | None = None) -> str:
    if config.query:
        return config.query

    parts = []
    categories = [f"cat:{category}" for category in config.categories]
    extra_terms = [f'all:"{term}"' if " " in term else f"all:{term}" for term in config.extra_terms]
    discovery_query = _join_or(categories + extra_terms)
    if discovery_query:
        parts.append(discovery_query)

    keyword_query = _build_keyword_query(config.keywords, config.keyword_fields)
    if keyword_query:
        parts.append(keyword_query)

    author_query = _build_author_query(config.authors, config.match_all_authors)
    if author_query:
        parts.append(author_query)

    time_query = _build_time_query(config, today=today)
    if time_query:
        parts.append(time_query)

    return " AND ".join(f"({part})" for part in parts)


def _build_keyword_query(keywords: list[str], fields: list[str]) -> str:
    field_names = set(fields or ["all"])
    terms = []
    for keyword in keywords:
        if "all" in field_names:
            terms.append(_field_query("all", keyword))
            continue
        field_terms = []
        if "title" in field_names:
            field_terms.append(_field_query("ti", keyword))
        if "abstract" in field_names:
            field_terms.append(_field_query("abs", keyword))
        if field_terms:
            terms.append(_join_or(field_terms))
    return " AND ".join(f"({term})" for term in terms)


def _build_author_query(authors: list[str], match_all: bool) -> str:
    queries = [_field_query("au", author) for author in authors]
    if match_all:
        return " AND ".join(f"({query})" for query in queries)
    return _join_or(queries)


def _build_time_query(config: ArxivConfig, today: dt.date | None) -> str:
    today = today or dt.date.today()
    if config.submitted_after:
        start = config.submitted_after.replace("-", "")
        end = config.submitted_before.replace("-", "") if config.submitted_before else "*"
        return f"submittedDate:[{start} TO {end}]"
    if config.lookback_days > 0:
        start = (today - dt.timedelta(days=config.lookback_days)).strftime("%Y%m%d")
        return f"submittedDate:[{start} TO *]"
    return ""


def _field_query(field: str, value: str) -> str:
    return f'{field}:"{value}"' if " " in value else f"{field}:{value}"


def _join_or(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return " OR ".join(f"({part})" for part in parts)
