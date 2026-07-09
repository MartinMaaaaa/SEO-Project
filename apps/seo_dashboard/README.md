# SEO Dashboard

Local web dashboard for this SEO operations project. The UI is Chinese and dark-mode by default; GSC keywords, page URLs, and generated AI prompts remain English where that is more useful for execution.

## Features

- Reads cached Google Search Console exports from `data/gsc/raw/`.
- Shows core GSC metrics, trend chart, top queries, top pages, and optimization opportunities.
- Syncs GSC data through the existing read-only `tools/gsc_cli.py` connector.
- Separates human-facing operations documents from AI/system documents.
- Generates English AI task prompt files under `.ai/runtime_tasks/`.
- Includes an API roadmap in the project root: `API_ROADMAP.md`.

## Run

Recommended for daily use:

```text
Double-click 启动SEO控制台.bat in the project root.
```

This opens a dedicated server window and then opens the dashboard in your browser.

```powershell
python apps/seo_dashboard/server.py
```

Or:

```powershell
powershell -ExecutionPolicy Bypass -File apps/seo_dashboard/start_dashboard.ps1
```

Open:

```text
http://127.0.0.1:8766
```

Stop:

```text
Close the window named "SEO Dashboard Server", or double-click 停止SEO控制台.bat.
```

```powershell
powershell -ExecutionPolicy Bypass -File apps/seo_dashboard/stop_dashboard.ps1
```

## Notes

- No credentials are sent to the browser.
- The browser calls the local Python server, and the server calls `tools/gsc_cli.py`.
- GSC exports remain local and are ignored by git.
- This is intentionally dependency-free for the first version. It can later be moved to React/Vite and SQLite/Postgres when needed.
