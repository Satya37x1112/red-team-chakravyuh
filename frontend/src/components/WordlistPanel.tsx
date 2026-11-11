import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useLiveContext } from "../live-context";
import { Button, Empty, Icon, Panel, Pill, Tag } from "./ui";

interface RockYouMeta {
  available: boolean;
  path?: string;
  filename?: string;
  format?: string;
  size_formatted?: string;
  size_bytes?: number;
  estimated_lines?: number;
  readable?: boolean;
  status?: string;
  status_message?: string;
}

export function WordlistPanel() {
  const { halted, notify } = useLiveContext();
  const [tab, setTab] = useState<"rockyou" | "offline" | "live">("rockyou");
  const [rockyou, setRockyou] = useState<RockYouMeta | null>(null);
  const [loadingMeta, setLoadingMeta] = useState(false);

  // Offline audit state
  const [inputHash, setInputHash] = useState("");
  const [detectedAlgos, setDetectedAlgos] = useState<string[]>([]);
  const [selectedAlgo, setSelectedAlgo] = useState("NTLM");
  const [candidateLimit, setCandidateLimit] = useState(100000);
  const [auditBusy, setAuditBusy] = useState(false);
  const [auditResult, setAuditResult] = useState<Record<string, unknown> | null>(null);
  const [auditError, setAuditError] = useState<string | null>(null);

  // Live validate state
  const [liveTarget, setLiveTarget] = useState("100.80.167.51");
  const [liveService, setLiveService] = useState("smb");
  const [liveAccount, setLiveAccount] = useState("labuser");
  const [livePasswords, setLivePasswords] = useState("Welcome1, Summer2026!, labpass");
  const [liveBusy, setLiveBusy] = useState(false);
  const [liveResult, setLiveResult] = useState<Record<string, unknown> | null>(null);
  const [liveError, setLiveError] = useState<string | null>(null);

  const loadRockYouStatus = useCallback(async () => {
    setLoadingMeta(true);
    try {
      const res = await api.authRockyouStatus();
      setRockyou(res as unknown as RockYouMeta);
    } catch {
      setRockyou({
        available: false,
        status: "NOT_FOUND",
        status_message: "RockYou wordlist could not be inspected.",
      });
    } finally {
      setLoadingMeta(false);
    }
  }, []);

  useEffect(() => {
    loadRockYouStatus();
  }, [loadRockYouStatus]);

  // Handle hash identification when input changes
  useEffect(() => {
    const trimmed = inputHash.trim();
    if (trimmed.length >= 32) {
      api
        .authIdentifyHash(trimmed)
        .then((res) => {
          const algos = (res.detected_algorithms as string[]) || [];
          setDetectedAlgos(algos);
          if (algos.length && !algos.includes(selectedAlgo)) {
            setSelectedAlgo(algos[0]);
          }
        })
        .catch(() => setDetectedAlgos([]));
    } else {
      setDetectedAlgos([]);
    }
  }, [inputHash, selectedAlgo]);

  const runOfflineAudit = async () => {
    if (!inputHash.trim()) return;
    setAuditBusy(true);
    setAuditError(null);
    setAuditResult(null);
    try {
      const res = await api.authOfflineAudit({
        hash: inputHash.trim(),
        algorithm: selectedAlgo,
        max_candidates: candidateLimit,
        timeout_seconds: 30,
      });
      setAuditResult(res);
      notify({
        tone: res.matched ? "ok" : "info",
        title: res.matched ? "Password Confirmed" : "Audit Complete",
        body: String(res.message),
      });
    } catch (e) {
      setAuditError((e as Error).message);
    } finally {
      setAuditBusy(false);
    }
  };

  const runLiveValidation = async () => {
    setLiveBusy(true);
    setLiveError(null);
    setLiveResult(null);
    try {
      const pwList = livePasswords
        .split(",")
        .map((p) => p.trim())
        .filter(Boolean)
        .slice(0, 3);

      const res = await api.authLiveValidate({
        target: liveTarget.trim(),
        service: liveService.trim(),
        account: liveAccount.trim(),
        passwords: pwList,
      });
      setLiveResult(res);
      notify({
        tone: res.authenticated ? "ok" : res.outcome === "LOCKOUT_HALT" ? "crit" : "info",
        title: "Live Authentication Result",
        body: String(res.message),
      });
    } catch (e) {
      setLiveError((e as Error).message);
    } finally {
      setLiveBusy(false);
    }
  };

  return (
    <Panel
      title="Authentication & Password Auditing"
      sub="Genuine RockYou integration, offline hash auditing, and bounded live authentication validation."
      actions={
        <div className="flex items-center gap-2">
          {rockyou?.available ? (
            <Pill tone="ok">ROCKYOU AVAILABLE</Pill>
          ) : (
            <Pill tone="warn">WORDLIST MISSING</Pill>
          )}
          <Tag>{tab.toUpperCase()}</Tag>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        {/* Navigation Tabs */}
        <div className="flex border-b border-line pb-2">
          <div className="flex gap-2">
            <button
              onClick={() => setTab("rockyou")}
              className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                tab === "rockyou"
                  ? "bg-accent text-canvas"
                  : "bg-surface text-muted hover:text-ink"
              }`}
            >
              Wordlist Status
            </button>
            <button
              onClick={() => setTab("offline")}
              className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                tab === "offline"
                  ? "bg-accent text-canvas"
                  : "bg-surface text-muted hover:text-ink"
              }`}
            >
              Offline Hash Audit
            </button>
            <button
              onClick={() => setTab("live")}
              className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                tab === "live"
                  ? "bg-accent text-canvas"
                  : "bg-surface text-muted hover:text-ink"
              }`}
            >
              Live Validation (Max 3)
            </button>
          </div>
        </div>

        {/* Tab 1: Wordlist Status */}
        {tab === "rockyou" && (
          <div className="flex flex-col gap-3 text-xs">
            {loadingMeta ? (
              <Empty>Detecting local wordlists…</Empty>
            ) : rockyou ? (
              <div className="flex flex-col gap-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded border border-line bg-canvas p-3">
                    <div className="text-2xs uppercase tracking-wide text-muted">Detection Status</div>
                    <div className="mt-1 flex items-center gap-2">
                      <span className={`inline-block h-2 w-2 rounded-full ${rockyou.available ? "bg-ok" : "bg-crit"}`} />
                      <span className="font-mono text-sm text-ink">{rockyou.status}</span>
                    </div>
                    <p className="mt-1 text-2xs text-muted">{rockyou.status_message}</p>
                  </div>

                  <div className="rounded border border-line bg-canvas p-3">
                    <div className="text-2xs uppercase tracking-wide text-muted">Wordlist Metadata</div>
                    <div className="mt-1 font-mono text-sm text-ink">
                      {rockyou.size_formatted || "0 B"}
                      {rockyou.format && (
                        <span className="ml-2 font-sans text-xs text-muted">({rockyou.format})</span>
                      )}
                    </div>
                    <p className="mt-1 text-2xs text-muted">
                      {rockyou.estimated_lines
                        ? `~${rockyou.estimated_lines.toLocaleString()} canonical entries`
                        : "Lines counted on demand"}
                    </p>
                  </div>
                </div>

                <div className="rounded border border-line bg-canvas p-3">
                  <div className="text-2xs uppercase tracking-wide text-muted">Filesystem Location</div>
                  <code className="mt-1 block font-mono text-xs text-ink">{rockyou.path || "Not found"}</code>
                  <p className="mt-1.5 text-2xs text-faint">
                    RockYou is streamed securely in gzip chunks. Passwords are never echoed into logs or telemetry.
                  </p>
                </div>
              </div>
            ) : (
              <Empty>Wordlist status unavailable.</Empty>
            )}
          </div>
        )}

        {/* Tab 2: Offline Password Hash Audit */}
        {tab === "offline" && (
          <div className="flex flex-col gap-3 text-xs">
            <p className="text-muted">
              Audit an authorized password hash against RockYou. Passwords are confirmed only upon genuine hash match.
            </p>

            <div className="flex flex-col gap-2">
              <label className="flex flex-col gap-1 text-2xs text-muted">
                Authorized Hash (NTLM, SHA-256, MD5, SHA-1)
                <input
                  type="text"
                  placeholder="e.g. 8846f7eaee8fb117ad06bdd830b7586c or 2b576acbe6bcfda7294d6bd18041b8fe"
                  value={inputHash}
                  onChange={(e) => setInputHash(e.target.value)}
                  className="h-8 rounded border border-line bg-canvas px-2 font-mono text-xs text-ink"
                />
              </label>

              <div className="flex flex-wrap items-center gap-3">
                <label className="flex flex-col gap-1 text-2xs text-muted">
                  Algorithm
                  <select
                    value={selectedAlgo}
                    onChange={(e) => setSelectedAlgo(e.target.value)}
                    className="h-8 rounded border border-line bg-canvas px-2 font-mono text-xs text-ink"
                  >
                    <option value="NTLM">NTLM (Windows SAM/AD)</option>
                    <option value="SHA-256">SHA-256</option>
                    <option value="MD5">MD5</option>
                    <option value="SHA-1">SHA-1</option>
                    <option value="SHA-512">SHA-512</option>
                  </select>
                </label>

                <label className="flex flex-col gap-1 text-2xs text-muted">
                  Max Candidates (≤500,000)
                  <input
                    type="number"
                    min={100}
                    max={500000}
                    step={1000}
                    value={candidateLimit}
                    onChange={(e) => setCandidateLimit(Number(e.target.value))}
                    className="h-8 w-28 rounded border border-line bg-canvas px-2 font-mono text-xs text-ink"
                  />
                </label>

                {detectedAlgos.length > 0 && (
                  <div className="mt-4 flex items-center gap-1.5">
                    <span className="text-2xs text-muted">Detected:</span>
                    {detectedAlgos.map((a) => (
                      <span key={a} className="rounded border border-ok/40 bg-ok/10 px-1.5 py-0.5 font-mono text-2xs text-ok">
                        {a}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="mt-2 flex items-center gap-2">
                <Button
                  variant="primary"
                  onClick={runOfflineAudit}
                  disabled={auditBusy || halted || !inputHash.trim() || !rockyou?.available}
                >
                  <Icon name="key" size={13} />
                  {auditBusy ? "Auditing Dictionary…" : "Run Offline Hash Audit"}
                </Button>
                {halted && <Pill tone="crit">Range halted — Kill switch engaged</Pill>}
              </div>

              {auditError && (
                <div className="rounded border border-crit/40 bg-crit/10 p-2.5 text-xs text-crit">{auditError}</div>
              )}

              {auditResult && (
                <div className={`mt-2 rounded border p-3 ${auditResult.matched ? "border-ok/50 bg-ok/5" : "border-line bg-canvas"}`}>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className={`h-2.5 w-2.5 rounded-full ${auditResult.matched ? "bg-ok" : "bg-muted"}`} />
                      <span className="font-semibold text-ink">
                        {auditResult.matched ? "VERIFIED MATCH CONFIRMED" : "NO MATCH FOUND"}
                      </span>
                    </div>
                    <Tag>{String(auditResult.stop_reason)}</Tag>
                  </div>

                  <p className="mt-1.5 text-xs text-muted">{String(auditResult.message)}</p>

                  <div className="mt-2.5 grid grid-cols-2 gap-2 font-mono text-2xs sm:grid-cols-4">
                    <div>
                      <span className="text-muted">Algorithm:</span> <span className="text-ink">{String(auditResult.algorithm)}</span>
                    </div>
                    <div>
                      <span className="text-muted">Tested:</span> <span className="text-ink">{Number(auditResult.candidates_tested).toLocaleString()}</span>
                    </div>
                    <div>
                      <span className="text-muted">Duration:</span> <span className="text-ink">{String(auditResult.duration_seconds)}s</span>
                    </div>
                    <div>
                      <span className="text-muted">Wordlist:</span> <span className="text-ink">{String(auditResult.wordlist_source)}</span>
                    </div>
                  </div>

                  {Boolean(auditResult.matched && auditResult.recovered_plaintext) && (
                    <div className="mt-3 rounded border border-ok/30 bg-ok/10 p-2.5 font-mono text-xs">
                      <span className="text-muted">Recovered Password: </span>
                      <span className="font-bold text-ok">{String(auditResult.recovered_plaintext)}</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 3: Live Validation Mode */}
        {tab === "live" && (
          <div className="flex flex-col gap-3 text-xs">
            <div className="rounded border border-amber-500/40 bg-amber-500/5 p-2.5">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-amber-500">LIVE LAB VALIDATION MODE</span>
                <Pill tone="warn">MAX 3 ATTEMPTS</Pill>
              </div>
              <p className="mt-1 text-2xs text-muted">
                Restricted to authorized lab target and dedicated test accounts only. Halts immediately on success or lockout warning.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <label className="flex flex-col gap-1 text-2xs text-muted">
                Authorized Target IP
                <input
                  type="text"
                  value={liveTarget}
                  onChange={(e) => setLiveTarget(e.target.value)}
                  className="h-8 rounded border border-line bg-canvas px-2 font-mono text-xs text-ink"
                />
              </label>

              <label className="flex flex-col gap-1 text-2xs text-muted">
                Protocol / Service
                <select
                  value={liveService}
                  onChange={(e) => setLiveService(e.target.value)}
                  className="h-8 rounded border border-line bg-canvas px-2 font-mono text-xs text-ink"
                >
                  <option value="smb">SMB (Port 445)</option>
                  <option value="ssh">SSH (Port 22)</option>
                  <option value="rdp">RDP (Port 3389)</option>
                  <option value="winrm">WinRM (Port 5985)</option>
                </select>
              </label>

              <label className="flex flex-col gap-1 text-2xs text-muted">
                Test Account (Non-Admin Only)
                <input
                  type="text"
                  value={liveAccount}
                  onChange={(e) => setLiveAccount(e.target.value)}
                  className="h-8 rounded border border-line bg-canvas px-2 font-mono text-xs text-ink"
                />
              </label>
            </div>

            <label className="flex flex-col gap-1 text-2xs text-muted">
              Candidate Passwords (≤3 comma-separated)
              <input
                type="text"
                value={livePasswords}
                onChange={(e) => setLivePasswords(e.target.value)}
                className="h-8 rounded border border-line bg-canvas px-2 font-mono text-xs text-ink"
              />
            </label>

            <div className="flex items-center gap-2">
              <Button
                variant="danger"
                onClick={runLiveValidation}
                disabled={liveBusy || halted || !liveTarget.trim() || !liveAccount.trim()}
              >
                <Icon name="play" size={13} />
                {liveBusy ? "Validating Target Auth…" : "Run Live Validation"}
              </Button>
              {halted && <Pill tone="crit">Range halted — Kill switch engaged</Pill>}
            </div>

            {liveError && (
              <div className="rounded border border-crit/40 bg-crit/10 p-2.5 text-xs text-crit">{liveError}</div>
            )}

            {liveResult && (
              <div className={`mt-2 rounded border p-3 ${liveResult.authenticated ? "border-ok/50 bg-ok/5" : "border-line bg-canvas"}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`h-2.5 w-2.5 rounded-full ${liveResult.authenticated ? "bg-ok" : "bg-muted"}`} />
                    <span className="font-semibold text-ink">{String(liveResult.outcome)}</span>
                  </div>
                  <Tag>{String(liveResult.stop_reason)}</Tag>
                </div>
                <p className="mt-1 text-xs text-muted">{String(liveResult.message)}</p>

                <div className="mt-2.5 grid grid-cols-2 gap-2 font-mono text-2xs sm:grid-cols-4">
                  <div>
                    <span className="text-muted">Target:</span> <span className="text-ink">{String(liveResult.target)}</span>
                  </div>
                  <div>
                    <span className="text-muted">Account:</span> <span className="text-ink">{String(liveResult.account_masked)}</span>
                  </div>
                  <div>
                    <span className="text-muted">Attempts:</span> <span className="text-ink">{String(liveResult.attempt_count)} / {String(liveResult.max_attempts_cap)}</span>
                  </div>
                  <div>
                    <span className="text-muted">Duration:</span> <span className="text-ink">{String(liveResult.duration_seconds)}s</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}
