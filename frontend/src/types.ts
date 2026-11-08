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
  network: NetworkProbe | null;
}

export interface PortState {
  port: number;
  open: boolean;
  service: string | null;
  latency_ms: number | null;
}

export interface NetworkProbe {
  target: string | null;
  reachable: boolean;
  latency_ms: number | null;
  open_ports: number[];
  ports: PortState[];
  http_status: number | null;
  http_server: string | null;
  probed_at: string | null;
  complete: boolean;
  ports_probed: number;
  ports_total: number;
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

export interface SmartIssue {
  severity: string;
  title: string;
  evidence: string;
  attacker_note: string;
  recommendation: string;
}

export interface SmartAnalysis {
  headline: string | null;
  model: string | null;
  issue_count: number;
  severity_counts: Record<string, number>;
  hosts_scanned: string[];
  issues: SmartIssue[];
}

export interface VervetFinding {
  handle: string;
  kind: string | null;
  detail: string | null;
  target: string | null;
}

export interface VervetEmulateResult {
  target: string;
  technique: string;
  authority: string;
  engagement_id: string;
  receipt: Record<string, unknown>;
  findings: VervetFinding[];
  coverage: Record<string, unknown> | null;
  artifact_id?: string;
}

export interface ReportFinding {
  severity: string;
  title: string;
  target: string | null;
  detail: string;
  technique?: string | null;
  source: string;
  at: string;
}

export interface AttackTechnique {
  id: string;
  name: string | null;
  tactic: string | null;
  observations: number;
  sources: string[];
}

export interface PentestReport {
  meta: { title: string; generated_at: string; operator: string | null; console_host: string | null };
  scope: { targets: string[]; telemetry_host: string | null; os_name: string | null };
  summary: {
    total_tests: number;
    tools_used: Record<string, number>;
    finding_count: number;
    technique_count: number;
    severity_breakdown: Record<string, number>;
  };
  methodology: { tool: string; status: string; role: string }[];
  findings: ReportFinding[];
  attack_coverage: AttackTechnique[];
  timeline: { at: string; integration: string; kind: string; title: string; summary: string }[];
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

// --- Section 3: centralized AI planner / operations ---
export interface OperationGatewayDecision {
  approved: boolean;
  rejected?: boolean;
  reason: string;
  policy_id?: string;
  execution_id?: string | null;
  module?: string;
  target?: string;
  adapter?: string | null;
  validated_parameters?: Record<string, number>;
  timestamp?: string;
}

export interface OperationPlanPreview {
  planning_status: "ai" | "fallback" | "unavailable";
  model: string | null;
  prompt_version: string;
  reasoning: string;
  runnable_modules: string[];
  telemetry_scope: string;
  plan: Record<string, unknown> | null;
  gateway_decision: OperationGatewayDecision | null;
}

export interface OperationStep {
  index: number;
  plan_source: "ai" | "system" | "none";
  model: string | null;
  prompt_version: string | null;
  ai_output: Record<string, unknown>;
  validation_ok: boolean;
  validation_error: string | null;
  gateway_decision: OperationGatewayDecision | Record<string, never>;
  execution_id: string | null;
  execution_state: string | null;
  result_summary: string;
  analysis: {
    measured_facts?: string[];
    interpretation?: string;
    interpretation_source?: string;
    objective_met?: boolean;
  } & Record<string, unknown>;
  feedback_action: "CONTINUE" | "MODIFY" | "STOP" | null;
  feedback_reasoning: string;
}

export interface OperationSummary {
  id: string;
  objective: string;
  scenario_id: string;
  status: string;
  final_recommendation: string | null;
  iterations: number;
  created_at: string;
}

export interface OperationDetail extends OperationSummary {
  module_hint: string | null;
  ended_at: string | null;
  steps: OperationStep[];
}

// --- Section 4: Credentialed Remote Access (RAT alternative) ---
export interface RemoteAccessStatus {
  name: string;
  title: string;
  available: boolean;
  reason: string;
  detail: {
    enabled?: boolean;
    protocol?: string;
    target?: string | null;
    credentials_configured?: boolean;
    runnable?: boolean;
    operations?: string[];
    operation_descriptions?: Record<string, string>;
    caps?: { max_run_seconds?: number };
  };
}

export interface RemoteAccessResult {
  operation: string;
  target: string;
  protocol: string;
  status: string;
  measured: Record<string, unknown>;
  message: string;
  exit_code: number | null;
  timed_out: boolean;
  duration_seconds: number;
  execution_id?: string;
  execution_state?: string;
}
