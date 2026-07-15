import { AnalysisChart, type ChartSeries } from "./AnalysisChart";

const series: ChartSeries[] = [
  { key: "clicks", label: "Clicks", color: "#36c9a5", unit: "count" },
  { key: "impressions", label: "Impressions", color: "#75a7ff", unit: "count" },
  { key: "ctr", label: "CTR", color: "#f2b84b", unit: "ratio" },
  { key: "position", label: "Position", color: "#d991ff", unit: "rank", invert: true },
];

const current = [
  { label: "2026-07-01", alignmentKey: "day:0", periodStart: "2026-07-01", periodEnd: "2026-07-01", clicks: 4, impressions: 80, ctr: .05, position: 3.2 },
  { label: "2026-07-02", alignmentKey: "day:1", periodStart: "2026-07-02", periodEnd: "2026-07-02", clicks: 7, impressions: 110, ctr: .063636, position: 2.7 },
  { label: "2026-07-04", alignmentKey: "day:3", periodStart: "2026-07-04", periodEnd: "2026-07-04", clicks: 5, impressions: 95, ctr: .052632, position: 4.1 },
];

const previous = [
  { label: "2026-06-27", alignmentKey: "day:0", periodStart: "2026-06-27", periodEnd: "2026-06-27", clicks: 3, impressions: 70, ctr: .042857, position: 3.8 },
  { label: "2026-06-28", alignmentKey: "day:1", periodStart: "2026-06-28", periodEnd: "2026-06-28", clicks: 8, impressions: 120, ctr: .066667, position: 3.1 },
  { label: "2026-06-29", alignmentKey: "day:2", periodStart: "2026-06-29", periodEnd: "2026-06-29", clicks: 6, impressions: 100, ctr: .06, position: 2.9 },
];

const metadata = {
  range: { start: "2026-07-01", end: "2026-07-04" },
  comparisonRange: { start: "2026-06-27", end: "2026-06-30" },
  timezone: "America/Los_Angeles (GSC reporting)",
  grain: "Day",
  freshness: "2026-07-05T08:00:00",
};

export function ChartStateFixtures({ locale }: { locale: string }) {
  const fixtures = [
    { title: "Complete comparison", rows: current, comparisonRows: previous, comparison: { status: "complete" as const } },
    { title: "Loading", rows: current, state: "loading" as const },
    { title: "Empty", rows: [], state: "empty" as const },
    { title: "Partial", rows: current, metadata: { ...metadata, partial: true, partialReason: "Deterministic partial coverage fixture." } },
    { title: "Stale", rows: current, metadata: { ...metadata, stale: true, staleReason: "Deterministic stale cache fixture." } },
    { title: "Comparison unavailable", rows: current, comparison: { status: "unavailable" as const, reason: "Deterministic unavailable comparison fixture." } },
    { title: "Error", rows: current, state: "error" as const, errorMessage: "Deterministic chart error fixture." },
  ];
  return <main className="fixturePage">
    <h1>SEO-048 chart state fixtures</h1>
    <p>Deterministic local QA only. No source sync is performed.</p>
    <section className="panel" data-fixture="four-metric-unit-lanes">
      <AnalysisChart rows={current} comparisonRows={previous} comparison={{ status: "complete" }} series={series} visibleSeries={["clicks", "impressions", "ctr", "position"]} locale={locale} title="Four metric unit lanes" metadata={metadata} />
    </section>
    {fixtures.map(fixture => <section className="panel" key={fixture.title} data-fixture={fixture.title.toLowerCase().replaceAll(" ", "-")}>
      <AnalysisChart rows={fixture.rows} comparisonRows={fixture.comparisonRows || []} comparison={fixture.comparison || { status: "none" }} series={series} visibleSeries={["clicks", "impressions"]} locale={locale} title={fixture.title} state={fixture.state || "ready"} errorMessage={fixture.errorMessage} metadata={fixture.metadata || metadata} />
    </section>)}
  </main>;
}
