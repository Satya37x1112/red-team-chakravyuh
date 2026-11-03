import { useMemo } from "react";
import type { AnalyticsRow, Kind } from "../types";
import { Empty, Panel } from "./ui";

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

/** Radar of each scenario's operational profile: volume, completion, risk, speed. */
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
      b.dur ? 1 - b.dur / maxDur + 0.15 : 0, // faster = higher "tempo"
    ]);
  }, [analytics]);

  const cx = 120, cy = 108, R = 78, N = axes.length;
  const pt = (i: number, r: number) => {
    const a = -Math.PI / 2 + (i / N) * 2 * Math.PI;
    return [cx + Math.cos(a) * R * r, cy + Math.sin(a) * R * r];
  };

  if (!analytics.length)
    return (
      <Panel title="Scenario profile" sub="Volume · completion · risk · tempo">
        <Empty>Run sessions to build the scenario profile.</Empty>
      </Panel>
    );

  return (
    <Panel title="Scenario profile" sub="Volume · completion · risk · tempo">
      <svg viewBox="0 0 240 220" className="w-full">
        {[0.25, 0.5, 0.75, 1].map((r) => (
          <polygon
            key={r}
            points={axes.map((_, i) => pt(i, r).map((n) => n.toFixed(1)).join(",")).join(" ")}
            className="fill-none stroke-line"
          />
        ))}
        {axes.map((ax, i) => {
          const [x, y] = pt(i, 1);
          const [lx, ly] = pt(i, 1.18);
          return (
            <g key={ax}>
              <line x1={cx} y1={cy} x2={x} y2={y} className="stroke-line" />
              <text x={lx} y={ly} textAnchor="middle" dominantBaseline="middle" className="fill-muted text-[8px]">{ax}</text>
            </g>
          );
        })}
        {data.map((vals, k) => (
          <polygon
            key={k}
            points={vals.map((v, i) => pt(i, Math.max(0.02, v)).map((n) => n.toFixed(1)).join(",")).join(" ")}
            fill={KIND_META[k].color}
            fillOpacity={0.12}
            stroke={KIND_META[k].color}
            strokeWidth={1.5}
          />
        ))}
      </svg>
      <Legend />
    </Panel>
  );
}

/** Scatter of completed sessions: risk vs. duration, coloured by scenario. */
export function RiskScatter({ analytics }: { analytics: AnalyticsRow[] }) {
  const pts = useMemo(
    () =>
      analytics
        .filter((r) => r.duration_s != null && r.risk_score != null)
        .map((r) => ({ x: r.duration_s as number, y: (r.risk_score as number) * 100, kind: r.kind })),
    [analytics]
  );
  const W = 360, H = 200, M = { l: 32, r: 12, t: 10, b: 28 };
  const iw = W - M.l - M.r, ih = H - M.t - M.b;
  const maxX = Math.max(10, ...pts.map((p) => p.x));
  const x = (v: number) => M.l + (v / maxX) * iw;
  const y = (v: number) => M.t + ih - (Math.min(v, 100) / 100) * ih;
  const color = (k: Kind) => KIND_META.find((m) => m.kind === k)!.color;

  if (!pts.length)
    return (
      <Panel title="Risk vs. duration" sub="Each dot is a completed session">
        <Empty>No completed sessions with a risk score yet.</Empty>
      </Panel>
    );

  return (
    <Panel title="Risk vs. duration" sub="Each dot is a completed session">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
        {[0, 25, 50, 75, 100].map((t) => (
          <g key={t}>
            <line x1={M.l} y1={y(t)} x2={W - M.r} y2={y(t)} className="stroke-line" />
            <text x={M.l - 6} y={y(t)} textAnchor="end" dominantBaseline="middle" className="fill-faint text-[9px]">{t}</text>
          </g>
        ))}
        <text x={M.l} y={H - 6} className="fill-faint text-[9px]">0s</text>
        <text x={W - M.r} y={H - 6} textAnchor="end" className="fill-faint text-[9px]">{Math.round(maxX)}s</text>
        <text x={10} y={M.t + 4} className="fill-muted text-[9px]">risk</text>
        {pts.map((p, i) => (
          <circle key={i} cx={x(p.x).toFixed(1)} cy={y(p.y).toFixed(1)} r={4} fill={color(p.kind)} fillOpacity={0.75} />
        ))}
      </svg>
      <Legend />
    </Panel>
  );
}
