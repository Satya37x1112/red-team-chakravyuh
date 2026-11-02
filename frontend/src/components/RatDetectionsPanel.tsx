import { useMemo } from "react";
import { useLiveContext } from "../live-context";
import { Gauge } from "./charts";
import { Empty, Panel, Pill } from "./ui";

/** Surfaces the RAT/UBA engine's genuine behavioural analysis: the latest real
 *  risk score and the real anomalies it flagged by category. Not mock — these
 *  come from scoring live endpoint telemetry against its baseline. */
export function RatDetectionsPanel() {
  const { events } = useLiveContext();

  const risk = useMemo(() => {
    const ev = events.find((e) => e.type === "RISK_SCORE_UPDATED");
    const v = ev?.payload?.risk_score as number | undefined;
    return v == null ? null : Math.round(v * 100);
  }, [events]);

  const anomalies = useMemo(
    () =>
      events
        .filter((e) => e.type === "UBA_EVENT_DETECTED")
        .slice(0, 8)
        .map((e) => ({
          category: (e.payload?.category as string) ?? "activity",
          score: e.payload?.score as number | undefined,
          message: (e.payload?.message as string) ?? "",
        })),
    [events]
  );

  const tone = risk == null ? "muted" : risk >= 70 ? "crit" : risk >= 40 ? "warn" : "ok";

  return (
    <Panel
      title="Endpoint behaviour"
      sub="UBA risk from live telemetry vs. baseline"
      actions={<Pill tone={tone}>{risk == null ? "no score yet" : risk >= 70 ? "high risk" : risk >= 40 ? "elevated" : "nominal"}</Pill>}
    >
      <Gauge value={risk} label="UBA RISK SCORE" />
      <div className="mt-3 border-t border-line pt-3">
        <div className="mb-2 text-2xs uppercase tracking-wide text-muted">Flagged deviations</div>
        {anomalies.length === 0 ? (
          <Empty>No behavioural deviations crossed the baseline yet. Run a session to score live activity.</Empty>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {anomalies.map((a, i) => (
              <li key={i} className="flex items-start gap-2 text-[13px]">
                <span className="mt-0.5 rounded bg-raised px-1.5 py-0.5 font-mono text-2xs capitalize text-muted">{a.category}</span>
                <span className="flex-1 text-ink">{a.message}</span>
                {a.score != null && <span className="font-mono text-2xs text-faint">{(a.score * 100).toFixed(0)}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Panel>
  );
}
