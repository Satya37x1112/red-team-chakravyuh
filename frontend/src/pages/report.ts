import type { AnalyticsRow, Telemetry } from "../types";
import { KINDS } from "../lib";

type Result = Record<string, unknown> | null;
type Assessment = { headline?: string; results?: string[]; weak_points?: string[]; recommendations?: string[] };
type Sev = "High" | "Medium" | "Low";

const esc = (s: unknown) =>
  String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c] as string));

function severityFor(text: string): Sev {
  const t = text.toLowerCase();
  if (/mfa|weak,? common|password|dictionary|high behavioural risk|rate limit|shedding|saturat|drives the host/.test(t)) return "High";
  if (/no anomalies|baseline|no lockout would/.test(t)) return "Low";
  return "Medium";
}

const SEV_COLOR: Record<Sev, string> = { High: "#cd2a2c", Medium: "#a3660a", Low: "#3b5fb8" };

/** Build a self-contained pentest-style report as an HTML string. */
export function buildReportHtml(telemetry: Telemetry | null, rows: AnalyticsRow[], results: Record<string, Result>): string {
  const done = rows.filter((r) => r.state === "RESULT");
  const now = new Date();
  const findings: { id: string; sev: Sev; scenario: string; text: string }[] = [];
  const remediation: Record<string, Set<string>> = {};

  done.forEach((r) => {
    const a = (results[r.id]?.analysis as { assessment?: Assessment } | undefined)?.assessment;
    const scen = KINDS[r.kind].name;
    (a?.weak_points ?? []).forEach((w) => {
      findings.push({ id: "", sev: severityFor(w), scenario: scen, text: w });
    });
    remediation[scen] = remediation[scen] ?? new Set();
    (a?.recommendations ?? []).forEach((x) => remediation[scen].add(x));
  });
  const order: Record<Sev, number> = { High: 0, Medium: 1, Low: 2 };
  findings.sort((x, y) => order[x.sev] - order[y.sev]);
  findings.forEach((f, i) => (f.id = `CV-${String(i + 1).padStart(2, "0")}`));
  const counts = { High: 0, Medium: 0, Low: 0 } as Record<Sev, number>;
  findings.forEach((f) => counts[f.sev]++);

  const sevBadge = (s: Sev) =>
    `<span style="display:inline-block;padding:1px 8px;border-radius:3px;font-size:11px;font-weight:600;color:#fff;background:${SEV_COLOR[s]}">${s}</span>`;

  const findingRows = findings
    .map(
      (f) =>
        `<tr><td style="font-family:monospace">${f.id}</td><td>${sevBadge(f.sev)}</td><td>${esc(f.scenario)}</td><td>${esc(f.text)}</td></tr>`
    )
    .join("");

  const scenarios = [...new Set(done.map((r) => KINDS[r.kind].name))];
  const detailSections = scenarios
    .map((scen) => {
      const fs = findings.filter((f) => f.scenario === scen);
      if (!fs.length) return "";
      const items = fs
        .map((f) => `<li><b>${f.id}</b> ${sevBadge(f.sev)}<br/>${esc(f.text)}</li>`)
        .join("");
      const recs = [...(remediation[scen] ?? [])].map((r) => `<li>${esc(r)}</li>`).join("");
      return `<h3>${esc(scen)}</h3><div class="muted">Findings</div><ul>${items}</ul>
        <div class="muted">Recommended remediation</div><ul class="recs">${recs}</ul>`;
    })
    .join("");

  const appendixRows = done
    .map((r) => {
      const m = (results[r.id]?.analysis as { simulation_metrics?: Record<string, unknown> } | undefined)?.simulation_metrics ?? {};
      const keys = Object.entries(m)
        .filter(([, v]) => typeof v === "number")
        .map(([k, v]) => `${k}=${v}`)
        .join(", ");
      return `<tr><td style="font-family:monospace">${esc(r.label)}</td><td>${esc(KINDS[r.kind].name)}</td><td>${
        r.risk_score == null ? "—" : Math.round(r.risk_score * 100)
      }</td><td style="font-size:11px">${esc(keys)}</td></tr>`;
    })
    .join("");

  const target = telemetry?.hostname ?? "lab target";
  const os = telemetry?.os_name ?? "unavailable";

  return `<!doctype html><html><head><meta charset="utf-8"><title>VAJRAPRAHAAR Assessment Report</title>
<style>
  @page { margin: 22mm 18mm; }
  * { box-sizing: border-box; }
  body { font-family: Georgia, "Times New Roman", serif; color: #1a1a1a; line-height: 1.5; font-size: 13px; margin: 0; }
  h1 { font-size: 26px; margin: 0 0 4px; }
  h2 { font-size: 17px; border-bottom: 2px solid #cd2a2c; padding-bottom: 4px; margin: 26px 0 10px; }
  h3 { font-size: 14px; margin: 16px 0 4px; color: #cd2a2c; }
  .muted { color: #666; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; margin-top: 8px; }
  table { width: 100%; border-collapse: collapse; margin: 8px 0; }
  th, td { border: 1px solid #ddd; padding: 6px 8px; text-align: left; vertical-align: top; font-size: 12px; }
  th { background: #f4f4f5; font-size: 11px; text-transform: uppercase; letter-spacing: .03em; }
  ul { margin: 4px 0 10px; padding-left: 18px; } li { margin: 3px 0; }
  ul.recs li { color: #176a3a; }
  .cover { border-left: 5px solid #cd2a2c; padding: 10px 0 10px 16px; margin-bottom: 8px; }
  .kpis { display: flex; gap: 10px; margin: 10px 0; }
  .kpi { flex: 1; border: 1px solid #ddd; border-radius: 4px; padding: 8px 10px; }
  .kpi b { font-size: 22px; display: block; } .kpi span { font-size: 11px; color: #666; }
  .foot { margin-top: 24px; border-top: 1px solid #ddd; padding-top: 8px; color: #888; font-size: 10px; }
  .pb { page-break-before: always; }
</style></head><body>
  <div class="cover">
    <h1>VAJRAPRAHAAR — Security Assessment Report</h1>
    <div class="muted" style="margin-top:2px">AI-assisted cyber-range · authorized lab engagement</div>
  </div>
  <table><tbody>
    <tr><th style="width:30%">Target host</th><td>${esc(target)} (${esc(os)})</td></tr>
    <tr><th>Report date</th><td>${now.toLocaleDateString()} ${now.toLocaleTimeString()}</td></tr>
    <tr><th>Sessions analysed</th><td>${done.length}</td></tr>
    <tr><th>Classification</th><td>Confidential — lab use only</td></tr>
  </tbody></table>

  <h2>1. Executive summary</h2>
  <p>This report summarises ${done.length} agent-driven assessment session(s) run against an isolated lab host.
  The engine observed real host telemetry, reasoned over it, and ran controlled simulations to surface weaknesses.
  <b>${findings.length}</b> finding(s) were identified.</p>
  <div class="kpis">
    <div class="kpi"><b style="color:${SEV_COLOR.High}">${counts.High}</b><span>High</span></div>
    <div class="kpi"><b style="color:${SEV_COLOR.Medium}">${counts.Medium}</b><span>Medium</span></div>
    <div class="kpi"><b style="color:${SEV_COLOR.Low}">${counts.Low}</b><span>Low</span></div>
  </div>

  <h2>2. Scope &amp; methodology</h2>
  <p>Scope: the single authorized lab host above, on an isolated network. No production systems were in scope.</p>
  <p>Methodology: each session followed the agent lifecycle —
  <i>discover → profile → plan → prepare → simulate → observe → adapt → analyze → result</i>.
  Telemetry collection is read-only; simulations are bounded and do not generate real attack traffic, credentials, or implants.</p>

  <h2>3. Findings summary</h2>
  ${findings.length ? `<table><thead><tr><th>ID</th><th>Severity</th><th>Scenario</th><th>Finding</th></tr></thead><tbody>${findingRows}</tbody></table>` : "<p>No findings recorded.</p>"}

  <h2 class="pb">4. Findings &amp; remediation</h2>
  ${detailSections || "<p>No detailed findings.</p>"}

  <h2>5. Appendix — session metrics</h2>
  <table><thead><tr><th>Session</th><th>Scenario</th><th>Risk</th><th>Simulation metrics</th></tr></thead><tbody>${appendixRows}</tbody></table>

  <div class="foot">Generated by VAJRAPRAHAAR. Findings derive from read-only telemetry and bounded simulations in an authorized lab. For defensive hardening use.</div>
</body></html>`;
}

/** Open the report in a new window and trigger the browser's print → Save as PDF. */
export function openReport(telemetry: Telemetry | null, rows: AnalyticsRow[], results: Record<string, Result>): void {
  const html = buildReportHtml(telemetry, rows, results);
  const w = window.open("", "_blank");
  if (!w) return;
  w.document.open();
  w.document.write(html);
  w.document.close();
  w.onload = () => setTimeout(() => w.print(), 300);
}
