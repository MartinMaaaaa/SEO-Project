import { Activity, Cloud, Database, RefreshCw, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

type StorageOverview = {
  architecture?: Record<string, string>;
  database?: {
    mode: string;
    primary: string;
    cloudReplica: string;
    localBackup: string;
    cloudDegraded: boolean;
    cloudMessage: string;
  };
  cloud?: {
    configured?: boolean;
    ok?: boolean;
    message?: string;
    tableCounts?: Record<string, number>;
    recentRuns?: ApiRun[];
    quotaSources?: QuotaSource[];
  };
  localBackup?: {
    sqlite?: { path: string; exists: boolean; bytes: number };
    latestBackup?: { backupId?: string; backupPath?: string; files?: number };
    rawDirectories?: Record<string, RawDirectory>;
  };
  recentRuns?: ApiRun[];
  quota?: { sources: QuotaSource[]; source: string; rules: Record<string, string> };
};

type ApiRun = {
  source: string;
  status: string;
  created_at?: string;
  raw_path?: string;
  error?: string;
};

type QuotaSource = {
  source: string;
  label?: string;
  freshness: string;
  todayRuns: number;
  estimatedCallsToday: number;
  latestSuccessAt?: string;
  recommendation?: string;
};

type RawDirectory = {
  path: string;
  exists: boolean;
  files: number;
  bytes: number;
  latestFile?: string;
};

const apiBase = "";

export function App() {
  const [storage, setStorage] = useState<StorageOverview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function loadStorage() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/storage/overview`);
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      setStorage(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown API error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadStorage();
  }, []);

  const counts = storage?.cloud?.tableCounts || {};
  const rawDirectories = storage?.localBackup?.rawDirectories || {};
  const quotaRows = storage?.quota?.sources || [];
  const recentRuns = storage?.recentRuns || [];
  const cloudDegraded = storage?.database?.cloudDegraded;

  return (
    <main className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brandMark">E</span>
          <div>
            <strong>SEO Data Console</strong>
            <small>Local-first operations</small>
          </div>
        </div>
        <nav>
          <span className="active">Storage operations</span>
          <a href="http://127.0.0.1:8766">Open full dashboard</a>
        </nav>
      </aside>

      <section className="content">
        <header className="topbar">
          <div>
            <p className="eyebrow">LOCAL SOURCE / CLOUD REPLICA</p>
            <h1>SEO operations dashboard</h1>
            <p className="subtitle">Local raw exports and SQLite remain authoritative; Supabase provides a shared cloud replica.</p>
          </div>
          <button className="primary" onClick={() => void loadStorage()} disabled={loading}>
            <RefreshCw size={17} />
            Refresh
          </button>
        </header>

        {error ? <div className="alert">API error: {error}</div> : null}

        <section className="kpis">
          <Metric icon={<Database />} label="Source of truth" value="Local data" detail={storage?.localBackup?.sqlite?.exists ? "SQLite available" : "SQLite missing"} tone={storage?.localBackup?.sqlite?.exists ? "good" : "bad"} />
          <Metric icon={<Cloud />} label="Cloud replica" value="Supabase" detail={storage?.cloud?.ok ? "Healthy" : "Needs check"} tone={storage?.cloud?.ok ? "good" : "warn"} />
          <Metric icon={<Activity />} label="Recent runs" value={String(recentRuns.length)} detail={storage?.quota?.source || "pending"} />
          <Metric icon={<ShieldCheck />} label="Local continuity" value={cloudDegraded ? "Protected" : "Ready"} detail={cloudDegraded ? "Cloud unavailable; local data remains usable" : "Local and cloud paths available"} tone={cloudDegraded ? "warn" : "good"} />
        </section>

        <section className="grid">
          <Panel title="Architecture">
            <KeyValue label="Frontend" value={storage?.architecture?.frontend || "React + TypeScript + Vite"} />
            <KeyValue label="Backend" value={storage?.architecture?.backend || "FastAPI service layer"} />
            <KeyValue label="Source of truth" value={storage?.architecture?.sourceOfTruth || "Local raw exports and SQLite"} />
            <KeyValue label="Cloud replica" value={storage?.architecture?.cloudReplica || "Supabase Postgres"} />
          </Panel>

          <Panel title="Cloud database">
            <KeyValue label="Configured" value={storage?.cloud?.configured ? "Yes" : "No"} />
            <KeyValue label="Connection" value={storage?.cloud?.ok ? "Healthy" : storage?.cloud?.message || "Unavailable"} />
            <KeyValue label="Mode" value={storage?.database?.mode || "local_first_cloud_replica"} />
          </Panel>
        </section>

        <section className="grid">
          <Panel title="Cloud table counts">
            <DataTable rows={Object.entries(counts).map(([table, rows]) => ({ table, rows }))} columns={["table", "rows"]} />
          </Panel>
          <Panel title="Local backup cache">
            <DataTable rows={Object.entries(rawDirectories).map(([source, item]) => ({ source, files: item.files, latest: item.latestFile || "-", path: item.path }))} columns={["source", "files", "latest", "path"]} />
          </Panel>
        </section>

        <Panel title="Quota and freshness">
          <DataTable rows={quotaRows} columns={["source", "freshness", "todayRuns", "estimatedCallsToday", "latestSuccessAt", "recommendation"]} />
        </Panel>

        <Panel title="Recent sync runs">
          <DataTable rows={recentRuns.slice(0, 12)} columns={["source", "status", "created_at", "raw_path", "error"]} />
        </Panel>
      </section>
    </main>
  );
}

function Metric(props: { icon: React.ReactNode; label: string; value: string; detail?: string; tone?: "good" | "warn" | "bad" }) {
  return (
    <article className={`metric ${props.tone || ""}`}>
      <div className="metricIcon">{props.icon}</div>
      <span>{props.label}</span>
      <strong>{props.value}</strong>
      <small>{props.detail}</small>
    </article>
  );
}

function Panel(props: { title: string; children: React.ReactNode }) {
  return (
    <section className="panel">
      <h2>{props.title}</h2>
      {props.children}
    </section>
  );
}

function KeyValue(props: { label: string; value: string }) {
  return (
    <div className="kv">
      <strong>{props.label}</strong>
      <span>{props.value}</span>
    </div>
  );
}

function DataTable(props: { rows: Record<string, unknown>[]; columns: string[] }) {
  const rows = useMemo(() => props.rows || [], [props.rows]);
  if (!rows.length) return <p className="empty">No data available.</p>;
  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>{props.columns.map((column) => <th key={column}>{column}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {props.columns.map((column) => <td key={column}>{formatCell(row[column])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatCell(value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
  return String(value);
}
