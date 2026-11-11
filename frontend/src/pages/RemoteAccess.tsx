import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useLiveContext } from "../live-context";
import { Button, Empty, Icon, Panel, Pill, SectionLabel, Tag } from "../components/ui";
import type { RemoteAccessResult, RemoteAccessStatus } from "../types";
import type { StateTone } from "../lib";

function statusTone(s: string | undefined): StateTone {
  if (s === "success" || s === "COMPLETED") return "ok";
  if (s === "auth_failed" || s === "unreachable" || s === "timed_out" || s === "INTEGRITY_MISMATCH") return "crit";
  if (s === "reachable_no_auth") return "warn";
  return "muted";
}

interface TransferFileItem {
  name: string;
  path: string;
  size_bytes: number;
}

export function RemoteAccess() {
  const { halted, notify } = useLiveContext();
  const [status, setStatus] = useState<RemoteAccessStatus | null>(null);
  const [operation, setOperation] = useState<string>("");
  const [result, setResult] = useState<RemoteAccessResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Data transfer state
  const [targetUrl, setTargetUrl] = useState("http://100.80.167.51:8090");
  const [authToken, setAuthToken] = useState("Chakravyuh-Lab-Auth-Token-2026");
  const [receiverCheck, setReceiverCheck] = useState<Record<string, unknown> | null>(null);
  const [checkingReceiver, setCheckingReceiver] = useState(false);
  const [availableFiles, setAvailableFiles] = useState<TransferFileItem[]>([]);
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [transferring, setTransferring] = useState(false);
  const [transferResult, setTransferResult] = useState<Record<string, unknown> | null>(null);
  const [transferError, setTransferError] = useState<string | null>(null);

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

  const loadFiles = useCallback(() => {
    api
      .transferListFiles()
      .then((files) => {
        setAvailableFiles(files);
        if (files.length > 0 && !selectedFile) {
          setSelectedFile(files[0].path);
        }
      })
      .catch(() => undefined);
  }, [selectedFile]);

  useEffect(() => {
    loadStatus();
    loadFiles();
  }, [loadStatus, loadFiles]);

  const ops = status?.detail.operations ?? [];
  const descriptions = status?.detail.operation_descriptions ?? {};
  const runnable = status?.detail.runnable === true;

  const runOperation = async () => {
    if (!operation) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.remoteAccessRun({ operation }));
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setBusy(false);
    }
  };

  const handleCheckReceiver = async () => {
    setCheckingReceiver(true);
    setTransferError(null);
    try {
      const res = await api.transferCheckReceiver({
        target_url: targetUrl.trim(),
        auth_token: authToken.trim(),
      });
      setReceiverCheck(res);
      notify({
        tone: res.reachable ? "ok" : "info",
        title: "Receiver Probe",
        body: res.reachable
          ? `Receiver at ${targetUrl} is online (Authenticated: ${res.authenticated ? "Yes" : "No"})`
          : `Receiver unreachable: ${res.error || "Connection failed"}`,
      });
    } catch (e) {
      setReceiverCheck({ reachable: false, error: (e as Error).message });
      setTransferError((e as Error).message);
    } finally {
      setCheckingReceiver(false);
    }
  };

  const handleSendTransfer = async () => {
    if (!selectedFile) return;
    setTransferring(true);
    setTransferError(null);
    setTransferResult(null);
    try {
      const res = await api.transferSend({
        file_path: selectedFile,
        target_url: targetUrl.trim(),
        auth_token: authToken.trim(),
      });
      setTransferResult(res);
      notify({
        tone: res.integrity_verified ? "ok" : "crit",
        title: res.integrity_verified ? "Transfer Verified" : "Integrity Mismatch",
        body: `File ${res.filename} transferred. SHA-256 match: ${res.integrity_verified ? "YES" : "NO"}`,
      });
    } catch (e) {
      setTransferError((e as Error).message);
    } finally {
      setTransferring(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {/* 1. Header & Remote Access Status */}
      <Panel
        title="Remote Access & Authenticated Data Transfer"
        sub="Controlled Windows post-exploitation demonstration: benign read-only NetExec administration and operator-controlled authenticated file transfer with SHA-256 verification."
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

      {/* 2. Genuine Remote File Transfer Panel */}
      <Panel
        title="Authenticated Remote File Transfer"
        sub="Transparent operator-controlled data transfer to the Windows lab receiver with SHA-256 integrity verification."
        actions={
          <div className="flex items-center gap-2">
            {receiverCheck?.reachable ? (
              <Pill tone="ok">RECEIVER ONLINE</Pill>
            ) : (
              <Pill tone="warn">RECEIVER UNCHECKED</Pill>
            )}
            <Tag>SHA-256 VERIFIED</Tag>
          </div>
        }
      >
        <div className="flex flex-col gap-4 text-xs">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-2xs text-muted">
              Windows Receiver URL
              <input
                type="text"
                value={targetUrl}
                onChange={(e) => setTargetUrl(e.target.value)}
                placeholder="http://100.80.167.51:8090"
                className="h-8 rounded border border-line bg-canvas px-2 font-mono text-xs text-ink"
              />
            </label>

            <label className="flex flex-col gap-1 text-2xs text-muted">
              Receiver Auth Token
              <input
                type="password"
                value={authToken}
                onChange={(e) => setAuthToken(e.target.value)}
                className="h-8 rounded border border-line bg-canvas px-2 font-mono text-xs text-ink"
              />
            </label>
          </div>

          <div className="flex items-center gap-2">
            <Button
              onClick={handleCheckReceiver}
              disabled={checkingReceiver || halted || !targetUrl.trim()}
            >
              <Icon name="pulse" size={13} />
              {checkingReceiver ? "Checking Receiver…" : "Check Receiver Connectivity"}
            </Button>
          </div>

          {receiverCheck && (
            <div className={`rounded border p-3 ${receiverCheck.reachable ? "border-ok/40 bg-ok/5" : "border-crit/40 bg-crit/5"}`}>
              <div className="flex items-center justify-between">
                <span className="font-semibold text-ink">
                  {receiverCheck.reachable ? "Receiver Ready & Accessible" : "Receiver Connection Failed"}
                </span>
                <Pill tone={receiverCheck.reachable ? "ok" : "crit"}>
                  {receiverCheck.reachable ? "READY" : "UNREACHABLE"}
                </Pill>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 font-mono text-2xs sm:grid-cols-3">
                <div>
                  <span className="text-muted">Target: </span>
                  <span className="text-ink">{String(receiverCheck.target_url || targetUrl)}</span>
                </div>
                <div>
                  <span className="text-muted">Authenticated: </span>
                  <span className={receiverCheck.authenticated ? "text-ok" : "text-warn"}>
                    {receiverCheck.authenticated ? "Valid Token" : "Missing / Denied"}
                  </span>
                </div>
                <div>
                  <span className="text-muted">Latency: </span>
                  <span className="text-ink">{String(receiverCheck.latency_ms ?? "—")} ms</span>
                </div>
              </div>
              {Boolean(receiverCheck.destination_directory) && (
                <div className="mt-1.5 font-mono text-2xs text-muted">
                  Storage Dir: {String(receiverCheck.destination_directory)}
                </div>
              )}
            </div>
          )}

          <div className="border-t border-line pt-3">
            <SectionLabel index="02" label="Select File to Transfer" />
            <div className="mt-2 grid gap-3 sm:grid-cols-2">
              <label className="flex flex-col gap-1 text-2xs text-muted">
                Source File (Max 10 MB)
                <select
                  value={selectedFile}
                  onChange={(e) => setSelectedFile(e.target.value)}
                  className="h-8 rounded border border-line bg-canvas px-2 font-mono text-xs text-ink"
                >
                  {availableFiles.map((f) => (
                    <option key={f.path} value={f.path}>
                      {f.name} ({f.size_bytes} B)
                    </option>
                  ))}
                </select>
              </label>

              <div className="flex items-end">
                <Button
                  variant="primary"
                  onClick={handleSendTransfer}
                  disabled={transferring || halted || !selectedFile || !targetUrl.trim()}
                >
                  <Icon name="download" size={13} />
                  {transferring ? "Transferring & Verifying…" : "Send Authenticated File"}
                </Button>
              </div>
            </div>
          </div>

          {transferError && (
            <div className="rounded border border-crit/40 bg-crit/10 p-2.5 text-xs text-crit">{transferError}</div>
          )}

          {transferResult && (
            <div className={`rounded border p-3.5 ${transferResult.integrity_verified ? "border-ok/50 bg-ok/5" : "border-crit/50 bg-crit/5"}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`h-2.5 w-2.5 rounded-full ${transferResult.integrity_verified ? "bg-ok" : "bg-crit"}`} />
                  <span className="font-semibold text-ink">
                    {transferResult.integrity_verified ? "INTEGRITY VERIFIED — SHA-256 MATCH" : "INTEGRITY MISMATCH"}
                  </span>
                </div>
                <Pill tone={transferResult.integrity_verified ? "ok" : "crit"}>
                  {transferResult.integrity_verified ? "VERIFIED" : "FAILED"}
                </Pill>
              </div>

              <div className="mt-2.5 flex flex-col gap-1.5 font-mono text-2xs">
                <div>
                  <span className="text-muted">Filename: </span>
                  <span className="font-bold text-ink">{String(transferResult.filename)}</span>
                  <span className="ml-3 text-muted">Size: </span>
                  <span className="text-ink">{String(transferResult.size_bytes)} bytes</span>
                  <span className="ml-3 text-muted">Duration: </span>
                  <span className="text-ink">{String(transferResult.duration_seconds)}s</span>
                </div>
                <div>
                  <span className="text-muted">Pre-Transfer SHA-256:  </span>
                  <span className="text-ink">{String(transferResult.pre_transfer_sha256)}</span>
                </div>
                <div>
                  <span className="text-muted">Post-Receipt SHA-256: </span>
                  <span className="text-ink">{String(transferResult.post_transfer_sha256)}</span>
                </div>
                {Boolean(transferResult.destination_path) && (
                  <div>
                    <span className="text-muted">Windows Target Path: </span>
                    <span className="text-ink">{String(transferResult.destination_path)}</span>
                  </div>
                )}
              </div>

              {Boolean(transferResult.uba_anomaly) && (
                <div className="mt-3 rounded border border-accent/40 bg-accent/5 p-2 text-2xs">
                  <span className="font-semibold uppercase tracking-wide text-accent">UBA Anomaly Logged: </span>
                  <span className="text-muted">
                    {String((transferResult.uba_anomaly as Record<string, unknown>).description)}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      </Panel>

      {/* 3. Approved Operations (NetExec Remote Administration) */}
      <Panel
        title="Approved Remote Operations (NetExec)"
        sub="Select one identifier. Fixed, read-only implementations — never commands."
      >
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
              <Button variant="primary" onClick={runOperation} disabled={busy || halted || !operation}>
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

      {/* 4. Operation Result */}
      {result && (
        <Panel title="Operation Result" sub="Measured facts from the actual operation — no fabricated output.">
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
