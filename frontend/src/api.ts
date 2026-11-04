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
  PentestReport,
  SessionBrief,
  SessionDetail,
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

  pentestgptIngest: () =>
    post("/api/integrations/pentestgpt/ingest").then(json<{ runs_found: number; added: number }>),

  central: () => fetch("/api/central/summary").then(json<CentralSummary>),
  report: () => fetch("/api/central/report").then(json<PentestReport>),
  artifacts: (integration?: string) =>
    fetch(`/api/integrations/artifacts${integration ? `?integration=${integration}` : ""}`).then(json<ArtifactRow[]>),
  artifact: (id: string) => fetch(`/api/integrations/artifacts/${id}`).then(json<ArtifactDetail>),
};
