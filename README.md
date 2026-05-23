# PaperRadar

<p align="center">
  <strong>Track, summarize, and publish preprint intelligence from arXiv and EarthArXiv.</strong>
</p>

<p align="center">
  <a href="docs/README.zh.md">中文文档</a> ·
  <a href="docs/index.html">GitHub Pages site</a> ·
  <a href="config/default.json">Configuration</a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="Sources" src="https://img.shields.io/badge/Sources-arXiv%20%7C%20EarthArXiv-0f766e?style=flat-square">
  <img alt="LLM" src="https://img.shields.io/badge/LLM-OpenAI--compatible-8b5cf6?style=flat-square">
  <img alt="Pages" src="https://img.shields.io/badge/Publish-GitHub%20Pages-111827?style=flat-square&logo=github">
</p>

PaperRadar is a lightweight preprint intelligence pipeline. It watches the research topics you care about, always fetches metadata and abstracts, can optionally download PDFs, can optionally parse PDFs into Markdown with MinerU, asks an OpenAI-compatible LLM for bilingual summaries, ranks keyword trends, and publishes a clean static digest through GitHub Pages.

The default setup tracks geophysics-related work across `arXiv` and `EarthArXiv`, but the project is source-aware and domain-agnostic: change `config/default.json` to follow other arXiv categories, EarthArXiv subjects, keywords, authors, or custom queries.

## Why It Exists

Research updates should feel like a radar screen, not a pile of tabs. PaperRadar is designed for:

- catching new preprints before they disappear into the feed;
- keeping PDFs, parsed Markdown, LLM summaries, and public JSON in a reproducible local archive;
- publishing a bilingual web digest without running a backend server;
- supporting both arXiv categories and EarthArXiv subjects without mixing their taxonomies;
- running incrementally so existing PDFs, Markdown, and summaries are reused.

## What You Get

| Layer | Output |
| --- | --- |
| Discovery | arXiv API plus EarthArXiv OAI-PMH metadata feed |
| Storage | Source-aware daily JSON, optional PDF cache, optional Markdown/MinerU cache |
| Understanding | English and Chinese LLM summaries from parsed Markdown when available, otherwise from abstracts |
| Trends | Per-paper keywords plus ranked keyword trends |
| Publishing | `docs/index.html` loads `docs/data/latest.*.json` at runtime |
| Automation | Server loop, git push, optional Chinese email digest |

## Data Flow

```text
arXiv categories / custom query      EarthArXiv subjects
              │                       │
              └──────── fetch metadata + abstracts ────────┐
                                      │                    │
                                      │                    ├─ if download_pdfs=false
                                      │                    │      skip local PDF archive
                                      │                    │
                                      ├─ if download_pdfs=true
                                      │  save PDFs under data/pdfs/
                                      │
                                      ├─ if parse_pdfs=true and PDF exists
                                      │      MinerU parse -> Markdown under data/markdown/
                                      │
                                      └─ LLM input
                                             ├─ Markdown when available
                                             └─ abstract fallback otherwise
                                                   │
                                      bilingual summaries + keyword trends
                                                   │
                               data/daily/<source>/YYYY-MM-DD.json
                                                   │
                                     docs/data/latest.*.json
                                                   │
                                           GitHub Pages UI
```

## Quick Start

```bash
python -m paperradar.cli run
```

Or use the wrapper script:

```bash
bash scripts/run_daily.sh
```

Use the Python environment that contains MinerU dependencies:

```bash
PAPERRADAR_PYTHON=/path/to/python bash scripts/run_daily.sh
```

For a dedicated server environment, point `PAPERRADAR_PYTHON` to the Python executable that has the required dependencies:

```bash
PAPERRADAR_PYTHON=/path/to/conda/env/bin/python bash scripts/run_daily.sh
```

Use the lightweight mode when MinerU is not installed. This mode still fetches metadata and abstracts, downloads PDFs when enabled, and calls the LLM, but summaries are generated from abstracts instead of parsed Markdown:

```bash
bash scripts/run_daily.sh --config config/light.json
```

## Configuration

Edit `config/default.json`.

```json
{
  "arxiv": {
    "categories": ["physics.geo-ph"],
    "extra_terms": ["geophysics", "seismology", "geodesy", "geodynamics", "geomagnetism"],
    "max_results": 100,
    "lookback_days": 7,
    "download_pdfs": true,
    "parse_pdfs": true
  },
  "eartharxiv": {
    "enabled": true,
    "subjects": ["Geophysics and Seismology", "Hydrology", "Glaciology"],
    "lookback_days": 7,
    "max_results": 25
  },
  "public_lookback_days": 60
}
```

Notes:

- Leave `arxiv.query` empty to let PaperRadar build a query from structured fields.
- Set `arxiv.query` only when you want to fully override the generated arXiv query.
- `arxiv.categories` are arXiv taxonomy values such as `physics.geo-ph`.
- `eartharxiv.subjects` are EarthArXiv subjects such as `Geophysics and Seismology`.
- `lookback_days` controls fetch windows; `public_lookback_days` controls the public page window.
- `arxiv.download_pdfs=false` skips local PDF archiving while keeping metadata, abstracts, links, LLM summaries, trends, and the web page.
- `arxiv.parse_pdfs=false` skips MinerU and summarizes from abstracts.
- `config/light.json` is the ready-to-use no-MinerU profile: PDF download remains enabled, PDF parsing is disabled.

## Outputs

```text
docs/index.html                                  static UI shell
docs/data/latest.json                            aggregated public data
docs/data/latest.arxiv.json                      arXiv-only public data
docs/data/latest.eartharxiv.json                 EarthArXiv-only public data

data/daily/<source>/YYYY-MM-DD.json              source-specific daily digests
data/daily/public/YYYY-MM-DD.json                aggregated public daily digests

data/pdfs/<source>/<category-or-subject>/<day>/  cached PDFs
data/markdown/<source>/<category-or-subject>/<day>/ parsed Markdown
data/mineru/<source>/<category-or-subject>/<day>/   MinerU raw outputs
```

`docs/index.html` does not bake paper content into HTML. It loads the JSON files in `docs/data/`, so the page updates when the JSON updates.

## Environment

Create a local `.env` from the example:

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

# Optional, only required when arxiv.parse_pdfs=true
MINERU_API_KEY=...
MINERU_API_BASE=...
```

Optional email delivery:

```bash
PAPERRADAR_EMAIL_ENABLED=1
PAPERRADAR_EMAIL_TO=your-email@example.com
PAPERRADAR_EMAIL_FROM=PaperRadar <your-email@example.com>
PAPERRADAR_SITE_URL=https://your-user.github.io/PaperRadar/

SMTP_HOST=smtp.qq.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=your-email@example.com
SMTP_PASSWORD=your-smtp-app-password
```

## GitHub Pages

1. Push the repository to GitHub.
2. Enable Pages from branch `main`, folder `/docs`.
3. Run PaperRadar on your server or local machine.
4. Commit and push `data/daily` plus `docs/data` updates.

MinerU parsing is optional. Without MinerU, use `config/light.json` to publish an abstract-based digest. Full PDF parsing is usually better on a machine where MinerU credentials and dependencies are already configured. GitHub-hosted Actions can publish the static page, but full PDF parsing is better kept on your own server.

## Automation

Run once and push updates:

```bash
bash scripts/server_daily_push.sh
```

Run every 8 hours anchored at 11:20 server time:

```bash
PAPERRADAR_PYTHON=/path/to/python nohup bash scripts/server_daily_loop.sh --run-at 11:20 --interval-hours 8 >> logs/daily/scheduler.nohup.log 2>&1 &
```

Cron equivalent:

```cron
20 3,11,19 * * * cd /path/to/PaperRadar && PAPERRADAR_PYTHON=/path/to/python bash scripts/server_daily_push.sh
```

Logs are written under `logs/daily/`.

## Email Digest

The email digest is intentionally compact:

- sent only when new papers are found;
- includes only newly discovered papers from the latest preprint publication date;
- uses Chinese summaries, keywords, paper IDs, authors, and the site link;
- logs failures without stopping the scheduler.

Preview before sending:

```bash
python -m paperradar.cli email --input docs/data/latest.json --latest-published-day --dry-run
```

## Useful Commands

```bash
python -m paperradar.cli fetch
python -m paperradar.cli run --date 2026-05-23
bash scripts/run_daily.sh --config config/light.json
python -m paperradar.cli aggregate-local --lookback-days 60
python -m paperradar.cli reanalyze --input data/daily/public/2026-05-23.json
python -m paperradar.cli registry --query seismic
python -m paperradar.cli email --input docs/data/latest.json --latest-published-day --dry-run
python -m paperradar.cli migrate-storage
```

Use `reanalyze` when you changed the model, prompt, or API settings and want to recompute summaries from existing JSON/Markdown.

Use `aggregate-local` when you only want to rebuild the public JSON and page from local daily digests. It does not fetch metadata, download PDFs, parse PDFs, or call the LLM.

## Current Baseline

The repository currently carries a public baseline for the configured geophysics-oriented setup:

- arXiv: `physics.geo-ph` plus related topic terms;
- EarthArXiv: configured Earth science subjects such as `Geophysics and Seismology`, `Hydrology`, `Glaciology`, `Climate`, and `Oceanography`;
- public page window: 60 days.
