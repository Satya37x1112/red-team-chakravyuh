import { KINDS } from "../lib";
import type { Decision, Kind } from "../types";
import { Button, Icon, Panel, Pill } from "./ui";

const CONFIDENCE: Record<string, "ok" | "warn" | "muted"> = { high: "ok", medium: "warn", low: "muted" };

export function DecisionPanel({
  kind,
  decision,
  loading,
  onRefresh,
}: {
  kind: Kind;
  decision: Decision | null;
  loading?: boolean;
  onRefresh?: () => void;
}) {
  const meta = KINDS[kind];
  const unavailable = !decision || decision.decision === null;
  const heuristic = decision?.status === "heuristic";

  return (
    <Panel
      title={meta.decisionLabel}
      sub={decision?.model ? `reasoned by ${decision.model}` : loading ? "reasoning over latest snapshot…" : "read-and-reason only"}
      actions={
        onRefresh && (
          <Button onClick={onRefresh} disabled={loading} title="Ask the agent again with the latest telemetry">
            <Icon name="refresh" size={13} className={loading ? "animate-spin" : ""} />
            Re-evaluate
          </Button>
        )
      }
    >
      <div className="flex items-end gap-3">
        <span className={`font-mono text-[52px] leading-none ${unavailable ? "text-faint" : "text-ink"}`}>
          {loading ? "··" : unavailable ? "—" : decision!.decision}
        </span>
        <span className="pb-1.5 text-sm text-muted">{meta.decisionUnit}</span>
        <span className="ml-auto pb-1">
          {decision && !loading && (
            unavailable ? (
              <Pill tone="warn">llm unavailable</Pill>
            ) : heuristic ? (
              <Pill tone="warn">heuristic fallback</Pill>
            ) : (
              <Pill tone={CONFIDENCE[decision.confidence] ?? "muted"}>{decision.confidence} confidence</Pill>
            )
          )}
        </span>
      </div>

      <div className="mt-4 border-t border-line pt-3">
        <div className="text-2xs text-muted">Reasoning</div>
        <p className="mt-1 text-[13px] leading-relaxed text-ink">
          {loading
            ? "Asking the model to reason over the latest real telemetry…"
            : decision?.reasoning || "No decision yet."}
        </p>
      </div>

      {!!decision?.observations_used?.length && (
        <div className="mt-3">
          <div className="text-2xs text-muted">Observations cited</div>
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {decision.observations_used.map((o, i) => (
              <li key={i} className="rounded border border-line bg-raised px-1.5 py-0.5 font-mono text-2xs text-muted">
                {o}
              </li>
            ))}
          </ul>
        </div>
      )}

      {unavailable && !loading && decision && (
        <p className="mt-3 rounded border border-line bg-raised px-3 py-2 text-xs text-muted">
          The agent did not invent a number. Check <code className="font-mono">OPENROUTER_API_KEY</code> and the telemetry source.
        </p>
      )}
    </Panel>
  );
}
