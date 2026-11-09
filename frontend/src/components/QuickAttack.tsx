import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useLiveContext } from "../live-context";
import { KIND_LIST, KINDS } from "../lib";
import type { Kind } from "../types";
import { Button, Icon, Panel, Pill, Segmented, Tag } from "./ui";

type Launched = { session_id: string; label: string; kind: Kind; state: string };

/**
 * QuickAttack — one-click launcher on the dashboard.
 *
 * Two modes:
 *  - No target IP: launches the existing gated internal attack session
 *    (POST /api/attacks/start) — a simulated lifecycle, no network traffic.
 *  - With a target IP: generates a BOUNDED, non-destructive SOC detection
 *    signature for the selected TTP against an authorized lab / tailnet IP
 *    (POST /api/attacks/soc-activity). Not a real attack — no flood/DoS, bogus
 *    credentials only (no lockout), read-only enumeration (no implant). Public
 *    IPs are refused server-side. The generated events are what the target's SOC
 *    logs — proof that red-team activity reached the target.
 */
export function QuickAttack() {
  const { halted, setActiveSessionId, notify } = useLiveContext();
  const [kind, setKind] = useState<Kind>("ddos");
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [launched, setLaunched] = useState<Launched | null>(null);
  const [soc, setSoc] = useState<Record<string, unknown> | null>(null);

  const run = async () => {
    const ip = target.trim();
    setBusy(true);
    setSoc(null);
    try {
      if (ip) {
        // SOC detection-signature against an authorized target IP.
        const res = await api.socActivity({ kind, target: ip });
        setSoc(res);
        notify({ tone: "ok", title: "SOC activity generated", body: `${KINDS[kind].name} → ${ip}` });
      } else {
        // Internal gated session (no network traffic).
        const res = await api.start(kind);
        setLaunched(res);
        setActiveSessionId(res.session_id);
        notify({ tone: "ok", title: "Attack launched", body: `${KINDS[kind].name} — ${res.label}` });
      }
    } catch (e) {
      notify({ tone: "crit", title: "Not started", body: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  const stop = async () => {
    try {
      await api.killSwitch();
      notify({ tone: "info", title: "Kill switch engaged", body: "Running sessions are being terminated." });
    } catch (e) {
      notify({ tone: "crit", title: "Kill switch failed", body: (e as Error).message });
    }
  };

  return (
    <Panel
      title="One-Click Attack"
      sub="Enter an authorized lab / tailnet target IP to generate a bounded, non-destructive SOC detection signature (DDoS / Brute Force / RAT) — the target's SOC logs the activity as proof. Leave the IP blank to run the internal simulated session. Public IPs are refused."
      actions={halted ? <Pill tone="crit">RANGE HALTED</Pill> : <Pill tone="ok">ARMED</Pill>}
    >
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <Segmented
            value={kind}
            onChange={setKind}
            options={KIND_LIST.map((k) => ({ value: k.kind, label: k.name }))}
          />
          <input
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !busy && !halted) run();
            }}
            placeholder="target IP (e.g. 100.80.167.51) — blank = simulate"
            className="h-8 w-72 rounded border border-line bg-canvas px-2.5 font-mono text-xs text-ink outline-none placeholder:text-faint focus:border-accent"
          />
          <Button
            variant="primary"
            onClick={run}
            disabled={busy || halted}
            title={halted ? "Kill switch engaged — re-arm the range first" : undefined}
          >
            <Icon name="play" size={12} />
            {halted ? "Range halted" : busy ? "Running…" : "RUN ATTACK"}
          </Button>
          {(launched || busy) && (
            <Button variant="danger" onClick={stop}>
              <Icon name="power" size={12} />
              Stop / Kill
            </Button>
          )}
        </div>

        {soc && (
          <div className="flex flex-col gap-2 rounded border border-amber-500/40 bg-amber-500/5 px-3 py-2.5 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <Pill tone="warn">SOC SIGNATURE</Pill>
              <Tag>{String((soc.label as string) ?? KINDS[kind].name)}</Tag>
              <span className="font-mono text-ink">{String(soc.target ?? "")}</span>
              {soc.source_ip ? <Tag>from {String(soc.source_ip)}</Tag> : null}
            </div>
            {soc.detectable_as ? (
              <div className="text-muted">
                <span className="text-faint">Detectable as: </span>
                {String(soc.detectable_as)}
              </div>
            ) : null}
            {soc.note ? <div className="text-ok">{String(soc.note)}</div> : null}
          </div>
        )}

        {launched && (
          <div className="flex flex-wrap items-center gap-2 rounded border border-line bg-canvas px-3 py-2 text-xs text-muted">
            <Pill tone="warn">{launched.state}</Pill>
            <Tag>{KINDS[launched.kind].name}</Tag>
            <span className="font-mono text-ink">{launched.label}</span>
            <Link to={KINDS[launched.kind].path} className="text-accent hover:underline">
              open live view →
            </Link>
          </div>
        )}
      </div>
    </Panel>
  );
}
