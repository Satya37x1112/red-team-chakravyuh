import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useLiveContext } from "../live-context";
import { parseTs } from "../lib";
import type { HistoryPoint } from "../types";
import { LineChart } from "./charts";
import { Panel, Segmented } from "./ui";

type Range = "15" | "60" | "360";
const CPU = "rgb(var(--accent))";
const MEM = "rgb(var(--series-2))";

export function HostLoadPanel({ height = 230, className = "" }: { height?: number; className?: string }) {
  const { telemetry } = useLiveContext();
  const [range, setRange] = useState<Range>("60");
  const [points, setPoints] = useState<HistoryPoint[]>([]);

  useEffect(() => {
    let alive = true;
    api
      .history(Number(range))
      .then((p) => alive && setPoints(p))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [range]);

  useEffect(() => {
    if (!telemetry?.available) return;
    const at = parseTs(telemetry.collected_at)?.getTime();
    if (!at) return;
    setPoints((prev) => {
      const last = prev.length ? parseTs(prev[prev.length - 1].t)?.getTime() ?? 0 : 0;
      if (at <= last) return prev;
      const cutoff = Date.now() - Number(range) * 60_000;
      const next = [
        ...prev,
        {
          t: telemetry.collected_at,
          cpu: telemetry.cpu_percent,
          mem: telemetry.memory_percent,
          disk: telemetry.disk_percent,
          procs: telemetry.process_count,
        },
      ];
      return next.filter((p) => (parseTs(p.t)?.getTime() ?? 0) >= cutoff);
    });
  }, [telemetry, range]);

  const { times, cpu, mem } = useMemo(
    () => ({
      times: points.map((p) => parseTs(p.t) as Date),
      cpu: points.map((p) => p.cpu),
      mem: points.map((p) => p.mem),
    }),
    [points]
  );
  const last = points[points.length - 1];

  return (
    <Panel
      className={className}
      title="Host load"
      sub={`Observed on ${telemetry?.hostname ?? "target"} · ${points.length} samples`}
      actions={
        <Segmented
          value={range}
          onChange={setRange}
          options={[
            { value: "15", label: "15m" },
            { value: "60", label: "1h" },
            { value: "360", label: "6h" },
          ]}
        />
      }
    >
      <div className="mb-3 flex flex-wrap gap-x-8 gap-y-2">
        {[
          { label: "CPU", color: CPU, v: last?.cpu },
          { label: "Memory", color: MEM, v: last?.mem },
          { label: "Disk", color: null, v: last?.disk },
          { label: "Processes", color: null, v: last?.procs, raw: true },
        ].map((m) => (
          <div key={m.label}>
            <div className="flex items-center gap-1.5 text-2xs text-muted">
              {m.color ? <span className="h-0.5 w-3 rounded" style={{ background: m.color }} /> : <span className="w-3" />}
              {m.label}
            </div>
            <div className="mt-0.5 font-mono text-lg text-ink">
              {m.v == null ? <span className="text-faint">n/a</span> : m.raw ? m.v : `${m.v.toFixed(1)}%`}
            </div>
          </div>
        ))}
      </div>
      <LineChart
        times={times}
        height={height}
        yMax={100}
        series={[
          { key: "cpu", label: "CPU", color: CPU, values: cpu, area: true },
          { key: "mem", label: "Memory", color: MEM, values: mem },
        ]}
      />
    </Panel>
  );
}
