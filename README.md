# SEO Project / SEO 数据项目

> 中文说明在前，English version follows.

## 中文

这是一个面向官网 SEO 运营的数据与工作流项目。它的目标是把 Google Search Console、GA4、PageSpeed Insights、CrUX 等数据接入本地工作台，并让 AI 在不接触密钥、不泄露原始数据的前提下辅助完成 SEO 分析、内容规划、技术 SEO 排查和月度复盘。

GitHub 仓库地址：

[MartinMaaaaa/SEO-Project](https://github.com/MartinMaaaaa/SEO-Project)

### 当前定位

本仓库只上传可公开的项目代码和通用提示词，不上传私密业务数据、API 凭证、原始导出、内部项目进度、内部 AI 记忆或具体分析结果。

### 可以上传到 GitHub 的内容

- `README.md`
- `apps/`：本地 SEO 控制台前端和后端代码
- `tools/`：不含密钥的数据连接器和工具代码
- `prompts/`：通用 SEO 分析提示词，不能包含真实数据、真实指标、客户信息或 API 密钥
- `docs/`：公开仓库使用说明和安全策略
- `db/migrations/`：未来数据库表结构迁移文件，不能包含真实数据

### 不允许上传的内容

以下内容已通过 `.gitignore` 默认排除：

- `.env`、`.env.*`
- OAuth token、API key、client secret、service account 文件
- `data/` 下的所有 GSC、GA4、PageSpeed、CrUX、SQLite 和原始导出
- `.ai/` 内部 AI 记忆、项目计划、交接日志、内部提示词
- `PROJECT_STATUS.md`、`CHANGELOG.md`、`API_ROADMAP.md`、`NEXT_STEPS.md`
- `backlog/` 和各 SEO 工作流目录中的私有运营内容
- 任何真实业务数据、真实指标、具体客户信息、截图、报告或分析结论

### 本地运行

本项目目前使用 Python 标准库后端和原生前端，不需要安装 npm 依赖。

启动本地控制台：

```powershell
python -u apps/seo_dashboard/server.py 8766
```

打开：

```text
http://127.0.0.1:8766
```

也可以使用本地启动脚本：

```text
启动SEO控制台.bat
```

### 本地私有配置

API 和数据配置只应存在本地，不应提交到 GitHub。

本地需要的私有文件包括：

- `.env`
- Google OAuth 凭证
- Google API key
- `data/` 原始导出和 SQLite 数据库
- 内部 AI 记忆和项目进度文件

### AI 协作原则

本项目可能由多个 AI 工具协作，包括 Codex、Claude Code 和 Google Antigravity。

公开仓库中只保留真正工作场景需要的、无具体数据的通用提示词。项目制作过程中的计划、进度、交接、内部 AI 记忆、API 配置说明和真实分析数据不上传。

提示词要求：

- 可以描述分析方法和输出格式
- 不能写入真实点击、曝光、排名、会话、URL 私有列表或 API 返回内容
- 不能包含密钥、token、账号 ID、客户隐私信息
- 应要求 AI 从本地数据源读取数据，而不是在提示词中硬编码数据

### 云数据库建议

后续如果需要云端数据库，建议优先考虑 Supabase Postgres。它适合保存结构化 SEO 数据、任务状态、AI 工作流记录和未来前端读取接口。

在迁移到云端前，应先确认：

- 本地 SQLite 数据模型稳定
- 用户同意把 SEO 数据保存到第三方云数据库
- 所有密钥只保存在本地或安全的云端 secret manager 中

### GitHub 上传前检查

在提交前建议执行：

```powershell
git status --short --ignored
git check-ignore -v .env data .ai PROJECT_STATUS.md CHANGELOG.md
```

确认 `.env`、`data/`、`.ai/`、项目进度和真实数据都处于 ignored 状态后，再提交。

---

## English

This is a data and workflow project for operating SEO for an official website. Its goal is to connect Google Search Console, GA4, PageSpeed Insights, CrUX, and related data sources to a local dashboard, then let AI assist with SEO analysis, content planning, technical SEO triage, and reporting without exposing secrets or raw private data.

GitHub repository:

[MartinMaaaaa/SEO-Project](https://github.com/MartinMaaaaa/SEO-Project)

### Repository Scope

This repository should only contain public-safe source code and generic prompts. It must not contain private business data, API credentials, raw exports, internal project progress, internal AI memory, or concrete SEO analysis results.

### Safe To Upload

- `README.md`
- `apps/`: local SEO dashboard frontend and backend code
- `tools/`: data connector and utility source code without secrets
- `prompts/`: generic SEO analysis prompts with no real metrics or client data
- `docs/`: public repository policy and usage docs
- `db/migrations/`: future database schema migrations with no real data

### Never Upload

The following are ignored by default:

- `.env`, `.env.*`
- OAuth tokens, API keys, client secrets, service account files
- Everything under `data/`, including raw GSC, GA4, PageSpeed, CrUX exports and SQLite databases
- Internal `.ai/` files, AI memory, plans, handoff logs, and private prompts
- `PROJECT_STATUS.md`, `CHANGELOG.md`, `API_ROADMAP.md`, `NEXT_STEPS.md`
- `backlog/` and private SEO workstream folders
- Real business data, real metrics, client details, screenshots, reports, or analysis conclusions

### Local Run

The current dashboard uses a Python standard-library backend and native frontend. No npm dependencies are required.

Start the local dashboard:

```powershell
python -u apps/seo_dashboard/server.py 8766
```

Open:

```text
http://127.0.0.1:8766
```

### Private Local Configuration

API credentials and analytics data must stay local and must not be committed.

Private local files include:

- `.env`
- Google OAuth credentials
- Google API keys
- Raw data and SQLite databases under `data/`
- Internal AI memory and project status files

### AI Collaboration Policy

This project may be operated by multiple AI tools, including Codex, Claude Code, and Google Antigravity.

Only generic, data-free work prompts should be uploaded. Project-building plans, internal handoffs, internal AI memory, API setup details, and concrete analysis data should remain local.

Prompt rules:

- Prompts may describe analysis methods and output formats.
- Prompts must not include real clicks, impressions, rankings, sessions, private URL lists, or API responses.
- Prompts must not include API keys, tokens, account secrets, or private user data.
- Prompts should instruct AI to read local data sources instead of hardcoding metrics in the prompt.

### Cloud Database Recommendation

If a cloud database is needed later, Supabase Postgres is the recommended first option. It is a good fit for structured SEO facts, task state, AI workflow records, and future frontend access.

Before cloud migration:

- Stabilize the local SQLite model.
- Confirm that private SEO data may be stored in a third-party cloud service.
- Keep secrets in local `.env` files or a secure cloud secret manager.

### Pre-Commit Safety Check

Before committing:

```powershell
git status --short --ignored
git check-ignore -v .env data .ai PROJECT_STATUS.md CHANGELOG.md
```

Confirm that `.env`, `data/`, `.ai/`, project status files, and real data are ignored before pushing.
