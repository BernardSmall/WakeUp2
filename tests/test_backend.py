import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from pydantic import ValidationError

from backend.config import DetectionSettings
from backend.detection.camera_manager import CameraManager
from backend.detection.drowsiness_detector import DrowsinessDetector
from backend.detection.eye_tracker import calculate_eye_ears, eye_aspect_ratio
from backend.services.session_service import SessionService


class EyeTrackerTests(unittest.TestCase):
    def test_eye_aspect_ratio_and_short_landmark_list(self):
        coordinates = [
            (0, 0), (1, 1), (3, 1), (4, 0), (3, -1), (1, -1),
            (5, 0), (6, 1), (8, 1), (9, 0), (8, -1), (6, -1),
        ]
        points = [SimpleNamespace(x=x / 10, y=y / 10) for x, y in coordinates]
        self.assertAlmostEqual(eye_aspect_ratio(points, list(range(6)), 10, 10), 0.5)
        self.assertEqual(calculate_eye_ears(points[:10], 10, 10), (None, None))


class DrowsinessDetectorTests(unittest.TestCase):
    def test_time_threshold_dedupes_alert_until_reopen(self):
        detector = DrowsinessDetector()
        self.assertFalse(detector.update(0.1, 0.2, 1.0, 10.0)["alert_triggered"])
        self.assertFalse(detector.update(0.1, 0.2, 1.0, 10.8)["alert_triggered"])
        self.assertTrue(detector.update(0.1, 0.2, 1.0, 11.01)["alert_triggered"])
        self.assertFalse(detector.update(0.1, 0.2, 1.0, 12.0)["alert_triggered"])
        self.assertEqual(detector.update(0.3, 0.2, 1.0, 12.1)["eye_status"], "OPEN")
        self.assertFalse(detector.update(0.1, 0.2, 1.0, 13.0)["alert_triggered"])
        self.assertTrue(detector.update(0.1, 0.2, 1.0, 14.01)["alert_triggered"])

    def test_missing_ear_resets_closure_without_alert(self):
        detector = DrowsinessDetector()
        detector.update(0.1, 0.2, 1.0, 1.0)
        result = detector.update(None, 0.2, 1.0, 1.5)
        self.assertEqual(result["eye_status"], "TRACKING LOST")
        self.assertEqual(result["closure_duration_seconds"], 0.0)
        self.assertFalse(result["alert_triggered"])


class SettingsAndHistoryTests(unittest.TestCase):
    def test_settings_validate_ranges(self):
        with self.assertRaises(ValidationError):
            DetectionSettings(ear_threshold=0.8)
        with self.assertRaises(ValidationError):
            DetectionSettings(closed_duration_seconds=0.1)

    def test_session_and_alerts_are_persisted(self):
        with tempfile.TemporaryDirectory() as temporary:
            service = SessionService(Path(temporary) / "sessions.sqlite3")
            session_id, _ = service.start(DetectionSettings())
            service.record_alert(session_id)
            service.stop(session_id)

            session = service.get_session(session_id)
            self.assertEqual(session["alert_count"], 1)
            self.assertEqual(len(session["alert_timestamps"]), 1)
            self.assertIsNotNone(session["ended_at"])
            self.assertGreaterEqual(session["duration_seconds"], 0)


class CameraLifecycleTests(unittest.TestCase):
    def test_camera_is_released_when_monitoring_stops(self):
        settings = DetectionSettings()
        capture = _FakeCapture()
        settings_service = _FakeSettingsService(settings)
        session_service = _FakeSessionService()
        manager = CameraManager(settings_service, session_service)

        with patch("backend.detection.camera_manager.cv2.VideoCapture", return_value=capture):
            with patch(
                "mediapipe.solutions.face_mesh.FaceMesh",
                return_value=_FakeFaceMesh(),
            ):
                manager.start()
                deadline = time.monotonic() + 3
                while manager.snapshot()["status"] == "STARTING" and time.monotonic() < deadline:
                    time.sleep(0.02)
                state = manager.stop()

        self.assertEqual(state["status"], "INACTIVE")
        self.assertTrue(capture.released)
        self.assertEqual(session_service.stopped, [1])


class _FakeSettingsService:
    def __init__(self, settings):
        self.settings = settings

    def get(self):
        return self.settings.model_copy()

    def update(self, settings):
        self.settings = settings.model_copy()
        return self.get()


class _FakeSessionService:
    def __init__(self):
        self.stopped = []
        self.alerts = 0

    def start(self, _settings):
        return 1, None

    def record_alert(self, _session_id):
        self.alerts += 1
        return None

    def stop(self, session_id):
        if session_id is not None:
            self.stopped.append(session_id)


class _FakeCapture:
    def __init__(self):
        self.released = False

    def isOpened(self):
        return True

    def set(self, *_args):
        return True

    def read(self):
        return True, np.zeros((64, 64, 3), dtype=np.uint8)

    def release(self):
        self.released = True


class _FakeFaceMesh:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def process(self, _frame):
        return SimpleNamespace(multi_face_landmarks=None)


if __name__ == "__main__":
    unittest.main()
