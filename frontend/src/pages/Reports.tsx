import { useEffect, useState } from "react";
import { api } from "../api";
import { ModuleResults } from "../components/ModuleResults";
import { Button, Empty, Icon, Panel, Pill, RiskCells, Segmented } from "../components/ui";
import { useLiveContext } from "../live-context";
import { KINDS, KIND_LIST, clock, parseTs, stateLabel, stateTone } from "../lib";
import type { Kind } from "../types";
import { downloadReport } from "./Dashboard";

type Result = Record<string, unknown> | null;

export function Reports() {
  const { analytics, telemetry } = useLiveContext();
  const [kind, setKind] = useState<Kind>("ddos");
  const [results, setResults] = useState<Record<string, Result>>({});

  const recent = analytics.filter((r) => r.state === "RESULT").slice(-12).reverse();
  const ids = recent.map((r) => r.id).join(",");

  useEffect(() => {
    const missing = recent.filter((r) => !(r.id in results));
    if (!missing.length) return;
    Promise.all(missing.map(async (r) => [r.id, await api.result(r.id)] as const)).then((pairs) =>
      setResults((m) => ({ ...m, ...Object.fromEntries(pairs) }))
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids]);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-ink">Reports</h1>
          <p className="mt-1 text-xs text-muted">What the agent decided, what it observed, and what it concluded — per scenario and per run.</p>
        </div>
        <Button onClick={() => downloadReport(telemetry, analytics)} disabled={!analytics.length}>
          <Icon name="download" size={14} />
          Export JSON
        </Button>
      </div>

      <div className="flex items-center justify-between">
        <h2 className="text-[13px] font-semibold text-ink">Scenario results</h2>
        <Segmented value={kind} onChange={setKind} options={KIND_LIST.map((k) => ({ value: k.kind, label: k.name }))} />
      </div>
      <ModuleResults kind={kind} />

      <h2 className="mt-2 text-[13px] font-semibold text-ink">Completed runs</h2>
      {recent.length === 0 ? (
        <Empty>No completed sessions to report on yet.</Empty>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {recent.map((r) => {
            const res = results[r.id];
            const reasoning = (res?.decision as { reasoning?: string } | undefined)?.reasoning;
            const meta = KINDS[r.kind];
            return (
              <Panel
                key={r.id}
                title={
                  <span className="flex items-center gap-2">
                    <span className="font-mono">{r.label}</span>
                    <span className="font-normal text-muted">· {meta.name}</span>
                  </span>
                }
                sub={clock(parseTs(r.started_at), true)}
                actions={<Pill tone={stateTone(r.state)}>{stateLabel(r.state)}</Pill>}
              >
                <div className="grid grid-cols-3 gap-3 border-b border-line pb-3">
                  <div>
                    <div className="text-2xs text-muted">{meta.decisionLabel}</div>
                    <div className="mt-0.5 font-mono text-sm text-ink">
                      {r.decision == null ? "—" : `${r.decision} ${meta.decisionUnit}`}
                    </div>
                  </div>
                  <div>
                    <div className="text-2xs text-muted">CPU Δ</div>
                    <div className="mt-0.5 font-mono text-sm text-ink">
                      {r.deltas?.cpu_percent == null ? "—" : `${r.deltas.cpu_percent > 0 ? "+" : ""}${r.deltas.cpu_percent} pts`}
                    </div>
                  </div>
                  <div>
                    <div className="text-2xs text-muted">Risk</div>
                    <div className="mt-1">
                      <RiskCells score={r.risk_score} />
                    </div>
                  </div>
                </div>
                <p className="mt-3 text-xs text-ink">{String(res?.summary ?? "Loading summary…")}</p>
                {reasoning && <p className="mt-2 text-xs leading-relaxed text-muted">{reasoning}</p>}
              </Panel>
            );
          })}
        </div>
      )}
    </div>
  );
}
