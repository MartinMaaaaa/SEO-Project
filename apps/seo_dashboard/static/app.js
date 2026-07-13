const state = {
  status: null,
  gsc: null,
  ga4: null,
  pagespeed: null,
  crux: null,
  storage: null,
  latestTaskPath: "",
  activeView: "overview",
  gscFilters: [],
  gscDetail: null,
};

const tableStates = new Map();
const chartModels = new Map();

const viewCopy = {
  overview: ["总览", "跨 GSC、GA4、PageSpeed 的核心 SEO 数据视图。"],
  gsc: ["GSC 查询分析", "按关键词、URL、日期和曝光阈值筛选自然搜索表现。"],
  ga4: ["GA4 行为分析", "用图表查看访问、用户、浏览、参与和渠道结构。"],
  pagespeed: ["PageSpeed 性能", "按页面保存性能抓取历史，标记抓取时间和过期状态。"],
  crux: ["CrUX 体验", "查看真实用户 Core Web Vitals 数据是否可用。"],
  ai: ["AI 分析任务", "生成英文任务提示词，交给 AI 基于最新数据继续分析。"],
  storage: ["运维监控", "集中查看数据库容量、API 额度、日志异常和同步历史。"],
  settings: ["连接与同步", "检查 API 配置状态、预留运维配置并触发数据同步。"],
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));
const fmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const pct = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 });

document.addEventListener("DOMContentLoaded", () => {
  bindNavigation();
  bindActions();
  bindGlobalTooltips();
  restoreSidebar();
  loadAll();
});

function bindNavigation() {
  $$(".nav-item").forEach((button) => {
    button.title = button.querySelector(".nav-label")?.textContent || button.textContent.trim();
    button.addEventListener("click", () => showView(button.dataset.view));
  });
  $("#openSettings").addEventListener("click", () => showView("settings"));
  $("#sidebarToggle").addEventListener("click", toggleSidebar);
}

function showView(view) {
  state.activeView = view;
  $$(".nav-item").forEach((item) => {
    const active = item.dataset.view === view;
    item.classList.toggle("active", active);
    if (active) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
  $$(".view").forEach((section) => section.classList.toggle("active", section.id === view));
  const [title, subtitle] = viewCopy[view] || viewCopy.overview;
  $("#viewTitle").textContent = title;
  $("#viewSubtitle").textContent = subtitle;
  redrawCurrentView(view);
}

function restoreSidebar() {
  const collapsed = localStorage.getItem("seoSidebarCollapsed") === "true";
  $(".app-shell").classList.toggle("sidebar-collapsed", collapsed);
  updateSidebarToggle(collapsed);
}

function toggleSidebar() {
  const shell = $(".app-shell");
  const collapsed = !shell.classList.contains("sidebar-collapsed");
  shell.classList.toggle("sidebar-collapsed", collapsed);
  localStorage.setItem("seoSidebarCollapsed", String(collapsed));
  updateSidebarToggle(collapsed);
  window.setTimeout(() => redrawCurrentView(state.activeView), 180);
}

function updateSidebarToggle(collapsed) {
  const button = $("#sidebarToggle");
  button.textContent = collapsed ? "›" : "‹";
  button.title = collapsed ? "展开侧边栏" : "折叠侧边栏";
  button.setAttribute("aria-label", button.title);
}

function bindGlobalTooltips() {
  document.addEventListener("pointerover", (event) => {
    const target = event.target.closest("[data-tooltip]");
    if (!target) return;
    showDataTooltip(target.dataset.tooltip || "", event.clientX, event.clientY);
  });
  document.addEventListener("pointermove", (event) => {
    if (!event.target.closest("[data-tooltip]")) return;
    positionDataTooltip(event.clientX, event.clientY);
  });
  document.addEventListener("pointerout", (event) => {
    if (event.target.closest("[data-tooltip]")) hideDataTooltip();
  });
  document.addEventListener("focusin", (event) => {
    const target = event.target.closest("[data-tooltip]");
    if (!target) return;
    const rect = target.getBoundingClientRect();
    showDataTooltip(target.dataset.tooltip || "", rect.left + rect.width / 2, rect.bottom);
  });
  document.addEventListener("focusout", (event) => {
    if (event.target.closest("[data-tooltip]")) hideDataTooltip();
  });
}

function showDataTooltip(content, x, y, html = false) {
  const tooltip = $("#dataTooltip");
  if (!content) return;
  if (html) tooltip.innerHTML = content;
  else tooltip.textContent = content;
  tooltip.classList.add("visible");
  positionDataTooltip(x, y);
}

function positionDataTooltip(x, y) {
  const tooltip = $("#dataTooltip");
  const left = Math.min(x + 14, window.innerWidth - tooltip.offsetWidth - 12);
  const top = Math.min(y + 16, window.innerHeight - tooltip.offsetHeight - 12);
  tooltip.style.left = `${Math.max(left, 12)}px`;
  tooltip.style.top = `${Math.max(top, 12)}px`;
}

function hideDataTooltip() {
  $("#dataTooltip").classList.remove("visible");
}

function bindActions() {
  $("#refreshData").addEventListener("click", loadAll);
  $("#syncGscTop").addEventListener("click", syncGsc);
  $("#syncGscSettings").addEventListener("click", syncGsc);
  $("#syncGa4").addEventListener("click", syncGa4);
  $("#syncGa4Top").addEventListener("click", syncGa4);
  $("#syncGa4Settings").addEventListener("click", syncGa4);
  $("#syncPageSpeed").addEventListener("click", syncPageSpeed);
  $("#syncPageSpeedTop").addEventListener("click", syncPageSpeed);
  $("#syncPageSpeedSettings").addEventListener("click", syncPageSpeed);
  $("#syncCrux").addEventListener("click", syncCrux);
  $("#syncCruxTop").addEventListener("click", syncCrux);
  $("#syncCruxSettings").addEventListener("click", syncCrux);
  $("#refreshStorage").addEventListener("click", loadStorage);
  $("#applyGscFilters").addEventListener("click", loadGscExplorer);
  $("#reloadGsc").addEventListener("click", loadGscExplorer);
  $("#addGscFilter").addEventListener("click", addGscFilter);
  $("#resetGscFilters").addEventListener("click", resetGscFilters);
  $("#exportGscCsv").addEventListener("click", exportGscCsv);
  $("#createGscTask").addEventListener("click", createScopedGscTask);
  $("#closeGscDetail").addEventListener("click", () => { state.gscDetail = null; renderGscDetail(); });
  $("#ga4ChannelFilter").addEventListener("change", loadGa4Analytics);
  $("#ga4ChartMode").addEventListener("change", renderGa4);
  $("#psiUrlSelect").addEventListener("change", () => {
    $("#psiUrlInput").value = $("#psiUrlSelect").value;
    renderPageSpeed();
  });
  $("#psiStrategy").addEventListener("change", renderPageSpeed);
  $("#createAiTask").addEventListener("click", createAiTask);
  $$(".action-menu-popover button").forEach((button) => {
    button.addEventListener("click", () => button.closest("details")?.removeAttribute("open"));
  });
}

async function loadAll() {
  await Promise.all([loadStatus(), loadGscExplorer(), loadGa4Analytics(), loadPageSpeed(), loadCrux(), loadStorage()]);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

async function loadStatus() {
  const data = await api("/api/status");
  state.status = data;
  const site = data.env.GSC_SITE_URL;
  const token = data.env.GSC_OAUTH_REFRESH_TOKEN;
  const ok = site?.configured && token?.configured;
  $("#connectionState").textContent = ok ? `已连接 ${site.value}` : "GSC 未配置";
  $("#connectionState").classList.toggle("ok", Boolean(ok));
  $("#settingSite").textContent = site?.value || "-";
  $("#settingToken").textContent = token?.configured ? token.value : "未配置";
  $("#settingGa4").textContent = data.env.GA4_PROPERTY_ID?.value || "-";
  $("#settingPageSpeed").textContent = data.env.PAGESPEED_API_KEY?.configured ? data.env.PAGESPEED_API_KEY.value : "未配置";
  $("#settingCrux").textContent = data.env.CRUX_API_KEY?.configured ? data.env.CRUX_API_KEY.value : "未配置";
}

async function loadGscExplorer() {
  const params = new URLSearchParams({
    preset: $("#gscPreset")?.value || "28",
    start: $("#gscStartDate")?.value || "",
    end: $("#gscEndDate")?.value || "",
    compare: $("#gscCompare")?.value || "previous",
    grain: $("#gscGrain")?.value || "day",
    dimension: $("#gscDimension")?.value || "query",
    filters: JSON.stringify(state.gscFilters),
    minImpressions: $("#gscMinImpressions")?.value || "0",
    sort: $("#gscSort")?.value || "clicks",
    limit: "50",
  });
  const data = await api(`/api/gsc/explorer?${params.toString()}`);
  state.gsc = data;
  $("#gscStartDate").value = data.filters?.start || "";
  $("#gscEndDate").value = data.filters?.end || "";
  renderGsc();
  renderOverview();
}

async function loadGa4Analytics() {
  const channel = $("#ga4ChannelFilter")?.value || "";
  const params = new URLSearchParams({ channel });
  const data = await api(`/api/ga4/analytics?${params.toString()}`);
  state.ga4 = data;
  renderGa4ChannelOptions(data.filters?.channels || []);
  renderGa4();
  renderOverview();
}

async function loadPageSpeed() {
  state.pagespeed = await api("/api/pagespeed/history");
  renderPageSpeedOptions();
  renderPageSpeed();
  renderOverview();
}

async function loadCrux() {
  state.crux = await api("/api/crux/summary");
  renderCrux();
}

async function loadStorage() {
  state.storage = await api("/api/storage/overview");
  renderStorage();
}

function renderOverview() {
  const gsc = state.gsc;
  const ga4 = state.ga4;
  const ps = selectedPageSpeedRun();
  if (gsc) {
    $("#kpiGscClicks").textContent = fmt.format(gsc.totals.clicks || 0);
    $("#kpiGscImpressions").textContent = fmt.format(gsc.totals.impressions || 0);
    $("#gscRangeTag").textContent = `${gsc.filters?.start || "-"} 至 ${gsc.filters?.end || "-"}`;
    renderRankList("#overviewQueryList", gsc.queries || [], "label", "clicks", "Clicks");
    renderRankList("#overviewPageList", gsc.pages || [], "label", "impressions", "Impr.");
    drawLineChart("overviewGscChart", gsc.trend || [], [
      { key: "clicks", label: "Clicks", color: "#38bdf8" },
      { key: "impressions", label: "Impressions", color: "#a78bfa" },
    ], { xKey: "date", xLabel: "日期", yLabel: "点击 / 曝光" });
  }
  if (ga4) {
    $("#kpiGa4Sessions").textContent = fmt.format(ga4.totals.sessions || 0);
    $("#kpiGa4Engagement").textContent = pct.format(ga4.totals.engagementRate || 0);
    drawBarChart("overviewChannelChart", ga4.channels || [], "channel", "sessions", "#22d3ee", {
      xLabel: "渠道",
      yLabel: "Sessions",
    });
  }
  $("#kpiPsiPerformance").textContent = ps ? fmt.format(ps.scores.performance || 0) : "-";
}

function renderGsc() {
  const data = state.gsc;
  if (!data) return;
  $("#gscClicks").textContent = fmt.format(data.totals.clicks || 0);
  $("#gscImpressions").textContent = fmt.format(data.totals.impressions || 0);
  $("#gscCtr").textContent = pct.format(data.totals.ctr || 0);
  $("#gscPosition").textContent = fmt.format(data.totals.position || 0);
  $("#gscSourceFile").textContent = data.sourceFile || "Local cache";
  const deltaText = (metric, percent = false, inverse = false) => {
    const delta = data.totals[`delta_${metric}`];
    const rate = data.totals[`change_${metric}`];
    if (delta == null) return "无对比数据";
    const good = inverse ? delta < 0 : delta > 0;
    return `${delta > 0 ? "+" : ""}${percent ? pct.format(delta) : fmt.format(delta)} · ${rate == null ? "基期为 0" : pct.format(rate)} ${good ? "改善" : delta === 0 ? "持平" : "下降"}`;
  };
  $("#gscClicksDelta").textContent = deltaText("clicks");
  $("#gscImpressionsDelta").textContent = deltaText("impressions");
  $("#gscCtrDelta").textContent = deltaText("ctr", true);
  $("#gscPositionDelta").textContent = deltaText("position", false, true);
  drawLineChart("gscTrendChart", data.trend || [], [
    { key: "clicks", label: "Clicks", color: "#38bdf8" },
    { key: "impressions", label: "Impressions", color: "#a78bfa" },
    { key: "ctr", label: "CTR", color: "#34d399", scale: 100, suffix: "%" },
  ], { xKey: "date", xLabel: "日期", yLabel: "数值 / CTR (%)" });
  renderGscScope();
  renderGscComparisonTable();
  renderGscDetail();
}

function addGscFilter() {
  const value = $("#gscFilterValue").value.trim();
  if (!value) return;
  state.gscFilters.push({ field: $("#gscFilterField").value, operator: $("#gscFilterOperator").value, value });
  $("#gscFilterValue").value = "";
  loadGscExplorer();
}

function resetGscFilters() { state.gscFilters = []; state.gscDetail = null; loadGscExplorer(); }

function renderGscScope() {
  const data = state.gsc;
  $("#gscFilterChips").innerHTML = state.gscFilters.map((item, index) => `<button type="button" data-filter-index="${index}">${escapeHtml(item.field)} ${escapeHtml(item.operator)} “${escapeHtml(item.value)}” ×</button>`).join("") || "<span>无维度筛选</span>";
  $$("#gscFilterChips [data-filter-index]").forEach((button) => button.addEventListener("click", () => { state.gscFilters.splice(Number(button.dataset.filterIndex), 1); loadGscExplorer(); }));
  const m = data.metadata || {};
  $("#gscScopeSummary").innerHTML = `<strong>${escapeHtml(data.filters.start)} 至 ${escapeHtml(data.filters.end)}</strong> · 对比 ${escapeHtml(data.filters.compareStart || "无")} 至 ${escapeHtml(data.filters.compareEnd || "无")} · 比较状态：${escapeHtml(data.filters.comparisonStatus)} · ${escapeHtml(data.filters.grain)} · ${escapeHtml(data.filters.dimension)}<br><span>来源：${escapeHtml(m.source || "-")} · 属性：${escapeHtml(m.property || "-")} · 时区：${escapeHtml(m.timezone || "-")} · 最新完整日期：${escapeHtml(m.latestCompleteDate || "-")} · 缓存覆盖：${escapeHtml(m.availableStart)} 至 ${escapeHtml(m.availableEnd)}</span><br><small>${escapeHtml((m.limitations || []).join(" "))}</small>`;
}

function renderGscComparisonTable() {
  const data = state.gsc; const dimension = data.filters.dimension;
  $("#gscTableTitle").textContent = `${dimension === "query" ? "Queries" : dimension === "page" ? "Pages" : "Dates"} 对比表`;
  $("#gscRowLimit").textContent = `最多 ${data.metadata.rowLimit} 行 · 当前 ${data.table.length}`;
  const columns = ["label", "clicks", "previous_clicks", "delta_clicks", "change_clicks", "click_contribution", "impressions", "ctr", "position"];
  const labels = { label: dimension, clicks: "当前 Clicks", previous_clicks: "对比 Clicks", delta_clicks: "变化", change_clicks: "变化率", click_contribution: "变化贡献", impressions: "曝光", ctr: "CTR", position: "平均排名" };
  const cell = (row, key) => row[key] == null ? "-" : key.includes("change") || key === "click_contribution" || key === "ctr" ? pct.format(row[key]) : key === "label" ? escapeHtml(row[key]) : fmt.format(row[key]);
  $("#gscComparisonTable").innerHTML = `<div class="table-scroll"><table><thead><tr>${columns.map((key) => `<th>${labels[key]}</th>`).join("")}</tr></thead><tbody>${data.table.map((row, index) => `<tr data-gsc-row="${index}" tabindex="0">${columns.map((key) => `<td title="${escapeHtml(String(row[key] ?? ""))}">${cell(row,key)}</td>`).join("")}</tr>`).join("") || `<tr><td colspan="9">当前范围无数据。可能原因：日期范围、筛选、匿名化或缓存未覆盖。</td></tr>`}</tbody></table></div>`;
  if (["query", "page"].includes(dimension)) $$("#gscComparisonTable [data-gsc-row]").forEach((row) => row.addEventListener("click", () => { state.gscDetail = { field: dimension, value: data.table[Number(row.dataset.gscRow)].label }; renderGscDetail(); }));
}

function renderGscDetail() {
  const box = $("#gscDetail"); if (!state.gscDetail) { box.innerHTML = "<p>尚未选择 Query 或 Page。</p>"; return; }
  const { field, value } = state.gscDetail; const related = field === "query" ? state.gsc.rows.filter((r) => r.query === value) : state.gsc.rows.filter((r) => r.page === value);
  const other = field === "query" ? "page" : "query";
  $("#gscDetailTitle").textContent = `${field === "query" ? "Keyword" : "Page"} Detail：${value}`;
  box.innerHTML = `<div class="status-card compact"><strong>${escapeHtml(value)}</strong><p>GA4 主要转化：Not configured · Country / Device / Search Appearance：需要新采集 · Cannibalization：仅可作为 heuristic。</p></div>`;
  renderRowsTable("#gscDetail", related, ["date", other, "clicks", "impressions", "ctr", "position"]);
}

function exportGscCsv() {
  const data = state.gsc; if (!data) return;
  const meta = { source: data.metadata.source, property: data.metadata.property, current: `${data.filters.start}/${data.filters.end}`, comparison: `${data.filters.compareStart}/${data.filters.compareEnd}`, timezone: data.metadata.timezone, dimension: data.filters.dimension, filters: state.gscFilters, exportedAt: new Date().toISOString(), limitations: data.metadata.limitations };
  const keys = Object.keys(data.table[0] || { label: "" }); const quote = (value) => `"${String(value ?? "").replaceAll('"','""')}"`;
  const csv = [`# metadata=${JSON.stringify(meta)}`, keys.map(quote).join(","), ...data.table.map((row) => keys.map((key) => quote(row[key])).join(","))].join("\r\n");
  const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" })); link.download = `gsc-analysis-${data.filters.dimension}-${data.filters.end}.csv`; link.click(); URL.revokeObjectURL(link.href);
}

async function createScopedGscTask() {
  const data = state.gsc; const evidence = (data.table || []).slice(0, 5).map((r) => ({ label: r.label, clicks: r.clicks, previousClicks: r.previous_clicks, deltaClicks: r.delta_clicks, contribution: r.click_contribution }));
  const context = JSON.stringify({ contractVersion: data.contractVersion, scope: data.filters, filters: state.gscFilters, sourceFile: data.sourceFile, limitations: data.metadata.limitations, evidence, requiredVerification: "Re-run the same saved scope after the action window; do not infer causality." }, null, 2);
  const result = await api("/api/ai/task", { method: "POST", body: JSON.stringify({ taskType: "gsc_scoped_investigation", context }) });
  state.latestTaskPath = result.path || ""; alert(result.path ? `已生成范围化任务：${result.path}` : "任务生成失败");
}

function renderGa4ChannelOptions(channels) {
  const select = $("#ga4ChannelFilter");
  const current = select.value;
  select.innerHTML = `<option value="">全部渠道</option>${channels.map((item) => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("")}`;
  select.value = channels.includes(current) ? current : "";
}

function renderGa4() {
  const data = state.ga4;
  if (!data) return;
  renderStatus("#ga4Status", data.status, data.sourceFile ? "GA4 数据已可用。" : "GA4 暂无数据。", data.sourceFile);
  $("#ga4Sessions").textContent = fmt.format(data.totals.sessions || 0);
  $("#ga4Users").textContent = fmt.format(data.totals.totalUsers || 0);
  $("#ga4Views").textContent = fmt.format(data.totals.screenPageViews || 0);
  $("#ga4Engaged").textContent = fmt.format(data.totals.engagedSessions || 0);
  renderRowsTable("#ga4ChannelTable", data.channels || [], ["channel", "sessions", "totalUsers", "screenPageViews", "engagementRate", "viewsPerSession"]);
  const mode = $("#ga4ChartMode").value;
  const titles = {
    sessions: "Sessions 趋势",
    users: "Users 趋势",
    views: "Views 趋势",
    engagement: "Engagement Rate 趋势",
    channels: "渠道 Sessions 对比",
  };
  $("#ga4ChartTitle").textContent = titles[mode] || "GA4 图表";
  if (mode === "channels") {
    drawBarChart("ga4MainChart", data.channels || [], "channel", "sessions", "#38bdf8", {
      xLabel: "渠道",
      yLabel: "Sessions",
    });
  } else if (mode === "engagement") {
    drawLineChart(
      "ga4MainChart",
      data.trend || [],
      [{ key: "engagementRate", label: "Engagement rate", color: "#34d399", scale: 100, suffix: "%" }],
      { xKey: "date", xLabel: "日期", yLabel: "参与率 (%)", maxValue: 100 }
    );
  } else {
    const keyMap = { sessions: "sessions", users: "totalUsers", views: "screenPageViews" };
    drawLineChart("ga4MainChart", data.trend || [], [{ key: keyMap[mode], label: titles[mode], color: "#22d3ee" }], {
      xKey: "date",
      xLabel: "日期",
      yLabel: titles[mode],
    });
  }
}

function renderPageSpeedOptions() {
  const data = state.pagespeed;
  if (!data) return;
  const select = $("#psiUrlSelect");
  const current = select.value;
  select.innerHTML = `<option value="">选择 GSC 页面</option>${(data.pages || [])
    .map((item) => `<option value="${escapeHtml(item.url)}">${escapeHtml(shortUrl(item.url))}${item.isStale ? " · 需刷新" : ""}</option>`)
    .join("")}`;
  select.value = current;
}

function renderPageSpeed() {
  const data = state.pagespeed;
  if (!data) return;
  const selected = selectedPageSpeedRun();
  renderStatus("#pagespeedStatus", data.status, selected ? `最新抓取：${selected.fetchedAt || selected.modified}` : "暂无 PageSpeed 抓取记录。", selected?.rawPath || "");
  const scores = selected?.scores || {};
  $("#pagespeedScores").innerHTML = ["performance", "accessibility", "bestPractices", "seo"]
    .map((key) => `<article class="score-card ${scoreClass(scores[key])}"><span>${scoreLabel(key)}</span><strong>${fmt.format(scores[key] || 0)}</strong></article>`)
    .join("");
  const metrics = selected?.metrics || {};
  $("#pagespeedMetrics").innerHTML = [
    ["LCP", metrics.lcp || "-"],
    ["TBT", metrics.tbt || "-"],
    ["CLS", metrics.cls || "-"],
    ["Speed Index", metrics.speedIndex || "-"],
    ["Fetched", selected?.fetchedAt || "-"],
    ["Status", selected?.isStale ? "建议重新抓取" : "数据新鲜"],
  ]
    .map(([label, value]) => `<div><strong>${escapeHtml(label)}</strong><span>${escapeHtml(value)}</span></div>`)
    .join("");
  const selectedUrl = $("#psiUrlInput").value || $("#psiUrlSelect").value;
  const selectedStrategy = $("#psiStrategy").value;
  const runs = (data.runs || [])
    .filter((run) => (!selectedUrl || run.url === selectedUrl) && (!selectedStrategy || run.strategy === selectedStrategy))
    .reverse();
  drawLineChart("pagespeedHistoryChart", runs, [
    { key: "performance", label: "Performance", color: "#38bdf8", path: "scores.performance" },
    { key: "accessibility", label: "Accessibility", color: "#34d399", path: "scores.accessibility" },
    { key: "seo", label: "SEO", color: "#a78bfa", path: "scores.seo" },
  ], { xKey: "fetchedAt", xLabel: "抓取时间", yLabel: "Lighthouse score", maxValue: 100 });
  renderPageSpeedPages(data.pages || []);
  renderRowsTable("#pagespeedRuns", (data.runs || []).slice(0, 30), ["url", "strategy", "fetchedAt", "ageDays", "scores.performance", "metrics.lcp", "metrics.tbt", "rawPath"]);
}

function renderPageSpeedPages(pages) {
  const container = $("#pagespeedPages");
  if (!pages.length) {
    container.innerHTML = "<p>暂无页面。</p>";
    return;
  }
  container.innerHTML = pages
    .map(
      (item) => `
      <button class="rank-row page-option" data-url="${escapeHtml(item.url)}">
        <span>${escapeHtml(shortUrl(item.url))}</span>
        <strong>${item.tested ? (item.isStale ? "需刷新" : "已监控") : "未抓取"}</strong>
      </button>`
    )
    .join("");
  $$(".page-option").forEach((button) => {
    button.addEventListener("click", () => {
      $("#psiUrlInput").value = button.dataset.url;
      $("#psiUrlSelect").value = button.dataset.url;
      renderPageSpeed();
    });
  });
}

function selectedPageSpeedRun() {
  const data = state.pagespeed;
  if (!data?.runs?.length) return null;
  const selectedUrl = $("#psiUrlInput")?.value || $("#psiUrlSelect")?.value || "";
  const selectedStrategy = $("#psiStrategy")?.value || "";
  return (
    data.runs.find((run) => (!selectedUrl || run.url === selectedUrl) && (!selectedStrategy || run.strategy === selectedStrategy)) ||
    data.runs[0]
  );
}

function renderCrux() {
  const data = state.crux;
  if (!data) return;
  renderStatus("#cruxStatus", data.status, data.message || "", data.sourceFile || "");
  const metrics = data.summary?.metrics || {};
  $("#cruxMetrics").innerHTML = Object.keys(metrics).length
    ? Object.entries(metrics).map(([key, value]) => `<div><strong>${escapeHtml(key)}</strong><span>p75: ${escapeHtml(value.p75 ?? "-")}</span></div>`).join("")
    : "<div><strong>暂无 CrUX 指标</strong><span>这通常表示真实用户样本不足。</span></div>";
}

function renderStorage() {
  const data = state.storage;
  if (!data) return;
  const sqlite = data.sqlite || {};
  const cloud = data.cloud || {};
  const quota = data.quota || {};
  const capacity = data.capacity || {};
  const logs = data.logs || {};
  const quotaSources = quota.sources || [];
  const configuredLimits = quotaSources.filter((row) => row.dailyLimit);
  const quotaAlerts = quotaSources.filter((row) => ["warning", "critical"].includes(row.limitStatus));
  const localBytes = Number(capacity.sqlite?.bytes || 0) + Number(capacity.rawCache?.bytes || 0) + Number(capacity.backups?.bytes || 0);

  $("#storageSqliteState").textContent = sqlite.exists ? "OK" : "Missing";
  $("#storageSqliteMeta").textContent = `${formatBytes(localBytes)} · SQLite / Raw / Backup`;
  $("#storageCloudState").textContent = cloud.ok ? "Healthy" : cloud.configured ? "Needs check" : "Not set";
  $("#storageCloudMeta").textContent = cloud.message || "Supabase cloud replica";
  $("#storageQuotaState").textContent = quotaAlerts.length ? `${quotaAlerts.length} Alert` : configuredLimits.length ? "Normal" : "待配置";
  $("#storageQuotaMeta").textContent = configuredLimits.length
    ? `${configuredLimits.length}/${quotaSources.length} sources configured`
    : "显示本地估算，官方上限待配置";
  $("#storageLogState").textContent = logs.status === "healthy" ? "Healthy" : "Attention";
  $("#storageLogMeta").textContent = `${logs.errorCount || 0} errors · ${logs.warningCount || 0} warnings`;

  renderKeyValueList("#storageArchitecture", [
    ["Mode", data.architecture?.mode || "-"],
    ["Source of truth", data.architecture?.sourceOfTruth || "-"],
    ["Cloud role", data.architecture?.cloudRole || "-"],
    ["Backup policy", data.architecture?.backupPolicy || "-"],
  ]);

  renderRawDirectoryList(data.rawDirectories || {});
  renderCloudStatus(cloud);
  renderCapacity(capacity);
  renderQuotaTable(quotaSources);
  renderQuotaMonitoring(quota.officialMonitoring || {});
  renderLogMonitoring(logs);
  renderRowsTable(
    "#storageRuns",
    (data.recentRuns || []).map((row) => ({
      source: row.source,
      status: row.status,
      cloudUpload: cloudUploadLabel(row.summary?.cloudSync),
      created_at: row.created_at,
      raw_path: row.raw_path,
      error: row.error,
    })),
    ["source", "status", "cloudUpload", "created_at", "raw_path", "error"]
  );
  renderTableCounts(cloud.tableCounts || {});
}

function renderCapacity(capacity) {
  const disk = capacity.localDisk || {};
  const cloud = capacity.cloudDatabase || {};
  const rows = [
    {
      label: "本地磁盘",
      value: disk.usedBytes,
      limit: disk.totalBytes,
      detail: `${formatBytes(disk.freeBytes || 0)} free`,
      utilization: disk.utilization,
    },
    {
      label: "SQLite",
      value: capacity.sqlite?.bytes || 0,
      limit: null,
      detail: "Local operations database",
      utilization: null,
    },
    {
      label: "Raw cache",
      value: capacity.rawCache?.bytes || 0,
      limit: null,
      detail: "GSC / GA4 / PageSpeed / CrUX",
      utilization: null,
    },
    {
      label: "Backups",
      value: capacity.backups?.bytes || 0,
      limit: null,
      detail: `${capacity.backups?.files || 0} files`,
      utilization: null,
    },
    {
      label: "Supabase",
      value: cloud.bytes,
      limit: cloud.limitBytes,
      detail: cloud.limitBytes ? "Configured plan limit" : `待配置 ${cloud.limitConfigKey || "database limit"}`,
      utilization: cloud.utilization,
    },
  ];
  $("#storageCapacity").innerHTML = rows
    .map((row) => {
      const percent = row.utilization == null ? null : Math.min(Math.max(Number(row.utilization), 0), 1);
      const stateClass = percent == null ? "unknown" : percent >= 0.9 ? "critical" : percent >= 0.75 ? "warning" : "normal";
      const value = row.value == null ? "Unknown" : formatBytes(row.value);
      const limit = row.limit ? ` / ${formatBytes(row.limit)}` : "";
      return `
        <div class="capacity-row">
          <div class="capacity-heading">
            <strong>${escapeHtml(row.label)}</strong>
            <span>${escapeHtml(value + limit)}</span>
          </div>
          <div class="capacity-track ${stateClass}" aria-label="${escapeHtml(row.label)} capacity">
            <span style="width: ${percent == null ? 0 : percent * 100}%"></span>
          </div>
          <small>${escapeHtml(row.detail)}${percent == null ? "" : ` · ${pct.format(percent)} used`}</small>
        </div>`;
    })
    .join("");
}

function renderRawDirectoryList(rawDirectories) {
  const rows = Object.entries(rawDirectories).map(([source, item]) => [
    source.toUpperCase(),
    `${fmt.format(item.files || 0)} files · ${formatBytes(item.bytes || 0)} · latest ${item.latestFile || "-"}`,
  ]);
  renderKeyValueList("#storageRawDirs", rows);
}

function renderCloudStatus(cloud) {
  const backup = cloud.latestBackup || {};
  renderKeyValueList("#storageCloud", [
    ["Configured", cloud.configured ? "Yes" : "No"],
    ["Connection", cloud.ok ? "Healthy" : cloud.message || "Unavailable"],
    ["Postgres", cloud.health?.version || "-"],
    ["Latest backup", backup.backupId ? `${backup.backupId} · ${backup.files || 0} files` : "-"],
    ["Backup path", backup.backupPath || "-"],
  ]);
}

function renderQuotaTable(rows) {
  renderRowsTable(
    "#storageQuota",
    rows.map((row) => ({
      source: row.source,
      freshness: row.freshness,
      ageDays: row.ageDays ?? "-",
      todayRuns: row.todayRuns,
      estCallsToday: row.estimatedCallsToday,
      dailyLimit: row.dailyLimit ?? "待配置",
      utilization: row.utilization == null ? "Unknown" : row.utilization,
      limitStatus: row.limitStatus,
      latestSuccessAt: row.latestSuccessAt || "-",
      recommendation: row.recommendation,
    })),
    ["source", "freshness", "ageDays", "todayRuns", "estCallsToday", "dailyLimit", "utilization", "limitStatus", "latestSuccessAt", "recommendation"]
  );
}

function renderQuotaMonitoring(monitoring) {
  const configured = monitoring.projectConfigured && monitoring.enabled;
  $("#quotaMonitoringNotice").innerHTML = `
    <strong class="integration-state ${configured ? "ready" : "pending"}">${configured ? "配置已预留" : "等待配置"}</strong>
    <p>当前页面使用 SQLite 调用记录估算额度。官方使用量需要后续接入 Google Cloud Monitoring API。</p>
    <div class="config-code">${escapeHtml((monitoring.requiredConfig || []).join(" · ") || "GOOGLE_CLOUD_PROJECT_ID")}</div>
  `;
}

function renderLogMonitoring(logs) {
  const tag = $("#logHealthTag");
  tag.textContent = logs.status === "healthy" ? "Healthy" : "Needs attention";
  tag.className = `tag ${logs.status === "healthy" ? "good" : "bad"}`;
  const fileEntries = (logs.files || []).flatMap((file) =>
    (file.entries || []).map((entry) => ({
      level: entry.level,
      source: file.name,
      createdAt: file.modified || "-",
      message: entry.message,
    }))
  );
  const rows = [...(logs.apiIssues || []), ...fileEntries].slice(0, 50);
  renderRowsTable("#operationsLogTable", rows, ["level", "source", "createdAt", "message"]);
  renderKeyValueList(
    "#logFileSummary",
    (logs.files || []).map((file) => [
      file.name,
      file.exists
        ? `${formatBytes(file.bytes || 0)} · ${file.lineCount || 0} lines · ${file.errorCount || 0} errors`
        : "Not created",
    ])
  );
}

function renderTableCounts(counts) {
  const rows = Object.entries(counts).map(([table, count]) => ({ table, rows: count }));
  renderRowsTable("#storageTableCounts", rows, ["table", "rows"]);
}

function cloudUploadLabel(cloudSync) {
  if (!cloudSync) return "Not recorded";
  if (cloudSync.ok) return cloudSync.backupId ? `Uploaded · ${cloudSync.backupId}` : "Uploaded";
  if (cloudSync.skipped) return "Skipped";
  return "Failed";
}

function renderKeyValueList(selector, rows) {
  const container = $(selector);
  if (!rows.length) {
    container.innerHTML = "<p>暂无数据。</p>";
    return;
  }
  container.innerHTML = rows
    .map(([label, value]) => `<div><strong>${escapeHtml(label)}</strong><span>${escapeHtml(value)}</span></div>`)
    .join("");
}

async function syncGsc() {
  setSyncMessage("正在同步 GSC...");
  try {
    const result = await api("/api/gsc/sync", { method: "POST", body: "{}" });
    setSyncMessage(result.ok ? "GSC 同步完成。" : "GSC 同步失败，请查看本地服务窗口。");
    await Promise.all([loadGscExplorer(), loadStorage()]);
  } catch (error) {
    setSyncMessage(`GSC 同步失败：${error.message}`);
  }
}

async function syncGa4() {
  await syncApi("/api/ga4/sync", "正在同步 GA4...", async () => {
    await Promise.all([loadGa4Analytics(), loadStorage()]);
  });
}

async function syncPageSpeed() {
  const url = $("#psiUrlInput").value || $("#psiUrlSelect").value || "";
  const strategy = $("#psiStrategy").value || "mobile";
  await syncApi("/api/pagespeed/sync", "正在抓取 PageSpeed...", async () => {
    await Promise.all([loadPageSpeed(), loadStorage()]);
  }, { url, strategy });
}

async function syncCrux() {
  await syncApi("/api/crux/sync", "正在同步 CrUX...", async () => {
    await Promise.all([loadCrux(), loadStorage()]);
  });
}

async function syncApi(endpoint, message, after, payload = {}) {
  setSyncMessage(message);
  try {
    const result = await api(endpoint, { method: "POST", body: JSON.stringify(payload) });
    setSyncMessage(result.ok ? "同步完成。" : "同步返回异常，请查看对应面板。");
    await after();
  } catch (error) {
    setSyncMessage(`同步失败：${error.message}`);
  }
}

function setSyncMessage(message) {
  $("#syncMessage").textContent = message;
}

async function createAiTask() {
  const payload = {
    taskType: $("#aiTaskType").value,
    context: $("#aiContext").value,
  };
  const task = await api("/api/ai/task", { method: "POST", body: JSON.stringify(payload) });
  state.latestTaskPath = task.path;
  $("#aiPromptOutput").textContent = `${task.path}\n\n${task.content}`;
}

function renderStatus(selector, status, message, sourceFile) {
  const label = status === "ok" ? "可用" : status === "no_data" ? "暂无数据" : "需处理";
  $(selector).innerHTML = `
    <strong class="state ${escapeHtml(status || "")}">${label}</strong>
    <span>${escapeHtml(message || "")}</span>
    ${sourceFile ? `<small>${escapeHtml(sourceFile)}</small>` : ""}
  `;
}

function renderMetricTable(selector, rows, labelName) {
  const mapped = rows.map((row) => ({
    [labelName]: row.label,
    clicks: row.clicks,
    impressions: row.impressions,
    ctr: row.ctr,
    position: row.position,
    reason: row.reason,
  }));
  renderRowsTable(selector, mapped, [labelName, "clicks", "impressions", "ctr", "position", "reason"]);
}

function renderRowsTable(selector, rows, columns) {
  const previous = tableStates.get(selector) || {};
  tableStates.set(selector, {
    rows: [...(rows || [])],
    columns: [...columns],
    query: previous.query || "",
    sortColumn: columns.includes(previous.sortColumn) ? previous.sortColumn : "",
    sortDirection: previous.sortDirection || "desc",
    columnFilter: columns.includes(previous.columnFilter?.column) ? previous.columnFilter : null,
  });
  renderTableState(selector);
}

function renderTableState(selector) {
  const container = $(selector);
  const tableState = tableStates.get(selector);
  if (!container || !tableState) return;
  const query = tableState.query.trim().toLowerCase();
  let rows = tableState.rows.filter((row) => {
    const queryMatch =
      !query ||
      tableState.columns.some((column) => String(getPath(row, column) ?? "").toLowerCase().includes(query));
    const columnMatch =
      !tableState.columnFilter ||
      String(getPath(row, tableState.columnFilter.column) ?? "") === tableState.columnFilter.value;
    return queryMatch && columnMatch;
  });
  if (tableState.sortColumn) {
    const direction = tableState.sortDirection === "asc" ? 1 : -1;
    rows = [...rows].sort(
      (left, right) =>
        compareTableValues(getPath(left, tableState.sortColumn), getPath(right, tableState.sortColumn)) * direction
    );
  }
  const filterLabel = tableState.columnFilter
    ? `${tableColumnLabel(tableState.columnFilter.column)} = ${shortText(tableState.columnFilter.value, 36)}`
    : "";
  if (!tableState.rows.length) {
    container.innerHTML = '<div class="empty-state"><strong>暂无数据</strong><span>当前数据源没有可显示的记录。</span></div>';
    return;
  }
  container.innerHTML = `
    <div class="table-toolbar">
      <div class="table-summary">
        <strong>${fmt.format(rows.length)} / ${fmt.format(tableState.rows.length)} rows</strong>
        <span>${filterLabel ? `已筛选：${escapeHtml(filterLabel)}` : "点击单元格可按该值筛选"}</span>
      </div>
      <div class="table-tools">
        ${tableState.columnFilter ? '<button class="table-clear-filter" type="button">清除点击筛选</button>' : ""}
        <input class="table-search" type="search" value="${escapeHtml(tableState.query)}" placeholder="搜索当前表格" aria-label="搜索当前表格" />
      </div>
    </div>
    <div class="table-scroll">
      <table>
        <thead>
          <tr>${tableState.columns
            .map((column) => {
              const active = tableState.sortColumn === column;
              const arrow = active ? (tableState.sortDirection === "asc" ? "↑" : "↓") : "↕";
              return `<th><button class="table-sort" type="button" data-column="${escapeHtml(column)}">${escapeHtml(
                tableColumnLabel(column)
              )}<span aria-hidden="true">${arrow}</span></button></th>`;
            })
            .join("")}</tr>
        </thead>
        <tbody>
          ${rows
            .slice(0, 250)
            .map(
              (row) =>
                `<tr>${tableState.columns
                  .map((column) => {
                    const value = getPath(row, column);
                    const fullValue = formatFullCell(value, column);
                    const displayValue = formatCell(value, column);
                    return `<td><button class="table-cell" type="button" data-column="${escapeHtml(
                      column
                    )}" data-value="${escapeHtml(String(value ?? ""))}" data-tooltip="${escapeHtml(
                      fullValue
                    )}" aria-label="${escapeHtml(`${tableColumnLabel(column)}: ${fullValue}`)}">${escapeHtml(
                      displayValue
                    )}</button></td>`;
                  })
                  .join("")}</tr>`
            )
            .join("")}
        </tbody>
      </table>
    </div>
    ${rows.length > 250 ? `<div class="table-limit-note">仅显示前 250 行，请继续筛选以缩小范围。</div>` : ""}`;
  bindTableInteractions(selector);
}

function bindTableInteractions(selector) {
  const container = $(selector);
  const tableState = tableStates.get(selector);
  const search = container.querySelector(".table-search");
  search?.addEventListener("input", (event) => {
    const cursor = event.target.selectionStart;
    tableState.query = event.target.value;
    window.clearTimeout(tableState.searchTimer);
    tableState.searchTimer = window.setTimeout(() => {
      renderTableState(selector);
      const next = $(selector).querySelector(".table-search");
      next?.focus();
      next?.setSelectionRange(cursor, cursor);
    }, 140);
  });
  container.querySelector(".table-clear-filter")?.addEventListener("click", () => {
    tableState.columnFilter = null;
    renderTableState(selector);
  });
  container.querySelectorAll(".table-sort").forEach((button) => {
    button.addEventListener("click", () => {
      const column = button.dataset.column;
      if (tableState.sortColumn === column) {
        tableState.sortDirection = tableState.sortDirection === "asc" ? "desc" : "asc";
      } else {
        tableState.sortColumn = column;
        tableState.sortDirection = "desc";
      }
      renderTableState(selector);
    });
  });
  container.querySelectorAll(".table-cell").forEach((button) => {
    button.addEventListener("click", () => {
      const nextFilter = { column: button.dataset.column, value: button.dataset.value };
      const same =
        tableState.columnFilter?.column === nextFilter.column &&
        tableState.columnFilter?.value === nextFilter.value;
      tableState.columnFilter = same ? null : nextFilter;
      renderTableState(selector);
    });
  });
}

function compareTableValues(left, right) {
  const leftNumber = Number(left);
  const rightNumber = Number(right);
  if (String(left ?? "").trim() && String(right ?? "").trim() && Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) {
    return leftNumber - rightNumber;
  }
  return String(left ?? "").localeCompare(String(right ?? ""), "zh-CN", { numeric: true, sensitivity: "base" });
}

function tableColumnLabel(column) {
  const labels = {
    date: "日期",
    query: "查询词",
    page: "页面",
    clicks: "点击",
    impressions: "曝光",
    ctr: "点击率",
    position: "平均排名",
    channel: "渠道",
    sessions: "会话",
    totalUsers: "用户",
    screenPageViews: "浏览",
    engagementRate: "参与率",
    viewsPerSession: "每次会话浏览",
    source: "来源",
    status: "状态",
    freshness: "新鲜度",
    ageDays: "数据年龄",
    todayRuns: "今日运行",
    estCallsToday: "今日估算调用",
    dailyLimit: "每日上限",
    utilization: "使用率",
    limitStatus: "额度状态",
    latestSuccessAt: "最近成功",
    recommendation: "建议",
    cloudUpload: "云上传",
    created_at: "时间",
    raw_path: "本地文件",
    error: "错误",
    level: "级别",
    createdAt: "时间",
    message: "消息",
    table: "云端表",
    rows: "记录数",
    url: "页面",
    strategy: "设备",
    fetchedAt: "抓取时间",
    "scores.performance": "性能分数",
    "metrics.lcp": "LCP",
    "metrics.tbt": "TBT",
    rawPath: "原始文件",
    Query: "查询词",
    Page: "页面",
    reason: "机会判断",
  };
  return labels[column] || column;
}

function renderRankList(selector, rows, labelKey, metricKey, metricLabel) {
  const container = $(selector);
  if (!rows?.length) {
    container.innerHTML = "<p>暂无数据。</p>";
    return;
  }
  container.innerHTML = rows
    .slice(0, 8)
    .map(
      (row) => `
      <div class="rank-row">
        <span>${escapeHtml(shortText(row[labelKey] || row.label || "", 58))}</span>
        <strong>${fmt.format(Number(row[metricKey] || 0))} ${metricLabel}</strong>
      </div>`
    )
    .join("");
}

function formatCell(value, col) {
  if (col === "ctr" || col === "engagementRate" || col === "utilization") {
    return value === "Unknown" ? "Unknown" : pct.format(Number(value || 0));
  }
  if (typeof value === "number") return fmt.format(value);
  return shortText(value ?? "", col.includes("raw") || col.includes("Path") || col === "message" ? 70 : 52);
}

function formatFullCell(value, col) {
  if (col === "ctr" || col === "engagementRate" || col === "utilization") {
    return value === "Unknown" ? "Unknown" : pct.format(Number(value || 0));
  }
  if (typeof value === "object" && value !== null) return JSON.stringify(value);
  return String(value ?? "-");
}

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (bytes >= 1024 * 1024) return `${fmt.format(bytes / 1024 / 1024)} MB`;
  if (bytes >= 1024) return `${fmt.format(bytes / 1024)} KB`;
  return `${fmt.format(bytes)} B`;
}

function setupCanvas(id) {
  const canvas = $(`#${id}`);
  const ctx = canvas.getContext("2d");
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(canvas.clientWidth || canvas.parentElement?.clientWidth || 760, 320);
  const height = Number(canvas.getAttribute("height")) || 300;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);
  return { canvas, ctx, width, height };
}

function drawLineChart(id, rows, series, options = {}) {
  const { canvas, ctx, width, height } = setupCanvas(id);
  if (!rows?.length) {
    chartModels.delete(id);
    return drawCenteredText(ctx, width, height, "暂无图表数据");
  }
  const values = series.flatMap((item) => rows.map((row) => Number(readSeriesValue(row, item)) || 0));
  const maxValue = Number(options.maxValue || niceAxisMax(Math.max(...values, 1)));
  const plot = drawChartAxes(ctx, width, height, maxValue, rows, options, (row) => getPath(row, options.xKey) ?? "");
  const hoverPoints = rows.map((row, index) => ({
    x: plot.left + (index / Math.max(rows.length - 1, 1)) * (plot.right - plot.left),
    label: formatAxisValue(getPath(row, options.xKey) ?? index + 1),
    values: [],
  }));

  series.forEach((item, seriesIndex) => {
    ctx.strokeStyle = item.color;
    ctx.lineWidth = 2.2;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.beginPath();
    rows.forEach((row, index) => {
      const value = Number(readSeriesValue(row, item)) || 0;
      const x = hoverPoints[index].x;
      const y = plot.bottom - (value / maxValue) * (plot.bottom - plot.top);
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
      hoverPoints[index].values.push({
        label: item.label,
        value: `${fmt.format(value)}${item.suffix || ""}`,
        color: item.color,
      });
    });
    ctx.stroke();
    ctx.fillStyle = item.color;
    ctx.fillRect(plot.left + seriesIndex * 142, 12, 18, 3);
    ctx.fillStyle = "#aebbb8";
    ctx.font = "12px Segoe UI";
    ctx.fillText(item.label, plot.left + 24 + seriesIndex * 142, 17);
  });
  chartModels.set(id, { type: "line", points: hoverPoints });
  bindChartHover(canvas);
}

function drawBarChart(id, rows, labelKey, valueKey, color, options = {}) {
  const { canvas, ctx, width, height } = setupCanvas(id);
  const data = (rows || []).slice(0, 8);
  if (!data.length) {
    chartModels.delete(id);
    return drawCenteredText(ctx, width, height, "暂无图表数据");
  }
  const maxValue = Number(options.maxValue || niceAxisMax(Math.max(...data.map((row) => Number(row[valueKey]) || 0), 1)));
  const plot = drawChartAxes(ctx, width, height, maxValue, data, { ...options, hideXTickLabels: true }, (row) => row[labelKey]);
  const gap = 12;
  const barWidth = Math.max((plot.right - plot.left - gap * (data.length - 1)) / data.length, 6);
  const hoverPoints = [];
  data.forEach((row, index) => {
    const value = Number(row[valueKey]) || 0;
    const barHeight = (value / maxValue) * (plot.bottom - plot.top);
    const x = plot.left + index * (barWidth + gap);
    const y = plot.bottom - barHeight;
    ctx.fillStyle = color;
    ctx.fillRect(x, y, barWidth, barHeight);
    ctx.fillStyle = "#879592";
    ctx.textAlign = "center";
    ctx.font = "11px Segoe UI";
    ctx.fillText(shortText(String(row[labelKey] || "-"), 12), x + barWidth / 2, plot.bottom + 20);
    ctx.textAlign = "left";
    if (barWidth >= 34) {
      ctx.fillStyle = "#dce5e2";
      ctx.textAlign = "center";
      ctx.font = "11px Segoe UI";
      ctx.fillText(fmt.format(value), x + barWidth / 2, Math.max(y - 7, plot.top + 10));
      ctx.textAlign = "left";
    }
    hoverPoints.push({
      x: x + barWidth / 2,
      label: String(row[labelKey] || "-"),
      values: [{ label: options.yLabel || valueKey, value: fmt.format(value), color }],
    });
  });
  chartModels.set(id, { type: "bar", points: hoverPoints });
  bindChartHover(canvas);
}

function drawChartAxes(ctx, width, height, maxValue, rows, options, labelGetter) {
  const plot = { left: 68, right: width - 24, top: 38, bottom: height - 68 };
  ctx.font = "11px Segoe UI";
  ctx.fillStyle = "#879592";
  ctx.strokeStyle = "rgba(138, 159, 154, 0.18)";
  ctx.lineWidth = 1;
  for (let index = 0; index <= 4; index += 1) {
    const y = plot.top + index * ((plot.bottom - plot.top) / 4);
    const value = maxValue * (1 - index / 4);
    ctx.beginPath();
    ctx.moveTo(plot.left, y);
    ctx.lineTo(plot.right, y);
    ctx.stroke();
    ctx.textAlign = "right";
    ctx.fillText(formatAxisNumber(value), plot.left - 10, y + 4);
  }
  ctx.textAlign = "center";
  if (!options.hideXTickLabels) {
    axisTickIndexes(rows.length).forEach((index) => {
      const x = plot.left + (index / Math.max(rows.length - 1, 1)) * (plot.right - plot.left);
      ctx.fillText(shortText(formatAxisValue(labelGetter(rows[index])), 16), x, plot.bottom + 20);
    });
  }
  ctx.fillStyle = "#aebbb8";
  ctx.font = "12px Segoe UI";
  ctx.fillText(options.xLabel || "", (plot.left + plot.right) / 2, height - 14);
  ctx.save();
  ctx.translate(16, (plot.top + plot.bottom) / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText(options.yLabel || "", 0, 0);
  ctx.restore();
  ctx.textAlign = "left";
  return plot;
}

function axisTickIndexes(length) {
  if (length <= 1) return [0];
  const count = Math.min(length, 5);
  return Array.from(new Set(Array.from({ length: count }, (_, index) => Math.round((index / (count - 1)) * (length - 1)))));
}

function niceAxisMax(value) {
  const power = 10 ** Math.floor(Math.log10(Math.max(value, 1)));
  const normalized = value / power;
  const nice = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return nice * power;
}

function formatAxisNumber(value) {
  if (Math.abs(value) >= 1000000) return `${fmt.format(value / 1000000)}M`;
  if (Math.abs(value) >= 1000) return `${fmt.format(value / 1000)}K`;
  return fmt.format(value);
}

function formatAxisValue(value) {
  const text = String(value ?? "-");
  if (/^\d{4}-\d{2}-\d{2}/.test(text)) return text.slice(5, 10);
  return text;
}

function bindChartHover(canvas) {
  if (canvas.dataset.hoverBound === "true") return;
  canvas.dataset.hoverBound = "true";
  canvas.addEventListener("pointermove", (event) => {
    const model = chartModels.get(canvas.id);
    if (!model?.points?.length) return;
    const rect = canvas.getBoundingClientRect();
    const localX = ((event.clientX - rect.left) / rect.width) * canvas.clientWidth;
    const point = model.points.reduce((best, item) =>
      Math.abs(item.x - localX) < Math.abs(best.x - localX) ? item : best
    );
    const content = `
      <strong>${escapeHtml(point.label)}</strong>
      ${point.values
        .map(
          (item) =>
            `<span><i style="background:${escapeHtml(item.color)}"></i>${escapeHtml(item.label)} <b>${escapeHtml(
              item.value
            )}</b></span>`
        )
        .join("")}`;
    showDataTooltip(content, event.clientX, event.clientY, true);
  });
  canvas.addEventListener("pointerleave", hideDataTooltip);
}

function drawCenteredText(ctx, width, height, text) {
  ctx.fillStyle = "#8ea0b8";
  ctx.textAlign = "center";
  ctx.font = "14px Segoe UI";
  ctx.fillText(text, width / 2, height / 2);
  ctx.textAlign = "left";
}

function readSeriesValue(row, item) {
  const value = item.path ? getPath(row, item.path) : row[item.key];
  return (Number(value) || 0) * (item.scale || 1);
}

function getPath(obj, path) {
  return String(path)
    .split(".")
    .reduce((acc, key) => (acc && acc[key] !== undefined ? acc[key] : undefined), obj);
}

function redrawCurrentView(view) {
  if (view === "overview") renderOverview();
  if (view === "gsc") renderGsc();
  if (view === "ga4") renderGa4();
  if (view === "pagespeed") renderPageSpeed();
  if (view === "storage") renderStorage();
}

function scoreLabel(key) {
  return { performance: "Performance", accessibility: "Accessibility", bestPractices: "Best Practices", seo: "SEO" }[key] || key;
}

function scoreClass(value) {
  const score = Number(value || 0);
  if (score >= 90) return "good";
  if (score >= 50) return "warn";
  return "bad";
}

function shortUrl(url) {
  return String(url || "").replace(/^https?:\/\/(www\.)?/, "");
}

function shortText(value, length = 80) {
  const text = String(value ?? "");
  return text.length > length ? `${text.slice(0, length - 1)}…` : text;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
