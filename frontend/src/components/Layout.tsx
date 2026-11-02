import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useLiveContext, type Toast } from "../live-context";
import { Dot, Icon, Kbd, Logo } from "./ui";

type NavItem = { to: string; label: string; icon: Parameters<typeof Icon>[0]["name"] };

const NAV: { heading: string; items: NavItem[] }[] = [
  {
    heading: "Overview",
    items: [
      { to: "/", label: "Dashboard", icon: "grid" },
      { to: "/history", label: "Execution history", icon: "history" },
    ],
  },
  {
    heading: "Operations",
    items: [
      { to: "/ddos", label: "DDoS", icon: "pulse" },
      { to: "/bruteforce", label: "Brute force", icon: "key" },
      { to: "/rat", label: "RAT", icon: "terminal" },
    ],
  },
  {
    heading: "Agent",
    items: [
      { to: "/agent", label: "Activity", icon: "bot" },
      { to: "/reports", label: "Reports", icon: "file" },
    ],
  },
  { heading: "Lab", items: [{ to: "/range", label: "Cyber range", icon: "network" }] },
];

const TITLES: Record<string, string> = Object.fromEntries(
  NAV.flatMap((g) => g.items.map((i) => [i.to, i.label]))
);
TITLES["/"] = "Overview";

const isMac = typeof navigator !== "undefined" && /Mac/i.test(navigator.platform);

function ToastStack({ toasts }: { toasts: Toast[] }) {
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[320px] flex-col gap-2" aria-live="polite">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`pointer-events-auto rounded-md border bg-surface px-3.5 py-3 shadow-xl shadow-black/15 ${
            t.tone === "crit" ? "border-crit/50" : t.tone === "ok" ? "border-ok/40" : "border-line"
          }`}
        >
          <div className="flex items-center gap-2 text-[13px] font-semibold text-ink">
            <Dot tone={t.tone === "crit" ? "crit" : t.tone === "ok" ? "ok" : "muted"} />
            {t.title}
          </div>
          {t.body && <p className="mt-1 pl-3.5 text-xs text-muted">{t.body}</p>}
        </div>
      ))}
    </div>
  );
}

export function Layout({ toasts }: { toasts: Toast[] }) {
  const { telemetry, connected, halted, engageKillSwitch, rearm, theme, toggleTheme, analytics } = useLiveContext();
  const { pathname } = useLocation();
  const running = analytics.filter((r) => !["RESULT", "KILLED", "FAILED"].includes(r.state)).length;

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[224px_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-screen flex-col border-r border-line bg-surface lg:flex">
        <div className="flex h-[52px] items-center gap-2.5 border-b border-line px-4">
          <Logo />
          <span className="text-[14px] font-semibold tracking-tight text-ink">chakravyuh</span>
          <span className="ml-auto rounded border border-line px-1.5 font-mono text-2xs text-muted">range</span>
        </div>
        <nav className="flex flex-1 flex-col gap-5 overflow-y-auto px-3 py-4">
          {NAV.map((group) => (
            <div key={group.heading} className="flex flex-col gap-px">
              <div className="px-2 pb-1.5 font-mono text-2xs uppercase tracking-[0.12em] text-faint">{group.heading}</div>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    `flex h-8 items-center gap-2.5 rounded px-2 text-[13px] transition-colors ${
                      isActive ? "bg-raised font-medium text-ink" : "text-muted hover:bg-raised/60 hover:text-ink"
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <Icon name={item.icon} className={isActive ? "text-accent" : ""} />
                      {item.label}
                      {item.to === "/history" && analytics.length > 0 && (
                        <span className="ml-auto rounded bg-raised px-1.5 font-mono text-2xs text-muted">{analytics.length}</span>
                      )}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="border-t border-line px-4 py-3">
          <div className="flex items-center gap-2 text-xs text-ink">
            <Dot tone={connected ? "ok" : "crit"} pulse={connected} />
            {connected ? "Telemetry live" : "Disconnected"}
          </div>
          <div className="mt-1 truncate font-mono text-2xs text-faint">
            {telemetry?.source ?? "—"} · {telemetry?.hostname ?? "no target"}
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-30 border-b border-line bg-canvas/90 backdrop-blur">
          <div className="flex h-[52px] items-center gap-3 px-4 sm:px-6">
            <div className="flex min-w-0 items-center gap-2 text-xs">
              <span className="lg:hidden">
                <Logo size={20} />
              </span>
              <span className="text-muted">Range</span>
              <span className="text-faint">/</span>
              <span className="truncate font-medium text-ink">{TITLES[pathname] ?? "Overview"}</span>
            </div>

            <div className="ml-auto flex items-center gap-2">
              <span className="hidden items-center gap-2 rounded border border-line bg-surface px-2.5 py-1 font-mono text-2xs text-muted md:inline-flex">
                <Dot tone={telemetry?.available ? "ok" : "warn"} />
                {telemetry?.hostname ?? "target"} · {telemetry?.source ?? "—"}
                {running > 0 && <span className="text-warn">· {running} running</span>}
              </span>
              <button
                onClick={toggleTheme}
                className="grid h-8 w-8 place-items-center rounded border border-line bg-surface text-muted transition-colors hover:text-ink"
                title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
                aria-label="Toggle colour theme"
              >
                <Icon name={theme === "dark" ? "sun" : "moon"} />
              </button>
              {halted ? (
                <button
                  onClick={rearm}
                  className="inline-flex h-8 items-center gap-2 rounded border border-crit bg-crit px-3 text-xs font-semibold text-white"
                  title="Range halted. Click to re-arm."
                >
                  <Icon name="shield" size={14} />
                  Re-arm range
                </button>
              ) : (
                <button
                  onClick={engageKillSwitch}
                  className="inline-flex h-8 items-center gap-2 rounded border border-crit/60 px-3 text-xs font-semibold text-crit transition-colors hover:bg-crit hover:text-white"
                  title={`Terminate all sessions and halt the range (${isMac ? "⌘" : "Win"} + Alt + K)`}
                >
                  <Icon name="power" size={14} />
                  Kill switch
                  <span className="hidden gap-0.5 sm:inline-flex">
                    <Kbd>{isMac ? "⌘" : "Win"}</Kbd>
                    <Kbd>Alt</Kbd>
                    <Kbd>K</Kbd>
                  </span>
                </button>
              )}
            </div>
          </div>

          <nav className="flex gap-1 overflow-x-auto border-t border-line px-3 py-1.5 lg:hidden">
            {NAV.flatMap((g) => g.items).map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `shrink-0 rounded px-2.5 py-1 text-xs ${isActive ? "bg-raised font-medium text-ink" : "text-muted"}`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          {halted && (
            <div className="flex flex-wrap items-center gap-3 border-t border-crit/40 bg-crit/10 px-4 py-2 sm:px-6">
              <span className="flex items-center gap-2 font-mono text-2xs font-medium uppercase tracking-[0.12em] text-crit">
                <Dot tone="crit" pulse />
                Kill switch engaged
              </span>
              <span className="text-xs text-ink">
                Range halted. Running sessions were terminated and new sessions are blocked until you re-arm.
              </span>
            </div>
          )}
        </header>

        <main className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6">
          <Outlet />
        </main>
      </div>

      <ToastStack toasts={toasts} />
    </div>
  );
}
