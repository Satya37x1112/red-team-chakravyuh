import { Dot, Panel, Tag } from "../components/ui";
import { useLiveContext } from "../live-context";

export function Range() {
  const { telemetry, connected, halted } = useLiveContext();
  const nodes = [
    {
      name: "CHAKRAVYUH AGENT",
      role: "controller",
      sub: "Orchestrator · decision engine · telemetry poller",
      addr: location.host,
      up: connected,
      status: connected ? "socket live" : "socket down",
    },
    {
      name: (telemetry?.hostname ?? "LAB-TARGET").toUpperCase(),
      role: "target",
      sub: telemetry?.os_name ?? "Target OS unavailable",
      addr: telemetry?.source === "winrm" ? "WinRM endpoint" : telemetry?.source ?? "—",
      up: !!telemetry?.available,
      status: telemetry?.available ? "reporting" : "no telemetry",
    },
  ];
  const ifaces = telemetry?.interfaces ?? [];

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight text-ink">Cyber range</h1>
        <p className="mt-1 text-xs text-muted">Only what the collector can actually see. Nothing here is drawn from a template.</p>
      </div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <Panel title="Range topology" sub={`${nodes.filter((n) => n.up).length}/${nodes.length} nodes up · host-only network`}>
          <ol className="relative flex flex-col gap-5 pl-6">
            <span className="absolute bottom-3 left-[5px] top-3 border-l border-dashed border-lineStrong" />
            {nodes.map((n) => (
              <li key={n.role} className="relative flex items-start justify-between gap-4">
                <span
                  className={`absolute -left-6 top-1 h-[11px] w-[11px] rounded-full border-2 ${
                    n.role === "controller" ? "border-accent bg-accent" : n.up ? "border-ok bg-surface" : "border-faint bg-surface"
                  }`}
                />
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-medium text-ink">{n.name}</span>
                    <Tag>{n.role}</Tag>
                  </div>
                  <div className="mt-0.5 text-2xs text-muted">{n.sub}</div>
                </div>
                <div className="shrink-0 text-right font-mono text-2xs">
                  <div className="text-ink">{n.addr}</div>
                  <div className={n.up ? "text-ok" : "text-faint"}>{n.status}</div>
                </div>
              </li>
            ))}
          </ol>
          <div className="mt-5 grid grid-cols-2 gap-4 border-t border-line pt-3">
            <div>
              <div className="text-2xs text-muted">Range state</div>
              <div className={`mt-0.5 flex items-center gap-1.5 font-mono text-xs ${halted ? "text-crit" : "text-ok"}`}>
                <Dot tone={halted ? "crit" : "ok"} />
                {halted ? "halted" : "armed"}
              </div>
            </div>
            <div>
              <div className="text-2xs text-muted">Execution adapters</div>
              <div className="mt-0.5 font-mono text-xs text-ink">stubbed · none wired</div>
            </div>
          </div>
        </Panel>

        <Panel title="Target interfaces" sub="Reported by the collector" bodyClass="pt-3">
          {ifaces.length === 0 ? (
            <p className="px-4 pb-4 text-xs text-muted">No interface data in the latest snapshot.</p>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="border-y border-line text-left font-mono text-2xs uppercase tracking-wider text-faint">
                  <th className="px-4 py-2 font-medium">Interface</th>
                  <th className="px-3 py-2 font-medium">Addresses</th>
                  <th className="px-3 py-2 font-medium">State</th>
                </tr>
              </thead>
              <tbody>
                {ifaces.map((i) => (
                  <tr key={i.name} className="border-b border-line last:border-0">
                    <td className="px-4 py-2 font-mono text-ink">{i.name}</td>
                    <td className="px-3 py-2 font-mono text-muted">{i.addresses.join(", ") || "—"}</td>
                    <td className="px-3 py-2">
                      <span className="inline-flex items-center gap-1.5 font-mono text-2xs text-muted">
                        <Dot tone={i.is_up ? "ok" : i.is_up === false ? "muted" : "warn"} />
                        {i.is_up ? "up" : i.is_up === false ? "down" : "unknown"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </div>
  );
}
