# PaperRadar

[中文文档](docs/README.zh.md)

PaperRadar is a configurable preprint radar for arXiv and EarthArXiv. It tracks topics you care about, downloads metadata and PDFs, optionally parses PDFs with MinerU, summarizes papers with an OpenAI-compatible LLM, ranks keyword trends, and publishes a bilingual static digest through GitHub Pages.

The default configuration tracks `physics.geo-ph` with geophysics-related terms. The project is domain-agnostic: edit `config/default.json` to monitor other arXiv categories, keywords, authors, or a custom query.

## Features

- Fetch recent arXiv papers from configured categories, keywords, authors, or raw queries.
- Fetch EarthArXiv preprints through the official OAI-PMH metadata feed.
- Cache PDFs locally without re-downloading existing files.
- Parse PDFs into Markdown with the bundled MinerU integration.
- Generate English and Chinese paper summaries with an OpenAI-compatible LLM.
- Extract per-paper keywords and rank daily trending keywords.
- Render a static GitHub Pages site from `docs/`.
- Use an incremental registry so existing PDFs, Markdown, and summaries are skipped.

## Quick Start

```bash
python -m paperradar.cli run
```

Or use the wrapper script:

```bash
bash scripts/run_daily.sh
```

Use `PAPERRADAR_PYTHON` when you want a specific Python environment, for example one with MinerU installed:

```bash
PAPERRADAR_PYTHON=/path/to/python bash scripts/run_daily.sh
```

Main outputs:

- `data/daily/<source>/YYYY-MM-DD.json`: source-specific daily digest JSON
- `docs/index.html`: GitHub Pages HTML page
- `data/daily/public/YYYY-MM-DD.json`: aggregated public daily digest JSON
- `docs/data/latest.json`: latest aggregated public page data
- `docs/data/latest.arxiv.json` and `docs/data/latest.eartharxiv.json`: latest source-specific public data
- `data/pdfs/<source>/<category>/<YYYYMMDD>/`: cached PDFs grouped by source and preprint publication date
- `data/markdown/<source>/<category>/<YYYYMMDD>/`: parsed Markdown grouped by source and preprint publication date
- `data/mineru/<source>/<category>/<YYYYMMDD>/`: MinerU outputs grouped by source and preprint publication date

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

`lookback_days` controls the incremental fetch window. `public_lookback_days` controls the generated page window; the default public window is `60`, roughly two months of locally known matching papers.

`storage_category_policy` controls local cache folders:

- `configured`: use the first configured category folder when `categories` is non-empty.
- `matched`: use a configured category only if the paper metadata contains it.
- any other value: use the paper's primary arXiv category.

## Environment

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

# Optional email delivery after successful digest updates.
PAPERRADAR_EMAIL_ENABLED=0
PAPERRADAR_EMAIL_TO=your-email@example.com
PAPERRADAR_EMAIL_FROM=PaperRadar <your-smtp-user@example.com>
PAPERRADAR_SITE_URL=https://your-user.github.io/PaperRadar/
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=your-smtp-user@example.com
SMTP_PASSWORD=your-smtp-password-or-app-password
```

## GitHub Pages

1. Push the repository to GitHub.
2. In repository settings, enable Pages from branch `main`, folder `/docs`.
3. Run PaperRadar locally or on a server, then commit and push updated `data/daily` and `docs` outputs.

GitHub-hosted Actions can publish the generated page, but full PDF parsing with MinerU is usually better on a local/server environment where MinerU credentials and dependencies are already configured.

## Email Digest

PaperRadar can send a compact Chinese email after an automated update. The email is designed as a notification, not a full copy of the website:

- It is sent only when new papers are found.
- It includes only the newly discovered papers from the latest preprint publication date.
- It includes each paper's title, preprint ID, authors, one-sentence Chinese summary, keywords, and repository link.
- If an 8-hour check finds no new papers, no email is sent.
- If email delivery fails, the failure is logged and the scheduler continues.

Enable it in `.env` with your own SMTP account:

```bash
PAPERRADAR_EMAIL_ENABLED=1
PAPERRADAR_EMAIL_TO=your-email@example.com
PAPERRADAR_EMAIL_FROM=PaperRadar <your-email@example.com>
SMTP_HOST=smtp.qq.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=your-email@example.com
SMTP_PASSWORD=your-smtp-app-password
```

Preview the email body without sending:

```bash
python -m paperradar.cli email --input docs/data/latest.json --latest-published-day --dry-run
```

## Server Automation

For a server that already has proxy, MinerU, and LLM credentials in `.env`, run once and push updates with:

```bash
bash scripts/server_daily_push.sh
```

Run every 8 hours, anchored at 11:20 server time, with cron:

```cron
20 3,11,19 * * * cd /path/to/PaperRadar && PAPERRADAR_PYTHON=/path/to/python bash scripts/server_daily_push.sh
```

If `crontab` is unavailable, use the lightweight scheduler:

```bash
PAPERRADAR_PYTHON=/path/to/python nohup bash scripts/server_daily_loop.sh --run-at 11:20 --interval-hours 8 >> logs/daily/scheduler.nohup.log 2>&1 &
```

## Commands

```bash
python -m paperradar.cli fetch
python -m paperradar.cli run --date 2026-05-21
python -m paperradar.cli render --input data/daily/public/2026-05-21.json
python -m paperradar.cli aggregate-local --lookback-days 60
python -m paperradar.cli reanalyze --input data/daily/public/2026-05-21.json
python -m paperradar.cli registry --query seismic
python -m paperradar.cli email --input docs/data/latest.json --latest-published-day --dry-run
python -m paperradar.cli migrate-storage
```

Use `reanalyze` when you changed the LLM model, summary instructions, or API settings and want to recompute summaries from existing daily JSON/Markdown without fetching arXiv or parsing PDFs again.

Use `aggregate-local` to rebuild the public page from existing local daily JSON files only. It does not fetch arXiv, download PDFs, parse PDFs, or call the LLM.
