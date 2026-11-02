import { EventStream } from "../components/EventStream";
import { Panel } from "../components/ui";
import { useLiveContext } from "../live-context";

export function AgentActivity() {
  const { events } = useLiveContext();
  const counts = events.reduce<Record<string, number>>((m, e) => {
    m[e.type] = (m[e.type] ?? 0) + 1;
    return m;
  }, {});
  const top = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 8);
  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight text-ink">Agent activity</h1>
        <p className="mt-1 text-xs text-muted">Every lifecycle event broadcast over the WebSocket since this page loaded.</p>
      </div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_260px]">
        <Panel title="Console" actions={<span className="font-mono text-2xs text-faint">{events.length} events</span>}>
          <EventStream events={events} height={560} empty="No agent activity yet. Start a session from an operation page." />
        </Panel>
        <Panel title="Event mix">
          {top.length === 0 ? (
            <p className="text-xs text-muted">Nothing received yet.</p>
          ) : (
            <ul className="flex flex-col gap-2.5">
              {top.map(([type, n]) => (
                <li key={type}>
                  <div className="flex justify-between font-mono text-2xs">
                    <span className="truncate text-muted">{type.toLowerCase().replace(/_/g, " ")}</span>
                    <span className="text-ink">{n}</span>
                  </div>
                  <div className="mt-1 h-1 rounded-full bg-line">
                    <div className="h-full rounded-full bg-accent" style={{ width: `${(n / top[0][1]) * 100}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
