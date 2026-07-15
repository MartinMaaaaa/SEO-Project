import { useEffect, useId, useMemo, useState } from "react";

type Row = Record<string, any>;
type Unit = "count" | "ratio" | "rank";

export type ChartSeries = {
  key: string;
  label: string;
  color: string;
  unit: Unit;
  invert?: boolean;
};

export type ChartMetadata = {
  range?: { start?: string; end?: string };
  comparisonRange?: { start?: string; end?: string } | null;
  timezone?: string;
  grain?: string;
  freshness?: string;
  partial?: boolean;
  partialReason?: string;
  stale?: boolean;
  staleReason?: string;
};

export type ChartComparison = {
  status: "complete" | "partial" | "unavailable" | "none";
  reason?: string | null;
};

type Props = {
  rows: Row[];
  comparisonRows?: Row[];
  comparison?: ChartComparison;
  series: ChartSeries[];
  visibleSeries: string[];
  onVisibleSeriesChange?: (keys: string[]) => void;
  selectedKey?: string | null;
  onSelectedKeyChange?: (key: string | null) => void;
  annotations?: Row[];
  locale?: string;
  title?: string;
  metadata?: ChartMetadata;
  state?: "ready" | "loading" | "empty" | "error";
  errorMessage?: string;
  displayMode?: "unit_lanes";
  maxVisibleSeries?: number;
};

const WIDTH = 920;
const PAD = { left: 70, right: 18, top: 22, bottom: 58 };
const LANE_GAP = 34;

const chartCopy = {
  en: {
    series: "Chart series", current: "Current period", comparison: "Comparison period", range: "Range",
    timezone: "Timezone", grain: "Grain", freshness: "Freshness", unit: "Units / lanes", count: "Count",
    ratio: "Percentage", rank: "Average position", loading: "Loading chart data…", empty: "No data in this scope.",
    error: "Chart data could not be loaded.", partial: "Partial data", stale: "Stale cached data",
    comparisonPartial: "Comparison is only partially covered and is not plotted.",
    comparisonUnavailable: "Comparison is unavailable and is not plotted.", noData: "no data",
    minimum: "minimum", maximum: "maximum", to: "to", selected: "Selected",
    reversed: "Ranking axis is reversed so lower position numbers appear higher.", unavailable: "Unavailable",
  },
  zh: {
    series: "图表序列", current: "当前期", comparison: "比较期", range: "日期范围", timezone: "时区",
    grain: "时间粒度", freshness: "数据时间", unit: "单位 / 分区", count: "数量", ratio: "百分比",
    rank: "平均排名", loading: "正在载入图表数据…", empty: "当前范围没有数据。", error: "图表数据载入失败。",
    partial: "部分数据", stale: "缓存数据已过期", comparisonPartial: "比较期仅部分被缓存覆盖，因此未绘制。",
    comparisonUnavailable: "比较期不可用，因此未绘制。", noData: "无数据", minimum: "最小值",
    maximum: "最大值", to: "至", selected: "已选择", reversed: "排名轴已反转，数值较小的排名显示在更高位置。",
    unavailable: "不可用",
  },
};

function keyOf(row: Row): string {
  return String(row.alignmentKey ?? row.date ?? row.label ?? "");
}

function labelOf(row?: Row): string {
  return row ? String(row.label ?? row.date ?? "") : "";
}

function numericValue(row: Row | undefined, key: string): number | null {
  if (!row || row[key] === null || row[key] === undefined || row[key] === "") return null;
  const value = Number(row[key]);
  return Number.isFinite(value) ? value : null;
}

function rangeLabel(range?: { start?: string; end?: string } | null): string {
  if (!range?.start && !range?.end) return "—";
  return range.start === range.end ? String(range.start || range.end) : `${range.start || "—"} – ${range.end || "—"}`;
}

function alignmentOrder(key: string): number {
  const value = Number(key.slice(key.lastIndexOf(":") + 1));
  return Number.isFinite(value) ? value : Number.MAX_SAFE_INTEGER;
}

export function AnalysisChart({
  rows,
  comparisonRows = [],
  comparison = { status: "none" },
  series,
  visibleSeries,
  onVisibleSeriesChange,
  selectedKey,
  onSelectedKeyChange,
  annotations = [],
  locale = "en",
  title = "Trend",
  metadata = {},
  state = "ready",
  errorMessage,
  maxVisibleSeries = 4,
}: Props) {
  const id = useId();
  const text = locale === "zh-CN" ? chartCopy.zh : chartCopy.en;
  const [transientKey, setTransientKey] = useState<string | null>(null);
  const [localSelectedKey, setLocalSelectedKey] = useState<string | null>(null);
  const effectiveSelectedKey = selectedKey === undefined ? localSelectedKey : selectedKey;
  const requested = series.filter(item => visibleSeries.includes(item.key)).slice(0, maxVisibleSeries);
  const active = requested.length ? requested : series.slice(0, 1);
  const units = Array.from(new Set(active.map(item => item.unit)));
  const laneHeight = units.length === 1 ? 230 : 170;
  const height = PAD.top + units.length * laneHeight + Math.max(0, units.length - 1) * LANE_GAP + PAD.bottom;
  const plotWidth = WIDTH - PAD.left - PAD.right;
  const laneFor = (unit: Unit) => {
    const index = Math.max(units.indexOf(unit), 0);
    const top = PAD.top + index * (laneHeight + LANE_GAP);
    return { index, top, bottom: top + laneHeight, height: laneHeight };
  };
  const scaleFor = (unit: Unit) => {
    const definitions = active.filter(item => item.unit === unit);
    const values = [...rows, ...comparisonRows]
      .flatMap(row => definitions.map(def => numericValue(row, def.key)))
      .filter((value): value is number => value !== null);
    const minimum = unit === "count" || unit === "ratio" ? 0 : Math.min(...values, 1);
    const maximum = Math.max(...values, unit === "ratio" ? 0.01 : 1);
    return { minimum, maximum, span: Math.max(maximum - minimum, unit === "ratio" ? 0.01 : 1) };
  };
  const scales = Object.fromEntries(units.map(unit => [unit, scaleFor(unit)])) as Record<Unit, { minimum: number; maximum: number; span: number }>;
  const currentByKey = useMemo(() => new Map(rows.map(row => [keyOf(row), row])), [rows]);
  const comparisonByKey = useMemo(() => new Map(comparisonRows.map(row => [keyOf(row), row])), [comparisonRows]);
  const slots = useMemo(() => Array.from(new Set([...currentByKey.keys(), ...comparisonByKey.keys()])).sort((a, b) => {
    const offset = alignmentOrder(a) - alignmentOrder(b);
    return offset || a.localeCompare(b);
  }), [currentByKey, comparisonByKey]);
  const x = (index: number) => PAD.left + (slots.length <= 1 ? plotWidth / 2 : index * plotWidth / (slots.length - 1));
  const y = (definition: ChartSeries, value: number) => {
    const lane = laneFor(definition.unit);
    const scale = scales[definition.unit];
    const normalized = (value - scale.minimum) / scale.span;
    return lane.top + (definition.invert ? normalized : 1 - normalized) * lane.height;
  };
  const format = (value: number, unit: Unit) => unit === "ratio"
    ? new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 2 }).format(value)
    : new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(value);
  const annotationDates = new Set(annotations.map(item => item.date));
  const activeKey = transientKey ?? effectiveSelectedKey;
  const activeIndex = activeKey ? slots.indexOf(activeKey) : -1;
  const activeCurrent = activeKey ? currentByKey.get(activeKey) : undefined;
  const activeComparison = activeKey ? comparisonByKey.get(activeKey) : undefined;
  const actualState = state === "ready" && !rows.length ? "empty" : state;

  const summary = useMemo(() => active.map(def => {
    const describe = (periodRows: Row[], period: string) => {
      const data = periodRows.map(row => numericValue(row, def.key)).filter((value): value is number => value !== null);
      if (!data.length) return `${period} ${text.noData}`;
      return `${period} ${format(data[0], def.unit)} ${text.to} ${format(data[data.length - 1], def.unit)}, ${text.minimum} ${format(Math.min(...data), def.unit)}, ${text.maximum} ${format(Math.max(...data), def.unit)}`;
    };
    const parts = [describe(rows, text.current)];
    if (comparison.status === "complete") parts.push(describe(comparisonRows, text.comparison));
    return `${def.label} (${text[def.unit]}): ${parts.join(". ")}`;
  }).join(". "), [rows, comparisonRows, visibleSeries, locale, comparison.status]);

  useEffect(() => { setTransientKey(null); }, [rows, comparisonRows, visibleSeries]);
  useEffect(() => {
    if (effectiveSelectedKey && !slots.includes(effectiveSelectedKey)) {
      if (selectedKey === undefined) setLocalSelectedKey(null);
      else onSelectedKeyChange?.(null);
    }
  }, [effectiveSelectedKey, selectedKey, slots, onSelectedKeyChange]);

  function selectPoint(key: string) {
    const next = effectiveSelectedKey === key ? null : key;
    if (selectedKey === undefined) setLocalSelectedKey(next);
    onSelectedKeyChange?.(next);
  }

  function toggle(definition: ChartSeries) {
    let next: string[];
    if (visibleSeries.includes(definition.key)) {
      next = visibleSeries.length > 1 ? visibleSeries.filter(key => key !== definition.key) : visibleSeries;
    } else {
      next = visibleSeries.length >= maxVisibleSeries ? visibleSeries : [...visibleSeries, definition.key];
    }
    onVisibleSeriesChange?.(next);
  }

  function segments(definition: ChartSeries, source: Map<string, Row>): string[] {
    const result: string[] = [];
    let points: string[] = [];
    slots.forEach((slot, index) => {
      const value = numericValue(source.get(slot), definition.key);
      if (value === null) {
        if (points.length) result.push(points.join(" "));
        points = [];
      } else points.push(`${x(index)},${y(definition, value)}`);
    });
    if (points.length) result.push(points.join(" "));
    return result;
  }

  const metadataBlock = <dl className="chartMetadata">
    <div><dt>{text.range}</dt><dd>{rangeLabel(metadata.range)}</dd></div>
    {comparison.status !== "none" && <div><dt>{text.comparison}</dt><dd>{rangeLabel(metadata.comparisonRange)}</dd></div>}
    <div><dt>{text.timezone}</dt><dd>{metadata.timezone || "—"}</dd></div>
    <div><dt>{text.grain}</dt><dd>{metadata.grain || "—"}</dd></div>
    <div><dt>{text.unit}</dt><dd>{units.map(unit => text[unit]).join(" · ")}</dd></div>
    <div><dt>{text.freshness}</dt><dd>{metadata.freshness || "—"}</dd></div>
  </dl>;

  return <figure className="analysisChart" aria-labelledby={`${id}-title`} aria-describedby={`${id}-summary`} aria-busy={actualState === "loading"}>
    <figcaption id={`${id}-title`}>{title}</figcaption>
    {metadataBlock}
    {(metadata.partial || metadata.stale || comparison.status === "partial" || comparison.status === "unavailable") && <div className="chartNotices" aria-live="polite">
      {metadata.partial && <p className="chartNotice partial"><strong>{text.partial}.</strong> {metadata.partialReason}</p>}
      {metadata.stale && <p className="chartNotice stale"><strong>{text.stale}.</strong> {metadata.staleReason}</p>}
      {comparison.status === "partial" && <p className="chartNotice comparison"><strong>{text.comparisonPartial}</strong> {comparison.reason}</p>}
      {comparison.status === "unavailable" && <p className="chartNotice comparison"><strong>{text.comparisonUnavailable}</strong> {comparison.reason}</p>}
    </div>}
    {actualState === "loading" ? <div className="chartState loading" role="status">{text.loading}</div>
      : actualState === "error" ? <div className="chartState error" role="alert"><strong>{text.error}</strong>{errorMessage && <span>{errorMessage}</span>}</div>
      : actualState === "empty" ? <div className="chartState empty" role="status">{text.empty}</div>
      : <>
        <div className="chartLegend" aria-label={text.series}>
          {series.map(def => {
            const selected = visibleSeries.includes(def.key);
            const capped = !selected && visibleSeries.length >= maxVisibleSeries;
            return <button type="button" key={def.key} className={selected ? "active" : ""} aria-pressed={selected} disabled={capped} onClick={() => toggle(def)}>
              <span className="legendLine current" style={{ borderColor: def.color }} />{def.label}<small>{text[def.unit]}</small>
            </button>;
          })}
          <span className="periodLegend"><i className="legendLine current" />{text.current}</span>
          {comparison.status === "complete" && <span className="periodLegend"><i className="legendLine previous" />{text.comparison}</span>}
        </div>
        <div className="chartCanvas">
          <svg viewBox={`0 0 ${WIDTH} ${height}`} role="img" aria-label={title} style={{ minHeight: height }}>
            {units.flatMap(unit => {
              const lane = laneFor(unit);
              const scale = scales[unit];
              const inverted = active.some(def => def.unit === unit && def.invert);
              return Array.from({ length: 3 }, (_, index) => {
                const yy = lane.top + index * lane.height / 2;
                const shown = inverted ? scale.minimum + scale.span * index / 2 : scale.maximum - scale.span * index / 2;
                return <g key={`${unit}-${index}`}><line x1={PAD.left} x2={WIDTH - PAD.right} y1={yy} y2={yy} className="gridLine" /><text x={PAD.left - 8} y={yy + 4} textAnchor="end" className="axisText">{format(shown, unit)}</text></g>;
              });
            })}
            {units.map(unit => {
              const lane = laneFor(unit);
              return <g key={`axis-${unit}`}>
                <text x="16" y={lane.top + lane.height / 2} textAnchor="middle" className="axisTitle" transform={`rotate(-90 16 ${lane.top + lane.height / 2})`}>{text[unit]}</text>
                <line x1={PAD.left} x2={PAD.left} y1={lane.top} y2={lane.bottom} className="axisLine" />
                <line x1={PAD.left} x2={WIDTH - PAD.right} y1={lane.bottom} y2={lane.bottom} className="axisLine" />
              </g>;
            })}
            {slots.map((slot, index) => {
              const label = labelOf(currentByKey.get(slot)) || labelOf(comparisonByKey.get(slot));
              const show = slots.length <= 8 || index % Math.ceil(slots.length / 7) === 0 || index === slots.length - 1;
              return show ? <text key={slot} x={x(index)} y={height - 27} textAnchor="middle" className="axisText">{label}</text> : null;
            })}
            {active.flatMap(def => segments(def, currentByKey).map((points, index) => <polyline key={`current-${def.key}-${index}`} points={points} fill="none" stroke={def.color} strokeWidth="3" vectorEffect="non-scaling-stroke" />))}
            {comparison.status === "complete" && active.flatMap(def => segments(def, comparisonByKey).map((points, index) => <polyline key={`comparison-${def.key}-${index}`} points={points} fill="none" stroke={def.color} strokeWidth="2.5" strokeDasharray="8 6" opacity="0.78" vectorEffect="non-scaling-stroke" />))}
            {slots.map((slot, index) => {
              const current = currentByKey.get(slot);
              const previous = comparisonByKey.get(slot);
              const label = labelOf(current) || labelOf(previous);
              const ariaValues = active.flatMap(def => [
                `${text.current} ${def.label} ${numericValue(current, def.key) === null ? text.unavailable : format(numericValue(current, def.key) as number, def.unit)}`,
                ...(comparison.status === "complete" ? [`${text.comparison} ${def.label} ${numericValue(previous, def.key) === null ? text.unavailable : format(numericValue(previous, def.key) as number, def.unit)}`] : []),
              ]).join(", ");
              const hitTop = laneFor(units[0]).top;
              const hitBottom = laneFor(units[units.length - 1]).bottom;
              return <g key={slot} className={effectiveSelectedKey === slot ? "selectedPoint" : ""}>
                {current && (annotationDates.has(current.date) || annotationDates.has(label)) ? <path d={`M ${x(index)-5} ${PAD.top-10} L ${x(index)+5} ${PAD.top-10} L ${x(index)} ${PAD.top-2} Z`} className="annotationMarker" /> : null}
                <rect x={x(index)-10} y={hitTop} width="20" height={hitBottom-hitTop} fill="#ffffff" fillOpacity="0.001" tabIndex={0} role="button" aria-pressed={effectiveSelectedKey === slot}
                  aria-label={`${label}. ${ariaValues}`}
                  onClick={() => selectPoint(slot)}
                  onFocus={() => setTransientKey(slot)} onBlur={() => setTransientKey(null)} onMouseEnter={() => setTransientKey(slot)} onMouseLeave={() => setTransientKey(null)}
                  onKeyDown={event => {
                    if (event.key === "ArrowRight") { event.preventDefault(); (event.currentTarget.parentElement?.nextElementSibling?.querySelector("rect") as SVGRectElement | null)?.focus(); }
                    if (event.key === "ArrowLeft") { event.preventDefault(); (event.currentTarget.parentElement?.previousElementSibling?.querySelector("rect") as SVGRectElement | null)?.focus(); }
                    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectPoint(slot); }
                  }} />
                {active.map(def => {
                  const value = numericValue(current, def.key);
                  return value === null ? null : <circle key={`current-${def.key}`} cx={x(index)} cy={y(def, value)} r="4" fill={def.color} aria-hidden="true" />;
                })}
                {comparison.status === "complete" && active.map(def => {
                  const value = numericValue(previous, def.key);
                  return value === null ? null : <circle key={`comparison-${def.key}`} cx={x(index)} cy={y(def, value)} r="4" fill="#15191a" stroke={def.color} strokeWidth="2" aria-hidden="true" />;
                })}
              </g>;
            })}
          </svg>
          {activeIndex >= 0 && <div className="chartTooltip" role="status" style={{ left: `${Math.min(Math.max(x(activeIndex) / WIDTH * 100, 10), 84)}%` }}>
            <strong>{labelOf(activeCurrent) || labelOf(activeComparison)}</strong>
            <small>{text.current}: {activeCurrent ? `${activeCurrent.periodStart || ""}${activeCurrent.periodEnd && activeCurrent.periodEnd !== activeCurrent.periodStart ? ` – ${activeCurrent.periodEnd}` : ""}` : text.unavailable}</small>
            {active.map(def => <span key={`current-${def.key}`}><i className="tooltipLine current" style={{ borderColor: def.color }} />{def.label} ({text[def.unit]}): {numericValue(activeCurrent, def.key) === null ? text.unavailable : format(numericValue(activeCurrent, def.key) as number, def.unit)}</span>)}
            {comparison.status === "complete" && <><small>{text.comparison}: {activeComparison ? `${activeComparison.periodStart || ""}${activeComparison.periodEnd && activeComparison.periodEnd !== activeComparison.periodStart ? ` – ${activeComparison.periodEnd}` : ""}` : text.unavailable}</small>
              {active.map(def => <span key={`comparison-${def.key}`}><i className="tooltipLine previous" style={{ borderColor: def.color }} />{def.label} ({text[def.unit]}): {numericValue(activeComparison, def.key) === null ? text.unavailable : format(numericValue(activeComparison, def.key) as number, def.unit)}</span>)}</>}
            {annotations.filter(item => activeCurrent && (item.date === activeCurrent.date || item.date === labelOf(activeCurrent))).map(item => <small key={item.id}>{item.title}</small>)}
            {effectiveSelectedKey === activeKey && <small className="selectionLabel">{text.selected}</small>}
          </div>}
        </div>
      </>}
    <p id={`${id}-summary`} className="srOnly">{actualState === "ready" ? summary : actualState === "loading" ? text.loading : actualState === "error" ? `${text.error} ${errorMessage || ""}` : text.empty}. {active.some(def => def.invert) ? text.reversed : ""}</p>
  </figure>;
}
