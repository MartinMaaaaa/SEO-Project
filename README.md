<div align="center">

# SEO Data Console

**A local-first SEO analytics workspace for GSC, GA4, PageSpeed Insights, CrUX, and AI-assisted SEO operations.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](#)
[![No npm required](https://img.shields.io/badge/Frontend-No%20npm%20required-22c55e?style=for-the-badge)](#)
[![Local First](https://img.shields.io/badge/Data-Local%20First-0ea5e9?style=for-the-badge)](#)

<a href="#中文"><img src="https://img.shields.io/badge/Language-中文-0ea5e9?style=for-the-badge" alt="中文" /></a>
<a href="#english"><img src="https://img.shields.io/badge/Language-English-111827?style=for-the-badge" alt="English" /></a>

</div>

---

## 中文

### 项目简介

SEO Data Console 是一个本地优先的 SEO 数据分析工作台，用于把多个 SEO 和网站分析数据源集中到一个可视化界面中，帮助运营者更快完成关键词分析、页面表现诊断、技术 SEO 排查和 AI 辅助决策。

当前支持的数据源和能力包括：

- Google Search Console 查询和页面表现分析
- GA4 访问、用户、浏览和参与度分析
- PageSpeed Insights 页面性能记录和历史对比
- Chrome UX Report 可用性检测
- AI 分析任务提示词生成
- 本地 SQLite 同步记录和数据缓存

这个项目适合用于搭建一个长期 SEO 运营系统，而不是一次性的报表脚本。

### 功能亮点

| 模块 | 能力 |
|---|---|
| GSC Explorer | 支持按关键词、URL、日期、曝光阈值和指标排序查看搜索表现 |
| GA4 Analytics | 支持 Sessions、Users、Views、Engagement、Channel 等图表视图 |
| PageSpeed Library | 保存每次页面性能抓取结果，记录 URL、设备、抓取时间、分数和核心指标 |
| CrUX Monitor | 检测真实用户 Core Web Vitals 数据是否可用 |
| Local Storage | 使用 SQLite 保存同步历史和结构化状态 |
| AI Prompts | 提供不含真实数据的通用 SEO 分析提示词模板 |

### 界面方向

项目的前端目标是更接近 GSC、GA4 和 Semrush 一类分析工具：

- 用图表代替阅读原始文件
- 用筛选器定位关键词和 URL 问题
- 用历史数据判断页面性能是否过期
- 用 AI prompt 把分析任务交给 Codex、Claude Code、Google Antigravity 等工具继续执行

### 技术架构

```text
SEO-Project
├─ apps/seo_dashboard/        本地 Web 控制台
│  ├─ server.py               Python 标准库后端
│  ├─ local_store.py          SQLite 本地存储
│  └─ static/                 原生 HTML / CSS / JavaScript 前端
├─ tools/                     Google API 和数据同步 CLI
├─ prompts/                   可复用 SEO 分析提示词模板
└─ docs/                      公开文档
```

### 快速开始

克隆项目：

```powershell
git clone https://github.com/MartinMaaaaa/SEO-Project.git
cd SEO-Project
```

启动本地控制台：

```powershell
python -u apps/seo_dashboard/server.py 8766
```

打开浏览器：

```text
http://127.0.0.1:8766
```

Windows 用户也可以双击：

```text
启动SEO控制台.bat
```

停止控制台：

```text
停止SEO控制台.bat
```

### 数据连接器

项目中的 `tools/` 目录包含 Google 数据源的命令行工具：

| 工具 | 用途 |
|---|---|
| `tools/gsc_cli.py` | Google Search Console 数据同步 |
| `tools/ga4_cli.py` | GA4 Data API 数据同步 |
| `tools/pagespeed_cli.py` | PageSpeed Insights 抓取 |
| `tools/crux_cli.py` | Chrome UX Report 查询 |
| `tools/google_oauth_cli.py` | Google OAuth 授权辅助 |

示例：

```powershell
python tools/gsc_cli.py check-env
python tools/ga4_cli.py check-env
python tools/pagespeed_cli.py check-env
python tools/crux_cli.py check-env
```

### AI 工作流

`prompts/` 中提供了通用提示词模板：

- GSC 机会分析
- GA4 参与度分析
- PageSpeed 技术 SEO 排查
- 月度 SEO 报告

这些模板不会包含真实业务数据。实际分析时，AI 应读取本地数据源或本地数据库，而不是把真实指标写进 prompt。

### 数据策略

项目采用 local-first 设计：

- API 凭证保存在本地环境文件中
- 原始导出保存在本地数据目录中
- SQLite 用于本地同步历史和结构化状态
- 后续可以迁移到 Supabase Postgres 或其他云数据库

### 路线图

- 完善 GSC / GA4 / PageSpeed 图表和筛选体验
- 增加 API 配额和调用频率监控面板
- 将更多原始数据导入结构化 SQLite 表
- 增加数据库迁移脚本
- 支持云端数据库同步
- 扩展 AI 自动分析和任务生成能力

<p align="right"><a href="#seo-data-console">Back to top ↑</a></p>

---

## English

### Overview

SEO Data Console is a local-first SEO analytics workspace. It brings multiple SEO and website analytics data sources into one dashboard so operators can analyze search performance, diagnose page quality, monitor technical SEO, and generate AI-assisted SEO workflows.

Current capabilities include:

- Google Search Console query and page analysis
- GA4 sessions, users, views, and engagement analysis
- PageSpeed Insights performance tracking and history
- Chrome UX Report availability checks
- AI task prompt generation
- Local SQLite sync history and cache tracking

The project is designed as a long-term SEO operations system rather than a one-off reporting script.

### Features

| Module | Capability |
|---|---|
| GSC Explorer | Filter search performance by query, URL, date range, impressions, and metric sort |
| GA4 Analytics | Switch between sessions, users, views, engagement, and channel charts |
| PageSpeed Library | Store every page performance run with URL, device, fetch time, scores, and core metrics |
| CrUX Monitor | Check whether real-user Core Web Vitals data is available |
| Local Storage | Use SQLite to track sync history and structured status |
| AI Prompts | Provide reusable SEO prompt templates without real analytics data |

### Product Direction

The frontend aims to feel closer to GSC, GA4, and Semrush-style workflows:

- Charts instead of raw file reading
- Filters for query and URL investigation
- Historical PageSpeed tracking and freshness checks
- Prompt generation for tools like Codex, Claude Code, and Google Antigravity

### Architecture

```text
SEO-Project
├─ apps/seo_dashboard/        Local web console
│  ├─ server.py               Python standard-library backend
│  ├─ local_store.py          SQLite local storage
│  └─ static/                 Native HTML / CSS / JavaScript frontend
├─ tools/                     Google API and data sync CLIs
├─ prompts/                   Reusable SEO analysis prompt templates
└─ docs/                      Public documentation
```

### Quick Start

Clone:

```powershell
git clone https://github.com/MartinMaaaaa/SEO-Project.git
cd SEO-Project
```

Start the local dashboard:

```powershell
python -u apps/seo_dashboard/server.py 8766
```

Open:

```text
http://127.0.0.1:8766
```

Windows users can also double-click:

```text
启动SEO控制台.bat
```

To stop:

```text
停止SEO控制台.bat
```

### Data Connectors

The `tools/` directory contains command-line utilities for Google data sources:

| Tool | Purpose |
|---|---|
| `tools/gsc_cli.py` | Google Search Console data sync |
| `tools/ga4_cli.py` | GA4 Data API sync |
| `tools/pagespeed_cli.py` | PageSpeed Insights runs |
| `tools/crux_cli.py` | Chrome UX Report queries |
| `tools/google_oauth_cli.py` | Google OAuth helper |

Examples:

```powershell
python tools/gsc_cli.py check-env
python tools/ga4_cli.py check-env
python tools/pagespeed_cli.py check-env
python tools/crux_cli.py check-env
```

### AI Workflow

The `prompts/` directory includes generic templates for:

- GSC opportunity analysis
- GA4 engagement analysis
- PageSpeed technical SEO triage
- Monthly SEO reporting

These templates do not contain real business data. During real analysis, AI should read local data sources or local database tables instead of hardcoding metrics inside prompts.

### Data Strategy

The project follows a local-first design:

- API credentials stay in local environment files
- Raw exports stay in local data directories
- SQLite tracks local sync history and structured status
- Cloud databases such as Supabase Postgres can be added later

### Roadmap

- Improve GSC / GA4 / PageSpeed charts and filters
- Add an API quota and call-frequency monitoring panel
- Import more raw data into structured SQLite tables
- Add database migration scripts
- Support optional cloud database synchronization
- Expand AI-assisted analysis and task generation

<p align="right"><a href="#seo-data-console">Back to top ↑</a></p>
