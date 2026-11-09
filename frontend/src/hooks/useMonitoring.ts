import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../services/api";
import type { MonitoringSnapshot } from "../types";

export function useMonitoring(onAlert: (snapshot: MonitoringSnapshot) => void) {
  const [snapshot, setSnapshot] = useState<MonitoringSnapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const onAlertRef = useRef(onAlert);
  const seenAlert = useRef(0);

  useEffect(() => {
    onAlertRef.current = onAlert;
  }, [onAlert]);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retryTimer = 0;
    let connectTimer = 0;
    let stopped = false;
    let hasInitialSnapshot = false;
    let observedSession: number | null = null;
    let delay = 500;

    const connect = () => {
      if (stopped) return;
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      socket = new WebSocket(`${protocol}//${window.location.host}/ws/monitoring`);
      socket.onopen = () => {
        setConnected(true);
        setError(null);
        delay = 500;
      };
      socket.onmessage = (event) => {
        const next = JSON.parse(event.data) as MonitoringSnapshot;
        setSnapshot(next);
        if (!hasInitialSnapshot || next.session_id !== observedSession) {
          hasInitialSnapshot = true;
          observedSession = next.session_id;
          seenAlert.current = next.latest_alert_id;
        } else if (next.latest_alert_id > seenAlert.current) {
          seenAlert.current = next.latest_alert_id;
          onAlertRef.current(next);
        }
      };
      socket.onerror = () => setError("Live connection interrupted. Reconnecting…");
      socket.onclose = () => {
        setConnected(false);
        if (!stopped) {
          retryTimer = window.setTimeout(connect, delay);
          delay = Math.min(delay * 2, 5000);
        }
      };
    };

    connectTimer = window.setTimeout(connect, 0);
    api.status().then(setSnapshot).catch((reason: Error) => setError(reason.message));
    return () => {
      stopped = true;
      window.clearTimeout(connectTimer);
      window.clearTimeout(retryTimer);
      socket?.close();
    };
  }, []);

  const start = useCallback(async () => {
    setError(null);
    try {
      const result = await api.start();
      setSnapshot(result);
      return result;
    } catch (reason) {
      setError((reason as Error).message);
      throw reason;
    }
  }, []);

  const stop = useCallback(async () => {
    setError(null);
    try {
      const result = await api.stop();
      setSnapshot(result);
      return result;
    } catch (reason) {
      setError((reason as Error).message);
      throw reason;
    }
  }, []);

  return { snapshot, connected, error, setError, start, stop };
}
