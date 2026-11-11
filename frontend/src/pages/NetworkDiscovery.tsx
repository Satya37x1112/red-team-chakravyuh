import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { Button, Empty, Icon, Panel, Pill, SectionLabel, Tag } from "../components/ui";
import { useLiveContext } from "../live-context";
import type { DiscoveredHost, DiscoveryScanStatus, NetworkIface, NetworkSubnet, TailnetStatus } from "../types";

export function NetworkDiscovery() {
  const navigate = useNavigate();
  const { notify, halted } = useLiveContext();

  // Network topology state
  const [interfaces, setInterfaces] = useState<NetworkIface[]>([]);
  const [subnets, setSubnets] = useState<NetworkSubnet[]>([]);
  const [tailnet, setTailnet] = useState<TailnetStatus | null>(null);
  const [targets, setTargets] = useState<DiscoveredHost[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Lab subnet discovery form
  const [enableLabSubnet, setEnableLabSubnet] = useState(false);
  const [labSubnetCidr, setLabSubnetCidr] = useState("192.168.100.0/24");
  const [maxHosts, setMaxHosts] = useState(32);
  const [timeoutSec, setTimeoutSec] = useState(0.5);

  // Active scan state
  const [activeScan, setActiveScan] = useState<DiscoveryScanStatus | null>(null);

  // Manual target entry
  const [manualIp, setManualIp] = useState("");
  const [manualHostname, setManualHostname] = useState("");
  const [manualBusy, setManualBusy] = useState(false);
  const [manualResult, setManualResult] = useState<{ ok: boolean; msg: string } | null>(null);

  const selectedTarget = targets.find((t) => t.selected);

  // 1. Refresh topology and inventory
  const refreshAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ifaces, subs, tnet, tgts] = await Promise.all([
        api.networkInterfaces().catch(() => []),
        api.networkSubnets().catch(() => []),
        api.networkTailnet().catch(() => null),
        api.networkTargets().catch(() => []),
      ]);
      setInterfaces(ifaces);
      setSubnets(subs);
      setTailnet(tnet);
      setTargets(tgts);
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  // 2. Poll active discovery scan progress
  useEffect(() => {
    if (!activeScan || activeScan.state !== "RUNNING") return;
    const timer = setInterval(async () => {
      try {
        const status = await api.networkDiscoveryStatus(activeScan.scan_id);
        setActiveScan(status);
        if (status.state !== "RUNNING") {
          clearInterval(timer);
          // Refresh targets when scan finishes
          api.networkTargets().then(setTargets).catch(() => undefined);
          notify({
            tone: status.state === "COMPLETED" ? "ok" : "crit",
            title: `Discovery ${status.state}`,
            body: `Discovered ${status.found_count} reachable hosts.`,
          });
        }
      } catch {
        clearInterval(timer);
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [activeScan, notify]);

  // 3. Start discovery scan
  const startScan = async (mode: "tailnet" | "lab_subnet") => {
    if (halted) {
      notify({ tone: "crit", title: "Kill switch is engaged", body: "Network scans cannot be started." });
      return;
    }
    setError(null);
    try {
      const scan = await api.networkDiscoveryStart({
        mode,
        subnet: mode === "lab_subnet" ? labSubnetCidr.trim() : undefined,
        enable_lab_subnet: mode === "lab_subnet" ? enableLabSubnet : false,
        max_hosts: maxHosts,
        timeout: timeoutSec,
      });
      setActiveScan(scan);
      notify({
        tone: "ok",
        title: "Discovery scan started",
        body: `Running in mode: ${mode} (${scan.total_hosts} targets)`,
      });
    } catch (e) {
      const msg = String((e as Error).message);
      setError(msg);
      notify({ tone: "crit", title: "Scan refused", body: msg });
    }
  };

  // 4. Cancel active scan
  const cancelScan = async () => {
    if (!activeScan) return;
    try {
      await api.networkDiscoveryCancel(activeScan.scan_id);
      setActiveScan((prev) => (prev ? { ...prev, state: "CANCELLED" } : null));
      notify({ tone: "crit", title: "Scan cancelled", body: "Discovery stopped by operator." });
    } catch (e) {
      notify({ tone: "crit", title: "Cancel failed", body: String((e as Error).message) });
    }
  };

  // 5. Explicit target selection & authorization
  const selectTarget = async (ip: string, hostname?: string) => {
    try {
      const res = await api.networkSelectTarget({ ip, hostname });
      notify({
        tone: "ok",
        title: "Target Authorized & Selected",
        body: `${ip} (${res.target.hostname}) is now the active assessment target.`,
      });
      // Refresh target inventory
      const updated = await api.networkTargets();
      setTargets(updated);
    } catch (e) {
      const msg = String((e as Error).message);
      notify({ tone: "crit", title: "Authorization Refused", body: msg });
    }
  };

  // 6. Manual target submission
  const submitManualTarget = async () => {
    const ip = manualIp.trim();
    if (!ip) return;
    setManualBusy(true);
    setManualResult(null);
    try {
      const res = await api.networkSelectTarget({ ip, hostname: manualHostname.trim() || undefined });
      setManualResult({ ok: true, msg: `Authorized: ${res.message}` });
      setManualIp("");
      setManualHostname("");
      const updated = await api.networkTargets();
      setTargets(updated);
      notify({ tone: "ok", title: "Manual Target Authorized", body: `${ip} selected as active target.` });
    } catch (e) {
      const msg = String((e as Error).message);
      setManualResult({ ok: false, msg });
      notify({ tone: "crit", title: "Authorization Refused", body: msg });
    } finally {
      setManualBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      {/* ---------- HEADER & SELECTED TARGET BANNER ---------- */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-ink">Network Discovery & Target Selection</h1>
          <p className="mt-1 text-sm text-muted">
            Enumerate interfaces, discover tailnet peer devices, safely probe authorized lab subnets, and select targets.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={refreshAll} disabled={loading}>
            <Icon name="refresh" className={loading ? "animate-spin" : ""} /> Refresh Topology
          </Button>
          {selectedTarget && (
            <Button
              variant="primary"
              onClick={() => navigate(`/?target=${encodeURIComponent(selectedTarget.ip)}`)}
            >
              Run Assessment on {selectedTarget.ip} →
            </Button>
          )}
        </div>
      </div>

      {/* Active Selected Target Notice */}
      {selectedTarget ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-ok/40 bg-ok/10 px-4 py-3 text-sm">
          <div className="flex items-center gap-2 text-ink">
            <span className="h-2.5 w-2.5 rounded-full bg-ok animate-pulse" />
            <span className="font-semibold">ACTIVE TARGET:</span>
            <span className="font-mono font-bold text-accent">{selectedTarget.ip}</span>
            {selectedTarget.hostname && (
              <span className="text-muted">({selectedTarget.hostname})</span>
            )}
            <Pill tone="ok">Authorized Lab Target</Pill>
            <Tag>Source: {selectedTarget.discovery_source}</Tag>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted">
              {selectedTarget.detected_ports.length > 0
                ? `Open ports: ${selectedTarget.detected_ports.join(", ")}`
                : "No ports probed yet"}
            </span>
            <Button
              variant="ghost"
              onClick={() => navigate(`/?target=${encodeURIComponent(selectedTarget.ip)}`)}
            >
              Open in Dashboard
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-between rounded-lg border border-warn/40 bg-warn/10 px-4 py-2.5 text-xs text-ink">
          <div className="flex items-center gap-2">
            <Icon name="alert" className="text-warn" />
            <span>No target currently selected. Select an authorized peer or enter an RFC1918 lab IP below.</span>
          </div>
        </div>
      )}

      {error && (
        <div className="rounded border border-crit/40 bg-crit/10 px-3.5 py-2.5 text-xs text-crit">
          <span className="font-semibold">Discovery Policy Refusal:</span> {error}
        </div>
      )}

      {/* ---------- 1. INTERFACES & SCOPE CLASSIFICATION ---------- */}
      <Panel
        title="Active Network Interfaces & Scope Classification"
        sub={`Discovered ${interfaces.length} interface(s) and ${subnets.length} subnet(s). Hotspot network (10.81.189.0/24) and loopback are strictly prohibited.`}
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {interfaces.map((iface) => {
            const isTailnet = iface.category === "tailnet";
            const isDisallowed = iface.category.includes("disallowed") || iface.category === "loopback";
            return (
              <div
                key={iface.interface}
                className={`rounded border p-3 flex flex-col justify-between ${
                  isTailnet
                    ? "border-accent/40 bg-accent/5"
                    : isDisallowed
                    ? "border-crit/30 bg-crit/5 opacity-80"
                    : "border-line bg-surface"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-sm font-bold text-ink">{iface.interface}</span>
                    <Pill
                      tone={
                        iface.category === "tailnet"
                          ? "ok"
                          : iface.category === "hotspot_disallowed"
                          ? "crit"
                          : iface.category === "loopback"
                          ? "muted"
                          : "warn"
                      }
                    >
                      {iface.category}
                    </Pill>
                  </div>
                  <div className="mt-2 font-mono text-xs text-ink">{iface.ip}</div>
                  <div className="font-mono text-2xs text-muted">Subnet: {iface.cidr}</div>
                </div>
                <div className="mt-3 pt-2 border-t border-line/60 text-2xs text-muted">
                  {iface.authorized_for_discovery ? (
                    <span className="text-ok font-semibold">✓ Authorized for discovery</span>
                  ) : (
                    <span className="text-crit font-medium">✕ {iface.rejection_reason}</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Panel>

      {/* ---------- 2. TAILNET PEER DISCOVERY (DEFAULT SCOPE) ---------- */}
      <Panel
        title="Tailnet Peer Discovery (Default Scope)"
        sub="Enumerates known nodes on the Tailscale mesh network. Reachability is actively verified via non-destructive probes."
      >
        {tailnet?.available ? (
          <div className="flex flex-col gap-4">
            {/* Self Node Banner */}
            <div className="flex flex-wrap items-center justify-between rounded border border-line bg-canvas px-3 py-2 text-xs">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-muted">Operator Host (Self):</span>
                <span className="font-mono font-bold text-ink">{tailnet.self.hostname}</span>
                <span className="font-mono text-accent">({tailnet.self.tailscale_ip})</span>
                <Tag>{tailnet.self.os}</Tag>
              </div>
              <Button
                variant="ghost"
                onClick={() => startScan("tailnet")}
                disabled={activeScan?.state === "RUNNING"}
              >
                <Icon name="pulse" /> Scan Tailnet Peers
              </Button>
            </div>

            {/* Peers Grid */}
            <div className="overflow-x-auto rounded border border-line">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-line bg-canvas font-mono text-faint uppercase">
                  <tr>
                    <th className="px-3 py-2">Peer Node</th>
                    <th className="px-3 py-2">Tailscale IP</th>
                    <th className="px-3 py-2">OS</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Authorization</th>
                    <th className="px-3 py-2 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line bg-surface">
                  {tailnet.peers.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-3 py-4 text-center text-muted">
                        No tailnet peers found.
                      </td>
                    </tr>
                  ) : (
                    tailnet.peers.map((peer) => {
                      const isSelected = selectedTarget?.ip === peer.ip;
                      return (
                        <tr key={peer.ip} className={isSelected ? "bg-accent/10" : ""}>
                          <td className="px-3 py-2.5 font-medium text-ink">
                            <div className="flex items-center gap-1.5">
                              <span
                                className={`h-2 w-2 rounded-full ${
                                  peer.online ? "bg-ok" : "bg-faint"
                                }`}
                              />
                              <span>{peer.hostname}</span>
                            </div>
                            <div className="font-mono text-2xs text-muted">{peer.dns_name}</div>
                          </td>
                          <td className="px-3 py-2.5 font-mono text-ink">{peer.ip}</td>
                          <td className="px-3 py-2.5">
                            <Tag>{peer.os}</Tag>
                          </td>
                          <td className="px-3 py-2.5">
                            <Pill tone={peer.online ? "ok" : "muted"}>
                              {peer.online ? "Online" : "Offline"}
                            </Pill>
                          </td>
                          <td className="px-3 py-2.5">
                            {isSelected ? (
                              <Pill tone="ok">Selected & Authorized</Pill>
                            ) : (
                              <Pill tone="warn">Pending Selection</Pill>
                            )}
                          </td>
                          <td className="px-3 py-2.5 text-right">
                            <Button
                              variant={isSelected ? "ghost" : "primary"}
                              onClick={() => selectTarget(peer.ip, peer.hostname)}
                              disabled={isSelected}
                            >
                              {isSelected ? "Selected ✓" : "Select Target"}
                            </Button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <Empty>{tailnet?.error ?? "Tailscale service is unavailable on this operator workstation."}</Empty>
        )}
      </Panel>

      {/* ---------- 3. DEDICATED LAB-SUBNET DISCOVERY (OPTIONAL) ---------- */}
      <Panel
        title="Dedicated Lab-Subnet Discovery (Optional)"
        sub="Disabled by default. Bounded TCP-connect discovery strictly limited to explicitly authorized RFC1918 lab subnets."
      >
        <div className="flex flex-col gap-3">
          <label className="flex items-center gap-2.5 text-xs text-ink cursor-pointer select-none">
            <input
              type="checkbox"
              checked={enableLabSubnet}
              onChange={(e) => setEnableLabSubnet(e.target.checked)}
              className="h-4 w-4 rounded border-line text-accent focus:ring-accent"
            />
            <span className="font-semibold">
              Enable Dedicated Lab Subnet Discovery (I confirm explicit authorization for this subnet)
            </span>
          </label>

          {enableLabSubnet && (
            <div className="flex flex-col gap-3 rounded border border-warn/40 bg-warn/5 p-3.5 mt-1">
              <div className="text-2xs text-warn flex items-center gap-1.5 font-medium">
                <Icon name="alert" size={14} />
                <span>
                  Safety Enforcement: Scans are bounded to max 64 hosts and permitted ports (22, 80, 443, 445, 3389, 8080).
                  Public IPs and shared hotspot (10.81.189.0/24) fail closed.
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <SectionLabel index="01" label="Lab Subnet CIDR (max /24)" />
                  <input
                    type="text"
                    value={labSubnetCidr}
                    onChange={(e) => setLabSubnetCidr(e.target.value)}
                    placeholder="e.g. 192.168.100.0/24"
                    className="mt-1 h-8 w-full rounded border border-line bg-canvas px-2.5 font-mono text-xs text-ink focus:border-accent"
                  />
                </div>
                <div>
                  <SectionLabel index="02" label="Max Host Limit (clamped ≤ 64)" />
                  <input
                    type="number"
                    min={1}
                    max={64}
                    value={maxHosts}
                    onChange={(e) => setMaxHosts(parseInt(e.target.value) || 32)}
                    className="mt-1 h-8 w-full rounded border border-line bg-canvas px-2.5 font-mono text-xs text-ink focus:border-accent"
                  />
                </div>
                <div>
                  <SectionLabel index="03" label="Connect Timeout (sec)" />
                  <input
                    type="number"
                    step={0.1}
                    min={0.2}
                    max={2.0}
                    value={timeoutSec}
                    onChange={(e) => setTimeoutSec(parseFloat(e.target.value) || 0.5)}
                    className="mt-1 h-8 w-full rounded border border-line bg-canvas px-2.5 font-mono text-xs text-ink focus:border-accent"
                  />
                </div>
              </div>
              <div className="flex justify-end mt-1">
                <Button
                  variant="primary"
                  onClick={() => startScan("lab_subnet")}
                  disabled={activeScan?.state === "RUNNING"}
                >
                  <Icon name="network" /> Start Lab Subnet Sweep
                </Button>
              </div>
            </div>
          )}
        </div>
      </Panel>

      {/* ---------- 4. ACTIVE SCAN PROGRESS BAR ---------- */}
      {activeScan && (
        <Panel
          title={`Discovery Scan [${activeScan.mode.toUpperCase()}]`}
          sub={`Scan ID: ${activeScan.scan_id} | Execution Record: ${activeScan.execution_id ?? "registered"}`}
        >
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <Pill
                  tone={
                    activeScan.state === "RUNNING"
                      ? "warn"
                      : activeScan.state === "COMPLETED"
                      ? "ok"
                      : "crit"
                  }
                >
                  {activeScan.state}
                </Pill>
                <span className="text-muted">
                  Scanned {activeScan.scanned_hosts} of {activeScan.total_hosts} targets
                </span>
                {activeScan.current_host && activeScan.state === "RUNNING" && (
                  <span className="font-mono text-2xs text-accent">
                    Probing: {activeScan.current_host}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 font-mono text-xs">
                <span>{activeScan.progress_percent}%</span>
                {activeScan.state === "RUNNING" && (
                  <Button variant="danger" onClick={cancelScan}>
                    Cancel Scan
                  </Button>
                )}
              </div>
            </div>

            {/* Progress bar */}
            <div className="h-2 w-full overflow-hidden rounded-full bg-raised">
              <div
                className={`h-full transition-all duration-300 ${
                  activeScan.state === "RUNNING"
                    ? "bg-accent"
                    : activeScan.state === "COMPLETED"
                    ? "bg-ok"
                    : "bg-crit"
                }`}
                style={{ width: `${activeScan.progress_percent}%` }}
              />
            </div>
          </div>
        </Panel>
      )}

      {/* ---------- 5. TARGET INVENTORY & DISCOVERED HOSTS ---------- */}
      <Panel
        title="Discovered Target Inventory"
        sub="Targets discovered via Tailnet or Lab sweeps. Note: Discovered hosts are not authorized until explicitly selected."
      >
        <div className="overflow-x-auto rounded border border-line">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-line bg-canvas font-mono text-faint uppercase">
              <tr>
                <th className="px-3 py-2">Host / IP</th>
                <th className="px-3 py-2">Source</th>
                <th className="px-3 py-2">Reachability</th>
                <th className="px-3 py-2">Open Ports & Services</th>
                <th className="px-3 py-2">Authorization Status</th>
                <th className="px-3 py-2 text-right">Target Selection</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-surface">
              {targets.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-3 py-5 text-center text-muted">
                    No targets discovered yet. Run a Tailnet scan or add an authorized IP manually below.
                  </td>
                </tr>
              ) : (
                targets.map((tgt) => {
                  const isSelected = tgt.selected;
                  return (
                    <tr key={tgt.ip} className={isSelected ? "bg-accent/10" : ""}>
                      <td className="px-3 py-2.5">
                        <div className="font-mono font-bold text-ink">{tgt.ip}</div>
                        {tgt.hostname && tgt.hostname !== tgt.ip && (
                          <div className="text-2xs text-muted">{tgt.hostname}</div>
                        )}
                      </td>
                      <td className="px-3 py-2.5">
                        <Tag>{tgt.discovery_source}</Tag>
                      </td>
                      <td className="px-3 py-2.5">
                        <Pill
                          tone={
                            tgt.reachability_status === "reachable"
                              ? "ok"
                              : tgt.reachability_status === "unreachable"
                              ? "muted"
                              : "warn"
                          }
                        >
                          {tgt.reachability_status}
                        </Pill>
                      </td>
                      <td className="px-3 py-2.5">
                        {tgt.detected_ports.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {tgt.detected_ports.map((p) => {
                              const svc = tgt.services?.find((s) => s.port === p)?.service;
                              return (
                                <Tag key={p}>
                                  {p} {svc ? `(${svc})` : ""}
                                </Tag>
                              );
                            })}
                          </div>
                        ) : (
                          <span className="text-2xs text-faint">None detected</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5">
                        <Pill
                          tone={
                            tgt.authorization_status === "authorized"
                              ? "ok"
                              : tgt.authorization_status === "unauthorized"
                              ? "crit"
                              : "warn"
                          }
                        >
                          {tgt.authorization_status}
                        </Pill>
                        {tgt.authorization_reason && (
                          <div className="mt-0.5 text-3xs text-muted max-w-[200px] truncate" title={tgt.authorization_reason}>
                            {tgt.authorization_reason}
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <Button
                          variant={isSelected ? "ghost" : "primary"}
                          onClick={() => selectTarget(tgt.ip, tgt.hostname)}
                          disabled={isSelected}
                        >
                          {isSelected ? "Active Target ✓" : "Select Target"}
                        </Button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Panel>

      {/* ---------- 6. MANUAL TARGET AUTHORIZATION ENTRY ---------- */}
      <Panel
        title="Manual Target Authorization"
        sub="Manually register an authorized target. Undergoes the identical fail-closed authorization checks (RFC1918 or current Tailnet peer required; public IPs refused)."
      >
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="text"
              value={manualIp}
              onChange={(e) => setManualIp(e.target.value)}
              placeholder="Target IPv4 literal (e.g. 100.84.184.33 or 192.168.1.100)"
              className="h-8 w-72 rounded border border-line bg-canvas px-3 font-mono text-xs text-ink focus:border-accent"
              onKeyDown={(e) => {
                if (e.key === "Enter") submitManualTarget();
              }}
            />
            <input
              type="text"
              value={manualHostname}
              onChange={(e) => setManualHostname(e.target.value)}
              placeholder="Optional Hostname (e.g. Windows-Lab-Target)"
              className="h-8 w-56 rounded border border-line bg-canvas px-3 font-mono text-xs text-ink focus:border-accent"
              onKeyDown={(e) => {
                if (e.key === "Enter") submitManualTarget();
              }}
            />
            <Button
              variant="primary"
              onClick={submitManualTarget}
              disabled={manualBusy || !manualIp.trim()}
            >
              {manualBusy ? "Validating..." : "Authorize & Select Target"}
            </Button>
          </div>

          {manualResult && (
            <div
              className={`rounded px-3 py-2 text-xs ${
                manualResult.ok
                  ? "border border-ok/40 bg-ok/10 text-ok"
                  : "border border-crit/40 bg-crit/10 text-crit"
              }`}
            >
              {manualResult.ok ? "✓ " : "✕ "}
              {manualResult.msg}
            </div>
          )}
        </div>
      </Panel>
    </div>
  );
}
