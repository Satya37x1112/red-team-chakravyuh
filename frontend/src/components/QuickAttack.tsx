import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useLiveContext } from "../live-context";
import { KIND_LIST, KINDS } from "../lib";
import type { Kind } from "../types";
import { Button, Icon, Panel, Pill, Segmented, Tag } from "./ui";

type Launched = { session_id: string; label: string; kind: Kind; state: string };

/**
 * QuickAttack — one-click launch of a gated attack session.
 * It only calls the existing, gated POST /api/attacks/start; it does NOT bypass
 * the Safety Gateway. The backend still enforces the kill switch, the target
 * allowlist, and each module's enable flag — so a disabled/unauthorized target
 * fails closed exactly as before. This is just a faster trigger for the flow
 * that the per-module Operation pages already use.
 */
export function QuickAttack() {
  const { halted, setActiveSessionId, notify } = useLiveContext();
  const [kind, setKind] = useState<Kind>("ddos");
  const [busy, setBusy] = useState(false);
  const [launched, setLaunched] = useState<Launched | null>(null);

  const run = async () => {
    setBusy(true);
    try {
      const res = await api.start(kind);
      setLaunched(res);
      setActiveSessionId(res.session_id);
      notify({ tone: "ok", title: "Attack launched", body: `${KINDS[kind].name} — ${res.label}` });
    } catch (e) {
      notify({ tone: "crit", title: "Attack not started", body: (e as Error).message });
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
      sub="Launch a gated attack session against the configured lab target. Fail-closed — the Safety Gateway still enforces the target allowlist and per-module enable flags."
      actions={halted ? <Pill tone="crit">RANGE HALTED</Pill> : <Pill tone="ok">ARMED</Pill>}
    >
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <Segmented
            value={kind}
            onChange={setKind}
            options={KIND_LIST.map((k) => ({ value: k.kind, label: k.name }))}
          />
          <Button
            variant="primary"
            onClick={run}
            disabled={busy || halted}
            title={halted ? "Kill switch engaged — re-arm the range first" : undefined}
          >
            <Icon name="play" size={12} />
            {halted ? "Range halted" : busy ? "Launching…" : "RUN ATTACK"}
          </Button>
          {launched && (
            <Button variant="danger" onClick={stop}>
              <Icon name="power" size={12} />
              Stop / Kill
            </Button>
          )}
        </div>
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
