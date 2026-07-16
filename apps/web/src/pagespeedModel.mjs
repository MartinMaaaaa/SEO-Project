export const CATEGORY_IDS = ["performance", "accessibility", "best-practices", "seo"];

export function normalizeClientUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) throw new Error("required");
  let parsed;
  try { parsed = new URL(raw); } catch { throw new Error("invalid"); }
  if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error("scheme");
  if (parsed.username || parsed.password) throw new Error("credentials");
  const host = parsed.hostname.toLowerCase();
  if (!host || host === 'localhost' || host.endsWith('.local') || host.endsWith('.internal') || /^(127\.|10\.|192\.168\.|169\.254\.)/.test(host)) throw new Error("public");
  parsed.hash = '';
  parsed.protocol = parsed.protocol.toLowerCase();
  parsed.hostname = host;
  if ((parsed.protocol === 'https:' && parsed.port === '443') || (parsed.protocol === 'http:' && parsed.port === '80')) parsed.port = '';
  if (!parsed.pathname) parsed.pathname = '/';
  return parsed.toString();
}

export function auditState(audit) {
  const mode = String(audit?.scoreDisplayMode || '').toLowerCase();
  if (mode === 'manual') return 'manual';
  if (mode === 'notapplicable') return 'notApplicable';
  if (mode === 'informative' || mode === 'debug') return 'informative';
  if (audit?.score === 1) return 'passed';
  if (audit?.score === null || audit?.score === undefined) return 'unscored';
  return 'needsAttention';
}

export function flattenAudits(result) {
  const refsByAudit = new Map();
  for (const [category, refs] of Object.entries(result?.categoryAuditRefs || {})) {
    for (const ref of Array.isArray(refs) ? refs : []) {
      const current = refsByAudit.get(ref.id) || { categories: [], groups: [], weight: 0 };
      if (!current.categories.includes(category)) current.categories.push(category);
      if (ref.group && !current.groups.includes(ref.group)) current.groups.push(ref.group);
      if (typeof ref.weight === 'number') current.weight += ref.weight;
      refsByAudit.set(ref.id, current);
    }
  }
  return Object.entries(result?.audits || {}).map(([id, audit]) => {
    const refs = refsByAudit.get(id) || { categories: [], groups: [], weight: 0 };
    const details = audit?.details && typeof audit.details === 'object' ? audit.details : null;
    const savingsMs = typeof details?.overallSavingsMs === 'number' ? details.overallSavingsMs : typeof audit?.metricSavings?.LCP === 'number' ? audit.metricSavings.LCP : null;
    const savingsBytes = typeof details?.overallSavingsBytes === 'number' ? details.overallSavingsBytes : null;
    return {
      ...audit,
      id,
      categories: refs.categories,
      groups: refs.groups,
      weight: refs.weight,
      state: auditState(audit),
      detailType: details?.type || 'none',
      savingsMs,
      savingsBytes,
      searchText: `${id} ${audit?.title || ''} ${audit?.description || ''} ${audit?.displayValue || ''}`.toLowerCase(),
    };
  });
}

export function latestByStrategy(results) {
  const map = { mobile: null, desktop: null };
  for (const result of Array.isArray(results) ? results : []) {
    if (result?.status === 'success' && (result?.strategy === 'mobile' || result?.strategy === 'desktop') && !map[result.strategy]) map[result.strategy] = result;
  }
  return map;
}

export function deviceOutcome(results) {
  const values = Object.values(results || {});
  const successes = values.filter(item => item?.ok).length;
  if (!values.length) return 'idle';
  if (successes === values.length) return 'success';
  if (successes) return 'partial';
  return 'error';
}
