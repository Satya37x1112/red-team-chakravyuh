import type { Kind } from "./types";

/** Backend timestamps from SQLite come back without an offset; they are UTC. */
export function parseTs(s: string | null | undefined): Date | null {
  if (!s) return null;
  const iso = /[zZ]|[+-]\d\d:?\d\d$/.test(s) ? s : `${s}Z`;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

export const clock = (d: Date | null, seconds = false) =>
  d
    ? d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: seconds ? "2-digit" : undefined })
    : "--:--";

export function uptime(seconds: number | null | undefined): string | null {
  if (seconds == null) return null;
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return d ? `${d}d ${h}h` : `${h}h ${m}m`;
}

export function duration(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

export function median(values: number[]): number | null {
  if (!values.length) return null;
  const s = [...values].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

interface KindMeta {
  kind: Kind;
  path: string;
  index: string;
  name: string;
  sub: string;
  mitre: string;
  blurb: string;
  vector: string;
  decisionLabel: string;
  decisionUnit: string;
  impactMetric: "cpu_percent" | "memory_percent" | null;
  impactLabel: string;
}

export const KINDS: Record<Kind, KindMeta> = {
  ddos: {
    kind: "ddos",
    path: "/ddos",
    index: "01",
    name: "DDoS",
    sub: "Service-load simulation",
    mitre: "T1498",
    blurb: "Controlled load test that measures how the target host responds under volumetric pressure.",
    vector: "Locust adapter · HTTP/TCP · lab-only",
    decisionLabel: "Load sources",
    decisionUnit: "sources",
    impactMetric: "cpu_percent",
    impactLabel: "CPU change during run",
  },
  bruteforce: {
    kind: "bruteforce",
    path: "/bruteforce",
    index: "02",
    name: "Brute Force",
    sub: "Authentication resilience test",
    mitre: "T1110",
    blurb: "Account-lockout and credential-policy test paced by the agent against lab authentication endpoints.",
    vector: "Auth adapter · rate-limited · lab-only",
    decisionLabel: "Attempt rate",
    decisionUnit: "/min",
    impactMetric: "memory_percent",
    impactLabel: "Memory change during run",
  },
  ratuba: {
    kind: "ratuba",
    path: "/rat",
    index: "03",
    name: "RAT",
    sub: "Endpoint behaviour analytics",
    mitre: "T1219",
    blurb: "Baselines real endpoint activity and scores deviations — process, network and logon behaviour.",
    vector: "UBA engine · baseline vs. live · lab-only",
    decisionLabel: "Baseline window",
    decisionUnit: "min",
    impactMetric: null,
    impactLabel: "UBA risk score",
  },
};

export const KIND_LIST = [KINDS.ddos, KINDS.bruteforce, KINDS.ratuba];

export type StateTone = "ok" | "warn" | "crit" | "muted";
export function stateTone(state: string): StateTone {
  if (state === "RESULT") return "ok";
  if (state === "KILLED" || state === "FAILED") return "crit";
  return "warn";
}
export function stateLabel(state: string): string {
  if (state === "RESULT") return "completed";
  if (state === "KILLED") return "killed";
  if (state === "FAILED") return "failed";
  return state.toLowerCase();
}
