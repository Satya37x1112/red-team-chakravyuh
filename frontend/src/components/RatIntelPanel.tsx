import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Button, Empty, Icon, Panel, Pill } from "./ui";
import type { ArtifactDetail, ArtifactRow, SmartAnalysis } from "../types";
import type { StateTone } from "../lib";

const TOOLS = "vervet,caldera,pentestgpt";

const SEV_TONE: Record<string, StateTone> = {
  critical: "crit",
  high: "crit",
  medium: "warn",
  low: "ok",
  info: "muted",
};

const LABEL: Record<string, string> = { vervet: "vervet", caldera: "CALDERA", pentestgpt: "PentestGPT" };
const TONE: Record<string, "ok" | "warn" | "crit" | "muted"> = {
  vervet: "ok",
  caldera: "warn",
  pentestgpt: "crit",
};

function fmt(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

/** Adversary-emulation intel for the RAT scenario: every vervet scan, CALDERA
 *  analysis, and PentestGPT run, pulled from the central artifact store. */
export function RatIntelPanel() {
  const [rows, setRows] = useState<ArtifactRow[] | null>(null);
  const [intel, setIntel] = useState<SmartAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<ArtifactDetail | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    // Sync any PentestGPT CLI runs first, then fetch artifacts + the smart analysis.
    api
      .pentestgptIngest()
      .catch(() => undefined)
      .finally(() => {
        api
          .artifacts(TOOLS)
          .then(setRows)
          .catch((e) => setError(String((e as Error).message)));
        api
          .analysis()
          .then(setIntel)
          .catch(() => undefined);
      });
  }, []);

  useEffect(load, [load]);

  const openRow = useCallback((r: ArtifactRow) => {
    setBusy(true);
    setOpen(null);
    api
      .artifact(r.id)
      .then(setOpen)
      .catch((e) => setError(String((e as Error).message)))
      .finally(() => setBusy(false));
  }, []);

  const counts =
    rows?.reduce<Record<string, number>>((acc, r) => {
      acc[r.integration] = (acc[r.integration] ?? 0) + 1;
      return acc;
    }, {}) ?? {};

  return (
    <Panel
      title="Adversary emulation intel"
      sub="vervet scans · CALDERA analyses · PentestGPT runs — all feeding the RAT picture"
      actions={
        <Button onClick={load}>
          <Icon name="refresh" size={13} />
          Sync
        </Button>
      }
    >
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-1.5">
          {(["vervet", "caldera", "pentestgpt"] as const).map((t) => (
            <Pill key={t} tone={counts[t] ? TONE[t] : "muted"}>
              {LABEL[t]} · {counts[t] ?? 0}
            </Pill>
          ))}
        </div>

        {intel && intel.issue_count > 0 && (
          <div className="flex flex-col gap-2.5">
            <div className="rounded-lg border-2 border-crit/40 bg-crit/5 p-3.5">
              <div className="flex items-center gap-2">
                <Icon name="alert" size={14} className="text-crit" />
                <span className="font-mono text-2xs uppercase tracking-wide text-crit">
                  Smart analysis — kya dikkat hai
                </span>
                <span className="h-px flex-1 bg-crit/20" />
                {intel.model && <span className="font-mono text-2xs text-faint">{intel.model}</span>}
              </div>
              {intel.headline && (
                <p className="mt-2 text-[14px] font-semibold leading-snug text-ink">{intel.headline}</p>
              )}
              <div className="mt-2 flex flex-wrap gap-1.5">
                {(["critical", "high", "medium", "low"] as const).map((s) =>
                  intel.severity_counts[s] ? (
                    <Pill key={s} tone={SEV_TONE[s]}>
                      {s} · {intel.severity_counts[s]}
                    </Pill>
                  ) : null
                )}
              </div>
            </div>
            <div className="flex flex-col gap-2">
              {intel.issues.map((iss, i) => (
                <div key={i} className="rounded-lg border border-line bg-surface p-3">
                  <div className="flex items-center gap-2">
                    <Pill tone={SEV_TONE[iss.severity] ?? "muted"}>{iss.severity}</Pill>
                    <span className="text-[13px] font-semibold text-ink">{iss.title}</span>
                  </div>
                  <p className="mt-1.5 text-xs text-ink">
                    <span className="font-semibold text-crit">Attacker: </span>
                    {iss.attacker_note}
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    <span className="font-semibold text-ok">Fix: </span>
                    {iss.recommendation}
                  </p>
                  <p className="mt-1 font-mono text-2xs text-faint">{iss.evidence}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {error && <p className="rounded border border-crit/40 bg-crit/10 px-3 py-2 text-xs text-crit">{error}</p>}

        {rows === null ? (
          <Empty>Loading intel…</Empty>
        ) : rows.length === 0 ? (
          <Empty>
            No emulation data yet. Run a vervet scan or CALDERA analysis on the Integrations page, or a PentestGPT
            engagement from the CLI.
          </Empty>
        ) : (
          <div className="flex max-h-[320px] flex-col divide-y divide-line overflow-auto">
            {rows.map((r) => (
              <button
                key={r.id}
                onClick={() => openRow(r)}
                className="flex items-start gap-3 py-2.5 text-left transition-colors first:pt-0 hover:bg-raised/40"
              >
                <Pill tone={TONE[r.integration] ?? "muted"}>{LABEL[r.integration] ?? r.integration}</Pill>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[13px] text-ink">{r.title || r.kind}</div>
                  <div className="truncate text-2xs text-muted">{r.summary}</div>
                </div>
                <span className="shrink-0 font-mono text-2xs text-faint">{fmt(r.created_at)}</span>
              </button>
            ))}
          </div>
        )}

        {(busy || open) && (
          <div className="rounded border border-line bg-canvas p-3">
            {busy ? (
              <p className="text-xs text-muted">Loading…</p>
            ) : open ? (
              <>
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="text-[13px] font-semibold text-ink">
                    {LABEL[open.integration] ?? open.integration} · {open.title}
                  </span>
                  <Button onClick={() => setOpen(null)}>
                    <Icon name="chevron" size={13} />
                    Close
                  </Button>
                </div>
                <pre className="max-h-72 overflow-auto font-mono text-2xs leading-relaxed text-ink">
                  {JSON.stringify(open.payload, null, 2)}
                </pre>
              </>
            ) : null}
          </div>
        )}
      </div>
    </Panel>
  );
}
