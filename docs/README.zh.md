# PaperRadar

[English](../README.md)

PaperRadar 是一个可配置的 arXiv 论文雷达。它可以追踪你关心的主题，获取论文元数据和 PDF，可选地用 MinerU 解析 PDF，再用 OpenAI-compatible LLM 生成中英文总结、提取关键词趋势，并通过 GitHub Pages 发布静态日报页面。

当前默认配置追踪 `physics.geo-ph`，并带有 geophysics 相关主题词。但项目本身是通用的：你可以修改 `config/default.json` 来追踪其它 arXiv 分类、关键词、作者，或者自定义查询语句。

## 功能

- 按 arXiv 分类、关键词、作者或自定义 query 获取近期论文。
- 本地缓存 PDF，已存在的 PDF 不会重复下载。
- 使用内置 MinerU 集成将 PDF 解析为 Markdown。
- 使用 OpenAI-compatible LLM 生成中英文论文总结。
- 为每篇论文提取关键词，并统计每日 trending keywords。
- 从 `docs/` 生成可直接用于 GitHub Pages 的静态页面。
- 使用 registry 增量管理，已有 PDF、Markdown、LLM 总结都会自动跳过。

## 快速开始

```bash
python -m paperradar.cli run
```

也可以使用封装脚本：

```bash
bash scripts/run_daily.sh
```

如果需要指定带 MinerU 依赖的 Python 环境，可以设置 `PAPERRADAR_PYTHON`：

```bash
PAPERRADAR_PYTHON=/path/to/python bash scripts/run_daily.sh
```

主要输出：

- `data/daily/YYYY-MM-DD.json`：每日结果 JSON
- `docs/index.html`：GitHub Pages 页面
- `docs/data/latest.json`：页面使用的最新公开数据
- `data/pdfs/<category>/<YYYYMMDD>/`：按 arXiv 论文发布日期分组的 PDF 缓存
- `data/markdown/<category>/<YYYYMMDD>/`：按 arXiv 论文发布日期分组的 Markdown
- `data/mineru/<category>/<YYYYMMDD>/`：按 arXiv 论文发布日期分组的 MinerU 输出

## 配置

修改 `config/default.json`：

```json
{
  "arxiv": {
    "categories": ["physics.geo-ph"],
    "extra_terms": ["geophysics", "seismology", "geodesy", "geodynamics", "geomagnetism"],
    "keywords": [],
    "authors": [],
    "max_results": 100,
    "lookback_days": 60,
    "download_pdfs": true,
    "parse_pdfs": true,
    "storage_category_policy": "configured"
  }
}
```

如果 `query` 为空，PaperRadar 会根据上面的结构化字段自动拼接 arXiv 查询。只有在你想完全接管 arXiv 查询语句时，才需要设置 `query`。

`lookback_days` 控制公开页面的滚动时间窗口。默认值 `60` 会在生成页面中保留大约两个月内匹配到的论文。

`storage_category_policy` 控制本地缓存目录：

- `configured`：只要配置了 `categories`，就使用第一个配置分类作为目录。
- `matched`：只有当论文 metadata 中包含配置分类时，才使用配置分类目录。
- 其它值：使用论文 metadata 中的 primary arXiv category。

## 环境变量

本地运行时复制 `.env.example`：

```bash
cp .env.example .env
```

常用变量：

```bash
LLM_API_KEY=...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
HTTP_PROXY=http://user:password@host:port
HTTPS_PROXY=http://user:password@host:port
MINERU_API_KEY=...
MINERU_API_BASE=...

# 可选：在成功更新公开日报后发送中文邮件。
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

1. 将仓库 push 到 GitHub。
2. 在仓库设置中启用 Pages，来源选择 `main` 分支的 `/docs` 目录。
3. 在本地或服务器运行 PaperRadar，然后提交并推送更新后的 `data/daily` 和 `docs` 输出。

GitHub-hosted Actions 可以发布生成后的页面，但完整 PDF + MinerU 解析更适合在已有 MinerU 依赖和密钥的本地/服务器环境中运行。

## 邮件日报

PaperRadar 可以在自动更新后发送一封精简中文邮件。邮件用于提醒你有新论文，不会把网页里的全部内容都塞进邮箱：

- 只有发现新论文时才发送。
- 只发送新增论文中最新 arXiv 发布日期那一天的内容。
- 每篇论文包含标题、arXiv ID、作者、一句话中文总结、关键词和 arXiv 链接。
- 如果某次 8 小时检查没有新论文，就不会发送邮件。
- 如果邮件发送失败，只会记录到日志，不会中断后续自动更新。

在 `.env` 中配置自己的 SMTP 账号即可启用：

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

可以先预览邮件正文，不实际发送：

```bash
python -m paperradar.cli email --input docs/data/latest.json --latest-published-day --dry-run
```

## 服务器自动更新

如果服务器已经在 `.env` 中配置好了代理、MinerU 和 LLM 密钥，可以运行一次并推送更新：

```bash
bash scripts/server_daily_push.sh
```

每 8 小时运行一次，并以服务器时间 11:20 为锚点的 cron 示例：

```cron
20 3,11,19 * * * cd /path/to/PaperRadar && PAPERRADAR_PYTHON=/path/to/python bash scripts/server_daily_push.sh
```

如果服务器没有 `crontab`，可以改用轻量常驻调度脚本：

```bash
PAPERRADAR_PYTHON=/path/to/python nohup bash scripts/server_daily_loop.sh --run-at 11:20 --interval-hours 8 >> logs/daily/scheduler.nohup.log 2>&1 &
```

## 常用命令

```bash
python -m paperradar.cli fetch
python -m paperradar.cli run --date 2026-05-21
python -m paperradar.cli render --input data/daily/2026-05-21.json
python -m paperradar.cli aggregate-local --lookback-days 60
python -m paperradar.cli reanalyze --input data/daily/2026-05-21.json
python -m paperradar.cli registry --query seismic
python -m paperradar.cli email --input docs/data/latest.json --latest-published-day --dry-run
python -m paperradar.cli migrate-storage
```

当你修改了 LLM 模型、提示词或 API 设置，想基于已有 daily JSON/Markdown 重新生成总结，但不重新抓取 arXiv、不重新解析 PDF 时，使用 `reanalyze`。

如果只想用本地已有的 daily JSON 重新生成公开页面，使用 `aggregate-local`。它不会抓取 arXiv，不会下载 PDF，不会解析 PDF，也不会调用 LLM。
