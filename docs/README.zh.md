# PaperRadar

<p align="center">
  <strong>面向 arXiv 与 EarthArXiv 的预印本雷达。</strong><br>
  追踪主题、总结论文、提取趋势，并发布为静态研究动态页面。
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <a href="index.html">GitHub Pages 页面</a> ·
  <a href="../config/default.json">示例配置</a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="Sources" src="https://img.shields.io/badge/Sources-arXiv%20%7C%20EarthArXiv-0f766e?style=flat-square">
  <img alt="LLM" src="https://img.shields.io/badge/LLM-OpenAI--compatible-8b5cf6?style=flat-square">
  <img alt="Pages" src="https://img.shields.io/badge/Publish-GitHub%20Pages-111827?style=flat-square&logo=github">
</p>

PaperRadar 将预印本信息流整理成可检索的研究动态。它从 arXiv 和 EarthArXiv 获取元数据与摘要，可选下载 PDF，可选使用 MinerU 将 PDF 解析为 Markdown，再调用 OpenAI-compatible LLM 生成中英文简明总结、关键词趋势，并发布为 GitHub Pages 静态页面。

默认配置面向地球物理/地球科学主题，但流程本身是通用的。修改 `config/default.json` 后，可以追踪其他 arXiv 分类、EarthArXiv subjects、关键词、作者或自定义 arXiv 查询。

## 功能

- 支持 arXiv category/custom query 与 EarthArXiv subject。
- PDF 下载和 MinerU PDF-to-Markdown 解析均为可选能力。
- 没有 MinerU 时可使用 abstract-only 轻量模式。
- 使用 OpenAI-compatible LLM 生成中英文摘要。
- 按 source 分开保存和展示，避免混淆 arXiv 与 EarthArXiv taxonomy。
- 静态网页支持来源切换、搜索、分页、关键词趋势和详情折叠。
- 支持服务器自动运行、git push、邮件提醒、日志、健康检查和本地失败报告。

## 流程

```text
元数据 + 摘要
        |
        +-- 可选 PDF 归档
        +-- 可选 MinerU Markdown 解析
        |
优先基于 Markdown 总结，否则基于摘要总结
        |
data/daily/<source>/YYYY-MM-DD.json
        |
docs/data/latest.*.json + docs/index.html
        |
GitHub Pages
```

## 快速开始

```bash
cp .env.example .env
python -m paperradar.cli run
```

也可以使用封装脚本：

```bash
bash scripts/run_daily.sh
```

没有 MinerU 时使用轻量模式：

```bash
bash scripts/run_daily.sh --config config/light.json
```

指定包含 MinerU 依赖的 Python 环境：

```bash
PAPERRADAR_PYTHON=/path/to/conda/env/bin/python bash scripts/run_daily.sh
```

## 配置

修改 `config/default.json`：

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

常用开关：

- `arxiv.query`：完整 arXiv 查询语句覆盖。
- `arxiv.download_pdfs=false`：跳过本地 PDF 归档。
- `arxiv.parse_pdfs=false`：跳过 MinerU，直接基于摘要总结。
- `config/light.json`：开箱即用的摘要总结模式。
- `public_lookback_days`：公开页面展示的发表日期窗口。

## 环境变量

常用 `.env`：

```bash
LLM_API_KEY=...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

HTTP_PROXY=http://user:password@host:port
HTTPS_PROXY=http://user:password@host:port

# 可选，仅 arxiv.parse_pdfs=true 时需要
MINERU_API_KEY=...
MINERU_API_BASE=...
```

可选邮件提醒：

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

## 输出

```text
docs/index.html                    静态页面
docs/data/latest.json              聚合公开数据
docs/data/latest.arxiv.json        arXiv 公开数据
docs/data/latest.eartharxiv.json   EarthArXiv 公开数据

data/daily/<source>/YYYY-MM-DD.json   按来源保存的 daily digest
data/pdfs/                            可选 PDF 缓存
data/markdown/                        可选 Markdown 缓存
data/mineru/                          可选 MinerU 原始输出
data/status/                          本地失败报告，git-ignored
```

`docs/index.html` 在浏览器运行时加载 `docs/data/latest.*.json`，因此更新 JSON 即可更新网页内容。

## GitHub Pages

1. 将仓库推送到 GitHub。
2. 在仓库设置中启用 Pages，来源选择 `main` 分支的 `/docs` 目录。
3. 在本地或服务器运行 PaperRadar。
4. 提交并推送更新后的 `data/daily` 与 `docs/data`。

MinerU 更适合在自己的服务器运行；GitHub Pages 只需要 `docs/` 里的静态文件。

## 自动化

运行一次、提交、推送，并在有新论文时发送邮件：

```bash
bash scripts/server_daily_push.sh
```

以服务器时间 11:20 为锚点，每 8 小时运行一次：

```bash
PAPERRADAR_PYTHON=/path/to/python nohup bash scripts/server_daily_loop.sh --run-at 11:20 --interval-hours 8 >> logs/daily/scheduler.nohup.log 2>&1 &
```

检查服务器状态：

```bash
bash scripts/health_check.sh
```

邮件是增量发送的：每轮会比较运行前后的 digest，只发送新增论文；没有新增内容时不会发送。

## 常用命令

```bash
python -m paperradar.cli fetch
python -m paperradar.cli run --date 2026-05-23
python -m paperradar.cli aggregate-local --lookback-days 60
python -m paperradar.cli reanalyze --input data/daily/public/2026-05-23.json
python -m paperradar.cli registry --query seismic
python -m paperradar.cli failures --input docs/data/latest.json
python -m paperradar.cli email --input docs/data/latest.json --latest-published-day --dry-run
```

## 默认基线

仓库当前包含一份面向地球科学的公开基线数据：

- arXiv: `physics.geo-ph` 与相关主题词。
- EarthArXiv: `Geophysics and Seismology`、`Hydrology`、`Glaciology`、`Climate`、`Oceanography` 等 subjects。
- 公开页面窗口：60 天。

## 致谢

PaperRadar 的部分代码实现、重构、文档整理和自动化流程搭建由 OpenAI Codex 辅助完成。

