const PHASES = ["DISCOVER", "PROFILE", "PLAN", "PREPARE", "OBSERVE", "ADAPT", "ANALYZE", "RESULT"];

export function Lifecycle({ current, killed }: { current: string | null; killed?: boolean }) {
  const idx = current ? PHASES.indexOf(current) : -1;
  const finished = current === "RESULT";
  return (
    <ol className="grid grid-cols-4 gap-px overflow-hidden rounded border border-line bg-line sm:grid-cols-8">
      {PHASES.map((p, i) => {
        const done = idx >= 0 && (i < idx || finished);
        const active = i === idx && !killed && !finished;
        const stopped = killed && i === Math.max(idx, 0);
        return (
          <li key={p} className="relative bg-surface px-3 pb-2.5 pt-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-2xs text-faint">{String(i + 1).padStart(2, "0")}</span>
              {stopped && <span className="font-mono text-2xs text-crit">killed</span>}
            </div>
            <div
              className={`mt-1 font-mono text-[11px] font-medium ${
                stopped ? "text-crit" : active ? "text-accent" : done ? "text-ink" : "text-faint"
              }`}
            >
              {p}
            </div>
            <span
              className={`absolute inset-x-0 bottom-0 h-0.5 ${
                stopped ? "bg-crit" : active ? "animate-pulse-dot bg-accent" : done ? "bg-ok" : "bg-transparent"
              }`}
            />
          </li>
        );
      })}
    </ol>
  );
}
