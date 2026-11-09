import {
  Activity,
  AlertTriangle,
  AudioLines,
  Camera,
  Check,
  ChevronRight,
  CircleHelp,
  Eye,
  EyeOff,
  LayoutDashboard,
  LoaderCircle,
  Pause,
  Play,
  RefreshCw,
  Settings2,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Fragment,
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { useMonitoring } from "./hooks/useMonitoring";
import { api } from "./services/api";
import type {
  DetectionSettings,
  CameraCatalog,
  MonitoringSnapshot,
  PageName,
  SessionRecord,
} from "./types";

type ChartPoint = { time: string; ear: number };

function formatDuration(seconds: number) {
  const safe = Math.max(0, Math.floor(seconds));
  return `${Math.floor(safe / 60)
    .toString()
    .padStart(2, "0")}:${(safe % 60).toString().padStart(2, "0")}`;
}

function formatDate(value: string) {
  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function App() {
  const [page, setPage] = useState<PageName>("Dashboard");
  const [settings, setSettings] = useState<DetectionSettings | null>(null);
  const [settingsMessage, setSettingsMessage] = useState("");
  const [cameraCatalog, setCameraCatalog] = useState<CameraCatalog | null>(null);
  const [cameraLoading, setCameraLoading] = useState(false);
  const [cameraBusy, setCameraBusy] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [historyError, setHistoryError] = useState("");
  const [chartData, setChartData] = useState<ChartPoint[]>([]);
  const [clock, setClock] = useState(new Date());
  const [cameraImageFailed, setCameraImageFailed] = useState(false);
  const audioContext = useRef<AudioContext | null>(null);
  const lastChartSample = useRef(0);
  const lastBeep = useRef(0);
  const [pending, setPending] = useState(false);
  const [audioError, setAudioError] = useState("");
  const [themePreference, setThemePreference] = useState<"light" | "dark" | "system">(() => {
    try {
      const stored = localStorage.getItem("wakeup2-theme");
      return stored === "light" || stored === "dark" ? stored : "system";
    } catch {
      return "system";
    }
  });

  const playAlert = useCallback((volume: number) => {
    if (volume <= 0) return;
    const now = Date.now();
    if (now - lastBeep.current < 1200) return;
    lastBeep.current = now;
    const context = audioContext.current;
    if (!context) return;

    void context.resume().then(() => {
      const start = context.currentTime;
      [0, 0.32].forEach((offset) => {
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        oscillator.type = "sine";
        oscillator.frequency.value = 740;
        gain.gain.setValueAtTime(Math.max(0.005, volume * 0.18), start + offset);
        gain.gain.exponentialRampToValueAtTime(0.005, start + offset + 0.22);
        oscillator.connect(gain);
        gain.connect(context.destination);
        oscillator.start(start + offset);
        oscillator.stop(start + offset + 0.23);
      });
    }).catch(() => {
      setAudioError("Browser audio is unavailable or blocked; visual alerts remain active.");
    });
  }, []);

  const onAlert = useCallback(
    (_snapshot: MonitoringSnapshot) => {
      if (settings?.audio_enabled) playAlert(settings.audio_volume);
    },
    [playAlert, settings],
  );
  const { snapshot, connected, error, setError, start, stop } =
    useMonitoring(onAlert);

  useEffect(() => {
    api.settings().then(setSettings).catch((reason: Error) => setError(reason.message));
    const timer = window.setInterval(() => setClock(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, [setError]);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const applyTheme = () => {
      const isDark = themePreference === "dark" || (themePreference === "system" && media.matches);
      const resolved = isDark ? "dark" : "light";
      document.documentElement.dataset.theme = resolved;
      document.documentElement.style.colorScheme = resolved;
    };

    try {
      localStorage.setItem("wakeup2-theme", themePreference);
    } catch {
      setSettingsMessage("Theme preference could not be saved in this browser.");
    }
    applyTheme();
    media.addEventListener("change", applyTheme);
    return () => media.removeEventListener("change", applyTheme);
  }, [themePreference]);

  useEffect(() => {
    if (snapshot?.ear_mean == null || !snapshot.monitoring) return;
    const now = Date.now();
    if (now - lastChartSample.current < 500) return;
    lastChartSample.current = now;
    setChartData((previous) =>
      [...previous, { time: new Date().toLocaleTimeString(), ear: snapshot.ear_mean! }].slice(
        -120,
      ),
    );
  }, [snapshot]);

  useEffect(() => {
    if (page !== "Monitoring History") return;
    setHistoryError("");
    api
      .sessions()
      .then(({ sessions: items }) => setSessions(items))
      .catch((reason: Error) => setHistoryError(reason.message));
  }, [page]);

  const refreshCameras = useCallback(async () => {
    setCameraLoading(true);
    setCameraError("");
    try {
      const catalog = await api.cameras();
      setCameraCatalog(catalog);
      if (catalog.error) setCameraError(catalog.error);
    } catch (reason) {
      setCameraError((reason as Error).message);
    } finally {
      setCameraLoading(false);
    }
  }, []);

  useEffect(() => {
    if (page === "Settings") void refreshCameras();
  }, [page, refreshCameras]);

  const startMonitoring = async () => {
    setError(null);
    if (settings?.audio_enabled && !audioContext.current) {
      try {
        audioContext.current = new AudioContext();
        await audioContext.current.resume();
        setAudioError("");
      } catch {
        setAudioError("Browser audio is unavailable or blocked; monitoring will continue silently.");
      }
    }
    setChartData([]);
    setCameraImageFailed(false);
    setPending(true);
    try {
      await start();
    } catch {
      // The hook displays backend errors in the dashboard.
    } finally {
      setPending(false);
    }
  };

  const stopMonitoring = async () => {
    setPending(true);
    try {
      await stop();
    } catch {
      // The hook displays backend errors in the dashboard.
    } finally {
      setPending(false);
    }
  };

  const saveSettings = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!settings) return;
    setSettingsMessage("");
    try {
      const saved = await api.updateSettings(settings);
      setSettings(saved);
      setSettingsMessage("Settings saved and applied.");
    } catch (reason) {
      setSettingsMessage((reason as Error).message);
    }
  };

  const chooseCamera = async (cameraId: string) => {
    if (!cameraId) return;
    setCameraBusy(true);
    setCameraError("");
    setSettingsMessage("");
    try {
      const catalog = await api.selectCamera(cameraId);
      setCameraCatalog(catalog);
      const selected = catalog.cameras.find(
        (camera) => camera.camera_id === catalog.selected_camera_id,
      );
      if (selected) {
        setSettings((current) =>
          current
            ? {
                ...current,
                camera_id: selected.camera_id,
                camera_index: selected.index,
              }
            : current,
        );
        setSettingsMessage(`Camera switched to ${selected.name}.`);
      }
      setCameraImageFailed(false);
    } catch (reason) {
      const message = (reason as Error).message;
      setCameraError(message);
    } finally {
      setCameraBusy(false);
    }
  };

  const testAlert = async () => {
    if (!settings) return;
    try {
      if (!audioContext.current) audioContext.current = new AudioContext();
      await audioContext.current.resume();
      setAudioError("");
    } catch {
      setAudioError("Browser audio could not be started. Check browser audio permissions.");
      return;
    }
    playAlert(settings.audio_volume);
    setSettingsMessage("Test alert played in your browser.");
  };

  const clearHistory = async () => {
    if (!window.confirm("Permanently clear all locally stored monitoring history?")) return;
    try {
      await api.clearSessions();
      setSessions([]);
    } catch (reason) {
      setHistoryError((reason as Error).message);
    }
  };

  const statusLabel = snapshot?.monitoring
    ? snapshot.status === "STARTING"
      ? "Starting"
      : snapshot.status === "DROWSINESS_DETECTED"
        ? "Alert active"
        : "Monitoring"
    : snapshot?.status === "CAMERA_ERROR"
      ? "Camera error"
      : "Inactive";
  const isAlert = snapshot?.status === "DROWSINESS_DETECTED";

  return (
    <div className="app-shell">
      <header className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Eye size={19} strokeWidth={2} /></div>
          <div>
            <div className="brand-name">WakeUp<span>2</span></div>
          </div>
        </div>
        <nav className="nav-list" aria-label="Main navigation">
          <NavButton
            active={page === "Dashboard"}
            icon={<LayoutDashboard size={16} />}
            onClick={() => setPage("Dashboard")}
          >
            Monitor
          </NavButton>
          <NavButton
            active={page === "Monitoring History"}
            icon={<Activity size={16} />}
            onClick={() => setPage("Monitoring History")}
          >
            History
          </NavButton>
          <NavButton
            active={page === "Settings"}
            icon={<Settings2 size={16} />}
            onClick={() => setPage("Settings")}
          >
            Settings
          </NavButton>
          <NavButton
            active={page === "About"}
            icon={<CircleHelp size={16} />}
            onClick={() => setPage("About")}
          >
            About
          </NavButton>
        </nav>
        <div className="connection-pill">
          <span className={`connection-dot ${connected ? "connected" : ""}`} />
          {connected ? "Connected" : "Reconnecting"}
        </div>
      </header>

      <main className="main-area">
        <header className="topbar">
          <div>
            <h1>{page === "Dashboard" ? "Monitor" : page === "Monitoring History" ? "History" : page}</h1>
          </div>
          <div className="topbar-right">
            <div className="clock">{clock.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div>
            <div className={`status-indicator ${isAlert ? "danger" : snapshot?.monitoring ? "live" : ""}`}>
              <span className="status-dot" />{statusLabel}
            </div>
          </div>
        </header>

        {(error || snapshot?.camera_error || snapshot?.camera_notice) && (
          <div className="error-banner" role={snapshot?.camera_error || error ? "alert" : "status"}>
            <AlertTriangle size={17} />
            <span>{snapshot?.camera_error ?? error ?? snapshot?.camera_notice}</span>
          </div>
        )}
        {audioError && (
          <div className="error-banner" role="status">
            <AudioLines size={17} />
            <span>{audioError}</span>
          </div>
        )}

        {page === "Dashboard" && (
          <section className="page-content dashboard-page">
            <div className="welcome-row">
              <div>
                <h2>Live monitoring</h2>
                <p>Eye tracking and closure measurements from your local camera.</p>
              </div>
            </div>

            <div className="dashboard-grid">
              <section className={`panel camera-panel ${isAlert ? "panel-alert" : ""}`}>
                <div className="panel-heading">
                  <div><h3>Camera</h3><span>{snapshot?.monitoring ? "Processed locally" : "Not in use"}</span></div>
                  <div className={`feed-state ${snapshot?.monitoring ? "feed-on" : ""}`}><span className="status-dot" />{snapshot?.monitoring ? "Live" : "Idle"}</div>
                </div>
                <div className="video-stage">
                  {snapshot?.monitoring && !cameraImageFailed ? (
                    <img
                      className="camera-feed"
                      src={`/api/video?session=${snapshot.session_id ?? ""}`}
                      alt="Live webcam feed with locally processed eye landmarks"
                      onError={() => setCameraImageFailed(true)}
                    />
                  ) : (
                    <div className="camera-placeholder">
                      <div className="camera-placeholder-icon">{cameraImageFailed ? <Camera size={24} /> : <EyeOff size={24} />}</div>
                      <strong>{cameraImageFailed ? "Video stream unavailable" : "Camera standing by"}</strong>
                      <span>{cameraImageFailed ? "Check camera access, then try again." : "Start monitoring to connect the camera and view eye tracking."}</span>
                    </div>
                  )}
                </div>
                <div className="camera-controls">
                  <div className="face-state">
                    <span className={`face-indicator ${snapshot?.face_detected ? "face-ok" : ""}`} />
                    <span>Face {snapshot?.face_detected ? "detected" : snapshot?.monitoring ? "not detected" : "tracking off"}</span>
                  </div>
                  <div className="control-actions">
                    <button className="button button-secondary" onClick={stopMonitoring} disabled={!snapshot?.monitoring || pending}>
                      {pending ? <LoaderCircle className="spin" size={16} /> : <Pause size={16} />} Stop
                    </button>
                    <button className="button button-primary" onClick={startMonitoring} disabled={!!snapshot?.monitoring || pending || !connected}>
                      {pending ? <LoaderCircle className="spin" size={16} /> : <Play size={16} />} Start monitoring
                    </button>
                  </div>
                </div>
              </section>

              <section className={`metrics-panel ${isAlert ? "metric-danger" : ""}`} aria-label="Current detection measurements">
                <div className="metrics-title">Detection</div>
                <div className={`metric-row ${isAlert ? "text-danger" : ""}`}>
                  <span>Eye status</span><strong>{eyeStatusLabel(snapshot)}</strong>
                </div>
                <div className="metric-row">
                  <span>Mean EAR <small>Threshold {settings?.ear_threshold.toFixed(2) ?? "0.20"}</small></span>
                  <strong className="mono">{snapshot?.ear_mean == null ? "—" : snapshot.ear_mean.toFixed(3)}</strong>
                </div>
                <div className="metric-row">
                  <span>Eye closure</span>
                  <strong className="mono">{(snapshot?.closure_duration_seconds ?? 0).toFixed(1)} s</strong>
                </div>
                <div className="metric-row">
                  <span>Alerts this session</span>
                  <strong className={isAlert ? "text-danger" : ""}>{snapshot?.alert_count ?? 0}</strong>
                </div>
                <div className="monitoring-state">
                  <span className={`status-dot ${snapshot?.monitoring ? "active-dot" : ""}`} />
                  <span>{isAlert ? "Prolonged eye closure detected" : statusDescription(snapshot)}</span>
                </div>
              </section>

              <section className={`panel graph-panel ${isAlert ? "panel-alert" : ""}`}>
                <div className="panel-heading graph-heading">
                  <div><h3>EAR history</h3><span>Recent measurements</span></div>
                  <div className="graph-legend"><span /> EAR <i /> Threshold</div>
                </div>
                <div className="chart-wrap">
                  {chartData.length ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData} margin={{ top: 12, right: 12, left: -18, bottom: 0 }}>
                        <CartesianGrid stroke="var(--border)" strokeDasharray="3 5" vertical={false} />
                        <XAxis dataKey="time" tick={{ fill: "var(--secondary)", fontSize: 10 }} tickLine={false} axisLine={false} minTickGap={42} />
                        <YAxis domain={[0, "auto"]} tick={{ fill: "var(--secondary)", fontSize: 10 }} tickLine={false} axisLine={false} />
                        <Tooltip contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 6, color: "var(--text)" }} labelStyle={{ color: "var(--secondary)" }} />
                        <ReferenceLine y={settings?.ear_threshold ?? 0.2} stroke="var(--chart-threshold)" strokeDasharray="5 5" />
                        <Line type="monotone" dataKey="ear" stroke="var(--chart-line)" strokeWidth={2} dot={false} isAnimationActive={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="chart-empty"><span>EAR measurements will appear when a face is detected.</span></div>
                  )}
                </div>
              </section>

              {isAlert && <section className="alert-card" role="alert"><AlertTriangle size={18} /><div><strong>WAKE UP!</strong><span>Prolonged eye closure detected. Please take a break.</span></div></section>}
            </div>
          </section>
        )}

        {page === "Monitoring History" && (
          <section className="page-content">
            <div className="welcome-row">
              <div><h2>Monitoring history</h2><p>Local session summaries and drowsiness alert timestamps.</p></div>
              <button className="button button-secondary" onClick={clearHistory} disabled={!sessions.length}><Trash2 size={15} /> Clear history</button>
            </div>
            {historyError && <div className="error-banner"><AlertTriangle size={17} />{historyError}</div>}
            <div className="panel history-panel">
              {sessions.length ? (
                <div className="table-scroll">
                  <table className="history-table">
                    <thead><tr><th>Session</th><th>Started</th><th>Duration</th><th>Alerts</th><th>Configuration</th></tr></thead>
                    <tbody>
                      {sessions.map((session) => (
                        <Fragment key={session.id}>
                          <tr>
                            <td><strong>Session #{session.id}</strong><small>{session.ended_at ? "Completed" : "In progress"}</small></td>
                            <td>{formatDate(session.started_at)}</td>
                            <td className="mono">{formatDuration(session.duration_seconds)}</td>
                            <td className={session.alert_count ? "history-alert" : ""}>{session.alert_count}</td>
                            <td className="history-config">EAR {session.settings.ear_threshold.toFixed(2)} · {session.settings.closed_duration_seconds}s</td>
                          </tr>
                          {session.alert_timestamps.length > 0 && (
                            <tr className="alert-times-row">
                              <td colSpan={5}><div className="alert-times">{session.alert_timestamps.map((time, index) => <span key={`${time}-${index}`}>Alert {index + 1} · {formatDate(time)}</span>)}</div></td>
                            </tr>
                          )}
                        </Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <div className="empty-history"><Activity size={23} /><strong>No sessions yet</strong><span>Start monitoring to create your first local session record.</span></div>}
            </div>
            <p className="history-note"><ShieldAlert size={15} /> History is stored locally in SQLite. No camera footage is saved.</p>
          </section>
        )}

        {page === "Settings" && (
          <section className="page-content narrow-page">
            <div className="welcome-row"><div><h2>Detection settings</h2><p>Adjust sensitivity and local alert behavior.</p></div></div>
            <form className="panel settings-panel" onSubmit={saveSettings}>
              {settings ? (
                <>
                  <div className="form-section-title"><Camera size={17} /> Camera</div>
                  <div className="setting-row camera-setting-row">
                    <span>
                      <strong>Camera device</strong>
                      <small>
                        {cameraCatalog?.cameras.find(
                          (camera) => camera.camera_id === cameraCatalog.selected_camera_id,
                        )?.name ?? "Select an available camera. Device names come from macOS."}
                      </small>
                    </span>
                    <div className="camera-selector">
                      <select
                        className="theme-select camera-select"
                        aria-label="Camera device"
                        value={cameraCatalog?.selected_camera_id ?? ""}
                        disabled={cameraLoading || cameraBusy || !cameraCatalog?.cameras.length}
                        onChange={(event) => void chooseCamera(event.target.value)}
                      >
                        <option value="">
                          {cameraLoading
                            ? "Loading cameras…"
                            : cameraCatalog?.cameras.length
                              ? "Select a camera"
                              : "No cameras found"}
                        </option>
                        {cameraCatalog?.cameras.map((camera) => (
                          <option key={camera.camera_id} value={camera.camera_id}>
                            {camera.name}
                          </option>
                        ))}
                      </select>
                      <button
                        className="button button-secondary refresh-cameras"
                        type="button"
                        onClick={() => void refreshCameras()}
                        disabled={cameraLoading || cameraBusy}
                        aria-label="Refresh camera list"
                        title="Refresh camera list"
                      >
                        {cameraLoading ? <LoaderCircle className="spin" size={15} /> : <RefreshCw size={15} />}
                        <span>Refresh</span>
                      </button>
                    </div>
                  </div>
                  {(cameraCatalog?.notice || cameraError) && (
                    <div className="camera-message" role={cameraError ? "alert" : "status"}>
                      {cameraError || cameraCatalog?.notice}
                    </div>
                  )}
                  {!cameraLoading && !cameraError && !cameraCatalog?.cameras.length && (
                    <div className="camera-message" role="status">
                      No camera devices are available. Connect a camera, check macOS privacy permissions, then refresh.
                    </div>
                  )}
                  {cameraBusy && <div className="camera-message" role="status">Switching cameras and verifying the video feed…</div>}
                  <div className="form-section-title"><Settings2 size={17} /> Detection</div>
                  <label className="setting-row">
                    <span><strong>Eye Aspect Ratio threshold</strong><small>EAR values below this are classified as closed.</small></span>
                    <div className="range-control"><input type="range" min="0.12" max="0.35" step="0.01" value={settings.ear_threshold} onChange={(event) => setSettings({ ...settings, ear_threshold: Number(event.target.value) })} /><output>{settings.ear_threshold.toFixed(2)}</output></div>
                  </label>
                  <label className="setting-row">
                    <span><strong>Alert after eye closure</strong><small>Continuous closure duration required before warning.</small></span>
                    <div className="number-control"><input type="number" min="0.3" max="10" step="0.1" value={settings.closed_duration_seconds} onChange={(event) => setSettings({ ...settings, closed_duration_seconds: Number(event.target.value) })} /><span>sec</span></div>
                  </label>
                  {(settings.ear_threshold > 0.28 || settings.closed_duration_seconds < 0.8) && (
                    <div className="sensitivity-warning"><AlertTriangle size={16} /><span>These sensitivity settings may increase false alerts. Tune them under your normal lighting and camera position.</span></div>
                  )}
                  <div className="form-section-title audio-title"><AudioLines size={17} /> Interface & audio</div>
                  <label className="setting-row theme-row">
                    <span><strong>Appearance</strong><small>Choose a theme or follow your operating system.</small></span>
                    <select
                      className="theme-select"
                      aria-label="Appearance preference"
                      value={themePreference}
                      onChange={(event) => setThemePreference(event.target.value as "light" | "dark" | "system")}
                    >
                      <option value="light">Light</option>
                      <option value="dark">Dark</option>
                      <option value="system">System</option>
                    </select>
                  </label>
                  <label className="toggle-row">
                    <span><strong>Show eye landmarks</strong><small>Draw tracked contours over the camera feed.</small></span>
                    <input type="checkbox" checked={settings.show_landmarks} onChange={(event) => setSettings({ ...settings, show_landmarks: event.target.checked })} />
                  </label>
                  <label className="toggle-row">
                    <span><strong>Browser audio alerts</strong><small>Sound is generated locally by this browser after monitoring starts.</small></span>
                    <input type="checkbox" checked={settings.audio_enabled} onChange={(event) => setSettings({ ...settings, audio_enabled: event.target.checked })} />
                  </label>
                  <label className="setting-row volume-row">
                    <span><strong>Alert volume</strong><small>Browser audio level. System/browser mute can still suppress sound.</small></span>
                    <div className="range-control"><input type="range" min="0" max="1" step="0.05" value={settings.audio_volume} onChange={(event) => setSettings({ ...settings, audio_volume: Number(event.target.value) })} /><output>{Math.round(settings.audio_volume * 100)}%</output></div>
                  </label>
                  <div className="settings-actions">
                    <button className="button button-secondary" type="button" onClick={testAlert}><AudioLines size={16} /> Test audio</button>
                    <button className="button button-primary" type="submit" disabled={cameraBusy}><Check size={16} /> Save settings</button>
                  </div>
                  {settingsMessage && <div className={settingsMessage.includes("saved") || settingsMessage.includes("played") ? "success-message" : "inline-error"}>{settingsMessage}</div>}
                </>
              ) : <div className="loading-state"><LoaderCircle className="spin" /> Loading settings…</div>}
            </form>
            <div className="settings-footnote"><ShieldAlert size={15} /> Camera sensitivity varies with lighting, pose, and individual features. WakeUp2 is an experimental tool, not a certified safety device.</div>
          </section>
        )}

        {page === "About" && (
          <section className="page-content narrow-page">
            <div className="welcome-row"><div><h2>About WakeUp2</h2><p>Local computer vision for awareness of prolonged eye closure.</p></div></div>
            <div className="panel about-panel">
              <div className="about-hero"><div className="brand-mark"><Eye size={23} /></div><div><h2>WakeUp2</h2><span>Real-Time Drowsiness Monitoring</span></div></div>
              <p>WakeUp2 is an experimental computer-vision project that observes eye openness through a locally connected webcam. Face landmarks and eye measurements are processed on this computer; video is not uploaded or saved.</p>
              <div className="about-feature"><div className="metric-icon"><Eye size={17} /></div><div><strong>Eye Aspect Ratio (EAR)</strong><p>EAR compares the vertical distance between eye landmarks with the horizontal eye width. A lower value indicates a more closed eye; sustained closure beyond the configured duration triggers one alert for that closure event.</p></div></div>
              <div className="about-feature"><div className="metric-icon"><Activity size={17} /></div><div><strong>Technology</strong><p>Python, FastAPI, OpenCV, MediaPipe Face Mesh, React, TypeScript, and a local SQLite history database.</p></div></div>
              <div className="safety-notice"><ShieldAlert size={18} /><div><strong>Important limitations</strong><p>This software is not certified, medically validated, or suitable as a safety-critical driver-monitoring system. Lighting, camera placement, face pose, and individual differences affect accuracy. Do not rely on it to prevent accidents or replace proper rest.</p></div></div>
            </div>
          </section>
        )}

        <footer className="app-footer"><span>WakeUp2 · Local computer vision</span><span>Camera data stays on this device</span></footer>
      </main>
    </div>
  );
}

function NavButton({
  active,
  icon,
  onClick,
  children,
}: {
  active: boolean;
  icon: ReactNode;
  onClick: () => void;
  children: string;
}) {
  return <button className={`nav-item ${active ? "nav-active" : ""}`} aria-label={children} title={children} onClick={onClick}>{icon}<span>{children}</span>{active && <ChevronRight className="nav-chevron" size={15} />}</button>;
}

function eyeStatusLabel(snapshot: MonitoringSnapshot | null) {
  if (!snapshot?.monitoring) return "Inactive";
  if (snapshot.status === "DROWSINESS_DETECTED") return "Drowsy";
  if (snapshot.eye_status === "CLOSED") return "Eyes closed";
  if (snapshot.eye_status === "OPEN") return "Eyes open";
  return snapshot.status === "STARTING" ? "Starting…" : "No face";
}

function statusDescription(snapshot: MonitoringSnapshot | null) {
  if (!snapshot?.monitoring) return "Start monitoring when you are ready.";
  if (snapshot.status === "STARTING") return "Connecting to your camera…";
  if (snapshot.status === "FACE_NOT_DETECTED") return "Position your face in view of the camera.";
  if (snapshot.status === "TRACKING_LOST") return "Eye landmarks are temporarily unavailable.";
  return "No prolonged eye closure detected.";
}

export default App;
