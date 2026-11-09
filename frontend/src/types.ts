export type DetectionSettings = {
  ear_threshold: number;
  closed_duration_seconds: number;
  camera_index: number;
  camera_id: string | null;
  show_landmarks: boolean;
  audio_enabled: boolean;
  audio_volume: number;
};

export type CameraDevice = {
  camera_id: string;
  name: string;
  index: number;
};

export type CameraCatalog = {
  cameras: CameraDevice[];
  selected_camera_id: string | null;
  notice: string | null;
  error: string | null;
};

export type MonitoringSnapshot = {
  monitoring: boolean;
  status: string;
  eye_status: string;
  face_detected: boolean;
  ear_left: number | null;
  ear_right: number | null;
  ear_mean: number | null;
  closure_duration_seconds: number;
  consecutive_closed_frames: number;
  alert_count: number;
  latest_alert_id: number;
  latest_alert_at: string | null;
  camera_error: string | null;
  camera_notice: string | null;
  session_id: number | null;
  settings: DetectionSettings;
  updated_at: string;
};

export type SessionRecord = {
  id: number;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number;
  alert_count: number;
  alert_timestamps: string[];
  settings: DetectionSettings;
};

export type PageName = "Dashboard" | "Monitoring History" | "Settings" | "About";
