import { useMemo } from "react";
import { useLiveContext } from "../live-context";
import { Empty, Panel, Tag } from "./ui";

type M = {
  simulated_peak_load_pct?: number;
  requests_per_second?: number;
  shannon_entropy?: number;
  entropy_normalized?: number;
  serviced_pct?: number;
  simulated_dropped?: number;
};

/** DDoS detection/measurement metrics (blue-team view) from the latest run. */
export function DdosMetricsPanel() {
  const { events } = useLiveContext();
  const m = useMemo<M | null>(() => {
    const ev = events.find((e) => (e.payload?.metrics as M | undefined)?.simulated_peak_load_pct != null);
    return (ev?.payload?.metrics as M) ?? null;
  }, [events]);

  if (!m) {
    return (
      <Panel title="Traffic analysis" sub="DDoS detection metrics" actions={<Tag>detection</Tag>}>
        <Empty>Run a DDoS session to measure traffic rate, entropy and drop rate.</Empty>
      </Panel>
    );
  }

  const loss = m.serviced_pct == null ? null : Math.round((100 - m.serviced_pct) * 10) / 10;
  const cells: { label: string; value: string; hint?: string }[] = [
    { label: "Peak load", value: m.simulated_peak_load_pct == null ? "—" : `${m.simulated_peak_load_pct}%` },
    { label: "Request rate", value: m.requests_per_second == null ? "—" : `${m.requests_per_second}/s` },
    { label: "Drop rate", value: loss == null ? "—" : `${loss}%` },
    { label: "Shannon entropy", value: m.shannon_entropy == null ? "—" : `${m.shannon_entropy} bit`, hint: "source distribution randomness" },
    { label: "Entropy (norm.)", value: m.entropy_normalized == null ? "—" : `${m.entropy_normalized}`, hint: "1 = evenly spread · low = concentrated flood" },
  ];

  return (
    <Panel title="Traffic analysis" sub="DDoS detection metrics (H = −Σ p·log₂ p)" actions={<Tag>detection</Tag>}>
      <div className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-5">
        {cells.map((c) => (
          <div key={c.label}>
            <div className="text-2xs text-muted">{c.label}</div>
            <div className="mt-0.5 font-mono text-lg text-ink">{c.value}</div>
            {c.hint && <div className="mt-0.5 text-[10px] leading-tight text-faint">{c.hint}</div>}
          </div>
        ))}
      </div>
    </Panel>
  );
}
