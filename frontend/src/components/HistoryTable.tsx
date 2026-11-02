import { Fragment, useState } from "react";
import { api } from "../api";
import { KINDS, clock, duration, parseTs, stateLabel, stateTone } from "../lib";
import type { AgentEventRow, AnalyticsRow, Kind } from "../types";
import { EventStream } from "./EventStream";
import { Empty, Icon, Pill, RiskCells, Segmented } from "./ui";

type Filter = "all" | Kind;

export function HistoryFilter({ value, onChange }: { value: Filter; onChange: (f: Filter) => void }) {
  return (
    <Segmented
      value={value}
      onChange={onChange}
      options={[
        { value: "all", label: "All" },
        { value: "ddos", label: "DDoS" },
        { value: "bruteforce", label: "Brute Force" },
        { value: "ratuba", label: "RAT" },
      ]}
    />
  );
}

export function HistoryTable({ rows, filter, limit }: { rows: AnalyticsRow[]; filter: Filter; limit?: number }) {
  const [open, setOpen] = useState<string | null>(null);
  const [events, setEvents] = useState<Record<string, AgentEventRow[]>>({});
  const shown = rows
    .filter((r) => filter === "all" || r.kind === filter)
    .slice()
    .reverse()
    .slice(0, limit);

  const toggle = async (id: string) => {
    setOpen((cur) => (cur === id ? null : id));
    if (!events[id]) {
      try {
        const s = await api.session(id);
        setEvents((m) => ({ ...m, [id]: [...s.events].reverse() }));
      } catch {
        setEvents((m) => ({ ...m, [id]: [] }));
      }
    }
  };

  if (!shown.length) return <div className="p-4"><Empty>No sessions recorded{filter !== "all" ? " for this scenario" : ""} yet.</Empty></div>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-xs">
        <thead>
          <tr className="border-y border-line text-left font-mono text-2xs uppercase tracking-wider text-faint">
            <th className="px-4 py-2 font-medium">Time</th>
            <th className="px-3 py-2 font-medium">Session</th>
            <th className="px-3 py-2 font-medium">Scenario</th>
            <th className="px-3 py-2 font-medium">Decision</th>
            <th className="px-3 py-2 font-medium">Risk</th>
            <th className="px-3 py-2 font-medium">Duration</th>
            <th className="px-3 py-2 font-medium">Status</th>
            <th className="w-8" />
          </tr>
        </thead>
        <tbody>
          {shown.map((r) => {
            const meta = KINDS[r.kind];
            const isOpen = open === r.id;
            return (
              <Fragment key={r.id}>
                <tr
                  onClick={() => toggle(r.id)}
                  className={`cursor-pointer border-b border-line transition-colors hover:bg-raised/60 ${isOpen ? "bg-raised/60" : ""}`}
                >
                  <td className="px-4 py-2.5 font-mono text-muted">{clock(parseTs(r.started_at))}</td>
                  <td className="px-3 py-2.5 font-mono font-medium text-ink">{r.label}</td>
                  <td className="px-3 py-2.5 text-ink">{meta.name}</td>
                  <td className="px-3 py-2.5 font-mono text-ink">
                    {r.decision == null ? <span className="text-faint">—</span> : `${r.decision} ${meta.decisionUnit}`}
                  </td>
                  <td className="px-3 py-2.5">
                    <RiskCells score={r.risk_score} />
                  </td>
                  <td className="px-3 py-2.5 font-mono text-muted">{duration(r.duration_s)}</td>
                  <td className="px-3 py-2.5">
                    <Pill tone={stateTone(r.state)}>{stateLabel(r.state)}</Pill>
                  </td>
                  <td className="pr-3 text-faint">
                    <Icon name="chevron" size={14} className={`transition-transform ${isOpen ? "rotate-180" : ""}`} />
                  </td>
                </tr>
                {isOpen && (
                  <tr className="border-b border-line bg-raised/40">
                    <td colSpan={8} className="px-4 py-3">
                      {events[r.id] ? (
                        <EventStream events={events[r.id]} height={220} footer={false} empty="No events persisted." />
                      ) : (
                        <div className="py-3 text-xs text-muted">Loading events…</div>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
