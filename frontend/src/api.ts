import type {
  AnalyticsRow,
  ArtifactDetail,
  ArtifactRow,
  CalderaAnalysis,
  CalderaSample,
  CentralSummary,
  Decision,
  HistoryPoint,
  IntegrationStatus,
  Kind,
  LlmConfig,
  LlmTestResult,
  OperationDetail,
  OperationPlanPreview,
  OperationSummary,
  PentestReport,
  RemoteAccessResult,
  RemoteAccessStatus,
  SessionBrief,
  SessionDetail,
  SmartAnalysis,
  Telemetry,
  VervetEmulateResult,
} from "./types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

const post = (url: string, body?: unknown) =>
  fetch(url, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

export const api = {
  health: () =>
    fetch("/api/health").then(json<{ status: string; telemetry_source: string; halted: boolean }>),
  telemetry: () => fetch("/api/telemetry/latest").then(json<Telemetry>),
  history: (minutes: number) => fetch(`/api/telemetry/history?minutes=${minutes}`).then(json<HistoryPoint[]>),
  probeTarget: (target: string) =>
    post("/api/telemetry/probe", { target }).then(json<Record<string, unknown>>),
  analytics: () => fetch("/api/analytics/sessions").then(json<AnalyticsRow[]>),
  decision: (kind: Kind) => fetch(`/api/decision/${kind}`).then(json<Decision>),
  sessions: () => fetch("/api/sessions").then(json<SessionBrief[]>),
  session: (id: string) => fetch(`/api/sessions/${id}`).then(json<SessionDetail>),
  result: (id: string) =>
    fetch(`/api/results/${id}`).then((r) => (r.ok ? (r.json() as Promise<Record<string, unknown>>) : null)),
  socActivity: (body: { kind: string; target: string }) =>
    post("/api/attacks/soc-activity", body).then(json<Record<string, unknown>>),
  start: (kind: Kind) =>
    post("/api/attacks/start", { kind }).then(
      json<{ session_id: string; label: string; kind: Kind; state: string }>
    ),
  killSwitch: () => post("/api/killswitch").then(json<{ halted: boolean; killed: string[] }>),
  rearm: (adminToken: string) =>
    post("/api/killswitch/reset", { admin_token: adminToken }).then(json<{ halted: boolean }>),

  integrations: () => fetch("/api/integrations").then(json<IntegrationStatus[]>),
  calderaSamples: () => fetch("/api/integrations/caldera/samples").then(json<CalderaSample[]>),
  calderaAnalyze: (body: { sample?: string; reports?: unknown[]; ai?: boolean }) =>
    post("/api/integrations/caldera/analyze", body).then(json<CalderaAnalysis>),
  vervetDescribe: () => fetch("/api/integrations/vervet/describe").then(json<Record<string, unknown>>),
  vervetEmulate: (body: { target: string; technique?: string }) =>
    post("/api/integrations/vervet/emulate", body).then(json<VervetEmulateResult>),
  locustRun: (body: { users?: number; spawn_rate?: number; run_seconds?: number; target_url?: string }) =>
    post("/api/integrations/locust/run", body).then(json<Record<string, unknown>>),
  locustSimulate: (body: { users?: number; spawn_rate?: number; run_seconds?: number }) =>
    post("/api/integrations/locust/simulate", body).then(json<Record<string, unknown>>),
  hydraRun: (body: { tasks?: number; run_seconds?: number }) =>
    post("/api/integrations/hydra/run", body).then(json<Record<string, unknown>>),

  pentestgptIngest: () =>
    post("/api/integrations/pentestgpt/ingest").then(json<{ runs_found: number; added: number }>),

  // Section 3: centralized AI planner / operations
  operationPlan: (body: { objective: string; module_hint?: string }) =>
    post("/api/operations/plan", body).then(json<OperationPlanPreview>),
  startOperation: (body: { objective: string; module_hint?: string; max_iterations?: number }) =>
    post("/api/operations", body).then(json<OperationDetail>),
  listOperations: () => fetch("/api/operations").then(json<OperationSummary[]>),
  getOperation: (id: string) => fetch(`/api/operations/${id}`).then(json<OperationDetail>),

  // Stage 1: generic LLM provider config (API key never returned by the backend)
  llmConfig: () => fetch("/api/llm/config").then(json<LlmConfig>),
  updateLlmConfig: (body: { provider?: string; base_url?: string; model?: string; timeout?: number; api_key?: string }) =>
    post("/api/llm/config", body).then(json<LlmConfig>),
  testLlm: () => post("/api/llm/test").then(json<LlmTestResult>),

  // Section 4: Credentialed Remote Access (RAT alternative)
  remoteAccessStatus: () => fetch("/api/integrations/remote_access").then(json<RemoteAccessStatus>),
  remoteAccessRun: (body: { operation: string; run_seconds?: number }) =>
    post("/api/integrations/remote_access/run", body).then(json<RemoteAccessResult>),

  // Authentication Testing & RockYou / Offline Auditing
  authRockyouStatus: () => fetch("/api/auth/rockyou/status").then(json<Record<string, unknown>>),
  authIdentifyHash: (hash: string) => post("/api/auth/identify-hash", { hash }).then(json<Record<string, unknown>>),
  authOfflineAudit: (body: { hash: string; algorithm?: string; max_candidates?: number; timeout_seconds?: number }) =>
    post("/api/auth/offline-audit", body).then(json<Record<string, unknown>>),
  authLiveValidate: (body: { target: string; service?: string; account?: string; passwords?: string[]; port?: number }) =>
    post("/api/auth/live-validate", body).then(json<Record<string, unknown>>),

  // Remote Data Transfer & Windows Receiver
  transferCheckReceiver: (body: { target_url: string; auth_token?: string }) =>
    post("/api/transfer/receiver/check", body).then(json<Record<string, unknown>>),
  transferListFiles: () =>
    fetch("/api/transfer/files").then(json<Array<{ name: string; path: string; size_bytes: number }>>),
  transferSend: (body: { file_path: string; target_url: string; auth_token: string; destination_filename?: string }) =>
    post("/api/transfer/send", body).then(json<Record<string, unknown>>),

  // One-Click Orchestrated Assessment
  assessmentRun: (body: { target: string; password_hash?: string }) =>
    post("/api/assessment/run", body).then(json<Record<string, unknown>>),
  assessmentLatest: () =>
    fetch("/api/assessment/latest").then((r) => (r.ok ? (r.json() as Promise<Record<string, unknown> | null>) : null)),

  central: () => fetch("/api/central/summary").then(json<CentralSummary>),
  report: () => fetch("/api/central/report").then(json<PentestReport>),
  analysis: () => fetch("/api/central/analysis").then(json<SmartAnalysis>),
  artifacts: (integration?: string) =>
    fetch(`/api/integrations/artifacts${integration ? `?integration=${integration}` : ""}`).then(json<ArtifactRow[]>),
  artifact: (id: string) => fetch(`/api/integrations/artifacts/${id}`).then(json<ArtifactDetail>),
};
