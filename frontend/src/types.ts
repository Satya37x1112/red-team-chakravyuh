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

export interface IntegrationStatus {
  name: string;
  title: string;
  category: "analysis" | "load-test" | "emulation" | "agent" | string;
  repo: string;
  available: boolean;
  reason: string;
  detail: Record<string, unknown>;
}

export interface CalderaSample {
  file: string;
  operation: string | null;
}

export interface CalderaStats {
  total_steps: number;
  success: number;
  failed: number;
  success_rate: number;
  distinct_techniques: number;
  distinct_tactics: number;
  techniques: { name: string; count: number }[];
  tactics: { name: string; count: number }[];
}

export interface CalderaStep {
  operation: string | null;
  agent: string | null;
  ability: string | null;
  technique_id: string | null;
  technique_name: string | null;
  tactic: string | null;
  status: "Success" | "Failed" | string;
  executor: string | null;
  platform: string | null;
  command: string | null;
}

export interface CalderaAnalysis {
  reports: Record<string, unknown>[];
  steps: CalderaStep[];
  stats: CalderaStats;
  ai: {
    status: "ok" | "skipped" | "unavailable" | string;
    model: string | null;
    report_markdown: string | null;
    errors: string[];
  };
}

export interface ArtifactRow {
  id: string;
  created_at: string;
  integration: string;
  kind: string;
  title: string;
  summary: string;
}

export interface ArtifactDetail extends ArtifactRow {
  payload: Record<string, unknown>;
}

export interface CentralSummary {
  telemetry: {
    available: boolean;
    source: string;
    hostname: string | null;
    os_name: string | null;
    logged_in_user: string | null;
    cpu_percent: number | null;
    memory_percent: number | null;
    disk_percent: number | null;
    process_count: number | null;
    collected_at: string | null;
  } | null;
  sessions: { total: number; by_state: Record<string, number> };
  integrations: { total: number; available: number; items: IntegrationStatus[] };
  artifacts: { total: number; by_integration: Record<string, number>; recent: ArtifactRow[] };
}

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
