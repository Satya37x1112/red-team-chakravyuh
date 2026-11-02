import { useLiveContext } from "../live-context";
import { clock, parseTs } from "../lib";
import type { AgentEventRow, LiveEvent } from "../types";
import { Dot } from "./ui";

type Row = { key: string; type: string; message: string; time: Date | null };

function toRows(events: (LiveEvent | AgentEventRow)[]): Row[] {
  return events.map((e, i) => {
    if ("event_type" in e) {
      return { key: e.id, type: e.event_type, message: e.message, time: parseTs(e.created_at) };
    }
    return {
      key: `${e.ts ?? ""}-${i}`,
      type: e.type,
      message: (e.payload?.message as string) ?? "",
      time: parseTs(e.ts) ?? null,
    };
  });
}

function tone(type: string): string {
  if (type.startsWith("KILL")) return "text-crit";
  if (type.includes("COMPLETE") || type === "TARGET_IDENTIFIED") return "text-ok";
  if (type.startsWith("UBA") || type.startsWith("RISK")) return "text-warn";
  if (type.startsWith("PLAN") || type.startsWith("BOT")) return "text-accent";
  return "text-muted";
}

const label = (type: string) => type.toLowerCase().replace(/_/g, " ");

export function EventStream({
  events,
  empty = "No events yet.",
  height = 300,
  footer = true,
}: {
  events: (LiveEvent | AgentEventRow)[];
  empty?: string;
  height?: number;
  footer?: boolean;
}) {
  const { connected } = useLiveContext();
  const rows = toRows(events);
  return (
    <div className="overflow-hidden rounded border border-line bg-canvas font-mono text-[11.5px]">
      <div className="overflow-y-auto px-3 py-2" style={{ maxHeight: height, minHeight: Math.min(height, 140) }}>
        {rows.length === 0 ? (
          <div className="py-6 text-center text-muted">{empty}</div>
        ) : (
          <ul>
            {rows.map((r) => (
              <li key={r.key} className="grid grid-cols-[64px_150px_minmax(0,1fr)] gap-3 py-[3px] leading-5">
                <span className="text-faint">{clock(r.time, true)}</span>
                <span className={`truncate ${tone(r.type)}`}>{label(r.type)}</span>
                <span className="break-words text-ink/85">{r.message}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      {footer && (
        <div className="flex items-center gap-2 border-t border-line px-3 py-1.5 text-2xs text-faint">
          <Dot tone={connected ? "ok" : "crit"} pulse={connected} />
          {connected ? "listening on /ws" : "socket disconnected — retrying"}
        </div>
      )}
    </div>
  );
}
