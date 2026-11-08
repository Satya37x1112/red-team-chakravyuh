import { useEffect, useState } from "react";
import { api } from "../api";
import { useLiveContext } from "../live-context";
import { Button, Empty, Panel, Pill, SectionLabel, Tag } from "../components/ui";
import type { Telemetry } from "../types";

/**
 * Target Recon — the blackbox (agentless, IP-only) view of the authorized target.
 * Shown in the order the operator asked for: (1) the target IP, (2) which ports
 * are open, (3) the telemetry. Honest throughout: with no blackbox source and no
 * target configured it shows an unavailable state, and host internals (CPU/RAM)
 * are marked "not visible" because an external probe cannot see them.
 */
export function TargetRecon() {
  const { telemetry: live } = useLiveContext();
  const [snap, setSnap] = useState<Telemetry | null>(live);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (live) setSnap(live);
  }, [live]);

  const refresh = async () => {
    setBusy(true);
    try {
      setSnap(await api.telemetry());
    } catch {
      /* keep previous */
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    refresh(); // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const net = snap?.network ?? null;
  const isBlackbox = snap?.source === "blackbox";
  const openPorts = net?.ports.filter((p) => p.open) ?? [];
  const closedPorts = net?.ports.filter((p) => !p.open) ?? [];

  return (
    <div className="flex flex-col gap-4">
      {/* ---------- 1. TARGET IP ---------- */}
      <Panel
        title="Target"
        sub="Agentless probe from Kali — IP only, no credentials, nothing installed on the target."
        actions={
          <Button variant="ghost" onClick={refresh} disabled={busy}>
            {busy ? "Probing…" : "Re-probe"}
          </Button>
        }
      >
        {!snap || !snap.available ? (
          <Empty>
            Telemetry unavailable. Set <code className="font-mono">TELEMETRY_SOURCE=blackbox</code> and{" "}
            <code className="font-mono">BLACKBOX_TARGET=&lt;lab IP&gt;</code> to probe a target.
          </Empty>
        ) : (
          <div className="flex flex-wrap items-center gap-4">
            <div>
              <div className="font-mono text-2xs uppercase tracking-wide text-faint">IP address</div>
              <div className="font-mono text-2xl font-semibold text-ink">
                {net?.target ?? snap.hostname ?? "—"}
              </div>
            </div>
            <div className="flex flex-col gap-1">
              <Pill tone={net?.reachable ? "ok" : "crit"}>
                {net?.reachable ? "REACHABLE" : "NO RESPONSE"}
              </Pill>
              {net?.latency_ms != null && <Tag>latency {net.latency_ms} ms</Tag>}
              {isBlackbox && <Tag>source: blackbox</Tag>}
            </div>
          </div>
        )}
      </Panel>

      {/* ---------- 2. OPEN PORTS ---------- */}
      <Panel title="Open ports" sub="TCP services observed from the network. No credentials used.">
        {!net ? (
          <Empty>No port data — the blackbox probe has not run.</Empty>
        ) : openPorts.length === 0 ? (
          <Empty>No open TCP ports observed among the probed set.</Empty>
        ) : (
          <div className="flex flex-col gap-3">
            {net.complete === false && (
              <div className="rounded border border-warn/40 bg-warn/5 px-3 py-2 text-2xs text-warn">
                Partial probe — only {net.ports_probed}/{net.ports_total} ports were checked within the time
                budget. Unchecked ports are not shown (not assumed closed).
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              {openPorts.map((p) => (
                <span
                  key={p.port}
                  className="inline-flex items-center gap-1.5 rounded border border-ok/40 bg-ok/10 px-2 py-1 font-mono text-xs text-ok"
                >
                  <span className="font-semibold">{p.port}</span>
                  {p.service && <span className="text-2xs text-ok/80">{p.service}</span>}
                  {p.latency_ms != null && <span className="text-2xs text-ok/60">{p.latency_ms}ms</span>}
                </span>
              ))}
            </div>
            {closedPorts.length > 0 && (
              <div className="text-2xs text-faint">
                Also probed (closed/filtered): {closedPorts.map((p) => p.port).join(", ")}
              </div>
            )}
          </div>
        )}
      </Panel>

      {/* ---------- 3. TELEMETRY ---------- */}
      <Panel title="Telemetry" sub="What the probe measured. External view — host internals are not visible.">
        {!snap || !snap.available ? (
          <Empty>No telemetry available.</Empty>
        ) : (
          <div className="flex flex-col gap-3">
            <SectionLabel index="01" label="Network" />
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
              <Tag>reachable: {net?.reachable ? "yes" : "no"}</Tag>
              <Tag>open ports: {net?.open_ports.length ?? 0}</Tag>
              {net?.http_status != null && <Tag>HTTP {net.http_status}</Tag>}
              {net?.http_server && <Tag>Server: {net.http_server}</Tag>}
              {net?.probed_at && <Tag>probed {new Date(net.probed_at).toLocaleTimeString()}</Tag>}
            </div>

            {isBlackbox && (
              <>
                <SectionLabel index="02" label="Host internals" />
                <p className="text-xs text-muted">
                  CPU, memory, processes and OS details are{" "}
                  <span className="text-warn">not visible</span> from an external probe. For inside
                  metrics, use an authorized WinRM/WMI source (credentials required).
                </p>
              </>
            )}

            {!isBlackbox && (
              <>
                <SectionLabel index="02" label="Host metrics" />
                <div className="flex flex-wrap gap-2 text-xs text-muted">
                  <Tag>CPU: {snap.cpu_percent ?? "—"}%</Tag>
                  <Tag>MEM: {snap.memory_percent ?? "—"}%</Tag>
                  <Tag>DISK: {snap.disk_percent ?? "—"}%</Tag>
                  <Tag>procs: {snap.process_count ?? "—"}</Tag>
                  <Tag>OS: {snap.os_name ?? "—"}</Tag>
                </div>
              </>
            )}
          </div>
        )}
      </Panel>
    </div>
  );
}
