import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type Language = "zh-CN" | "en";
type Dictionary = Record<string, string>;

const en: Dictionary = {
  overview: "Overview", gsc: "GSC workbench", ga4: "GA4 behavior", pagespeed: "PageSpeed",
  crux: "CrUX field data", tasks: "AI tasks", operations: "Operations", settings: "Connections",
  independent: "Independent React/FastAPI", eyebrow: "LOCAL-FIRST SEO OPERATIONS",
  subtitle: "Cached raw exports and SQLite are authoritative. Source sync is always an explicit action.",
  reload: "Reload cached data", apiError: "API error", language: "简体中文",
  attention: "What requires attention", sourceHealth: "Source health", analyzeSearch: "Analyze cached search performance",
  comparisonOutside: "Comparison baseline is outside cached coverage.", reviewDrivers: "Review contribution and query/page drivers.",
  reviewFailures: "Review lab failures", failureSeparated: "Failed Lighthouse runs are separated from real scores.",
  checkOperations: "Check data operations", cloudDegraded: "Cloud is degraded; local continuity remains available.",
  reviewFreshness: "Review freshness, quota and sync history.", scopeComparison: "Scope and comparison",
  query: "Query", page: "Page", range: "Range", comparison: "Comparison", grain: "Grain",
  last7: "Last 7 days", last28: "Last 28 days", last90: "Last 90 days", previousPeriod: "Previous period",
  none: "None", day: "Day", week: "Week", month: "Month", applyScope: "Apply cached scope", syncSource: "Sync source",
  syncConfirm: "Sync GSC now? This makes baseline and dimension API requests. Search Appearance may require one extra request per returned appearance type.",
  comparisonStatus: "Comparison", unknown: "unknown", clicks: "Clicks", impressions: "Impressions", ctr: "CTR",
  avgPosition: "Avg position", trend: "Trend", scopedRows: "Scoped rows", exportMetadata: "Export CSV + metadata",
  drilldown: "Drill-down", filterByValue: "Filter by value", createTask: "Create scoped AI task", taskCreated: "Scoped AI task created.",
  dimensions: "Dimension availability", propertyGrain: "Property-level grain", available: "Available", unavailable: "Unavailable",
  requiresCollection: "Requires compatible collection", queryPlaceholder: "contains…", pagePlaceholder: "URL contains…",
  sessions: "Sessions", users: "Users", views: "Views", engagement: "Engagement", behaviorTrend: "Behavior trend",
  channelsRows: "Channels and rows", channel: "Channel", allChannels: "All channels", labMonitoring: "Lab monitoring",
  device: "Device", all: "All", mobile: "Mobile", desktop: "Desktop", priorityPages: "Priority page monitoring",
  loadingCache: "Loading cached state…", recentTasks: "Recent scope-aware AI tasks", refreshHistory: "Refresh history",
  sqlite: "SQLite", cloudReplica: "Cloud replica", healthy: "Healthy", optionalDegraded: "Optional/degraded",
  recentRuns: "Recent runs", backup: "Backup", quotaFreshness: "Quota and freshness", syncHistory: "Recent sync history",
  rawCache: "Raw cache", cloudTables: "Cloud tables", maskedSettings: "Masked connection settings",
  secretsMasked: "Secrets are masked. Sync actions remain explicit in each source view.", searchRows: "Search rows…",
  noData: "No data in this scope.", comparisonUnavailable: "Comparison unavailable", vsComparison: "vs comparison",
  noCache: "No cache", conversionsUnknown: "Conversions unknown", pageSpeedRuns: "PageSpeed runs", failed: "failed",
  loading: "Loading", noDimensionCache: "No compatible local dimension cache has been collected yet.",
  incompatibleFilter: "This property-level grain cannot be combined with Query or Page filters.",
  rangeUnsupported: "The selected range is outside this dimension cache coverage.", exactGrain: "Exact stored grain",
  savedAnalysis: "Saved views", viewName: "View name", viewDescription: "Notes", saveNew: "Save new view",
  updateView: "Update selected", loadView: "Load", deleteView: "Delete", favorite: "Favorite", noSavedViews: "No saved views yet.",
  deleteViewConfirm: "Delete this saved view?", completeState: "Dates, comparison, grain, filters, chart, table and drill-down state are stored together.",
  annotations: "Annotations", annotationDate: "Date", annotationTime: "Time", annotationTitle: "Title", annotationType: "Type",
  affectedPageGroup: "Affected page group", notes: "Notes", addAnnotation: "Add annotation", deleteAnnotationConfirm: "Delete this annotation?",
  release: "Release", contentUpdate: "Content update", migration: "Migration", campaign: "Campaign", tracking: "Tracking", googleUpdate: "Google update", note: "Note",
  custom: "Custom", startDate: "Start date", endDate: "End date", chartMetric: "Chart metric", tableSort: "Table sort", saved: "Saved", updated: "Updated",
  keywordDetail: "Keyword Detail", pageDetail: "Page Detail", rankingPages: "Ranking Pages", queryPortfolio: "Query Portfolio",
  opportunityGroups: "Opportunity groups", increased: "Increased", declined: "Declined", new: "New", lost: "Lost", nearFirstPage: "Near first page",
  dimensionSplits: "Dimension splits", dataFreshness: "Data freshness", detailLoading: "Loading detail…", relationshipGrain: "Relationships use the exact date + query + page cache grain.",
  limitations: "Limitations",
  partialDataReason: "The requested current range extends beyond cached coverage; only observed cached dates are shown.",
  comparisonPartialReason: "The comparison range is only partially covered by the local cache; comparison values are suppressed.",
  comparisonDisabled: "Comparison is disabled.", latestCompleteDate: "Latest complete date", selectedPeriod: "Selected period",
  currentUnavailable: "Current period unavailable", timezoneUnknown: "Property timezone unavailable in cached export",
  comparisonComplete: "Complete", comparisonPartial: "Partial coverage",
  chartMetrics: "Visible metrics", metricLimit: "Select 1–4 metrics. Different units stay visible in labeled lanes.",
  unitLanesHelp: "Counts, rates and ranking use separate labeled lanes; exact source values remain in Tooltip, table and export.",
  countUnit: "count", percentageUnit: "percentage", rankUnit: "rank (lower is better)", rowCount: "Rows",
  lastAttempt: "Last attempt", lastSuccess: "Last successful sync", sourceDelay: "Source delay",
  sync_in_progress: "Source sync in progress", sync_success: "Source sync succeeded", sync_partial: "Source sync partially succeeded",
  sync_skipped_fresh: "Source sync skipped by freshness policy", sync_error: "Source sync failed",
  localSaved: "Local persistence", apiRuns: "SQLite API runs", cloudResult: "Optional cloud replication",
  replicated: "replicated", skippedOptional: "skipped / unavailable", ga4SyncConfirm: "Sync the latest GA4 Organic Search source reports now? This calls the configured Google Analytics Data API and stores independent validated grains locally.",
  notCollected: "Configured, not collected", notConfigured: "Not configured", keyEventsConversions: "Key events / Conversions",
  ga4OrganicScope: "GA4 Organic Search scope and source sync", ga4Tables: "GA4 organic acquisition and landing-page tables",
  sourceMedium: "Source / medium", landingPage: "Landing page", country: "Country",
};

const zh: Dictionary = {
  overview: "概览", gsc: "GSC 工作台", ga4: "GA4 行为分析", pagespeed: "PageSpeed",
  crux: "CrUX 实际用户数据", tasks: "AI 任务", operations: "运行与存储", settings: "连接设置",
  independent: "React/FastAPI 独立运行", eyebrow: "本地优先 SEO 运营",
  subtitle: "缓存的原始导出与 SQLite 是权威数据源；源数据同步始终由用户明确触发。",
  reload: "重新载入缓存", apiError: "API 错误", language: "English",
  attention: "今日需要关注", sourceHealth: "数据源健康状态", analyzeSearch: "分析缓存的搜索表现",
  comparisonOutside: "比较基线超出当前缓存覆盖范围。", reviewDrivers: "检查贡献度以及 Query/Page 变化驱动。",
  reviewFailures: "检查实验室运行失败", failureSeparated: "Lighthouse 运行失败与真实评分已分开显示。",
  checkOperations: "检查数据运行状态", cloudDegraded: "云副本降级；本地数据仍可持续使用。",
  reviewFreshness: "检查新鲜度、配额和同步历史。", scopeComparison: "范围与比较",
  query: "Query", page: "Page", range: "日期范围", comparison: "比较", grain: "时间粒度",
  last7: "最近 7 天", last28: "最近 28 天", last90: "最近 90 天", previousPeriod: "上一周期",
  none: "无", day: "日", week: "周", month: "月", applyScope: "应用缓存范围", syncSource: "同步源数据",
  syncConfirm: "现在同步 GSC？这会调用基线与维度 API；Search Appearance 可能按返回的每种类型增加一次请求。",
  comparisonStatus: "比较状态", unknown: "未知", clicks: "Clicks", impressions: "Impressions", ctr: "CTR",
  avgPosition: "平均排名", trend: "趋势", scopedRows: "当前范围明细", exportMetadata: "导出 CSV + 元数据",
  drilldown: "下钻", filterByValue: "按此值筛选", createTask: "创建带范围的 AI 任务", taskCreated: "已创建带范围的 AI 任务。",
  dimensions: "维度可用性", propertyGrain: "属性级粒度", available: "可用", unavailable: "不可用",
  requiresCollection: "需要兼容的数据采集", queryPlaceholder: "包含…", pagePlaceholder: "URL 包含…",
  sessions: "Sessions", users: "Users", views: "Views", engagement: "参与度", behaviorTrend: "行为趋势",
  channelsRows: "渠道与明细", channel: "渠道", allChannels: "全部渠道", labMonitoring: "实验室监测",
  device: "设备", all: "全部", mobile: "移动设备", desktop: "桌面设备", priorityPages: "重点页面监测",
  loadingCache: "正在载入缓存状态…", recentTasks: "最近的范围感知 AI 任务", refreshHistory: "刷新历史",
  sqlite: "SQLite", cloudReplica: "云副本", healthy: "健康", optionalDegraded: "可选/降级",
  recentRuns: "近期运行", backup: "备份", quotaFreshness: "配额与数据新鲜度", syncHistory: "近期同步历史",
  rawCache: "原始缓存", cloudTables: "云端表", maskedSettings: "已脱敏的连接设置",
  secretsMasked: "密钥均已脱敏；各数据源的同步操作仍需明确触发。", searchRows: "搜索明细…",
  noData: "当前范围没有数据。", comparisonUnavailable: "比较不可用", vsComparison: "相对比较期",
  noCache: "无缓存", conversionsUnknown: "转化未配置", pageSpeedRuns: "PageSpeed 运行", failed: "失败",
  loading: "载入中", noDimensionCache: "尚未采集兼容的本地维度缓存。",
  incompatibleFilter: "此属性级粒度不能与 Query 或 Page 筛选组合。",
  rangeUnsupported: "所选日期超出该维度缓存的覆盖范围。", exactGrain: "真实存储粒度",
  savedAnalysis: "保存视图", viewName: "视图名称", viewDescription: "说明", saveNew: "新建保存视图",
  updateView: "更新已选视图", loadView: "载入", deleteView: "删除", favorite: "收藏", noSavedViews: "尚无保存视图。",
  deleteViewConfirm: "确定删除此保存视图？", completeState: "日期、比较、粒度、筛选、图表、表格与下钻状态会作为一个整体保存。",
  annotations: "注释", annotationDate: "日期", annotationTime: "时间", annotationTitle: "标题", annotationType: "类型",
  affectedPageGroup: "受影响页面组", notes: "备注", addAnnotation: "添加注释", deleteAnnotationConfirm: "确定删除此注释？",
  release: "发布", contentUpdate: "内容更新", migration: "迁移", campaign: "活动", tracking: "跟踪调整", googleUpdate: "Google 更新", note: "备注",
  custom: "自定义", startDate: "开始日期", endDate: "结束日期", chartMetric: "图表指标", tableSort: "表格排序", saved: "已保存", updated: "已更新",
  keywordDetail: "关键词详情", pageDetail: "页面详情", rankingPages: "排名页面", queryPortfolio: "Query Portfolio",
  opportunityGroups: "机会分组", increased: "上涨", declined: "下降", new: "新增", lost: "丢失", nearFirstPage: "接近第一页",
  dimensionSplits: "维度拆分", dataFreshness: "数据新鲜度", detailLoading: "正在载入详情…", relationshipGrain: "关系数据使用真实的 date + query + page 缓存粒度。",
  limitations: "数据限制",
  partialDataReason: "当前请求范围超出缓存覆盖；仅显示缓存中真实存在的日期。",
  comparisonPartialReason: "比较期仅部分被本地缓存覆盖；比较值已隐藏。",
  comparisonDisabled: "比较已关闭。", latestCompleteDate: "最新完整日期", selectedPeriod: "已选周期",
  currentUnavailable: "当前期不可用", timezoneUnknown: "缓存导出未提供属性时区",
  comparisonComplete: "完整", comparisonPartial: "部分覆盖",
  chartMetrics: "显示指标", metricLimit: "可选择 1–4 个指标；不同单位会保留在清楚标注的独立分区中。",
  unitLanesHelp: "数量、比例和排名使用独立标注分区；Tooltip、表格与导出保留源数据精确值。",
  countUnit: "数量", percentageUnit: "百分比", rankUnit: "排名（数值越小越好）", rowCount: "行数",
  lastAttempt: "上次尝试", lastSuccess: "上次成功同步", sourceDelay: "来源延迟说明",
  sync_in_progress: "正在同步来源数据", sync_success: "来源同步成功", sync_partial: "来源同步部分成功",
  sync_skipped_fresh: "因新鲜度策略跳过同步", sync_error: "来源同步失败",
  localSaved: "本地保存", apiRuns: "SQLite API 运行记录", cloudResult: "可选云端复制",
  replicated: "已复制", skippedOptional: "已跳过 / 不可用", ga4SyncConfirm: "现在同步最新 GA4 Organic Search 来源报告？这会调用已配置的 Google Analytics Data API，并按独立验证粒度保存到本地。",
  notCollected: "已配置但尚未采集", notConfigured: "未配置", keyEventsConversions: "Key events / Conversions",
  ga4OrganicScope: "GA4 自然搜索范围与来源同步", ga4Tables: "GA4 自然搜索获客与落地页表格",
  sourceMedium: "Source / medium", landingPage: "Landing page", country: "Country",
};

type I18nValue = { language: Language; setLanguage: (value: Language) => void; t: (key: string) => string };
const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguage] = useState<Language>(() => {
    try { return localStorage.getItem("seo-dashboard-language") === "en" ? "en" : "zh-CN"; }
    catch { return "zh-CN"; }
  });
  useEffect(() => {
    document.documentElement.lang = language;
    try { localStorage.setItem("seo-dashboard-language", language); } catch { /* local persistence is optional */ }
  }, [language]);
  const value = useMemo<I18nValue>(() => ({ language, setLanguage, t: key => (language === "zh-CN" ? zh : en)[key] || en[key] || key }), [language]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n must be used inside I18nProvider");
  return value;
}

export function localizeReason(reason: string, t: (key: string) => string): string {
  if (!reason) return "";
  if (reason.includes("Requires a compatible")) return t("noDimensionCache");
  if (reason.includes("outside this dimension cache")) return t("rangeUnsupported");
  if (reason.includes("cannot be combined")) return t("incompatibleFilter");
  return reason;
}
