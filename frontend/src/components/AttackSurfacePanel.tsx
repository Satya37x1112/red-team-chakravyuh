import { useMemo } from "react";
import { useLiveContext } from "../live-context";
import { Empty, Panel, Pill, Tag } from "./ui";

const SERVICES: Record<number, string> = {
  21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP", 110: "POP3",
  139: "NetBIOS", 143: "IMAP", 161: "SNMP", 389: "LDAP", 443: "HTTPS", 445: "SMB",
  631: "IPP", 3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 5900: "VNC", 6379: "Redis",
  8080: "HTTP-alt", 8443: "HTTPS-alt", 27017: "MongoDB",
};

function parseAddr(laddr: string | null): { host: string; port: number } | null {
  if (!laddr) return null;
  const i = laddr.lastIndexOf(":");
  if (i < 0) return null;
  const port = Number(laddr.slice(i + 1));
  if (!Number.isFinite(port)) return null;
  return { host: laddr.slice(0, i), port };
}
const isExternal = (h: string) => h === "0.0.0.0" || h === "::" || h === "*";
const isLoopback = (h: string) => h === "127.0.0.1" || h === "::1" || h.startsWith("127.");

export function AttackSurfacePanel() {
  const { telemetry } = useLiveContext();

  const surface = useMemo(() => {
    const conns = telemetry?.connections ?? [];
    const listen = conns.filter((c) => c.status === "LISTEN").map((c) => parseAddr(c.laddr)).filter(Boolean) as { host: string; port: number }[];
    const seen = new Set<number>();
    const ports = listen.filter((l) => (seen.has(l.port) ? false : seen.add(l.port)));
    const external = ports.filter((l) => isExternal(l.host)).sort((a, b) => a.port - b.port);
    const loopback = ports.filter((l) => isLoopback(l.host)).length;
    const established = conns.filter((c) => c.status === "ESTABLISHED").length;
    const addrs = (telemetry?.interfaces ?? [])
      .flatMap((i) => i.addresses)
      .filter((a) => /^\d+\.\d+\.\d+\.\d+$/.test(a) && !a.startsWith("127."));
    return { external, loopbackCount: loopback, established, addrs, total: ports.length };
  }, [telemetry]);

  if (!telemetry?.available)
    return (
      <Panel title="Attack surface" sub="Exposed services & reachable addresses" actions={<Tag>recon</Tag>}>
        <Empty>Telemetry unavailable — no surface to enumerate.</Empty>
      </Panel>
    );

  return (
    <Panel title="Attack surface" sub="Exposed services & reachable addresses (read-only enumeration)" actions={<Tag>recon</Tag>}>
      <div className="grid grid-cols-3 gap-3 border-b border-line pb-3">
        <div>
          <div className="text-2xs text-muted">Externally bound</div>
          <div className="mt-0.5 font-mono text-lg text-ink">{surface.external.length}</div>
        </div>
        <div>
          <div className="text-2xs text-muted">Loopback-only</div>
          <div className="mt-0.5 font-mono text-lg text-ink">{surface.loopbackCount}</div>
        </div>
        <div>
          <div className="text-2xs text-muted">Live connections</div>
          <div className="mt-0.5 font-mono text-lg text-ink">{surface.established}</div>
        </div>
      </div>

      <div className="mt-3">
        <div className="mb-1.5 text-2xs uppercase tracking-wide text-muted">Reachable addresses</div>
        <div className="flex flex-wrap gap-1.5">
          {surface.addrs.length ? (
            surface.addrs.map((a) => (
              <span key={a} className="rounded border border-line bg-raised px-1.5 py-0.5 font-mono text-2xs text-ink">{a}</span>
            ))
          ) : (
            <span className="text-xs text-muted">none outside loopback</span>
          )}
        </div>
      </div>

      <div className="mt-3">
        <div className="mb-1.5 flex items-center justify-between">
          <span className="text-2xs uppercase tracking-wide text-crit">Externally reachable listeners</span>
          <span className="font-mono text-2xs text-faint">{surface.external.length} of {surface.total} listening</span>
        </div>
        {surface.external.length ? (
          <ul className="flex flex-col gap-1">
            {surface.external.slice(0, 10).map((l) => (
              <li key={`${l.host}:${l.port}`} className="flex items-center gap-2 text-[13px]">
                <span className="font-mono text-ink">{l.host}:{l.port}</span>
                <span className="text-muted">{SERVICES[l.port] ?? "unknown service"}</span>
                <Pill tone="warn">external</Pill>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted">No services bound to all interfaces — surface is limited to loopback.</p>
        )}
      </div>
    </Panel>
  );
}
