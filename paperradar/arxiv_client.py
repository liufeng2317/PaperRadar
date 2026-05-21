from __future__ import annotations

import datetime as dt
import html
import random
import socket
import time
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

from paperradar.storage import migrate_legacy_file, paper_pdf_path, safe_arxiv_id


ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


@dataclass(frozen=True)
class Paper:
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    published: str
    updated: str
    categories: list[str]
    pdf_url: str
    abs_url: str

    def to_dict(self) -> dict:
        return asdict(self)


def fetch_recent_papers(
    query: str,
    max_results: int = 25,
    lookback_days: int = 7,
    today: dt.date | None = None,
    polite_delay_seconds: float = 3.0,
    retries: int = 2,
    sort_by: str = "submittedDate",
    sort_order: str = "descending",
) -> list[Paper]:
    today = today or dt.date.today()
    cutoff = today - dt.timedelta(days=lookback_days)
    params = {
        "search_query": query,
        "start": "0",
        "max_results": str(max_results),
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }
    url = f"{ARXIV_API_URL}?{urllib.parse.urlencode(params)}"
    payload = _read_arxiv_url(url, polite_delay_seconds=polite_delay_seconds, retries=retries)

    root = ET.fromstring(payload)
    papers: list[Paper] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        paper = _parse_entry(entry)
        published_date = dt.datetime.fromisoformat(paper.published.replace("Z", "+00:00")).date()
        if published_date >= cutoff:
            papers.append(paper)
    return papers


def _parse_entry(entry: ET.Element) -> Paper:
    title = _clean_text(_find_text(entry, "atom:title"))
    abstract = _clean_text(_find_text(entry, "atom:summary"))
    published = _find_text(entry, "atom:published")
    updated = _find_text(entry, "atom:updated")
    abs_url = _find_text(entry, "atom:id")
    arxiv_id = abs_url.rsplit("/", 1)[-1]
    authors = [
        _clean_text(author.findtext("atom:name", default="", namespaces=ATOM_NS))
        for author in entry.findall("atom:author", ATOM_NS)
    ]
    categories = [
        category.attrib["term"]
        for category in entry.findall("atom:category", ATOM_NS)
        if "term" in category.attrib
    ]
    pdf_url = ""
    for link in entry.findall("atom:link", ATOM_NS):
        if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
            pdf_url = link.attrib.get("href", "")
            break
    return Paper(
        arxiv_id=arxiv_id,
        title=title,
        authors=authors,
        abstract=abstract,
        published=published,
        updated=updated,
        categories=categories,
        pdf_url=pdf_url,
        abs_url=abs_url,
    )


def _find_text(entry: ET.Element, path: str) -> str:
    return entry.findtext(path, default="", namespaces=ATOM_NS)


def _clean_text(value: str) -> str:
    return " ".join(html.unescape(value).split())


def download_pdf(
    paper: Paper,
    pdf_dir: str | Path = "data/pdfs",
    polite_delay_seconds: float = 3.0,
    retries: int = 2,
    preferred_categories: list[str] | None = None,
    category_policy: str = "configured",
) -> str:
    if not paper.pdf_url:
        raise RuntimeError(f"Paper {paper.arxiv_id} does not include a PDF URL.")

    output_dir = Path(pdf_dir)
    output_path = paper_pdf_path(output_dir, paper, preferred_categories, category_policy)
    legacy_path = output_dir / f"{safe_arxiv_id(paper.arxiv_id)}.pdf"
    migrate_legacy_file(legacy_path, output_path)
    if output_path.exists() and output_path.stat().st_size > 0:
        return str(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _read_arxiv_url(
        paper.pdf_url, polite_delay_seconds=polite_delay_seconds, retries=retries
    )
    if not payload.startswith(b"%PDF"):
        raise RuntimeError(f"Downloaded content for {paper.arxiv_id} does not look like a PDF.")
    output_path.write_bytes(payload)
    return str(output_path)


def _read_arxiv_url(url: str, polite_delay_seconds: float, retries: int) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "PaperRadar/0.1 (daily research digest; contact: repository owner)"},
    )
    for attempt in range(retries + 1):
        if attempt == 0:
            time.sleep(max(0.0, polite_delay_seconds))
        else:
            time.sleep((10.0 * attempt) + random.uniform(0, 2))
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except HTTPError as exc:
            if exc.code == 429 and attempt < retries:
                continue
            if exc.code == 429:
                raise RuntimeError(
                    "arXiv API rate limit reached (HTTP 429). Wait a few minutes and try again."
                ) from exc
            raise RuntimeError(f"arXiv API returned HTTP {exc.code}.") from exc
        except (TimeoutError, socket.timeout, URLError) as exc:
            raise RuntimeError(
                "Could not reach the arXiv API. Check network/proxy settings and try again."
            ) from exc

    raise RuntimeError("Could not read from the arXiv API.")
