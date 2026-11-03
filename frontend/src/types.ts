export interface ProcessInfo {
  pid: number;
  name: string;
  username: string | null;
  memory_mb: number | null;
}

export interface NetworkInterface {
  name: string;
  addresses: string[];
  is_up: boolean | null;
}

export interface NetworkConnection {
  laddr: string | null;
  raddr: string | null;
  status: string | null;
  pid: number | null;
}

export interface Telemetry {
  collected_at: string;
  source: string;
  available: boolean;
  error: string | null;
  hostname: string | null;
  os_name: string | null;
  logged_in_user: string | null;
  uptime_seconds: number | null;
  cpu_percent: number | null;
  memory_percent: number | null;
  memory_total_mb: number | null;
  disk_percent: number | null;
  processes: ProcessInfo[];
  process_count: number | null;
  interfaces: NetworkInterface[];
  connections: NetworkConnection[];
  windows_events: unknown[];
}

export interface Decision {
  status: "ok" | "heuristic" | "llm_unavailable";
  parameter: string;
  decision: number | null;
  reasoning: string;
  observations_used: string[];
  confidence: string;
  model: string | null;
}

export type Kind = "ddos" | "bruteforce" | "ratuba";

export interface SessionBrief {
  id: string;
  label: string;
  kind: Kind;
  state: string;
  target_id: string;
  started_at: string;
  ended_at: string | null;
}

export interface AgentEventRow {
  id: string;
  created_at: string;
  event_type: string;
  phase: string | null;
  message: string;
  payload: Record<string, unknown>;
}

export interface SessionDetail extends SessionBrief {
  events: AgentEventRow[];
}

export interface LiveEvent {
  type: string;
  ts?: string;
  payload: Record<string, unknown> & { phase?: string | null; message?: string; session_id?: string };
}

export interface HistoryPoint {
  t: string;
  cpu: number | null;
  mem: number | null;
  disk: number | null;
  procs: number | null;
}

export type MetricMap = Partial<Record<"cpu_percent" | "memory_percent" | "disk_percent" | "process_count", number | null>>;

export interface AnalyticsRow {
  id: string;
  label: string;
  kind: Kind;
  state: string;
  started_at: string;
  duration_s: number | null;
  parameter: string | null;
  decision: number | null;
  decision_source: string | null;
  adapted: number | null;
  risk_score: number | null;
  before: MetricMap | null;
  after: MetricMap | null;
  deltas: MetricMap | null;
  anomalies: { category: string | null; score: number | null; message: string }[];
}
