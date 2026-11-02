import { createContext, useContext } from "react";
import type { AnalyticsRow, LiveEvent, Telemetry } from "./types";

export interface Toast {
  id: number;
  tone: "ok" | "crit" | "info";
  title: string;
  body?: string;
}

interface LiveContextValue {
  telemetry: Telemetry | null;
  events: LiveEvent[];
  connected: boolean;
  activeSessionId: string | null;
  setActiveSessionId: (id: string | null) => void;
  analytics: AnalyticsRow[];
  refreshAnalytics: () => void;
  halted: boolean;
  engageKillSwitch: () => Promise<void>;
  rearm: () => Promise<void>;
  theme: "light" | "dark";
  toggleTheme: () => void;
  notify: (t: Omit<Toast, "id">) => void;
}

export const LiveContext = createContext<LiveContextValue | null>(null);

export function useLiveContext(): LiveContextValue {
  const ctx = useContext(LiveContext);
  if (!ctx) throw new Error("useLiveContext must be used within LiveContext.Provider");
  return ctx;
}
