import type { ReactNode } from "react";
import type { StateTone } from "../lib";

const ICONS: Record<string, string> = {
  grid: "M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h6v6h-6z",
  pulse: "M22 12h-4l-3 9L9 3l-3 9H2",
  key: "M15.5 7.5 19 4m2-2-2 2m0 0 3 3-3.5 3.5-3-3M11.4 11.6a5.5 5.5 0 1 1-7.8 7.8 5.5 5.5 0 0 1 7.8-7.8Z",
  terminal: "M4 17l6-6-6-6 M12 19h8",
  bot: "M12 8V4H8 M5 8h14a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z M2 14h2 M20 14h2 M15 13v2 M9 13v2",
  history: "M3 3v5h5 M3.05 13A9 9 0 1 0 6 5.3L3 8 M12 7v5l4 2",
  file: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8",
  network: "M9 2h6v6H9z M2 16h6v6H2z M16 16h6v6h-6z M5 16v-3h14v3 M12 13V8",
  power: "M18.36 6.64a9 9 0 1 1-12.73 0 M12 2v10",
  sun: "M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8 M12 2v2 M12 20v2 M4.93 4.93l1.41 1.41 M17.66 17.66l1.41 1.41 M2 12h2 M20 12h2 M4.93 19.07l1.41-1.41 M17.66 6.34l1.41-1.41",
  moon: "M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z",
  play: "M7 4.5v15l12-7.5z",
  download: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M7 10l5 5 5-5 M12 15V3",
  chevron: "M6 9l6 6 6-6",
  arrow: "M7 17L17 7 M8 7h9v9",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  refresh: "M21 12a9 9 0 1 1-2.64-6.36L21 8 M21 3v5h-5",
  layers: "M12 2 2 7l10 5 10-5-10-5z M2 17l10 5 10-5 M2 12l10 5 10-5",
  hub: "M12 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4z M12 2v8 M12 14v8 M2 12h8 M14 12h8",
  alert: "M10.3 3.3 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.3a2 2 0 0 0-3.4 0z M12 9v4 M12 17h.01",
};

export function Icon({ name, size = 15, className = "" }: { name: keyof typeof ICONS; size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`shrink-0 ${className}`}
      aria-hidden
    >
      <path d={ICONS[name]} />
    </svg>
  );
}

/** Concentric, broken rings — the chakravyuh formation. */
export function Logo({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect width="24" height="24" rx="5" className="fill-accent" />
      <g stroke="white" strokeWidth="1.6" strokeLinecap="round">
        <path d="M12 3.6a8.4 8.4 0 1 1-7.3 4.2" />
        <path d="M12 6.8a5.2 5.2 0 1 0 4.6 2.8" />
        <path d="M12 10a2 2 0 1 1-1.8 1.1" />
      </g>
    </svg>
  );
}

export function Panel({
  title,
  sub,
  actions,
  children,
  className = "",
  bodyClass = "p-4",
}: {
  title?: ReactNode;
  sub?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClass?: string;
}) {
  return (
    <section className={`flex min-w-0 flex-col rounded-lg border border-line bg-surface ${className}`}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3 px-4 pt-3.5">
          <div className="min-w-0">
            {title && <h2 className="text-[13px] font-semibold text-ink">{title}</h2>}
            {sub && <p className="mt-0.5 text-xs text-muted">{sub}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={`min-w-0 flex-1 ${bodyClass}`}>{children}</div>
    </section>
  );
}

/** Numbered section rule used to keep telemetry / decision / analysis visibly separate. */
export function SectionLabel({ index, label, hint }: { index: string; label: string; hint?: ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <span className="font-mono text-2xs text-accent">{index}</span>
      <span className="font-mono text-2xs font-medium uppercase tracking-[0.14em] text-ink">{label}</span>
      <span className="h-px flex-1 bg-line" />
      {hint && <span className="font-mono text-2xs text-faint">{hint}</span>}
    </div>
  );
}

const DOT: Record<StateTone, string> = { ok: "bg-ok", warn: "bg-warn", crit: "bg-crit", muted: "bg-faint" };

export function Dot({ tone, pulse = false }: { tone: StateTone; pulse?: boolean }) {
  return <span className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${DOT[tone]} ${pulse ? "animate-pulse-dot" : ""}`} />;
}

const PILL: Record<StateTone, string> = {
  ok: "border-ok/30 bg-ok/10 text-ok",
  warn: "border-warn/30 bg-warn/10 text-warn",
  crit: "border-crit/35 bg-crit/10 text-crit",
  muted: "border-line bg-raised text-muted",
};

export function Pill({ tone = "muted", children, dot = true }: { tone?: StateTone; children: ReactNode; dot?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded border px-1.5 py-0.5 font-mono text-2xs ${PILL[tone]}`}>
      {dot && <Dot tone={tone} pulse={tone === "warn"} />}
      {children}
    </span>
  );
}

export function Tag({ children }: { children: ReactNode }) {
  return (
    <span className="rounded border border-line px-1.5 py-px font-mono text-2xs text-muted">{children}</span>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded border border-current/30 px-1 font-mono text-[10px] leading-4 opacity-80">{children}</kbd>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded border border-line bg-canvas p-0.5" role="tablist">
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={o.value === value}
          onClick={() => onChange(o.value)}
          className={`rounded-[3px] px-2 py-0.5 text-xs transition-colors ${
            o.value === value ? "bg-raised font-medium text-ink shadow-[inset_0_0_0_1px_rgb(var(--line-strong))]" : "text-muted hover:text-ink"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Button({
  children,
  onClick,
  variant = "ghost",
  disabled,
  title,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "ghost" | "danger";
  disabled?: boolean;
  title?: string;
  type?: "button" | "submit";
}) {
  const styles = {
    primary: "border-accent bg-accent text-white hover:bg-accentHover hover:border-accentHover",
    ghost: "border-line bg-surface text-ink hover:border-lineStrong hover:bg-raised",
    danger: "border-crit/50 text-crit hover:bg-crit hover:text-white hover:border-crit",
  }[variant];
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`inline-flex h-8 items-center gap-2 rounded border px-3 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-45 ${styles}`}
    >
      {children}
    </button>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="grid h-full min-h-[120px] place-items-center rounded border border-dashed border-line px-4 py-6 text-center text-xs text-muted">
      <div>{children}</div>
    </div>
  );
}

export function Stat({
  label,
  value,
  unit,
  sub,
  tone,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  sub?: ReactNode;
  tone?: StateTone;
}) {
  const empty = value === null || value === undefined;
  return (
    <div className="min-w-0 px-4 py-3.5">
      <div className="flex items-center gap-1.5 text-xs text-muted">
        {tone && <Dot tone={tone} />}
        {label}
      </div>
      <div className={`mt-1.5 truncate font-mono text-[22px] leading-7 ${empty ? "text-faint" : "text-ink"}`}>
        {empty ? "—" : value}
        {!empty && unit && <span className="ml-1 text-xs text-muted">{unit}</span>}
      </div>
      {sub && <div className="mt-1 truncate text-2xs text-faint">{sub}</div>}
    </div>
  );
}

export function Meter({ percent }: { percent: number | null }) {
  if (percent == null) return <div className="h-1 rounded-full bg-line" />;
  const tone = percent >= 85 ? "bg-crit" : percent >= 65 ? "bg-warn" : "bg-ok";
  return (
    <div className="h-1 overflow-hidden rounded-full bg-line">
      <div className={`h-full rounded-full ${tone}`} style={{ width: `${Math.min(100, Math.max(0, percent))}%` }} />
    </div>
  );
}

/** Ten-cell segmented risk bar (0..1). */
export function RiskCells({ score }: { score: number | null }) {
  if (score == null) return <span className="font-mono text-2xs text-faint">—</span>;
  const filled = Math.round(score * 10);
  const tone = score >= 0.7 ? "bg-crit" : score >= 0.4 ? "bg-warn" : "bg-ok";
  return (
    <span className="inline-flex items-center gap-2">
      <span className="inline-flex gap-px">
        {Array.from({ length: 10 }, (_, i) => (
          <span key={i} className={`h-3 w-[3px] rounded-[1px] ${i < filled ? tone : "bg-line"}`} />
        ))}
      </span>
      <span className="font-mono text-2xs text-muted">{(score * 100).toFixed(0)}</span>
    </span>
  );
}
