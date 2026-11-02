import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { DecisionPanel } from "../components/DecisionPanel";
import { EventStream } from "../components/EventStream";
import { HostLoadPanel } from "../components/HostLoadPanel";
import { Lifecycle } from "../components/Lifecycle";
import { ModuleResults } from "../components/ModuleResults";
import { TelemetryPanel } from "../components/TelemetryPanel";
import { WordlistPanel } from "../components/WordlistPanel";
import { Button, Icon, Panel, Pill, RiskCells, SectionLabel, Tag } from "../components/ui";
import { useLiveContext } from "../live-context";
import { KINDS } from "../lib";
import type { Decision, Kind } from "../types";

export function Operation({ kind }: { kind: Kind }) {
  const meta = KINDS[kind];
  const { telemetry, events, setActiveSessionId, halted, notify } = useLiveContext();
  const [decision, setDecision] = useState<Decision | null>(null);
  const [decisionLoading, setDecisionLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [label, setLabel] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [analysis, setAnalysis] = useState<Record<string, unknown> | null>(null);

  const loadDecision = useCallback(async () => {
    setDecisionLoading(true);
    try {
      setDecision(await api.decision(kind));
    } catch {
      setDecision(null);
    } finally {
      setDecisionLoading(false);
    }
  }, [kind]);

  useEffect(() => {
    loadDecision();
    setSessionId(null);
    setLabel(null);
    setAnalysis(null);
    setRunning(false);
  }, [kind, loadDecision]);

  const sessionEvents = useMemo(
    () =>
      sessionId
        ? events.filter(
            (e) =>
              e.payload?.session_id === sessionId ||
              (e.type === "KILL_SWITCH_ENGAGED" && (e.payload?.killed as string[] | undefined)?.includes(sessionId))
          )
        : [],
    [events, sessionId]
  );
  const phase = useMemo(() => {
    const ev = sessionEvents.find((e) => e.payload?.phase && e.payload.phase !== "KILLED");
    return (ev?.payload?.phase as string) ?? null;
  }, [sessionEvents]);
  const killed = sessionEvents.some((e) => e.type.startsWith("KILL_SWITCH"));
  const complete = phase === "RESULT" || killed;

  useEffect(() => {
    if (!sessionId || !complete) return;
    setRunning(false);
    setActiveSessionId(null);
    if (killed) return;
    let cancelled = false;
    const t = setTimeout(async () => {
      const r = await api.result(sessionId);
      if (!cancelled) setAnalysis(r);
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [sessionId, complete, killed, setActiveSessionId]);

  const run = async () => {
    setRunning(true);
    setAnalysis(null);
    try {
      const res = await api.start(kind);
      setSessionId(res.session_id);
      setLabel(res.label);
      setActiveSessionId(res.session_id);
      loadDecision();
    } catch (e) {
      setRunning(false);
      notify({ tone: "crit", title: "Session not started", body: (e as Error).message });
    }
  };

  const findings = (analysis?.analysis as { findings?: string[] } | undefined)?.findings ?? [];
  const risk = analysis?.risk_score as number | null | undefined;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-2xl">
          <div className="flex items-center gap-2 font-mono text-2xs text-muted">
            <span className="text-accent">OP {meta.index}</span>
            <Tag>{meta.mitre}</Tag>
            <span>{meta.vector}</span>
          </div>
          <h1 className="mt-1.5 text-[22px] font-semibold tracking-tight text-ink">
            {meta.name} <span className="font-normal text-muted">— {meta.sub}</span>
          </h1>
          <p className="mt-1 text-xs leading-relaxed text-muted">{meta.blurb}</p>
        </div>
        <Button
          variant="primary"
          onClick={run}
          disabled={running || halted}
          title={halted ? "Kill switch engaged — re-arm the range first" : undefined}
        >
          <Icon name="play" size={12} />
          {halted ? "Range halted" : running ? "Session running…" : "Run agent session"}
        </Button>
      </div>

      <Panel
        title="Agent lifecycle"
        sub={label ? `Session ${label}` : "No session started on this page yet"}
        actions={
          sessionId && (
            <Pill tone={killed ? "crit" : phase === "RESULT" ? "ok" : "warn"}>
              {killed ? "killed" : phase === "RESULT" ? "complete" : (phase ?? "starting").toLowerCase()}
            </Pill>
          )
        }
      >
        <Lifecycle current={phase} killed={killed} />
      </Panel>

      <section className="flex flex-col gap-3">
        <SectionLabel index="01" label="Real lab telemetry" hint={telemetry ? `${telemetry.source} collector` : "waiting"} />
        {kind === "bruteforce" ? (
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
            <TelemetryPanel telemetry={telemetry} />
            <WordlistPanel />
          </div>
        ) : (
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
            <HostLoadPanel height={200} />
            <TelemetryPanel telemetry={telemetry} />
          </div>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <SectionLabel index="02" label="Agent decision" hint="read-and-reason · no action taken" />
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
          <DecisionPanel kind={kind} decision={decision} loading={decisionLoading} onRefresh={loadDecision} />
          <Panel title="Session events" sub={sessionId ? `${sessionEvents.length} events for this run` : "Streams here once a session starts"}>
            <EventStream events={sessionEvents} height={260} empty="Run a session to stream its lifecycle here." />
          </Panel>
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <SectionLabel index="03" label="Analysis" hint={complete ? (killed ? "session killed" : "session complete") : "after a session"} />
        {(analysis || killed) && (
          <Panel title={`Latest run · ${label ?? ""}`}>
            {killed ? (
              <p className="text-[13px] text-crit">Session terminated by the kill switch before analysis. No result was recorded.</p>
            ) : (
              <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_180px]">
                <div>
                  <p className="text-[13px] text-ink">{String(analysis?.summary ?? "")}</p>
                  {findings.length > 0 && (
                    <ul className="mt-2 flex flex-col gap-1">
                      {findings.map((f, i) => (
                        <li key={i} className="flex gap-2 text-xs text-muted">
                          <span className="font-mono text-faint">{String(i + 1).padStart(2, "0")}</span>
                          {f}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="border-line md:border-l md:pl-4">
                  <div className="text-2xs text-muted">Risk score</div>
                  <div className="mt-1.5">
                    <RiskCells score={risk ?? null} />
                  </div>
                </div>
              </div>
            )}
          </Panel>
        )}
        <ModuleResults kind={kind} />
      </section>
    </div>
  );
}
