# PaperRadar

[English](../README.md)

PaperRadar 是一个可配置的 arXiv 论文雷达。它可以追踪你关心的主题，获取论文元数据和 PDF，可选地用 MinerU 解析 PDF，再用 LLM 生成中英文总结、提取关键词趋势，并通过 GitHub Pages 发布静态日报页面。

当前默认配置追踪的是 `physics.geo-ph`，并带有 geophysics 相关主题词。但项目本身是通用的：你可以通过修改 `config/default.json` 来追踪其它 arXiv 分类、关键词、作者，或者自定义查询语句。

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

封装脚本默认使用 `python`。如果你需要指定带 MinerU 依赖的环境，可以设置 `PAPERRADAR_PYTHON`：

```bash
bash scripts/run_daily.sh
```

主要输出：

- `data/daily/YYYY-MM-DD.json`：每日结果 JSON
- `docs/index.html`：GitHub Pages 页面
- `docs/data/latest.json`：页面使用的最新公开数据
- `data/pdfs/`、`data/markdown/`、`data/mineru/`：本地缓存，已被 git 忽略
- `data/paper_registry.json`：本地管理表，已被 git 忽略

## 配置主题

修改 `config/default.json`：

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

如果 `query` 为空，PaperRadar 会根据上面的结构化字段自动拼接 arXiv 查询。只有在你想完全接管 arXiv 查询语句时，才需要设置 `query`。

`storage_category_policy` 控制本地缓存目录：

- `configured`：只要配置了 `categories`，就使用第一个配置分类作为目录。
- `matched`：只有当论文 metadata 中包含配置分类时，才使用配置分类目录。
- 其它值：使用论文 metadata 中的 primary arXiv category。

## 密钥和 `.env`

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
```

不要提交 `.env`。它已经被 `.gitignore` 忽略。

## GitHub Pages

1. 将仓库 push 到 GitHub。
2. 在仓库设置中启用 Pages，来源选择 `main` 分支的 `/docs` 目录。
3. 如果希望 GitHub Actions 调用 LLM，将 `LLM_API_KEY` 添加为 Actions secret。
4. 如有需要，将 `LLM_BASE_URL` 和 `LLM_MODEL` 添加为 Actions variables。
5. `.github/workflows/daily.yml` 会每天运行并提交更新后的 `data/` 和 `docs/`。

提醒：完整的 PDF + MinerU 解析更适合在本地服务器运行，因为那里已经有 MinerU 依赖和密钥。GitHub Actions 可以负责发布 `docs/` 页面，但如果要在 Actions 中跑 MinerU，需要额外配置依赖和密钥。

如果使用 GitHub 托管的 Actions，建议选择以下模式之一：

- metadata/abstract-only：在 `config/default.json` 中设置 `"parse_pdfs": false`。
- MinerU Cloud 解析：安装 MinerU 可选依赖，并配置所需的 `MINERU_*` secrets 或 variables。
- 完整本地解析：在自己的机器或 self-hosted runner 上运行 PaperRadar，然后提交/推送生成的 `docs/` 输出。

## 服务器定时运行

如果服务器上已经在 `.env` 中配置好了代理、MinerU 和 LLM 密钥，可以使用：

```bash
bash scripts/server_daily_push.sh
```

这个脚本会先拉取 GitHub 最新状态，再运行完整日报流程，然后只提交公开输出目录（`data/daily` 和 `docs`）并 push 到 GitHub。本地缓存和密钥仍然会被 git 忽略。
日志和当前 PID 文件默认写入 `logs/daily/`。

每天服务器时间 11:20 自动运行的 cron 示例：

```cron
20 11 * * * cd /path/to/PaperRadar && PAPERRADAR_PYTHON=/path/to/python bash scripts/server_daily_push.sh
```

如果服务器没有 `crontab`，可以改用轻量常驻调度脚本：

```bash
PAPERRADAR_PYTHON=/path/to/python nohup bash scripts/server_daily_loop.sh --run-at 11:20 >> logs/daily/scheduler.nohup.log 2>&1 &
```

查看或停止它：

```bash
cat logs/daily/server_daily_scheduler.pid
kill $(cat logs/daily/server_daily_scheduler.pid)
```

如果服务器任务是主要更新方式，建议关闭 `.github/workflows/daily.yml` 里的定时 schedule，或者保留为手动触发，避免两个任务同时 push。

## 常用命令

当你修改了 LLM 模型、提示词或 API 设置，想基于已有 daily JSON/Markdown 重新生成总结，但不重新抓取 arXiv、不重新解析 PDF 时，使用 `reanalyze`。

```bash
python -m paperradar.cli fetch
python -m paperradar.cli run --date 2026-05-21
python -m paperradar.cli render --input data/daily/2026-05-21.json
python -m paperradar.cli reanalyze --input data/daily/2026-05-21.json
python -m paperradar.cli registry --query seismic
python -m paperradar.cli migrate-storage
```

脚本封装：

```bash
bash scripts/run_daily.sh
bash scripts/run_daily.sh run --limit 3
bash scripts/run_daily.sh reanalyze --input data/daily/2026-05-21.json
bash scripts/run_daily.sh registry --query seismic
bash scripts/run_daily.sh migrate-storage
```

## 不应该上传的内容

当前 `.gitignore` 已经忽略本地密钥和较重的私有/缓存产物：

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
- Python/build 缓存

`docs/` 目录是公开页面输出，应该提交到 GitHub。
