import type {
  AnalyticsRow,
  Decision,
  HistoryPoint,
  Kind,
  SessionBrief,
  SessionDetail,
  Telemetry,
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
};
