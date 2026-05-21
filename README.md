# PaperRadar

[中文文档](docs/README.zh.md)

PaperRadar is a configurable arXiv paper radar. It tracks topics you care about, downloads paper metadata and PDFs, optionally parses PDFs with MinerU, summarizes papers with an LLM, ranks keyword trends, and publishes a bilingual static digest through GitHub Pages.

The default configuration currently tracks `physics.geo-ph` with geophysics-related topic terms. The project itself is domain-agnostic: change `config/default.json` to monitor other arXiv categories, keywords, authors, or a custom query.

## Features

- Fetch recent arXiv papers from configured categories, keywords, authors, or raw queries.
- Cache PDFs locally without re-downloading existing files.
- Parse PDFs into Markdown with the bundled MinerU integration.
- Summarize papers in English and Chinese with an OpenAI-compatible LLM.
- Extract per-paper keywords and rank daily trending keywords.
- Render a static GitHub Pages site from `docs/`.
- Use an incremental registry so existing PDFs, Markdown, and summaries are skipped.

## Quick Start

```bash
python -m paperradar.cli run
```

The convenience wrapper uses `python` by default. Set `PAPERRADAR_PYTHON` when you want a specific environment, for example one that has MinerU installed:

```bash
bash scripts/run_daily.sh
```

Main outputs:

- `data/daily/YYYY-MM-DD.json`: daily digest JSON
- `docs/index.html`: GitHub Pages HTML page
- `docs/data/latest.json`: latest public page data
- `data/pdfs/`, `data/markdown/`, `data/mineru/`: local caches, ignored by git
- `data/paper_registry.json`: local management registry, ignored by git

## Configuration

Edit `config/default.json`:

```json
{
  "arxiv": {
    "categories": ["physics.geo-ph"],
    "extra_terms": ["geophysics", "seismology", "geodesy", "geodynamics", "geomagnetism"],
    "keywords": [],
    "authors": [],
    "max_results": 100,
    "lookback_days": 7,
    "download_pdfs": true,
    "parse_pdfs": true,
    "storage_category_policy": "configured"
  }
}
```

Leave `query` empty to let PaperRadar build a query from the structured fields above. Set `query` only when you want to fully override the generated arXiv query.

`storage_category_policy` controls local cache folders:

- `configured`: use the first configured category folder when `categories` is non-empty.
- `matched`: use a configured category only if the paper metadata contains it.
- any other value: use the paper's primary arXiv category.

## Secrets And `.env`

Copy `.env.example` to `.env` for local runs:

```bash
cp .env.example .env
```

Common variables:

```bash
LLM_API_KEY=...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
HTTP_PROXY=http://user:password@host:port
HTTPS_PROXY=http://user:password@host:port
MINERU_API_KEY=...
MINERU_API_BASE=...
```

Never commit `.env`. It is ignored by git.

## GitHub Pages

1. Push the repository to GitHub.
2. In repository settings, enable Pages from branch `main`, folder `/docs`.
3. Add `LLM_API_KEY` as an Actions secret if you want GitHub Actions to call an LLM.
4. Add `LLM_BASE_URL` and `LLM_MODEL` as Actions variables when needed.
5. The workflow `.github/workflows/daily.yml` runs daily and commits updated `data/` and `docs/` outputs.

Note: full PDF parsing with MinerU is usually better on a local/server environment where MinerU credentials and dependencies are already configured. GitHub Actions can still publish the generated `docs/` page, but it may need extra setup for MinerU.

## Local Commands

```bash
python -m paperradar.cli fetch
python -m paperradar.cli run --date 2026-05-21
python -m paperradar.cli render --input data/daily/2026-05-21.json
python -m paperradar.cli reanalyze --input data/daily/2026-05-21.json
python -m paperradar.cli registry --query seismic
python -m paperradar.cli migrate-storage
```

Wrapper examples:

```bash
bash scripts/run_daily.sh
bash scripts/run_daily.sh run --limit 3
bash scripts/run_daily.sh reanalyze --input data/daily/2026-05-21.json
bash scripts/run_daily.sh registry --query seismic
bash scripts/run_daily.sh migrate-storage
```

## What Should Not Be Uploaded

The repository is configured to ignore local secrets and heavy/generated private caches:

- `.env`
- `data/pdfs/`
- `data/mineru/`
- `data/markdown/`
- `data/paper_registry.json`
- `data/quarantine/`
- `data/smoke/`
- `docs_smoke/`
- `logs/`
- `pkg/`
- Python/build caches

The public site files under `docs/` are intended to be committed.
