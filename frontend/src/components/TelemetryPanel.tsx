import { uptime } from "../lib";
import type { Telemetry } from "../types";
import { Meter, Panel, Pill } from "./ui";

function TelemetryFacts({ telemetry }: { telemetry: Telemetry | null }) {
  const facts: [string, string | number | null | undefined][] = [
    ["Hostname", telemetry?.hostname],
    ["Operating system", telemetry?.os_name],
    ["Logged-in user", telemetry?.logged_in_user],
    ["Uptime", uptime(telemetry?.uptime_seconds)],
    ["Processes", telemetry?.process_count],
    ["Interfaces", telemetry?.interfaces?.length],
  ];
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
      {facts.map(([k, v]) => (
        <div key={k} className="min-w-0">
          <dt className="text-2xs text-muted">{k}</dt>
          <dd className={`mt-0.5 truncate font-mono text-xs ${v == null ? "text-faint" : "text-ink"}`} title={v == null ? undefined : String(v)}>
            {v ?? "unavailable"}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function TelemetryPanel({ telemetry }: { telemetry: Telemetry | null }) {
  return (
    <Panel
      title="Target state"
      sub={telemetry ? `via ${telemetry.source} collector` : "waiting for first poll"}
      actions={
        <Pill tone={telemetry?.available ? "ok" : "warn"}>{telemetry?.available ? "reporting" : "unavailable"}</Pill>
      }
    >
      {telemetry && !telemetry.available && (
        <p className="mb-3 rounded border border-warn/30 bg-warn/10 px-3 py-2 text-xs text-warn">
          No real telemetry: {telemetry.error ?? "source not configured"}. Nothing is fabricated.
        </p>
      )}
      <TelemetryFacts telemetry={telemetry} />
      <div className="mt-4 grid gap-4 border-t border-line pt-4 sm:grid-cols-3">
        {(
          [
            ["CPU", telemetry?.cpu_percent],
            ["Memory", telemetry?.memory_percent],
            ["Disk", telemetry?.disk_percent],
          ] as const
        ).map(([label, pct]) => (
          <div key={label}>
            <div className="mb-1.5 flex items-baseline justify-between">
              <span className="text-2xs text-muted">{label}</span>
              <span className="font-mono text-xs text-ink">{pct == null ? <span className="text-faint">n/a</span> : `${pct}%`}</span>
            </div>
            <Meter percent={pct ?? null} />
          </div>
        ))}
      </div>
      {!!telemetry?.processes?.length && (
        <div className="mt-4 border-t border-line pt-3">
          <div className="mb-1.5 text-2xs text-muted">Top processes by memory</div>
          <table className="w-full font-mono text-[11.5px]">
            <tbody>
              {telemetry.processes.slice(0, 5).map((p) => (
                <tr key={p.pid} className="border-b border-line/70 last:border-0">
                  <td className="w-16 py-1 text-faint">{p.pid}</td>
                  <td className="truncate py-1 text-ink">{p.name}</td>
                  <td className="py-1 text-right text-muted">{p.memory_mb != null ? `${p.memory_mb} MB` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
