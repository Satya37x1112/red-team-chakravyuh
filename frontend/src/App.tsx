import { useCallback, useEffect, useRef, useState } from "react";
import { Route, Routes } from "react-router-dom";
import { api } from "./api";
import { Layout } from "./components/Layout";
import { LiveContext, type Toast } from "./live-context";
import { useLive } from "./useLive";
import { Dashboard } from "./pages/Dashboard";
import { Operation } from "./pages/Operation";
import { AgentActivity } from "./pages/AgentActivity";
import { History } from "./pages/History";
import { Reports } from "./pages/Reports";
import { Range } from "./pages/Range";
import { Integrations } from "./pages/Integrations";
import { OperationsCenter } from "./pages/OperationsCenter";
import { Report as PentestReport } from "./pages/Report";
import type { AnalyticsRow } from "./types";

const REFRESH_ON = new Set(["KILL_SWITCH_ACTIVATED", "KILL_SWITCH_ENGAGED", "SIMULATION_COMPLETE", "PLAN_CREATED"]);

export default function App() {
  const { telemetry, events, connected } = useLive();
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsRow[]>([]);
  const [halted, setHalted] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [theme, setTheme] = useState<"light" | "dark">(() =>
    document.documentElement.classList.contains("dark") ? "dark" : "light"
  );
  const toastSeq = useRef(0);

  const notify = useCallback((t: Omit<Toast, "id">) => {
    const id = ++toastSeq.current;
    setToasts((prev) => [...prev, { ...t, id }].slice(-4));
    window.setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== id)), 5200);
  }, []);

  const refreshAnalytics = useCallback(() => {
    api.analytics().then(setAnalytics).catch(() => undefined);
  }, []);

  useEffect(() => {
    refreshAnalytics();
    api.health().then((h) => setHalted(h.halted)).catch(() => undefined);
  }, [refreshAnalytics]);

  // React to server-side events, whichever client triggered them.
  const latest = events[0];
  useEffect(() => {
    if (!latest) return;
    if (latest.type === "KILL_SWITCH_ENGAGED") setHalted(true);
    if (latest.type === "KILL_SWITCH_RESET") setHalted(false);
    if (REFRESH_ON.has(latest.type)) refreshAnalytics();
  }, [latest, refreshAnalytics]);

  const engageKillSwitch = useCallback(async () => {
    try {
      const res = await api.killSwitch();
      setHalted(true);
      setActiveSessionId(null);
      notify({
        tone: "crit",
        title: "Kill switch engaged",
        body: res.killed.length
          ? `${res.killed.length} session${res.killed.length > 1 ? "s" : ""} terminated. Range halted.`
          : "No session was running. Range halted — new sessions are blocked.",
      });
      refreshAnalytics();
    } catch (e) {
      notify({ tone: "crit", title: "Kill switch request failed", body: String((e as Error).message) });
    }
  }, [notify, refreshAnalytics]);

  const rearm = useCallback(async () => {
    try {
      await api.rearm();
      setHalted(false);
      notify({ tone: "ok", title: "Range re-armed", body: "Sessions can be started again." });
    } catch (e) {
      notify({ tone: "crit", title: "Re-arm failed", body: String((e as Error).message) });
    }
  }, [notify]);

  // Win + Alt + K. Ctrl + Alt + K is a fallback for desktops that swallow the Win key.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code !== "KeyK" || !e.altKey) return;
      const win = e.metaKey || e.getModifierState("Meta") || e.getModifierState("OS");
      if (!win && !e.ctrlKey) return;
      e.preventDefault();
      engageKillSwitch();
    };
    window.addEventListener("keydown", onKey, { capture: true });
    return () => window.removeEventListener("keydown", onKey, { capture: true });
  }, [engageKillSwitch]);

  const toggleTheme = useCallback(() => {
    setTheme((t) => {
      const next = t === "dark" ? "light" : "dark";
      document.documentElement.classList.toggle("dark", next === "dark");
      try {
        localStorage.setItem("cv-theme", next);
      } catch {
        /* private mode */
      }
      return next;
    });
  }, []);

  return (
    <LiveContext.Provider
      value={{
        telemetry,
        events,
        connected,
        activeSessionId,
        setActiveSessionId,
        analytics,
        refreshAnalytics,
        halted,
        engageKillSwitch,
        rearm,
        theme,
        toggleTheme,
        notify,
      }}
    >
      <Routes>
        <Route element={<Layout toasts={toasts} />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/central" element={<OperationsCenter />} />
          <Route path="/report" element={<PentestReport />} />
          <Route path="/ddos" element={<Operation kind="ddos" />} />
          <Route path="/bruteforce" element={<Operation kind="bruteforce" />} />
          <Route path="/rat" element={<Operation kind="ratuba" />} />
          <Route path="/agent" element={<AgentActivity />} />
          <Route path="/history" element={<History />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/integrations" element={<Integrations />} />
          <Route path="/range" element={<Range />} />
        </Route>
      </Routes>
    </LiveContext.Provider>
  );
}
