import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Button, Empty, Panel, Pill, SectionLabel, Tag } from "../components/ui";
import type { OperationDetail, OperationPlanPreview, OperationStep, OperationSummary } from "../types";
import type { StateTone } from "../lib";

/**
 * Centralized AI Planner (Section 3). The user submits an objective; the backend
 * builds scenario context, the AI planner proposes a bounded ExecutionPlan, the
 * deterministic Safety Gateway authorizes it, and the feedback loop recommends
 * CONTINUE / MODIFY / STOP. Everything here is honest: AI vs fallback vs
 * unavailable are shown distinctly, and measured facts are separated from AI
 * interpretation. "Preview" never executes; "Run" is fail-closed (a disabled
 * module is rejected by the gateway, so nothing runs for real).
 */

function planningTone(status: string): StateTone {
  return status === "ai" ? "ok" : status === "fallback" ? "warn" : "muted";
}
function stateTone(state: string | null): StateTone {
  if (!state) return "muted";
  if (state === "COMPLETED") return "ok";
  if (state === "FAILED" || state === "TIMED_OUT") return "crit";
  if (state === "REJECTED" || state === "CANCELLED") return "warn";
  return "muted";
}
function feedbackTone(action: string | null): StateTone {
  return action === "CONTINUE" ? "ok" : action === "MODIFY" ? "warn" : "muted";
}

function GatewayLine({ d }: { d: OperationStep["gateway_decision"] }) {
  const dec = d as { approved?: boolean; reason?: string; validated_parameters?: Record<string, number> };
  if (!dec || dec.approved === undefined) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
      <Pill tone={dec.approved ? "ok" : "crit"}>{dec.approved ? "GATEWAY APPROVED" : "GATEWAY REJECTED"}</Pill>
      <span className="min-w-0">{dec.reason}</span>
      {dec.validated_parameters &&
        Object.entries(dec.validated_parameters).map(([k, v]) => <Tag key={k}>{k}={v}</Tag>)}
    </div>
  );
}

function StepCard({ step }: { step: OperationStep }) {
  const facts = step.analysis?.measured_facts ?? [];
  const interp = step.analysis?.interpretation;
  const interpSrc = step.analysis?.interpretation_source;
  return (
    <div className="rounded-md border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-2xs text-accent">#{step.index + 1}</span>
        <Pill tone={planningTone(step.plan_source === "ai" ? "ai" : step.plan_source === "system" ? "fallback" : "unavailable")}>
          {step.plan_source === "ai" ? "AI PLAN" : step.plan_source === "system" ? "FALLBACK (NOT AI)" : "NO PLAN"}
        </Pill>
        {step.model && <Tag>{step.model}</Tag>}
        {step.execution_state && <Pill tone={stateTone(step.execution_state)}>{step.execution_state}</Pill>}
        {step.feedback_action && <Pill tone={feedbackTone(step.feedback_action)}>→ {step.feedback_action}</Pill>}
      </div>

      {!step.validation_ok && step.validation_error && (
        <p className="mt-2 text-xs text-muted">{step.validation_error}</p>
      )}

      <div className="mt-2">
        <GatewayLine d={step.gateway_decision} />
      </div>

      {facts.length > 0 && (
        <div className="mt-2">
          <div className="font-mono text-2xs uppercase tracking-wide text-faint">Measured facts (evidence)</div>
          <ul className="mt-1 list-disc pl-4 text-xs text-ink">
            {facts.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </div>
      )}
      {interp && (
        <p className="mt-2 text-xs text-muted">
          <span className="font-mono text-2xs uppercase tracking-wide text-faint">
            Interpretation{interpSrc ? ` · ${interpSrc}` : ""}:
          </span>{" "}
          {interp}
        </p>
      )}
      {step.feedback_reasoning && (
        <p className="mt-1.5 text-xs text-muted">
          <span className="font-mono text-2xs uppercase tracking-wide text-faint">Feedback:</span>{" "}
          {step.feedback_reasoning}
        </p>
      )}
    </div>
  );
}

export function AIPlanner() {
  const [objective, setObjective] = useState("");
  const [moduleHint, setModuleHint] = useState("");
  const [preview, setPreview] = useState<OperationPlanPreview | null>(null);
  const [operation, setOperation] = useState<OperationDetail | null>(null);
  const [ops, setOps] = useState<OperationSummary[]>([]);
  const [busy, setBusy] = useState<"" | "preview" | "run">("");
  const [error, setError] = useState<string | null>(null);

  const refreshOps = useCallback(() => {
    api.listOperations().then(setOps).catch(() => undefined);
  }, []);
  useEffect(() => refreshOps(), [refreshOps]);

  const body = () => ({ objective, module_hint: moduleHint || undefined });

  const doPreview = async () => {
    if (!objective.trim()) return;
    setBusy("preview");
    setError(null);
    setOperation(null);
    try {
      setPreview(await api.operationPlan(body()));
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy("");
    }
  };

  const doRun = async () => {
    if (!objective.trim()) return;
    setBusy("run");
    setError(null);
    setPreview(null);
    try {
      const op = await api.startOperation(body());
      setOperation(op);
      refreshOps();
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy("");
    }
  };

  const openOp = async (id: string) => {
    try {
      setOperation(await api.getOperation(id));
      setPreview(null);
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_260px]">
      <div className="flex flex-col gap-4">
        <Panel
          title="Centralized AI Planner"
          sub="One AI brain: objective → context → plan → Safety Gateway → execution → analysis → feedback. Deterministic safety stays outside the AI."
        >
          <div className="flex flex-col gap-3">
            <textarea
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              placeholder="Describe the authorized-lab objective, e.g. 'test the lab host's SSH login resilience'"
              rows={2}
              className="w-full resize-y rounded border border-line bg-canvas px-3 py-2 text-sm text-ink outline-none placeholder:text-faint focus:border-accent"
            />
            <div className="flex flex-wrap items-center gap-2">
              <input
                value={moduleHint}
                onChange={(e) => setModuleHint(e.target.value)}
                placeholder="module hint (optional): bruteforce | ddos"
                className="h-8 flex-1 rounded border border-line bg-canvas px-2.5 text-xs text-ink outline-none placeholder:text-faint focus:border-accent"
              />
              <Button variant="ghost" onClick={doPreview} disabled={busy !== "" || !objective.trim()}>
                {busy === "preview" ? "Previewing…" : "Preview plan"}
              </Button>
              <Button variant="primary" onClick={doRun} disabled={busy !== "" || !objective.trim()}>
                {busy === "run" ? "Running…" : "Run operation"}
              </Button>
            </div>
            <p className="text-2xs text-faint">
              Preview never executes. Run is fail-closed: a disabled module is rejected by the Safety Gateway, so
              nothing runs for real.
            </p>
            {error && <p className="text-xs text-crit">{error}</p>}
          </div>
        </Panel>

        {preview && (
          <Panel title="Plan preview (dry run — no execution)">
            <div className="flex flex-col gap-3">
              <SectionLabel index="01" label="Planner" />
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                <Pill tone={planningTone(preview.planning_status)}>
                  {preview.planning_status === "ai"
                    ? "AI-GENERATED"
                    : preview.planning_status === "fallback"
                    ? "FALLBACK (NOT AI)"
                    : "UNAVAILABLE"}
                </Pill>
                {preview.model && <Tag>{preview.model}</Tag>}
                <Tag>telemetry: {preview.telemetry_scope}</Tag>
                <Tag>runnable: {preview.runnable_modules.join(", ") || "none"}</Tag>
              </div>
              <p className="text-xs text-muted">{preview.reasoning}</p>
              {preview.plan ? (
                <>
                  <SectionLabel index="02" label="Safety Gateway" />
                  <GatewayLine d={(preview.gateway_decision ?? {}) as OperationStep["gateway_decision"]} />
                </>
              ) : (
                <Empty>No runnable plan — the AI has nothing it can safely propose for this scope.</Empty>
              )}
            </div>
          </Panel>
        )}

        {operation && (
          <Panel
            title={`Operation · ${operation.status}`}
            sub={operation.objective}
            actions={
              <div className="flex items-center gap-2">
                {operation.final_recommendation && (
                  <Pill tone={feedbackTone(operation.final_recommendation)}>{operation.final_recommendation}</Pill>
                )}
                <Tag>{operation.iterations} iteration(s)</Tag>
              </div>
            }
          >
            {operation.steps.length === 0 ? (
              <Empty>No iterations recorded.</Empty>
            ) : (
              <div className="flex flex-col gap-2.5">
                {operation.steps.map((s) => (
                  <StepCard key={s.index} step={s} />
                ))}
              </div>
            )}
          </Panel>
        )}
      </div>

      <Panel title="Recent operations" bodyClass="p-2">
        {ops.length === 0 ? (
          <Empty>None yet.</Empty>
        ) : (
          <ul className="flex flex-col">
            {ops.map((o) => (
              <li key={o.id}>
                <button
                  onClick={() => openOp(o.id)}
                  className="flex w-full flex-col gap-1 rounded px-2 py-2 text-left hover:bg-raised"
                >
                  <span className="flex items-center gap-2">
                    <Pill tone={o.status === "COMPLETED" ? "ok" : o.status === "FAILED" ? "crit" : "muted"} dot={false}>
                      {o.status}
                    </Pill>
                    <span className="font-mono text-2xs text-faint">{o.iterations}×</span>
                  </span>
                  <span className="line-clamp-2 text-xs text-ink">{o.objective}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
