import { useMemo } from "react";
import { useLiveContext } from "../live-context";
import { Button, Empty, Icon, Panel, Tag } from "./ui";

type Metrics = {
  mock_usernames?: string[];
  mock_passwords?: string[];
  mock_wordlist_preview?: string[];
  mock_wordlist_size?: number;
  mock_wordlist_note?: string;
  mock_wordlist_confirmed_weak?: string[];
  mock_wordlist_derived_count?: number;
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
  const confirmed = metrics?.mock_wordlist_confirmed_weak ?? [];
  const derived = metrics?.mock_wordlist_derived_count ?? 0;

  const downloadTxt = () => {
    const lines = users.flatMap((u) => pws.map((p) => `${u}:${p}`));
    const body = [`# VAJRAPRAHAAR mock wordlist — ${lines.length} candidate pairs`, "", ...lines].join("\n");
    const url = URL.createObjectURL(new Blob([body], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `vajraprahaar-wordlist-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Panel
      title="Suggested wordlist"
      sub={metrics ? `${metrics.mock_wordlist_size ?? users.length * pws.length} entries · ${derived} telemetry-targeted · ${confirmed.length} confirmed-weak` : "generated when a session runs"}
      actions={
        <span className="flex items-center gap-2">
          {metrics && (
            <Button onClick={downloadTxt} title="Download the wordlist as a .txt file">
              <Icon name="download" size={13} /> .txt
            </Button>
          )}
          <Tag>mock</Tag>
        </span>
      }
    >
      {!metrics ? (
        <Empty>Run a brute-force session to generate a mock wordlist from the real snapshot.</Empty>
      ) : (
        <div className="flex flex-col gap-4">
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
                {pws.map((p) => {
                  const isHit = confirmed.includes(p);
                  return (
                    <span
                      key={p}
                      title={isHit ? "Confirmed weak — cracked against the authorized lab target" : undefined}
                      className={`rounded border px-1.5 py-0.5 font-mono text-2xs ${isHit ? "border-crit/50 bg-crit/10 text-crit" : "border-line bg-raised text-ink"}`}
                    >
                      {p}{isHit ? " ✓" : ""}
                    </span>
                  );
                })}
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
