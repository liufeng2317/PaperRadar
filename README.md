# PaperRadar

<p align="center">
  <strong>Preprint radar for arXiv and EarthArXiv.</strong><br>
  Track topics, summarize papers, rank trends, and publish a static research digest.
</p>

<p align="center">
  <a href="docs/README.zh.md">中文文档</a> ·
  <a href="docs/index.html">GitHub Pages site</a> ·
  <a href="config/default.json">Example config</a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="Sources" src="https://img.shields.io/badge/Sources-arXiv%20%7C%20EarthArXiv-0f766e?style=flat-square">
  <img alt="LLM" src="https://img.shields.io/badge/LLM-OpenAI--compatible-8b5cf6?style=flat-square">
  <img alt="Pages" src="https://img.shields.io/badge/Publish-GitHub%20Pages-111827?style=flat-square&logo=github">
</p>

PaperRadar turns preprint feeds into a searchable research digest. It fetches metadata and abstracts from arXiv and EarthArXiv, optionally archives PDFs, optionally parses PDFs to Markdown with MinerU, generates concise bilingual LLM summaries, ranks keyword trends, and publishes the result as a GitHub Pages site.

The default configuration tracks geophysics-oriented topics, but the pipeline is domain-agnostic. Change `config/default.json` to follow other arXiv categories, EarthArXiv subjects, keywords, authors, or custom arXiv queries.

## Features

- arXiv category/custom-query tracking and EarthArXiv subject tracking.
- Optional PDF download and optional MinerU PDF-to-Markdown parsing.
- Abstract-only mode for lightweight deployments without MinerU.
- OpenAI-compatible LLM summaries in English and Chinese.
- Source-aware storage and public JSON: arXiv and EarthArXiv stay separate.
- Static web UI with source tabs, search, pagination, keyword trends, and detail folding.
- Server automation with git push, compact email digest, logs, health checks, and local failure reports.

## How It Works

```text
metadata + abstracts
        |
        +-- optional PDF archive
        +-- optional MinerU Markdown parsing
        |
LLM summary from Markdown when available, otherwise abstract
        |
data/daily/<source>/YYYY-MM-DD.json
        |
docs/data/latest.*.json + docs/index.html
        |
GitHub Pages
```

## Quick Start

```bash
cp .env.example .env
python -m paperradar.cli run
```

Or use the wrapper script:

```bash
bash scripts/run_daily.sh
```

Use the lightweight profile when MinerU is not available:

```bash
bash scripts/run_daily.sh --config config/light.json
```

Use a specific Python environment, for example a Conda environment with MinerU installed:

```bash
PAPERRADAR_PYTHON=/path/to/conda/env/bin/python bash scripts/run_daily.sh
```

## Configuration

Edit `config/default.json`:

```json
{
  "arxiv": {
    "categories": ["physics.geo-ph"],
    "extra_terms": ["geophysics", "seismology", "geodesy"],
    "download_pdfs": true,
    "parse_pdfs": true
  },
  "eartharxiv": {
    "enabled": true,
    "subjects": ["Geophysics and Seismology", "Hydrology", "Glaciology"]
  },
  "public_lookback_days": 60
}
```

Useful switches:

- `arxiv.query`: optional full arXiv query override.
- `arxiv.download_pdfs=false`: skip local PDF archiving.
- `arxiv.parse_pdfs=false`: skip MinerU and summarize from abstracts.
- `config/light.json`: ready-to-use abstract-based profile.
- `public_lookback_days`: number of publication days shown on the public page.

## Environment

Common `.env` values:

```bash
LLM_API_KEY=...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

HTTP_PROXY=http://user:password@host:port
HTTPS_PROXY=http://user:password@host:port

# Optional, only needed when arxiv.parse_pdfs=true
MINERU_API_KEY=...
MINERU_API_BASE=...
```

Optional email delivery:

```bash
PAPERRADAR_EMAIL_ENABLED=1
PAPERRADAR_EMAIL_TO=your-email@example.com
PAPERRADAR_SITE_URL=https://your-user.github.io/PaperRadar/

SMTP_HOST=smtp.qq.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=your-email@example.com
SMTP_PASSWORD=your-smtp-app-password
```

## Outputs

```text
docs/index.html                    static UI
docs/data/latest.json              combined public data
docs/data/latest.arxiv.json        arXiv public data
docs/data/latest.eartharxiv.json   EarthArXiv public data

data/daily/<source>/YYYY-MM-DD.json   source-specific daily digests
data/pdfs/                            optional PDF cache
data/markdown/                        optional Markdown cache
data/mineru/                          optional MinerU raw outputs
data/status/                          local failure reports, git-ignored
```

`docs/index.html` loads `docs/data/latest.*.json` at runtime, so updating the JSON updates the site content.

## GitHub Pages

1. Push the repository to GitHub.
2. Enable Pages from branch `main`, folder `/docs`.
3. Run PaperRadar locally or on your own server.
4. Commit and push updated `data/daily` and `docs/data` outputs.

MinerU parsing is usually better on your own machine or server. GitHub Pages only needs the static files in `docs/`.

## Automation

Run once, commit, push, and send email if new papers are found:

```bash
bash scripts/server_daily_push.sh
```

Run every 8 hours, anchored at 11:20 server time:

```bash
PAPERRADAR_PYTHON=/path/to/python nohup bash scripts/server_daily_loop.sh --run-at 11:20 --interval-hours 8 >> logs/daily/scheduler.nohup.log 2>&1 &
```

Check server status:

```bash
bash scripts/health_check.sh
```

The email digest is incremental: it compares the pre-run and post-run digests, sends only newly discovered papers, and skips sending when nothing new is found.

## Common Commands

```bash
python -m paperradar.cli fetch
python -m paperradar.cli run --date 2026-05-23
python -m paperradar.cli aggregate-local --lookback-days 60
python -m paperradar.cli reanalyze --input data/daily/public/2026-05-23.json
python -m paperradar.cli registry --query seismic
python -m paperradar.cli failures --input docs/data/latest.json
python -m paperradar.cli email --input docs/data/latest.json --latest-published-day --dry-run
```

## Default Baseline

This repository currently includes a public geoscience-oriented baseline:

- arXiv: `physics.geo-ph` plus related topic terms.
- EarthArXiv: subjects such as `Geophysics and Seismology`, `Hydrology`, `Glaciology`, `Climate`, and `Oceanography`.
- Public page window: 60 days.
