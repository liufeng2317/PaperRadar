from __future__ import annotations

import html
import os
import smtplib
from collections import Counter
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Any


TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class EmailSettings:
    enabled: bool
    host: str
    port: int
    username: str
    password: str
    sender: str
    recipients: list[str]
    security: str
    site_url: str


def load_email_settings() -> EmailSettings:
    recipients = _split_addresses(os.getenv("PAPERRADAR_EMAIL_TO", ""))
    sender = os.getenv("PAPERRADAR_EMAIL_FROM", "") or os.getenv("SMTP_USER", "")
    return EmailSettings(
        enabled=_env_true("PAPERRADAR_EMAIL_ENABLED"),
        host=os.getenv("SMTP_HOST", ""),
        port=int(os.getenv("SMTP_PORT", "587") or "587"),
        username=os.getenv("SMTP_USER", ""),
        password=os.getenv("SMTP_PASSWORD", ""),
        sender=sender,
        recipients=recipients,
        security=os.getenv("SMTP_SECURITY", "starttls").strip().lower(),
        site_url=os.getenv("PAPERRADAR_SITE_URL", "").strip(),
    )


def send_digest_email(digest: dict[str, Any], settings: EmailSettings | None = None) -> str:
    settings = settings or load_email_settings()
    if not settings.enabled:
        return "email disabled; set PAPERRADAR_EMAIL_ENABLED=1 to enable"
    _validate_settings(settings)

    message = EmailMessage()
    message["Subject"] = _subject(digest)
    message["From"] = settings.sender
    message["To"] = ", ".join(settings.recipients)
    message.set_content(render_text_email(digest, settings.site_url))
    message.add_alternative(render_html_email(digest, settings.site_url), subtype="html")

    if settings.security == "ssl":
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings.host, settings.port, context=context, timeout=60) as smtp:
            _login_if_needed(smtp, settings)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(settings.host, settings.port, timeout=60) as smtp:
            smtp.ehlo()
            if settings.security == "starttls":
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            elif settings.security not in {"none", ""}:
                raise RuntimeError(f"Unsupported SMTP_SECURITY={settings.security!r}")
            _login_if_needed(smtp, settings)
            smtp.send_message(message)
    return f"email sent to {', '.join(settings.recipients)}"


def filter_digest_for_email(
    digest: dict[str, Any],
    previous_digest: dict[str, Any] | None = None,
    *,
    new_only: bool = False,
    latest_published_day: bool = False,
) -> dict[str, Any]:
    filtered = dict(digest)
    papers = list(digest.get("papers", []))
    if new_only and previous_digest:
        previous_ids = {_paper_id(item) for item in previous_digest.get("papers", [])}
        papers = [item for item in papers if _paper_id(item) not in previous_ids]
    if latest_published_day and papers:
        latest_day = max(_published_day(item) for item in papers)
        papers = [item for item in papers if _published_day(item) == latest_day]
        filtered["email_published_day"] = latest_day
    filtered["papers"] = papers
    filtered["trending_keywords"] = _rank_keywords_from_papers(papers)
    return filtered


def render_text_email(digest: dict[str, Any], site_url: str = "") -> str:
    papers = digest.get("papers", [])
    lines = [
        _email_title(digest),
        f"新增论文数量：{len(papers)}",
    ]
    if site_url:
        lines.append(f"网页：{site_url}")
    lines.append("")

    trend_items = _trend_items_zh(digest)[:15]
    if trend_items:
        lines.append("热门关键词：")
        lines.append("、".join(trend_items))
        lines.append("")

    for index, item in enumerate(papers, start=1):
        paper = item.get("paper", {})
        analysis = item.get("analysis", {})
        authors = ", ".join(paper.get("authors", [])[:4])
        if len(paper.get("authors", [])) > 4:
            authors += " 等"
        keywords = analysis.get("keywords_zh") or analysis.get("keywords_en") or []
        lines.extend(
            [
                f"{index}. {paper.get('title', '')}",
                f"   ID: {paper.get('arxiv_id', '')} | {paper.get('published', '')[:10]} | {authors}",
                f"   一句话：{analysis.get('one_sentence_zh') or analysis.get('one_sentence_en') or ''}",
                f"   关键词：{'、'.join(keywords[:5])}",
                f"   链接：{paper.get('abs_url', '')}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def render_html_email(digest: dict[str, Any], site_url: str = "") -> str:
    papers = digest.get("papers", [])
    title = html.escape(_email_title(digest))
    trend_html = ""
    trend_items = _trend_items_zh(digest)[:15]
    if trend_items:
        trend_html = "<p><strong>热门关键词：</strong>" + "、".join(
            html.escape(item) for item in trend_items
        ) + "</p>"
    site_html = f'<p><a href="{html.escape(site_url)}">打开 PaperRadar 网页</a></p>' if site_url else ""

    paper_blocks = []
    for index, item in enumerate(papers, start=1):
        paper = item.get("paper", {})
        analysis = item.get("analysis", {})
        title = html.escape(str(paper.get("title", "")))
        arxiv_id = html.escape(str(paper.get("arxiv_id", "")))
        published = html.escape(str(paper.get("published", ""))[:10])
        abs_url = html.escape(str(paper.get("abs_url", "")))
        pdf_url = html.escape(str(paper.get("pdf_url", "")))
        authors = ", ".join(str(a) for a in paper.get("authors", [])[:4])
        if len(paper.get("authors", [])) > 4:
            authors += " 等"
        sentence = analysis.get("one_sentence_zh") or analysis.get("one_sentence_en") or ""
        keywords = analysis.get("keywords_zh") or analysis.get("keywords_en") or []
        keyword_text = "、".join(str(k) for k in keywords[:5])
        paper_blocks.append(
            f"""
            <li style=\"margin:0 0 18px 0;\">
              <p style=\"margin:0 0 6px 0;\"><strong>{index}. {title}</strong></p>
              <p style=\"margin:0 0 6px 0;color:#555;\">ID: {arxiv_id} | {published} | {html.escape(authors)}</p>
              <p style=\"margin:0 0 6px 0;\">{html.escape(str(sentence))}</p>
              <p style=\"margin:0 0 6px 0;color:#555;\">关键词：{html.escape(keyword_text)}</p>
              <p style=\"margin:0;\"><a href=\"{abs_url}\">摘要</a> · <a href=\"{pdf_url}\">PDF</a></p>
            </li>
            """
        )

    return f"""<!doctype html>
<html>
  <body style=\"font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;line-height:1.55;color:#111;\">
    <h2 style=\"margin-bottom:4px;\">{title}</h2>
    <p style=\"margin-top:0;color:#555;\">新增 {len(papers)} 篇论文</p>
    {site_html}
    {trend_html}
    <ol style=\"padding-left:22px;\">{''.join(paper_blocks)}</ol>
  </body>
</html>
"""


def digest_from_file(path: str | Path) -> dict[str, Any]:
    import json

    return json.loads(Path(path).read_text(encoding="utf-8"))


def _subject(digest: dict[str, Any]) -> str:
    day = digest.get("email_published_day") or digest.get("date", "")
    count = len(digest.get("papers", []))
    return f"[PaperRadar] {day} 预印本新论文：{count} 篇"


def _email_title(digest: dict[str, Any]) -> str:
    day = digest.get("email_published_day") or digest.get("date", "")
    return f"PaperRadar 中文新论文 - {day}"


def _paper_id(item: dict[str, Any]) -> str:
    return str(item.get("paper", {}).get("arxiv_id", ""))


def _published_day(item: dict[str, Any]) -> str:
    return str(item.get("paper", {}).get("published", ""))[:10]


def _rank_keywords_from_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for item in papers:
        analysis = item.get("analysis", {})
        for keyword in analysis.get("keywords_zh") or []:
            text = str(keyword).strip()
            if text:
                counter[text] += 1
    return [{"keyword_zh": keyword, "score": count} for keyword, count in counter.most_common()]


def _trend_items_zh(digest: dict[str, Any]) -> list[str]:
    counter: Counter[str] = Counter()
    for item in digest.get("papers", []):
        analysis = item.get("analysis", {})
        for keyword in analysis.get("keywords_zh") or []:
            text = str(keyword).strip()
            if text:
                counter[text] += 1
    if counter:
        return [f"{keyword}({count})" for keyword, count in counter.most_common()]
    return _trend_items(digest)


def _trend_items(digest: dict[str, Any]) -> list[str]:
    values = []
    for item in digest.get("trending_keywords", []):
        if isinstance(item, dict):
            keyword = item.get("keyword_zh") or item.get("keyword") or item.get("keyword_en")
            count = item.get("count") or item.get("score")
            if keyword and count:
                values.append(f"{keyword}({count})")
            elif keyword:
                values.append(str(keyword))
        elif isinstance(item, (list, tuple)) and item:
            values.append(str(item[0]))
        elif item:
            values.append(str(item))
    return values


def _split_addresses(value: str) -> list[str]:
    return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in TRUE_VALUES


def _validate_settings(settings: EmailSettings) -> None:
    missing = []
    if not settings.host:
        missing.append("SMTP_HOST")
    if not settings.sender:
        missing.append("PAPERRADAR_EMAIL_FROM or SMTP_USER")
    if not settings.recipients:
        missing.append("PAPERRADAR_EMAIL_TO")
    if missing:
        raise RuntimeError("Missing email settings: " + ", ".join(missing))


def _login_if_needed(smtp: smtplib.SMTP, settings: EmailSettings) -> None:
    if settings.username or settings.password:
        smtp.login(settings.username, settings.password)
