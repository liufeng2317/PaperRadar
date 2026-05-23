from __future__ import annotations

import datetime as dt
import html
import random
import socket
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError

from paperradar.arxiv_client import Paper


OAI_NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def fetch_eartharxiv_papers(
    base_url: str = "https://eartharxiv.org/api/oai/",
    max_results: int = 25,
    lookback_days: int = 60,
    today: dt.date | None = None,
    subjects: list[str] | None = None,
    keywords: list[str] | None = None,
    polite_delay_seconds: float = 3.0,
    retries: int = 2,
    disable_proxy: bool = True,
) -> list[Paper]:
    today = today or dt.date.today()
    cutoff = today - dt.timedelta(days=lookback_days)
    params = {
        "verb": "ListRecords",
        "metadataPrefix": "oai_dc",
        "from": cutoff.isoformat(),
        "until": today.isoformat(),
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    payload = _read_url(
        url,
        polite_delay_seconds=polite_delay_seconds,
        retries=retries,
        disable_proxy=disable_proxy,
    )
    root = ET.fromstring(payload)
    papers: list[Paper] = []
    for record in root.findall(".//oai:record", OAI_NS):
        paper = _parse_record(record)
        if not paper:
            continue
        try:
            published_date = dt.datetime.fromisoformat(
                paper.published.replace("Z", "+00:00")
            ).date()
        except ValueError:
            continue
        if published_date < cutoff:
            continue
        if not _matches_filters(paper, subjects or [], keywords or []):
            continue
        papers.append(paper)
        if len(papers) >= max_results:
            break
    return papers


def _parse_record(record: ET.Element) -> Paper | None:
    metadata = record.find("oai:metadata", OAI_NS)
    if metadata is None:
        return None
    title = _clean(_first(metadata, "dc:title"))
    abstract = _clean(_first(metadata, "dc:description"))
    authors = [_clean(item.text or "") for item in metadata.findall(".//dc:creator", OAI_NS)]
    subjects = [_clean(item.text or "") for item in metadata.findall(".//dc:subject", OAI_NS)]
    dates = [_clean(item.text or "") for item in metadata.findall(".//dc:date", OAI_NS)]
    identifiers = [_clean(item.text or "") for item in metadata.findall(".//dc:identifier", OAI_NS)]
    source_id = _source_id(identifiers, record)
    if not title or not source_id:
        return None
    published = dates[0] if dates else _header_datestamp(record)
    updated = dates[-1] if dates else published
    pdf_url = _pdf_url(identifiers)
    abs_url = f"https://eartharxiv.org/repository/view/{source_id}/"
    doi = next((value for value in identifiers if value.startswith("10.")), "")
    categories = subjects or ["EarthArXiv"]
    paper = Paper(
        arxiv_id=f"eartharxiv-{source_id}",
        title=title,
        authors=authors,
        abstract=abstract,
        published=published,
        updated=updated,
        categories=categories,
        pdf_url=pdf_url,
        abs_url=abs_url,
        source="eartharxiv",
        source_id=source_id,
        doi=doi,
    )
    return paper


def _matches_filters(paper: Paper, subjects: list[str], keywords: list[str]) -> bool:
    subject_needles = [item.lower() for item in subjects if item]
    keyword_needles = [item.lower() for item in keywords if item]
    subject_text = " ".join(paper.categories).lower()
    search_text = " ".join([paper.title, paper.abstract, subject_text]).lower()
    subject_ok = not subject_needles or any(needle in subject_text for needle in subject_needles)
    keyword_ok = not keyword_needles or any(needle in search_text for needle in keyword_needles)
    return subject_ok and keyword_ok


def _first(parent: ET.Element, path: str) -> str:
    node = parent.find(f".//{path}", OAI_NS)
    return node.text if node is not None and node.text else ""


def _source_id(identifiers: list[str], record: ET.Element) -> str:
    for value in identifiers:
        if value.isdigit():
            return value
    header_id = _first(record, "oai:identifier")
    if header_id.rsplit(":", 1)[-1].isdigit():
        return header_id.rsplit(":", 1)[-1]
    return ""


def _pdf_url(identifiers: list[str]) -> str:
    for value in identifiers:
        if "/download/" in value and value.startswith("http"):
            return value
    return ""


def _header_datestamp(record: ET.Element) -> str:
    return _first(record, "oai:datestamp")


def _clean(value: str) -> str:
    return " ".join(html.unescape(value).split())


def _read_url(url: str, polite_delay_seconds: float, retries: int, disable_proxy: bool) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "PaperRadar/0.1 (EarthArXiv OAI-PMH harvester)"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if disable_proxy else urllib.request.build_opener()
    for attempt in range(retries + 1):
        if attempt == 0:
            time.sleep(max(0.0, polite_delay_seconds))
        else:
            time.sleep((10.0 * attempt) + random.uniform(0, 2))
        try:
            with opener.open(request, timeout=30) as response:
                return response.read()
        except HTTPError as exc:
            if exc.code in {429, 500, 502, 503, 504} and attempt < retries:
                continue
            raise RuntimeError(f"EarthArXiv OAI returned HTTP {exc.code}.") from exc
        except (TimeoutError, socket.timeout, URLError) as exc:
            if attempt < retries:
                continue
            raise RuntimeError("Could not reach EarthArXiv OAI. Check network/proxy settings.") from exc
    raise RuntimeError("Could not read from EarthArXiv OAI.")
