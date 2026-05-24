from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from paperradar.trend import rank_keywords


PAPERS_PER_PAGE = 25


def write_outputs(digest: dict[str, Any], docs_dir: str | Path = "docs") -> None:
    docs_path = Path(docs_dir)
    data_path = docs_path / "data"
    data_path.mkdir(parents=True, exist_ok=True)
    _write_json(data_path / "latest.json", digest)
    for source in ["arxiv", "eartharxiv"]:
        _write_json(data_path / f"latest.{source}.json", _source_digest(digest, source))
    (docs_path / "index.html").write_text(render_html(digest), encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _source_digest(digest: dict[str, Any], source: str) -> dict[str, Any]:
    papers = [
        item for item in digest.get("papers", [])
        if (item.get("paper", {}).get("source") or "arxiv") == source
    ]
    source_digest = dict(digest)
    source_digest["papers"] = papers
    source_digest["trending_keywords"] = rank_keywords(
        papers, top_n=digest.get("config", {}).get("trending_top_n", 30)
    )
    source_digest["source"] = source
    return source_digest


def render_html(digest: dict[str, Any]) -> str:
    return """<!doctype html>
<html lang="zh-CN" data-lang="zh">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PaperRadar</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #142033;
      --muted: #647084;
      --line: #d9e0ea;
      --soft-line: #e8edf4;
      --bg: #f6f8fb;
      --panel: #ffffff;
      --panel-soft: #fbfcfe;
      --accent: #0f766e;
      --accent-soft: #e8f7f4;
      --earth: #6f7d1f;
      --earth-soft: #f3f6df;
      --arxiv: #365cc8;
      --arxiv-soft: #eef3ff;
      --accent-2: #7c3aed;
      --danger: #b42318;
      --shadow: 0 10px 30px rgb(20 32 51 / .08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
      line-height: 1.55;
    }
    header { border-bottom: 1px solid var(--line); background: linear-gradient(180deg, #ffffff 0%, #f8fbfb 100%); }
    .wrap { width: min(1180px, calc(100% - 32px)); margin: 0 auto; }
    .hero { padding: 34px 0 24px; display: grid; gap: 18px; }
    .topbar { display: flex; justify-content: space-between; gap: 16px; align-items: start; }
    h1 { margin: 0; font-size: clamp(2.2rem, 5vw, 4.7rem); line-height: .96; letter-spacing: 0; }
    .hero-copy { display: grid; gap: 9px; }
    .kicker { margin: 0; color: var(--accent); font-size: .82rem; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; }
    .lede { max-width: 920px; margin: 0; color: var(--ink); font-size: clamp(1.08rem, 2.1vw, 1.42rem); line-height: 1.38; font-weight: 650; }
    .scope { max-width: 980px; margin: 0; color: var(--muted); font-size: .94rem; }
    .scope strong { color: var(--accent); }
    .lang-toggle {
      display: inline-flex;
      gap: 2px;
      padding: 3px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--bg);
      flex: 0 0 auto;
    }
    .lang-toggle button {
      min-width: 54px;
      border: 0;
      border-radius: 6px;
      padding: 7px 10px;
      background: transparent;
      color: var(--muted);
      font: inherit;
      font-size: .9rem;
      cursor: pointer;
    }
    .lang-toggle button[aria-pressed="true"] { background: var(--panel); color: var(--ink); box-shadow: 0 1px 2px rgb(16 24 40 / .12); }
    html[data-lang="zh"] [data-lang="en"] { display: none; }
    html[data-lang="en"] [data-lang="zh"] { display: none; }
    .dash { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 4px; }
    .metric { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 13px 14px; box-shadow: 0 1px 2px rgb(20 32 51 / .04); }
    .metric span { display: block; color: var(--muted); font-size: .78rem; text-transform: uppercase; letter-spacing: .04em; }
    .metric strong { display: block; margin-top: 4px; font-size: 1.35rem; line-height: 1.1; }
    .metric small { display: block; margin-top: 3px; color: var(--muted); font-size: .78rem; overflow-wrap: anywhere; }
    main { padding: 24px 0 48px; }
    .grid { display: grid; grid-template-columns: minmax(0, 1fr) 330px; gap: 22px; align-items: start; }
    section { min-width: 0; }
    h2 { margin: 0 0 14px; font-size: 1.08rem; }
    .toolbar { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; margin-bottom: 14px; }
    .search {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px 12px;
      color: var(--ink);
      background: var(--panel);
      font: inherit;
      box-shadow: inset 0 1px 2px rgb(20 32 51 / .03);
    }
    .clear-filter {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      color: var(--ink);
      padding: 0 12px;
      font: inherit;
      cursor: pointer;
    }
    .active-filter { min-height: 22px; color: var(--muted); font-size: .88rem; margin: -4px 0 12px; }
    .active-filter strong { color: var(--accent); }
    .source-tabs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; margin: 0 0 16px; }
    .source-tabs button {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px 13px;
      background: var(--panel);
      color: var(--ink);
      font: inherit;
      font-weight: 750;
      cursor: pointer;
      text-align: left;
      box-shadow: 0 1px 2px rgb(20 32 51 / .04);
    }
    .source-tabs button::before { content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 999px; margin-right: 7px; background: var(--arxiv); }
    .source-tabs button[data-source-tab="eartharxiv"]::before { background: var(--earth); }
    .source-tabs button[aria-selected="true"] { border-color: color-mix(in srgb, var(--accent) 50%, var(--line)); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent) 22%, transparent), var(--shadow); }
    .source-tabs small { display: block; margin-top: 3px; color: var(--muted); font-weight: 500; }
    .source-panel[hidden] { display: none; }
    .panel-title { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 12px; }
    .panel-title h2 { margin: 0; }
    .panel-title span { color: var(--muted); font-size: .88rem; }
    .empty-source, .load-error { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 20px; color: var(--muted); }
    .load-error { color: var(--danger); border-color: color-mix(in srgb, var(--danger) 30%, var(--line)); }
    .source-badge { display: inline-flex; align-items: center; border-radius: 999px; padding: 2px 8px; border: 1px solid color-mix(in srgb, var(--arxiv) 34%, var(--line)); color: var(--arxiv); background: var(--arxiv-soft); font-size: .75rem; font-weight: 800; }
    .source-badge.eartharxiv { border-color: color-mix(in srgb, var(--earth) 36%, var(--line)); color: var(--earth); background: var(--earth-soft); }
    .paper { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 2px rgb(20 32 51 / .04); }
    .paper:hover { border-color: color-mix(in srgb, var(--accent) 28%, var(--line)); }
    .paper-head { display: flex; justify-content: space-between; gap: 14px; align-items: start; }
    .paper h3 { margin: 0 0 8px; font-size: 1.08rem; line-height: 1.34; }
    .paper h3 a { color: var(--ink); text-decoration: none; }
    .paper h3 a:hover { color: var(--accent); }
    .paper-actions { display: flex; gap: 7px; flex: 0 0 auto; }
    .paper-actions a { border: 1px solid var(--line); border-radius: 7px; padding: 5px 8px; color: var(--ink); text-decoration: none; font-size: .8rem; background: var(--panel-soft); }
    .authors { margin: 0 0 8px; color: var(--muted); font-size: .88rem; }
    .one-line { margin: 10px 0; font-size: .98rem; }
    .one-line strong { font-weight: 650; }
    details { margin-top: 12px; border-top: 1px solid var(--soft-line); padding-top: 11px; }
    summary { width: fit-content; color: var(--accent); cursor: pointer; font-weight: 700; font-size: .9rem; }
    .summary { display: grid; gap: 8px; margin: 12px 0; }
    .summary ul { margin: 0; padding-left: 1.1rem; }
    .detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
    .detail-item { background: var(--panel-soft); border: 1px solid var(--soft-line); border-radius: 8px; padding: 10px; font-size: .9rem; }
    .detail-item strong { display: block; margin-bottom: 3px; color: var(--ink); }
    .paper.is-hidden { display: none; }
    .keywords { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 10px; }
    .keywords button, .keywords span { border: 1px solid color-mix(in srgb, var(--accent) 30%, var(--line)); color: var(--accent); border-radius: 999px; padding: 3px 9px; font-size: .82rem; background: #effaf8; font: inherit; cursor: pointer; }
    .keywords button:hover { background: #dff5ef; }
    .side { position: sticky; top: 16px; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; box-shadow: 0 1px 2px rgb(20 32 51 / .04); }
    .trend { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
    .trend button { width: 100%; border: 0; background: transparent; display: grid; grid-template-columns: 24px minmax(0, 1fr) 32px; gap: 8px; align-items: center; padding: 3px 0; color: inherit; font: inherit; cursor: pointer; text-align: left; }
    .trend .rank { color: var(--muted); font-variant-numeric: tabular-nums; }
    .trend strong { min-width: 0; overflow-wrap: anywhere; font-size: .9rem; }
    .trend em { color: var(--accent-2); font-style: normal; font-weight: 800; text-align: right; }
    .bar { grid-column: 2 / 4; height: 5px; background: var(--soft-line); border-radius: 999px; overflow: hidden; }
    .bar i { display: block; height: 100%; width: var(--w); background: linear-gradient(90deg, var(--accent), var(--accent-2)); border-radius: inherit; }
    .pagination { display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-top: 18px; color: var(--muted); font-size: .9rem; }
    .page-buttons { display: flex; gap: 8px; }
    .pagination button { border: 1px solid var(--line); border-radius: 7px; padding: 7px 11px; background: var(--panel); color: var(--ink); font: inherit; cursor: pointer; }
    .pagination button:disabled { color: var(--muted); cursor: not-allowed; opacity: .55; }
    .pagination.is-hidden { display: none; }
    footer { color: var(--muted); padding: 24px 0; border-top: 1px solid var(--line); }
    footer .footer-inner { display: grid; gap: 8px; }
    footer strong { color: var(--ink); }
    footer a { color: var(--accent); text-decoration: none; }
    footer a:hover { text-decoration: underline; }
    footer .credit-line { margin: 0; }
    footer .license-note { margin: 0; font-size: .86rem; line-height: 1.55; max-width: 880px; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } .side { position: static; } .dash { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
    @media (max-width: 620px) { .topbar { display: grid; } .lang-toggle { justify-self: start; } .toolbar { grid-template-columns: 1fr; } .source-tabs { grid-template-columns: 1fr; } .paper-head { display: grid; } .paper-actions { justify-content: start; } .detail-grid { grid-template-columns: 1fr; } .pagination { align-items: stretch; flex-direction: column; } }
  </style>
</head>
<body>
  <header>
    <div class="wrap hero">
      <div class="topbar">
        <h1 id="site-title">PaperRadar</h1>
        <div class="lang-toggle" role="group" aria-label="Language">
          <button type="button" data-set-lang="zh" aria-pressed="true">中文</button>
          <button type="button" data-set-lang="en" aria-pressed="false">EN</button>
        </div>
      </div>
      <div class="hero-copy">
        <p class="kicker" data-lang="zh" id="source-kicker-zh">正在加载</p>
        <p class="kicker" data-lang="en" id="source-kicker-en">Loading</p>
        <p class="lede" data-lang="zh" id="description-zh">正在加载最新预印本数据...</p>
        <p class="lede" data-lang="en" id="description-en">Loading latest preprint data...</p>
        <p class="scope" data-lang="zh" id="scope-zh"></p>
        <p class="scope" data-lang="en" id="scope-en"></p>
      </div>
      <div class="dash" aria-label="Digest metrics">
        <div class="metric"><span>Total</span><strong id="metric-total">--</strong><small id="metric-date">--</small></div>
        <div class="metric"><span>arXiv</span><strong id="metric-arxiv">--</strong><small>PaperRadar-Arxiv</small></div>
        <div class="metric"><span>EarthArXiv</span><strong id="metric-eartharxiv">--</strong><small>PaperRadar-EarthArxiv</small></div>
        <div class="metric"><span>Updated</span><strong id="metric-updated">--</strong><small id="metric-generated">--</small></div>
      </div>
    </div>
  </header>
  <main class="wrap grid">
    <section>
      <div class="toolbar">
        <input class="search" id="paper-search" type="search" autocomplete="off" placeholder="Search titles, authors, keywords, subjects">
        <button class="clear-filter" type="button" id="clear-filter"><span data-lang="zh">清除</span><span data-lang="en">Clear</span></button>
      </div>
      <div class="active-filter" id="active-filter"></div>
      <div class="source-tabs" role="tablist" aria-label="Preprint source">
        <button type="button" role="tab" data-source-tab="arxiv" aria-selected="true">PaperRadar-Arxiv<small data-count="arxiv">0 papers</small></button>
        <button type="button" role="tab" data-source-tab="eartharxiv" aria-selected="false">PaperRadar-EarthArxiv<small data-count="eartharxiv">0 papers</small></button>
      </div>
      <div class="source-panel" data-source-panel="arxiv" role="tabpanel"><div class="panel-title"><h2>PaperRadar-Arxiv</h2><span data-visible-count="arxiv"></span></div><div data-paper-list="arxiv" class="empty-source">Loading...</div></div>
      <div class="source-panel" data-source-panel="eartharxiv" role="tabpanel" hidden><div class="panel-title"><h2>PaperRadar-EarthArxiv</h2><span data-visible-count="eartharxiv"></span></div><div data-paper-list="eartharxiv" class="empty-source">Loading...</div></div>
    </section>
    <aside class="side">
      <h2 data-lang="zh">关键词趋势</h2>
      <h2 data-lang="en">Keyword Trends</h2>
      <ol class="trend" id="trend-list"></ol>
    </aside>
  </main>
  <footer>
    <div class="wrap footer-inner" data-lang="zh">
      <p class="credit-line"><strong>PaperRadar</strong> © 2026 Feng Liu. 基于 arXiv 与 EarthArXiv 预印本元数据、PDF 解析结果和 LLM 辅助摘要生成。</p>
      <p class="license-note">论文版权与原始内容归作者及对应预印本平台所有；本页面仅提供研究动态索引与自动化摘要，引用和使用时请以原文为准。</p>
    </div>
    <div class="wrap footer-inner" data-lang="en">
      <p class="credit-line"><strong>PaperRadar</strong> © 2026 Feng Liu. Generated from arXiv and EarthArXiv metadata, optional PDF parsing, and LLM-assisted summaries.</p>
      <p class="license-note">Paper copyrights and source content belong to their authors and respective preprint platforms; this page is an automated research index, so please cite and verify against the original papers.</p>
    </div>
  </footer>
  <script>
    const PAGE_SIZE = __PAGE_SIZE__;
    const SOURCES = ["arxiv", "eartharxiv"];
    const SOURCE_FILES = { arxiv: "data/latest.arxiv.json", eartharxiv: "data/latest.eartharxiv.json" };
    const pageState = new Map(SOURCES.map((source) => [source, 1]));
    const digests = new Map();
    const viewState = { source: "arxiv", query: "", keyword: "" };

    const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
    const compactSentence = (value, maxChars = 260) => { const text = String(value ?? "").replace(/\\s+/g, " ").trim(); return text.length <= maxChars ? text : `${text.slice(0, maxChars - 1).trim()}...`; };
    const sourceLabel = (source) => source === "eartharxiv" ? "EarthArXiv" : "arXiv";
    const classificationLabel = (source) => source === "eartharxiv" ? "Subjects" : "Categories";
    const keywordsForLang = (analysis, lang) => lang === "zh" ? (analysis.keywords_zh || analysis.keywords_en || []) : (analysis.keywords_en || analysis.keywords_zh || []);

    const searchText = (item) => {
      const paper = item.paper || {};
      const analysis = item.analysis || {};
      return [paper.title, ...(paper.authors || []), ...(paper.categories || []), ...(analysis.keywords_en || []), ...(analysis.keywords_zh || []), analysis.one_sentence_en, analysis.one_sentence_zh, analysis.topic].join(" ").toLowerCase();
    };
    const matchesFilters = (item) => {
      const text = searchText(item);
      const queryOk = !viewState.query || text.includes(viewState.query.toLowerCase());
      const keywordOk = !viewState.keyword || text.includes(viewState.keyword.toLowerCase());
      return queryOk && keywordOk;
    };
    const filteredPapers = (source) => (digests.get(source)?.papers || []).filter(matchesFilters);

    const renderSummaryBlock = (summary) => {
      const items = Array.isArray(summary) ? summary : summary ? [summary] : [];
      const body = items.filter(Boolean).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
      return body ? `<ul>${body}</ul>` : "";
    };
    const renderAnalysisDetails = (analysis = {}) => {
      const rows = [["主要贡献", "Contribution", analysis.contribution_zh, analysis.contribution_en], ["方法", "Method", analysis.method_zh, analysis.method_en], ["数据/区域", "Data/region", analysis.data_or_region_zh, analysis.data_or_region_en], ["相关性", "Relevance", analysis.geophysics_relevance_zh, analysis.geophysics_relevance_en]];
      return `<div class="detail-grid">${rows.map(([labelZh, labelEn, valueZh, valueEn]) => {
        if (!valueZh && !valueEn) return "";
        return `<div class="detail-item"><strong data-lang="zh">${labelZh}</strong><strong data-lang="en">${labelEn}</strong><span data-lang="zh">${escapeHtml(valueZh || valueEn || "")}</span><span data-lang="en">${escapeHtml(valueEn || valueZh || "")}</span></div>`;
      }).join("")}</div>`;
    };
    const renderActions = (paper = {}) => {
      const links = [];
      if (paper.pdf_url) links.push(`<a href="${escapeHtml(paper.pdf_url)}">PDF</a>`);
      if (paper.abs_url) links.push(`<a href="${escapeHtml(paper.abs_url)}">Abstract</a>`);
      return links.join("");
    };
    const renderKeywords = (keywords = []) => keywords.map((keyword) => `<button type="button" data-keyword="${escapeHtml(keyword)}">${escapeHtml(keyword)}</button>`).join("");
    const renderPaperCard = (item, index) => {
      const paper = item.paper || {};
      const analysis = item.analysis || {};
      const source = paper.source || "arxiv";
      const authors = Array.isArray(paper.authors) ? paper.authors : [];
      let authorText = authors.slice(0, 6).join(", ");
      if (authors.length > 6) authorText += " et al.";
      const categories = Array.isArray(paper.categories) ? paper.categories.join(", ") : "";
      const actions = renderActions(paper);
      return `
        <article class="paper" data-page-item data-index="${index + 1}">
          <div class="paper-head">
            <div>
              <h3><a href="${escapeHtml(paper.abs_url || paper.pdf_url || "#")}">${escapeHtml(paper.title || "Untitled")}</a></h3>
              <p class="authors"><span class="source-badge ${source}">${sourceLabel(source)}</span> ${escapeHtml(String(paper.published || "").slice(0, 10))} · ${classificationLabel(source)}: ${escapeHtml(categories)}</p>
            </div>
            <div class="paper-actions">${actions}</div>
          </div>
          <p class="authors">${escapeHtml(authorText)}</p>
          <p class="one-line" data-lang="zh"><strong>${escapeHtml(compactSentence(analysis.one_sentence_zh || analysis.one_sentence_en || ""))}</strong></p>
          <p class="one-line" data-lang="en"><strong>${escapeHtml(compactSentence(analysis.one_sentence_en || analysis.one_sentence_zh || ""))}</strong></p>
          <div class="keywords" data-lang="zh">${renderKeywords(keywordsForLang(analysis, "zh"))}</div>
          <div class="keywords" data-lang="en">${renderKeywords(keywordsForLang(analysis, "en"))}</div>
          <details>
            <summary><span data-lang="zh">展开详细总结</span><span data-lang="en">Show details</span></summary>
            <div class="summary" data-lang="zh">${renderSummaryBlock(analysis.summary_zh || analysis.summary_en)}</div>
            <div class="summary" data-lang="en">${renderSummaryBlock(analysis.summary_en || analysis.summary_zh)}</div>
            ${renderAnalysisDetails(analysis)}
          </details>
        </article>`;
    };
    const renderPagination = () => `<nav class="pagination" data-pagination aria-label="Paper pages"><span data-lang="zh" data-page-info-zh></span><span data-lang="en" data-page-info-en></span><div class="page-buttons"><button type="button" data-page-prev data-lang="zh">上一页</button><button type="button" data-page-prev data-lang="en">Previous</button><button type="button" data-page-next data-lang="zh">下一页</button><button type="button" data-page-next data-lang="en">Next</button></div></nav>`;
    const emptySource = () => `<div class="empty-source"><span data-lang="zh">当前没有匹配论文。</span><span data-lang="en">No matching papers.</span></div>`;
    const renderSourcePanel = (source) => {
      const all = digests.get(source)?.papers || [];
      const papers = filteredPapers(source);
      const container = document.querySelector(`[data-paper-list="${source}"]`);
      const panel = document.querySelector(`[data-source-panel="${source}"]`);
      const count = document.querySelector(`[data-count="${source}"]`);
      const visible = document.querySelector(`[data-visible-count="${source}"]`);
      if (count) count.textContent = `${all.length} papers`;
      if (visible) visible.textContent = `${papers.length} / ${all.length}`;
      if (!container || !panel) return;
      container.classList.remove("empty-source", "load-error");
      container.innerHTML = papers.length ? papers.map(renderPaperCard).join("") + renderPagination() : emptySource();
      container.querySelectorAll("[data-keyword]").forEach((button) => button.addEventListener("click", () => setKeyword(button.dataset.keyword || "")));
      attachPagination(panel);
      renderPanelPage(panel);
    };
    const renderTrends = (source) => {
      const digest = digests.get(source) || digests.get("arxiv") || digests.get("eartharxiv");
      const trends = digest?.trending_keywords || [];
      const maxScore = Math.max(1, ...trends.map((item) => Number(item.score || 0)));
      const list = document.getElementById("trend-list");
      if (!list) return;
      list.innerHTML = trends.map((item, index) => {
        const score = Number(item.score || 0);
        const width = Math.max(8, Math.round((score / maxScore) * 100));
        const keyword = escapeHtml(item.keyword || "");
        return `<li><button type="button" data-trend-keyword="${keyword}"><span class="rank">${index + 1}</span><strong>${keyword}</strong><em>${escapeHtml(score)}</em><span class="bar"><i style="--w:${width}%"></i></span></button></li>`;
      }).join("");
      list.querySelectorAll("[data-trend-keyword]").forEach((button) => button.addEventListener("click", () => setKeyword(button.dataset.trendKeyword || "")));
    };
    const renderHeader = () => {
      const primary = digests.get("arxiv") || digests.get("eartharxiv");
      if (!primary) return;
      const config = primary.config || {};
      const counts = Object.fromEntries(SOURCES.map((source) => [source, (digests.get(source)?.papers || []).length]));
      const allPapers = counts.arxiv + counts.eartharxiv;
      document.title = `${config.site_title || "PaperRadar"} | ${primary.date || ""}`;
      document.getElementById("site-title").textContent = config.site_title || "PaperRadar";
      document.getElementById("metric-total").textContent = allPapers;
      document.getElementById("metric-arxiv").textContent = counts.arxiv;
      document.getElementById("metric-eartharxiv").textContent = counts.eartharxiv;
      document.getElementById("metric-date").textContent = primary.date || "--";
      document.getElementById("metric-updated").textContent = primary.generated_at ? primary.generated_at.slice(0, 10) : "--";
      document.getElementById("metric-generated").textContent = primary.generated_at || "--";
      updateHero(viewState.source || "arxiv");
    };
    const updateHero = (source) => {
      const digest = digests.get(source) || digests.get("arxiv") || digests.get("eartharxiv");
      if (!digest) return;
      const config = digest.config || {};
      const count = (digest.papers || []).length;
      const topicCount = digest.trending_keywords?.length || 0;
      const label = sourceLabel(source);
      document.getElementById("source-kicker-zh").textContent = source === "eartharxiv" ? "EarthArXiv 预印本动态" : "arXiv 预印本动态";
      document.getElementById("source-kicker-en").textContent = `${label} preprint signal`;
      document.getElementById("description-zh").textContent = source === "eartharxiv"
        ? `聚焦 EarthArXiv 地球科学预印本：自动整理 ${count} 篇新近论文，提炼一句话摘要、研究细节与关键词趋势。`
        : `聚焦 arXiv 配置主题：自动整理 ${count} 篇新近论文，快速看清方法、数据区域、核心贡献和研究趋势。`;
      document.getElementById("description-en").textContent = source === "eartharxiv"
        ? `A focused EarthArXiv digest with ${count} recent preprints, concise summaries, research details, and keyword trends.`
        : `A focused arXiv digest with ${count} recent preprints, surfacing methods, regions, contributions, and keyword trends.`;
      const [scopeZh, scopeEn] = renderScope(source, config, topicCount);
      document.getElementById("scope-zh").innerHTML = scopeZh;
      document.getElementById("scope-en").innerHTML = scopeEn;
    };
    const renderScope = (source, config = {}, topicCount = 0) => {
      const arxiv = config.arxiv || {};
      const earth = config.eartharxiv || {};
      if (source === "eartharxiv") {
        const subjects = (earth.subjects || []).slice(0, 8).join(", ") || "configured EarthArXiv subjects";
        return [
          `当前来源: <strong>EarthArXiv</strong> · Subjects: ${escapeHtml(subjects)} · 关键词趋势: ${topicCount}`,
          `Current source: <strong>EarthArXiv</strong> · Subjects: ${escapeHtml(subjects)} · Keyword trends: ${topicCount}`,
        ];
      }
      const categories = (arxiv.categories || []).join(", ") || "configured arXiv categories";
      const terms = [...(arxiv.extra_terms || []), ...(arxiv.keywords || [])].filter(Boolean);
      const topicTerms = terms.slice(0, 8).join(", ") || "configured terms";
      if (arxiv.query) {
        return [
          `当前来源: <strong>arXiv</strong> · Query: ${escapeHtml(arxiv.query)} · 关键词趋势: ${topicCount}`,
          `Current source: <strong>arXiv</strong> · Query: ${escapeHtml(arxiv.query)} · Keyword trends: ${topicCount}`,
        ];
      }
      return [
        `当前来源: <strong>arXiv</strong> · Categories: ${escapeHtml(categories)} · 主题词: ${escapeHtml(topicTerms)} · 关键词趋势: ${topicCount}`,
        `Current source: <strong>arXiv</strong> · Categories: ${escapeHtml(categories)} · Topic terms: ${escapeHtml(topicTerms)} · Keyword trends: ${topicCount}`,
      ];
    };
    const attachPagination = (panel) => {
      panel.querySelectorAll("[data-page-prev]").forEach((button) => { button.onclick = () => { const source = panel.dataset.sourcePanel; pageState.set(source, Math.max(1, (pageState.get(source) || 1) - 1)); renderPanelPage(panel); }; });
      panel.querySelectorAll("[data-page-next]").forEach((button) => { button.onclick = () => { const source = panel.dataset.sourcePanel; pageState.set(source, (pageState.get(source) || 1) + 1); renderPanelPage(panel); }; });
    };
    const renderPanelPage = (panel) => {
      const source = panel.dataset.sourcePanel;
      const papers = Array.from(panel.querySelectorAll("[data-page-item]"));
      const totalPages = Math.max(1, Math.ceil(papers.length / PAGE_SIZE));
      const currentPage = Math.min(pageState.get(source) || 1, totalPages);
      pageState.set(source, currentPage);
      papers.forEach((paper, index) => paper.classList.toggle("is-hidden", Math.floor(index / PAGE_SIZE) + 1 !== currentPage));
      const pagination = panel.querySelector("[data-pagination]");
      const infoZh = panel.querySelector("[data-page-info-zh]");
      const infoEn = panel.querySelector("[data-page-info-en]");
      if (infoZh) infoZh.textContent = `第 ${currentPage} / ${totalPages} 页，每页最多 ${PAGE_SIZE} 篇`;
      if (infoEn) infoEn.textContent = `Page ${currentPage} of ${totalPages}, up to ${PAGE_SIZE} papers per page`;
      panel.querySelectorAll("[data-page-prev]").forEach((button) => button.disabled = currentPage <= 1);
      panel.querySelectorAll("[data-page-next]").forEach((button) => button.disabled = currentPage >= totalPages);
      if (pagination) pagination.classList.toggle("is-hidden", totalPages <= 1 || papers.length === 0);
    };
    const refreshPanels = () => { SOURCES.forEach((source) => { pageState.set(source, 1); renderSourcePanel(source); }); renderActiveFilter(); activate(viewState.source); };
    const setKeyword = (keyword) => { viewState.keyword = keyword; refreshPanels(); };
    const renderActiveFilter = () => {
      const node = document.getElementById("active-filter");
      if (!node) return;
      const parts = [];
      if (viewState.query) parts.push(`search: <strong>${escapeHtml(viewState.query)}</strong>`);
      if (viewState.keyword) parts.push(`keyword: <strong>${escapeHtml(viewState.keyword)}</strong>`);
      node.innerHTML = parts.join(" · ");
    };
    const activate = (source) => {
      viewState.source = source;
      document.querySelectorAll("[data-source-tab]").forEach((tab) => tab.setAttribute("aria-selected", String(tab.dataset.sourceTab === source)));
      document.querySelectorAll("[data-source-panel]").forEach((panel) => { const active = panel.dataset.sourcePanel === source; panel.hidden = !active; if (active) renderPanelPage(panel); });
      renderTrends(source);
      updateHero(source);
      localStorage.setItem("paperradar.source", source);
    };
    const setLanguage = (lang) => { const root = document.documentElement; root.dataset.lang = lang; root.lang = lang === "zh" ? "zh-CN" : "en"; localStorage.setItem("paperradar.lang", lang); document.querySelectorAll("[data-set-lang]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.setLang === lang))); };
    const loadDigest = async (source) => { const response = await fetch(SOURCE_FILES[source], { cache: "no-store" }); if (!response.ok) throw new Error(`${source} ${response.status}`); return response.json(); };
    const showLoadError = (source, error) => { const container = document.querySelector(`[data-paper-list="${source}"]`); if (!container) return; container.className = "load-error"; container.textContent = `Failed to load ${SOURCE_FILES[source]}: ${error.message}`; };

    document.querySelectorAll("[data-set-lang]").forEach((button) => button.addEventListener("click", () => setLanguage(button.dataset.setLang)));
    document.querySelectorAll("[data-source-tab]").forEach((tab) => tab.addEventListener("click", () => activate(tab.dataset.sourceTab)));
    document.getElementById("paper-search").addEventListener("input", (event) => { viewState.query = event.target.value.trim(); refreshPanels(); });
    document.getElementById("clear-filter").addEventListener("click", () => { viewState.query = ""; viewState.keyword = ""; document.getElementById("paper-search").value = ""; refreshPanels(); });
    setLanguage(localStorage.getItem("paperradar.lang") === "en" ? "en" : "zh");

    (async () => {
      await Promise.all(SOURCES.map(async (source) => { try { digests.set(source, await loadDigest(source)); } catch (error) { showLoadError(source, error); } }));
      renderHeader();
      SOURCES.forEach(renderSourcePanel);
      const saved = localStorage.getItem("paperradar.source");
      activate(SOURCES.includes(saved) ? saved : "arxiv");
    })();
  </script>
</body>
</html>
""".replace("__PAGE_SIZE__", str(PAPERS_PER_PAGE))

def _source_counts(papers: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"arxiv": 0, "eartharxiv": 0}
    for item in papers:
        source = item.get("paper", {}).get("source") or "arxiv"
        counts[source] = counts.get(source, 0) + 1
    return counts


def _source_label(source: str) -> str:
    return "EarthArXiv" if source == "eartharxiv" else "arXiv"


def _source_title(source: str) -> str:
    if source == "eartharxiv":
        return "PaperRadar-EarthArxiv"
    return "PaperRadar-Arxiv"


def _render_source_tabs(counts: dict[str, int]) -> str:
    buttons = []
    for source in ["arxiv", "eartharxiv"]:
        selected = "true" if source == "arxiv" else "false"
        label = _source_title(source)
        count = counts.get(source, 0)
        buttons.append(
            f'<button type="button" role="tab" data-source-tab="{source}" aria-selected="{selected}">'
            f'{_e(label)}<small>{count} papers</small></button>'
        )
    return '<div class="source-tabs" role="tablist" aria-label="Preprint source">' + "".join(buttons) + "</div>"


def _render_source_panels(papers: list[dict[str, Any]]) -> str:
    grouped = {"arxiv": [], "eartharxiv": []}
    for item in papers:
        source = item.get("paper", {}).get("source") or "arxiv"
        grouped.setdefault(source, []).append(item)
    panels = []
    for source in ["arxiv", "eartharxiv"]:
        items = grouped.get(source, [])
        cards = "\n".join(_render_paper_card(item, index) for index, item in enumerate(items))
        hidden = "" if source == "arxiv" else " hidden"
        if not items:
            cards = (
                '<div class="empty-source">'
                '<span data-lang="zh">当前还没有这个来源的论文。下一次自动更新发现新内容后会显示在这里。</span>'
                '<span data-lang="en">No papers from this source yet. New items will appear here after an automated update finds them.</span>'
                '</div>'
            )
        panels.append(
            f'<div class="source-panel" data-source-panel="{source}" role="tabpanel"{hidden}>'
            f'<h2>{_e(_source_title(source))}</h2>'
            f'{cards}'
            f'{_render_pagination()}'
            '</div>'
        )
    return "\n".join(panels)


def _render_pagination() -> str:
    return """
      <nav class="pagination" data-pagination aria-label="Paper pages">
        <span data-lang="zh" data-page-info-zh></span>
        <span data-lang="en" data-page-info-en></span>
        <div class="page-buttons">
          <button type="button" data-page-prev data-lang="zh">上一页</button>
          <button type="button" data-page-prev data-lang="en">Previous</button>
          <button type="button" data-page-next data-lang="zh">下一页</button>
          <button type="button" data-page-next data-lang="en">Next</button>
        </div>
      </nav>
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
    source = paper.get("source") or "arxiv"
    source_badge = f'<span class="source-badge">{_e(_source_label(source))}</span>'
    one_sentence_zh = _compact_sentence(analysis.get("one_sentence_zh") or "")
    one_sentence_en = _compact_sentence(analysis.get("one_sentence_en") or "")
    summary_zh = _render_summary_block(analysis.get("summary_zh"))
    summary_en = _render_summary_block(analysis.get("summary_en"))
    details = _render_analysis_details(analysis)
    return f"""
<article class="paper" data-page-item data-index="{index + 1}">
  <h3><a href="{_e(paper['abs_url'])}">{_e(paper['title'])}</a></h3>
  <p class="authors">{source_badge}{_e(authors)} · {_e(paper['published'][:10])} · {_e(_classification_label(source))}: {_e(', '.join(paper['categories']))}</p>
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


def _classification_label(source: str) -> str:
    return "Subjects" if source == "eartharxiv" else "Categories"


def _render_scope_text(config: dict[str, Any]) -> tuple[str, str]:
    arxiv_config = config.get("arxiv", {})
    eartharxiv_config = config.get("eartharxiv", {})
    query = arxiv_config.get("query") or ""
    arxiv_categories = arxiv_config.get("categories") or []
    arxiv_terms = [
        str(term)
        for term in [*(arxiv_config.get("extra_terms") or []), *(arxiv_config.get("keywords") or [])]
        if term
    ]
    earth_subjects = eartharxiv_config.get("subjects") or []
    earth_keywords = [str(term) for term in eartharxiv_config.get("keywords") or [] if term]

    if query:
        arxiv_part_zh = f'arXiv query: <strong>{_e(query)}</strong>'
        arxiv_part_en = f'arXiv query: <strong>{_e(query)}</strong>'
    else:
        arxiv_category_text = ", ".join(str(category) for category in arxiv_categories) or "all configured categories"
        arxiv_part_zh = f'arXiv categories: <strong>{_e(arxiv_category_text)}</strong>'
        arxiv_part_en = f'arXiv categories: <strong>{_e(arxiv_category_text)}</strong>'
        if arxiv_terms:
            terms = ", ".join(arxiv_terms[:8])
            suffix = " ..." if len(arxiv_terms) > 8 else ""
            arxiv_part_zh += f'; 主题词: {_e(terms)}{suffix}'
            arxiv_part_en += f'; topic terms: {_e(terms)}{suffix}'

    parts_zh = [arxiv_part_zh]
    parts_en = [arxiv_part_en]
    if eartharxiv_config.get("enabled"):
        subject_text = ", ".join(str(subject) for subject in earth_subjects) or "all configured subjects"
        earth_part_zh = f'EarthArXiv subjects: <strong>{_e(subject_text)}</strong>'
        earth_part_en = f'EarthArXiv subjects: <strong>{_e(subject_text)}</strong>'
        if earth_keywords:
            terms = ", ".join(earth_keywords[:8])
            suffix = " ..." if len(earth_keywords) > 8 else ""
            earth_part_zh += f'; 关键词: {_e(terms)}{suffix}'
            earth_part_en += f'; keywords: {_e(terms)}{suffix}'
        parts_zh.append(earth_part_zh)
        parts_en.append(earth_part_en)

    return (
        '当前追踪范围: ' + ' | '.join(parts_zh),
        'Current scope: ' + ' | '.join(parts_en),
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
            f'<a href="{_e(pdf_url)}">PDF</a>'
            '</p>'
        )
    if error:
        return (
            '<p class="authors" data-lang="zh">PDF 下载待处理: '
            f"{_e(error)} · "
            f'<a href="{_e(pdf_url)}">PDF</a></p>'
            '<p class="authors" data-lang="en">PDF download pending: '
            f"{_e(error)} · "
            f'<a href="{_e(pdf_url)}">PDF</a></p>'
        )
    return ""


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)
