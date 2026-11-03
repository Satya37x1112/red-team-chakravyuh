import { useMemo } from "react";
import type { AnalyticsRow, Kind } from "../types";
import { Dot, Empty, Panel } from "./ui";

const KIND_META: { kind: Kind; name: string; color: string }[] = [
  { kind: "ddos", name: "DDoS", color: "rgb(var(--accent))" },
  { kind: "bruteforce", name: "Brute Force", color: "rgb(var(--series-2))" },
  { kind: "ratuba", name: "RAT", color: "rgb(var(--warn))" },
];

const Legend = () => (
  <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
    {KIND_META.map((k) => (
      <span key={k.kind} className="flex items-center gap-1.5 text-2xs text-muted">
        <span className="h-2 w-2 rounded-sm" style={{ background: k.color }} />
        {k.name}
      </span>
    ))}
  </div>
);

/** Pseudo-3D radar: an elliptical (tilted-disc) grid with extruded, gradient-filled
 *  polygons per scenario — volume, completion, risk, tempo. */
export function ScenarioRadar({ analytics }: { analytics: AnalyticsRow[] }) {
  const axes = ["Volume", "Completion", "Mean risk", "Tempo"];
  const data = useMemo(() => {
    const byKind = KIND_META.map(({ kind }) => {
      const rows = analytics.filter((r) => r.kind === kind);
      const done = rows.filter((r) => r.state === "RESULT");
      const risks = rows.map((r) => r.risk_score).filter((v): v is number => v != null);
      const durs = done.map((r) => r.duration_s).filter((v): v is number => v != null);
      return {
        runs: rows.length,
        completion: rows.length ? done.length / rows.length : 0,
        risk: risks.length ? risks.reduce((a, b) => a + b, 0) / risks.length : 0,
        dur: durs.length ? durs.reduce((a, b) => a + b, 0) / durs.length : 0,
      };
    });
    const maxRuns = Math.max(1, ...byKind.map((b) => b.runs));
    const maxDur = Math.max(1, ...byKind.map((b) => b.dur));
    return byKind.map((b) => [
      b.runs / maxRuns,
      b.completion,
      b.risk,
      b.dur ? 1 - b.dur / maxDur + 0.15 : 0,
    ]);
  }, [analytics]);

  const cx = 150, cy = 118, R = 92, SQUASH = 0.62, N = axes.length, DEPTH = 10;
  const pt = (i: number, r: number, dy = 0) => {
    const a = -Math.PI / 2 + (i / N) * 2 * Math.PI;
    return [cx + Math.cos(a) * R * r, cy + Math.sin(a) * R * SQUASH * r + dy];
  };
  const poly = (vals: number[], dy = 0) =>
    vals.map((v, i) => pt(i, Math.max(0.02, v), dy).map((n) => n.toFixed(1)).join(",")).join(" ");

  if (!analytics.length)
    return (
      <Panel title="Scenario profile" sub="Volume · completion · risk · tempo">
        <Empty>Run sessions to build the scenario profile.</Empty>
      </Panel>
    );

  return (
    <Panel title="Scenario profile" sub="Volume · completion · risk · tempo">
      <svg viewBox="0 0 300 230" className="w-full">
        <defs>
          {KIND_META.map((k, i) => (
            <linearGradient key={k.kind} id={`rad-${i}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={k.color} stopOpacity="0.38" />
              <stop offset="100%" stopColor={k.color} stopOpacity="0.08" />
            </linearGradient>
          ))}
          <filter id="rad-shadow" x="-20%" y="-20%" width="140%" height="160%">
            <feDropShadow dx="0" dy="4" stdDeviation="4" floodOpacity="0.18" />
          </filter>
        </defs>
        {/* tilted elliptical grid rings */}
        {[0.25, 0.5, 0.75, 1].map((r) => (
          <ellipse key={r} cx={cx} cy={cy} rx={R * r} ry={R * SQUASH * r} className="fill-none stroke-line" />
        ))}
        {axes.map((ax, i) => {
          const [x, y] = pt(i, 1);
          const [lx, ly] = pt(i, 1.22);
          return (
            <g key={ax}>
              <line x1={cx} y1={cy} x2={x} y2={y} className="stroke-line" />
              <text x={lx} y={ly} textAnchor="middle" dominantBaseline="middle" className="fill-muted text-[10px]">{ax}</text>
            </g>
          );
        })}
        {/* extruded depth + top face per scenario */}
        {data.map((vals, k) => (
          <g key={k} filter="url(#rad-shadow)">
            <polygon points={poly(vals, DEPTH)} fill={KIND_META[k].color} fillOpacity={0.14} />
            <polygon points={poly(vals)} fill={`url(#rad-${k})`} stroke={KIND_META[k].color} strokeWidth={1.6} strokeLinejoin="round" />
          </g>
        ))}
      </svg>
      <Legend />
    </Panel>
  );
}

/** Session outcomes per scenario: completed / killed / failed / running. */
export function OutcomesByScenario({ analytics }: { analytics: AnalyticsRow[] }) {
  const seg = [
    { key: "RESULT", label: "Completed", color: "rgb(var(--ok))", tone: "ok" as const },
    { key: "running", label: "Running", color: "rgb(var(--warn))", tone: "warn" as const },
    { key: "KILLED", label: "Killed", color: "rgb(var(--crit))", tone: "crit" as const },
    { key: "FAILED", label: "Failed", color: "rgb(var(--muted))", tone: "muted" as const },
  ];
  const rows = useMemo(
    () =>
      KIND_META.map(({ kind, name }) => {
        const rs = analytics.filter((r) => r.kind === kind);
        const done = rs.filter((r) => r.state === "RESULT").length;
        const killed = rs.filter((r) => r.state === "KILLED").length;
        const failed = rs.filter((r) => r.state === "FAILED").length;
        const running = rs.length - done - killed - failed;
        return { name, total: rs.length, counts: { RESULT: done, running, KILLED: killed, FAILED: failed } as Record<string, number> };
      }),
    [analytics]
  );
  const max = Math.max(1, ...rows.map((r) => r.total));

  if (!analytics.length)
    return (
      <Panel title="Session outcomes" sub="How each scenario's runs ended">
        <Empty>No sessions yet.</Empty>
      </Panel>
    );

  return (
    <Panel title="Session outcomes" sub="How each scenario's runs ended">
      <div className="flex flex-col gap-4 pt-1">
        {rows.map((r) => (
          <div key={r.name}>
            <div className="mb-1 flex items-baseline justify-between">
              <span className="text-xs text-ink">{r.name}</span>
              <span className="font-mono text-2xs text-muted">{r.total} run{r.total === 1 ? "" : "s"}</span>
            </div>
            <div className="flex h-5 overflow-hidden rounded bg-line" style={{ width: `${Math.max(8, (r.total / max) * 100)}%` }}>
              {seg.map((s) =>
                r.counts[s.key] ? (
                  <div
                    key={s.key}
                    title={`${s.label}: ${r.counts[s.key]}`}
                    style={{ width: `${(r.counts[s.key] / r.total) * 100}%`, background: s.color }}
                  />
                ) : null
              )}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 border-t border-line pt-3">
        {seg.map((s) => (
          <span key={s.key} className="flex items-center gap-1.5 text-2xs text-muted">
            <Dot tone={s.tone} /> {s.label}
          </span>
        ))}
      </div>
    </Panel>
  );
}
