import type {
  CameraCatalog,
  DetectionSettings,
  MonitoringSnapshot,
  SessionRecord,
} from "../types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail ?? message;
    } catch {
      // Retain the HTTP status when the server does not return JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export const api = {
  status: () => request<MonitoringSnapshot>("/api/status"),
  start: () =>
    request<MonitoringSnapshot>("/api/monitoring/start", { method: "POST" }),
  stop: () =>
    request<MonitoringSnapshot>("/api/monitoring/stop", { method: "POST" }),
  settings: () => request<DetectionSettings>("/api/settings"),
  updateSettings: (settings: DetectionSettings) =>
    request<DetectionSettings>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    }),
  cameras: () => request<CameraCatalog>("/api/cameras"),
  selectCamera: (cameraId: string) =>
    request<CameraCatalog>("/api/cameras/select", {
      method: "POST",
      body: JSON.stringify({ camera_id: cameraId }),
    }),
  sessions: () => request<{ sessions: SessionRecord[] }>("/api/sessions"),
  clearSessions: () =>
    request<{ cleared: boolean }>("/api/sessions?confirm=true", {
      method: "DELETE",
    }),
};
