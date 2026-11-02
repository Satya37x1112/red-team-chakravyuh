import { useMemo } from "react";
import { useLiveContext } from "../live-context";
import { Empty, Panel, Tag } from "./ui";

type Metrics = {
  mock_usernames?: string[];
  mock_passwords?: string[];
  mock_wordlist_preview?: string[];
  mock_wordlist_size?: number;
  mock_wordlist_note?: string;
};

/** Shows the latest synthetic wordlist the brute-force agent suggested from
 *  observed telemetry. Display-only: these are mock values, never used. */
export function WordlistPanel() {
  const { events } = useLiveContext();
  const metrics = useMemo<Metrics | null>(() => {
    const ev = events.find(
      (e) => (e.payload?.metrics as Metrics | undefined)?.mock_usernames
    );
    return (ev?.payload?.metrics as Metrics) ?? null;
  }, [events]);

  const users = metrics?.mock_usernames ?? [];
  const pws = metrics?.mock_passwords ?? [];
  const preview = metrics?.mock_wordlist_preview ?? [];

  return (
    <Panel
      title="Suggested wordlist"
      sub={metrics ? `${metrics.mock_wordlist_size ?? users.length * pws.length} entries · shaped by observed OS and account` : "generated when a session runs"}
      actions={<Tag>synthetic</Tag>}
    >
      {!metrics ? (
        <Empty>Run a brute-force session to generate a synthetic wordlist from the real snapshot.</Empty>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="rounded-md border border-warn/40 bg-warn/5 px-3 py-2 text-2xs text-warn">
            {metrics.mock_wordlist_note ?? "Synthetic — display only, never used against any service."}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <div className="mb-1.5 text-2xs uppercase tracking-wide text-muted">Usernames</div>
              <div className="flex flex-wrap gap-1.5">
                {users.map((u) => (
                  <span key={u} className="rounded border border-line bg-raised px-1.5 py-0.5 font-mono text-2xs text-ink">{u}</span>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-1.5 text-2xs uppercase tracking-wide text-muted">Passwords</div>
              <div className="flex flex-wrap gap-1.5">
                {pws.map((p) => (
                  <span key={p} className="rounded border border-line bg-raised px-1.5 py-0.5 font-mono text-2xs text-ink">{p}</span>
                ))}
              </div>
            </div>
          </div>
          {preview.length > 0 && (
            <div>
              <div className="mb-1.5 text-2xs uppercase tracking-wide text-muted">Candidate pairs (preview)</div>
              <ul className="flex flex-col gap-0.5">
                {preview.map((pair) => (
                  <li key={pair} className="font-mono text-2xs text-muted">{pair}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}
