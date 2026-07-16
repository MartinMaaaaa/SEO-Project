import { AlertTriangle, CheckCircle2, ChevronDown, CircleHelp, Info, Minus, Smartphone, Monitor } from "lucide-react";
import { useState, type KeyboardEvent, type MouseEvent, type ReactNode } from "react";

export type Tone = "good" | "warn" | "bad" | "info" | "neutral";

const toneIcon = {
  good: CheckCircle2,
  warn: AlertTriangle,
  bad: AlertTriangle,
  info: Info,
  neutral: Minus,
};

export function StatusBadge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  const Icon = toneIcon[tone];
  return <span className={`statusBadge ${tone}`}><Icon size={13} aria-hidden="true" />{children}</span>;
}

export function PageHeader({ eyebrow, title, description, status, actions }: {
  eyebrow: string;
  title: string;
  description: string;
  status?: ReactNode;
  actions?: ReactNode;
}) {
  return <header className="pageHeader">
    <div className="pageIdentity">
      <p className="eyebrow">{eyebrow}</p>
      <div className="pageTitleRow"><h1>{title}</h1>{status}</div>
      <p className="subtitle">{description}</p>
    </div>
    {actions && <div className="pageActions">{actions}</div>}
  </header>;
}

export function KpiCard({ label, value, detail, tone = "neutral", trend }: {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  tone?: Tone;
  trend?: ReactNode;
}) {
  return <article className={`metric ${tone}`}>
    <div className="metricTop"><span>{label}</span>{trend}</div>
    <strong>{value}</strong>
    <small>{detail || "—"}</small>
  </article>;
}

export function Disclosure({ title, summary, count, tone = "neutral", defaultOpen = false, children, className = "" }: {
  title: string;
  summary?: ReactNode;
  count?: number | string;
  tone?: Tone;
  defaultOpen?: boolean;
  children: ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const toggleWithMouse = (event: MouseEvent<HTMLElement>) => { event.preventDefault(); setOpen(value => !value); };
  const toggleWithKeyboard = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setOpen(value => !value); }
  };
  return <details className={`disclosure ${tone} ${className}`} open={open}>
    <summary role="button" aria-expanded={open} onClick={toggleWithMouse} onKeyDown={toggleWithKeyboard}>
      <span className="disclosureLabel"><ChevronDown size={17} aria-hidden="true" /><span><strong>{title}</strong>{summary && <small>{summary}</small>}</span></span>
      {count !== undefined && <span className="disclosureCount">{count}</span>}
    </summary>
    <div className="disclosureBody">{children}</div>
  </details>;
}

export function StatePanel({ tone = "info", title, detail, action }: {
  tone?: Tone;
  title: string;
  detail?: ReactNode;
  action?: ReactNode;
}) {
  const Icon = tone === "neutral" ? CircleHelp : toneIcon[tone];
  return <section className={`statePanel ${tone}`} role={tone === "bad" ? "alert" : "status"}>
    <Icon size={19} aria-hidden="true" />
    <div><strong>{title}</strong>{detail && <p>{detail}</p>}</div>
    {action && <div className="stateAction">{action}</div>}
  </section>;
}

export function ActionBar({ children, label }: { children: ReactNode; label?: string }) {
  return <div className="actionBar" role="group" aria-label={label}>{children}</div>;
}

export function PageSelector({ label, value, options, onChange }: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return <label className="pageSelector">{label}<select value={value} onChange={event => onChange(event.target.value)}>{options.map(option => <option value={option} key={option}>{option}</option>)}</select></label>;
}

export function DeviceToggle({ value, onChange, mobileLabel, desktopLabel, allLabel }: {
  value: string;
  onChange: (value: string) => void;
  mobileLabel: string;
  desktopLabel: string;
  allLabel?: string;
}) {
  const options = [
    ...(allLabel ? [{ value: "", label: allLabel, icon: Minus }] : []),
    { value: "mobile", label: mobileLabel, icon: Smartphone },
    { value: "desktop", label: desktopLabel, icon: Monitor },
  ];
  return <div className="segmented" role="group" aria-label={`${mobileLabel} / ${desktopLabel}`}>{options.map(option => {
    const Icon = option.icon;
    return <button type="button" key={option.value || "all"} aria-pressed={value === option.value} className={value === option.value ? "active" : ""} onClick={() => onChange(option.value)}><Icon size={15} aria-hidden="true" />{option.label}</button>;
  })}</div>;
}

export function RunComparisonFrame({ currentTitle, previousTitle, current, previous }: {
  currentTitle: string;
  previousTitle: string;
  current: ReactNode;
  previous: ReactNode;
}) {
  return <div className="runComparisonFrame">
    <section><span>{currentTitle}</span>{current}</section>
    <section><span>{previousTitle}</span>{previous}</section>
  </div>;
}

export function AuditGroup({ title, status, children }: { title: string; status?: ReactNode; children: ReactNode }) {
  return <section className="auditGroup"><header><h3>{title}</h3>{status}</header>{children}</section>;
}
