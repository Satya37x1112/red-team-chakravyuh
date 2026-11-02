import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { useLiveContext } from "../live-context";
import { parseTs } from "../lib";
import type { HistoryPoint } from "../types";
import { LineChart } from "./charts";
import { Panel, Segmented } from "./ui";

type Range = "15" | "60" | "360";
const CPU = "rgb(var(--accent))";
const MEM = "rgb(var(--series-2))";
const SIM = "rgb(var(--warn))";
const SIM_WINDOW_MS = 45_000;

export function HostLoadPanel({ height = 230, className = "" }: { height?: number; className?: string }) {
  const { telemetry, events } = useLiveContext();
  const [range, setRange] = useState<Range>("60");
  const [points, setPoints] = useState<HistoryPoint[]>([]);
  const [sim, setSim] = useState<{ peak: number; start: number } | null>(null);
  const [, force] = useState(0);
  const timer = useRef<number | undefined>(undefined);

  // Pick up the most recent DDoS simulation's modelled peak load (synthetic).
  useEffect(() => {
    const ev = events.find(
      (e) => (e.payload?.metrics as { simulated_peak_load_pct?: number } | undefined)?.simulated_peak_load_pct != null
    );
    if (!ev) return;
    const peak = (ev.payload.metrics as { simulated_peak_load_pct: number }).simulated_peak_load_pct;
    const start = parseTs(ev.ts)?.getTime() ?? Date.now();
    setSim((prev) => (prev && prev.start >= start ? prev : { peak, start }));
  }, [events]);

  // While a spike is active, tick so it fades out on its own.
  useEffect(() => {
    if (!sim) return;
    timer.current = window.setInterval(() => force((n) => n + 1), 2000);
    return () => clearInterval(timer.current);
  }, [sim]);

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

  const simActive = !!sim && Date.now() - sim.start < SIM_WINDOW_MS;
  const { times, cpu, mem, simLoad } = useMemo(
    () => ({
      times: points.map((p) => parseTs(p.t) as Date),
      cpu: points.map((p) => p.cpu),
      mem: points.map((p) => p.mem),
      simLoad: ((): (number | null)[] => {
        const arr: (number | null)[] = points.map(() => null);
        if (!sim || !simActive) return arr;
        const n = points.length;
        const k = Math.min(n, 22);         // spread the ramp over more samples so it rises gently
        const base = points[n - 1]?.cpu ?? 6; // start from the current real CPU, not a jump
        // stable per-run pseudo-noise so the curve looks organic, not a clean bell
        const rnd = (x: number) => {
          const v = Math.sin((sim.start / 1000 + x) * 12.9898) * 43758.5453;
          return v - Math.floor(v);
        };
        const peak = sim.peak + (rnd(0.5) - 0.5) * 5; // slightly different peak each run
        for (let j = 0; j < k; j++) {
          const frac = k === 1 ? 0.5 : j / (k - 1);
          const tri = 1 - Math.abs(frac - 0.5) * 2;          // 0 → 1 → 0
          const eased = tri * tri * tri * (tri * (tri * 6 - 15) + 10); // smootherstep
          const noise = (rnd(j + 1) - 0.5) * 5 * (0.3 + eased); // more wobble near the peak
          arr[n - k + j] = Math.max(0, Math.min(100, Math.round(base + (peak - base) * eased + noise)));
        }
        return arr;
      })(),
    }),
    [points, sim, simActive]
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
      {simActive && (
        <div className="mb-2 flex items-center gap-1.5 text-2xs text-muted">
          <span className="h-0.5 w-3 rounded" style={{ background: SIM }} />
          Simulated load
        </div>
      )}
      <LineChart
        times={times}
        height={height}
        yMax={100}
        series={[
          { key: "cpu", label: "CPU", color: CPU, values: cpu, area: true },
          { key: "mem", label: "Memory", color: MEM, values: mem },
          ...(simActive ? [{ key: "sim", label: "Simulated load", color: SIM, values: simLoad, smooth: true }] : []),
        ]}
      />
    </Panel>
  );
}
