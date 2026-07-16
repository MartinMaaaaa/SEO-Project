import { AlertTriangle, CheckCircle2, Download, FileJson, Monitor, Play, RefreshCw, Search, Smartphone, Wrench } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { CATEGORY_IDS, flattenAudits, latestByStrategy, normalizeClientUrl } from "../pagespeedModel.mjs";
import { useI18n } from "../i18n";
import { ActionBar, Disclosure, KpiCard, StatePanel, StatusBadge, type Tone } from "./Ui";

type Json = Record<string, any>;
type Device = "mobile" | "desktop";
type DevicePhase = "idle" | "running" | "success" | "error";

const categoryLabels: Record<string, string> = {
  performance: "Performance",
  accessibility: "Accessibility",
  "best-practices": "Best Practices",
  seo: "SEO",
};

async function requestJson(path: string, options?: RequestInit) {
  const response = await fetch(path, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(String(body.detail || `${response.status} ${response.statusText}`));
  return body;
}

export function PageExperienceWorkbench({ initialPagespeed, initialCrux }: { initialPagespeed?: Json; initialCrux?: Json }) {
  const { language } = useI18n();
  const zh = language === "zh-CN";
  const text = copy(zh);
  const initialResults = (initialPagespeed?.results || initialPagespeed?.runs || []) as Json[];
  const initialUrls = [...new Set(initialResults.map(item => String(item.urlKey || item.requestedUrl || "")).filter(Boolean))];
  const [results, setResults] = useState<Json[]>(initialResults);
  const [urlInput, setUrlInput] = useState(initialUrls[0] || "");
  const [validation, setValidation] = useState<{ normalized: string; error: string }>({ normalized: initialUrls[0] || "", error: "" });
  const [selectedDevice, setSelectedDevice] = useState<Device>("mobile");
  const [deviceState, setDeviceState] = useState<Record<Device, { phase: DevicePhase; message: string; started: number | null }>>({
    mobile: { phase: "idle", message: "", started: null },
    desktop: { phase: "idle", message: "", started: null },
  });
  const [now, setNow] = useState(Date.now());
  const [notice, setNotice] = useState("");
  const [crux, setCrux] = useState<Json>(initialCrux || {});
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [stateFilter, setStateFilter] = useState("needsAttention");
  const [groupFilter, setGroupFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [rawEvidence, setRawEvidence] = useState<Json | null>(null);
  const [taskStatus, setTaskStatus] = useState("");
  const resultSummaryRef = useRef<HTMLDivElement>(null);
  const errorRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    try { setValidation({ normalized: normalizeClientUrl(urlInput), error: "" }); }
    catch { setValidation({ normalized: "", error: urlInput ? text.invalidUrl : text.urlRequired }); }
  }, [urlInput, text.invalidUrl, text.urlRequired]);

  useEffect(() => {
    if (!Object.values(deviceState).some(item => item.phase === "running")) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [deviceState]);

  const scoped = useMemo(() => results.filter(item => !validation.normalized || item.urlKey === validation.normalized), [results, validation.normalized]);
  const latest = useMemo(() => latestByStrategy(scoped), [scoped]);
  useEffect(() => {
    if (!latest[selectedDevice] && latest.mobile) setSelectedDevice("mobile");
    else if (!latest[selectedDevice] && latest.desktop) setSelectedDevice("desktop");
  }, [latest.mobile, latest.desktop, selectedDevice]);
  const selected = latest[selectedDevice] as Json | null;
  const audits = useMemo(() => flattenAudits(selected || {}), [selected]);
  const groups = useMemo(() => [...new Set(audits.flatMap(item => item.groups || []).filter(Boolean))].sort(), [audits]);
  const visibleAudits = useMemo(() => audits.filter(item => {
    if (categoryFilter !== "all" && !item.categories.includes(categoryFilter)) return false;
    if (stateFilter !== "all" && item.state !== stateFilter) return false;
    if (groupFilter !== "all" && !item.groups.includes(groupFilter)) return false;
    return !search.trim() || item.searchText.includes(search.trim().toLowerCase());
  }).sort((a, b) => Number(b.savingsMs || 0) - Number(a.savingsMs || 0) || Number(b.weight || 0) - Number(a.weight || 0) || String(a.title).localeCompare(String(b.title))), [audits, categoryFilter, stateFilter, groupFilter, search]);
  const auditCsvContent = useMemo(() => {
    if (!selected) return "";
    const columns = ["id", "title", "state", "categories", "groups", "score", "displayValue", "numericValue", "numericUnit", "detailType", "savingsMs", "savingsBytes"];
    return [
      "# source=PageSpeed Insights / Lighthouse", `# url=${selected.urlKey}`, `# strategy=${selected.strategy}`,
      `# fetch_time=${selected.fetchTime || ""}`, `# lighthouse_version=${selected.lighthouseVersion || ""}`,
      `# extracted_at=${new Date().toISOString()}`, `# limitations=${JSON.stringify(selected.limitations || [])}`,
      columns.join(","),
      ...visibleAudits.map(item => columns.map(key => csvValue(Array.isArray(item[key]) ? item[key].join("|") : item[key])).join(",")),
    ].join("\n");
  }, [selected, visibleAudits]);

  async function reloadSaved(preferredUrl = validation.normalized) {
    if (!preferredUrl) {
      errorRef.current?.focus();
      return;
    }
    setNotice(text.loadingSaved);
    try {
      const [saved, field] = await Promise.all([
        requestJson(`/api/pagespeed/latest?url=${encodeURIComponent(preferredUrl)}`),
        requestJson(`/api/crux/summary?url=${encodeURIComponent(preferredUrl)}`),
      ]);
      setResults(saved.results || []);
      setCrux(field || {});
      setRawEvidence(null);
      setNotice(saved.results?.length ? text.savedLoaded : text.noSaved);
    } catch (error) {
      setNotice(`${text.loadFailed}: ${String(error instanceof Error ? error.message : error)}`);
    }
  }

  async function runLive(devices: Device[]) {
    if (!validation.normalized) {
      setNotice(validation.error);
      errorRef.current?.focus();
      return;
    }
    const started = Date.now();
    setNotice(text.quotaNotice);
    setTaskStatus("");
    setRawEvidence(null);
    setDeviceState(current => ({
      ...current,
      ...Object.fromEntries(devices.map(device => [device, { phase: "running", message: text.running, started }])) as Record<Device, any>,
    }));
    try {
      const body = await requestJson("/api/pagespeed/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: validation.normalized, strategies: devices, categories: CATEGORY_IDS, locale: language }),
      });
      setDeviceState(current => {
        const next = { ...current };
        for (const device of devices) {
          const outcome = body.results?.[device];
          next[device] = outcome?.ok
            ? { phase: "success", message: text.savedSuccess, started: null }
            : { phase: "error", message: errorLabel(outcome?.error?.code, text) + (outcome?.error?.message ? ` · ${outcome.error.message}` : ""), started: null };
        }
        return next;
      });
      await reloadSaved(body.normalizedUrl || validation.normalized);
      window.setTimeout(() => resultSummaryRef.current?.focus(), 0);
    } catch (error) {
      const message = String(error instanceof Error ? error.message : error);
      setDeviceState(current => ({ ...current, ...Object.fromEntries(devices.map(device => [device, { phase: "error", message, started: null }])) as Record<Device, any> }));
      setNotice(`${text.testFailed}: ${message}`);
    }
  }

  async function loadRaw() {
    if (!selected || !validation.normalized) return;
    try {
      setRawEvidence(await requestJson(`/api/pagespeed/raw?url=${encodeURIComponent(validation.normalized)}&strategy=${selectedDevice}`));
    } catch (error) {
      setNotice(`${text.rawFailed}: ${String(error instanceof Error ? error.message : error)}`);
    }
  }

  async function createTask(audit: Json) {
    if (!selected) return;
    const evidence = {
      url: selected.urlKey,
      strategy: selected.strategy,
      fetchTime: selected.fetchTime,
      lighthouseVersion: selected.lighthouseVersion,
      auditId: audit.id,
      title: audit.title,
      displayValue: audit.displayValue ?? null,
      numericValue: audit.numericValue ?? null,
      numericUnit: audit.numericUnit ?? null,
      sourceDescription: audit.description,
      savingsMs: audit.savingsMs,
      savingsBytes: audit.savingsBytes,
      limitation: selected.limitations?.[2] || "Source-returned evidence does not prove ranking or business impact.",
    };
    try {
      const response = await requestJson("/api/ai/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ taskType: "pagespeed_technical_audit", title: `${audit.title} · ${selected.strategy}`, scope: { source: "PageSpeed Insights", url: selected.urlKey, strategy: selected.strategy }, evidence }) });
      setTaskStatus(`${text.taskCreated}: ${response.path}`);
    } catch (error) {
      setTaskStatus(`${text.taskFailed}: ${String(error instanceof Error ? error.message : error)}`);
    }
  }

  function exportLatestJson() {
    if (!selected) return;
    downloadFile(`pagespeed-${selected.strategy}-latest.json`, JSON.stringify(selected, null, 2), "application/json");
  }

  const statusTone: Tone = notice.includes(text.failedWord) ? "bad" : Object.values(deviceState).some(item => item.phase === "running") ? "info" : "neutral";
  return <div className="psiWorkbench">
    <section className="panel priority-primary psiControlPanel" aria-labelledby="psi-controls-title">
      <header className="panelHeader"><div><p className="sectionKicker">LIVE API · LOCAL LATEST</p><h2 id="psi-controls-title">{text.testTitle}</h2></div><StatusBadge tone={statusTone}>{text.explicitOnly}</StatusBadge></header>
      <label className="psiUrlLabel" htmlFor="psi-url">{text.urlLabel}</label>
      <div className="psiUrlRow"><input id="psi-url" value={urlInput} onChange={event => setUrlInput(event.target.value)} placeholder="https://example.com/page" aria-invalid={Boolean(validation.error)} aria-describedby="psi-url-help" list="psi-saved-urls" /><datalist id="psi-saved-urls">{[...new Set(results.map(item => item.urlKey).filter(Boolean))].map(item => <option key={item} value={item} />)}</datalist><button onClick={() => void reloadSaved()} disabled={!validation.normalized}><RefreshCw size={16} />{text.reloadSaved}</button></div>
      <p id="psi-url-help" ref={errorRef} tabIndex={-1} className={validation.error ? "fieldError" : "normalizedPreview"}>{validation.error || `${text.normalized}: ${validation.normalized}`}</p>
      <ActionBar label={text.liveActions}>
        <button className="primary" onClick={() => void runLive(["mobile"])} disabled={!validation.normalized || deviceState.mobile.phase === "running"}><Smartphone size={16} />{text.testMobile}</button>
        <button className="primary" onClick={() => void runLive(["desktop"])} disabled={!validation.normalized || deviceState.desktop.phase === "running"}><Monitor size={16} />{text.testDesktop}</button>
        <button onClick={() => void runLive(["mobile", "desktop"])} disabled={!validation.normalized || deviceState.mobile.phase === "running" || deviceState.desktop.phase === "running"}><Play size={16} />{text.testBoth}</button>
      </ActionBar>
      <p className="notice psiQuotaNotice">{text.quotaNotice}</p>
      <div className="psiDeviceProgress" aria-live="polite">
        {(["mobile", "desktop"] as Device[]).map(device => <DeviceState key={device} device={device} state={deviceState[device]} now={now} result={latest[device]} text={text} />)}
      </div>
      <p className="srLive" role="status" aria-live="polite">{notice}</p>
    </section>

    <section ref={resultSummaryRef} tabIndex={-1} className="panel priority-primary psiResults" aria-labelledby="psi-results-title">
      <header className="panelHeader psiResultsHeader"><div><p className="sectionKicker">LATEST SUCCESS · NO HISTORY</p><h2 id="psi-results-title">{text.latestTitle}</h2></div>{selected && <StatusBadge tone={selected.latestAttempt?.status === "failed" ? "warn" : "good"}>{selected.latestAttempt?.status === "failed" ? text.lastAttemptFailed : text.saved}</StatusBadge>}</header>
      {!latest.mobile && !latest.desktop ? <StatePanel tone="neutral" title={text.noSaved} detail={text.noSavedDetail} /> : <>
        <div className="psiTabs" role="tablist" aria-label={text.deviceTabs}>{(["mobile", "desktop"] as Device[]).map(device => <button key={device} role="tab" aria-selected={selectedDevice === device} aria-controls={`psi-panel-${device}`} id={`psi-tab-${device}`} className={selectedDevice === device ? "active" : ""} disabled={!latest[device]} tabIndex={selectedDevice === device ? 0 : -1} onClick={() => setSelectedDevice(device)} onKeyDown={event => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault()
            setSelectedDevice(device)
            return
          }
          if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
            event.preventDefault()
            const next: Device = device === "mobile" ? "desktop" : "mobile"
            if (latest[next]) {
              setSelectedDevice(next)
              window.requestAnimationFrame(() => document.getElementById(`psi-tab-${next}`)?.focus())
            }
          }
        }}>{device === "mobile" ? <Smartphone size={15} /> : <Monitor size={15} />}{device === "mobile" ? text.mobile : text.desktop}</button>)}</div>
        <DeviceComparison mobile={latest.mobile} desktop={latest.desktop} text={text} />
        {selected && <div role="tabpanel" id={`psi-panel-${selectedDevice}`} aria-labelledby={`psi-tab-${selectedDevice}`}>
          {selected.latestAttempt?.status === "failed" && <StatePanel tone="warn" title={text.lastAttemptFailed} detail={`${errorLabel(selected.latestAttempt.errorCode, text)} · ${selected.latestAttempt.message || ""}. ${text.successPreserved}`} />}
          <SourceMetadata result={selected} text={text} />
          <section className="psiScoreGrid" aria-label={text.categoryScores}>{CATEGORY_IDS.map(category => <KpiCard key={category} label={categoryLabels[category]} value={scoreValue(selected.categories?.[category]?.score, text)} detail={selected.categories?.[category] ? text.sourceScore : text.notReturned} tone={scoreTone(selected.categories?.[category]?.score)} />)}</section>
          <section className="psiMetricGrid" aria-label={text.labMetrics}>{Object.entries(selected.metrics || {}).map(([id, metric]: any) => <KpiCard key={id} label={metricLabel(id)} value={metric?.displayValue ?? text.unavailable} detail={metric?.numericValue === null || metric?.numericValue === undefined ? text.notReturned : `${metric.numericValue} ${metric.numericUnit || ""}`} />)}{!Object.keys(selected.metrics || {}).length && <StatePanel tone="neutral" title={text.noMetrics} />}</section>
          <p className="notice">{text.inpNotice}</p>
          {safeImage(selected.fullPageScreenshot?.screenshot?.data) && <Disclosure title={zh ? "整页截图" : "Full-page screenshot"} summary={zh ? "Lighthouse 来源返回的整页截图（延迟加载）" : "Source-returned Lighthouse full-page screenshot (lazy loaded)"}><img className="psiFullScreenshot" loading="lazy" src={selected.fullPageScreenshot.screenshot.data} alt={zh ? "Lighthouse 整页截图证据" : "Lighthouse full-page screenshot evidence"} /></Disclosure>}
        </div>}
      </>}
    </section>

    {selected && <section className="panel priority-primary psiAuditSection" aria-labelledby="psi-audits-title">
      <header className="panelHeader"><div><p className="sectionKicker">SOURCE-BACKED AUDITS</p><h2 id="psi-audits-title">{text.auditTitle}</h2><p>{text.auditPurpose}</p></div><span className="rowCount">{visibleAudits.length}/{audits.length}</span></header>
      <ActionBar label={text.exportActions}><a className="downloadAction" href={`data:text/csv;charset=utf-8,${encodeURIComponent(`\uFEFF${auditCsvContent}`)}`} download={`pagespeed-${selected.strategy}-audits.csv`}><Download size={16} />CSV</a><button onClick={exportLatestJson}><FileJson size={16} />JSON</button></ActionBar>
      <div className="psiAuditFilters">
        <label>{text.category}<select value={categoryFilter} onChange={event => setCategoryFilter(event.target.value)}><option value="all">{text.all}</option>{CATEGORY_IDS.map(id => <option key={id} value={id}>{categoryLabels[id]}</option>)}</select></label>
        <label>{text.auditState}<select value={stateFilter} onChange={event => setStateFilter(event.target.value)}><option value="all">{text.all}</option>{["needsAttention", "passed", "manual", "informative", "notApplicable", "unscored"].map(value => <option key={value} value={value}>{stateLabel(value, text)}</option>)}</select></label>
        <label>{text.group}<select value={groupFilter} onChange={event => setGroupFilter(event.target.value)}><option value="all">{text.all}</option>{groups.map(value => <option key={value} value={value}>{selected.categoryGroups?.[value]?.title || value}</option>)}</select></label>
        <label>{text.search}<span className="inputWithIcon"><Search size={15} /><input value={search} onChange={event => setSearch(event.target.value)} placeholder={text.searchPlaceholder} /></span></label>
      </div>
      {visibleAudits.length ? <div className="psiAuditList">{visibleAudits.map(audit => <AuditCard key={audit.id} audit={audit} text={text} onTask={() => void createTask(audit)} />)}</div> : <StatePanel tone="neutral" title={text.noAuditMatch} />}
      {taskStatus && <p className="notice" role="status">{taskStatus}</p>}
    </section>}

    <section className="panel priority-secondary psiCruxSection" aria-labelledby="psi-crux-title">
      <header className="panelHeader"><div><p className="sectionKicker">CHROME UX REPORT · FIELD</p><h2 id="psi-crux-title">{text.cruxTitle}</h2><p>{text.cruxPurpose}</p></div><StatusBadge tone={crux.status === "ok" ? "good" : crux.status === "no_data" ? "warn" : "neutral"}>{crux.displayStatus || text.loading}</StatusBadge></header>
      {crux.status !== "ok" ? <StatePanel tone="warn" title="No dataset" detail={crux.message || text.noCrux} /> : <CruxEvidence crux={crux} text={text} />}
    </section>

    <Disclosure title={text.technicalTitle} summary={text.technicalSummary} count={(selected?.runWarnings?.length || 0) + (selected ? 1 : 0)}>
      {!selected ? <p className="empty">{text.noSaved}</p> : <>
        <div className="psiTechnicalGrid"><Key label="URL key" value={selected.urlKey} /><Key label="Requested URL" value={selected.requestedUrl} /><Key label="Final URL" value={selected.finalUrl} /><Key label="Fetch time" value={selected.fetchTime} /><Key label="Saved time" value={selected.savedAt} /><Key label="Lighthouse" value={selected.lighthouseVersion} /><Key label="Locale" value={selected.locale} /><Key label="Raw reference" value={selected.rawReference} /></div>
        <Disclosure title={text.warningsEnvironment} summary={text.sourceTechnical}><pre>{limitedJson({ runWarnings: selected.runWarnings, environment: selected.environment, configSettings: selected.configSettings, timing: selected.timing })}</pre></Disclosure>
        <Disclosure title={text.rawTitle} summary={text.rawSummary}>
          {!rawEvidence ? <button onClick={() => void loadRaw()}><FileJson size={16} />{text.loadRaw}</button> : <><button onClick={() => downloadFile(`pagespeed-${selectedDevice}-raw.json`, JSON.stringify(rawEvidence, null, 2), "application/json")}><Download size={16} />{text.downloadRaw}</button><pre>{limitedJson(rawEvidence, 120000)}</pre></>}
        </Disclosure>
      </>}
    </Disclosure>
  </div>;
}

function DeviceState({ device, state, now, result, text }: { device: Device; state: { phase: DevicePhase; message: string; started: number | null }; now: number; result: Json | null; text: Json }) {
  const tone: Tone = state.phase === "success" ? "good" : state.phase === "error" ? "bad" : state.phase === "running" ? "info" : result ? "neutral" : "neutral";
  return <article className={`psiDeviceState ${state.phase}`}><div><strong>{device === "mobile" ? text.mobile : text.desktop}</strong><StatusBadge tone={tone}>{state.phase === "idle" ? (result ? text.saved : text.idle) : state.phase === "running" ? text.running : state.phase === "success" ? text.completed : text.failedWord}</StatusBadge></div><p>{state.phase === "running" && state.started ? `${text.elapsed}: ${Math.max(0, Math.floor((now - state.started) / 1000))}s` : state.message || (result ? `${text.savedAt}: ${result.savedAt || "—"}` : text.notTested)}</p></article>;
}

function DeviceComparison({ mobile, desktop, text }: { mobile: Json | null; desktop: Json | null; text: Json }) {
  return <section className="psiComparison" aria-label={text.comparisonTitle}><h3>{text.comparisonTitle}</h3><div>{(["mobile", "desktop"] as Device[]).map(device => { const result = device === "mobile" ? mobile : desktop; return <article key={device}><span>{device === "mobile" ? text.mobile : text.desktop}</span>{result ? <><strong>Performance {scoreValue(result.categories?.performance?.score, text)}</strong><small>{result.fetchTime || "—"}</small><div>{CATEGORY_IDS.map(category => <span key={category}>{categoryLabels[category]} <b>{scoreValue(result.categories?.[category]?.score, text)}</b></span>)}</div></> : <p>{text.noSavedDevice}</p>}</article>; })}</div></section>;
}

function SourceMetadata({ result, text }: { result: Json; text: Json }) {
  return <dl className="psiMetadata"><div><dt>{text.requested}</dt><dd>{result.requestedUrl || "—"}</dd></div><div><dt>{text.final}</dt><dd>{result.finalUrl || "—"}</dd></div><div><dt>{text.fetched}</dt><dd>{result.fetchTime || "—"}</dd></div><div><dt>{text.savedAt}</dt><dd>{result.savedAt || "—"}</dd></div><div><dt>Lighthouse</dt><dd>{result.lighthouseVersion || "—"}</dd></div><div><dt>{text.freshness}</dt><dd>{freshness(result.savedAt, text)}</dd></div></dl>;
}

function AuditCard({ audit, text, onTask }: { audit: Json; text: Json; onTask: () => void }) {
  const tone: Tone = audit.state === "passed" ? "good" : audit.state === "needsAttention" ? "warn" : "neutral";
  return <Disclosure className="psiAuditCard" title={audit.title || audit.id} summary={<span>{audit.id} · {audit.displayValue ?? stateLabel(audit.state, text)}</span>} count={stateLabel(audit.state, text)} tone={tone}>
    <div className="psiAuditMeta"><StatusBadge tone={tone}>{stateLabel(audit.state, text)}</StatusBadge>{audit.categories.map((category: string) => <span key={category}>{categoryLabels[category]}</span>)}{audit.groups.map((group: string) => <span key={group}>{group}</span>)}<span>{audit.detailType}</span></div>
    {audit.description && <p className="psiAuditDescription">{audit.description}</p>}
    {(audit.savingsMs !== null || audit.savingsBytes !== null) && <p className="psiSavings">{audit.savingsMs !== null && `${text.savingsTime}: ${audit.savingsMs} ms`}{audit.savingsMs !== null && audit.savingsBytes !== null ? " · " : ""}{audit.savingsBytes !== null && `${text.savingsBytes}: ${formatBytes(audit.savingsBytes)}`}</p>}
    <AuditDetails details={audit.details} text={text} />
    {(audit.documentationLinks || []).map((href: string) => safeHref(href) ? <a key={href} href={href} target="_blank" rel="noreferrer">{text.sourceDocumentation}</a> : null)}
    <button onClick={onTask}><Wrench size={15} />{text.createTask}</button>
  </Disclosure>;
}

function AuditDetails({ details, text }: { details: Json | null; text: Json }) {
  if (!details) return <p className="empty">{text.noStructuredDetail}</p>;
  const type = details.type || "unknown";
  if (type === "screenshot" && safeImage(details.data)) return <img className="psiScreenshot" loading="lazy" src={details.data} alt={text.lighthouseScreenshot} />;
  if (type === "filmstrip") return <div className="psiFilmstrip">{(details.items || []).slice(0, 12).map((item: Json, index: number) => safeImage(item.data) ? <figure key={index}><img loading="lazy" src={item.data} alt={`${text.filmstrip} ${index + 1}`} /><figcaption>{item.timing ?? "—"} ms</figcaption></figure> : null)}</div>;
  if (["table", "opportunity", "list"].includes(type) && Array.isArray(details.items)) return <DetailTable headings={details.headings || []} items={details.items} text={text} />;
  return <div className="psiUnknownDetail"><p>{text.unknownDetail}: <code>{type}</code></p><pre>{limitedJson(details, 30000)}</pre></div>;
}

function DetailTable({ headings, items, text }: { headings: Json[]; items: Json[]; text: Json }) {
  const columns = headings.length ? headings.map(item => String(item.key || item.label || "value")) : [...new Set(items.slice(0, 10).flatMap(item => Object.keys(item || {})))].slice(0, 12);
  return <div className="psiResourceTable" role="region" aria-label={text.resourceTable} tabIndex={0}><table><thead><tr>{columns.map(column => <th key={column}>{headings.find(item => item.key === column)?.label || column}</th>)}</tr></thead><tbody>{items.slice(0, 100).map((item, index) => <tr key={index}>{columns.map(column => <td key={column}>{detailCell(item?.[column])}</td>)}</tr>)}</tbody></table>{items.length > 100 && <p>{text.truncatedRows}: {items.length}</p>}</div>;
}

function CruxEvidence({ crux, text }: { crux: Json; text: Json }) {
  const metrics = Object.entries(crux.metrics || {});
  return <><div className="psiCruxMeta"><Key label={text.scope} value={crux.scope} /><Key label={text.formFactor} value={crux.formFactor} /><Key label={text.originFallback} value={crux.originFallback ? text.yes : text.no} /><Key label={text.collectionPeriod} value={limitedJson(crux.collectionPeriod, 1000)} /></div>{crux.originFallback && <StatePanel tone="warn" title={text.originFallbackTitle} detail={text.originFallbackDetail} />}<div className="psiMetricGrid">{metrics.map(([name, metric]: any) => <KpiCard key={name} label={cruxMetricLabel(name)} value={metric?.p75 ?? text.unavailable} detail={Array.isArray(metric?.histogram) ? `${metric.histogram.length} ${text.distributionBuckets}` : text.noDistribution} />)}</div>{crux.assessment === null && <p className="notice">{text.noCwvAssessment}</p>}</>;
}

function Key({ label, value }: { label: string; value: any }) { return <div className="keyValue"><span>{label}</span><strong>{value === null || value === undefined || value === "" ? "—" : String(value)}</strong></div>; }
function scoreValue(value: any, text: Json) { return value === null || value === undefined ? text.unavailable : String(value); }
function scoreTone(value: any): Tone { return value === null || value === undefined ? "neutral" : value >= 90 ? "good" : value >= 50 ? "warn" : "bad"; }
function metricLabel(id: string) { return ({ "first-contentful-paint": "FCP", "largest-contentful-paint": "LCP", "speed-index": "Speed Index", "total-blocking-time": "TBT", "cumulative-layout-shift": "CLS" } as Record<string, string>)[id] || id; }
function cruxMetricLabel(id: string) { return ({ largest_contentful_paint: "LCP p75", interaction_to_next_paint: "INP p75", cumulative_layout_shift: "CLS p75", first_contentful_paint: "FCP p75", experimental_time_to_first_byte: "TTFB p75" } as Record<string, string>)[id] || id; }
function stateLabel(value: string, text: Json) { return text.states[value] || value; }
function errorLabel(value: string, text: Json) { return text.errors[value] || value || text.failedWord; }
function freshness(savedAt: string, text: Json) { const time = Date.parse(savedAt || ""); if (!Number.isFinite(time)) return text.unknown; const days = Math.max(0, Math.floor((Date.now() - time) / 86400000)); return days > 7 ? `${text.stale} · ${days}d` : `${text.fresh} · ${days}d`; }
function safeHref(value: string) { try { return new URL(value).protocol === "https:"; } catch { return false; } }
function safeImage(value: any) { return typeof value === "string" && /^data:image\/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(value); }
function detailCell(value: any): string { if (value === null || value === undefined) return "—"; if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value); if (typeof value === "object" && value.snippet) return String(value.snippet); return limitedJson(value, 2000); }
function limitedJson(value: any, max = 60000) { const output = JSON.stringify(value, null, 2) || ""; return output.length > max ? `${output.slice(0, max)}\n… [truncated in view]` : output; }
function formatBytes(value: number) { return value >= 1048576 ? `${(value / 1048576).toFixed(2)} MB` : value >= 1024 ? `${(value / 1024).toFixed(1)} KB` : `${value} B`; }
function csvValue(value: any) { const text = value === null || value === undefined ? "" : String(value); return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text; }
function downloadFile(name: string, content: string, type: string) { const blob = new Blob([content], { type }); const href = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = href; anchor.download = name; anchor.click(); window.setTimeout(() => URL.revokeObjectURL(href), 1000); }

function copy(zh: boolean): Json {
  return zh ? {
    testTitle: "实时 PageSpeed 测试与本地最新结果", explicitOnly: "仅由用户明确触发", urlLabel: "公开页面 URL", invalidUrl: "请输入有效的公开 http/https URL；不支持凭据、私有地址或其他 scheme。", urlRequired: "请输入公开页面 URL。", normalized: "规范化预览", reloadSaved: "重新读取已保存结果", liveActions: "实时 API 测试", testMobile: "测试 Mobile", testDesktop: "测试 Desktop", testBoth: "测试两者", quotaNotice: "实时测试会调用 PageSpeed Insights API 并消耗配额；重新读取只访问本地缓存。", running: "测试进行中", elapsed: "已用时", savedSuccess: "真实结果已完成本地保存", completed: "已完成", failedWord: "失败", idle: "待命", notTested: "尚未在本次会话测试", saved: "已保存", savedAt: "保存时间", loadingSaved: "正在读取本地最新结果…", savedLoaded: "已重新读取本地最新结果。", noSaved: "没有已保存结果", noSavedDetail: "输入公开 URL 后运行实时测试，或重新读取已保存结果。", loadFailed: "读取失败", testFailed: "测试失败", rawFailed: "raw 证据读取失败", latestTitle: "同一页面的最新 Mobile 与 Desktop", deviceTabs: "设备结果", mobile: "Mobile", desktop: "Desktop", noSavedDevice: "该设备没有成功结果", comparisonTitle: "最新 Mobile vs Desktop", lastAttemptFailed: "最近尝试失败", successPreserved: "上一份成功结果仍已保留。", requested: "请求 URL", final: "最终 URL", fetched: "抓取时间", freshness: "新鲜度", fresh: "新鲜", stale: "已过期", unknown: "未知", categoryScores: "Lighthouse 四类别分数", sourceScore: "Lighthouse source score", notReturned: "来源未返回", unavailable: "不可用", labMetrics: "实验室指标", noMetrics: "来源未返回核心实验室指标", inpNotice: "Lighthouse 实验室结果不包含实测 INP。TBT 是相关的主线程阻塞诊断代理，但不是 INP。", auditTitle: "审计、机会与诊断", auditPurpose: "按 Lighthouse 返回的 category refs、group、state 与 detail type 组织；不添加自创建议。", exportActions: "导出来源证据", category: "类别", auditState: "审计状态", group: "分组", search: "搜索", searchPlaceholder: "Audit ID、标题或来源说明…", all: "全部", noAuditMatch: "没有匹配当前筛选的审计", states: { needsAttention: "需关注", passed: "已通过", manual: "需人工检查", informative: "信息", notApplicable: "不适用", unscored: "未评分" }, errors: { validation: "校验错误", timeout: "超时", rate_limited: "API 限流", forbidden: "API 禁止访问", upstream_error: "上游错误", runtime_error: "Lighthouse 运行错误", invalid_response: "无效响应", persistence_error: "本地持久化失败", network_error: "网络错误", in_progress: "相同 URL/device 已在测试" }, savingsTime: "来源估算节省时间", savingsBytes: "来源估算节省字节", sourceDocumentation: "来源文档", createTask: "创建技术 SEO 任务", taskCreated: "任务已创建", taskFailed: "任务创建失败", noStructuredDetail: "来源未返回结构化 detail。", lighthouseScreenshot: "Lighthouse 截图证据", filmstrip: "Lighthouse filmstrip 帧", unknownDetail: "未知 detail type；安全摘要如下", resourceTable: "审计资源明细（内部可滚动）", truncatedRows: "界面仅显示前 100 行；来源总行数", cruxTitle: "CrUX 实际用户数据", cruxPurpose: "Field 数据与 Lighthouse Lab 数据保持独立；page/origin/fallback 均明确标注。", loading: "载入中", noCrux: "当前 page/origin 没有 CrUX 数据；Lab 测试仍可使用。", scope: "范围", formFactor: "Form factor", originFallback: "Origin fallback", yes: "是", no: "否", collectionPeriod: "采集周期", originFallbackTitle: "正在显示 origin fallback", originFallbackDetail: "该数据不是 page-level；所有指标和导出都按 origin fallback 标注。", distributionBuckets: "个分布区间", noDistribution: "来源未返回分布", noCwvAssessment: "来源信息不足，未显示 Core Web Vitals assessment。", technicalTitle: "技术证据", technicalSummary: "warnings、environment/config、完整 raw 与持久化证据（默认折叠）", warningsEnvironment: "Warnings、environment 与 config", sourceTechnical: "来源原始技术字段的安全展示", rawTitle: "完整 raw payload", rawSummary: "仅从本地活动文件延迟读取；不会调用 Google", loadRaw: "读取本地 raw 证据", downloadRaw: "下载完整 raw JSON",
  } : {
    testTitle: "Live PageSpeed test and locally saved latest result", explicitOnly: "Explicit user action only", urlLabel: "Public page URL", invalidUrl: "Enter a valid public http/https URL. Credentials, private targets, and other schemes are not supported.", urlRequired: "Enter a public page URL.", normalized: "Normalized preview", reloadSaved: "Reload saved result", liveActions: "Live API tests", testMobile: "Test Mobile", testDesktop: "Test Desktop", testBoth: "Test both", quotaNotice: "Live tests call the PageSpeed Insights API and consume quota. Reload reads local persistence only.", running: "Test in progress", elapsed: "Elapsed", savedSuccess: "Real result completed local persistence", completed: "Completed", failedWord: "Failed", idle: "Idle", notTested: "Not tested in this session", saved: "Saved", savedAt: "Saved at", loadingSaved: "Reading locally saved latest results…", savedLoaded: "Locally saved latest results reloaded.", noSaved: "No saved result", noSavedDetail: "Enter a public URL and run a live test, or reload a saved result.", loadFailed: "Reload failed", testFailed: "Test failed", rawFailed: "Raw evidence failed", latestTitle: "Latest Mobile and Desktop for the same page", deviceTabs: "Device results", mobile: "Mobile", desktop: "Desktop", noSavedDevice: "No successful result for this device", comparisonTitle: "Latest Mobile vs Desktop", lastAttemptFailed: "Latest attempt failed", successPreserved: "The previous successful result remains available.", requested: "Requested URL", final: "Final URL", fetched: "Fetched at", freshness: "Freshness", fresh: "Fresh", stale: "Stale", unknown: "Unknown", categoryScores: "Four Lighthouse category scores", sourceScore: "Lighthouse source score", notReturned: "Not returned by source", unavailable: "Unavailable", labMetrics: "Lab metrics", noMetrics: "No core lab metrics were returned", inpNotice: "Lighthouse Lab results do not measure INP. TBT is a related main-thread blocking diagnostic proxy, not INP.", auditTitle: "Audits, opportunities and diagnostics", auditPurpose: "Organized from returned category refs, groups, states and detail types; no invented advice.", exportActions: "Export source evidence", category: "Category", auditState: "Audit state", group: "Group", search: "Search", searchPlaceholder: "Audit ID, title or source description…", all: "All", noAuditMatch: "No audits match the active filters", states: { needsAttention: "Needs attention", passed: "Passed", manual: "Manual", informative: "Informative", notApplicable: "Not applicable", unscored: "Unscored" }, errors: { validation: "Validation error", timeout: "Timeout", rate_limited: "API rate limited", forbidden: "API forbidden", upstream_error: "Upstream error", runtime_error: "Lighthouse runtime error", invalid_response: "Invalid response", persistence_error: "Local persistence error", network_error: "Network error", in_progress: "The same URL/device is already running" }, savingsTime: "Source estimated time savings", savingsBytes: "Source estimated byte savings", sourceDocumentation: "Source documentation", createTask: "Create technical SEO task", taskCreated: "Task created", taskFailed: "Task creation failed", noStructuredDetail: "No structured detail returned by the source.", lighthouseScreenshot: "Lighthouse screenshot evidence", filmstrip: "Lighthouse filmstrip frame", unknownDetail: "Unknown detail type; safe summary follows", resourceTable: "Audit resource details (internally scrollable)", truncatedRows: "UI shows the first 100 rows; source total", cruxTitle: "CrUX field data", cruxPurpose: "Field evidence stays separate from Lighthouse Lab evidence; page/origin/fallback is explicit.", loading: "Loading", noCrux: "No CrUX dataset exists for this page/origin. Lab testing remains available.", scope: "Scope", formFactor: "Form factor", originFallback: "Origin fallback", yes: "Yes", no: "No", collectionPeriod: "Collection period", originFallbackTitle: "Showing origin fallback", originFallbackDetail: "This is not page-level data; every affected metric and export remains labelled as origin fallback.", distributionBuckets: "distribution buckets", noDistribution: "No distribution returned", noCwvAssessment: "Source evidence is insufficient, so no Core Web Vitals assessment is shown.", technicalTitle: "Technical evidence", technicalSummary: "Warnings, environment/config, full raw and persistence evidence (closed by default)", warningsEnvironment: "Warnings, environment and config", sourceTechnical: "Safe display of source-original technical fields", rawTitle: "Complete raw payload", rawSummary: "Lazy local active-file read only; never calls Google", loadRaw: "Load local raw evidence", downloadRaw: "Download complete raw JSON",
  };
}
