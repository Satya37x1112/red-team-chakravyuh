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
  analytics: () => fetch("/api/analytics/sessions").then(json<AnalyticsRow[]>),
  decision: (kind: Kind) => fetch(`/api/decision/${kind}`).then(json<Decision>),
  sessions: () => fetch("/api/sessions").then(json<SessionBrief[]>),
  session: (id: string) => fetch(`/api/sessions/${id}`).then(json<SessionDetail>),
  result: (id: string) =>
    fetch(`/api/results/${id}`).then((r) => (r.ok ? (r.json() as Promise<Record<string, unknown>>) : null)),
  start: (kind: Kind) =>
    post("/api/attacks/start", { kind }).then(
      json<{ session_id: string; label: string; kind: Kind; state: string }>
    ),
  killSwitch: () => post("/api/killswitch").then(json<{ halted: boolean; killed: string[] }>),
  rearm: () => post("/api/killswitch/reset").then(json<{ halted: boolean }>),

  integrations: () => fetch("/api/integrations").then(json<IntegrationStatus[]>),
  calderaSamples: () => fetch("/api/integrations/caldera/samples").then(json<CalderaSample[]>),
  calderaAnalyze: (body: { sample?: string; reports?: unknown[]; ai?: boolean }) =>
    post("/api/integrations/caldera/analyze", body).then(json<CalderaAnalysis>),
  vervetDescribe: () => fetch("/api/integrations/vervet/describe").then(json<Record<string, unknown>>),
  vervetEmulate: (body: { target: string; technique?: string }) =>
    post("/api/integrations/vervet/emulate", body).then(json<VervetEmulateResult>),
  locustRun: (body: { users?: number; spawn_rate?: number; run_seconds?: number }) =>
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

  central: () => fetch("/api/central/summary").then(json<CentralSummary>),
  report: () => fetch("/api/central/report").then(json<PentestReport>),
  analysis: () => fetch("/api/central/analysis").then(json<SmartAnalysis>),
  artifacts: (integration?: string) =>
    fetch(`/api/integrations/artifacts${integration ? `?integration=${integration}` : ""}`).then(json<ArtifactRow[]>),
  artifact: (id: string) => fetch(`/api/integrations/artifacts/${id}`).then(json<ArtifactDetail>),
};
