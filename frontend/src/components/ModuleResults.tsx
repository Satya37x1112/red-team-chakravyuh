import { Link } from "react-router-dom";
import { useLiveContext } from "../live-context";
import { KINDS, clock, duration, median, parseTs, stateLabel, stateTone } from "../lib";
import type { AnalyticsRow, Kind } from "../types";
import { BarChart, TipRow, type BarDatum } from "./charts";
import { Empty, Icon, Panel, Pill, Tag } from "./ui";

const MAX_RUNS = 24;
const short = (label: string) => label.split("-").pop() ?? label;

function runTip(r: AnalyticsRow, lines: [string, string][]) {
  return (
    <>
      <div className="mb-1 flex items-center justify-between">
        <span className="font-mono text-2xs text-ink">{r.label}</span>
        <span className="font-mono text-2xs text-faint">{clock(parseTs(r.started_at))}</span>
      </div>
      {lines.map(([k, v]) => (
        <TipRow key={k} label={k} value={v} />
      ))}
      <TipRow label="Status" value={stateLabel(r.state)} />
    </>
  );
}

function useKindRuns(kind: Kind) {
  const { analytics } = useLiveContext();
  return analytics.filter((r) => r.kind === kind);
}

function decisionData(rows: AnalyticsRow[], kind: Kind): BarDatum[] {
  const meta = KINDS[kind];
  return rows.map((r) => ({
    key: r.id,
    label: short(r.label),
    value: r.decision,
    dim: r.state !== "RESULT",
    tip: runTip(r, [
      [meta.decisionLabel, r.decision == null ? "unavailable" : `${r.decision} ${meta.decisionUnit}`],
      ["After adapt", r.adapted == null ? "—" : `${r.adapted} ${meta.decisionUnit}`],
      ["Source", r.decision_source ?? "—"],
    ]),
  }));
}

function impactData(rows: AnalyticsRow[], kind: Kind): BarDatum[] {
  const meta = KINDS[kind];
  if (kind === "ratuba") {
    return rows.map((r) => ({
      key: r.id,
      label: short(r.label),
      value: r.risk_score == null ? null : r.risk_score * 100,
      dim: r.state !== "RESULT",
      tip: runTip(r, [
        ["Risk score", r.risk_score == null ? "n/a" : (r.risk_score * 100).toFixed(0)],
        ["Anomalies", String(r.anomalies.length)],
      ]),
    }));
  }
  const metric = meta.impactMetric!;
  return rows.map((r) => {
    const d = r.deltas?.[metric] ?? null;
    const b = r.before?.[metric];
    const a = r.after?.[metric];
    return {
      key: r.id,
      label: short(r.label),
      value: d,
      dim: r.state !== "RESULT",
      tip: runTip(r, [
        ["Change", d == null ? "n/a" : `${d > 0 ? "+" : ""}${d.toFixed(1)} pts`],
        ["Before → after", b == null || a == null ? "—" : `${b.toFixed(1)}% → ${a.toFixed(1)}%`],
      ]),
    };
  });
}

function Summary({ rows, kind }: { rows: AnalyticsRow[]; kind: Kind }) {
  const meta = KINDS[kind];
  const done = rows.filter((r) => r.state === "RESULT").length;
  const killed = rows.filter((r) => r.state === "KILLED").length;
  const med = median(rows.map((r) => r.decision).filter((v): v is number => v != null));
  const risks = rows.map((r) => r.risk_score).filter((v): v is number => v != null);
  const durs = rows.map((r) => r.duration_s).filter((v): v is number => v != null);
  const cells: [string, string][] = [
    ["Runs", String(rows.length)],
    ["Completed", String(done)],
    ["Killed", String(killed)],
    [`Median ${meta.decisionLabel.toLowerCase()}`, med == null ? "—" : `${med} ${meta.decisionUnit}`],
    kind === "ratuba"
      ? ["Peak risk", risks.length ? (Math.max(...risks) * 100).toFixed(0) : "—"]
      : ["Median duration", duration(median(durs))],
  ];
  return (
    <div className="grid grid-cols-2 divide-line border-b border-line sm:grid-cols-5 sm:divide-x">
      {cells.map(([k, v]) => (
        <div key={k} className="px-4 py-3">
          <div className="text-2xs text-muted">{k}</div>
          <div className="mt-1 font-mono text-base text-ink">{v}</div>
        </div>
      ))}
    </div>
  );
}

function AnomalyBreakdown({ rows }: { rows: AnalyticsRow[] }) {
  const all = rows.flatMap((r) => r.anomalies);
  const cats = ["process", "network", "logon"].map((c) => {
    const hits = all.filter((a) => a.category === c);
    const scores = hits.map((a) => a.score ?? 0);
    return { c, n: hits.length, peak: scores.length ? Math.max(...scores) : null };
  });
  const maxN = Math.max(1, ...cats.map((x) => x.n));
  return (
    <div className="flex flex-col gap-3">
      {cats.map(({ c, n, peak }) => (
        <div key={c}>
          <div className="mb-1 flex items-baseline justify-between text-xs">
            <span className="capitalize text-ink">{c}</span>
            <span className="font-mono text-2xs text-muted">
              {n} flagged{peak != null && ` · peak ${(peak * 100).toFixed(0)}`}
            </span>
          </div>
          <div className="h-2 rounded-sm bg-line">
            <div className="h-full rounded-sm bg-accent" style={{ width: `${(n / maxN) * 100}%`, minWidth: n ? 4 : 0 }} />
          </div>
        </div>
      ))}
      {all.length === 0 && (
        <p className="text-xs text-muted">
          No behavioural deviations crossed the baseline across {rows.length} run{rows.length === 1 ? "" : "s"}.
        </p>
      )}
    </div>
  );
}

const DivergingKey = () => (
  <span className="flex items-center gap-3 font-mono text-2xs text-muted">
    <span className="flex items-center gap-1">
      <span className="h-2 w-2 rounded-sm bg-accent" />
      rise
    </span>
    <span className="flex items-center gap-1">
      <span className="h-2 w-2 rounded-sm bg-series2" />
      drop
    </span>
  </span>
);

/** Full results block for one module — used on the operation page. */
export function ModuleResults({ kind }: { kind: Kind }) {
  const meta = KINDS[kind];
  const rows = useKindRuns(kind).slice(-MAX_RUNS);
  if (!rows.length) {
    return (
      <Panel title={`${meta.name} results`}>
        <Empty>No {meta.name} runs recorded yet. Run an agent session to populate these charts.</Empty>
      </Panel>
    );
  }
  return (
    <Panel title={`${meta.name} results`} sub={`Last ${rows.length} runs, from persisted session data`} bodyClass="">
      <div className="mt-3">
        <Summary rows={rows} kind={kind} />
      </div>
      <div className="grid gap-0 lg:grid-cols-2 lg:divide-x lg:divide-line">
        <div className="p-4">
          <div className="mb-2 text-xs font-medium text-ink">
            Agent decision per run <span className="font-normal text-muted">· {meta.decisionLabel.toLowerCase()} ({meta.decisionUnit})</span>
          </div>
          <BarChart data={decisionData(rows, kind)} height={190} />
        </div>
        <div className="border-t border-line p-4 lg:border-t-0">
          <div className="mb-2 flex items-center justify-between gap-3">
            <span className="text-xs font-medium text-ink">
              {meta.impactLabel}
              <span className="font-normal text-muted"> · {kind === "ratuba" ? "0–100" : "percentage points"}</span>
            </span>
            {kind !== "ratuba" && <DivergingKey />}
          </div>
          {kind === "ratuba" ? (
            <BarChart data={impactData(rows, kind)} height={190} yMax={100} threshold={{ value: 70, label: "high risk" }} />
          ) : (
            <BarChart data={impactData(rows, kind)} height={190} diverging />
          )}
        </div>
      </div>
      {kind === "ratuba" && (
        <div className="border-t border-line p-4">
          <div className="mb-3 text-xs font-medium text-ink">Anomalies by category</div>
          <AnomalyBreakdown rows={rows} />
        </div>
      )}
    </Panel>
  );
}

/** Compact card for the dashboard grid. */
export function ModuleCard({ kind }: { kind: Kind }) {
  const meta = KINDS[kind];
  const rows = useKindRuns(kind);
  const recent = rows.slice(-16);
  const last = rows[rows.length - 1];
  const chart = kind === "ratuba" ? impactData(recent, kind) : decisionData(recent, kind);
  return (
    <Panel bodyClass="flex flex-col p-4">
      <div className="flex items-center justify-between">
        <span className="font-mono text-2xs text-faint">{meta.index}</span>
        <Tag>{meta.mitre}</Tag>
      </div>
      <div className="mt-3 text-[15px] font-semibold text-ink">{meta.name}</div>
      <div className="text-xs text-muted">{meta.sub}</div>

      <div className="mt-4 flex items-end justify-between gap-3">
        <div>
          <div className="text-2xs text-muted">{kind === "ratuba" ? "Last risk score" : `Last ${meta.decisionLabel.toLowerCase()}`}</div>
          <div className="mt-0.5 font-mono text-xl text-ink">
            {!last
              ? "—"
              : kind === "ratuba"
                ? last.risk_score == null ? "—" : (last.risk_score * 100).toFixed(0)
                : last.decision == null ? "—" : `${last.decision}`}
            {last && kind !== "ratuba" && last.decision != null && (
              <span className="ml-1 text-xs text-muted">{meta.decisionUnit}</span>
            )}
            {last && kind !== "ratuba" && last.decision == null && (
              <span className="ml-2 font-mono text-2xs text-warn">llm unavailable</span>
            )}
          </div>
        </div>
        {last && <Pill tone={stateTone(last.state)}>{stateLabel(last.state)}</Pill>}
      </div>

      <div className="mt-3">
        {recent.length ? (
          <BarChart
            data={chart}
            height={118}
            yMax={kind === "ratuba" ? 100 : undefined}
            threshold={kind === "ratuba" ? { value: 70, label: "high" } : undefined}
          />
        ) : (
          <Empty>No runs yet</Empty>
        )}
      </div>

      <div className="mt-3 flex items-center justify-between border-t border-line pt-3">
        <span className="font-mono text-2xs text-faint">
          {rows.length} run{rows.length === 1 ? "" : "s"} · {meta.vector.split(" · ")[0]}
        </span>
        <Link to={meta.path} className="inline-flex items-center gap-1 text-xs font-medium text-ink hover:text-accent">
          Open <Icon name="arrow" size={13} />
        </Link>
      </div>
    </Panel>
  );
}
