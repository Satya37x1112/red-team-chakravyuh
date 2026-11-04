import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Button, Empty, Icon, Pill } from "../components/ui";
import type { PentestReport, ReportFinding } from "../types";
import type { StateTone } from "../lib";

const SEV_TONE: Record<string, StateTone> = {
  critical: "crit",
  high: "crit",
  medium: "warn",
  low: "ok",
  info: "muted",
};

function fmt(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function download(name: string, text: string, type: string) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function reportToHtml(r: PentestReport): string {
  const esc = (s: unknown) =>
    String(s ?? "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c] || c));
  const findingRows = r.findings
    .map(
      (f) => `<tr><td class="sev ${f.severity}">${esc(f.severity)}</td><td>${esc(f.title)}</td>
      <td>${esc(f.target)}</td><td>${esc(f.detail)}</td><td>${esc(f.source)}</td></tr>`
    )
    .join("");
  const techRows = r.attack_coverage
    .map(
      (t) =>
        `<tr><td class="mono">${esc(t.id)}</td><td>${esc(t.name)}</td><td>${esc(t.tactic)}</td><td>${t.observations}</td><td>${esc(
          t.sources.join(", ")
        )}</td></tr>`
    )
    .join("");
  return `<!doctype html><html><head><meta charset="utf-8"><title>${esc(r.meta.title)}</title>
<style>
  body{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;color:#111;max-width:900px;margin:40px auto;padding:0 20px}
  h1{font-size:24px;margin:0 0 4px} h2{font-size:17px;margin:28px 0 8px;border-bottom:2px solid #eee;padding-bottom:4px}
  .muted{color:#666;font-size:13px} table{width:100%;border-collapse:collapse;margin-top:8px;font-size:13px}
  th,td{border:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top} th{background:#f5f5f5}
  .mono{font-family:ui-monospace,Menlo,Consolas,monospace} .sev{font-weight:700;text-transform:uppercase;font-size:11px}
  .sev.critical,.sev.high{color:#b00020}.sev.medium{color:#b26a00}.sev.low{color:#1a7f37}.sev.info{color:#555}
  .kv{display:flex;gap:8px}.kv b{min-width:120px;color:#444}
</style></head><body>
  <h1>${esc(r.meta.title)}</h1>
  <div class="muted">Generated ${fmt(r.meta.generated_at)} · operator ${esc(r.meta.operator)} · console ${esc(
    r.meta.console_host
  )}</div>
  <h2>1. Scope</h2>
  <div class="kv"><b>Targets</b><span class="mono">${esc(r.scope.targets.join(", ") || "—")}</span></div>
  <div class="kv"><b>Host</b><span>${esc(r.scope.telemetry_host)} (${esc(r.scope.os_name)})</span></div>
  <h2>2. Summary</h2>
  <div class="kv"><b>Tests run</b><span>${r.summary.total_tests}</span></div>
  <div class="kv"><b>Findings</b><span>${r.summary.finding_count}</span></div>
  <div class="kv"><b>ATT&CK techniques</b><span>${r.summary.technique_count}</span></div>
  <div class="kv"><b>Severity</b><span>${Object.entries(r.summary.severity_breakdown)
    .map(([k, v]) => `${k}: ${v}`)
    .join(" · ")}</span></div>
  <h2>3. Methodology</h2>
  <table><tr><th>Tool</th><th>Role</th><th>Status</th></tr>${r.methodology
    .map((m) => `<tr><td>${esc(m.tool)}</td><td>${esc(m.role)}</td><td>${esc(m.status)}</td></tr>`)
    .join("")}</table>
  <h2>4. Findings</h2>
  <table><tr><th>Severity</th><th>Finding</th><th>Target</th><th>Detail</th><th>Source</th></tr>${findingRows}</table>
  <h2>5. MITRE ATT&CK Coverage</h2>
  <table><tr><th>ID</th><th>Technique</th><th>Tactic</th><th>Obs.</th><th>Source</th></tr>${techRows}</table>
  <h2>6. Timeline</h2>
  <table><tr><th>Time</th><th>Tool</th><th>Activity</th></tr>${r.timeline
    .map((t) => `<tr><td>${fmt(t.at)}</td><td>${esc(t.integration)}</td><td>${esc(t.summary)}</td></tr>`)
    .join("")}</table>
</body></html>`;
}

function FindingCard({ f }: { f: ReportFinding }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-3.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Pill tone={SEV_TONE[f.severity] ?? "muted"}>{f.severity}</Pill>
          <span className="text-[13px] font-semibold text-ink">{f.title}</span>
        </div>
        <span className="font-mono text-2xs text-faint">{f.source}</span>
      </div>
      <p className="mt-1.5 text-xs text-muted">{f.detail}</p>
      <div className="mt-1.5 flex flex-wrap gap-2 text-2xs text-faint">
        {f.target && <span className="font-mono">target: {f.target}</span>}
        {f.technique && <span>· {f.technique}</span>}
        <span>· {fmt(f.at)}</span>
      </div>
    </div>
  );
}

export function Report() {
  const [r, setR] = useState<PentestReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .report()
      .then(setR)
      .catch((e) => setError(String((e as Error).message)));
  }, []);

  useEffect(load, [load]);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-ink">Pentest Report</h1>
          <p className="mt-1 text-xs text-muted">
            Every test the range has run — CALDERA, Locust, and vervet — assembled into one engagement report.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={() => r && download("pentest-report.html", reportToHtml(r), "text/html")} disabled={!r}>
            <Icon name="download" size={13} />
            Download HTML
          </Button>
          <Button onClick={() => r && download("pentest-report.json", JSON.stringify(r, null, 2), "application/json")} disabled={!r}>
            <Icon name="download" size={13} />
            JSON
          </Button>
          <Button variant="primary" onClick={() => window.print()} disabled={!r}>
            <Icon name="file" size={13} />
            Print / PDF
          </Button>
          <Button onClick={load}>
            <Icon name="refresh" size={13} />
            Refresh
          </Button>
        </div>
      </div>

      {error && <p className="rounded border border-crit/40 bg-crit/10 px-3 py-2 text-xs text-crit">{error}</p>}

      {!r ? (
        <Empty>Loading report…</Empty>
      ) : r.summary.total_tests === 0 ? (
        <Empty>No tests recorded yet. Run a CALDERA analysis, Locust test, or vervet scan to populate the report.</Empty>
      ) : (
        <>
          <div className="rounded-lg border border-line bg-surface p-4">
            <div className="text-[15px] font-semibold text-ink">{r.meta.title}</div>
            <div className="mt-1 text-xs text-muted">
              Generated {fmt(r.meta.generated_at)} · operator <span className="font-mono">{r.meta.operator ?? "—"}</span> ·
              console <span className="font-mono">{r.meta.console_host ?? "—"}</span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {(["critical", "high", "medium", "low", "info"] as const).map((s) => (
                <div key={s} className="rounded border border-line bg-canvas px-3 py-2">
                  <div className="text-2xs uppercase text-faint">{s}</div>
                  <div className="mt-0.5 font-mono text-lg text-ink">{r.summary.severity_breakdown[s] ?? 0}</div>
                </div>
              ))}
              <div className="rounded border border-line bg-canvas px-3 py-2">
                <div className="text-2xs uppercase text-faint">techniques</div>
                <div className="mt-0.5 font-mono text-lg text-ink">{r.summary.technique_count}</div>
              </div>
            </div>
            <div className="mt-3 text-2xs text-muted">
              Scope: <span className="font-mono text-ink">{r.scope.targets.join(", ") || "—"}</span>
            </div>
          </div>

          <div>
            <h2 className="mb-2 text-[13px] font-semibold text-ink">Findings ({r.findings.length})</h2>
            <div className="flex flex-col gap-2.5">
              {r.findings.map((f, i) => (
                <FindingCard key={i} f={f} />
              ))}
            </div>
          </div>

          <div>
            <h2 className="mb-2 text-[13px] font-semibold text-ink">MITRE ATT&CK Coverage ({r.attack_coverage.length})</h2>
            <div className="overflow-hidden rounded-lg border border-line">
              <div className="grid grid-cols-[90px_1fr_110px_60px_90px] gap-2 bg-raised px-3 py-1.5 text-2xs uppercase text-faint">
                <span>ID</span><span>Technique</span><span>Tactic</span><span>Obs.</span><span>Source</span>
              </div>
              {r.attack_coverage.map((t) => (
                <div key={t.id} className="grid grid-cols-[90px_1fr_110px_60px_90px] gap-2 border-t border-line px-3 py-1.5 text-xs">
                  <span className="font-mono text-accent">{t.id}</span>
                  <span className="truncate text-ink">{t.name}</span>
                  <span className="text-muted">{t.tactic ?? "—"}</span>
                  <span className="font-mono text-muted">{t.observations}</span>
                  <span className="text-2xs text-muted">{t.sources.join(", ")}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
