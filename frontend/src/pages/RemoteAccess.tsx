import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useLiveContext } from "../live-context";
import { Button, Empty, Panel, Pill, SectionLabel, Tag } from "../components/ui";
import type { RemoteAccessResult, RemoteAccessStatus } from "../types";
import type { StateTone } from "../lib";

/**
 * Credentialed Remote Access / Post-Exploitation Demonstration (RAT Alternative).
 * The user picks ONE approved operation IDENTIFIER (never a command). The request
 * goes through the Safety Gateway; a disabled/unauthorized request is rejected
 * and never runs. Credentials live server-side and are never shown here. There is
 * no command input and no shell.
 */

function statusTone(s: string | undefined): StateTone {
  if (s === "success") return "ok";
  if (s === "auth_failed" || s === "unreachable" || s === "timed_out") return "crit";
  if (s === "reachable_no_auth") return "warn";
  return "muted";
}

export function RemoteAccess() {
  const { halted } = useLiveContext();
  const [status, setStatus] = useState<RemoteAccessStatus | null>(null);
  const [operation, setOperation] = useState<string>("");
  const [result, setResult] = useState<RemoteAccessResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadStatus = useCallback(() => {
    api
      .remoteAccessStatus()
      .then((s) => {
        setStatus(s);
        const ops = s.detail.operations ?? [];
        setOperation((cur) => cur || ops[0] || "");
      })
      .catch((e) => setError(String((e as Error).message)));
  }, []);
  useEffect(() => loadStatus(), [loadStatus]);

  const ops = status?.detail.operations ?? [];
  const descriptions = status?.detail.operation_descriptions ?? {};
  const runnable = status?.detail.runnable === true;

  const run = async () => {
    if (!operation) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.remoteAccessRun({ operation }));
    } catch (e) {
      // A Safety-Gateway rejection (423) or failure (502) arrives as an error here.
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Panel
        title="Credentialed Remote Access / Post-Exploitation Demonstration (RAT Alternative)"
        sub="Controlled, credentialed remote administration via an approved interface — a fixed allowlist of benign READ-ONLY operations. No implant, no persistence, no arbitrary commands."
        actions={
          status ? (
            <Pill tone={status.available && runnable ? "ok" : status.available ? "warn" : "crit"}>
              {runnable ? "ARMED" : status.available ? "NOT ARMED" : "UNAVAILABLE"}
            </Pill>
          ) : undefined
        }
      >
        {!status ? (
          <Empty>Loading module status…</Empty>
        ) : (
          <div className="flex flex-col gap-2 text-xs text-muted">
            <p>{status.reason}</p>
            <div className="flex flex-wrap items-center gap-2">
              <Tag>protocol: {status.detail.protocol ?? "—"}</Tag>
              <Tag>target: {status.detail.target ?? "not configured"}</Tag>
              <Tag>creds: {status.detail.credentials_configured ? "configured" : "missing"}</Tag>
              <Tag>max {status.detail.caps?.max_run_seconds ?? "—"}s</Tag>
            </div>
            <p className="text-2xs text-faint">
              Credentials are stored server-side and are never shown, logged, or sent to the AI.
            </p>
          </div>
        )}
      </Panel>

      <Panel title="Approved operations" sub="Select one identifier. These map to fixed, read-only implementations — not commands.">
        {ops.length === 0 ? (
          <Empty>No operations available.</Empty>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap gap-2">
              {ops.map((op) => (
                <button
                  key={op}
                  onClick={() => setOperation(op)}
                  title={descriptions[op] ?? op}
                  className={`rounded border px-2.5 py-1 font-mono text-xs transition-colors ${
                    op === operation
                      ? "border-accent bg-accent/10 text-ink"
                      : "border-line bg-surface text-muted hover:border-lineStrong hover:text-ink"
                  }`}
                >
                  {op}
                </button>
              ))}
            </div>
            {operation && <p className="text-xs text-muted">{descriptions[operation]}</p>}
            <div className="flex items-center gap-2">
              <Button variant="primary" onClick={run} disabled={busy || halted || !operation}>
                {busy ? "Running…" : "Run operation"}
              </Button>
              {halted && <Pill tone="crit">Kill switch engaged — execution blocked</Pill>}
            </div>
            {error && (
              <div className="rounded border border-crit/40 bg-crit/5 px-3 py-2 text-xs text-crit">
                {error}
              </div>
            )}
          </div>
        )}
      </Panel>

      {result && (
        <Panel title="Result" sub="Measured facts from the actual operation — no fabricated output.">
          <div className="flex flex-col gap-3">
            <SectionLabel index="01" label="Outcome" />
            <div className="flex flex-wrap items-center gap-2">
              <Tag>{result.operation}</Tag>
              <Pill tone={statusTone(result.status)}>{result.status}</Pill>
              {result.execution_state && <Tag>exec: {result.execution_state}</Tag>}
              <Tag>{result.duration_seconds}s</Tag>
            </div>
            <p className="text-xs text-muted">{result.message}</p>
            {Object.keys(result.measured ?? {}).length > 0 && (
              <>
                <SectionLabel index="02" label="Measured facts" />
                <ul className="flex flex-col gap-1 text-xs text-ink">
                  {Object.entries(result.measured).map(([k, v]) => (
                    <li key={k} className="flex gap-2">
                      <span className="font-mono text-2xs uppercase tracking-wide text-faint">{k}</span>
                      <span>{v === null ? "—" : String(v)}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        </Panel>
      )}
    </div>
  );
}
