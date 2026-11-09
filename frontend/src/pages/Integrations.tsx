import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Button, Empty, Icon, Panel, Pill, SectionLabel } from "../components/ui";
import type { CalderaAnalysis, CalderaSample, IntegrationStatus, VervetEmulateResult } from "../types";

const CATEGORY_LABEL: Record<string, string> = {
  analysis: "Analysis",
  "load-test": "Load test",
  emulation: "Emulation",
  agent: "Agent",
};

function statusTone(s: IntegrationStatus): "ok" | "warn" | "muted" {
  if (!s.available) return "muted";
  if (s.detail?.runnable === false) return "warn";
  return "ok";
}

function DetailChips({ detail }: { detail: Record<string, unknown> }) {
  const entries = Object.entries(detail).filter(
    ([, v]) => v !== null && v !== undefined && typeof v !== "object"
  );
  if (!entries.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {entries.map(([k, v]) => (
        <span key={k} className="rounded border border-line bg-raised px-1.5 py-px font-mono text-2xs text-muted">
          {k}=<span className="text-ink">{String(v)}</span>
        </span>
      ))}
    </div>
  );
}

function StatTile({ label, value, tone = "ink" }: { label: string; value: string | number; tone?: "ink" | "ok" | "crit" }) {
  const color = tone === "ok" ? "text-ok" : tone === "crit" ? "text-crit" : "text-ink";
  return (
    <div className="rounded border border-line bg-canvas px-3 py-2">
      <div className="text-2xs text-muted">{label}</div>
      <div className={`mt-0.5 font-mono text-lg ${color}`}>{value}</div>
    </div>
  );
}

function CalderaPanel({ status }: { status: IntegrationStatus }) {
  const [samples, setSamples] = useState<CalderaSample[]>([]);
  const [sample, setSample] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CalderaAnalysis | null>(null);

  useEffect(() => {
    api
      .calderaSamples()
      .then((s) => {
        setSamples(s);
        if (s.length) setSample(s[0].file);
      })
      .catch(() => undefined);
  }, []);

  const run = useCallback(async () => {
    if (!sample) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await api.calderaAnalyze({ sample }));
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  }, [sample]);

  const stats = result?.stats;

  return (
    <Panel
      title="MITRE CALDERA Analyzer"
      sub="Parse a Caldera operation report into ATT&CK technique/tactic coverage."
      actions={<Pill tone={statusTone(status)}>{status.available ? "ready" : "unavailable"}</Pill>}
    >
      <div className="flex flex-col gap-4">
        <p className="text-xs text-muted">{status.reason}</p>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={sample}
            onChange={(e) => setSample(e.target.value)}
            className="h-8 rounded border border-line bg-canvas px-2 text-xs text-ink"
          >
            {samples.length === 0 && <option value="">No sample reports found</option>}
            {samples.map((s) => (
              <option key={s.file} value={s.file}>
                {s.operation ? `${s.operation} — ${s.file}` : s.file}
              </option>
            ))}
          </select>
          <Button variant="primary" onClick={run} disabled={busy || !sample}>
            <Icon name="play" size={13} />
            {busy ? "Analyzing…" : "Analyze"}
          </Button>
        </div>

        {error && <p className="rounded border border-crit/40 bg-crit/10 px-3 py-2 text-xs text-crit">{error}</p>}

        {stats && (
          <div className="flex flex-col gap-4">
            <SectionLabel index="01" label="ATT&CK coverage" hint={`${stats.total_steps} steps`} />
            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
              <StatTile label="Techniques" value={stats.distinct_techniques} />
              <StatTile label="Tactics" value={stats.distinct_tactics} />
              <StatTile label="Succeeded" value={stats.success} tone="ok" />
              <StatTile label="Failed" value={stats.failed} tone={stats.failed ? "crit" : "ink"} />
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <div>
                <div className="mb-1.5 text-2xs uppercase tracking-wide text-faint">Techniques</div>
                <div className="overflow-hidden rounded border border-line">
                  {stats.techniques.map((t, i) => (
                    <div
                      key={t.name}
                      className={`flex items-center justify-between gap-2 px-2.5 py-1.5 text-xs ${
                        i % 2 ? "bg-canvas" : "bg-surface"
                      }`}
                    >
                      <span className="truncate text-ink">{t.name}</span>
                      <span className="shrink-0 font-mono text-2xs text-muted">×{t.count}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <div className="mb-1.5 text-2xs uppercase tracking-wide text-faint">Tactics</div>
                <div className="flex flex-wrap gap-1.5">
                  {stats.tactics.map((t) => (
                    <span key={t.name} className="rounded border border-line bg-raised px-2 py-0.5 text-xs text-ink">
                      {t.name} <span className="font-mono text-2xs text-muted">×{t.count}</span>
                    </span>
                  ))}
                </div>
              </div>
            </div>

          </div>
        )}
      </div>
    </Panel>
  );
}

function VervetPanel({ status }: { status: IntegrationStatus }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [doc, setDoc] = useState<Record<string, unknown> | null>(null);

  const suggested = (status.detail?.suggested_target as string | undefined) ?? "127.0.0.1";
  const guiTechs = (status.detail?.gui_techniques as string[] | undefined) ?? ["T1046"];
  const [target, setTarget] = useState(suggested);
  const [scanning, setScanning] = useState(false);
  const [scanErr, setScanErr] = useState<string | null>(null);
  const [scan, setScan] = useState<VervetEmulateResult | null>(null);

  const describe = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setDoc(await api.vervetDescribe());
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  }, []);

  const runScan = useCallback(async () => {
    setScanning(true);
    setScanErr(null);
    try {
      setScan(await api.vervetEmulate({ target, technique: guiTechs[0] }));
    } catch (e) {
      setScanErr(String((e as Error).message));
    } finally {
      setScanning(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  const verbs = (doc?.verbs as string[] | undefined) ?? [];
  const techniques = (doc?.techniques as Record<string, unknown>[] | undefined) ?? [];

  return (
    <Panel
      title="vervet Adversary Emulation"
      sub="Signed, CLI-first emulation. Read-only describe / coverage from the console."
      actions={<Pill tone={statusTone(status)}>{status.available ? "ready" : "unavailable"}</Pill>}
    >
      <div className="flex flex-col gap-3">
        <p className="text-xs text-muted">{status.reason}</p>
        {status.available ? (
          <div>
            <Button variant="primary" onClick={describe} disabled={busy}>
              <Icon name="terminal" size={13} />
              {busy ? "Running…" : "vervet describe"}
            </Button>
          </div>
        ) : (
          <code className="block rounded border border-line bg-canvas px-2.5 py-2 font-mono text-2xs text-muted">
            cargo build --release -p vervet-cli
          </code>
        )}
        {status.available && (
          <div className="flex flex-col gap-2 rounded border border-line bg-canvas p-3">
            <SectionLabel index="scan" label="Service discovery scan" hint={guiTechs.join(", ")} />
            <div className="flex flex-wrap items-center gap-2">
              <input
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                placeholder="target IPv4 (e.g. 127.0.0.1)"
                className="h-8 w-48 rounded border border-line bg-surface px-2 font-mono text-xs text-ink"
              />
              <Button variant="danger" onClick={runScan} disabled={scanning || !target}>
                <Icon name="pulse" size={13} />
                {scanning ? "Scanning…" : "Run scan"}
              </Button>
              <span className="text-2xs text-faint">Auto-signs a scope for this target · authorized use only</span>
            </div>
            {scanErr && <p className="rounded border border-crit/40 bg-crit/10 px-3 py-2 text-xs text-crit">{scanErr}</p>}
            {scan && (
              <div className="flex flex-col gap-2">
                <div className="text-2xs text-muted">
                  {scan.technique} vs <span className="font-mono text-ink">{scan.target}</span> · engagement{" "}
                  <span className="font-mono">{scan.engagement_id}</span> · {scan.findings.length} observation(s)
                </div>
                {scan.findings.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {scan.findings.map((f) => (
                      <span key={f.handle} className="rounded border border-ok/30 bg-ok/10 px-2 py-0.5 font-mono text-2xs text-ok">
                        {f.detail} <span className="text-muted">open</span>
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-2xs text-muted">No open service ports observed.</p>
                )}
              </div>
            )}
          </div>
        )}
        {error && <p className="rounded border border-crit/40 bg-crit/10 px-3 py-2 text-xs text-crit">{error}</p>}
        {doc && (
          <div className="flex flex-col gap-3">
            {verbs.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {verbs.map((v) => (
                  <span key={v} className="rounded border border-line bg-raised px-1.5 py-px font-mono text-2xs text-ink">
                    {v}
                  </span>
                ))}
              </div>
            )}
            {techniques.length > 0 && (
              <div className="overflow-hidden rounded border border-line">
                {techniques.map((t, i) => (
                  <div key={i} className={`px-2.5 py-1.5 text-xs ${i % 2 ? "bg-canvas" : "bg-surface"}`}>
                    <span className="font-mono text-2xs text-accent">{String(t.attack_id ?? t.id ?? "")}</span>{" "}
                    <span className="text-ink">{String(t.name ?? t.title ?? JSON.stringify(t))}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}

function LocustPanel({ status }: { status: IntegrationStatus }) {
  const runnable = status.available && status.detail?.runnable === true;
  const caps = (status.detail?.caps as { max_users?: number; max_spawn_rate?: number; max_run_seconds?: number }) ?? {};
  const [users, setUsers] = useState<number>(caps.max_users ?? 10);
  const [rate, setRate] = useState<number>(caps.max_spawn_rate ?? 2);
  const [secs, setSecs] = useState<number>(Math.min(30, caps.max_run_seconds ?? 30));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const run = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.locustRun({ users, spawn_rate: rate, run_seconds: secs }));
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  }, [users, rate, secs]);

  const simulate = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.locustSimulate({ users, spawn_rate: rate, run_seconds: secs }));
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  }, [users, rate, secs]);

  const stop = useCallback(async () => {
    try {
      await api.killSwitch();
    } catch (e) {
      setError(String((e as Error).message));
    }
  }, []);

  return (
    <Panel
      title="Locust Load Test"
      sub="The real DDoS driver. Fail-closed: runs only an operator locustfile at an authorized target."
      actions={<Pill tone={statusTone(status)}>{runnable ? "armed" : status.available ? "disarmed" : "unavailable"}</Pill>}
    >
      <div className="flex flex-col gap-3">
        <p className="text-xs text-muted">{status.reason}</p>
        <DetailChips detail={status.detail} />
        {runnable ? (
          <>
            <div className="flex flex-wrap items-end gap-3">
              <label className="flex flex-col gap-1 text-2xs text-muted">
                Users (≤{caps.max_users})
                <input
                  type="number"
                  min={1}
                  max={caps.max_users}
                  value={users}
                  onChange={(e) => setUsers(Number(e.target.value))}
                  className="h-8 w-20 rounded border border-line bg-canvas px-2 text-xs text-ink"
                />
              </label>
              <label className="flex flex-col gap-1 text-2xs text-muted">
                Spawn/s (≤{caps.max_spawn_rate})
                <input
                  type="number"
                  min={1}
                  max={caps.max_spawn_rate}
                  value={rate}
                  onChange={(e) => setRate(Number(e.target.value))}
                  className="h-8 w-20 rounded border border-line bg-canvas px-2 text-xs text-ink"
                />
              </label>
              <label className="flex flex-col gap-1 text-2xs text-muted">
                Seconds (≤{caps.max_run_seconds})
                <input
                  type="number"
                  min={1}
                  max={caps.max_run_seconds}
                  value={secs}
                  onChange={(e) => setSecs(Number(e.target.value))}
                  className="h-8 w-20 rounded border border-line bg-canvas px-2 text-xs text-ink"
                />
              </label>
              <Button variant="danger" onClick={run} disabled={busy}>
                <Icon name="pulse" size={13} />
                {busy ? "Running…" : "Run load test"}
              </Button>
            </div>
            <p className="text-2xs text-faint">
              Authorized lab targets only. Values are clamped to the configured caps server-side.
            </p>
          </>
        ) : (
          <code className="block rounded border border-line bg-canvas px-2.5 py-2 font-mono text-2xs text-muted">
            LOCUST_ENABLED=true · LOCUST_FILE_PATH=… · LOCUST_TARGET_URL=…
          </code>
        )}

        <div className="flex flex-col gap-2 rounded border border-amber-500/40 bg-amber-500/5 px-3 py-2.5">
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-2xs font-semibold uppercase tracking-wide text-amber-500">
              Simulation mode — no network traffic
            </span>
            <Pill tone="warn">SIMULATED</Pill>
          </div>
          <p className="text-2xs text-muted">
            Demonstrates the full execution lifecycle (Safety Gateway · Registry · Kill Switch · audit)
            with synthetic telemetry. Sends nothing — no target is contacted. Uses the caps above
            (users ≤{caps.max_users}, spawn ≤{caps.max_spawn_rate}, ≤{caps.max_run_seconds}s), clamped server-side.
          </p>
          <div className="flex items-center gap-2">
            <Button variant="ghost" onClick={simulate} disabled={busy}>
              <Icon name="pulse" size={13} />
              {busy ? "Simulating…" : "Run simulation"}
            </Button>
            <Button variant="danger" onClick={stop} disabled={!busy}>
              <Icon name="power" size={12} />
              Stop
            </Button>
          </div>
        </div>
        {error && <p className="rounded border border-crit/40 bg-crit/10 px-3 py-2 text-xs text-crit">{error}</p>}
        {result && (
          <div className="flex flex-col gap-2">
            {result.simulated === true && (
              <div className="rounded border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-center font-mono text-2xs font-semibold uppercase tracking-wide text-amber-500">
                {String(result.banner ?? "SIMULATION — NO NETWORK TRAFFIC GENERATED")}
                {result.stopped_early === true ? " · STOPPED" : ""}
              </div>
            )}
            {(() => {
              const t = result.totals as
                | { requests?: number; failures?: number; rps?: number; error_pct?: number; p95_ms?: number }
                | undefined;
              const sim = result.simulated === true;
              return t ? (
                <div className="grid grid-cols-3 gap-2.5">
                  <StatTile label={sim ? "Sim requests" : "Requests"} value={Number(t.requests ?? 0)} />
                  <StatTile label={sim ? "Sim req/s" : "Req/s"} value={Number(t.rps ?? 0)} tone="ok" />
                  {sim ? (
                    <StatTile label="Sim p95 ms" value={Number(t.p95_ms ?? 0)} />
                  ) : (
                    <StatTile label="Failures" value={Number(t.failures ?? 0)} tone={Number(t.failures ?? 0) ? "crit" : "ink"} />
                  )}
                </div>
              ) : null;
            })()}
            <pre className="max-h-72 overflow-auto rounded border border-line bg-canvas p-3 font-mono text-2xs text-ink">
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </Panel>
  );
}

function HydraPanel({ status }: { status: IntegrationStatus }) {
  const runnable = status.available && status.detail?.runnable === true;
  const caps = (status.detail?.caps as { max_tasks?: number; max_attempts?: number; max_run_seconds?: number }) ?? {};
  const [tasks, setTasks] = useState<number>(caps.max_tasks ?? 4);
  const [secs, setSecs] = useState<number>(Math.min(60, caps.max_run_seconds ?? 60));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const run = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.hydraRun({ tasks, run_seconds: secs }));
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  }, [tasks, secs]);

  const found = (result?.found as { login?: string; service?: string; port?: number }[] | undefined) ?? [];

  return (
    <Panel
      title="THC-Hydra Login Cracker"
      sub="The real credential-test driver. Fail-closed: runs only the operator list pair at an authorized target."
      actions={<Pill tone={statusTone(status)}>{runnable ? "armed" : status.available ? "disarmed" : "unavailable"}</Pill>}
    >
      <div className="flex flex-col gap-3">
        <p className="text-xs text-muted">{status.reason}</p>
        <DetailChips detail={status.detail} />
        {runnable ? (
          <>
            <div className="flex flex-wrap items-end gap-3">
              <label className="flex flex-col gap-1 text-2xs text-muted">
                Tasks (≤{caps.max_tasks})
                <input
                  type="number"
                  min={1}
                  max={caps.max_tasks}
                  value={tasks}
                  onChange={(e) => setTasks(Number(e.target.value))}
                  className="h-8 w-20 rounded border border-line bg-canvas px-2 text-xs text-ink"
                />
              </label>
              <label className="flex flex-col gap-1 text-2xs text-muted">
                Seconds (≤{caps.max_run_seconds})
                <input
                  type="number"
                  min={1}
                  max={caps.max_run_seconds}
                  value={secs}
                  onChange={(e) => setSecs(Number(e.target.value))}
                  className="h-8 w-20 rounded border border-line bg-canvas px-2 text-xs text-ink"
                />
              </label>
              <Button variant="danger" onClick={run} disabled={busy}>
                <Icon name="pulse" size={13} />
                {busy ? "Running…" : "Run credential test"}
              </Button>
            </div>
            <p className="text-2xs text-faint">
              Authorized lab targets only. Target, service, and wordlists are fixed server-side; cracked passwords are
              never returned to the UI.
            </p>
          </>
        ) : (
          <code className="block rounded border border-line bg-canvas px-2.5 py-2 font-mono text-2xs text-muted">
            HYDRA_ENABLED=true · HYDRA_TARGET=… · HYDRA_USERLIST_PATH=… · HYDRA_PASSLIST_PATH=…
          </code>
        )}
        {error && <p className="rounded border border-crit/40 bg-crit/10 px-3 py-2 text-xs text-crit">{error}</p>}
        {result && (() => {
          const cracked = Number(result.found_count ?? 0) > 0;
          const made = Number(result.attempts_made ?? 0);
          const space = Number(result.attempt_space ?? 0);
          const pct = space ? Math.min(100, Math.round((made / space) * 100)) : cracked ? 100 : 0;
          const feed = (result.attempt_feed as { n?: number; login?: string; pass_masked?: string }[] | undefined) ?? [];
          const dur = result.duration_seconds as number | undefined;
          const hit = found[0];
          return (
            <div className="flex flex-col gap-3">
              <div className={`rounded border px-3 py-2.5 ${cracked ? "border-crit/40 bg-crit/10" : "border-line bg-canvas"}`}>
                <div className="flex items-center gap-2">
                  {cracked && <Icon name="key" size={14} />}
                  <span className={`text-sm font-semibold ${cracked ? "text-crit" : "text-ink"}`}>
                    {cracked ? "CREDENTIAL CRACKED" : "No valid credentials found"}
                  </span>
                </div>
                {cracked && hit && (
                  <div className="mt-1 font-mono text-xs text-ink">
                    {hit.login}<span className="text-muted">@{hit.service}:{hit.port}</span>
                    {result.cracked_at ? <span className="text-muted"> · cracked at attempt #{String(result.cracked_at)}</span> : null}
                  </div>
                )}
                {!cracked && typeof result.message === "string" && (
                  <p className="mt-1 text-2xs text-muted">{result.message}</p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
                <StatTile label="Attempts" value={space ? `${made}/${space}` : made} />
                <StatTile label="Cracked at" value={result.cracked_at ? `#${String(result.cracked_at)}` : "-"} tone={cracked ? "crit" : "ink"} />
                <StatTile label="Duration" value={dur != null ? `${dur}s` : "-"} />
                <StatTile label="Found" value={Number(result.found_count ?? 0)} tone={cracked ? "crit" : "ok"} />
              </div>

              {space > 0 && (
                <div className="h-1.5 w-full overflow-hidden rounded bg-raised">
                  <div className={`h-full ${cracked ? "bg-crit" : "bg-ok"}`} style={{ width: `${pct}%` }} />
                </div>
              )}

              {feed.length > 0 && (
                <div>
                  <div className="mb-1 text-2xs uppercase tracking-wide text-faint">Attempt feed (passwords masked)</div>
                  <div className="max-h-48 overflow-auto rounded border border-line bg-canvas p-2 font-mono text-2xs">
                    {feed.map((a, i) => {
                      const isHit = cracked && i === feed.length - 1;
                      return (
                        <div key={i} className={`flex items-center gap-2 px-1 py-0.5 ${isHit ? "text-crit" : "text-muted"}`}>
                          <span className="w-9 shrink-0 text-faint">#{a.n ?? i + 1}</span>
                          <span className={isHit ? "text-crit" : "text-ink"}>{a.login}</span>
                          <span className="text-faint">:</span>
                          <span className="tracking-widest">{a.pass_masked}</span>
                          <span className="ml-auto">{isHit ? "✓ CRACKED" : "✗"}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          );
        })()}
      </div>
    </Panel>
  );
}

function GenericPanel({ status }: { status: IntegrationStatus }) {
  return (
    <Panel
      title={status.title}
      sub={`${CATEGORY_LABEL[status.category] ?? status.category} · ${status.repo}`}
      actions={<Pill tone={statusTone(status)}>{status.available ? "ready" : "unavailable"}</Pill>}
    >
      <div className="flex flex-col gap-3">
        <p className="text-xs text-muted">{status.reason}</p>
        <DetailChips detail={status.detail} />
      </div>
    </Panel>
  );
}

export function Integrations() {
  const [statuses, setStatuses] = useState<IntegrationStatus[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .integrations()
      .then(setStatuses)
      .catch((e) => setError(String((e as Error).message)));
  }, []);

  useEffect(load, [load]);

  const byName = useMemo(() => Object.fromEntries((statuses ?? []).map((s) => [s.name, s])), [statuses]);
  const availableCount = (statuses ?? []).filter((s) => s.available).length;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-ink">Integrations</h1>
          <p className="mt-1 text-xs text-muted">
            External red-team tooling wired into the range. Each adapter is optional and reports its own status —
            missing toolchains or keys degrade cleanly, they don't crash the console.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {statuses && (
            <span className="rounded border border-line bg-surface px-2 py-1 font-mono text-2xs text-muted">
              {availableCount}/{statuses.length} ready
            </span>
          )}
          <Button onClick={load}>
            <Icon name="refresh" size={13} />
            Refresh
          </Button>
        </div>
      </div>

      {error && <p className="rounded border border-crit/40 bg-crit/10 px-3 py-2 text-xs text-crit">{error}</p>}

      {statuses === null ? (
        <Empty>Loading integrations…</Empty>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {byName.caldera && <CalderaPanel status={byName.caldera} />}
          {byName.locust && <LocustPanel status={byName.locust} />}
          {byName.hydra && <HydraPanel status={byName.hydra} />}
          {byName.vervet && <VervetPanel status={byName.vervet} />}
          {byName.pentestgpt && <GenericPanel status={byName.pentestgpt} />}
        </div>
      )}
    </div>
  );
}
