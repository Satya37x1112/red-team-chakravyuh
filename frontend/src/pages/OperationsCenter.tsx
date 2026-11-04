import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Button, Empty, Icon, Panel, Pill } from "../components/ui";
import type { ArtifactDetail, ArtifactRow, CentralSummary } from "../types";

const INTEG_LABEL: Record<string, string> = {
  caldera: "CALDERA",
  locust: "Locust",
  vervet: "vervet",
  pentestgpt: "PentestGPT",
};

const KIND_TONE: Record<string, "ok" | "warn" | "crit" | "muted"> = {
  analysis: "ok",
  load_test: "warn",
  describe: "muted",
  run: "crit",
};

function Tile({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface px-3.5 py-3">
      <div className="text-2xs uppercase tracking-wide text-faint">{label}</div>
      <div className="mt-1 font-mono text-xl text-ink">{value}</div>
      {sub && <div className="mt-0.5 text-2xs text-muted">{sub}</div>}
    </div>
  );
}

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function OperationsCenter() {
  const [data, setData] = useState<CentralSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<ArtifactDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const load = useCallback(() => {
    api
      .central()
      .then(setData)
      .catch((e) => setError(String((e as Error).message)));
  }, []);

  useEffect(() => {
    load();
    const t = window.setInterval(load, 8000);
    return () => window.clearInterval(t);
  }, [load]);

  const openArtifact = useCallback((row: ArtifactRow) => {
    setLoadingDetail(true);
    setSelected(null);
    api
      .artifact(row.id)
      .then(setSelected)
      .catch((e) => setError(String((e as Error).message)))
      .finally(() => setLoadingDetail(false));
  }, []);

  const exportAll = useCallback(() => {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `chakravyuh-operations-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [data]);

  const t = data?.telemetry;
  const pct = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v)}%`);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight text-ink">Operations Center</h1>
          <p className="mt-1 text-xs text-muted">
            One place for everything the range produces — live telemetry, sessions, and every integration output.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={exportAll} disabled={!data}>
            <Icon name="download" size={13} />
            Export all
          </Button>
          <Button onClick={load}>
            <Icon name="refresh" size={13} />
            Refresh
          </Button>
        </div>
      </div>

      {error && <p className="rounded border border-crit/40 bg-crit/10 px-3 py-2 text-xs text-crit">{error}</p>}

      {!data ? (
        <Empty>Loading operations summary…</Empty>
      ) : (
        <>
          {/* Top metrics */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Tile label="Target" value={t?.hostname ?? "—"} sub={t?.os_name ?? (t?.available ? "" : "offline")} />
            <Tile label="CPU" value={pct(t?.cpu_percent)} />
            <Tile label="Memory" value={pct(t?.memory_percent)} />
            <Tile label="Disk" value={pct(t?.disk_percent)} />
            <Tile label="Sessions" value={data.sessions.total} sub="total runs" />
            <Tile
              label="Integrations"
              value={`${data.integrations.available}/${data.integrations.total}`}
              sub="ready"
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
            {/* Integration + artifact rollup */}
            <Panel title="Integrations" sub="Wired tooling and how much each has produced">
              <div className="flex flex-col divide-y divide-line">
                {data.integrations.items.map((it) => (
                  <div key={it.name} className="flex items-center justify-between gap-2 py-2 first:pt-0 last:pb-0">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 text-[13px] text-ink">
                        {INTEG_LABEL[it.name] ?? it.title}
                        <Pill tone={it.available ? "ok" : "muted"}>{it.available ? "ready" : "off"}</Pill>
                      </div>
                      <div className="truncate text-2xs text-muted">{it.category}</div>
                    </div>
                    <div className="shrink-0 font-mono text-2xs text-muted">
                      {data.artifacts.by_integration[it.name] ?? 0} artifacts
                    </div>
                  </div>
                ))}
              </div>
            </Panel>

            {/* Recent artifacts */}
            <Panel
              title="Recent activity"
              sub={`${data.artifacts.total} total artifact${data.artifacts.total === 1 ? "" : "s"} in the central store`}
            >
              {data.artifacts.recent.length === 0 ? (
                <Empty>No integration outputs yet. Run an analysis, load test, or describe to populate this.</Empty>
              ) : (
                <div className="flex flex-col divide-y divide-line">
                  {data.artifacts.recent.map((a) => (
                    <button
                      key={a.id}
                      onClick={() => openArtifact(a)}
                      className="flex items-start gap-3 py-2.5 text-left transition-colors first:pt-0 last:pb-0 hover:bg-raised/40"
                    >
                      <Pill tone={KIND_TONE[a.kind] ?? "muted"}>{INTEG_LABEL[a.integration] ?? a.integration}</Pill>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-[13px] text-ink">{a.title || a.kind}</div>
                        <div className="truncate text-2xs text-muted">{a.summary}</div>
                      </div>
                      <div className="shrink-0 font-mono text-2xs text-faint">{fmtTime(a.created_at)}</div>
                    </button>
                  ))}
                </div>
              )}
            </Panel>
          </div>

          {/* Artifact detail */}
          {(loadingDetail || selected) && (
            <Panel
              title={selected ? `${INTEG_LABEL[selected.integration] ?? selected.integration} · ${selected.title}` : "Loading…"}
              sub={selected ? fmtTime(selected.created_at) : undefined}
              actions={
                selected && (
                  <Button onClick={() => setSelected(null)}>
                    <Icon name="chevron" size={13} />
                    Close
                  </Button>
                )
              }
            >
              {loadingDetail ? (
                <Empty>Loading artifact…</Empty>
              ) : selected ? (
                <pre className="max-h-[420px] overflow-auto rounded border border-line bg-canvas p-3 font-mono text-2xs leading-relaxed text-ink">
                  {JSON.stringify(selected.payload, null, 2)}
                </pre>
              ) : null}
            </Panel>
          )}
        </>
      )}
    </div>
  );
}
