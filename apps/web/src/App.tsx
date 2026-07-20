import { Activity, Bot, Gauge, Languages, Menu, RefreshCw, Search, ServerCog, Settings, Sparkles, X, Zap } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { AnalysisChart, type ChartSeries } from "./components/AnalysisChart";
import { ChartStateFixtures } from "./components/ChartStateFixtures";
import { PageExperienceWorkbench } from "./components/PageExperienceWorkbench";
import { ActionBar, DeviceToggle, Disclosure, KpiCard, PageHeader, PageSelector, RunComparisonFrame, StatePanel, StatusBadge, type Tone } from "./components/Ui";
import { localizeReason, useI18n } from "./i18n";

type Json = Record<string, any>;
type View = "overview" | "gsc" | "ga4" | "experience" | "tasks" | "operations" | "settings";
type NavItem = { id: View; label: string; icon: React.ReactNode };

async function api(path: string, options?: RequestInit) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

export function App() {
  const { language, setLanguage, t } = useI18n();
  const fixtureMode = new URLSearchParams(window.location.search).get("chartFixtures") === "1";
  const navGroups: { id: string; label: string; items: NavItem[]; utility?: boolean }[] = [
    { id: "workspace", label: t("workspace"), items: [
      { id: "overview", label: t("overview"), icon: <Activity size={18} /> },
      { id: "gsc", label: t("searchPerformance"), icon: <Search size={18} /> },
      { id: "ga4", label: t("organicBehavior"), icon: <Gauge size={18} /> },
      { id: "experience", label: t("pageExperience"), icon: <Zap size={18} /> },
    ] },
    { id: "work", label: t("work"), items: [
      { id: "tasks", label: t("tasks"), icon: <Bot size={18} /> },
    ] },
    { id: "utility", label: t("utility"), utility: true, items: [
      { id: "operations", label: t("operations"), icon: <ServerCog size={18} /> },
      { id: "settings", label: t("settings"), icon: <Settings size={18} /> },
    ] },
  ];
  const views = navGroups.flatMap(group => group.items);
  const [view, setView] = useState<View>("overview");
  const [data, setData] = useState<Record<string, any>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [navOpen, setNavOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const navDialogRef = useRef<HTMLDialogElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  async function load(key: string, path: string) {
    setError("");
    try {
      const value = await api(path);
      setData(current => ({ ...current, [key]: value }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unknown API error");
    }
  }

  async function refreshAll() {
    setBusy("reload");
    await Promise.all([
      load("health", "/api/health"), load("status", "/api/status"), load("storage", "/api/storage/overview"),
      load("gsc", "/api/gsc/explorer"), load("ga4", "/api/ga4/analytics"), load("pagespeed", "/api/pagespeed/history"),
      load("crux", "/api/crux/summary"), load("tasks", "/api/ai/tasks"),
    ]);
    setBusy("");
  }

  useEffect(() => { if (!fixtureMode) void refreshAll(); }, [fixtureMode]);
  useEffect(() => {
    const dialog = navDialogRef.current;
    if (!dialog) return;
    if (navOpen && !dialog.open) { dialog.showModal(); closeButtonRef.current?.focus(); }
    if (!navOpen && dialog.open) dialog.close();
  }, [navOpen]);

  if (fixtureMode) return <ChartStateFixtures locale={language} />;

  const activeItem = views.find(item => item.id === view);
  const pageDescriptions: Record<View, string> = {
    overview: t("overviewPurpose"), gsc: t("gscPurpose"), ga4: t("ga4Purpose"), experience: t("experiencePurpose"),
    tasks: t("tasksPurpose"), operations: t("operationsPurpose"), settings: t("settingsPurpose"),
  };
  const globalTone: Tone = error ? "bad" : data.health?.ok ? "good" : "info";
  const navigate = (next: View) => { setView(next); setNavOpen(false); };
  const navigation = (mobile = false) => <nav className={mobile ? "mobileNavigation" : "groupedNavigation"} aria-label={t("mainNavigation")}>
    {navGroups.map(group => <section className={`navGroup ${group.utility ? "utility" : ""}`} key={group.id}>
      <p>{group.label}</p>
      {group.items.map(item => <button key={item.id} className={view === item.id ? "active" : ""} aria-current={view === item.id ? "page" : undefined} onClick={() => navigate(item.id)}>{item.icon}<span>{item.label}</span></button>)}
    </section>)}
  </nav>;

  return <main className="app">
    <aside className="sidebar">
      <div className="brand"><span className="brandMark">E</span><div><strong>SEO Data Console</strong><small>{t("independent")}</small></div></div>
      {navigation()}
      <div className="sidebarStatus"><StatusBadge tone={globalTone}>{error ? t("attentionNeeded") : data.health?.ok ? t("localReady") : t("loadingCache")}</StatusBadge><small>{t("localFirstShort")}</small></div>
    </aside>
    <dialog ref={navDialogRef} className="mobileNavDialog" aria-labelledby="mobile-nav-title" onClose={() => { setNavOpen(false); menuButtonRef.current?.focus(); }} onCancel={() => setNavOpen(false)}>
      <div className="mobileNavHeader"><div><span className="brandMark">E</span><strong id="mobile-nav-title">SEO Data Console</strong></div><button ref={closeButtonRef} className="iconButton" aria-label={t("closeNavigation")} onClick={() => setNavOpen(false)}><X size={20} /></button></div>
      {navigation(true)}
      <div className="mobileNavFooter"><StatusBadge tone={globalTone}>{error ? t("attentionNeeded") : data.health?.ok ? t("localReady") : t("loadingCache")}</StatusBadge></div>
    </dialog>
    <section className="content">
      <div className="mobileTopbar"><button ref={menuButtonRef} className="iconButton menuButton" aria-label={t("openNavigation")} aria-expanded={navOpen} onClick={() => setNavOpen(true)}><Menu size={20} /></button><strong>{activeItem?.label}</strong><StatusBadge tone={globalTone}>{data.health?.ok ? t("ready") : t("status")}</StatusBadge></div>
      <PageHeader eyebrow={t("eyebrow")} title={activeItem?.label || "SEO Data Console"} description={pageDescriptions[view]} status={<StatusBadge tone={globalTone}>{error ? t("attentionNeeded") : data.health?.ok ? t("localReady") : t("loading")}</StatusBadge>} actions={<>
        <button className="languageButton" onClick={() => setLanguage(language === "zh-CN" ? "en" : "zh-CN")}><Languages size={17} />{t("language")}</button>
        {view === "overview" && <button className="primary" onClick={() => void refreshAll()} disabled={!!busy}><RefreshCw size={17} />{t("refreshOverview")}</button>}
      </>} />
      {error && <div className="alert">{t("apiError")}: {error}</div>}
      {view === "overview" && <Overview data={data} navigate={navigate} />}
      {view === "gsc" && <Gsc initial={data.gsc} onData={value => setData(current => ({ ...current, gsc: value }))} setError={setError} />}
      {view === "ga4" && <Ga4 initial={data.ga4} onData={value => setData(current => ({ ...current, ga4: value }))} setError={setError} />}
      {view === "experience" && <PageExperienceWorkbench initialPagespeed={data.pagespeed} initialCrux={data.crux} />}
      {view === "tasks" && <Tasks initial={data.tasks} onRefresh={() => load("tasks", "/api/ai/tasks")} />}
      {view === "operations" && <Operations initial={data.storage} />}
      {view === "settings" && <Connections initial={data.status} />}
    </section>
  </main>;
}

function Overview({ data, navigate }: { data: Json; navigate: (view: View) => void }) {
  const { language, t } = useI18n();
  const gsc = data.gsc || {}, ga4 = data.ga4 || {}, ps = data.pagespeed || {}, crux = data.crux || {}, storage = data.storage || {};
  const failedRuns = ps.runs?.filter((row: Json) => row.status !== "success").length || 0;
  return <>
    <section className="overviewLead">
      <div><p className="sectionKicker">{t("dailyCommand")}</p><h2>{t("attention")}</h2><p>{t("overviewLead")}</p></div>
      <KiroAssistant />
    </section>
    <section className="kpis overviewKpis">
      <Metric label="GSC Clicks" value={fmt(gsc.totals?.clicks, language)} detail={gsc.comparison?.status === "unavailable" ? t("comparisonUnavailable") : delta(gsc.deltas?.delta_clicks, false, language, t)} tone="info" />
      <Metric label="GA4 Sessions" value={fmt(ga4.totals?.sessions, language)} detail={ga4.metadata?.conversionState === "available" ? t("conversionDataAvailable") : t("conversionsUnknown")} tone="info" />
      <Metric label={t("pageSpeedRuns")} value={fmt(ps.runs?.length, language)} detail={`${failedRuns} ${t("failed")}`} tone={failedRuns ? "bad" : "good"} />
      <Metric label="CrUX" value={crux.displayStatus || t("loading")} detail={crux.status === "no_data" ? t("labStillAvailable") : crux.message} tone={crux.status === "no_data" ? "warn" : "good"} />
    </section>
    {(storage.database?.cloudDegraded || failedRuns > 0) && <StatePanel tone="warn" title={t("attentionNeeded")} detail={storage.database?.cloudDegraded ? t("cloudDegraded") : t("failureSeparated")} />}
    <Panel title={t("quickWorkspaces")} eyebrow={t("oneClickAnalysis")}><div className="actionGrid">
      <Action icon={<Search size={18} />} title={t("searchPerformance")} detail={gsc.comparison?.status === "unavailable" ? t("comparisonOutside") : t("reviewDrivers")} onClick={() => navigate("gsc")} />
      <Action icon={<Gauge size={18} />} title={t("organicBehavior")} detail={t("reviewOrganicBehavior")} onClick={() => navigate("ga4")} />
      <Action icon={<Zap size={18} />} title={t("pageExperience")} detail={failedRuns ? t("reviewFailures") : t("reviewLabField")} onClick={() => navigate("experience")} />
    </div></Panel>
    <Panel title={t("sourceHealth")} eyebrow={t("freshnessAtGlance")}><div className="sourceHealthGrid">
      <SourceHealthCard source="GSC" status={gsc.status} detail={gsc.metadata?.latestCompleteDate || t("unknown")} />
      <SourceHealthCard source="GA4" status={ga4.status} detail={ga4.metadata?.latestCompleteDate || t("unknown")} />
      <SourceHealthCard source="PageSpeed" status={failedRuns ? "partial" : ps.status} detail={`${ps.runs?.length || 0} ${t("runs")}`} />
      <SourceHealthCard source="CrUX" status={crux.status} detail={crux.displayStatus || t("unknown")} />
    </div></Panel>
    <Disclosure title={t("technicalSourceEvidence")} summary={t("pathsAndLimitations")} count={4}>
      <Table rows={[
        { source: "GSC", state: gsc.status, cache: gsc.metadata?.sourceFile, limitation: gsc.metadata?.limitations?.[0] },
        { source: "GA4", state: ga4.status, cache: ga4.sourceFile, limitation: ga4.metadata?.limitations?.[0] },
        { source: "PageSpeed", state: ps.status, cache: ps.runs?.[0]?.rawPath, limitation: ps.metadata?.failureSemantics },
        { source: "CrUX", state: crux.displayStatus, cache: crux.sourceFile, limitation: crux.message },
      ]} columns={["source", "state", "cache", "limitation"]} technical />
    </Disclosure>
  </>;
}

function KiroAssistant() {
  return <div className="kiroAssistant" aria-hidden="true">
    <span className="kiroOrbit orbitOuter" />
    <span className="kiroOrbit orbitInner" />
    <span className="kiroGrid" />
    <span className="kiroSprite" />
    <span className="kiroStatus"><Sparkles size={12} />SEO OPS</span>
  </div>;
}

function SourceHealthCard({ source, status, detail }: { source: string; status?: string; detail?: React.ReactNode }) {
  const { t } = useI18n();
  const tone = sourceStatusTone(status);
  return <article className="sourceHealthCard"><div><strong>{source}</strong><StatusBadge tone={tone}>{status || t("unknown")}</StatusBadge></div><small>{detail || "—"}</small></article>;
}

const gscTabs = ["query", "page", "date", "country", "device", "searchAppearance"];
const gscChartSeries: ChartSeries[] = [
  { key: "clicks", label: "Clicks", color: "#36c9a5", unit: "count" },
  { key: "impressions", label: "Impressions", color: "#75a7ff", unit: "count" },
  { key: "ctr", label: "CTR", color: "#f2b84b", unit: "ratio" },
  { key: "position", label: "Position", color: "#d991ff", unit: "rank", invert: true },
];
const ga4ChartSeries: ChartSeries[] = [
  { key: "sessions", label: "Sessions", color: "#36c9a5", unit: "count" },
  { key: "totalUsers", label: "Users", color: "#75a7ff", unit: "count" },
  { key: "newUsers", label: "New Users", color: "#89d38c", unit: "count" },
  { key: "screenPageViews", label: "Views", color: "#f2b84b", unit: "count" },
  { key: "engagedSessions", label: "Engaged Sessions", color: "#d991ff", unit: "count" },
  { key: "engagementRate", label: "Engagement Rate", color: "#ff8d71", unit: "ratio" },
  { key: "keyEvents", label: "Key events / Conversions", color: "#53d7e8", unit: "count" },
];

function Gsc({ initial, onData, setError }: { initial: Json; onData: (value: Json) => void; setError: (value: string) => void }) {
  const { language, t } = useI18n();
  const [query, setQuery] = useState("");
  const [page, setPage] = useState("");
  const [preset, setPreset] = useState("28");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [grain, setGrain] = useState("day");
  const [comparison, setComparison] = useState("previous_period");
  const [tab, setTab] = useState("query");
  const [selected, setSelected] = useState<Json | null>(null);
  const [detail, setDetail] = useState<Json | null>(null);
  const [detailBusy, setDetailBusy] = useState(false);
  const [opportunityTab, setOpportunityTab] = useState("nearFirstPage");
  const [chartMetric, setChartMetric] = useState("clicks");
  const [visibleSeries, setVisibleSeries] = useState<string[]>(["clicks", "impressions"]);
  const displayMode = "unit_lanes" as const;
  const [selectedPointKey, setSelectedPointKey] = useState<string | null>(null);
  const [chartError, setChartError] = useState("");
  const [tableSort, setTableSort] = useState("clicks");
  const [tableSearch, setTableSearch] = useState("");
  const [savedViews, setSavedViews] = useState<Json[]>([]);
  const [selectedViewId, setSelectedViewId] = useState<number | null>(null);
  const [viewName, setViewName] = useState("");
  const [viewDescription, setViewDescription] = useState("");
  const [viewFavorite, setViewFavorite] = useState(false);
  const [annotations, setAnnotations] = useState<Json[]>([]);
  const [annotationDate, setAnnotationDate] = useState(new Date().toISOString().slice(0, 10));
  const [annotationTime, setAnnotationTime] = useState("");
  const [annotationTitle, setAnnotationTitle] = useState("");
  const [annotationType, setAnnotationType] = useState("note");
  const [affectedPageGroup, setAffectedPageGroup] = useState("");
  const [annotationNotes, setAnnotationNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [syncResult, setSyncResult] = useState<Json | null>(null);
  const data = initial || {};
  const capabilities = data.metadata?.dimensionCapabilities || {};
  const tableMetricColumns = visibleSeries.flatMap(metric => [metric, `previous_${metric}`, `delta_${metric}`, `change_${metric}`]);
  const tableColumns = ["label", ...(tab === "date" ? ["comparisonLabel"] : []), ...tableMetricColumns, "movement", ...(visibleSeries.includes("clicks") && tab !== "date" ? ["click_contribution"] : [])];

  async function refreshSavedViews() { setSavedViews(await api("/api/saved-views?source=gsc")); }
  async function refreshAnnotations(scope: Json = {}) {
    const params = new URLSearchParams();
    const range = scope.range || data.scope?.range || {};
    if (range.start) params.set("start", range.start);
    if (range.end) params.set("end", range.end);
    if ((scope.query ?? query)) params.set("query", scope.query ?? query);
    if ((scope.page ?? page)) params.set("url", scope.page ?? page);
    setAnnotations(await api(`/api/annotations?${params}`));
  }

  useEffect(() => {
    if (["country", "device", "searchAppearance"].includes(tab) && !capabilities[tab]?.enabled) setTab("query");
  }, [capabilities, tab]);
  useEffect(() => { void refreshSavedViews().catch(cause => setError(cause instanceof Error ? cause.message : "Saved view request failed")); }, []);
  useEffect(() => { if (data.scope) void refreshAnnotations().catch(cause => setError(cause instanceof Error ? cause.message : "Annotation request failed")); }, [data.scope?.range?.start, data.scope?.range?.end]);
  useEffect(() => {
    if (!selected?.label || !["query", "page"].includes(tab)) { setDetail(null); return; }
    let active = true;
    const params = new URLSearchParams({ entityType: tab, value: selected.label, preset, comparison, grain, limit: "100" });
    if (data.scope?.range?.start) params.set("start", data.scope.range.start);
    if (data.scope?.range?.end) params.set("end", data.scope.range.end);
    setDetailBusy(true);
    void api(`/api/gsc/detail?${params}`).then(value => { if (active) setDetail(value); }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : "Detail request failed"); }).finally(() => { if (active) setDetailBusy(false); });
    return () => { active = false; };
  }, [selected?.label, tab, data.scope?.range?.start, data.scope?.range?.end, comparison, grain]);

  async function apply(overrides: Json = {}) {
    setBusy(true);
    setChartError("");
    setSelectedPointKey(null);
    setSelected(null);
    setDetail(null);
    try {
      const next = { query, page, preset, start, end, grain, comparison, sort: tableSort, ...overrides };
      const params = new URLSearchParams({ query: next.query, page: next.page, preset: next.preset, grain: next.grain, comparison: next.comparison, sort: next.sort, limit: "100" });
      if (next.preset === "custom" && next.start && next.end) { params.set("start", next.start); params.set("end", next.end); }
      const value = await api(`/api/gsc/explorer?${params}`);
      onData(value);
      await refreshAnnotations({ range: value.scope?.range, query: next.query, page: next.page });
      return value;
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Request failed";
      setChartError(message);
      setError(message);
    } finally { setBusy(false); }
  }

  function viewConfig(): Json {
    const appliedRange = data.scope?.range;
    const appliedFilters = data.scope?.filters || [];
    return {
      version: 1,
      date: appliedRange ? { mode: "fixed", preset: "custom", start: appliedRange.start, end: appliedRange.end } : { mode: preset === "custom" ? "fixed" : "relative", preset, start, end },
      comparison: { mode: data.comparison?.mode || comparison }, grain: data.scope?.grain || grain,
      filters: appliedFilters,
      chart: { type: "time_series", metric: visibleSeries[0] || chartMetric, visibleSeries, displayMode },
      table: { dimension: tab, search: tableSearch, sort: { field: tableSort, direction: tableSort === "position" ? "asc" : "desc" }, rowLimit: 100 },
      drilldown: { dimension: tab, value: selected?.label || null },
    };
  }

  async function saveView(update = false) {
    if (!viewName.trim()) return;
    setBusy(true);
    try {
      const payload = { name: viewName.trim(), description: viewDescription, source: "gsc", isFavorite: viewFavorite, config: viewConfig() };
      const saved = await api(update && selectedViewId ? `/api/saved-views/${selectedViewId}` : "/api/saved-views", { method: update ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      setSelectedViewId(saved.id); await refreshSavedViews();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Saved view request failed"); }
    finally { setBusy(false); }
  }

  async function loadView(view: Json) {
    const config = view.config || {}, date = config.date || {}, filters = config.filters || [], table = config.table || {}, chart = config.chart || {}, drilldown = config.drilldown || {};
    const nextQuery = filters.find((item: Json) => item.field === "query")?.value || "";
    const nextPage = filters.find((item: Json) => item.field === "page")?.value || "";
    const nextPreset = date.preset || "28", nextGrain = config.grain || "day", nextComparison = config.comparison?.mode || "none", nextSort = table.sort?.field || "clicks";
    setSelectedViewId(view.id); setViewName(view.name); setViewDescription(view.description || ""); setViewFavorite(Boolean(view.isFavorite));
    setQuery(nextQuery); setPage(nextPage); setPreset(nextPreset); setStart(date.start || ""); setEnd(date.end || ""); setGrain(nextGrain); setComparison(nextComparison);
    const restoredSeries = (chart.visibleSeries?.length ? chart.visibleSeries : [chart.metric || "clicks"]).filter((key: string) => gscChartSeries.some(item => item.key === key)).slice(0, 4);
    setTab(table.dimension || "query"); setTableSearch(table.search || ""); setTableSort(nextSort); setChartMetric(restoredSeries[0] || "clicks"); setVisibleSeries(restoredSeries.length ? restoredSeries : ["clicks"]);
    const value = await apply({ query: nextQuery, page: nextPage, preset: nextPreset, start: date.start || "", end: date.end || "", grain: nextGrain, comparison: nextComparison, sort: nextSort });
    setSelected((value?.tables?.[drilldown.dimension || table.dimension] || []).find((row: Json) => row.label === drilldown.value) || null);
  }

  async function removeView(viewId: number) {
    if (!confirm(t("deleteViewConfirm"))) return;
    await api(`/api/saved-views/${viewId}?confirmed=true`, { method: "DELETE" });
    if (selectedViewId === viewId) { setSelectedViewId(null); setViewName(""); setViewDescription(""); }
    await refreshSavedViews();
  }

  async function addAnnotation() {
    if (!annotationTitle.trim()) return;
    await api("/api/annotations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ date: annotationDate, time: annotationTime, title: annotationTitle, type: annotationType, affectedUrl: page, affectedQuery: query, affectedPageGroup, notes: annotationNotes }) });
    setAnnotationTitle(""); setAnnotationNotes(""); await refreshAnnotations();
  }

  async function removeAnnotation(annotationId: number) {
    if (!confirm(t("deleteAnnotationConfirm"))) return;
    await api(`/api/annotations/${annotationId}?confirmed=true`, { method: "DELETE" }); await refreshAnnotations();
  }

  async function sync() {
    if (!confirm(t("syncConfirm"))) return;
    setBusy(true);
    setSyncResult({ status: "in_progress" });
    try {
      const result = await api("/api/gsc/sync", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ force: false }) });
      setSyncResult(result);
      if (["success", "partial"].includes(result.status)) await apply();
    }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Sync failed"); }
    finally { setBusy(false); }
  }

  function exportCsv() {
    const rows = data.tables?.[tab] || [];
    const meta = data.metadata || {};
    const columns = rows.length ? Object.keys(rows[0]) : [];
    const lines = [
      `# source=${meta.source || ""}`, `# range=${JSON.stringify(data.scope?.range || {})}`,
      `# comparison=${JSON.stringify(data.comparison || {})}`, `# filters=${JSON.stringify(data.scope?.filters || [])}`,
      `# dimension=${tab}`, `# dimension_contract=${JSON.stringify(capabilities[tab] || {})}`, `# timezone=${meta.timezone || ""}`,
      `# metrics=${JSON.stringify(visibleSeries)}`, `# display_mode=${displayMode}`, `# sort=${tableSort}`,
      `# row_count=${rows.length}`, `# latest_complete_date=${meta.latestCompleteDate || ""}`, `# extracted_at=${new Date().toISOString()}`,
      `# limitations=${JSON.stringify(meta.limitations || [])}`,
      columns.join(","), ...rows.map((row: Json) => columns.map(key => csv(row[key])).join(",")),
    ];
    download(`gsc-${tab}.csv`, lines.join("\n"));
  }

  return <>
    <Panel title={t("scopeComparison")} eyebrow={t("cachedAnalysisScope")} priority="primary">
      <div className="controls">
        <label>{t("query")}<input value={query} onChange={event => setQuery(event.target.value)} placeholder={t("queryPlaceholder")} /></label>
        <label>{t("page")}<input value={page} onChange={event => setPage(event.target.value)} placeholder={t("pagePlaceholder")} /></label>
        <label>{t("range")}<select value={preset} onChange={event => setPreset(event.target.value)}><option value="7">{t("last7")}</option><option value="28">{t("last28")}</option><option value="90">{t("last90")}</option><option value="custom">{t("custom")}</option></select></label>
        {preset === "custom" && <><label>{t("startDate")}<input type="date" value={start} onChange={event => setStart(event.target.value)} /></label><label>{t("endDate")}<input type="date" value={end} onChange={event => setEnd(event.target.value)} /></label></>}
        <label>{t("comparison")}<select value={comparison} onChange={event => setComparison(event.target.value)}><option value="previous_period">{t("previousPeriod")}</option><option value="none">{t("none")}</option></select></label>
        <label>{t("grain")}<select value={grain} onChange={event => setGrain(event.target.value)}><option value="day">{t("day")}</option><option value="week">{t("week")}</option><option value="month">{t("month")}</option></select></label>
        <button className="primary" onClick={() => void apply()} disabled={busy}>{t("applyScope")}</button>
        <button onClick={() => void sync()} disabled={busy}>{t("syncSource")}</button>
      </div>
      <div className="scopeChips" aria-label={t("activeScope")}>
        <span>{data.scope?.range?.start || "—"} → {data.scope?.range?.end || "—"}</span>
        <span>{t(data.scope?.grain || grain)}</span>
        {(data.scope?.filters || []).map((filter: Json, index: number) => <span key={`${filter.field}-${index}`}>{filter.field}: {filter.value}</span>)}
        {!(data.scope?.filters || []).length && <span>{t("noActiveFilters")}</span>}
      </div>
      <p className="notice">{t("comparisonStatus")}: <strong>{localizedComparisonStatus(data.comparison?.status, t)}</strong>. {data.metadata?.timezone}</p>
      <SourceFreshness metadata={data.metadata || {}} />
      {syncResult && <SyncResultPanel result={syncResult} />}
    </Panel>
    <DimensionAvailability capabilities={capabilities} />
    <section className="kpis">
      <Metric label={t("clicks")} value={fmt(data.totals?.clicks, language)} detail={delta(data.deltas?.delta_clicks, false, language, t)} />
      <Metric label={t("impressions")} value={fmt(data.totals?.impressions, language)} detail={delta(data.deltas?.delta_impressions, false, language, t)} />
      <Metric label={t("ctr")} value={pct(data.totals?.ctr)} detail={delta(data.deltas?.delta_ctr, true, language, t)} />
      <Metric label={t("avgPosition")} value={fmt(data.totals?.position, language)} detail={delta(data.deltas?.delta_position, false, language, t)} />
    </section>
    <Panel title={t("trend")} eyebrow={t("dailyAnalysis")} priority="primary"><MetricMultiSelect series={gscChartSeries} selected={visibleSeries} onChange={keys => { setVisibleSeries(keys); setChartMetric(keys[0] || "clicks"); }} /> <p className="notice">{t("unitLanesHelp")}</p><AnalysisChart
      rows={data.trend || []}
      comparisonRows={data.comparisonTrend || []}
      comparison={{ status: data.comparison?.status || "none", reason: localizedComparisonReason(data.comparison, t) }}
      series={gscChartSeries}
      visibleSeries={visibleSeries}
      onVisibleSeriesChange={keys => { setVisibleSeries(keys); setChartMetric(keys[0] || "clicks"); }}
      displayMode={displayMode}
      selectedKey={selectedPointKey}
      onSelectedKeyChange={setSelectedPointKey}
      annotations={annotations}
      locale={language}
      title={`GSC ${t("trend")}`}
      state={busy ? "loading" : chartError ? "error" : data.trend?.length ? "ready" : "empty"}
      errorMessage={chartError}
      metadata={{
        range: data.scope?.range,
        comparisonRange: data.comparison?.range,
        timezone: data.metadata?.timezone,
        grain: t(data.scope?.grain || "unknown"),
        freshness: data.metadata?.freshness,
        partial: data.metadata?.dataQuality?.coverageStatus === "partial",
        partialReason: t("partialDataReason"),
        stale: Boolean(data.metadata?.dataQuality?.isStale),
        staleReason: `${t("latestCompleteDate")}: ${data.metadata?.latestCompleteDate || t("unknown")}`,
      }}
    />
      {selectedPointKey && <SelectedTrendPoint current={(data.trend || []).find((row: Json) => row.alignmentKey === selectedPointKey)} comparison={(data.comparisonTrend || []).find((row: Json) => row.alignmentKey === selectedPointKey)} comparisonStatus={data.comparison?.status} />}
    </Panel>
    <Panel title={t("scopedRows")} eyebrow={t("chartTableSameScope")} priority="primary">
      <div className="tabs">{gscTabs.map(name => {
        const capability = capabilities[name];
        const disabled = Boolean(capability && !capability.enabled);
        return <button className={tab === name ? "active" : ""} disabled={disabled} title={disabled ? localizeReason(capability.reason, t) : ""} onClick={() => { setTab(name); setSelected(null); setDetail(null); }} key={name}>{dimensionLabel(name)}</button>;
      })}<button onClick={exportCsv}>{t("exportMetadata")}</button></div>
      <div className="controls"><label>{t("tableSort")}<select value={tableSort} onChange={event => { const value = event.target.value; setTableSort(value); void apply({ sort: value }); }}><option value="clicks">Clicks</option><option value="impressions">Impressions</option><option value="ctr">CTR</option><option value="position">Position</option></select></label></div>
      <Table rows={data.tables?.[tab] || []} columns={tableColumns} onRow={row => {
        if (tab === "date") {
          const point = (data.trend || []).find((item: Json) => row.label >= item.periodStart && row.label <= item.periodEnd);
          setSelectedPointKey(point?.alignmentKey || null);
          setSelected(null);
        } else setSelected(row);
      }} selected={row => tab === "date" && Boolean(selectedPointKey) && (data.trend || []).some((item: Json) => item.alignmentKey === selectedPointKey && row.label >= item.periodStart && row.label <= item.periodEnd)} search={tableSearch} onSearch={setTableSearch} />
    </Panel>
    {selected && (detailBusy ? <Panel title={t("drilldown")}><p>{t("detailLoading")}</p></Panel> : detail ? <GscDetailPanel detail={detail} selected={selected} opportunityTab={opportunityTab} setOpportunityTab={setOpportunityTab} annotations={annotations} selectedPointKey={selectedPointKey} onSelectedPointKeyChange={setSelectedPointKey} onFilter={() => { tab === "query" ? setQuery(selected.label) : setPage(selected.label); setSelected(null); }} onTask={async () => { await api("/api/ai/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ taskType: `gsc_${tab}_analysis`, title: `Analyze ${selected.label}`, scope: { ...data.scope, dimension: tab, relationshipGrain: ["date", "query", "page"] }, evidence: { selected, detail } }) }); alert(t("taskCreated")); }} /> : null)}
    <SavedViewsPanel views={savedViews} selectedId={selectedViewId} name={viewName} description={viewDescription} favorite={viewFavorite} busy={busy} setName={setViewName} setDescription={setViewDescription} setFavorite={setViewFavorite} onSave={() => void saveView(false)} onUpdate={() => void saveView(true)} onLoad={view => void loadView(view)} onDelete={id => void removeView(id)} />
    <AnnotationsPanel annotations={annotations} date={annotationDate} time={annotationTime} title={annotationTitle} type={annotationType} pageGroup={affectedPageGroup} notes={annotationNotes} setDate={setAnnotationDate} setTime={setAnnotationTime} setTitle={setAnnotationTitle} setType={setAnnotationType} setPageGroup={setAffectedPageGroup} setNotes={setAnnotationNotes} onAdd={() => void addAnnotation()} onDelete={id => void removeAnnotation(id)} />
  </>;
}

function DimensionAvailability({ capabilities }: { capabilities: Json }) {
  const { t } = useI18n();
  const unavailable = ["country", "device", "searchAppearance"].filter(name => !capabilities[name]?.enabled).length;
  return <Disclosure title={t("advancedDimensions")} summary={t("dimensionContractSummary")} count={`${3 - unavailable}/3`} tone={unavailable ? "warn" : "good"}><div className="dimensionGrid">{["country", "device", "searchAppearance"].map(name => {
    const item = capabilities[name] || {};
    return <article className={`dimensionCard ${item.enabled ? "enabled" : "disabled"}`} key={name}>
      <div><strong>{dimensionLabel(name)}</strong><span className="badge">{item.enabled ? t("available") : t("unavailable")}</span></div>
      <small>{t("exactGrain")}: {(item.grain || ["date", name]).join(" + ")} · {t("propertyGrain")}</small>
      {!item.enabled && <p>{localizeReason(item.reason || "Requires a compatible GSC collection.", t)}</p>}
    </article>;
  })}</div></Disclosure>;
}

function GscDetailPanel({ detail, selected, opportunityTab, setOpportunityTab, annotations, selectedPointKey, onSelectedPointKeyChange, onFilter, onTask }: {
  detail: Json; selected: Json; opportunityTab: string; setOpportunityTab: (value: string) => void; annotations: Json[];
  selectedPointKey: string | null; onSelectedPointKeyChange: (value: string | null) => void; onFilter: () => void; onTask: () => Promise<void>;
}) {
  const { language, t } = useI18n();
  const groups = detail.opportunities?.groups || {};
  const opportunityNames = ["increased", "declined", "new", "lost", "nearFirstPage"];
  const relatedLabel = detail.entityType === "query" ? t("rankingPages") : t("queryPortfolio");
  return <Panel title={detail.entityType === "query" ? t("keywordDetail") : t("pageDetail")}>
    <p className="mono detailValue">{detail.value}</p>
    <p className="notice">{t("relationshipGrain")} {t("dataFreshness")}: {detail.freshness || t("unknown")}</p>
    <section className="kpis detailKpis">
      <Metric label="Clicks" value={fmt(detail.totals?.clicks, language)} detail={delta(detail.deltas?.delta_clicks, false, language, t)} />
      <Metric label="Impressions" value={fmt(detail.totals?.impressions, language)} detail={delta(detail.deltas?.delta_impressions, false, language, t)} />
      <Metric label="CTR" value={pct(detail.totals?.ctr)} detail={delta(detail.deltas?.delta_ctr, true, language, t)} />
      <Metric label="Position" value={fmt(detail.totals?.position, language)} detail={delta(detail.deltas?.delta_position, false, language, t)} />
    </section>
    <AnalysisChart rows={detail.trend || []} comparisonRows={detail.comparisonTrend || []} comparison={{ status: detail.comparison?.status || "none", reason: localizedComparisonReason(detail.comparison, t) }} series={gscChartSeries} visibleSeries={["clicks", "impressions"]} selectedKey={selectedPointKey} onSelectedKeyChange={onSelectedPointKeyChange} annotations={annotations} locale={language} title={`${detail.entityType === "query" ? t("keywordDetail") : t("pageDetail")} ${t("trend")}`} metadata={{ range: detail.scope?.range, comparisonRange: detail.comparison?.range, timezone: detail.metadata?.timezone, grain: t(detail.metadata?.grain || "unknown"), freshness: detail.freshness, partial: detail.metadata?.dataQuality?.coverageStatus === "partial", partialReason: t("partialDataReason"), stale: Boolean(detail.metadata?.dataQuality?.isStale), staleReason: `${t("latestCompleteDate")}: ${detail.metadata?.latestCompleteDate || t("unknown")}` }} />
    <h3>{relatedLabel}</h3>
    <Table rows={detail.related?.rows || []} columns={["label", "clicks", "impressions", "ctr", "position", "previous_clicks", "delta_clicks", "movement"]} />
    <h3>{t("opportunityGroups")}</h3>
    <div className="tabs opportunityTabs">{opportunityNames.map(name => <button key={name} className={opportunityTab === name ? "active" : ""} onClick={() => setOpportunityTab(name)}>{t(name)} ({detail.opportunities?.counts?.[name] || 0})</button>)}</div>
    {detail.opportunities?.status === "comparison_unavailable" && <p className="notice">{t("comparisonUnavailable")}</p>}
    <Table rows={groups[opportunityTab] || []} columns={["label", "clicks", "impressions", "ctr", "position", "previous_clicks", "delta_clicks", "movement"]} />
    <h3>{t("dimensionSplits")}</h3>
    <DimensionAvailability capabilities={detail.dimensionCapabilities || {}} />
    <div className="controls detailActions"><button onClick={onFilter}>{t("filterByValue")}</button><button onClick={() => void onTask()}>{t("createTask")}</button></div>
    <details><summary>{t("limitations")}</summary><ul>{(detail.limitations || []).map((item: string, index: number) => <li key={index}>{item}</li>)}</ul></details>
  </Panel>;
}

function SelectedTrendPoint({ current, comparison, comparisonStatus }: { current?: Json; comparison?: Json; comparisonStatus?: string }) {
  const { language, t } = useI18n();
  const row = current || comparison;
  if (!row) return null;
  return <section className="selectedTrendDetail" aria-live="polite">
    <div><strong>{t("selectedPeriod")}: {current?.label || comparison?.label}</strong><span>{current ? `${current.periodStart}${current.periodEnd !== current.periodStart ? ` – ${current.periodEnd}` : ""}` : t("currentUnavailable")}</span></div>
    <div className="selectedTrendValues">
      {["clicks", "impressions", "ctr", "position"].map(metric => <span key={metric}><small>{metric === "position" ? t("avgPosition") : metric.toUpperCase()}</small><strong>{metric === "ctr" ? pct(current?.[metric]) : fmt(current?.[metric], language)}</strong>{comparisonStatus === "complete" && <em>{t("previousPeriod")}: {metric === "ctr" ? pct(comparison?.[metric]) : fmt(comparison?.[metric], language)}</em>}</span>)}
    </div>
  </section>;
}

function SavedViewsPanel({ views, selectedId, name, description, favorite, busy, setName, setDescription, setFavorite, onSave, onUpdate, onLoad, onDelete }: {
  views: Json[]; selectedId: number | null; name: string; description: string; favorite: boolean; busy: boolean;
  setName: (value: string) => void; setDescription: (value: string) => void; setFavorite: (value: boolean) => void;
  onSave: () => void; onUpdate: () => void; onLoad: (view: Json) => void; onDelete: (id: number) => void;
}) {
  const { t } = useI18n();
  return <Disclosure title={t("savedAnalysis")} summary={t("savedAnalysisSummary")} count={views.length}>
    <p className="notice">{t("completeState")}</p>
    <div className="controls savedViewEditor">
      <label>{t("viewName")}<input value={name} onChange={event => setName(event.target.value)} /></label>
      <label>{t("viewDescription")}<input value={description} onChange={event => setDescription(event.target.value)} /></label>
      <label className="checkLabel"><input type="checkbox" checked={favorite} onChange={event => setFavorite(event.target.checked)} />{t("favorite")}</label>
      <button className="primary" disabled={busy || !name.trim()} onClick={onSave}>{t("saveNew")}</button>
      <button disabled={busy || !selectedId || !name.trim()} onClick={onUpdate}>{t("updateView")}</button>
    </div>
    <div className="savedList">{views.map(view => <article className={selectedId === view.id ? "savedItem active" : "savedItem"} key={view.id}>
      <div><strong>{view.isFavorite ? "★ " : ""}{view.name}</strong><small>{view.description || view.updatedAt}</small></div>
      <div className="rowActions"><button onClick={() => onLoad(view)}>{t("loadView")}</button><button onClick={() => onDelete(view.id)}>{t("deleteView")}</button></div>
    </article>)}{!views.length && <p className="empty">{t("noSavedViews")}</p>}</div>
  </Disclosure>;
}

function AnnotationsPanel({ annotations, date, time, title, type, pageGroup, notes, setDate, setTime, setTitle, setType, setPageGroup, setNotes, onAdd, onDelete }: {
  annotations: Json[]; date: string; time: string; title: string; type: string; pageGroup: string; notes: string;
  setDate: (value: string) => void; setTime: (value: string) => void; setTitle: (value: string) => void; setType: (value: string) => void;
  setPageGroup: (value: string) => void; setNotes: (value: string) => void; onAdd: () => void; onDelete: (id: number) => void;
}) {
  const { t } = useI18n();
  return <Disclosure title={t("annotations")} summary={t("annotationsSummary")} count={annotations.length}>
    <div className="controls annotationEditor">
      <label>{t("annotationDate")}<input type="date" value={date} onChange={event => setDate(event.target.value)} /></label>
      <label>{t("annotationTime")}<input type="time" value={time} onChange={event => setTime(event.target.value)} /></label>
      <label>{t("annotationTitle")}<input value={title} onChange={event => setTitle(event.target.value)} /></label>
      <label>{t("annotationType")}<select value={type} onChange={event => setType(event.target.value)}><option value="note">Note</option><option value="content_update">Content update</option><option value="technical_change">Technical change</option><option value="campaign">Campaign</option><option value="algorithm_update">Algorithm update</option></select></label>
      <label>{t("affectedPageGroup")}<input value={pageGroup} onChange={event => setPageGroup(event.target.value)} placeholder="/products/" /></label>
      <label>{t("notes")}<input value={notes} onChange={event => setNotes(event.target.value)} /></label>
      <button className="primary" disabled={!title.trim()} onClick={onAdd}>{t("addAnnotation")}</button>
    </div>
    <div className="annotationList">{annotations.map(item => <article className="annotationItem" key={item.id}>
      <div><strong>{item.date}{item.time ? ` ${item.time}` : ""} · {item.title}</strong><small>{item.type}{item.affectedQuery ? ` · Query: ${item.affectedQuery}` : ""}{item.affectedUrl ? ` · URL: ${item.affectedUrl}` : ""}</small>{item.notes && <p>{item.notes}</p>}</div>
      <button onClick={() => onDelete(item.id)}>{t("deleteView")}</button>
    </article>)}{!annotations.length && <p className="empty">{t("noData")}</p>}</div>
  </Disclosure>;
}

function MetricMultiSelect({ series, selected, onChange }: { series: ChartSeries[]; selected: string[]; onChange: (keys: string[]) => void }) {
  const { t } = useI18n();
  return <fieldset className="metricSelector"><legend>{t("chartMetrics")}</legend>{series.map(item => {
    const checked = selected.includes(item.key);
    const disabled = (!checked && selected.length >= 4) || (checked && selected.length === 1);
    return <label key={item.key} className={checked ? "selected" : ""}><input type="checkbox" checked={checked} disabled={disabled} onChange={() => onChange(checked ? selected.filter(key => key !== item.key) : [...selected, item.key])} /><span style={{ borderColor: item.color }} />{item.label}<small>{item.unit === "ratio" ? t("percentageUnit") : item.unit === "rank" ? t("rankUnit") : t("countUnit")}</small></label>;
  })}<p>{t("metricLimit")}</p></fieldset>;
}

function SourceFreshness({ metadata }: { metadata: Json }) {
  const { t } = useI18n();
  return <dl className="sourceFreshness">
    <div><dt>{t("lastAttempt")}</dt><dd>{metadata.lastAttemptAt || t("unknown")}</dd></div>
    <div><dt>{t("lastSuccess")}</dt><dd>{metadata.lastSuccessAt || t("unknown")}</dd></div>
    <div><dt>{t("latestCompleteDate")}</dt><dd>{metadata.latestCompleteDate || t("unknown")}</dd></div>
    <div><dt>{t("sourceDelay")}</dt><dd>{metadata.sourceLatency || t("unknown")}</dd></div>
  </dl>;
}

function SyncResultPanel({ result }: { result: Json }) {
  const { t } = useI18n();
  const status = result.status || (result.ok ? "success" : "error");
  return <div className={`syncResult ${status}`} role="status" aria-live="polite">
    <strong>{t(`sync_${status}`)}</strong>
    {result.reason && <span>{result.reason}</span>}
    {result.localPersistence && <span>{t("localSaved")}: {result.localPersistence.rawFiles || 0} raw · {result.localPersistence.normalizedImports || 0} SQLite</span>}
    {result.runIds?.length ? <span>{t("apiRuns")}: {result.runIds.length}</span> : result.runId ? <span>{t("apiRuns")}: 1</span> : null}
    <span>{t("cloudResult")}: {Array.isArray(result.cloudSync) ? result.cloudSync.some((item: Json) => item?.ok) ? t("replicated") : t("skippedOptional") : result.cloudSync?.ok ? t("replicated") : t("skippedOptional")}</span>
  </div>;
}

type Ga4Subview = "overview" | "acquisition" | "landing" | "audience" | "conversions" | "saved";

const ga4SubviewKeys: { key: Ga4Subview; label: string }[] = [
  { key: "overview", label: "ga4Overview" },
  { key: "acquisition", label: "ga4Acquisition" },
  { key: "landing", label: "ga4LandingPages" },
  { key: "audience", label: "ga4Audience" },
  { key: "conversions", label: "ga4Conversions" },
  { key: "saved", label: "ga4SavedQueries" },
];

const ga4StandardTableMetrics = ["sessions", "totalUsers", "newUsers", "engagedSessions", "engagementRate", "viewsPerSession", "screenPageViews"];
const ga4StandardTableColumns = ["label", ...ga4StandardTableMetrics.flatMap(metric => [metric, `previous_${metric}`, `delta_${metric}`, `change_${metric}`])];
const ga4LandingTableColumns = [...ga4StandardTableColumns, "keyEvents", "previous_keyEvents", "delta_keyEvents", "change_keyEvents"];
const ga4ConversionTableColumns = ["label", "keyEvents", "previous_keyEvents", "delta_keyEvents", "change_keyEvents"];

function Ga4DimensionPanel({ title, purpose, rows, columns, capability, search, sort, setSearch, setSort, onExport }: {
  title: string; purpose: string; rows: Json[]; columns: string[]; capability?: Json; search: string; sort: string;
  setSearch: (value: string) => void; setSort: (value: string) => void; onExport: (rows: Json[], columns: string[]) => void;
}) {
  const { t } = useI18n();
  const sorted = [...rows].sort((a, b) => Number(b[sort] ?? -Infinity) - Number(a[sort] ?? -Infinity));
  const filtered = sorted.filter(row => !search || JSON.stringify(row).toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  if (capability && !capability.available) {
    return <Panel title={title} eyebrow={t("exactSnapshot")}><StatePanel tone="warn" title={t("unavailable")} detail={capability.reason || t("noDimensionCache")} /></Panel>;
  }
  return <Panel title={title} eyebrow={t("chartTableSameScope")} priority="primary">
    <p>{purpose}</p>
    <div className="controls ga4TableControls">
      <label>{t("tableSort")}<select value={sort} onChange={event => setSort(event.target.value)}>{columns.filter(key => key !== "label").map(key => <option key={key} value={key}>{metricLabel(key)}</option>)}</select></label>
      <button onClick={() => onExport(filtered, columns)}>{t("exportMetadata")}</button>
    </div>
    <Table rows={sorted} columns={columns} search={search} onSearch={setSearch} />
    {capability?.rowLimitReached && <p className="notice">{t("rowCount")}: {capability.rowCount} / {capability.rowLimit}</p>}
  </Panel>;
}

function Ga4({ initial, onData, setError }: { initial: Json; onData: (value: Json) => void; setError: (value: string) => void }) {
  const { language, t } = useI18n();
  const data = initial || {};
  const conversionAvailable = data.metadata?.conversionState === "available";
  const availableSeries = ga4ChartSeries.filter(item => item.key !== "keyEvents" || conversionAvailable);
  const [visibleSeries, setVisibleSeries] = useState<string[]>(["sessions", "totalUsers"]);
  const [subview, setSubview] = useState<Ga4Subview>("overview");
  const [acquisitionDimension, setAcquisitionDimension] = useState("sourceMedium");
  const [tableSearch, setTableSearch] = useState("");
  const [tableSort, setTableSort] = useState("sessions");
  const [rangeStart, setRangeStart] = useState(data.scope?.range?.start || "");
  const [rangeEnd, setRangeEnd] = useState(data.scope?.range?.end || "");
  const [busy, setBusy] = useState(false);
  const [syncResult, setSyncResult] = useState<Json | null>(null);
  const [savedViews, setSavedViews] = useState<Json[]>([]);
  const [selectedViewId, setSelectedViewId] = useState<number | null>(null);
  const [viewName, setViewName] = useState("");
  const [viewDescription, setViewDescription] = useState("");
  const [viewFavorite, setViewFavorite] = useState(false);
  const capabilities = data.metadata?.dimensionCapabilities || {};
  const availableScopes: Json[] = data.metadata?.availableScopes || [];
  const activeTable = subview === "acquisition" ? acquisitionDimension : subview === "landing" ? "landingPage" : subview === "audience" ? "device" : subview === "conversions" ? "event" : "landingPage";
  const requiredMetrics = ["sessions", "totalUsers", "newUsers", "engagedSessions", "engagementRate", "screenPageViews", "viewsPerSession", ...(conversionAvailable ? ["keyEvents"] : [])];

  useEffect(() => {
    if (!conversionAvailable && visibleSeries.includes("keyEvents")) setVisibleSeries(keys => keys.filter(key => key !== "keyEvents"));
  }, [conversionAvailable]);
  useEffect(() => { void api("/api/saved-views?source=ga4").then(setSavedViews).catch(cause => setError(cause instanceof Error ? cause.message : "Saved view request failed")); }, []);
  useEffect(() => {
    if (data.scope?.range?.start) setRangeStart(data.scope.range.start);
    if (data.scope?.range?.end) setRangeEnd(data.scope.range.end);
  }, [data.scope?.range?.start, data.scope?.range?.end]);

  async function queryCached(start = rangeStart, end = rangeEnd) {
    if (!start || !end) return;
    setBusy(true);
    try {
      const result = await api(`/api/ga4/analytics?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`);
      onData(result);
    }
    catch (cause) { setError(cause instanceof Error ? cause.message : "GA4 cache request failed"); }
    finally { setBusy(false); }
  }

  async function syncRange() {
    if (!rangeStart || !rangeEnd || !confirm(t("querySourceConfirm"))) return;
    setBusy(true); setSyncResult({ status: "in_progress" });
    try {
      const result = await api("/api/ga4/sync", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ force: false, start: rangeStart, end: rangeEnd }) });
      setSyncResult(result);
      if (["success", "partial", "skipped_cached_scope"].includes(result.status)) await queryCached(rangeStart, rangeEnd);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "GA4 sync failed"); }
    finally { setBusy(false); }
  }

  function moveSubview(event: React.KeyboardEvent<HTMLButtonElement>, key: Ga4Subview) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const current = ga4SubviewKeys.findIndex(item => item.key === key);
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? ga4SubviewKeys.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + ga4SubviewKeys.length) % ga4SubviewKeys.length;
    const nextKey = ga4SubviewKeys[next].key;
    setSubview(nextKey);
    window.setTimeout(() => document.getElementById(`ga4-tab-${nextKey}`)?.focus(), 0);
  }

  function viewConfig(): Json {
    return {
      version: 1,
      date: { mode: "fixed", preset: "custom", start: rangeStart, end: rangeEnd },
      comparison: { mode: data.comparison?.mode || "previous_period" }, grain: data.scope?.grain || "day",
      filters: [{ field: "sessionDefaultChannelGroup", operator: "equals", value: "Organic Search" }],
      chart: { type: "time_series", metric: visibleSeries[0], visibleSeries, displayMode: "unit_lanes" },
      table: { dimension: activeTable, search: tableSearch, sort: { field: tableSort, direction: "desc" }, rowLimit: data.scope?.rowLimit || 10000 },
      drilldown: { dimension: activeTable, value: null }, ga4Subview: subview, acquisitionDimension,
    };
  }

  async function saveView(update = false) {
    if (!viewName.trim()) return;
    setBusy(true);
    try {
      const payload = { name: viewName.trim(), description: viewDescription, source: "ga4", isFavorite: viewFavorite, config: viewConfig() };
      const saved = await api(update && selectedViewId ? `/api/saved-views/${selectedViewId}` : "/api/saved-views", { method: update ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      setSelectedViewId(saved.id); setSavedViews(await api("/api/saved-views?source=ga4"));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Saved view request failed"); }
    finally { setBusy(false); }
  }

  async function loadView(view: Json) {
    const chart = view.config?.chart || {}, table = view.config?.table || {};
    const date = view.config?.date || {};
    const restored = (chart.visibleSeries || [chart.metric || "sessions"]).filter((key: string) => availableSeries.some(item => item.key === key)).slice(0, 4);
    setSelectedViewId(view.id); setViewName(view.name); setViewDescription(view.description || ""); setViewFavorite(Boolean(view.isFavorite));
    setVisibleSeries(restored.length ? restored : ["sessions"]); setSubview(view.config?.ga4Subview || "overview");
    setAcquisitionDimension(view.config?.acquisitionDimension || (table.dimension === "channel" ? "channel" : "sourceMedium"));
    setTableSearch(table.search || ""); setTableSort(table.sort?.field || "sessions");
    if (date.start && date.end) { setRangeStart(date.start); setRangeEnd(date.end); await queryCached(date.start, date.end); }
  }

  async function removeView(id: number) {
    if (!confirm(t("deleteViewConfirm"))) return;
    await api(`/api/saved-views/${id}?confirmed=true`, { method: "DELETE" });
    if (selectedViewId === id) setSelectedViewId(null);
    setSavedViews(await api("/api/saved-views?source=ga4"));
  }

  function exportCsv(tableKey: string, rows: Json[], columns: string[]) {
    const lines = [
      `# source=${data.metadata?.source || ""}`, `# range=${JSON.stringify(data.scope?.range || {})}`,
      `# comparison=${JSON.stringify(data.comparison || {})}`, `# segment=Organic Search`, `# subview=${subview}`, `# dimension=${tableKey}`,
      `# metrics=${JSON.stringify(visibleSeries)}`, `# table_metrics=${JSON.stringify(requiredMetrics)}`, `# display_mode=unit_lanes`,
      `# filters=${JSON.stringify(tableSearch ? [{ field: tableKey, operator: "contains", value: tableSearch }] : [])}`, `# sort=${JSON.stringify({ field: tableSort, direction: "desc" })}`,
      `# timezone=${data.metadata?.timezone || ""}`, `# latest_complete_date=${data.metadata?.latestCompleteDate || ""}`,
      `# conversion_state=${data.metadata?.conversionState || ""}`, `# row_count=${rows.length}`, `# extracted_at=${new Date().toISOString()}`,
      `# limitations=${JSON.stringify(data.metadata?.limitations || [])}`,
      columns.join(","), ...rows.map((row: Json) => columns.map(key => csv(row[key])).join(",")),
    ];
    download(`ga4-organic-${tableKey}.csv`, lines.join("\n"));
  }

  const conversionValue = conversionAvailable ? fmt(data.totals?.keyEvents, language) : data.metadata?.conversionState === "not_collected" ? t("notCollected") : t("notConfigured");
  return <>
    <nav className="ga4Subnav" aria-label="GA4" role="tablist">
      {ga4SubviewKeys.map(item => <button id={`ga4-tab-${item.key}`} role="tab" aria-selected={subview === item.key} aria-controls={`ga4-panel-${item.key}`} tabIndex={subview === item.key ? 0 : -1} className={subview === item.key ? "active" : ""} key={item.key} onKeyDown={event => moveSubview(event, item.key)} onClick={() => setSubview(item.key)}>{t(item.label)}</button>)}
    </nav>
    <Panel title={t("ga4OrganicScope")} eyebrow={t("exactSnapshot")} priority="primary">
      <div className="ga4QueryGrid">
        <label>{t("cachedRanges")}<select value={availableScopes.some(scope => scope.range?.start === rangeStart && scope.range?.end === rangeEnd) ? `${rangeStart}|${rangeEnd}` : ""} onChange={event => { const [start, end] = event.target.value.split("|"); if (start && end) { setRangeStart(start); setRangeEnd(end); } }}><option value="">{t("custom")}</option>{availableScopes.map(scope => <option key={`${scope.range?.start}|${scope.range?.end}`} value={`${scope.range?.start}|${scope.range?.end}`}>{scope.range?.start} → {scope.range?.end}</option>)}</select></label>
        <label>{t("startDate")}<input type="date" value={rangeStart} onChange={event => setRangeStart(event.target.value)} /></label>
        <label>{t("endDate")}<input type="date" value={rangeEnd} onChange={event => setRangeEnd(event.target.value)} /></label>
      </div>
      <ActionBar label={t("sourceActions")}><button onClick={() => void queryCached()} disabled={busy || !rangeStart || !rangeEnd}><RefreshCw size={16} />{t("applyQuery")}</button><button className="primary" onClick={() => void syncRange()} disabled={busy || !rangeStart || !rangeEnd}><Zap size={16} />{t("querySourceRange")}</button></ActionBar>
      <p className="ga4QueryHelp">{t("customRangeHelp")}</p>
      <div className="scopeChips" aria-label={t("activeScope")}><span>Organic Search</span><span>{data.scope?.range?.start || rangeStart || "—"} → {data.scope?.range?.end || rangeEnd || "—"}</span><span>{t("comparison")}: {data.scope?.comparisonRange?.start || "—"} → {data.scope?.comparisonRange?.end || "—"}</span><span>{localizedComparisonStatus(data.comparison?.status, t)}</span></div>
      <SourceFreshness metadata={data.metadata || {}} />
      {syncResult && <SyncResultPanel result={syncResult} />}
      {data.status === "scope_unavailable" && <StatePanel tone="warn" title={t("unavailable")} detail={t("selectedRangeUnavailable")} />}
      {data.metadata?.snapshotStatus === "partial" && <StatePanel tone="warn" title={t("snapshotPartial")} detail={`${t("missingReports")}: ${(data.metadata?.missingReports || []).join(", ")}`} />}
    </Panel>
    {subview === "overview" && <section id="ga4-panel-overview" role="tabpanel" aria-labelledby="ga4-tab-overview">
      <section className="kpis">
        <Metric label={t("sessions")} value={fmt(data.totals?.sessions, language)} detail={delta(data.deltas?.delta_sessions, false, language, t)} />
        <Metric label={t("users")} value={fmt(data.totals?.totalUsers, language)} detail={delta(data.deltas?.delta_totalUsers, false, language, t)} />
        <Metric label={metricLabel("newUsers")} value={fmt(data.totals?.newUsers, language)} detail={delta(data.deltas?.delta_newUsers, false, language, t)} />
        <Metric label={metricLabel("engagementRate")} value={pct(data.totals?.engagementRate)} detail={delta(data.deltas?.delta_engagementRate, true, language, t)} />
        <Metric label={t("views")} value={fmt(data.totals?.screenPageViews, language)} detail={delta(data.deltas?.delta_screenPageViews, false, language, t)} />
        <Metric label={t("keyEventsConversions")} value={conversionValue} detail={Array.isArray(data.metadata?.primaryConversions) ? data.metadata.primaryConversions.join(", ") : data.metadata?.primaryConversions} />
      </section>
      <Panel title={t("behaviorTrend")} eyebrow={t("dailyAnalysis")} priority="primary">
        <MetricMultiSelect series={availableSeries} selected={visibleSeries} onChange={setVisibleSeries} />
        <p className="notice">{t("unitLanesHelp")}</p>
        <AnalysisChart rows={data.trend || []} comparisonRows={data.comparisonTrend || []} comparison={{ status: data.comparison?.status || "none" }} series={availableSeries} visibleSeries={visibleSeries} onVisibleSeriesChange={setVisibleSeries} locale={language} title={`GA4 ${t("behaviorTrend")}`} state={data.status === "no_data" || data.status === "scope_unavailable" ? "empty" : "ready"} displayMode="unit_lanes" metadata={{ range: data.scope?.range, comparisonRange: data.comparison?.range, timezone: data.metadata?.timezone || t("timezoneUnknown"), grain: t("day"), freshness: data.metadata?.freshness || data.sourceFile }} />
      </Panel>
    </section>}
    {subview === "acquisition" && <section id="ga4-panel-acquisition" role="tabpanel" aria-labelledby="ga4-tab-acquisition">
      <div className="tabs"><button className={acquisitionDimension === "sourceMedium" ? "active" : ""} onClick={() => setAcquisitionDimension("sourceMedium")}>{t("sourceMedium")}</button><button className={acquisitionDimension === "channel" ? "active" : ""} onClick={() => setAcquisitionDimension("channel")}>{t("channel")}</button></div>
      <Ga4DimensionPanel title={t("sourceMediumPerformance")} purpose={t("acquisitionPurpose")} rows={data.tables?.[acquisitionDimension] || []} columns={ga4StandardTableColumns} capability={capabilities[acquisitionDimension]} search={tableSearch} sort={tableSort} setSearch={setTableSearch} setSort={setTableSort} onExport={(rows, columns) => exportCsv(acquisitionDimension, rows, columns)} />
    </section>}
    {subview === "landing" && <section id="ga4-panel-landing" role="tabpanel" aria-labelledby="ga4-tab-landing"><Ga4DimensionPanel title={t("landingPagePerformance")} purpose={t("landingPagesPurpose")} rows={data.tables?.landingPage || []} columns={conversionAvailable ? ga4LandingTableColumns : ga4StandardTableColumns} capability={capabilities.landingPage} search={tableSearch} sort={tableSort} setSearch={setTableSearch} setSort={setTableSort} onExport={(rows, columns) => exportCsv("landingPage", rows, columns)} /></section>}
    {subview === "audience" && <section id="ga4-panel-audience" role="tabpanel" aria-labelledby="ga4-tab-audience" className="ga4AudienceGrid">
      <Ga4DimensionPanel title={t("devicePerformance")} purpose={t("audiencePurpose")} rows={data.tables?.device || []} columns={ga4StandardTableColumns} capability={capabilities.device} search={tableSearch} sort={tableSort} setSearch={setTableSearch} setSort={setTableSort} onExport={(rows, columns) => exportCsv("device", rows, columns)} />
      <Ga4DimensionPanel title={t("countryPerformance")} purpose={t("audiencePurpose")} rows={data.tables?.country || []} columns={ga4StandardTableColumns} capability={capabilities.country} search={tableSearch} sort={tableSort} setSearch={setTableSearch} setSort={setTableSort} onExport={(rows, columns) => exportCsv("country", rows, columns)} />
    </section>}
    {subview === "conversions" && <section id="ga4-panel-conversions" role="tabpanel" aria-labelledby="ga4-tab-conversions">
      <section className="kpis ga4ConversionKpis"><Metric label={t("keyEventsConversions")} value={conversionValue} detail={Array.isArray(data.metadata?.primaryConversions) ? data.metadata.primaryConversions.join(", ") : t("noConfiguredEvents")} /><Metric label={t("configuredEvents")} value={Array.isArray(data.metadata?.primaryConversions) ? fmt(data.metadata.primaryConversions.length, language) : "0"} detail={data.metadata?.conversionState || t("unknown")} /></section>
      <Ga4DimensionPanel title={t("keyEventPerformance")} purpose={t("conversionPurpose")} rows={data.tables?.event || []} columns={ga4ConversionTableColumns} capability={capabilities.event} search={tableSearch} sort={tableSort} setSearch={setTableSearch} setSort={setTableSort} onExport={(rows, columns) => exportCsv("event", rows, columns)} />
      <Ga4DimensionPanel title={t("conversionLandingPerformance")} purpose={t("conversionPurpose")} rows={data.tables?.conversionLandingPage || []} columns={ga4ConversionTableColumns} capability={capabilities.conversionLandingPage} search={tableSearch} sort={tableSort} setSearch={setTableSearch} setSort={setTableSort} onExport={(rows, columns) => exportCsv("conversionLandingPage", rows, columns)} />
    </section>}
    {subview === "saved" && <section id="ga4-panel-saved" role="tabpanel" aria-labelledby="ga4-tab-saved"><p className="notice">{t("savedQueriesPurpose")}</p><SavedViewsPanel views={savedViews} selectedId={selectedViewId} name={viewName} description={viewDescription} favorite={viewFavorite} busy={busy} setName={setViewName} setDescription={setViewDescription} setFavorite={setViewFavorite} onSave={() => void saveView(false)} onUpdate={() => void saveView(true)} onLoad={view => void loadView(view)} onDelete={id => void removeView(id)} /></section>}
    <Disclosure title={t("limitations")} summary={t("sourceLimitationsSummary")} count={(data.metadata?.limitations || []).length}><ul>{(data.metadata?.limitations || []).map((item: string, index: number) => <li key={index}>{item}</li>)}</ul></Disclosure>
    <Disclosure title={t("advancedDimensions")} summary={t("dimensionContractSummary")} count={Object.keys(capabilities).length}><Table rows={Object.entries(capabilities).map(([dimension, capability]: [string, any]) => ({ dimension, available: capability.available, grain: (capability.grain || []).join(" + "), rows: capability.rowCount, range: capability.range ? `${capability.range.start} → ${capability.range.end}` : "—", reason: capability.reason }))} columns={["dimension", "available", "grain", "rows", "range", "reason"]} technical /></Disclosure>
  </>;
}

function LegacyPageExperienceReference({ pagespeed: initialPagespeed, crux: initialCrux }: { pagespeed: Json; crux: Json }) {
  const { language, t } = useI18n();
  const pagespeed = initialPagespeed || {};
  const crux = initialCrux || {};
  const allRuns: Json[] = pagespeed.runs || [];
  const urls = [...new Set(allRuns.map(run => String(run.url || "")).filter(Boolean))];
  const [url, setUrl] = useState("");
  const [strategy, setStrategy] = useState("");
  useEffect(() => { if (urls.length && (!url || !urls.includes(url))) setUrl(urls[0]); }, [urls.join("|"), url]);
  const scopedRuns = allRuns.filter(run => (!url || run.url === url) && (!strategy || run.strategy === strategy));
  const currentRun = scopedRuns[0];
  const comparisonStrategy = strategy || currentRun?.strategy;
  const comparableSuccesses = allRuns.filter(run => run.url === (url || currentRun?.url) && run.strategy === comparisonStrategy && run.status === "success");
  const currentSuccessIndex = currentRun?.status === "success" ? comparableSuccesses.findIndex(run => run.fetchedAt === currentRun.fetchedAt) : -1;
  const previousRun = currentSuccessIndex >= 0 ? comparableSuccesses[currentSuccessIndex + 1] : comparableSuccesses[0];
  const conciseRuns = scopedRuns.map(run => ({
    status: run.displayStatus || (run.status === "success" ? t("completed") : t("runFailed")),
    url: run.url,
    device: run.strategy,
    fetchedAt: run.fetchedAt,
    freshness: run.isStale ? t("stale") : t("fresh"),
    performance: run.status === "success" ? run.scores?.performance : t("runFailed"),
    seo: run.status === "success" ? run.scores?.seo : "—",
    error: run.error || "—",
  }));
  const currentSucceeded = currentRun?.status === "success";
  const selectedTone: Tone = !currentRun ? "neutral" : !currentSucceeded ? "bad" : currentRun.isStale ? "warn" : "good";
  return <>
    <Panel title={t("experienceScope")} eyebrow={t("labAndFieldSeparated")} priority="primary">
      <div className="experienceControls">
        <PageSelector label={t("pageUrl")} value={url} options={urls} onChange={setUrl} />
        <div><span className="controlLabel">{t("device")}</span><DeviceToggle value={strategy} onChange={setStrategy} mobileLabel={t("mobile")} desktopLabel={t("desktop")} allLabel={t("all")} /></div>
      </div>
      <div className="scopeChips"><span>PageSpeed · Lab</span><span>{url || t("noData")}</span>{strategy && <span>{strategy}</span>}<span>CrUX · Field</span></div>
    </Panel>
    <section className="experienceSection" aria-labelledby="lab-data-title">
      <div className="sectionHeading"><div><p className="sectionKicker">PageSpeed / Lighthouse</p><h2 id="lab-data-title">{t("labData")}</h2><p>{t("labDataPurpose")}</p></div><StatusBadge tone={selectedTone}>{currentRun?.displayStatus || t("noRun")}</StatusBadge></div>
      {!currentRun ? <StatePanel tone="neutral" title={t("noRun")} detail={t("noRunForScope")} /> : !currentSucceeded ? <StatePanel tone="bad" title={t("runFailed")} detail={currentRun.error || pagespeed.metadata?.failureSemantics} /> : currentRun.isStale ? <StatePanel tone="warn" title={t("staleRun")} detail={currentRun.fetchedAt} /> : null}
      <section className="kpis experienceKpis">
        <Metric label="Performance" value={currentSucceeded ? fmt(currentRun.scores?.performance, language) : t("runFailed")} detail={currentRun?.fetchedAt} tone={selectedTone} />
        <Metric label="SEO" value={currentSucceeded ? fmt(currentRun.scores?.seo, language) : "—"} detail={currentRun?.strategy} tone={currentSucceeded ? "info" : "neutral"} />
        <Metric label="LCP" value={currentSucceeded ? cell(currentRun.metrics?.lcp, language) : "—"} detail={t("labMetricExact")} tone="neutral" />
        <Metric label="CLS" value={currentSucceeded ? cell(currentRun.metrics?.cls, language) : "—"} detail={t("labMetricExact")} tone="neutral" />
      </section>
      <RunComparisonFrame currentTitle={t("currentRun")} previousTitle={t("previousSuccessfulRun")} current={currentRun ? <RunSummary run={currentRun} /> : <span>—</span>} previous={previousRun ? <RunSummary run={previousRun} /> : <span className="empty">{t("comparisonUnavailable")}</span>} />
      <p className="notice">{pagespeed.metadata?.failureSemantics || t("failureSeparated")}</p>
    </section>
    <section className="experienceSection" aria-labelledby="field-data-title">
      <div className="sectionHeading"><div><p className="sectionKicker">Chrome UX Report</p><h2 id="field-data-title">{t("fieldData")}</h2><p>{t("fieldDataPurpose")}</p></div><StatusBadge tone={crux.status === "no_data" ? "warn" : crux.status === "ok" ? "good" : "neutral"}>{crux.displayStatus || t("loading")}</StatusBadge></div>
      <StatePanel tone={crux.status === "no_data" ? "warn" : crux.status === "ok" ? "good" : "neutral"} title={crux.displayStatus || t("fieldData")} detail={crux.message || t("loadingCache")} />
    </section>
    <Disclosure title={t("labRunHistory")} summary={t("conciseRowsTechnicalOnDemand")} count={conciseRuns.length}>
      <Table rows={conciseRuns} columns={["status", "url", "device", "fetchedAt", "freshness", "performance", "seo", "error"]} maxHeight="420px" />
    </Disclosure>
    <Disclosure title={t("priorityPages")} summary={t("priorityPageSummary")} count={(pagespeed.pages || []).length}>
      <Table rows={pagespeed.pages || []} columns={["url", "clicks", "impressions", "tested", "latestFetchedAt", "isStale"]} maxHeight="380px" />
    </Disclosure>
    <Disclosure title={t("technicalDetails")} summary={t("rawObjectsAndRunEvidence")} count={currentRun ? 1 : 0}>
      {currentRun ? <div className="technicalGrid"><KeyValue label={t("runStatus")} value={currentRun.displayStatus} /><KeyValue label={t("rawPath")} value={currentRun.rawPath} /><KeyValue label={t("finalUrl")} value={currentRun.finalUrl} /><KeyValue label={t("fetchedAt")} value={currentRun.fetchedAt} /><pre>{JSON.stringify({ scores: currentRun.scores, metrics: currentRun.metrics, error: currentRun.error }, null, 2)}</pre></div> : <p className="empty">{t("noData")}</p>}
      {crux.summary && <Disclosure title="CrUX summary" summary={t("fieldTechnicalSummary")}><pre>{JSON.stringify(crux.summary, null, 2)}</pre></Disclosure>}
    </Disclosure>
  </>;
}

function RunSummary({ run }: { run: Json }) {
  const { language, t } = useI18n();
  const succeeded = run.status === "success";
  return <div className="runSummary"><strong>{run.displayStatus || run.status}</strong><small>{run.fetchedAt || "—"}</small><span>{run.strategy || "—"}</span><b>{succeeded ? `Performance ${fmt(run.scores?.performance, language)}` : t("runFailed")}</b></div>;
}
function Tasks({ initial, onRefresh }: { initial: Json[]; onRefresh: () => void }) {
  const { t } = useI18n();
  const tasks = initial || [];
  return <>
    <Panel title={t("recentTasks")} eyebrow={t("workQueue")} priority="primary">
      <ActionBar label={t("taskActions")}><button onClick={onRefresh}><RefreshCw size={16} />{t("refreshHistory")}</button></ActionBar>
      {tasks.length ? <Table rows={tasks} columns={["name", "modified"]} /> : <StatePanel tone="neutral" title={t("noTasks")} detail={t("tasksCreatedFromAnalysis")} />}
    </Panel>
    <Disclosure title={t("taskTechnicalEvidence")} summary={t("pathsAndFileSizes")} count={tasks.length}>
      <Table rows={tasks} columns={["name", "modified", "path", "bytes"]} technical />
    </Disclosure>
  </>;
}

function Operations({ initial }: { initial: Json }) {
  const { language, t } = useI18n();
  const data = initial || {};
  const recentRuns: Json[] = data.recentRuns || [];
  const nonSuccessRuns = recentRuns.filter(run => !["ok", "success", "skipped", "skipped_fresh"].includes(String(run.status || "").toLowerCase()));
  const logErrors = Number(data.logs?.errorCount || 0);
  const rawDirectories = Object.entries(data.localBackup?.rawDirectories || {}).map(([source, item]: any) => ({ source, ...item }));
  const cloudTables = Object.entries(data.cloud?.tableCounts || {}).map(([table, rows]) => ({ table, rows }));
  return <>
    <section className="kpis">
      <Metric label={t("sqlite")} value={data.localBackup?.sqlite?.exists ? t("available") : t("unavailable")} detail={t("localSourceOfTruth")} tone={data.localBackup?.sqlite?.exists ? "good" : "bad"} />
      <Metric label={t("cloudReplica")} value={data.cloud?.ok ? t("healthy") : t("optionalDegraded")} detail={t("optionalReplica") } tone={data.cloud?.ok ? "good" : "warn"} />
      <Metric label={t("recentRuns")} value={fmt(recentRuns.length, language)} detail={`${nonSuccessRuns.length} ${t("needsReview")}`} tone={nonSuccessRuns.length ? "warn" : "neutral"} />
      <Metric label={t("logs")} value={logErrors ? `${logErrors} ${t("errors")}` : t("clear")} detail={`${data.logs?.warningCount || 0} ${t("warnings")}`} tone={logErrors ? "bad" : "good"} />
    </section>
    {(logErrors > 0 || nonSuccessRuns.length > 0) && <StatePanel tone={logErrors ? "bad" : "warn"} title={t("operationsAttention")} detail={`${nonSuccessRuns.length} ${t("nonSuccessRuns")} · ${logErrors} ${t("logErrors")}`} />}
    <Panel title={t("quotaFreshness")} eyebrow={t("sourceReadiness")} priority="primary"><Table rows={data.quota?.sources || []} columns={["source", "freshness", "todayRuns", "estimatedCallsToday", "latestSuccessAt", "recommendation"]} /></Panel>
    <Disclosure title={t("syncHistory")} summary={t("syncHistorySummary")} count={recentRuns.length} tone={nonSuccessRuns.length ? "warn" : "neutral"}>
      <Table rows={recentRuns.map(run => ({ source: run.source, status: run.status, created_at: run.created_at, error: run.error || "—" }))} columns={["source", "status", "created_at", "error"]} maxHeight="420px" />
      <Disclosure title={t("runPayloadsAndPaths")} summary={t("technicalOnly")} count={recentRuns.length}>
        <Table rows={recentRuns} columns={["source", "status", "created_at", "raw_path", "error", "summary"]} technical maxHeight="420px" />
      </Disclosure>
    </Disclosure>
    <Disclosure title={t("storageDetails")} summary={t("storageDetailsSummary")} count={rawDirectories.length + cloudTables.length}>
      <div className="technicalGrid compactGrid"><KeyValue label={t("backup")} value={data.localBackup?.latestBackup?.backupId || t("none")} /><KeyValue label={t("sqlitePath")} value={data.localBackup?.sqlite?.path} /><KeyValue label={t("databaseMode")} value={data.database?.mode} /><KeyValue label={t("runtimeMode")} value={data.architecture?.runtimeIndependence} /></div>
      <h3>{t("rawCache")}</h3><Table rows={rawDirectories} columns={["source", "files", "bytes", "latestFile", "path"]} technical />
      <h3>{t("cloudTables")}</h3><Table rows={cloudTables} columns={["table", "rows"]} />
    </Disclosure>
    <Disclosure title={t("logDetails")} summary={t("logDetailsSummary")} count={(data.logs?.files || []).length} tone={logErrors ? "bad" : "neutral"}>
      <Table rows={data.logs?.files || []} columns={["name", "bytes", "modified", "errors", "warnings"]} technical />
    </Disclosure>
  </>;
}

function Connections({ initial }: { initial: Json }) {
  const { t } = useI18n();
  const env = initial?.env || {};
  const rows = Object.entries(env).map(([key, value]: any) => ({ key, configured: value.configured, value: value.value }));
  const configured = rows.filter(row => row.configured).length;
  return <>
    <section className="kpis settingsKpis">
      <Metric label={t("configuredConnections")} value={`${configured}/${rows.length}`} detail={t("maskedAndLocal")} tone={configured ? "good" : "warn"} />
      <Metric label={t("secrets")} value={t("masked")} detail={t("neverRenderedRaw")} tone="good" />
    </section>
    <StatePanel tone="info" title={t("connectionSafety")} detail={t("secretsMasked")} />
    <Disclosure title={t("maskedSettings")} summary={t("connectionDiagnosticsSummary")} count={rows.length}>
      <Table rows={rows} columns={["key", "configured", "value"]} technical />
    </Disclosure>
  </>;
}

function Metric({ label, value, detail, tone }: { label: string; value: React.ReactNode; detail?: React.ReactNode; tone?: Tone }) { return <KpiCard label={label} value={value} detail={detail} tone={tone} />; }
function Panel({ title, eyebrow, priority, children }: { title: string; eyebrow?: string; priority?: "primary" | "secondary"; children: React.ReactNode }) { return <section className={`panel priority-${priority || "secondary"}`}><header className="panelHeader"><div>{eyebrow && <p className="sectionKicker">{eyebrow}</p>}<h2>{title}</h2></div></header>{children}</section>; }
function Action({ icon, title, detail, onClick }: { icon?: React.ReactNode; title: string; detail: string; onClick: () => void }) { return <button className="action" onClick={onClick}><span className="actionIcon">{icon || <Sparkles size={18} />}</span><strong>{title}</strong><span>{detail}</span></button>; }
function Table({ rows, columns, onRow, selected, search, onSearch, technical = false, maxHeight }: { rows: Json[]; columns: string[]; onRow?: (row: Json) => void; selected?: (row: Json) => boolean; search?: string; onSearch?: (value: string) => void; technical?: boolean; maxHeight?: string }) {
  const { language, t } = useI18n();
  const searchId = useId();
  const [internalSearch, setInternalSearch] = useState("");
  const activeSearch = search ?? internalSearch;
  const setActiveSearch = onSearch ?? setInternalSearch;
  const visible = useMemo(() => (rows || []).filter(row => JSON.stringify(row).toLowerCase().includes(activeSearch.toLowerCase())), [rows, activeSearch]);
  return <><div className="tableToolbar"><label className="srOnly" htmlFor={searchId}>{t("searchRows")}</label><input id={searchId} aria-label={t("searchRows")} className="tableSearch" value={activeSearch} onChange={event => setActiveSearch(event.target.value)} placeholder={t("searchRows")} /><span>{t("rowCount")}: {visible.length} / {(rows || []).length}</span></div><div className={`tableWrap ${technical ? "technicalTable" : ""}`} style={maxHeight ? { maxHeight } : undefined} tabIndex={0} role="region" aria-label={t("dataTable")}><table><thead><tr>{columns.map(column => <th scope="col" key={column}>{column}</th>)}</tr></thead><tbody>{visible.map((row, index) => { const isSelected = Boolean(selected?.(row)); return <tr key={`${row.id || row.label || row.name || row.url || "row"}-${index}`} tabIndex={onRow ? 0 : undefined} aria-selected={onRow ? isSelected : undefined} onClick={() => onRow?.(row)} onKeyDown={event => { if (onRow && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); onRow(row); } }} className={`${onRow ? "clickable" : ""}${isSelected ? " selectedRow" : ""}`}>{columns.map(column => <td key={column} title={cell(row[column], language, column)}>{cell(row[column], language, column)}</td>)}</tr>; })}</tbody></table>{!visible.length && <p className="empty">{t("noData")}</p>}</div></>;
}

function KeyValue({ label, value }: { label: string; value: React.ReactNode }) { return <div className="keyValue"><span>{label}</span><strong>{value || "—"}</strong></div>; }
function sourceStatusTone(status?: string): Tone { const value = String(status || "").toLowerCase(); if (["ok", "success", "fresh", "healthy"].includes(value)) return "good"; if (["error", "failed", "unhealthy"].includes(value)) return "bad"; if (["partial", "stale", "no_data", "no dataset", "missing"].includes(value)) return "warn"; return "neutral"; }
function dimensionLabel(value: string) { return ({ query: "Query", page: "Page", date: "Date", country: "Country", device: "Device", searchAppearance: "Search Appearance" } as Record<string, string>)[value] || value; }
function fmt(value: any, locale: string) { return value === undefined || value === null || value === "" ? "-" : new Intl.NumberFormat(locale === "zh-CN" ? "zh-CN" : "en-US", { maximumFractionDigits: 2 }).format(Number(value)); }
function pct(value: any) { return value === undefined || value === null || value === "" ? "-" : `${(Number(value) * 100).toFixed(2)}%`; }
function delta(value: any, percent: boolean, locale: string, t: (key: string) => string) { return value === undefined || value === null ? t("comparisonUnavailable") : `${Number(value) > 0 ? "+" : ""}${percent ? pct(value) : fmt(value, locale)} ${t("vsComparison")}`; }
function localizedComparisonReason(comparison: Json = {}, t: (key: string) => string) { return ({ partial_cache_coverage: t("comparisonPartialReason"), outside_cache_coverage: t("comparisonOutside"), disabled: t("comparisonDisabled") } as Record<string, string>)[comparison?.reasonCode] || comparison?.reason || ""; }
function localizedComparisonStatus(status: string, t: (key: string) => string) { return ({ complete: t("comparisonComplete"), partial: t("comparisonPartial"), unavailable: t("comparisonUnavailable"), none: t("comparisonDisabled") } as Record<string, string>)[status] || t("unknown"); }
function cell(value: any, locale: string, column = "") { if (value === null || value === undefined || value === "") return "-"; if (typeof value === "number") return column.startsWith("change_") || /(^|_)(ctr|engagementRate)$/.test(column) ? pct(value) : fmt(value, locale); if (typeof value === "object") return JSON.stringify(value); return String(value); }
function metricLabel(value: string) { return ({ totalUsers: "Users", newUsers: "New users", engagedSessions: "Engaged Sessions", engagementRate: "Engagement Rate", screenPageViews: "Views", keyEvents: "Key events / Conversions", sessions: "Sessions" } as Record<string, string>)[value] || value; }
function csv(value: any) { const text = value === null || value === undefined ? "" : typeof value === "object" ? JSON.stringify(value) : String(value); return `"${text.replaceAll('"', '""')}"`; }
function download(name: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.hidden = true;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
