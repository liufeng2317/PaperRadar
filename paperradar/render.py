from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


PAPERS_PER_PAGE = 25


def write_outputs(digest: dict[str, Any], docs_dir: str | Path = "docs") -> None:
    docs_path = Path(docs_dir)
    data_path = docs_path / "data"
    data_path.mkdir(parents=True, exist_ok=True)
    (data_path / "latest.json").write_text(
        json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (docs_path / "index.html").write_text(render_html(digest), encoding="utf-8")


def render_html(digest: dict[str, Any]) -> str:
    papers = digest["papers"]
    trending = digest["trending_keywords"]
    generated_at = digest["generated_at"]
    date = digest["date"]
    title = digest["config"]["site_title"]
    description_en = digest["config"]["site_description"]["en"]
    description_zh = digest["config"]["site_description"]["zh"]
    scope_zh, scope_en = _render_scope_text(digest["config"].get("arxiv", {}))
    paper_cards = "\n".join(_render_paper_card(item, index) for index, item in enumerate(papers))
    trend_items = "\n".join(
        f"<li><span>{i + 1}</span><strong>{_e(item['keyword'])}</strong><em>{item['score']}</em></li>"
        for i, item in enumerate(trending)
    )
    return f"""<!doctype html>
<html lang="zh-CN" data-lang="zh">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_e(title)} | {date}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #18212f;
      --muted: #667085;
      --line: #d7dde8;
      --bg: #f7f8fb;
      --panel: #ffffff;
      --accent: #0f766e;
      --accent-2: #8b5cf6;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
      line-height: 1.55;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }}
    .wrap {{ width: min(1120px, calc(100% - 32px)); margin: 0 auto; }}
    .hero {{ padding: 36px 0 28px; display: grid; gap: 18px; }}
    .topbar {{ display: flex; justify-content: space-between; gap: 16px; align-items: start; }}
    h1 {{ margin: 0; font-size: clamp(2rem, 5vw, 4.5rem); line-height: 1; letter-spacing: 0; }}
    .lede {{ max-width: 860px; margin: 0; color: var(--muted); font-size: 1.05rem; }}
    .scope {{ max-width: 860px; margin: -6px 0 0; color: var(--ink); font-size: .96rem; }}
    .scope strong {{ color: var(--accent); }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 10px; color: var(--muted); font-size: .92rem; }}
    .lang-toggle {{
      display: inline-flex;
      gap: 2px;
      padding: 3px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--bg);
      flex: 0 0 auto;
    }}
    .lang-toggle button {{
      min-width: 54px;
      border: 0;
      border-radius: 6px;
      padding: 7px 10px;
      background: transparent;
      color: var(--muted);
      font: inherit;
      font-size: .9rem;
      cursor: pointer;
    }}
    .lang-toggle button[aria-pressed="true"] {{
      background: var(--panel);
      color: var(--ink);
      box-shadow: 0 1px 2px rgb(16 24 40 / .12);
    }}
    html[data-lang="zh"] [data-lang="en"] {{ display: none; }}
    html[data-lang="en"] [data-lang="zh"] {{ display: none; }}
    main {{ padding: 28px 0 48px; }}
    .grid {{ display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 24px; align-items: start; }}
    section {{ min-width: 0; }}
    h2 {{ margin: 0 0 14px; font-size: 1.2rem; }}
    .paper {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      margin-bottom: 14px;
    }}
    .paper h3 {{ margin: 0 0 8px; font-size: 1.05rem; line-height: 1.35; }}
    .paper h3 a {{ color: var(--ink); text-decoration: none; }}
    .paper h3 a:hover {{ color: var(--accent); }}
    .authors {{ margin: 0 0 10px; color: var(--muted); font-size: .9rem; }}
    .summary {{ display: grid; gap: 8px; margin: 12px 0; }}
    .summary p {{ margin: 0; }}
    .one-line {{ margin: 12px 0; font-size: .98rem; }}
    .one-line strong {{ font-weight: 650; }}
    details {{
      margin-top: 14px;
      border-top: 1px solid var(--line);
      padding-top: 12px;
    }}
    summary {{
      width: fit-content;
      color: var(--accent);
      cursor: pointer;
      font-weight: 650;
      font-size: .92rem;
    }}
    .paper.is-hidden {{ display: none; }}
    .keywords {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }}
    .keywords span {{
      border: 1px solid color-mix(in srgb, var(--accent) 35%, var(--line));
      color: var(--accent);
      border-radius: 999px;
      padding: 3px 9px;
      font-size: .84rem;
      background: #effaf8;
    }}
    .side {{
      position: sticky;
      top: 16px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .trend {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 9px; }}
    .trend li {{ display: grid; grid-template-columns: 28px 1fr auto; gap: 8px; align-items: center; }}
    .trend span {{ color: var(--muted); font-variant-numeric: tabular-nums; }}
    .trend strong {{ min-width: 0; overflow-wrap: anywhere; font-size: .94rem; }}
    .trend em {{ color: var(--accent-2); font-style: normal; font-weight: 700; }}
    .pagination {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-top: 18px;
      color: var(--muted);
      font-size: .92rem;
    }}
    .page-buttons {{ display: flex; gap: 8px; }}
    .pagination button {{
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 7px 11px;
      background: var(--panel);
      color: var(--ink);
      font: inherit;
      cursor: pointer;
    }}
    .pagination button:disabled {{
      color: var(--muted);
      cursor: not-allowed;
      opacity: .55;
    }}
    .pagination.is-hidden {{ display: none; }}
    footer {{ color: var(--muted); padding: 24px 0; border-top: 1px solid var(--line); }}
    @media (max-width: 860px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .side {{ position: static; }}
      .topbar {{ display: grid; }}
      .lang-toggle {{ justify-self: start; }}
      .pagination {{ align-items: stretch; flex-direction: column; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="wrap hero">
      <div class="topbar">
        <h1>{_e(title)}</h1>
        <div class="lang-toggle" role="group" aria-label="Language">
          <button type="button" data-set-lang="zh" aria-pressed="true">中文</button>
          <button type="button" data-set-lang="en" aria-pressed="false">EN</button>
        </div>
      </div>
      <p class="lede" data-lang="zh">{_e(description_zh)}</p>
      <p class="lede" data-lang="en">{_e(description_en)}</p>
      <p class="scope" data-lang="zh">{scope_zh}</p>
      <p class="scope" data-lang="en">{scope_en}</p>
      <div class="meta">
        <span data-lang="zh">日期: {_e(date)}</span>
        <span data-lang="en">Date: {_e(date)}</span>
        <span data-lang="zh">论文: {len(papers)}</span>
        <span data-lang="en">Papers: {len(papers)}</span>
        <span data-lang="zh">生成时间: {_e(generated_at)}</span>
        <span data-lang="en">Generated: {_e(generated_at)}</span>
      </div>
    </div>
  </header>
  <main class="wrap grid">
    <section>
      <h2 data-lang="zh">最新论文</h2>
      <h2 data-lang="en">Latest Papers</h2>
      {paper_cards}
      <nav class="pagination" id="pagination" aria-label="Paper pages">
        <span data-lang="zh" id="page-info-zh"></span>
        <span data-lang="en" id="page-info-en"></span>
        <div class="page-buttons">
          <button type="button" id="prev-page" data-lang="zh">上一页</button>
          <button type="button" id="prev-page-en" data-lang="en">Previous</button>
          <button type="button" id="next-page" data-lang="zh">下一页</button>
          <button type="button" id="next-page-en" data-lang="en">Next</button>
        </div>
      </nav>
    </section>
    <aside class="side">
      <h2 data-lang="zh">关键词趋势</h2>
      <h2 data-lang="en">arXiv Trending</h2>
      <ol class="trend">{trend_items}</ol>
    </aside>
  </main>
  <footer>
    <div class="wrap" data-lang="zh">由 PaperRadar 基于 arXiv 元数据与 LLM 总结生成。</div>
    <div class="wrap" data-lang="en">Built by PaperRadar from arXiv metadata and LLM summaries.</div>
  </footer>
  <script>
    (() => {{
      const root = document.documentElement;
      const buttons = Array.from(document.querySelectorAll("[data-set-lang]"));
      const setLanguage = (lang) => {{
        root.dataset.lang = lang;
        root.lang = lang === "zh" ? "zh-CN" : "en";
        localStorage.setItem("paperradar.lang", lang);
        buttons.forEach((button) => {{
          button.setAttribute("aria-pressed", String(button.dataset.setLang === lang));
        }});
      }};
      buttons.forEach((button) => {{
        button.addEventListener("click", () => setLanguage(button.dataset.setLang));
      }});
      const saved = localStorage.getItem("paperradar.lang");
      setLanguage(saved === "en" ? "en" : "zh");
    }})();
    (() => {{
      const pageSize = {PAPERS_PER_PAGE};
      const papers = Array.from(document.querySelectorAll("[data-page-item]"));
      const totalPages = Math.max(1, Math.ceil(papers.length / pageSize));
      const pagination = document.getElementById("pagination");
      const infoZh = document.getElementById("page-info-zh");
      const infoEn = document.getElementById("page-info-en");
      const prevButtons = [document.getElementById("prev-page"), document.getElementById("prev-page-en")];
      const nextButtons = [document.getElementById("next-page"), document.getElementById("next-page-en")];
      let page = 1;
      const renderPage = () => {{
        papers.forEach((paper, index) => {{
          const paperPage = Math.floor(index / pageSize) + 1;
          paper.classList.toggle("is-hidden", paperPage !== page);
        }});
        if (infoZh) infoZh.textContent = `第 ${{page}} / ${{totalPages}} 页，每页最多 ${{pageSize}} 篇`;
        if (infoEn) infoEn.textContent = `Page ${{page}} of ${{totalPages}}, up to ${{pageSize}} papers per page`;
        prevButtons.forEach((button) => {{
          if (button) button.disabled = page <= 1;
        }});
        nextButtons.forEach((button) => {{
          if (button) button.disabled = page >= totalPages;
        }});
        if (pagination) pagination.classList.toggle("is-hidden", totalPages <= 1);
      }};
      prevButtons.forEach((button) => {{
        if (button) button.addEventListener("click", () => {{
          page = Math.max(1, page - 1);
          renderPage();
        }});
      }});
      nextButtons.forEach((button) => {{
        if (button) button.addEventListener("click", () => {{
          page = Math.min(totalPages, page + 1);
          renderPage();
        }});
      }});
      renderPage();
    }})();
  </script>
</body>
</html>
"""


def _render_paper_card(item: dict[str, Any], index: int) -> str:
    paper = item["paper"]
    analysis = item["analysis"]
    authors = ", ".join(paper["authors"][:6])
    if len(paper["authors"]) > 6:
        authors += " et al."
    keywords_en = "".join(f"<span>{_e(keyword)}</span>" for keyword in analysis.get("keywords_en", []))
    keywords_zh = "".join(f"<span>{_e(keyword)}</span>" for keyword in analysis.get("keywords_zh", []))
    pdf_status = _render_pdf_status(paper)
    one_sentence_zh = _compact_sentence(analysis.get("one_sentence_zh") or "")
    one_sentence_en = _compact_sentence(analysis.get("one_sentence_en") or "")
    summary_zh = _render_summary_block(analysis.get("summary_zh"))
    summary_en = _render_summary_block(analysis.get("summary_en"))
    details = _render_analysis_details(analysis)
    return f"""
<article class="paper" data-page-item data-index="{index + 1}">
  <h3><a href="{_e(paper['abs_url'])}">{_e(paper['title'])}</a></h3>
  <p class="authors">{_e(authors)} · {_e(paper['published'][:10])} · {_e(', '.join(paper['categories']))}</p>
  <p class="one-line" data-lang="zh"><strong>{_e(one_sentence_zh)}</strong></p>
  <p class="one-line" data-lang="en"><strong>{_e(one_sentence_en)}</strong></p>
  <div class="keywords" data-lang="zh">{keywords_zh or keywords_en}</div>
  <div class="keywords" data-lang="en">{keywords_en or keywords_zh}</div>
  <details>
    <summary><span data-lang="zh">展开详细总结</span><span data-lang="en">Show details</span></summary>
    <div class="summary" data-lang="zh">{summary_zh}</div>
    <div class="summary" data-lang="en">{summary_en}</div>
    {details}
    {pdf_status}
  </details>
</article>
"""


def _render_scope_text(arxiv_config: dict[str, Any]) -> tuple[str, str]:
    categories = arxiv_config.get("categories") or []
    extra_terms = arxiv_config.get("extra_terms") or []
    keywords = arxiv_config.get("keywords") or []
    query = arxiv_config.get("query") or ""

    if query:
        return (
            f'当前追踪范围: <strong>{_e(query)}</strong>',
            f'Current scope: <strong>{_e(query)}</strong>',
        )

    category_text = ", ".join(str(category) for category in categories) or "all configured arXiv"
    term_values = [str(term) for term in [*extra_terms, *keywords] if term]
    if term_values:
        terms = ", ".join(term_values[:8])
        suffix = " ..." if len(term_values) > 8 else ""
        return (
            f'当前追踪范围: <strong>{_e(category_text)}</strong>; 主题词: {_e(terms)}{suffix}',
            f'Current scope: <strong>{_e(category_text)}</strong>; topic terms: {_e(terms)}{suffix}',
        )

    return (
        f'当前追踪范围: <strong>{_e(category_text)}</strong>',
        f'Current scope: <strong>{_e(category_text)}</strong>',
    )


def _render_summary_block(summary: Any) -> str:
    items = summary if isinstance(summary, list) else [summary] if summary else []
    bullet_items = "".join(f"<li>{_e(item)}</li>" for item in items if item)
    return f"<ul>{bullet_items}</ul>" if bullet_items else ""


def _compact_sentence(value: Any, max_chars: int = 260) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _render_analysis_details(analysis: dict[str, Any]) -> str:
    rows_en = [
        ("Contribution", analysis.get("contribution_en")),
        ("Method", analysis.get("method_en")),
        ("Data/Region", analysis.get("data_or_region_en")),
        ("Relevance", analysis.get("geophysics_relevance_en")),
    ]
    rows_zh = [
        ("主要贡献", analysis.get("contribution_zh")),
        ("方法", analysis.get("method_zh")),
        ("数据/区域", analysis.get("data_or_region_zh")),
        ("相关性", analysis.get("geophysics_relevance_zh")),
    ]
    rendered_en = "".join(
        f"<p><strong>{_e(label)}:</strong> {_e(value)}</p>" for label, value in rows_en if value
    )
    rendered_zh = "".join(
        f"<p><strong>{_e(label)}:</strong> {_e(value)}</p>" for label, value in rows_zh if value
    )
    parts = []
    if rendered_zh:
        parts.append(f'<div class="summary" data-lang="zh">{rendered_zh}</div>')
    if rendered_en:
        parts.append(f'<div class="summary" data-lang="en">{rendered_en}</div>')
    return "".join(parts)


def _render_pdf_status(paper: dict[str, Any]) -> str:
    pdf_url = paper.get("pdf_url", "")
    error = paper.get("pdf_download_error")
    if pdf_url:
        return (
            '<p class="authors">'
            f'<a href="{_e(pdf_url)}">arXiv PDF</a>'
            '</p>'
        )
    if error:
        return (
            '<p class="authors" data-lang="zh">PDF 下载待处理: '
            f"{_e(error)} · "
            f'<a href="{_e(pdf_url)}">arXiv PDF</a></p>'
            '<p class="authors" data-lang="en">PDF download pending: '
            f"{_e(error)} · "
            f'<a href="{_e(pdf_url)}">arXiv PDF</a></p>'
        )
    return ""


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)
