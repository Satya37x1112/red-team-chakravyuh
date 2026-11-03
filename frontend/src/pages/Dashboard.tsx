import { useState } from "react";
import { Link } from "react-router-dom";
import { Gauge } from "../components/charts";
import { EventStream } from "../components/EventStream";
import { HistoryFilter, HistoryTable } from "../components/HistoryTable";
import { HostLoadPanel } from "../components/HostLoadPanel";
import { ModuleCard } from "../components/ModuleResults";
import { ScenarioRadar, RiskScatter } from "../components/analytics-charts";
import { Button, Dot, Icon, Panel, Stat } from "../components/ui";
import { useLiveContext } from "../live-context";
import { KIND_LIST, parseTs, uptime } from "../lib";
import type { AnalyticsRow, Kind, Telemetry } from "../types";

export function downloadReport(telemetry: Telemetry | null, sessions: AnalyticsRow[]) {
  const body = {
    generated_at: new Date().toISOString(),
    target: telemetry && {
      hostname: telemetry.hostname,
      os_name: telemetry.os_name,
      source: telemetry.source,
      collected_at: telemetry.collected_at,
    },
    sessions,
  };
  const url = URL.createObjectURL(new Blob([JSON.stringify(body, null, 2)], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `vajraprahaar-report-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

export function Dashboard() {
  const { telemetry, analytics, events, connected } = useLiveContext();
  const [filter, setFilter] = useState<"all" | Kind>("all");

  const count = (s: string) => analytics.filter((r) => r.state === s).length;
  const done = count("RESULT");
  const killed = count("KILLED");
  const failed = count("FAILED");
  const running = analytics.length - done - killed - failed;
  const finished = done + killed + failed;
  const rate = finished ? (done / finished) * 100 : null;
  const today = new Date().toDateString();
  const todayRuns = analytics.filter((r) => parseTs(r.started_at)?.toDateString() === today).length;
  const risks = analytics.map((r) => r.risk_score).filter((v): v is number => v != null);
  const meanRisk = risks.length ? (risks.reduce((a, b) => a + b, 0) / risks.length) * 100 : null;
  const llmShare = analytics.length
    ? (analytics.filter((r) => r.decision_source === "llm").length / analytics.length) * 100
    : null;

  const context: [string, string | null | undefined][] = [
    ["Target", telemetry?.hostname],
    ["Operating system", telemetry?.os_name],
    ["Operator", telemetry?.logged_in_user],
    ["Collector", telemetry?.source],
    ["Uptime", uptime(telemetry?.uptime_seconds)],
  ];

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 font-mono text-2xs text-muted">
            <Dot tone={running ? "warn" : connected ? "ok" : "crit"} pulse={!!running} />
            {running ? `${running} session running` : connected ? "Range idle · telemetry live" : "Telemetry offline"}
          </div>
          <h1 className="mt-1.5 text-[22px] font-semibold tracking-tight text-ink">Operations overview</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={() => downloadReport(telemetry, analytics)} disabled={!analytics.length}>
            <Icon name="download" size={14} />
            Export report
          </Button>
          <Link
            to="/ddos"
            className="inline-flex h-8 items-center gap-2 rounded border border-accent bg-accent px-3 text-xs font-medium text-white transition-colors hover:bg-accentHover"
          >
            <Icon name="play" size={12} />
            New session
          </Link>
        </div>
      </div>

      <dl className="flex flex-wrap border-y border-line">
        {context.map(([k, v]) => (
          <div key={k} className="min-w-[140px] flex-1 border-r border-line px-4 py-2.5 last:border-r-0">
            <dt className="font-mono text-2xs uppercase tracking-[0.1em] text-faint">{k}</dt>
            <dd className={`mt-1 truncate font-mono text-xs ${v ? "text-ink" : "text-faint"}`}>{v ?? "unavailable"}</dd>
          </div>
        ))}
      </dl>

      <section className="grid grid-cols-2 divide-line overflow-hidden rounded-lg border border-line bg-surface md:grid-cols-5 md:divide-x">
        <Stat label="Sessions run" value={analytics.length} sub={`${todayRuns} today`} />
        <Stat label="Completed" value={done} tone="ok" sub={rate == null ? "no finished runs" : `${rate.toFixed(0)}% of finished`} />
        <Stat label="Killed" value={killed} tone="crit" sub={failed ? `${failed} failed` : "via kill switch"} />
        <Stat label="Mean UBA risk" value={meanRisk == null ? null : meanRisk.toFixed(0)} unit="/100" sub={`${risks.length} scored runs`} />
        <Stat
          label="AI-reasoned plans"
          value={llmShare == null ? null : llmShare.toFixed(0)}
          unit="%"
          sub="decisions from the model"
        />
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <HostLoadPanel />
        <Panel title="Attack success rate" sub="Sessions that reached RESULT vs. killed or failed">
          <div className="flex h-full flex-col">
            <div className="flex flex-1 items-center py-2">
              <Gauge value={rate} label="objectives reached" />
            </div>
            <div className="grid grid-cols-3 border-t border-line pt-3">
              {(
                [
                  ["Succeeded", done, "ok"],
                  ["Killed", killed, "crit"],
                  ["Failed", failed, "muted"],
                ] as const
              ).map(([k, v, tone]) => (
                <div key={k} className="border-r border-line px-3 first:pl-0 last:border-r-0">
                  <div className="flex items-center gap-1.5 text-2xs text-muted">
                    <Dot tone={tone} />
                    {k}
                  </div>
                  <div className="mt-1 font-mono text-base text-ink">{v}</div>
                </div>
              ))}
            </div>
          </div>
        </Panel>
      </div>

      <section>
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-[13px] font-semibold text-ink">Results by scenario</h2>
          <span className="font-mono text-2xs text-faint">bars = one run each · hover for detail</span>
        </div>
        <div className="grid gap-5 md:grid-cols-3">
          {KIND_LIST.map((k) => (
            <ModuleCard key={k.kind} kind={k.kind} />
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-[13px] font-semibold text-ink">Operational analytics</h2>
        <div className="grid gap-5 md:grid-cols-2">
          <ScenarioRadar analytics={analytics} />
          <RiskScatter analytics={analytics} />
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <Panel
          title="Execution history"
          sub="Persisted sessions · click a row for its event log"
          actions={<HistoryFilter value={filter} onChange={setFilter} />}
          bodyClass="pt-3"
        >
          <HistoryTable rows={analytics} filter={filter} limit={8} />
          <div className="border-t border-line px-4 py-2.5 text-right">
            <Link to="/history" className="text-xs text-muted hover:text-ink">
              View all {analytics.length} sessions →
            </Link>
          </div>
        </Panel>
        <Panel title="Agent console" sub="Live lifecycle events over WebSocket" actions={<span className="font-mono text-2xs text-faint">{events.length} events</span>}>
          <EventStream events={events} height={330} empty="No agent activity in this browser session yet." />
        </Panel>
      </div>
    </div>
  );
}
