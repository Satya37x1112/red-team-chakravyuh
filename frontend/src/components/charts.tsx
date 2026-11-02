import { useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { clock } from "../lib";

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    ro.observe(el);
    setWidth(Math.floor(el.getBoundingClientRect().width));
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

function niceCeil(v: number): number {
  if (v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
}

const fmt = (v: number) => (Math.abs(v) >= 100 || Number.isInteger(v) ? v.toFixed(0) : v.toFixed(1));

function Tooltip({ x, width, children }: { x: number; width: number; children: ReactNode }) {
  const w = 168;
  const left = Math.min(Math.max(x + 12, 0), width - w);
  const flip = x + 12 + w > width;
  return (
    <div
      className="pointer-events-none absolute top-1 z-10 rounded border border-lineStrong bg-surface px-2.5 py-2 text-xs shadow-lg shadow-black/10"
      style={{ left: flip ? Math.max(0, x - w - 12) : left, width: w }}
    >
      {children}
    </div>
  );
}

export function TipRow({ color, label, value }: { color?: string; label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-px">
      <span className="flex items-center gap-1.5 text-muted">
        {color && <span className="h-2 w-2 rounded-sm" style={{ background: color }} />}
        {label}
      </span>
      <span className="font-mono text-ink">{value}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ line */

interface LineSeries {
  key: string;
  label: string;
  color: string;
  values: (number | null)[];
  area?: boolean;
  smooth?: boolean;
}

// Catmull-Rom -> cubic bezier for a smooth line through the given points.
function smoothD(pts: { x: number; y: number }[]): string {
  if (pts.length < 3) return pts.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join("");
  let d = `M${pts[0].x.toFixed(1)},${pts[0].y.toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += `C${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2.x.toFixed(1)},${p2.y.toFixed(1)}`;
  }
  return d;
}

export function LineChart({
  times,
  series,
  height = 220,
  yMax,
  unit = "%",
}: {
  times: Date[];
  series: LineSeries[];
  height?: number;
  yMax?: number;
  unit?: string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const M = { l: 34, r: 10, t: 10, b: 24 };
  const iw = Math.max(0, width - M.l - M.r);
  const ih = height - M.t - M.b;

  const geo = useMemo(() => {
    if (times.length < 2 || iw <= 0) return null;
    const t0 = times[0].getTime();
    const span = Math.max(1, times[times.length - 1].getTime() - t0);
    const xs = times.map((t) => M.l + ((t.getTime() - t0) / span) * iw);
    const peak = Math.max(0, ...series.flatMap((s) => s.values.filter((v): v is number => v != null)));
    const top = yMax ?? niceCeil(peak * 1.15);
    const y = (v: number) => M.t + ih - (Math.min(v, top) / top) * ih;
    const paths = series.map((s) => {
      // Split into contiguous non-null runs, then render each (smooth or straight).
      const runs: { x: number; y: number }[][] = [];
      let run: { x: number; y: number }[] = [];
      s.values.forEach((v, i) => {
        if (v == null) {
          if (run.length) runs.push(run);
          run = [];
        } else {
          run.push({ x: xs[i], y: y(v) });
        }
      });
      if (run.length) runs.push(run);
      let d = "";
      let area = "";
      for (const r of runs) {
        const seg = s.smooth ? smoothD(r) : r.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join("");
        d += seg;
        if (s.area) area += `${seg}L${r[r.length - 1].x.toFixed(1)},${M.t + ih}L${r[0].x.toFixed(1)},${M.t + ih}Z`;
      }
      return { d, area: s.area ? area : "" };
    });
    const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => top * f);
    const xTickCount = Math.max(2, Math.min(6, Math.floor(iw / 90)));
    const xTicks = Array.from({ length: xTickCount }, (_, i) =>
      Math.round((i / (xTickCount - 1)) * (times.length - 1))
    );
    return { xs, y, paths, ticks, xTicks, top };
  }, [times, series, iw, ih, yMax, M.l, M.t]);

  const onMove = (e: React.MouseEvent<SVGRectElement>) => {
    if (!geo) return;
    const px = e.clientX - (e.currentTarget.ownerSVGElement?.getBoundingClientRect().left ?? 0);
    let lo = 0;
    let hi = geo.xs.length - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (geo.xs[mid] < px) lo = mid;
      else hi = mid;
    }
    setHover(Math.abs(geo.xs[lo] - px) < Math.abs(geo.xs[hi] - px) ? lo : hi);
  };

  return (
    <div ref={ref} className="relative w-full" style={{ height }}>
      {width > 0 && !geo && (
        <div className="grid h-full place-items-center text-xs text-muted">Collecting telemetry samples…</div>
      )}
      {geo && (
        <svg width={width} height={height} className="block" role="img" aria-label={series.map((s) => s.label).join(", ")}>
          <defs>
            {series.map((s) => (
              <linearGradient key={s.key} id={`fill-${s.key}`} x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor={s.color} stopOpacity={0.16} />
                <stop offset="100%" stopColor={s.color} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>
          {geo.ticks.map((v) => (
            <g key={v}>
              <line
                x1={M.l}
                x2={width - M.r}
                y1={geo.y(v)}
                y2={geo.y(v)}
                className={v === 0 ? "stroke-lineStrong" : "stroke-line"}
                strokeDasharray={v === 0 ? undefined : "2 4"}
              />
              <text x={M.l - 8} y={geo.y(v) + 3.5} textAnchor="end" className="fill-faint font-mono text-[10px]">
                {fmt(v)}
              </text>
            </g>
          ))}
          {geo.xTicks.map((i) => (
            <text
              key={i}
              x={geo.xs[i]}
              y={height - 6}
              textAnchor={i === 0 ? "start" : i === times.length - 1 ? "end" : "middle"}
              className="fill-faint font-mono text-[10px]"
            >
              {clock(times[i])}
            </text>
          ))}
          {series.map((s, i) => (
            <g key={s.key}>
              {geo.paths[i].area && <path d={geo.paths[i].area} fill={`url(#fill-${s.key})`} />}
              <path d={geo.paths[i].d} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
            </g>
          ))}
          {hover != null && (
            <g>
              <line x1={geo.xs[hover]} x2={geo.xs[hover]} y1={M.t} y2={M.t + ih} className="stroke-lineStrong" />
              {series.map((s) =>
                s.values[hover] == null ? null : (
                  <circle
                    key={s.key}
                    cx={geo.xs[hover]}
                    cy={geo.y(s.values[hover] as number)}
                    r={4}
                    fill={s.color}
                    className="stroke-surface"
                    strokeWidth={2}
                  />
                )
              )}
            </g>
          )}
          <rect
            x={M.l}
            y={M.t}
            width={iw}
            height={ih}
            fill="transparent"
            onMouseMove={onMove}
            onMouseLeave={() => setHover(null)}
          />
        </svg>
      )}
      {geo && hover != null && (
        <Tooltip x={geo.xs[hover]} width={width}>
          <div className="mb-1 font-mono text-2xs text-faint">{clock(times[hover], true)}</div>
          {series.map((s) => (
            <TipRow
              key={s.key}
              color={s.color}
              label={s.label}
              value={s.values[hover] == null ? "n/a" : `${fmt(s.values[hover] as number)}${unit}`}
            />
          ))}
        </Tooltip>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ bars */

export interface BarDatum {
  key: string;
  label: string;
  value: number | null;
  tip: ReactNode;
  dim?: boolean;
}

/**
 * One bar per run. Positive bars use `color`; with `diverging`, negative bars use
 * `negColor` around a zero baseline. Null values render as an "n/a" tick, never a fake bar.
 */
export function BarChart({
  data,
  height = 180,
  color = "rgb(var(--accent))",
  negColor = "rgb(var(--series-2))",
  diverging = false,
  yMax,
  threshold,
}: {
  data: BarDatum[];
  height?: number;
  color?: string;
  negColor?: string;
  diverging?: boolean;
  yMax?: number;
  threshold?: { value: number; label: string };
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const M = { l: 34, r: 8, t: 12, b: 22 };
  const iw = Math.max(0, width - M.l - M.r);
  const ih = height - M.t - M.b;
  const vals = data.map((d) => d.value).filter((v): v is number => v != null);
  const posTop = yMax ?? niceCeil(Math.max(threshold?.value ?? 0, ...vals, 0) * 1.1 || 1);
  const negTop = diverging ? niceCeil(Math.max(0, ...vals.map((v) => -v)) * 1.1 || 0) : 0;
  const top = diverging ? Math.max(posTop, negTop) : posTop;
  const bottom = diverging && negTop > 0 ? -top : 0;
  const y = (v: number) => M.t + ((top - v) / (top - bottom)) * ih;
  const band = data.length ? iw / data.length : 0;
  const bw = Math.max(3, Math.min(26, band * 0.62));
  const labelEvery = Math.max(1, Math.ceil(42 / Math.max(band, 1)));
  const ticks = bottom < 0 ? [bottom, bottom / 2, 0, top / 2, top] : [0, top / 4, top / 2, (3 * top) / 4, top];

  const barPath = (cx: number, v: number) => {
    const x = cx - bw / 2;
    const y0 = y(0);
    const y1 = y(v);
    const h = Math.abs(y1 - y0);
    if (h < 0.5) return `M${x},${y0 - 0.75}h${bw}v1.5h${-bw}Z`;
    const r = Math.min(4, bw / 2, h);
    if (v >= 0) {
      return `M${x},${y0}V${y1 + r}Q${x},${y1} ${x + r},${y1}H${x + bw - r}Q${x + bw},${y1} ${x + bw},${y1 + r}V${y0}Z`;
    }
    return `M${x},${y0}V${y1 - r}Q${x},${y1} ${x + r},${y1}H${x + bw - r}Q${x + bw},${y1} ${x + bw},${y1 - r}V${y0}Z`;
  };

  return (
    <div ref={ref} className="relative w-full" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height} className="block" role="img">
          {ticks.map((v) => (
            <g key={v}>
              <line
                x1={M.l}
                x2={width - M.r}
                y1={y(v)}
                y2={y(v)}
                className={v === 0 ? "stroke-lineStrong" : "stroke-line"}
                strokeDasharray={v === 0 ? undefined : "2 4"}
              />
              <text x={M.l - 8} y={y(v) + 3.5} textAnchor="end" className="fill-faint font-mono text-[10px]">
                {fmt(v)}
              </text>
            </g>
          ))}
          {threshold && (
            <g>
              <line
                x1={M.l}
                x2={width - M.r}
                y1={y(threshold.value)}
                y2={y(threshold.value)}
                className="stroke-crit"
                strokeDasharray="4 3"
                strokeWidth={1}
              />
              <text x={width - M.r} y={y(threshold.value) - 4} textAnchor="end" className="fill-crit font-mono text-[10px]">
                {threshold.label}
              </text>
            </g>
          )}
          {data.map((d, i) => {
            const cx = M.l + band * i + band / 2;
            const active = hover === i;
            return (
              <g key={d.key} opacity={hover != null && !active ? 0.45 : d.dim ? 0.55 : 1}>
                {d.value == null ? (
                  <text x={cx} y={y(0) - 4} textAnchor="middle" className="fill-faint font-mono text-[9px]">
                    n/a
                  </text>
                ) : (
                  <path d={barPath(cx, d.value)} fill={d.value < 0 ? negColor : color} />
                )}
                {i % labelEvery === 0 && (
                  <text x={cx} y={height - 6} textAnchor="middle" className="fill-faint font-mono text-[10px]">
                    {d.label}
                  </text>
                )}
                <rect
                  x={M.l + band * i}
                  y={M.t}
                  width={band}
                  height={ih}
                  fill="transparent"
                  onMouseEnter={() => setHover(i)}
                  onMouseLeave={() => setHover(null)}
                />
              </g>
            );
          })}
        </svg>
      )}
      {hover != null && data[hover] && (
        <Tooltip x={M.l + band * hover + band / 2} width={width}>
          {data[hover].tip}
        </Tooltip>
      )}
    </div>
  );
}

/* ----------------------------------------------------------------- gauge */

export function Gauge({ value, label }: { value: number | null; label: string }) {
  const N = 42;
  const cx = 120;
  const cy = 118;
  const r1 = 78;
  const r2 = 100;
  const filled = value == null ? 0 : Math.round((value / 100) * N);
  const seg = (i: number) => {
    const gap = 0.012;
    const a0 = Math.PI + (i / N) * Math.PI + gap;
    const a1 = Math.PI + ((i + 1) / N) * Math.PI - gap;
    const p = (a: number, r: number) => `${(cx + r * Math.cos(a)).toFixed(2)},${(cy + r * Math.sin(a)).toFixed(2)}`;
    return `M${p(a0, r1)}L${p(a0, r2)}A${r2},${r2} 0 0 1 ${p(a1, r2)}L${p(a1, r1)}A${r1},${r1} 0 0 0 ${p(a0, r1)}Z`;
  };
  return (
    <svg viewBox="0 0 240 132" className="mx-auto block w-full max-w-[280px]" role="img" aria-label={`${label}: ${value ?? "n/a"}%`}>
      {Array.from({ length: N }, (_, i) => (
        <path key={i} d={seg(i)} className={i < filled ? "fill-accent" : "fill-line"} />
      ))}
      <text x={cx} y={cy - 18} textAnchor="middle" className="fill-ink font-mono text-[30px]">
        {value == null ? "—" : value.toFixed(1)}
        {value != null && <tspan className="fill-muted text-[13px]">%</tspan>}
      </text>
      <text x={cx} y={cy + 2} textAnchor="middle" className="fill-muted text-[10px]">
        {label}
      </text>
    </svg>
  );
}
