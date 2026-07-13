import { Activity, Bot, Cloud, Database, Gauge, RefreshCw, Search, Settings, Zap } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

type Json = Record<string, any>;
type View = "overview" | "gsc" | "ga4" | "pagespeed" | "crux" | "tasks" | "operations" | "settings";
const views: { id: View; label: string; icon: React.ReactNode }[] = [
  { id: "overview", label: "Overview", icon: <Activity size={17} /> }, { id: "gsc", label: "GSC workbench", icon: <Search size={17} /> },
  { id: "ga4", label: "GA4 behavior", icon: <Gauge size={17} /> }, { id: "pagespeed", label: "PageSpeed", icon: <Zap size={17} /> },
  { id: "crux", label: "CrUX field data", icon: <Cloud size={17} /> }, { id: "tasks", label: "AI tasks", icon: <Bot size={17} /> },
  { id: "operations", label: "Operations", icon: <Database size={17} /> }, { id: "settings", label: "Connections", icon: <Settings size={17} /> },
];

async function api(path: string, options?: RequestInit) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

export function App() {
  const [view, setView] = useState<View>("overview");
  const [data, setData] = useState<Record<string, any>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  async function load(key: string, path: string) {
    setError("");
    try { const value = await api(path); setData(current => ({ ...current, [key]: value })); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Unknown API error"); }
  }
  async function refreshAll() {
    setBusy("reload");
    await Promise.all([load("health", "/api/health"), load("status", "/api/status"), load("storage", "/api/storage/overview"), load("gsc", "/api/gsc/explorer"), load("ga4", "/api/ga4/analytics"), load("pagespeed", "/api/pagespeed/history"), load("crux", "/api/crux/summary"), load("tasks", "/api/ai/tasks")]);
    setBusy("");
  }
  useEffect(() => { void refreshAll(); }, []);
  return <main className="app">
    <aside className="sidebar"><div className="brand"><span className="brandMark">E</span><div><strong>SEO Data Console</strong><small>Independent React/FastAPI</small></div></div>
      <nav>{views.map(item => <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => setView(item.id)}>{item.icon}{item.label}</button>)}</nav>
    </aside>
    <section className="content"><header className="topbar"><div><p className="eyebrow">LOCAL-FIRST SEO OPERATIONS</p><h1>{views.find(item => item.id === view)?.label}</h1><p className="subtitle">Cached raw exports and SQLite are authoritative. Source sync is always an explicit action.</p></div><button className="primary" onClick={() => void refreshAll()} disabled={!!busy}><RefreshCw size={17} /> Reload cached data</button></header>
      {error && <div className="alert">API error: {error}</div>}
      {view === "overview" && <Overview data={data} navigate={setView} />}
      {view === "gsc" && <Gsc initial={data.gsc} onData={value => setData(current => ({ ...current, gsc: value }))} setError={setError} />}
      {view === "ga4" && <Ga4 initial={data.ga4} />}
      {view === "pagespeed" && <PageSpeed initial={data.pagespeed} />}
      {view === "crux" && <Crux initial={data.crux} />}
      {view === "tasks" && <Tasks initial={data.tasks} onRefresh={() => load("tasks", "/api/ai/tasks")} />}
      {view === "operations" && <Operations initial={data.storage} />}
      {view === "settings" && <Connections initial={data.status} />}
    </section>
  </main>;
}

function Overview({ data, navigate }: { data: Json; navigate: (view: View) => void }) {
  const gsc = data.gsc || {}, ga4 = data.ga4 || {}, ps = data.pagespeed || {}, crux = data.crux || {}, storage = data.storage || {};
  return <><section className="kpis"><Metric label="GSC clicks" value={fmt(gsc.totals?.clicks)} detail={gsc.metadata?.freshness || "No cache"} /><Metric label="GA4 sessions" value={fmt(ga4.totals?.sessions)} detail={ga4.metadata?.primaryConversions || "Conversions unknown"} /><Metric label="PageSpeed runs" value={fmt(ps.runs?.length)} detail={`${ps.runs?.filter((r: Json) => r.status === "failed").length || 0} failed`} /><Metric label="CrUX" value={crux.displayStatus || "Loading"} detail={crux.message} tone={crux.status === "no_data" ? "warn" : "good"} /></section>
    <Panel title="What requires attention"><div className="actionGrid"><Action title="Analyze cached search performance" detail={gsc.comparison?.status === "unavailable" ? "Comparison baseline is outside cached coverage." : "Review contribution and query/page drivers."} onClick={() => navigate("gsc")} /><Action title="Review lab failures" detail="Failed Lighthouse runs are separated from real scores." onClick={() => navigate("pagespeed")} /><Action title="Check data operations" detail={storage.database?.cloudDegraded ? "Cloud is degraded; local continuity remains available." : "Review freshness, quota and sync history."} onClick={() => navigate("operations")} /></div></Panel>
    <Panel title="Source health"><Table rows={[{ source: "GSC", state: gsc.status, cache: gsc.metadata?.sourceFile, limitation: gsc.metadata?.limitations?.[0] }, { source: "GA4", state: ga4.status, cache: ga4.sourceFile, limitation: ga4.metadata?.limitations?.[0] }, { source: "PageSpeed", state: ps.status, cache: ps.runs?.[0]?.rawPath, limitation: ps.metadata?.failureSemantics }, { source: "CrUX", state: crux.displayStatus, cache: crux.sourceFile, limitation: crux.message }]} columns={["source", "state", "cache", "limitation"]} /></Panel></>;
}

function Gsc({ initial, onData, setError }: { initial: Json; onData: (value: Json) => void; setError: (value: string) => void }) {
  const [query, setQuery] = useState(""), [page, setPage] = useState(""), [preset, setPreset] = useState("28"), [grain, setGrain] = useState("day"), [comparison, setComparison] = useState("previous_period"), [tab, setTab] = useState("query"), [selected, setSelected] = useState<Json | null>(null), [busy, setBusy] = useState(false);
  const data = initial || {};
  async function apply() { setBusy(true); try { const params = new URLSearchParams({ query, page, preset, grain, comparison, limit: "100" }); onData(await api(`/api/gsc/explorer?${params}`)); } catch (cause) { setError(cause instanceof Error ? cause.message : "Request failed"); } finally { setBusy(false); } }
  async function sync() { if (!confirm("Sync GSC now? This uses Google API quota.")) return; setBusy(true); try { await api("/api/gsc/sync", { method: "POST" }); await apply(); } finally { setBusy(false); } }
  function exportCsv() { const rows = data.tables?.[tab] || []; const meta = data.metadata || {}; const columns = rows.length ? Object.keys(rows[0]) : []; const lines = [`# source=${meta.source || ""}`, `# range=${JSON.stringify(data.scope?.range || {})}`, `# comparison=${JSON.stringify(data.comparison || {})}`, `# filters=${JSON.stringify(data.scope?.filters || [])}`, `# timezone=${meta.timezone || ""}`, columns.join(","), ...rows.map((row: Json) => columns.map(key => csv(row[key])).join(","))]; download(`gsc-${tab}.csv`, lines.join("\n")); }
  return <><Panel title="Scope and comparison"><div className="controls"><label>Query<input value={query} onChange={e => setQuery(e.target.value)} placeholder="contains…" /></label><label>Page<input value={page} onChange={e => setPage(e.target.value)} placeholder="URL contains…" /></label><label>Range<select value={preset} onChange={e => setPreset(e.target.value)}><option value="7">Last 7 days</option><option value="28">Last 28 days</option><option value="90">Last 90 days</option></select></label><label>Comparison<select value={comparison} onChange={e => setComparison(e.target.value)}><option value="previous_period">Previous period</option><option value="none">None</option></select></label><label>Grain<select value={grain} onChange={e => setGrain(e.target.value)}><option value="day">Day</option><option value="week">Week</option><option value="month">Month</option></select></label><button className="primary" onClick={() => void apply()} disabled={busy}>Apply cached scope</button><button onClick={() => void sync()} disabled={busy}>Sync source</button></div><p className="notice">Comparison: <strong>{data.comparison?.status || "unknown"}</strong>. {data.metadata?.limitations?.join(" ")}</p></Panel>
    <section className="kpis"><Metric label="Clicks" value={fmt(data.totals?.clicks)} detail={delta(data.deltas?.delta_clicks)} /><Metric label="Impressions" value={fmt(data.totals?.impressions)} detail={delta(data.deltas?.delta_impressions)} /><Metric label="CTR" value={pct(data.totals?.ctr)} detail={delta(data.deltas?.delta_ctr, true)} /><Metric label="Avg position" value={fmt(data.totals?.position)} detail={delta(data.deltas?.delta_position)} /></section>
    <Panel title="Trend"><MiniChart rows={data.trend || []} metric="clicks" /></Panel>
    <Panel title="Scoped rows"><div className="tabs">{["query", "page", "date"].map(name => <button className={tab === name ? "active" : ""} onClick={() => setTab(name)} key={name}>{name}</button>)}<button onClick={exportCsv}>Export CSV + metadata</button></div><Table rows={data.tables?.[tab] || []} columns={["label", "clicks", "impressions", "ctr", "position", "delta_clicks", "click_contribution"]} onRow={setSelected} /></Panel>
    {selected && <Panel title="Drill-down"><p className="mono">{selected.label}</p><div className="controls"><button onClick={() => { tab === "query" ? setQuery(selected.label) : setPage(selected.label); setSelected(null); }}>Filter by value</button><button onClick={async () => { await api("/api/ai/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ taskType: `gsc_${tab}_analysis`, title: `Analyze ${selected.label}`, scope: data.scope, evidence: selected }) }); alert("Scoped AI task created."); }}>Create scoped AI task</button></div></Panel>}
  </>;
}

function Ga4({ initial }: { initial: Json }) { const data = initial || {}; const [channel, setChannel] = useState(""); const rows = channel ? (data.rows || []).filter((row: Json) => String(row.sessionDefaultChannelGroup).includes(channel)) : data.channels || []; return <><section className="kpis"><Metric label="Sessions" value={fmt(data.totals?.sessions)} /><Metric label="Users" value={fmt(data.totals?.totalUsers)} /><Metric label="Views" value={fmt(data.totals?.screenPageViews)} /><Metric label="Engagement" value={pct(data.totals?.engagementRate)} detail={data.metadata?.primaryConversions} /></section><Panel title="Behavior trend"><MiniChart rows={data.trend || []} metric="sessions" /></Panel><Panel title="Channels and rows"><label>Channel <select value={channel} onChange={e => setChannel(e.target.value)}><option value="">All channels</option>{(data.filters?.channels || []).map((item: string) => <option key={item}>{item}</option>)}</select></label><Table rows={rows} columns={["sessionDefaultChannelGroup", "date", "sessions", "totalUsers", "screenPageViews", "engagedSessions", "engagementRate"]} /></Panel><p className="notice">{data.metadata?.limitations?.join(" ")}</p></>; }
function PageSpeed({ initial }: { initial: Json }) { const data = initial || {}; const [strategy, setStrategy] = useState(""); const runs = (data.runs || []).filter((run: Json) => !strategy || run.strategy === strategy); return <><Panel title="Lab monitoring"><div className="controls"><label>Device<select value={strategy} onChange={e => setStrategy(e.target.value)}><option value="">All</option><option value="mobile">Mobile</option><option value="desktop">Desktop</option></select></label></div><p className="notice">{data.metadata?.failureSemantics}</p><Table rows={runs} columns={["displayStatus", "url", "strategy", "fetchedAt", "isStale", "scores", "metrics", "error"]} /></Panel><Panel title="Priority page monitoring"><Table rows={data.pages || []} columns={["url", "clicks", "impressions", "tested", "latestFetchedAt", "isStale"]} /></Panel></>; }
function Crux({ initial }: { initial: Json }) { const data = initial || {}; return <Panel title={data.displayStatus || "CrUX"}><div className={`state ${data.status === "no_data" ? "warn" : "good"}`}>{data.message || "Loading cached state…"}</div>{data.summary && <pre>{JSON.stringify(data.summary, null, 2)}</pre>}</Panel>; }
function Tasks({ initial, onRefresh }: { initial: Json[]; onRefresh: () => void }) { return <Panel title="Recent scope-aware AI tasks"><button onClick={onRefresh}>Refresh history</button><Table rows={initial || []} columns={["name", "modified", "path", "bytes"]} /></Panel>; }
function Operations({ initial }: { initial: Json }) { const data = initial || {}; return <><section className="kpis"><Metric label="SQLite" value={data.localBackup?.sqlite?.exists ? "Available" : "Missing"} detail={data.localBackup?.sqlite?.path} tone={data.localBackup?.sqlite?.exists ? "good" : "bad"} /><Metric label="Cloud replica" value={data.cloud?.ok ? "Healthy" : "Optional/degraded"} detail={data.cloud?.message} tone={data.cloud?.ok ? "good" : "warn"} /><Metric label="Recent runs" value={fmt(data.recentRuns?.length)} /><Metric label="Backup" value={data.localBackup?.latestBackup?.backupId || "None"} /></section><Panel title="Quota and freshness"><Table rows={data.quota?.sources || []} columns={["source", "freshness", "todayRuns", "estimatedCallsToday", "latestSuccessAt", "recommendation"]} /></Panel><Panel title="Recent sync history"><Table rows={data.recentRuns || []} columns={["source", "status", "created_at", "raw_path", "error", "summary"]} /></Panel><div className="grid"><Panel title="Raw cache"><Table rows={Object.entries(data.localBackup?.rawDirectories || {}).map(([source, item]: any) => ({ source, ...item }))} columns={["source", "files", "bytes", "latestFile", "path"]} /></Panel><Panel title="Cloud tables"><Table rows={Object.entries(data.cloud?.tableCounts || {}).map(([table, rows]) => ({ table, rows }))} columns={["table", "rows"]} /></Panel></div></>; }
function Connections({ initial }: { initial: Json }) { const env = initial?.env || {}; return <Panel title="Masked connection settings"><p className="notice">Secrets are masked. Sync actions remain explicit in each source view.</p><Table rows={Object.entries(env).map(([key, value]: any) => ({ key, configured: value.configured, value: value.value }))} columns={["key", "configured", "value"]} /></Panel>; }

function Metric({ label, value, detail, tone }: { label: string; value: string; detail?: string; tone?: string }) { return <article className={`metric ${tone || ""}`}><span>{label}</span><strong>{value}</strong><small>{detail || "-"}</small></article>; }
function Panel({ title, children }: { title: string; children: React.ReactNode }) { return <section className="panel"><h2>{title}</h2>{children}</section>; }
function Action({ title, detail, onClick }: { title: string; detail: string; onClick: () => void }) { return <button className="action" onClick={onClick}><strong>{title}</strong><span>{detail}</span></button>; }
function Table({ rows, columns, onRow }: { rows: Json[]; columns: string[]; onRow?: (row: Json) => void }) { const [search, setSearch] = useState(""); const visible = useMemo(() => (rows || []).filter(row => JSON.stringify(row).toLowerCase().includes(search.toLowerCase())), [rows, search]); return <><input className="tableSearch" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search rows…" /><div className="tableWrap"><table><thead><tr>{columns.map(column => <th key={column}>{column}</th>)}</tr></thead><tbody>{visible.map((row, index) => <tr key={index} onClick={() => onRow?.(row)} className={onRow ? "clickable" : ""}>{columns.map(column => <td key={column} title={cell(row[column])}>{cell(row[column])}</td>)}</tr>)}</tbody></table>{!visible.length && <p className="empty">No data in this scope.</p>}</div></>; }
function MiniChart({ rows, metric }: { rows: Json[]; metric: string }) { const values = rows.map(row => Number(row[metric] || 0)); const max = Math.max(...values, 1); return <div className="chart" aria-label={`${metric} trend`}>{rows.map((row, index) => <div className="bar" key={index} style={{ height: `${Math.max((Number(row[metric] || 0) / max) * 100, 2)}%` }} title={`${row.label || row.date}: ${row[metric]}`}><span>{row.label || row.date}</span></div>)}</div>; }
function fmt(value: any) { return value === undefined || value === null || value === "" ? "-" : new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(Number(value)); }
function pct(value: any) { return value === undefined ? "-" : `${(Number(value) * 100).toFixed(2)}%`; }
function delta(value: any, percent = false) { return value === undefined || value === null ? "Comparison unavailable" : `${Number(value) > 0 ? "+" : ""}${percent ? pct(value) : fmt(value)} vs comparison`; }
function cell(value: any) { if (value === null || value === undefined || value === "") return "-"; if (typeof value === "number") return fmt(value); if (typeof value === "object") return JSON.stringify(value); return String(value); }
function csv(value: any) { const text = cell(value); return `"${text.replaceAll('"', '""')}"`; }
function download(name: string, content: string) { const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" })); link.download = name; link.click(); URL.revokeObjectURL(link.href); }
