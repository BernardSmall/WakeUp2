import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from backend.config import DetectionSettings
from backend.detection.camera_discovery import CameraDevice, discover_cameras
from backend.detection.camera_platform import capture_backends
from backend.detection.camera_manager import CameraManager


CAMERAS = [
    CameraDevice("device-built-in", "Built-in Camera", 0),
    CameraDevice("device-external", "External Camera", 2),
]


class CameraDiscoveryTests(unittest.TestCase):
    def test_discovers_avfoundation_names_and_stable_ids(self):
        devices = [
            _AVDevice("stable-built-in", "Built-in Camera"),
            _AVDevice("stable-external", "External Camera"),
        ]
        foundation = SimpleNamespace(
            AVCaptureDevice=SimpleNamespace(
                devicesWithMediaType_=lambda _media_type: devices
            ),
            AVMediaTypeVideo="video",
        )
        with patch("backend.detection.camera_discovery.platform.system", return_value="Darwin"):
            with patch.dict("sys.modules", {"AVFoundation": foundation}):
                cameras, error = discover_cameras()

        self.assertIsNone(error)
        self.assertEqual(
            cameras,
            [
                CameraDevice("stable-built-in", "Built-in Camera", 0),
                CameraDevice("stable-external", "External Camera", 1),
            ],
        )

    def test_reports_missing_avfoundation_bindings(self):
        with patch("backend.detection.camera_discovery.platform.system", return_value="Darwin"):
            with patch.dict("sys.modules", {"AVFoundation": None}):
                cameras, error = discover_cameras()

        self.assertEqual(cameras, [])
        self.assertIn("Install the project requirements", error)

    def test_non_macos_discovery_is_explicitly_unsupported(self):
        with patch("backend.detection.camera_discovery.platform.system", return_value="Linux"):
            cameras, error = discover_cameras()

        self.assertEqual(cameras, [])
        self.assertIn("macOS and Windows", error)

    def test_discovers_windows_camera_names_without_opening_cameras(self):
        from unittest.mock import Mock

        graph = SimpleNamespace(
            get_input_devices=lambda: ["USB Camera", "USB Camera", "Laptop Camera"]
        )
        comtypes = SimpleNamespace(CoInitialize=Mock(), CoUninitialize=Mock())
        pygrabber_graph = SimpleNamespace(FilterGraph=lambda: graph)
        with patch("backend.detection.camera_discovery.platform.system", return_value="Windows"):
            with patch.dict(
                "sys.modules",
                {
                    "comtypes": comtypes,
                    "pygrabber": SimpleNamespace(),
                    "pygrabber.dshow_graph": pygrabber_graph,
                },
            ):
                cameras, error = discover_cameras()

        self.assertIsNone(error)
        self.assertEqual(
            [camera.name for camera in cameras],
            ["USB Camera", "USB Camera", "Laptop Camera"],
        )
        self.assertEqual(
            [camera.camera_id for camera in cameras],
            ["directshow:USB Camera#1", "directshow:USB Camera#2", "directshow:Laptop Camera"],
        )
        comtypes.CoInitialize.assert_called_once()
        comtypes.CoUninitialize.assert_called_once()


class CameraPlatformTests(unittest.TestCase):
    def test_windows_prefers_directshow_then_media_foundation(self):
        with patch("backend.detection.camera_platform.platform.system", return_value="Windows"):
            self.assertEqual(capture_backends(), (cv2.CAP_DSHOW, cv2.CAP_MSMF))

    def test_macos_prefers_avfoundation(self):
        with patch("backend.detection.camera_platform.platform.system", return_value="Darwin"):
            self.assertEqual(
                capture_backends(),
                (cv2.CAP_AVFOUNDATION, cv2.CAP_ANY),
            )

    def test_falls_back_when_preferred_backend_cannot_open_device(self):
        from backend.detection.camera_platform import open_camera

        failed = _FakeCapture(opened=False)
        working = _FakeCapture()
        with patch("backend.detection.camera_platform.platform.system", return_value="Windows"):
            with patch(
                "backend.detection.camera_platform.cv2.VideoCapture",
                side_effect=[failed, working],
            ):
                self.assertIs(open_camera(0), working)
        self.assertTrue(failed.released)


class CameraSelectionTests(unittest.TestCase):
    def _manager(self, settings=None):
        settings_service = _FakeSettingsService(settings or DetectionSettings())
        session_service = _FakeSessionService()
        with patch("backend.detection.camera_manager.discover_cameras", return_value=([], None)):
            manager = CameraManager(settings_service, session_service)
        return manager, settings_service, session_service

    def test_camera_catalog_reports_empty_list(self):
        manager, _settings_service, _session_service = self._manager()
        with patch("backend.detection.camera_manager.discover_cameras", return_value=([], None)):
            catalog = manager.cameras()

        self.assertEqual(catalog["cameras"], [])
        self.assertIsNone(catalog["selected_camera_id"])

    def test_selects_available_camera_only_after_probe_succeeds(self):
        settings = DetectionSettings(camera_id=CAMERAS[0].camera_id)
        manager, settings_service, _session_service = self._manager(settings)
        capture = _FakeCapture()

        with patch("backend.detection.camera_manager.discover_cameras", return_value=(CAMERAS, None)):
            with patch("backend.detection.camera_manager.cv2.VideoCapture", return_value=capture):
                selected = manager.select_camera(CAMERAS[1].camera_id)

        self.assertEqual(settings_service.get().camera_id, CAMERAS[1].camera_id)
        self.assertEqual(settings_service.get().camera_index, CAMERAS[1].index)
        self.assertEqual(selected["selected_camera_id"], CAMERAS[1].camera_id)
        self.assertTrue(capture.released)

    def test_rejects_unavailable_camera_without_opening_it(self):
        manager, settings_service, _session_service = self._manager()
        with patch("backend.detection.camera_manager.discover_cameras", return_value=(CAMERAS, None)):
            with patch("backend.detection.camera_manager.cv2.VideoCapture") as open_camera:
                with self.assertRaisesRegex(ValueError, "no longer available"):
                    manager.select_camera("missing-device")

        open_camera.assert_not_called()
        self.assertIsNone(settings_service.get().camera_id)

    def test_switches_active_camera_after_releasing_previous_capture(self):
        settings = DetectionSettings(camera_id=CAMERAS[0].camera_id)
        manager, settings_service, _session_service = self._manager(settings)
        tracker = _CaptureTracker()
        with patch("backend.detection.camera_manager.discover_cameras", return_value=(CAMERAS, None)):
            with patch(
                "backend.detection.camera_manager.cv2.VideoCapture",
                side_effect=tracker.open,
            ):
                with patch(
                    "mediapipe.solutions.face_mesh.FaceMesh",
                    return_value=_FakeFaceMesh(),
                ):
                    manager.start()
                    self.assertTrue(manager._camera_ready_event.wait(timeout=2))
                    result = manager.select_camera(CAMERAS[1].camera_id)
                    self.assertTrue(manager.snapshot()["monitoring"])
                    self.assertEqual(settings_service.get().camera_id, CAMERAS[1].camera_id)
                    self.assertEqual([capture.index for capture in tracker.captures], [0, 2])
                    self.assertTrue(tracker.captures[0].released)
                    self.assertLessEqual(tracker.max_open, 1)
                    manager.stop()

        self.assertTrue(tracker.captures[1].released)
        self.assertFalse(result["error"])

    def test_failed_camera_connection_preserves_previous_selection(self):
        settings = DetectionSettings(camera_id=CAMERAS[0].camera_id)
        manager, settings_service, _session_service = self._manager(settings)
        failed_capture = _FakeCapture(opened=False)
        with patch("backend.detection.camera_manager.discover_cameras", return_value=(CAMERAS, None)):
            with patch("backend.detection.camera_manager.cv2.VideoCapture", return_value=failed_capture):
                with self.assertRaisesRegex(ValueError, "Cannot open External Camera"):
                    manager.select_camera(CAMERAS[1].camera_id)

        self.assertTrue(failed_capture.released)
        self.assertEqual(settings_service.get().camera_id, CAMERAS[0].camera_id)

    def test_failed_active_switch_restores_previous_camera_and_monitoring(self):
        settings = DetectionSettings(camera_id=CAMERAS[0].camera_id)
        manager, settings_service, _session_service = self._manager(settings)
        tracker = _CaptureTracker(fail_indices={CAMERAS[1].index})
        with patch("backend.detection.camera_manager.discover_cameras", return_value=(CAMERAS, None)):
            with patch(
                "backend.detection.camera_manager.cv2.VideoCapture",
                side_effect=tracker.open,
            ):
                with patch(
                    "mediapipe.solutions.face_mesh.FaceMesh",
                    return_value=_FakeFaceMesh(),
                ):
                    manager.start()
                    self.assertTrue(manager._camera_ready_event.wait(timeout=2))
                    with self.assertRaisesRegex(ValueError, "previous camera has been restored"):
                        manager.select_camera(CAMERAS[1].camera_id)
                    self.assertTrue(manager.snapshot()["monitoring"])
                    self.assertEqual(settings_service.get().camera_id, CAMERAS[0].camera_id)
                    self.assertEqual(
                        [capture.index for capture in tracker.captures],
                        [0, 2, 2, 0],
                    )
                    self.assertTrue(tracker.captures[0].released)
                    self.assertTrue(tracker.captures[1].released)
                    self.assertTrue(tracker.captures[2].released)
                    self.assertLessEqual(tracker.max_open, 1)
                    manager.stop()

        self.assertTrue(tracker.captures[3].released)

    def test_restores_saved_stable_id_and_updates_ephemeral_index(self):
        saved = DetectionSettings(camera_index=0, camera_id=CAMERAS[1].camera_id)
        manager, settings_service, _session_service = self._manager(saved)
        reordered = [
            CameraDevice(CAMERAS[1].camera_id, CAMERAS[1].name, 1),
            CameraDevice(CAMERAS[0].camera_id, CAMERAS[0].name, 0),
        ]
        with patch("backend.detection.camera_manager.discover_cameras", return_value=(reordered, None)):
            manager._refresh_devices()
            manager._restore_camera_selection()

        self.assertEqual(settings_service.get().camera_id, CAMERAS[1].camera_id)
        self.assertEqual(settings_service.get().camera_index, 1)

    def test_disconnected_saved_camera_falls_back_with_notice(self):
        saved = DetectionSettings(camera_index=1, camera_id="disconnected-device")
        settings_service = _FakeSettingsService(saved)
        with patch(
            "backend.detection.camera_manager.discover_cameras",
            return_value=([CAMERAS[0]], None),
        ):
            manager = CameraManager(settings_service, _FakeSessionService())
            catalog = manager.cameras()

        self.assertEqual(settings_service.get().camera_id, CAMERAS[0].camera_id)
        self.assertIn("previously selected camera is unavailable", catalog["notice"])

    def test_disconnected_saved_camera_is_reported_when_no_fallback_exists(self):
        saved = DetectionSettings(camera_index=1, camera_id="disconnected-device")
        settings_service = _FakeSettingsService(saved)
        with patch("backend.detection.camera_manager.discover_cameras", return_value=([], None)):
            manager = CameraManager(settings_service, _FakeSessionService())

        self.assertIn("no cameras are currently connected", manager.snapshot()["camera_notice"])
        self.assertEqual(settings_service.get().camera_id, "disconnected-device")

    def test_empty_camera_list_rejects_selection(self):
        manager, _settings_service, _session_service = self._manager()
        with patch("backend.detection.camera_manager.discover_cameras", return_value=([], None)):
            with self.assertRaisesRegex(ValueError, "no longer available"):
                manager.select_camera("camera-id")
            catalog = manager.cameras()

        self.assertEqual(catalog["cameras"], [])


class _AVDevice:
    def __init__(self, camera_id, name):
        self._camera_id = camera_id
        self._name = name

    def uniqueID(self):
        return self._camera_id

    def localizedName(self):
        return self._name

    def isConnected(self):
        return True


class _FakeSettingsService:
    def __init__(self, settings):
        self.settings = settings.model_copy()

    def get(self):
        return self.settings.model_copy()

    def update(self, settings):
        self.settings = settings.model_copy()
        return self.get()


class _FakeSessionService:
    def __init__(self):
        self.stopped = []
        self._next_session = 0

    def start(self, _settings):
        self._next_session += 1
        return self._next_session, None

    def record_alert(self, _session_id):
        return None

    def stop(self, session_id):
        if session_id is not None:
            self.stopped.append(session_id)


class _FakeCapture:
    def __init__(self, index=0, tracker=None, opened=True):
        self.index = index
        self.tracker = tracker
        self.opened = opened
        self.released = False

    def isOpened(self):
        return self.opened

    def set(self, *_args):
        return True

    def read(self):
        if not self.opened or self.released:
            return False, None
        return True, np.zeros((32, 32, 3), dtype=np.uint8)

    def release(self):
        if not self.released:
            self.released = True
            if self.tracker and self.opened:
                self.tracker.closed()


class _CaptureTracker:
    def __init__(self, fail_indices=None):
        self.fail_indices = fail_indices or set()
        self.captures = []
        self.open_count = 0
        self.max_open = 0
        self.lock = threading.Lock()

    def open(self, index, _backend):
        with self.lock:
            opened = index not in self.fail_indices
            capture = _FakeCapture(index, self, opened=opened)
            self.captures.append(capture)
            if opened:
                self.open_count += 1
                self.max_open = max(self.max_open, self.open_count)
            return capture

    def closed(self):
        with self.lock:
            self.open_count -= 1


class _FakeFaceMesh:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def process(self, _frame):
        return SimpleNamespace(multi_face_landmarks=None)


if __name__ == "__main__":
    unittest.main()
