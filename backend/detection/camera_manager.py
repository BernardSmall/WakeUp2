import threading
import time
from datetime import datetime, timezone
from typing import Optional

import cv2

from backend.config import DetectionSettings
from backend.detection.drowsiness_detector import DrowsinessDetector
from backend.detection.camera_discovery import CameraDevice, discover_cameras
from backend.detection.camera_platform import open_camera
from backend.detection.eye_tracker import (
    LEFT_EYE,
    RIGHT_EYE,
    calculate_eye_ears,
    eye_status_from_ear,
)
from backend.services.session_service import SessionService
from backend.services.settings_service import SettingsService


class CameraManager:
    def __init__(self, settings_service=None, session_service=None):
        self.settings_service = settings_service or SettingsService()
        self.session_service = session_service or SessionService()
        self._lock = threading.RLock()
        self._lifecycle_lock = threading.RLock()
        self._selection_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._frame: Optional[bytes] = None
        self._session_id = None
        self._started_at = None
        self._camera_ready_event = threading.Event()
        self._startup_error: Optional[str] = None
        self._camera_notice: Optional[str] = None
        self._devices: list[CameraDevice] = []
        self._discovery_error: Optional[str] = None
        self._state = self._empty_state()
        self._refresh_devices()
        self._restore_camera_selection()

    @staticmethod
    def _empty_state():
        return {
            "monitoring": False,
            "status": "INACTIVE",
            "eye_status": "INACTIVE",
            "face_detected": False,
            "ear_left": None,
            "ear_right": None,
            "ear_mean": None,
            "closure_duration_seconds": 0.0,
            "consecutive_closed_frames": 0,
            "alert_count": 0,
            "latest_alert_id": 0,
            "latest_alert_at": None,
            "camera_error": None,
            "session_id": None,
            "updated_at": datetime.now(timezone.utc),
        }

    def start(self):
        with self._lifecycle_lock:
            return self._start()

    def _start(self):
        with self._lock:
            if self._state["monitoring"]:
                return self.snapshot()
            previous_thread = self._thread
        if previous_thread and previous_thread.is_alive():
            previous_thread.join(timeout=4.0)
            if previous_thread.is_alive():
                raise RuntimeError("The previous camera capture is still shutting down.")

        with self._lock:
            if self._state["monitoring"]:
                return self.snapshot()

            settings = self.settings_service.get()
            session_id, started_at = self.session_service.start(settings)
            self._session_id = session_id
            self._started_at = started_at
            self._frame = None
            self._stop_event.clear()
            self._camera_ready_event.clear()
            self._startup_error = None
            self._state = {
                **self._empty_state(),
                "monitoring": True,
                "status": "STARTING",
                "eye_status": "NO FACE",
                "session_id": session_id,
                "updated_at": datetime.now(timezone.utc),
            }
            self._thread = threading.Thread(
                target=self._capture_loop,
                name="wake-up-camera",
                daemon=True,
            )
            self._thread.start()
            return self.snapshot()

    def stop(self):
        with self._lifecycle_lock:
            return self._stop()

    def _stop(self):
        with self._lock:
            if self._state["monitoring"]:
                self._stop_event.set()
            thread = self._thread

        if thread:
            thread.join(timeout=4.0)
        if thread and thread.is_alive():
            with self._lock:
                if self._state["monitoring"]:
                    self._state["status"] = "STOPPING"
                    self._state["updated_at"] = datetime.now(timezone.utc)
            return self.snapshot()
        return self.snapshot()

    def snapshot(self):
        with self._lock:
            state = dict(self._state)
            state["camera_notice"] = self._camera_notice
            state["settings"] = self.settings_service.get()
            return state

    def latest_frame(self):
        with self._lock:
            return self._frame

    def update_settings(self, settings: DetectionSettings):
        with self._lifecycle_lock:
            with self._lock:
                current = self.settings_service.get()
                if self._state["monitoring"] and (
                    settings.camera_index != current.camera_index
                    or settings.camera_id != current.camera_id
                ):
                    raise ValueError("Use the camera selector to switch cameras.")
                return self.settings_service.update(settings)

    def cameras(self):
        devices, discovery_error = self._refresh_devices()
        with self._lifecycle_lock:
            settings = self.settings_service.get()
            monitoring = self.snapshot()["monitoring"]
            matching_device = next(
                (device for device in devices if device.camera_id == settings.camera_id),
                None,
            )
            if not monitoring and matching_device:
                if matching_device.index != settings.camera_index:
                    settings = self.settings_service.update(
                        settings.model_copy(
                            update={"camera_index": matching_device.index}
                        )
                    )
            elif settings.camera_id and not matching_device and not discovery_error:
                with self._lock:
                    self._camera_notice = (
                        "The selected camera is unavailable. Connect it again or "
                        "choose another available camera."
                    )
            with self._lock:
                notice = self._camera_notice
        return {
            "cameras": [
                {
                    "camera_id": device.camera_id,
                    "name": device.name,
                    "index": device.index,
                }
                for device in devices
            ],
            "selected_camera_id": settings.camera_id,
            "notice": notice,
            "error": discovery_error,
        }

    def select_camera(self, camera_id: str):
        with self._selection_lock:
            with self._lifecycle_lock:
                return self._select_camera(camera_id)

    def _select_camera(self, camera_id: str):
        devices, discovery_error = self._refresh_devices()
        if discovery_error:
            raise ValueError(discovery_error)
        device = next((item for item in devices if item.camera_id == camera_id), None)
        if device is None:
            raise ValueError("That camera is no longer available. Refresh the device list.")

        previous_settings = self.settings_service.get()
        was_monitoring = self.snapshot()["monitoring"]
        if previous_settings.camera_id == device.camera_id:
            if not was_monitoring:
                self._probe_camera(device)
            with self._lock:
                self._camera_notice = None
            return self.cameras()

        self.stop()
        with self._lock:
            thread = self._thread
        if thread and thread.is_alive():
            raise RuntimeError("The current camera is still shutting down; try again shortly.")

        selected_settings = previous_settings.model_copy(
            update={"camera_id": device.camera_id, "camera_index": device.index}
        )
        if not was_monitoring:
            self._probe_camera(device)
            self.settings_service.update(selected_settings)
            with self._lock:
                self._camera_notice = None
            return self.cameras()

        self.settings_service.update(selected_settings)
        self.start()
        if self._wait_for_camera_ready():
            with self._lock:
                self._camera_notice = None
            return self.cameras()

        with self._lock:
            startup_error = self._startup_error or "The selected camera did not become ready."
        self.stop()
        with self._lock:
            thread = self._thread
        if thread and thread.is_alive():
            raise RuntimeError(
                f"{startup_error} The previous camera could not be restored while capture was shutting down."
            )

        self.settings_service.update(previous_settings)
        self.start()
        if self._wait_for_camera_ready():
            raise ValueError(
                f"{startup_error} The previous camera has been restored."
            )

        with self._lock:
            restore_error = self._startup_error or "The previous camera did not become ready."
        raise ValueError(
            f"{startup_error} WakeUp2 could not restore the previous camera: {restore_error}"
        )

    def _refresh_devices(self):
        devices, discovery_error = discover_cameras()
        with self._lock:
            self._devices = devices
            self._discovery_error = discovery_error
        return devices, discovery_error

    def _restore_camera_selection(self):
        settings = self.settings_service.get()
        if not self._devices:
            if settings.camera_id and not self._discovery_error:
                self._camera_notice = (
                    "The previously selected camera is unavailable, and no cameras "
                    "are currently connected."
                )
            return

        selected = next(
            (device for device in self._devices if device.camera_id == settings.camera_id),
            None,
        )
        if selected is None and settings.camera_id is None:
            selected = next(
                (device for device in self._devices if device.index == settings.camera_index),
                None,
            )
        if selected is None:
            selected = self._devices[0]
            with self._lock:
                if settings.camera_id:
                    self._camera_notice = (
                        f"The previously selected camera is unavailable. "
                        f"Using {selected.name} instead."
                    )

        if (
            selected.camera_id != settings.camera_id
            or selected.index != settings.camera_index
        ):
            self.settings_service.update(
                settings.model_copy(
                    update={"camera_id": selected.camera_id, "camera_index": selected.index}
                )
            )

    def _probe_camera(self, device: CameraDevice):
        capture = open_camera(device.index)
        if capture is None:
            raise ValueError(
                f"Cannot open {device.name}. Check camera permissions and try again."
            )
        try:
            for _ in range(10):
                ok, _frame = capture.read()
                if ok:
                    return
                time.sleep(0.05)
            raise ValueError(
                f"{device.name} opened but did not provide a video frame. "
                "Check camera permissions and whether another app is using it."
            )
        finally:
            capture.release()

    def _wait_for_camera_ready(self, timeout: float = 8.0):
        if not self._camera_ready_event.wait(timeout):
            return False
        with self._lock:
            return self._state["monitoring"] and self._startup_error is None

    def _set_error(self, message):
        with self._lock:
            self._state.update(
                monitoring=False,
                status="CAMERA_ERROR",
                eye_status="NO FACE",
                camera_error=message,
                closure_duration_seconds=0.0,
                consecutive_closed_frames=0,
                updated_at=datetime.now(timezone.utc),
            )
            self._frame = None
            self._startup_error = message
            self._camera_ready_event.set()

    def _finish(self):
        with self._lock:
            session_id = self._session_id
            if self._state["status"] != "CAMERA_ERROR":
                self._state.update(
                    monitoring=False,
                    status="INACTIVE",
                    eye_status="INACTIVE",
                    face_detected=False,
                    ear_left=None,
                    ear_right=None,
                    ear_mean=None,
                    closure_duration_seconds=0.0,
                    consecutive_closed_frames=0,
                    camera_error=None,
                    updated_at=datetime.now(timezone.utc),
                )
            self._frame = None
            self._thread = None
            self._session_id = None
        self.session_service.stop(session_id)

    def _capture_loop(self):
        capture = None
        try:
            settings = self.settings_service.get()
            capture = open_camera(settings.camera_index)
            if capture is None:
                self._set_error(
                    "Cannot open the selected camera. Check macOS camera permissions "
                    "and whether the device is still connected."
                )
                return

            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            import mediapipe as mp

            detector = DrowsinessDetector()
            failed_reads = 0
            with mp.solutions.face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            ) as face_mesh:
                while not self._stop_event.is_set():
                    cycle_started = time.monotonic()
                    ok, frame = capture.read()
                    if not ok:
                        failed_reads += 1
                        if failed_reads >= 10:
                            self._set_error(
                                "Camera stopped delivering frames. Check whether it was disconnected."
                            )
                            return
                        time.sleep(0.05)
                        continue
                    failed_reads = 0
                    self._camera_ready_event.set()
                    frame = cv2.flip(frame, 1)
                    height, width = frame.shape[:2]
                    result = face_mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    face_detected = bool(result.multi_face_landmarks)
                    ear_left = ear_right = ear_mean = None
                    if face_detected:
                        landmarks = result.multi_face_landmarks[0].landmark
                        ear_left, ear_right = calculate_eye_ears(landmarks, width, height)
                        if ear_left is not None and ear_right is not None:
                            ear_mean = (ear_left + ear_right) / 2.0
                        if self.settings_service.get().show_landmarks:
                            self._draw_eye_landmarks(frame, landmarks, width, height)

                    current_settings = self.settings_service.get()
                    detection = detector.update(
                        ear_mean,
                        current_settings.ear_threshold,
                        current_settings.closed_duration_seconds,
                        time.monotonic(),
                    )
                    alert_at = detection["alert_at"]
                    with self._lock:
                        session_id = self._session_id
                    if alert_at and session_id is not None:
                        recorded_at = self.session_service.record_alert(session_id)
                        with self._lock:
                            self._state["alert_count"] += 1
                            self._state["latest_alert_id"] += 1
                            self._state["latest_alert_at"] = recorded_at

                    state_name = (
                        "DROWSINESS_DETECTED"
                        if detector.alert_triggered
                        else "EYES_CLOSED"
                        if detection["eye_status"] == "CLOSED"
                        else "NORMAL"
                        if detection["eye_status"] == "OPEN"
                        else "FACE_NOT_DETECTED"
                        if not face_detected
                        else "TRACKING_LOST"
                    )
                    self._draw_status(frame, detection["eye_status"], ear_mean, detector.alert_triggered)
                    encoded, jpeg = cv2.imencode(
                        ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                    )
                    with self._lock:
                        if encoded:
                            self._frame = jpeg.tobytes()
                        self._state.update(
                            monitoring=True,
                            status=state_name,
                            eye_status=detection["eye_status"]
                            if face_detected
                            else "NO FACE",
                            face_detected=face_detected,
                            ear_left=ear_left,
                            ear_right=ear_right,
                            ear_mean=ear_mean,
                            closure_duration_seconds=detection[
                                "closure_duration_seconds"
                            ],
                            consecutive_closed_frames=detection[
                                "consecutive_closed_frames"
                            ],
                            camera_error=None,
                            updated_at=datetime.now(timezone.utc),
                        )
                    time.sleep(max(0.0, 1 / 15 - (time.monotonic() - cycle_started)))
        except Exception as error:
            self._set_error(f"Camera processing failed: {error}")
        finally:
            if capture is not None:
                capture.release()
            self._finish()

    @staticmethod
    def _draw_eye_landmarks(frame, landmarks, width, height):
        for indices in (LEFT_EYE, RIGHT_EYE):
            points = [
                (int(landmarks[index].x * width), int(landmarks[index].y * height))
                for index in indices
            ]
            for start, end in zip(points, points[1:] + points[:1]):
                cv2.line(frame, start, end, (45, 212, 191), 1)

    @staticmethod
    def _draw_status(frame, eye_status, ear, alert):
        text = "WAKE UP!" if alert else eye_status
        color = (40, 70, 235) if alert else (45, 212, 191)
        cv2.putText(
            frame,
            f"EAR: {ear:.3f}" if ear is not None else "EAR: --",
            (18, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (245, 248, 250),
            2,
        )
        cv2.putText(
            frame,
            text,
            (18, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
        )
