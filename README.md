<div align="center">

# SEO Data Console

**A local-first React and FastAPI workbench for GSC, GA4, PageSpeed, CrUX, storage operations, and AI-assisted SEO analysis.**

[![React](https://img.shields.io/badge/Frontend-React%20%2B%20TypeScript-149eca?style=for-the-badge&logo=react&logoColor=white)](#)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](#)
[![Local First](https://img.shields.io/badge/Data-Local%20First-0ea5e9?style=for-the-badge)](#)
[![Tests](https://img.shields.io/badge/Tests-Pytest%20%2B%20TypeScript-22c55e?style=for-the-badge)](#)

<a href="#中文"><img src="https://img.shields.io/badge/Language-中文-0ea5e9?style=for-the-badge" alt="中文" /></a>
<a href="#english"><img src="https://img.shields.io/badge/Language-English-111827?style=for-the-badge" alt="English" /></a>

</div>

---

## 中文

### 项目简介

SEO Data Console 是一个面向长期 SEO 运营的本地优先分析工作台。当前主应用采用 React、TypeScript、Vite 和 FastAPI，将搜索表现、站内行为、页面性能、真实用户体验、数据同步和 AI 任务集中在同一个界面中。

本地原始导出和 SQLite 始终是数据真源。Supabase Postgres 是可选的云端副本和分析数据库；即使云端未配置或暂时不可用，本地分析仍可继续运行。

### 当前能力

| 模块 | 能力 |
|---|---|
| Overview | 汇总 GSC、GA4、PageSpeed、CrUX 状态和需要处理的事项 |
| GSC Workbench | 日期范围、比较覆盖、日/周/月粒度、Query/Page 过滤、指标增量、贡献、下钻和带元数据 CSV 导出 |
| GA4 Behavior | Sessions、Users、Views、Engagement、Channel 和缓存明细分析 |
| PageSpeed | URL/设备筛选、运行历史、陈旧状态、核心指标和明确的失败状态 |
| CrUX | 展示字段数据；没有覆盖时显示 `No dataset`，不伪造成通过或失败 |
| AI Tasks | 根据当前筛选范围和证据创建可追踪的 AI 分析任务 |
| Operations | SQLite、原始缓存、Supabase、备份、容量、额度、新鲜度、日志和同步历史 |
| Connections | 仅显示脱敏后的连接配置状态 |

### 架构

```text
SEO-Project
├─ apps/
│  ├─ web/                    React + TypeScript + Vite
│  ├─ api/                    FastAPI、分析服务、SQLite 与云同步
│  └─ seo_dashboard/          冻结的旧版功能参考，不再作为主应用开发
├─ tools/                     GSC / GA4 / PageSpeed / CrUX 连接器 CLI
├─ db/migrations/             Supabase/Postgres 数据库迁移
├─ prompts/                   可公开复用的 SEO 提示词模板
└─ docs/                      架构和仓库策略文档
```

详细设计见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

### 环境要求

- Python 3.11 或更新版本
- Node.js 20.19 或更新版本
- Windows 为当前主要启动和验收平台
- Google/Supabase 配置为可选项；没有凭证时仍可使用已有本地缓存

### 安装与构建

```powershell
git clone https://github.com/MartinMaaaaa/SEO-Project.git
cd SEO-Project

python -m pip install -r apps/api/requirements.txt

cd apps/web
npm install
npm run typecheck
npm run build
cd ../..
```

如果所在网络无法访问默认 npm 注册表，可使用可访问的镜像：

```powershell
npm install --registry=https://registry.npmmirror.com
```

### 启动

Windows 用户可双击：

```text
启动SEO控制台.bat
```

或使用英文入口：

```powershell
start-seo-dashboard.bat
```

前端和后端地址：

```text
React:  http://127.0.0.1:5173/
FastAPI: http://127.0.0.1:8787/
```

停止应用：

```powershell
stop-seo-dashboard.bat
```

也可以直接启动 FastAPI：

```powershell
python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8787
```

根启动器会分别启动 React/Vite 和 FastAPI；Vite 将 `/api` 请求代理到 FastAPI。

### 数据连接器

| 工具 | 用途 |
|---|---|
| `tools/gsc_cli.py` | Google Search Console 同步和导出 |
| `tools/ga4_cli.py` | GA4 Data API 同步 |
| `tools/pagespeed_cli.py` | PageSpeed Insights 检测 |
| `tools/crux_cli.py` | Chrome UX Report 查询 |
| `tools/google_oauth_cli.py` | Google OAuth 授权辅助 |

连接器应优先遵守缓存新鲜度规则，避免为开发或测试重复消耗 API 配额。

### 测试

```powershell
python -m pytest apps/api/tests -q

cd apps/web
npm run typecheck
npm run build
```

后端测试包括：

- 缓存端点和指标语义
- GSC CTR、加权排名和比较覆盖
- PageSpeed 失败状态
- CrUX `No dataset` 状态
- AI 任务创建与历史
- 旧版目录不可访问时的独立运行测试

### 数据与安全

- `.env`、OAuth token、API key 和数据库连接串不会提交到 GitHub。
- `data/`、SQLite、本地备份和真实分析导出保持私有。
- 状态接口只返回脱敏配置。
- 成功的 API 导出在启用 Supabase 时先创建本地备份，再执行可选云复制。
- 前端不会把必需功能跳转回冻结旧版。

### 下一阶段

- 增加兼容的 GSC country/device/search appearance 数据粒度
- 增加持久化 saved views 和 annotations
- 扩展 GA4 funnel 与 path exploration
- 建立规范化的跨来源页面分析和 URL 匹配质量报告

<p align="right"><a href="#seo-data-console">返回顶部 ↑</a></p>

---

## English

### Overview

SEO Data Console is a local-first analytics workbench for long-running SEO operations. The active application uses React, TypeScript, Vite, and FastAPI to combine search performance, onsite behavior, page experience, data operations, and AI-assisted workflows.

Local raw exports and SQLite remain the source of truth. Supabase Postgres is an optional cloud replica and analysis database; local analysis continues to work when cloud services are absent or temporarily unavailable.

### Current Capabilities

| Area | Capability |
|---|---|
| Overview | GSC, GA4, PageSpeed, CrUX health and actionable attention states |
| GSC Workbench | Date scopes, comparison coverage, day/week/month grain, query/page filters, deltas, contribution, drill-down, and metadata-aware CSV export |
| GA4 Behavior | Sessions, users, views, engagement, channels, and cached detail rows |
| PageSpeed | URL/device filters, run history, freshness, core metrics, and explicit failure semantics |
| CrUX | Field data when available and an honest `No dataset` state otherwise |
| AI Tasks | Scope-aware task creation with preserved evidence |
| Operations | SQLite, raw cache, Supabase, backups, capacity, quota, freshness, logs, and sync history |
| Connections | Masked configuration status without secret exposure |

### Architecture

```text
SEO-Project
├─ apps/
│  ├─ web/                    React + TypeScript + Vite
│  ├─ api/                    FastAPI, analytics, SQLite, and cloud sync
│  └─ seo_dashboard/          Frozen legacy reference, no longer the active app
├─ tools/                     GSC / GA4 / PageSpeed / CrUX connector CLIs
├─ db/migrations/             Supabase/Postgres migrations
├─ prompts/                   Public reusable SEO prompt templates
└─ docs/                      Architecture and repository policy
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for more detail.

### Requirements

- Python 3.11+
- Node.js 20.19+
- Windows is the primary verified launch platform
- Google and Supabase credentials are optional when cached local data already exists

### Install and Build

```powershell
git clone https://github.com/MartinMaaaaa/SEO-Project.git
cd SEO-Project

python -m pip install -r apps/api/requirements.txt

cd apps/web
npm install
npm run typecheck
npm run build
cd ../..
```

If the default npm registry is unreachable from your network:

```powershell
npm install --registry=https://registry.npmmirror.com
```

### Run

Double-click `启动SEO控制台.bat`, or run:

```powershell
start-seo-dashboard.bat
```

Frontend and backend:

```text
React:  http://127.0.0.1:5173/
FastAPI: http://127.0.0.1:8787/
```

Stop:

```powershell
stop-seo-dashboard.bat
```

Direct FastAPI startup is also supported:

```powershell
python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8787
```

The root launcher starts React/Vite and FastAPI as separate processes. Vite proxies `/api` requests to FastAPI.

### Test

```powershell
python -m pytest apps/api/tests -q

cd apps/web
npm run typecheck
npm run build
```

The backend suite covers cached contracts, GSC metric semantics, PageSpeed failures, CrUX missing coverage, scoped AI tasks, and operation with all legacy-directory filesystem access blocked.

### Data and Security

- `.env`, OAuth tokens, API keys, and database URLs are never committed.
- `data/`, SQLite, backups, and real analytics exports remain private.
- Status responses expose masked configuration only.
- When Supabase is enabled, successful exports are backed up locally before optional cloud replication.
- Required functionality never links users back to the frozen dashboard.

### Next Product Work

- Compatible GSC country/device/search-appearance collection
- Persistent saved views and annotations
- GA4 funnel and path exploration
- Normalized cross-source page analysis and URL join-quality reporting

<p align="right"><a href="#seo-data-console">Back to top ↑</a></p>
