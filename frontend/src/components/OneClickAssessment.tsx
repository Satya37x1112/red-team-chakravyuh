import { useEffect, useState } from "react";
import { api } from "../api";
import { useLiveContext } from "../live-context";
import { KIND_LIST, KINDS } from "../lib";
import type { Kind } from "../types";
import { Button, Icon, Panel, Pill, Segmented } from "./ui";

export interface AssessmentStep {
  id: string;
  name: string;
  status: "READY" | "RUNNING" | "DONE" | "SKIPPED" | "BLOCKED" | "STOPPED" | "UNAVAILABLE";
  details?: string;
  data?: Record<string, unknown>;
  duration_seconds?: number;
}

export interface OpenPortDetail {
  port: number;
  service: string;
  latency_ms?: number | null;
}

export interface AssessmentResult {
  assessment_id: string;
  target: string;
  status: "COMPLETED" | "STOPPED" | "BLOCKED" | "FAILED";
  started_at: string;
  completed_at: string;
  open_ports: number[];
  open_port_details: OpenPortDetail[];
  steps: AssessmentStep[];
  summary: {
    status?: string;
    target_online?: boolean;
    open_ports_count?: number;
    total_steps?: number;
    completed_steps?: number;
    skipped_steps?: number;
    unavailable_steps?: number;
    duration_seconds?: number;
    execution_id?: string;
    audit_id?: number;
    reason?: string;
  };
}

const DEFAULT_STEPS: AssessmentStep[] = [
  { id: "target_validation", name: "1. Target Authorization Validation", status: "READY", details: "Verify RFC1918 or current Tailnet peer (fail-closed)." },
  { id: "reachability", name: "2. Target Reachability Probe", status: "READY", details: "Non-destructive TCP connect / Tailscale ping." },
  { id: "recon_probe", name: "3. Non-Destructive Recon Probe", status: "READY", details: "Enumerate open ports and service latency." },
  { id: "soc_ddos", name: "4. DDoS SOC Detection Signature", status: "READY", details: "Bounded connection burst (40 connects max, ≤8s)." },
  { id: "soc_bruteforce", name: "5. Brute Force SOC Signature", status: "READY", details: "5 bogus usernames to port 445 (no lockout)." },
  { id: "soc_rat", name: "6. RAT / Remote Access SOC Signature", status: "READY", details: "Read-only SMB enumeration (no implant/persistence)." },
  { id: "offline_hash_audit", name: "7. Offline RockYou Hash Audit", status: "READY", details: "Audit password hash against local RockYou wordlist." },
  { id: "locust_load_test", name: "8. Live HTTP Load Test", status: "UNAVAILABLE", details: "Requires setup (authorized target URL & locustfile)." },
  { id: "remote_file_transfer", name: "9. Authenticated Remote File Transfer", status: "UNAVAILABLE", details: "Requires setup (Windows receiver on port 8090)." },
];

function stepTone(status: string): "ok" | "warn" | "crit" | "muted" {
  switch (status) {
    case "DONE":
      return "ok";
    case "RUNNING":
      return "warn";
    case "BLOCKED":
    case "STOPPED":
    case "FAILED":
      return "crit";
    case "UNAVAILABLE":
    case "SKIPPED":
    default:
      return "muted";
  }
}

export function OneClickAssessment() {
  const { halted, notify } = useLiveContext();
  const [target, setTarget] = useState("100.80.167.51");
  const [passwordHash, setPasswordHash] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AssessmentResult | null>(null);
  const [steps, setSteps] = useState<AssessmentStep[]>(DEFAULT_STEPS);
  const [openPorts, setOpenPorts] = useState<OpenPortDetail[]>([]);
  const [showSingleTtp, setShowSingleTtp] = useState(false);
  const [singleKind, setSingleKind] = useState<Kind>("ddos");
  const [singleSoc, setSingleSoc] = useState<Record<string, unknown> | null>(null);
  const [expandedStep, setExpandedStep] = useState<string | null>(null);

  // Load previous assessment on mount if available, or populate selected target
  useEffect(() => {
    const paramTarget = new URLSearchParams(window.location.search).get("target");
    if (paramTarget) {
      setTarget(paramTarget);
    } else {
      api.networkTargets().then((list) => {
        const active = list.find((t) => t.selected);
        if (active?.ip) setTarget(active.ip);
      }).catch(() => undefined);
    }

    api
      .assessmentLatest()
      .then((data) => {
        if (data && Array.isArray(data.steps)) {
          const res = data as unknown as AssessmentResult;
          setResult(res);
          setSteps(res.steps);
          if (!paramTarget && res.target) setTarget(res.target);
          if (Array.isArray(res.open_port_details)) {
            setOpenPorts(res.open_port_details);
          }
        }
      })
      .catch(() => undefined);
  }, []);

  const runAssessment = async () => {
    const ip = target.trim();
    if (!ip) {
      notify({ tone: "crit", title: "Target required", body: "Enter an authorized lab target IP." });
      return;
    }
    setBusy(true);
    setResult(null);
    setOpenPorts([]);
    // Mark initial steps running
    setSteps((prev) =>
      prev.map((s) => ({
        ...s,
        status: s.id === "target_validation" ? "RUNNING" : "READY",
      }))
    );

    try {
      const res = (await api.assessmentRun({
        target: ip,
        password_hash: passwordHash.trim() || undefined,
      })) as unknown as AssessmentResult;

      setResult(res);
      setSteps(res.steps || DEFAULT_STEPS);
      if (Array.isArray(res.open_port_details)) {
        setOpenPorts(res.open_port_details);
      }

      if (res.status === "BLOCKED") {
        notify({ tone: "crit", title: "Target Refused", body: res.summary?.reason || "Target refused (fail-closed)." });
      } else if (res.status === "STOPPED") {
        notify({ tone: "crit", title: "Assessment Stopped", body: "Sequence halted by Kill Switch." });
      } else {
        const portCount = res.open_ports?.length ?? 0;
        const online = res.summary?.target_online ?? false;
        notify({
          tone: online ? "ok" : "info",
          title: "Assessment Completed",
          body: online
            ? `Assessed ${ip}: ${portCount} open port(s) detected.`
            : `Assessed ${ip}: Target is OFFLINE (stopped early).`,
        });
      }
    } catch (e) {
      notify({ tone: "crit", title: "Assessment Failed", body: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  const runSingleTtp = async () => {
    const ip = target.trim();
    if (!ip) {
      notify({ tone: "crit", title: "Target required", body: "Enter an authorized target IP first." });
      return;
    }
    setBusy(true);
    setSingleSoc(null);
    try {
      const res = await api.socActivity({ kind: singleKind, target: ip });
      setSingleSoc(res);
      notify({ tone: "ok", title: "SOC signature generated", body: `${KINDS[singleKind].name} → ${ip}` });
    } catch (e) {
      notify({ tone: "crit", title: "Not started", body: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };

  const handleStop = async () => {
    try {
      await api.killSwitch();
      notify({ tone: "info", title: "Kill Switch Engaged", body: "Terminating all managed execution processes." });
    } catch (e) {
      notify({ tone: "crit", title: "Kill Switch Failed", body: (e as Error).message });
    }
  };

  return (
    <Panel
      title="One-Click Orchestrated Assessment"
      sub="Automated, bounded evaluation pipeline. Executes target validation, reachability probing, non-destructive port recon, purple-team SOC signatures, and local RockYou hash auditing in one click."
      actions={
        <div className="flex items-center gap-2">
          {result && (
            <span className="font-mono text-2xs text-muted">
              Last: <span className="text-ink">{result.target}</span> (
              {result.summary?.target_online ? `${result.open_ports?.length ?? 0} ports` : "offline"})
            </span>
          )}
          {halted ? <Pill tone="crit">RANGE HALTED</Pill> : <Pill tone="ok">ARMED</Pill>}
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        {/* Input Bar */}
        <div className="flex flex-col gap-2 rounded border border-line bg-canvas p-3">
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-2xs text-muted">
              Target IP (Authorized Lab / Tailnet Host)
              <div className="flex gap-2">
                <input
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !busy && !halted) runAssessment();
                  }}
                  placeholder="e.g. 100.80.167.51"
                  className="h-8 flex-1 rounded border border-line bg-surface px-2.5 font-mono text-xs text-ink outline-none placeholder:text-faint focus:border-accent"
                />
                <button
                  type="button"
                  onClick={() => setTarget("100.80.167.51")}
                  className="rounded border border-line bg-surface px-2 py-1 font-mono text-2xs text-muted hover:text-ink"
                  title="Lab Windows VM on Tailscale"
                >
                  Lab Target
                </button>
              </div>
            </label>

            <label className="flex flex-col gap-1 text-2xs text-muted">
              Authorized Password Hash (Optional — Local RockYou Audit)
              <div className="flex gap-2">
                <input
                  value={passwordHash}
                  onChange={(e) => setPasswordHash(e.target.value)}
                  placeholder="e.g. 5f4dcc3b5aa765d61d8327deb882cf99"
                  className="h-8 flex-1 rounded border border-line bg-surface px-2.5 font-mono text-xs text-ink outline-none placeholder:text-faint focus:border-accent"
                />
                <button
                  type="button"
                  onClick={() => setPasswordHash("5f4dcc3b5aa765d61d8327deb882cf99")}
                  className="rounded border border-line bg-surface px-2 py-1 font-mono text-2xs text-muted hover:text-ink"
                  title="Load MD5 of 'password' for demo"
                >
                  Sample Hash
                </button>
              </div>
            </label>
          </div>

          <div className="mt-1 flex flex-wrap items-center justify-between gap-3 pt-1 border-t border-line/60">
            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                onClick={runAssessment}
                disabled={busy || halted || !target.trim()}
                title={halted ? "Kill switch engaged — re-arm range first" : undefined}
              >
                <Icon name="play" size={13} />
                {busy ? "Assessing Target…" : "RUN ASSESSMENT"}
              </Button>

              {busy && (
                <Button variant="danger" onClick={handleStop}>
                  <Icon name="power" size={12} />
                  Stop / Kill
                </Button>
              )}

              <button
                type="button"
                onClick={() => setShowSingleTtp(!showSingleTtp)}
                className="text-2xs font-mono text-muted hover:text-ink underline ml-2"
              >
                {showSingleTtp ? "Hide Single TTP Launcher" : "Individual TTP Launcher"}
              </button>
            </div>

            <div className="font-mono text-2xs text-faint">
              RFC1918 or Tailnet peers only · Non-destructive · Zero external attacks
            </div>
          </div>
        </div>

        {/* Dedicated Target VM Open Ports Display */}
        <div className="rounded border border-line bg-canvas p-3 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Icon name="pulse" size={14} />
              <span className="text-xs font-semibold uppercase tracking-wide text-ink">
                Target VM Open Ports & Services
              </span>
            </div>
            <span className="font-mono text-2xs text-muted">
              Host: <span className="text-ink">{target || "None"}</span>
            </span>
          </div>

          {openPorts.length > 0 ? (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 pt-1">
              {openPorts.map((p) => (
                <div
                  key={p.port}
                  className="flex items-center justify-between rounded border border-ok/40 bg-ok/10 px-2.5 py-1.5 font-mono text-xs"
                >
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold text-ok">{p.port}</span>
                    <span className="text-2xs text-ink uppercase tracking-wide">/ {p.service}</span>
                  </div>
                  {p.latency_ms != null && (
                    <span className="text-2xs text-muted">{p.latency_ms} ms</span>
                  )}
                </div>
              ))}
            </div>
          ) : result ? (
            <div className="rounded border border-line bg-surface p-2.5 text-center text-xs text-muted">
              {result.summary?.target_online === false ? (
                <span className="text-amber-500 font-mono font-semibold">
                  TARGET OFFLINE — 0 open service ports responding on {target}
                </span>
              ) : (
                <span>No open service ports detected in standard recon port list.</span>
              )}
            </div>
          ) : (
            <div className="rounded border border-line bg-surface p-2.5 text-center text-xs text-muted">
              Click &quot;RUN ASSESSMENT&quot; to probe and display open service ports on the target VM.
            </div>
          )}
        </div>

        {/* Live Step-by-Step Checklist */}
        <div className="flex flex-col gap-2 rounded border border-line bg-surface p-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-ink">
              Assessment Execution Checklist
            </span>
            {result && (
              <span className="font-mono text-2xs text-muted">
                Duration: <span className="text-ink">{result.summary?.duration_seconds ?? "—"}s</span> · Execution:{" "}
                <span className="text-ink">{result.assessment_id?.slice(0, 8)}…</span>
              </span>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            {steps.map((step, idx) => {
              const isExpanded = expandedStep === step.id;
              const hasData = Boolean(step.data && Object.keys(step.data).length > 0);
              return (
                <div
                  key={step.id}
                  className="rounded border border-line/60 bg-canvas p-2.5 flex flex-col gap-1 text-xs"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-2xs text-faint">#{idx + 1}</span>
                      <span className="font-semibold text-ink">{step.name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {step.duration_seconds != null && (
                        <span className="font-mono text-2xs text-faint">{step.duration_seconds}s</span>
                      )}
                      <Pill tone={stepTone(step.status)}>{step.status}</Pill>
                    </div>
                  </div>

                  {step.details && (
                    <div className="text-2xs text-muted mt-0.5 font-mono">{step.details}</div>
                  )}

                  {hasData && (
                    <div className="mt-1">
                      <button
                        type="button"
                        onClick={() => setExpandedStep(isExpanded ? null : step.id)}
                        className="text-2xs font-mono text-muted hover:text-ink underline"
                      >
                        {isExpanded ? "Hide payload" : "Show payload"}
                      </button>
                      {isExpanded && (
                        <pre className="mt-1 max-h-36 overflow-auto rounded border border-line bg-surface p-2 font-mono text-2xs text-ink">
                          {JSON.stringify(step.data, null, 2)}
                        </pre>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Optional: Individual SOC Trigger Mode */}
        {showSingleTtp && (
          <div className="flex flex-col gap-2 rounded border border-amber-500/40 bg-amber-500/5 p-3 text-xs">
            <span className="font-semibold uppercase tracking-wide text-amber-500">
              Individual SOC Signature Generator
            </span>
            <div className="flex flex-wrap items-center gap-2">
              <Segmented
                value={singleKind}
                onChange={setSingleKind}
                options={KIND_LIST.map((k) => ({ value: k.kind, label: k.name }))}
              />
              <Button
                variant="primary"
                onClick={runSingleTtp}
                disabled={busy || halted || !target.trim()}
              >
                <Icon name="pulse" size={12} />
                Generate Single TTP
              </Button>
            </div>
            {singleSoc && (
              <div className="mt-2 rounded border border-line bg-canvas p-2 font-mono text-2xs text-ink">
                <div>
                  <span className="text-muted">Detectable as: </span>
                  {String(singleSoc.detectable_as || "—")}
                </div>
                <div className="mt-1 text-ok">{String(singleSoc.note || "")}</div>
              </div>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}
