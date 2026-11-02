import { useEffect, useRef, useState } from "react";
import type { LiveEvent, Telemetry } from "./types";

/**
 * Subscribes to the backend WebSocket. Exposes the most recent telemetry and a
 * rolling buffer of lifecycle events. Reconnects with backoff if the socket drops.
 */
export function useLive(maxEvents = 200) {
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const retry = useRef(0);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let timer: number | undefined;
    let closed = false;

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${proto}://${location.host}/ws`);

      socket.onopen = () => {
        setConnected(true);
        retry.current = 0;
      };
      socket.onmessage = (ev) => {
        let msg: LiveEvent;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }
        if (msg.type === "TELEMETRY_UPDATE") {
          setTelemetry(msg.payload as unknown as Telemetry);
          return;
        }
        setEvents((prev) => [msg, ...prev].slice(0, maxEvents));
      };
      socket.onclose = () => {
        setConnected(false);
        if (closed) return;
        retry.current = Math.min(retry.current + 1, 6);
        timer = window.setTimeout(connect, 500 * retry.current);
      };
      socket.onerror = () => socket?.close();
    };

    connect();
    return () => {
      closed = true;
      if (timer) clearTimeout(timer);
      socket?.close();
    };
  }, [maxEvents]);

  // Seed the buffer with persisted history so a fresh page isn't blank.
  useEffect(() => {
    fetch(`/api/events/recent?limit=${maxEvents}`)
      .then((r) => (r.ok ? (r.json() as Promise<LiveEvent[]>) : []))
      .then((past) => setEvents((live) => [...live, ...past].slice(0, maxEvents)))
      .catch(() => undefined);
  }, [maxEvents]);

  return { telemetry, events, connected, setEvents };
}
