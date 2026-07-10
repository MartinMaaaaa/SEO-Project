const state = {
  status: null,
  gsc: null,
  ga4: null,
  pagespeed: null,
  crux: null,
  storage: null,
  latestTaskPath: "",
};

const viewCopy = {
  overview: ["总览", "跨 GSC、GA4、PageSpeed 的核心 SEO 数据视图。"],
  gsc: ["GSC 查询分析", "按关键词、URL、日期和曝光阈值筛选自然搜索表现。"],
  ga4: ["GA4 行为分析", "用图表查看访问、用户、浏览、参与和渠道结构。"],
  pagespeed: ["PageSpeed 性能", "按页面保存性能抓取历史，标记抓取时间和过期状态。"],
  crux: ["CrUX 体验", "查看真实用户 Core Web Vitals 数据是否可用。"],
  ai: ["AI 分析任务", "生成英文任务提示词，交给 AI 基于最新数据继续分析。"],
  storage: ["本地存储", "查看 SQLite、Supabase、备份、API 配额和同步历史。"],
  settings: ["连接状态", "检查 API 配置状态并触发同步。"],
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));
const fmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const pct = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 });

document.addEventListener("DOMContentLoaded", () => {
  bindNavigation();
  bindActions();
  loadAll();
});

function bindNavigation() {
  $$(".nav-item").forEach((button) => {
    button.addEventListener("click", () => showView(button.dataset.view));
  });
}

function showView(view) {
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  $$(".view").forEach((section) => section.classList.toggle("active", section.id === view));
  const [title, subtitle] = viewCopy[view] || viewCopy.overview;
  $("#viewTitle").textContent = title;
  $("#viewSubtitle").textContent = subtitle;
  redrawCurrentView(view);
}

function bindActions() {
  $("#refreshData").addEventListener("click", loadAll);
  $("#syncGsc").addEventListener("click", syncGsc);
  $("#syncGscSettings").addEventListener("click", syncGsc);
  $("#syncGa4").addEventListener("click", syncGa4);
  $("#syncGa4Top").addEventListener("click", syncGa4);
  $("#syncGa4Settings").addEventListener("click", syncGa4);
  $("#syncPageSpeed").addEventListener("click", syncPageSpeed);
  $("#syncPageSpeedTop").addEventListener("click", syncPageSpeed);
  $("#syncPageSpeedSettings").addEventListener("click", syncPageSpeed);
  $("#syncCrux").addEventListener("click", syncCrux);
  $("#syncCruxSettings").addEventListener("click", syncCrux);
  $("#refreshStorage").addEventListener("click", loadStorage);
  $("#applyGscFilters").addEventListener("click", loadGscExplorer);
  $("#ga4ChannelFilter").addEventListener("change", loadGa4Analytics);
  $("#ga4ChartMode").addEventListener("change", renderGa4);
  $("#psiUrlSelect").addEventListener("change", () => {
    $("#psiUrlInput").value = $("#psiUrlSelect").value;
    renderPageSpeed();
  });
  $("#psiStrategy").addEventListener("change", renderPageSpeed);
  $("#createAiTask").addEventListener("click", createAiTask);
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
    query: $("#gscQueryFilter")?.value || "",
    page: $("#gscPageFilter")?.value || "",
    start: $("#gscStartDate")?.value || "",
    end: $("#gscEndDate")?.value || "",
    minImpressions: $("#gscMinImpressions")?.value || "0",
    sort: $("#gscSort")?.value || "clicks",
    limit: "50",
  });
  const data = await api(`/api/gsc/explorer?${params.toString()}`);
  state.gsc = data;
  if (!$("#gscStartDate").value && data.filters?.start) $("#gscStartDate").value = data.filters.start;
  if (!$("#gscEndDate").value && data.filters?.end) $("#gscEndDate").value = data.filters.end;
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
    ]);
  }
  if (ga4) {
    $("#kpiGa4Sessions").textContent = fmt.format(ga4.totals.sessions || 0);
    $("#kpiGa4Engagement").textContent = pct.format(ga4.totals.engagementRate || 0);
    drawBarChart("overviewChannelChart", ga4.channels || [], "channel", "sessions", "#22d3ee");
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
  drawLineChart("gscTrendChart", data.trend || [], [
    { key: "clicks", label: "Clicks", color: "#38bdf8" },
    { key: "impressions", label: "Impressions", color: "#a78bfa" },
    { key: "ctr", label: "CTR", color: "#34d399", scale: 100 },
  ]);
  renderMetricTable("#gscQueriesTable", data.queries || [], "Query");
  renderMetricTable("#gscPagesTable", data.pages || [], "Page");
  renderRowsTable("#gscRowsTable", data.rows || [], ["date", "query", "page", "clicks", "impressions", "ctr", "position"]);
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
    drawBarChart("ga4MainChart", data.channels || [], "channel", "sessions", "#38bdf8");
  } else if (mode === "engagement") {
    drawLineChart("ga4MainChart", data.trend || [], [{ key: "engagementRate", label: "Engagement rate", color: "#34d399", scale: 100 }], "%");
  } else {
    const keyMap = { sessions: "sessions", users: "totalUsers", views: "screenPageViews" };
    drawLineChart("ga4MainChart", data.trend || [], [{ key: keyMap[mode], label: titles[mode], color: "#22d3ee" }]);
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
  ]);
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
  const backup = cloud.latestBackup || {};
  const quota = data.quota || {};

  $("#storageSqliteState").textContent = sqlite.exists ? "OK" : "Missing";
  $("#storageSqliteMeta").textContent = `${sqlite.path || "-"} · ${formatBytes(sqlite.bytes || 0)}`;
  $("#storageCloudState").textContent = cloud.ok ? "Healthy" : cloud.configured ? "Needs check" : "Not set";
  $("#storageCloudMeta").textContent = cloud.message || "Supabase cloud replica";
  $("#storageApiRuns").textContent = fmt.format(quota.summary?.totalRuns || 0);
  $("#storageBackupState").textContent = backup.backupId ? "Ready" : "None";
  $("#storageBackupMeta").textContent = backup.backupId ? `${backup.backupId} · ${backup.files || 0} files` : "No local upload backup found";

  renderKeyValueList("#storageArchitecture", [
    ["Mode", data.architecture?.mode || "-"],
    ["Source of truth", data.architecture?.sourceOfTruth || "-"],
    ["Cloud role", data.architecture?.cloudRole || "-"],
    ["Backup policy", data.architecture?.backupPolicy || "-"],
  ]);

  renderRawDirectoryList(data.rawDirectories || {});
  renderCloudStatus(cloud);
  renderQuotaTable(quota.sources || []);
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
      latestSuccessAt: row.latestSuccessAt || "-",
      recommendation: row.recommendation,
    })),
    ["source", "freshness", "ageDays", "todayRuns", "estCallsToday", "latestSuccessAt", "recommendation"]
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
  const container = $(selector);
  if (!rows?.length) {
    container.innerHTML = "<p>暂无数据。</p>";
    return;
  }
  container.innerHTML = `
    <table>
      <thead><tr>${columns.map((col) => `<th>${escapeHtml(col)}</th>`).join("")}</tr></thead>
      <tbody>
        ${rows
          .map((row) => `<tr>${columns.map((col) => `<td>${formatCell(getPath(row, col), col)}</td>`).join("")}</tr>`)
          .join("")}
      </tbody>
    </table>`;
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
  if (col === "ctr" || col === "engagementRate") return pct.format(Number(value || 0));
  if (typeof value === "number") return escapeHtml(fmt.format(value));
  return escapeHtml(shortText(value ?? "", col.includes("raw") || col.includes("Path") ? 80 : 120));
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

function drawLineChart(id, rows, series, suffix = "") {
  const { ctx, width, height } = setupCanvas(id);
  drawGrid(ctx, width, height);
  if (!rows?.length) return drawCenteredText(ctx, width, height, "暂无图表数据");
  const left = 46;
  const right = width - 20;
  const top = 22;
  const bottom = height - 42;
  const allValues = [];
  series.forEach((item) => {
    rows.forEach((row) => allValues.push(Number(readSeriesValue(row, item)) || 0));
  });
  const max = Math.max(...allValues, 1);
  series.forEach((item, seriesIndex) => {
    ctx.strokeStyle = item.color;
    ctx.lineWidth = 2.4;
    ctx.beginPath();
    rows.forEach((row, index) => {
      const value = Number(readSeriesValue(row, item)) || 0;
      const x = left + (index / Math.max(rows.length - 1, 1)) * (right - left);
      const y = bottom - (value / max) * (bottom - top);
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.fillStyle = item.color;
    ctx.font = "12px Segoe UI";
    ctx.fillText(`${item.label}${suffix}`, left + seriesIndex * 150, height - 13);
  });
}

function drawBarChart(id, rows, labelKey, valueKey, color) {
  const { ctx, width, height } = setupCanvas(id);
  drawGrid(ctx, width, height);
  const data = (rows || []).slice(0, 8);
  if (!data.length) return drawCenteredText(ctx, width, height, "暂无图表数据");
  const left = 42;
  const top = 24;
  const bottom = height - 54;
  const gap = 10;
  const barWidth = (width - left - 24 - gap * (data.length - 1)) / data.length;
  const max = Math.max(...data.map((row) => Number(row[valueKey]) || 0), 1);
  data.forEach((row, index) => {
    const value = Number(row[valueKey]) || 0;
    const h = (value / max) * (bottom - top);
    const x = left + index * (barWidth + gap);
    const y = bottom - h;
    ctx.fillStyle = color;
    ctx.fillRect(x, y, Math.max(barWidth, 4), h);
    ctx.fillStyle = "#9fb6d4";
    ctx.font = "11px Segoe UI";
    ctx.fillText(shortText(row[labelKey] || "", 12), x, height - 18);
  });
}

function drawGrid(ctx, width, height) {
  ctx.strokeStyle = "rgba(125, 161, 213, 0.18)";
  ctx.lineWidth = 1;
  for (let i = 0; i < 5; i += 1) {
    const y = 22 + i * ((height - 66) / 4);
    ctx.beginPath();
    ctx.moveTo(42, y);
    ctx.lineTo(width - 18, y);
    ctx.stroke();
  }
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
