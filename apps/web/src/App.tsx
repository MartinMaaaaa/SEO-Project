import { Activity, Bot, Cloud, Database, Gauge, Languages, RefreshCw, Search, Settings, Zap } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { AnalysisChart, type ChartSeries } from "./components/AnalysisChart";
import { ChartStateFixtures } from "./components/ChartStateFixtures";
import { localizeReason, useI18n } from "./i18n";

type Json = Record<string, any>;
type View = "overview" | "gsc" | "ga4" | "pagespeed" | "crux" | "tasks" | "operations" | "settings";

async function api(path: string, options?: RequestInit) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

export function App() {
  const { language, setLanguage, t } = useI18n();
  const fixtureMode = new URLSearchParams(window.location.search).get("chartFixtures") === "1";
  const views: { id: View; label: string; icon: React.ReactNode }[] = [
    { id: "overview", label: t("overview"), icon: <Activity size={17} /> },
    { id: "gsc", label: t("gsc"), icon: <Search size={17} /> },
    { id: "ga4", label: t("ga4"), icon: <Gauge size={17} /> },
    { id: "pagespeed", label: t("pagespeed"), icon: <Zap size={17} /> },
    { id: "crux", label: t("crux"), icon: <Cloud size={17} /> },
    { id: "tasks", label: t("tasks"), icon: <Bot size={17} /> },
    { id: "operations", label: t("operations"), icon: <Database size={17} /> },
    { id: "settings", label: t("settings"), icon: <Settings size={17} /> },
  ];
  const [view, setView] = useState<View>("overview");
  const [data, setData] = useState<Record<string, any>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

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

  if (fixtureMode) return <ChartStateFixtures locale={language} />;

  return <main className="app">
    <aside className="sidebar">
      <div className="brand"><span className="brandMark">E</span><div><strong>SEO Data Console</strong><small>{t("independent")}</small></div></div>
      <nav>{views.map(item => <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => setView(item.id)}>{item.icon}{item.label}</button>)}</nav>
    </aside>
    <section className="content">
      <header className="topbar">
        <div><p className="eyebrow">{t("eyebrow")}</p><h1>{views.find(item => item.id === view)?.label}</h1><p className="subtitle">{t("subtitle")}</p></div>
        <div className="topActions">
          <button className="languageButton" onClick={() => setLanguage(language === "zh-CN" ? "en" : "zh-CN")}><Languages size={17} />{t("language")}</button>
          <button className="primary" onClick={() => void refreshAll()} disabled={!!busy}><RefreshCw size={17} />{t("reload")}</button>
        </div>
      </header>
      {error && <div className="alert">{t("apiError")}: {error}</div>}
      {view === "overview" && <Overview data={data} navigate={setView} />}
      {view === "gsc" && <Gsc initial={data.gsc} onData={value => setData(current => ({ ...current, gsc: value }))} setError={setError} />}
      {view === "ga4" && <Ga4 initial={data.ga4} onData={value => setData(current => ({ ...current, ga4: value }))} setError={setError} />}
      {view === "pagespeed" && <PageSpeed initial={data.pagespeed} />}
      {view === "crux" && <Crux initial={data.crux} />}
      {view === "tasks" && <Tasks initial={data.tasks} onRefresh={() => load("tasks", "/api/ai/tasks")} />}
      {view === "operations" && <Operations initial={data.storage} />}
      {view === "settings" && <Connections initial={data.status} />}
    </section>
  </main>;
}

function Overview({ data, navigate }: { data: Json; navigate: (view: View) => void }) {
  const { language, t } = useI18n();
  const gsc = data.gsc || {}, ga4 = data.ga4 || {}, ps = data.pagespeed || {}, crux = data.crux || {}, storage = data.storage || {};
  return <>
    <section className="kpis">
      <Metric label="GSC Clicks" value={fmt(gsc.totals?.clicks, language)} detail={gsc.metadata?.freshness || t("noCache")} />
      <Metric label="GA4 Sessions" value={fmt(ga4.totals?.sessions, language)} detail={ga4.metadata?.primaryConversions || t("conversionsUnknown")} />
      <Metric label={t("pageSpeedRuns")} value={fmt(ps.runs?.length, language)} detail={`${ps.runs?.filter((row: Json) => row.status === "failed").length || 0} ${t("failed")}`} />
      <Metric label="CrUX" value={crux.displayStatus || t("loading")} detail={crux.message} tone={crux.status === "no_data" ? "warn" : "good"} />
    </section>
    <Panel title={t("attention")}><div className="actionGrid">
      <Action title={t("analyzeSearch")} detail={gsc.comparison?.status === "unavailable" ? t("comparisonOutside") : t("reviewDrivers")} onClick={() => navigate("gsc")} />
      <Action title={t("reviewFailures")} detail={t("failureSeparated")} onClick={() => navigate("pagespeed")} />
      <Action title={t("checkOperations")} detail={storage.database?.cloudDegraded ? t("cloudDegraded") : t("reviewFreshness")} onClick={() => navigate("operations")} />
    </div></Panel>
    <Panel title={t("sourceHealth")}><Table rows={[
      { source: "GSC", state: gsc.status, cache: gsc.metadata?.sourceFile, limitation: gsc.metadata?.limitations?.[0] },
      { source: "GA4", state: ga4.status, cache: ga4.sourceFile, limitation: ga4.metadata?.limitations?.[0] },
      { source: "PageSpeed", state: ps.status, cache: ps.runs?.[0]?.rawPath, limitation: ps.metadata?.failureSemantics },
      { source: "CrUX", state: crux.displayStatus, cache: crux.sourceFile, limitation: crux.message },
    ]} columns={["source", "state", "cache", "limitation"]} /></Panel>
  </>;
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
    <Panel title={t("scopeComparison")}>
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
    <Panel title={t("trend")}><MetricMultiSelect series={gscChartSeries} selected={visibleSeries} onChange={keys => { setVisibleSeries(keys); setChartMetric(keys[0] || "clicks"); }} /> <p className="notice">{t("unitLanesHelp")}</p><AnalysisChart
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
    <Panel title={t("scopedRows")}>
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
  return <Panel title={t("dimensions")}><div className="dimensionGrid">{["country", "device", "searchAppearance"].map(name => {
    const item = capabilities[name] || {};
    return <article className={`dimensionCard ${item.enabled ? "enabled" : "disabled"}`} key={name}>
      <div><strong>{dimensionLabel(name)}</strong><span className="badge">{item.enabled ? t("available") : t("unavailable")}</span></div>
      <small>{t("exactGrain")}: {(item.grain || ["date", name]).join(" + ")} · {t("propertyGrain")}</small>
      {!item.enabled && <p>{localizeReason(item.reason || "Requires a compatible GSC collection.", t)}</p>}
    </article>;
  })}</div></Panel>;
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
  return <Panel title={t("savedAnalysis")}>
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
  </Panel>;
}

function AnnotationsPanel({ annotations, date, time, title, type, pageGroup, notes, setDate, setTime, setTitle, setType, setPageGroup, setNotes, onAdd, onDelete }: {
  annotations: Json[]; date: string; time: string; title: string; type: string; pageGroup: string; notes: string;
  setDate: (value: string) => void; setTime: (value: string) => void; setTitle: (value: string) => void; setType: (value: string) => void;
  setPageGroup: (value: string) => void; setNotes: (value: string) => void; onAdd: () => void; onDelete: (id: number) => void;
}) {
  const { t } = useI18n();
  return <Panel title={t("annotations")}>
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
  </Panel>;
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

function Ga4({ initial, onData, setError }: { initial: Json; onData: (value: Json) => void; setError: (value: string) => void }) {
  const { language, t } = useI18n();
  const data = initial || {};
  const conversionAvailable = data.metadata?.conversionState === "available";
  const availableSeries = ga4ChartSeries.filter(item => item.key !== "keyEvents" || conversionAvailable);
  const [visibleSeries, setVisibleSeries] = useState<string[]>(["sessions", "totalUsers"]);
  const [tableTab, setTableTab] = useState("landingPage");
  const [tableSearch, setTableSearch] = useState("");
  const [tableSort, setTableSort] = useState("sessions");
  const [busy, setBusy] = useState(false);
  const [syncResult, setSyncResult] = useState<Json | null>(null);
  const [savedViews, setSavedViews] = useState<Json[]>([]);
  const [selectedViewId, setSelectedViewId] = useState<number | null>(null);
  const [viewName, setViewName] = useState("");
  const [viewDescription, setViewDescription] = useState("");
  const [viewFavorite, setViewFavorite] = useState(false);
  const capabilities = data.metadata?.dimensionCapabilities || {};
  const tableTabs = ["channel", "sourceMedium", "landingPage", "device", "country"];
  const requiredMetrics = ["sessions", "totalUsers", "newUsers", "engagedSessions", "engagementRate", "screenPageViews", ...(conversionAvailable ? ["keyEvents"] : [])];
  const tableColumns = ["label", ...requiredMetrics.flatMap(metric => [metric, `previous_${metric}`, `delta_${metric}`, `change_${metric}`])];
  const rows = [...(data.tables?.[tableTab] || [])].sort((a: Json, b: Json) => Number(b[tableSort] ?? -Infinity) - Number(a[tableSort] ?? -Infinity));

  useEffect(() => {
    if (!conversionAvailable && visibleSeries.includes("keyEvents")) setVisibleSeries(keys => keys.filter(key => key !== "keyEvents"));
  }, [conversionAvailable]);
  useEffect(() => { void api("/api/saved-views?source=ga4").then(setSavedViews).catch(cause => setError(cause instanceof Error ? cause.message : "Saved view request failed")); }, []);
  useEffect(() => {
    if (capabilities[tableTab] && !capabilities[tableTab].available) {
      const fallback = tableTabs.find(key => capabilities[key]?.available);
      if (fallback) setTableTab(fallback);
    }
  }, [capabilities, tableTab]);

  async function reload() {
    setBusy(true);
    try { onData(await api("/api/ga4/analytics")); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "GA4 cache request failed"); }
    finally { setBusy(false); }
  }

  async function sync() {
    if (!confirm(t("ga4SyncConfirm"))) return;
    setBusy(true); setSyncResult({ status: "in_progress" });
    try {
      const result = await api("/api/ga4/sync", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ force: false }) });
      setSyncResult(result);
      if (["success", "partial"].includes(result.status)) onData(await api("/api/ga4/analytics"));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "GA4 sync failed"); }
    finally { setBusy(false); }
  }

  function viewConfig(): Json {
    return {
      version: 1,
      date: { mode: "fixed", preset: "custom", start: data.scope?.range?.start || "", end: data.scope?.range?.end || "" },
      comparison: { mode: data.comparison?.mode || "previous_period" }, grain: data.scope?.grain || "day",
      filters: [{ field: "sessionDefaultChannelGroup", operator: "equals", value: "Organic Search" }],
      chart: { type: "time_series", metric: visibleSeries[0], visibleSeries, displayMode: "unit_lanes" },
      table: { dimension: tableTab, search: tableSearch, sort: { field: tableSort, direction: "desc" }, rowLimit: data.scope?.rowLimit || 10000 },
      drilldown: { dimension: tableTab, value: null },
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

  function loadView(view: Json) {
    const chart = view.config?.chart || {}, table = view.config?.table || {};
    const restored = (chart.visibleSeries || [chart.metric || "sessions"]).filter((key: string) => availableSeries.some(item => item.key === key)).slice(0, 4);
    setSelectedViewId(view.id); setViewName(view.name); setViewDescription(view.description || ""); setViewFavorite(Boolean(view.isFavorite));
    setVisibleSeries(restored.length ? restored : ["sessions"]); setTableTab(table.dimension || "landingPage"); setTableSearch(table.search || ""); setTableSort(table.sort?.field || "sessions");
  }

  async function removeView(id: number) {
    if (!confirm(t("deleteViewConfirm"))) return;
    await api(`/api/saved-views/${id}?confirmed=true`, { method: "DELETE" });
    if (selectedViewId === id) setSelectedViewId(null);
    setSavedViews(await api("/api/saved-views?source=ga4"));
  }

  function exportCsv() {
    const columns = rows.length ? Object.keys(rows[0]) : tableColumns;
    const lines = [
      `# source=${data.metadata?.source || ""}`, `# range=${JSON.stringify(data.scope?.range || {})}`,
      `# comparison=${JSON.stringify(data.comparison || {})}`, `# segment=Organic Search`, `# dimension=${tableTab}`,
      `# metrics=${JSON.stringify(visibleSeries)}`, `# table_metrics=${JSON.stringify(requiredMetrics)}`, `# display_mode=unit_lanes`,
      `# timezone=${data.metadata?.timezone || ""}`, `# latest_complete_date=${data.metadata?.latestCompleteDate || ""}`,
      `# conversion_state=${data.metadata?.conversionState || ""}`, `# row_count=${rows.length}`, `# extracted_at=${new Date().toISOString()}`,
      `# limitations=${JSON.stringify(data.metadata?.limitations || [])}`,
      columns.join(","), ...rows.map((row: Json) => columns.map(key => csv(row[key])).join(",")),
    ];
    download(`ga4-organic-${tableTab}.csv`, lines.join("\n"));
  }

  const conversionValue = conversionAvailable ? fmt(data.totals?.keyEvents, language) : data.metadata?.conversionState === "not_collected" ? t("notCollected") : t("notConfigured");
  return <>
    <Panel title={t("ga4OrganicScope")}>
      <div className="controls"><button onClick={() => void reload()} disabled={busy}>{t("reload")}</button><button className="primary" onClick={() => void sync()} disabled={busy}>{t("syncSource")}</button></div>
      <p className="notice">Organic Search · {data.scope?.range?.start || "—"} – {data.scope?.range?.end || "—"} · {t("comparisonStatus")}: {localizedComparisonStatus(data.comparison?.status, t)}</p>
      <SourceFreshness metadata={data.metadata || {}} />
      {syncResult && <SyncResultPanel result={syncResult} />}
    </Panel>
    <section className="kpis">
      <Metric label={t("sessions")} value={fmt(data.totals?.sessions, language)} detail={delta(data.deltas?.delta_sessions, false, language, t)} />
      <Metric label={t("users")} value={fmt(data.totals?.totalUsers, language)} detail={delta(data.deltas?.delta_totalUsers, false, language, t)} />
      <Metric label={t("views")} value={fmt(data.totals?.screenPageViews, language)} detail={delta(data.deltas?.delta_screenPageViews, false, language, t)} />
      <Metric label={t("keyEventsConversions")} value={conversionValue} detail={Array.isArray(data.metadata?.primaryConversions) ? data.metadata.primaryConversions.join(", ") : data.metadata?.primaryConversions} />
    </section>
    <Panel title={t("behaviorTrend")}>
      <MetricMultiSelect series={availableSeries} selected={visibleSeries} onChange={setVisibleSeries} />
      <p className="notice">{t("unitLanesHelp")}</p>
      <AnalysisChart rows={data.trend || []} comparisonRows={data.comparisonTrend || []} comparison={{ status: data.comparison?.status || "none" }} series={availableSeries} visibleSeries={visibleSeries} onVisibleSeriesChange={setVisibleSeries} locale={language} title={`GA4 ${t("behaviorTrend")}`} state={data.status === "no_data" ? "empty" : "ready"} displayMode="unit_lanes" metadata={{ range: data.scope?.range, comparisonRange: data.comparison?.range, timezone: data.metadata?.timezone || t("timezoneUnknown"), grain: t("day"), freshness: data.metadata?.freshness || data.sourceFile }} />
    </Panel>
    <Panel title={t("ga4Tables")}>
      <div className="tabs">{tableTabs.map(key => <button key={key} className={tableTab === key ? "active" : ""} disabled={capabilities[key] && !capabilities[key].available} onClick={() => setTableTab(key)}>{t(key)}</button>)}<button onClick={exportCsv}>{t("exportMetadata")}</button></div>
      <div className="controls"><label>{t("tableSort")}<select value={tableSort} onChange={event => setTableSort(event.target.value)}>{requiredMetrics.map(metric => <option key={metric} value={metric}>{metricLabel(metric)}</option>)}</select></label></div>
      <Table rows={rows} columns={tableColumns} search={tableSearch} onSearch={setTableSearch} />
      <details><summary>{t("limitations")}</summary><ul>{(data.metadata?.limitations || []).map((item: string, index: number) => <li key={index}>{item}</li>)}</ul></details>
    </Panel>
    <SavedViewsPanel views={savedViews} selectedId={selectedViewId} name={viewName} description={viewDescription} favorite={viewFavorite} busy={busy} setName={setViewName} setDescription={setViewDescription} setFavorite={setViewFavorite} onSave={() => void saveView(false)} onUpdate={() => void saveView(true)} onLoad={loadView} onDelete={id => void removeView(id)} />
  </>;
}

function PageSpeed({ initial }: { initial: Json }) {
  const { t } = useI18n();
  const data = initial || {};
  const [strategy, setStrategy] = useState("");
  const runs = (data.runs || []).filter((run: Json) => !strategy || run.strategy === strategy);
  return <><Panel title={t("labMonitoring")}><div className="controls"><label>{t("device")}<select value={strategy} onChange={event => setStrategy(event.target.value)}><option value="">{t("all")}</option><option value="mobile">{t("mobile")}</option><option value="desktop">{t("desktop")}</option></select></label></div><p className="notice">{data.metadata?.failureSemantics}</p><Table rows={runs} columns={["displayStatus", "url", "strategy", "fetchedAt", "isStale", "scores", "metrics", "error"]} /></Panel><Panel title={t("priorityPages")}><Table rows={data.pages || []} columns={["url", "clicks", "impressions", "tested", "latestFetchedAt", "isStale"]} /></Panel></>;
}

function Crux({ initial }: { initial: Json }) { const { t } = useI18n(); const data = initial || {}; return <Panel title={data.displayStatus || "CrUX"}><div className={`state ${data.status === "no_data" ? "warn" : "good"}`}>{data.message || t("loadingCache")}</div>{data.summary && <pre>{JSON.stringify(data.summary, null, 2)}</pre>}</Panel>; }
function Tasks({ initial, onRefresh }: { initial: Json[]; onRefresh: () => void }) { const { t } = useI18n(); return <Panel title={t("recentTasks")}><button onClick={onRefresh}>{t("refreshHistory")}</button><Table rows={initial || []} columns={["name", "modified", "path", "bytes"]} /></Panel>; }
function Operations({ initial }: { initial: Json }) { const { language, t } = useI18n(); const data = initial || {}; return <><section className="kpis"><Metric label={t("sqlite")} value={data.localBackup?.sqlite?.exists ? t("available") : t("unavailable")} detail={data.localBackup?.sqlite?.path} tone={data.localBackup?.sqlite?.exists ? "good" : "bad"} /><Metric label={t("cloudReplica")} value={data.cloud?.ok ? t("healthy") : t("optionalDegraded")} detail={data.cloud?.message} tone={data.cloud?.ok ? "good" : "warn"} /><Metric label={t("recentRuns")} value={fmt(data.recentRuns?.length, language)} /><Metric label={t("backup")} value={data.localBackup?.latestBackup?.backupId || t("none")} /></section><Panel title={t("quotaFreshness")}><Table rows={data.quota?.sources || []} columns={["source", "freshness", "todayRuns", "estimatedCallsToday", "latestSuccessAt", "recommendation"]} /></Panel><Panel title={t("syncHistory")}><Table rows={data.recentRuns || []} columns={["source", "status", "created_at", "raw_path", "error", "summary"]} /></Panel><div className="grid"><Panel title={t("rawCache")}><Table rows={Object.entries(data.localBackup?.rawDirectories || {}).map(([source, item]: any) => ({ source, ...item }))} columns={["source", "files", "bytes", "latestFile", "path"]} /></Panel><Panel title={t("cloudTables")}><Table rows={Object.entries(data.cloud?.tableCounts || {}).map(([table, rows]) => ({ table, rows }))} columns={["table", "rows"]} /></Panel></div></>; }
function Connections({ initial }: { initial: Json }) { const { t } = useI18n(); const env = initial?.env || {}; return <Panel title={t("maskedSettings")}><p className="notice">{t("secretsMasked")}</p><Table rows={Object.entries(env).map(([key, value]: any) => ({ key, configured: value.configured, value: value.value }))} columns={["key", "configured", "value"]} /></Panel>; }

function Metric({ label, value, detail, tone }: { label: string; value: string; detail?: React.ReactNode; tone?: string }) { return <article className={`metric ${tone || ""}`}><span>{label}</span><strong>{value}</strong><small>{detail || "-"}</small></article>; }
function Panel({ title, children }: { title: string; children: React.ReactNode }) { return <section className="panel"><h2>{title}</h2>{children}</section>; }
function Action({ title, detail, onClick }: { title: string; detail: string; onClick: () => void }) { return <button className="action" onClick={onClick}><strong>{title}</strong><span>{detail}</span></button>; }
function Table({ rows, columns, onRow, selected, search, onSearch }: { rows: Json[]; columns: string[]; onRow?: (row: Json) => void; selected?: (row: Json) => boolean; search?: string; onSearch?: (value: string) => void }) { const { language, t } = useI18n(); const [internalSearch, setInternalSearch] = useState(""); const activeSearch = search ?? internalSearch; const setActiveSearch = onSearch ?? setInternalSearch; const visible = useMemo(() => (rows || []).filter(row => JSON.stringify(row).toLowerCase().includes(activeSearch.toLowerCase())), [rows, activeSearch]); return <><div className="tableToolbar"><input className="tableSearch" value={activeSearch} onChange={event => setActiveSearch(event.target.value)} placeholder={t("searchRows")} /><span>{t("rowCount")}: {visible.length} / {(rows || []).length}</span></div><div className="tableWrap"><table><thead><tr>{columns.map(column => <th key={column}>{column}</th>)}</tr></thead><tbody>{visible.map((row, index) => { const isSelected = Boolean(selected?.(row)); return <tr key={index} tabIndex={onRow ? 0 : undefined} aria-selected={onRow ? isSelected : undefined} onClick={() => onRow?.(row)} onKeyDown={event => { if (onRow && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); onRow(row); } }} className={`${onRow ? "clickable" : ""}${isSelected ? " selectedRow" : ""}`}>{columns.map(column => <td key={column} title={cell(row[column], language, column)}>{cell(row[column], language, column)}</td>)}</tr>; })}</tbody></table>{!visible.length && <p className="empty">{t("noData")}</p>}</div></>; }
function dimensionLabel(value: string) { return ({ query: "Query", page: "Page", date: "Date", country: "Country", device: "Device", searchAppearance: "Search Appearance" } as Record<string, string>)[value] || value; }
function fmt(value: any, locale: string) { return value === undefined || value === null || value === "" ? "-" : new Intl.NumberFormat(locale === "zh-CN" ? "zh-CN" : "en-US", { maximumFractionDigits: 2 }).format(Number(value)); }
function pct(value: any) { return value === undefined || value === null || value === "" ? "-" : `${(Number(value) * 100).toFixed(2)}%`; }
function delta(value: any, percent: boolean, locale: string, t: (key: string) => string) { return value === undefined || value === null ? t("comparisonUnavailable") : `${Number(value) > 0 ? "+" : ""}${percent ? pct(value) : fmt(value, locale)} ${t("vsComparison")}`; }
function localizedComparisonReason(comparison: Json = {}, t: (key: string) => string) { return ({ partial_cache_coverage: t("comparisonPartialReason"), outside_cache_coverage: t("comparisonOutside"), disabled: t("comparisonDisabled") } as Record<string, string>)[comparison?.reasonCode] || comparison?.reason || ""; }
function localizedComparisonStatus(status: string, t: (key: string) => string) { return ({ complete: t("comparisonComplete"), partial: t("comparisonPartial"), unavailable: t("comparisonUnavailable"), none: t("comparisonDisabled") } as Record<string, string>)[status] || t("unknown"); }
function cell(value: any, locale: string, column = "") { if (value === null || value === undefined || value === "") return "-"; if (typeof value === "number") return column.startsWith("change_") || /(^|_)(ctr|engagementRate)$/.test(column) ? pct(value) : fmt(value, locale); if (typeof value === "object") return JSON.stringify(value); return String(value); }
function metricLabel(value: string) { return ({ totalUsers: "Users", newUsers: "New users", engagedSessions: "Engaged Sessions", engagementRate: "Engagement Rate", screenPageViews: "Views", keyEvents: "Key events / Conversions", sessions: "Sessions" } as Record<string, string>)[value] || value; }
function csv(value: any) { const text = value === null || value === undefined ? "" : typeof value === "object" ? JSON.stringify(value) : String(value); return `"${text.replaceAll('"', '""')}"`; }
function download(name: string, content: string) { const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" })); link.download = name; link.click(); URL.revokeObjectURL(link.href); }
