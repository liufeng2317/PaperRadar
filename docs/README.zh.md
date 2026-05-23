# PaperRadar

<p align="center">
  <strong>追踪、总结并发布来自 arXiv 与 EarthArXiv 的预印本情报。</strong>
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <a href="index.html">GitHub Pages 页面</a> ·
  <a href="../config/default.json">配置文件</a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="Sources" src="https://img.shields.io/badge/Sources-arXiv%20%7C%20EarthArXiv-0f766e?style=flat-square">
  <img alt="LLM" src="https://img.shields.io/badge/LLM-OpenAI--compatible-8b5cf6?style=flat-square">
  <img alt="Pages" src="https://img.shields.io/badge/Publish-GitHub%20Pages-111827?style=flat-square&logo=github">
</p>

PaperRadar 是一个轻量级预印本情报流水线。它会追踪你关心的研究主题，始终获取元数据和摘要，可选地下载 PDF，可选地用 MinerU 将 PDF 解析成 Markdown，再调用 OpenAI-compatible LLM 生成中英文总结、提取关键词趋势，并通过 GitHub Pages 发布为静态网页。

当前默认配置偏向地球物理相关内容，同时支持 arXiv 和 EarthArXiv。项目本身是通用的：修改 `config/default.json` 后，可以追踪其它 arXiv 分类、EarthArXiv subjects、关键词、作者或自定义查询。

## 为什么需要它

科研动态不应该散落在一堆标签页里。PaperRadar 的目标是把每日预印本变成一个可检索、可发布、可持续更新的研究雷达：

- 及时发现新的预印本，而不是被信息流淹没；
- 在本地保留 PDF、Markdown、LLM 总结和公开 JSON；
- 不需要后端服务，也能发布双语网页；
- 正确区分 arXiv categories 和 EarthArXiv subjects；
- 增量运行，已有 PDF、Markdown、总结都会自动复用。

## 你会得到什么

| 层级 | 产物 |
| --- | --- |
| 发现 | arXiv API 与 EarthArXiv OAI-PMH 元数据接口 |
| 存储 | 按来源组织的 daily JSON、可选 PDF 缓存、可选 Markdown/MinerU 缓存 |
| 理解 | 优先基于 Markdown 的中英文 LLM 总结；没有 MinerU 时基于摘要总结 |
| 趋势 | 单篇关键词与整体关键词排行 |
| 发布 | `docs/index.html` 运行时加载 `docs/data/latest.*.json` |
| 自动化 | 服务器循环、git push、可选中文邮件提醒 |

## 数据流

```text
arXiv categories / custom query      EarthArXiv subjects
              │                       │
              └────── 获取元数据 + 摘要 ──────────────┐
                                      │              │
                                      │              ├─ 如果 download_pdfs=false
                                      │              │      跳过本地 PDF 归档
                                      │              │
                                      ├─ 如果 download_pdfs=true
                                      │      PDF 保存到 data/pdfs/
                                      │
                                      ├─ 如果 parse_pdfs=true 且 PDF 存在
                                      │      MinerU 解析 -> Markdown 保存到 data/markdown/
                                      │
                                      └─ LLM 输入
                                             ├─ 优先使用 Markdown
                                             └─ 没有 Markdown 时使用摘要
                                                   │
                                           双语总结 + 关键词趋势
                                                   │
                               data/daily/<source>/YYYY-MM-DD.json
                                                   │
                                     docs/data/latest.*.json
                                                   │
                                          GitHub Pages 页面
```

## 快速开始

```bash
python -m paperradar.cli run
```

或使用封装脚本：

```bash
bash scripts/run_daily.sh
```

建议使用包含 MinerU 依赖的 Python 环境：

```bash
PAPERRADAR_PYTHON=/path/to/python bash scripts/run_daily.sh
```

在服务器环境中，将 `PAPERRADAR_PYTHON` 指向已经安装依赖的 Python 可执行文件：

```bash
PAPERRADAR_PYTHON=/path/to/conda/env/bin/python bash scripts/run_daily.sh
```

如果没有安装 MinerU，可以使用轻量模式。该模式仍会获取元数据和摘要、按配置下载 PDF 并调用 LLM，但总结输入会从解析后的 Markdown 降级为论文摘要：

```bash
bash scripts/run_daily.sh --config config/light.json
```

## 配置

修改 `config/default.json`。

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

说明：

- `arxiv.query` 留空时，PaperRadar 会根据结构化字段自动拼接查询；
- 只有想完全接管 arXiv 查询语句时，才需要设置 `arxiv.query`；
- `arxiv.categories` 是 arXiv 分类，例如 `physics.geo-ph`；
- `eartharxiv.subjects` 是 EarthArXiv 的 subject，例如 `Geophysics and Seismology`；
- `lookback_days` 控制抓取窗口，`public_lookback_days` 控制公开页面展示窗口。
- `arxiv.download_pdfs=false` 会跳过本地 PDF 归档，但仍保留元数据、摘要、链接、LLM 总结、关键词趋势和网页展示。
- `arxiv.parse_pdfs=false` 会跳过 MinerU，并直接基于摘要总结。
- `config/light.json` 是开箱即用的无 MinerU 配置：保留 PDF 下载，关闭 PDF 解析。

## 输出结构

```text
docs/index.html                                  静态页面壳
docs/data/latest.json                            聚合公开数据
docs/data/latest.arxiv.json                      arXiv 数据
docs/data/latest.eartharxiv.json                 EarthArXiv 数据

data/daily/<source>/YYYY-MM-DD.json              按来源拆分的 daily digest
data/daily/public/YYYY-MM-DD.json                聚合 daily digest

data/pdfs/<source>/<category-or-subject>/<day>/  PDF 缓存
data/markdown/<source>/<category-or-subject>/<day>/ Markdown 缓存
data/mineru/<source>/<category-or-subject>/<day>/   MinerU 原始输出
```

`docs/index.html` 不再写死具体论文内容，而是在浏览器中加载 `docs/data/` 下的 JSON；更新 JSON 后，网页内容就会随之更新。

## 环境变量

从示例创建本地 `.env`：

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

# 可选，仅在 arxiv.parse_pdfs=true 时需要
MINERU_API_KEY=...
MINERU_API_BASE=...
```

可选邮件提醒：

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

1. 将仓库推送到 GitHub。
2. 在仓库设置中启用 Pages，来源选择 `main` 分支的 `/docs` 目录。
3. 在服务器或本地运行 PaperRadar。
4. 提交并推送 `data/daily` 与 `docs/data` 更新。

MinerU 解析是可选能力。没有 MinerU 时，可以使用 `config/light.json` 发布基于摘要的 digest。完整 PDF + MinerU 解析更适合在已经配置好 MinerU 密钥和依赖的服务器上运行；GitHub Actions 更适合负责静态页面发布。

## 自动化运行

运行一次并自动推送：

```bash
bash scripts/server_daily_push.sh
```

以服务器时间 11:20 为锚点，每 8 小时运行一次：

```bash
PAPERRADAR_PYTHON=/path/to/python nohup bash scripts/server_daily_loop.sh --run-at 11:20 --interval-hours 8 >> logs/daily/scheduler.nohup.log 2>&1 &
```

cron 等价写法：

```cron
20 3,11,19 * * * cd /path/to/PaperRadar && PAPERRADAR_PYTHON=/path/to/python bash scripts/server_daily_push.sh
```

日志位于 `logs/daily/`。

## 邮件日报

邮件日报保持简洁，只作为“有新论文”的提醒：

- 只有发现新论文时才发送；
- 只包含新增论文中最新预印本发布日期那一天的内容；
- 包含中文一句话总结、关键词、论文 ID、作者和网页链接；
- 邮件失败只记录日志，不中断后续调度。

发送前预览：

```bash
python -m paperradar.cli email --input docs/data/latest.json --latest-published-day --dry-run
```

## 常用命令

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

当你修改模型、提示词或 API 设置，希望基于已有 JSON/Markdown 重新生成总结时，用 `reanalyze`。

当你只想基于本地 daily JSON 重新生成公开 JSON 和页面时，用 `aggregate-local`。它不会抓取元数据、下载 PDF、解析 PDF 或调用 LLM。

## 当前基础数据

仓库当前已经包含一份面向地球科学/地球物理配置的公开基础数据：

- arXiv: `physics.geo-ph` 与相关主题词；
- EarthArXiv: `Geophysics and Seismology`、`Hydrology`、`Glaciology`、`Climate`、`Oceanography` 等 subjects；
- 公开页面窗口：60 天。
