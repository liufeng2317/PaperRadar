from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from typing import Any

from paperradar.arxiv_client import Paper


ANALYSIS_SCHEMA_VERSION = "paperradar.analysis.v3"
ANALYSIS_INPUT_VERSION = "markdown-clean-v1"

STOPWORDS = {
    "about",
    "after",
    "analysis",
    "based",
    "between",
    "from",
    "into",
    "model",
    "models",
    "observations",
    "paper",
    "results",
    "show",
    "shows",
    "study",
    "that",
    "the",
    "their",
    "this",
    "using",
    "with",
}

BAD_KEYWORDS = {
    "alpha",
    "beta",
    "delta",
    "gamma",
    "lambda",
    "mathbb",
    "mathbf",
    "mathcal",
    "mathrm",
    "nabla",
    "omega",
    "partial",
    "sigma",
    "theta",
    "times",
    "varepsilon",
}


def enrich_paper(
    paper: Paper,
    keywords_per_paper: int = 5,
    markdown_excerpt: str = "",
) -> dict[str, Any]:
    source = "markdown" if markdown_excerpt else "abstract"
    if _first_env("LLM_API_KEY", "OPENAI_API_KEY", "OPEN_API_KEY", "PJLAB_API_KEY"):
        try:
            return _enrich_with_llm(
                paper,
                keywords_per_paper,
                markdown_excerpt=markdown_excerpt,
                source=source,
            )
        except Exception as exc:
            fallback = _fallback_enrichment(paper, keywords_per_paper, markdown_excerpt=markdown_excerpt)
            fallback["llm_error"] = str(exc)
            return fallback
    return _fallback_enrichment(paper, keywords_per_paper, markdown_excerpt=markdown_excerpt)


def _enrich_with_llm(
    paper: Paper,
    keywords_per_paper: int,
    markdown_excerpt: str = "",
    source: str = "abstract",
) -> dict[str, Any]:
    api_key = _first_env("LLM_API_KEY", "OPENAI_API_KEY", "OPEN_API_KEY", "PJLAB_API_KEY")
    base_url = _first_env(
        "LLM_BASE_URL", "OPENAI_BASE_URL", "PJLAB_API_BASE_URL", default="https://api.openai.com/v1"
    ).rstrip("/")
    model = _first_env("LLM_MODEL", "OPENAI_MODEL", "PJLAB_API_CHAT_MODEL", default="gpt-4o-mini")
    prompt = f"""
Return strict JSON for this arXiv paper for a concise research digest. Base the answer primarily on the parsed PDF Markdown excerpt when it is available; otherwise use the abstract. Avoid copying long text verbatim.

Quality rules:
- Write for a scientific reader who wants to quickly decide whether to open the paper.
- Do not output Markdown, headings, citations, author affiliations, equations, or raw LaTeX.
- The one-sentence summary must be one complete sentence, not a title or abstract excerpt.
- English one-sentence summary: at most 35 words.
- Chinese one-sentence summary: at most 80 Chinese characters.
- The 3 summary bullets must be exactly: problem, approach, key result. If a key result is not stated, say what is evaluated or proposed instead of inventing numbers.
- Keywords must correctly describe the paper's core scientific content: target phenomenon, method, dataset/instrument, region/application, or main technical idea.
- Prefer specific terms that would help a researcher find related work. Single-word keywords are allowed when they are domain-specific, such as InSAR, DAS, seismicity, permafrost, or interferometry.
- Do not use formula fragments, variables, LaTeX commands, or generic research words as keywords. Bad examples: mathcal, mathbb, mathbf, nabla, omega, times, partial, model, data, method, learning, result.
- If the paper is only tangentially related to the configured digest topic, still summarize the paper accurately and note that the relevance is tangential.

Required schema:
{{
  "one_sentence_en": "one plain-language sentence in English",
  "one_sentence_zh": "one plain-language sentence in Simplified Chinese",
  "summary_en": ["3 bullet-like English strings: problem, approach, key result"],
  "summary_zh": ["3 bullet-like Simplified Chinese strings: problem, approach, key result"],
  "contribution_en": "main scientific or technical contribution in English",
  "contribution_zh": "main scientific or technical contribution in Simplified Chinese",
  "method_en": "main method, model, instrument, data, or workflow in English",
  "method_zh": "main method, model, instrument, data, or workflow in Simplified Chinese",
  "data_or_region_en": "study region, dataset, simulation setup, or observation source; use 'Not specified' if absent",
  "data_or_region_zh": "研究区域、数据集、模拟设置或观测来源；如果未说明则写'未说明'",
  "geophysics_relevance_en": "why this matters for the tracked scientific topic; if tangential, say so",
  "geophysics_relevance_zh": "为什么这对当前追踪主题重要；如果只是弱相关，请说明",
  "keywords_en": ["exactly {keywords_per_paper} short English keywords"],
  "keywords_zh": ["exactly {keywords_per_paper} short Simplified Chinese keywords"],
  "topic": "one short English topic label, 2 to 4 words",
  "audience_level": "specialist or broad"
}}

Title: {paper.title}
Authors: {", ".join(paper.authors)}
Categories: {", ".join(paper.categories)}
Abstract: {paper.abstract}
Markdown excerpt from parsed PDF, if available:
{markdown_excerpt or "(not available; use the abstract)"}
""".strip()
    payload = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "You summarize arXiv research accurately for a concise bilingual scientific digest.",
            },
            {"role": "user", "content": prompt},
        ],
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM API returned HTTP {exc.code}: {body[:500]}") from exc

    content = raw["choices"][0]["message"]["content"]
    enriched = json.loads(content)
    return _normalize_enrichment(
        enriched,
        keywords_per_paper,
        source=source,
        model=model,
    )


def _fallback_enrichment(
    paper: Paper,
    keywords_per_paper: int,
    markdown_excerpt: str = "",
) -> dict[str, Any]:
    source_text = paper.abstract or _extract_abstract_like_text(markdown_excerpt) or paper.title
    sentences = _clean_fallback_sentences(source_text)
    summary_en = sentences[0] if sentences else paper.title
    keywords = _extract_keywords(f"{paper.title} {source_text}", keywords_per_paper)
    return {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "input_version": ANALYSIS_INPUT_VERSION,
        "one_sentence_en": summary_en,
        "one_sentence_zh": "未配置可用 LLM；当前显示规则摘要。",
        "summary_en": sentences[:3] or [summary_en],
        "summary_zh": ["未配置 LLM_API_KEY；当前显示英文规则摘要。配置 LLM 后将生成中文摘要。"],
        "contribution_en": "",
        "contribution_zh": "",
        "method_en": "",
        "method_zh": "",
        "data_or_region_en": "",
        "data_or_region_zh": "",
        "geophysics_relevance_en": "",
        "geophysics_relevance_zh": "",
        "keywords_en": keywords,
        "keywords_zh": keywords,
        "topic": keywords[0] if keywords else "geophysics",
        "audience_level": "specialist",
        "llm_used": False,
        "source": "markdown" if markdown_excerpt else "abstract",
    }


def _normalize_enrichment(
    raw: dict[str, Any],
    keywords_per_paper: int,
    source: str,
    model: str,
) -> dict[str, Any]:
    keywords_en = _coerce_keywords(raw.get("keywords_en"), keywords_per_paper)
    keywords_zh = _coerce_keywords(raw.get("keywords_zh"), keywords_per_paper)
    return {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "input_version": ANALYSIS_INPUT_VERSION,
        "one_sentence_en": str(raw.get("one_sentence_en", "")).strip(),
        "one_sentence_zh": str(raw.get("one_sentence_zh", "")).strip(),
        "summary_en": _coerce_string_list(raw.get("summary_en"), limit=3),
        "summary_zh": _coerce_string_list(raw.get("summary_zh"), limit=3),
        "contribution_en": str(raw.get("contribution_en", "")).strip(),
        "contribution_zh": str(raw.get("contribution_zh", "")).strip(),
        "method_en": str(raw.get("method_en", "")).strip(),
        "method_zh": str(raw.get("method_zh", "")).strip(),
        "data_or_region_en": str(raw.get("data_or_region_en", "")).strip(),
        "data_or_region_zh": str(raw.get("data_or_region_zh", "")).strip(),
        "geophysics_relevance_en": str(raw.get("geophysics_relevance_en", "")).strip(),
        "geophysics_relevance_zh": str(raw.get("geophysics_relevance_zh", "")).strip(),
        "keywords_en": keywords_en,
        "keywords_zh": keywords_zh,
        "topic": str(raw.get("topic", keywords_en[0] if keywords_en else "geophysics")).strip(),
        "audience_level": str(raw.get("audience_level", "specialist")).strip(),
        "llm_used": True,
        "source": source,
        "model": model,
    }


def _coerce_keywords(value: Any, limit: int) -> list[str]:
    if isinstance(value, str):
        items = re.split(r"[,;，；]", value)
    elif isinstance(value, list):
        items = value
    else:
        items = []
    cleaned = []
    for item in items:
        keyword = _clean_keyword(str(item))
        if keyword and keyword.lower() not in {k.lower() for k in cleaned}:
            cleaned.append(keyword)
    return cleaned[:limit]


def _coerce_string_list(value: Any, limit: int) -> list[str]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = re.split(r"\n+|(?<=[.!?。！？])\s+", value)
    else:
        items = []
    cleaned = [str(item).strip(" -•\t") for item in items if str(item).strip(" -•\t")]
    return cleaned[:limit]


def _extract_keywords(text: str, limit: int) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z-]{3,}", text.lower())
    counts = Counter(token for token in tokens if token not in STOPWORDS and token not in BAD_KEYWORDS)
    return [word for word, _ in counts.most_common(limit)]


def _clean_keyword(value: str) -> str:
    keyword = " ".join(value.replace("_", " ").split()).strip(" -•\t.,;:()[]{}")
    lowered = keyword.lower()
    if not keyword or lowered in STOPWORDS or lowered in BAD_KEYWORDS:
        return ""
    if re.search(r"\\|[{}^_=]", keyword):
        return ""
    if len(keyword) < 3:
        return ""
    return keyword


def _extract_abstract_like_text(markdown: str) -> str:
    if not markdown:
        return ""
    match = re.search(r"(?is)#?\s*abstract\s*\n+(.*?)(?:\n\s*#{1,6}\s+\S|\Z)", markdown)
    if match:
        return _strip_markdown_noise(match.group(1))
    return _strip_markdown_noise(markdown)


def _strip_markdown_noise(text: str) -> str:
    text = re.sub(r"(?m)^\s*#{1,6}\s+.*$", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\$[^$]+\$", " ", text)
    text = re.sub(r"\\[A-Za-z]+", " ", text)
    return " ".join(text.split())


def _clean_fallback_sentences(text: str) -> list[str]:
    text = _strip_markdown_noise(text)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    cleaned = []
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 40:
            continue
        if sentence.lower().startswith(("abstract", "introduction")):
            continue
        cleaned.append(sentence)
    return cleaned


def _first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default
