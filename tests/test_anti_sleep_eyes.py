import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from anti_sleep_eyes import EyeClosureTracker, eye_aspect_ratio
from sound_manager import SoundManager


class EyeAspectRatioTests(unittest.TestCase):
    def test_calculates_eye_aspect_ratio(self):
        points = ((0, 0), (1, 1), (3, 1), (4, 0), (3, -1), (1, -1))
        landmarks = [SimpleNamespace(x=x / 10, y=y / 10) for x, y in points]

        self.assertAlmostEqual(
            eye_aspect_ratio(landmarks, list(range(6)), 10, 10),
            0.5,
        )

    def test_zero_width_eye_is_invalid(self):
        landmarks = [SimpleNamespace(x=0.25, y=0.5) for _ in range(6)]

        self.assertIsNone(eye_aspect_ratio(landmarks, list(range(6)), 100, 100))


class EyeClosureTrackerTests(unittest.TestCase):
    def setUp(self):
        self.tracker = EyeClosureTracker(threshold=0.2, closed_frames_trigger=3)

    def test_alert_triggers_once_per_closed_eye_episode(self):
        self.assertEqual(self.tracker.update(0.1), ("CLOSED", False))
        self.assertEqual(self.tracker.update(0.1), ("CLOSED", False))
        self.assertEqual(self.tracker.update(0.1), ("CLOSED", True))
        self.assertEqual(self.tracker.update(0.1), ("CLOSED", False))
        self.assertEqual(self.tracker.update(0.3), ("OPEN", False))

        self.assertEqual(self.tracker.update(0.1), ("CLOSED", False))
        self.assertEqual(self.tracker.update(0.1), ("CLOSED", False))
        self.assertEqual(self.tracker.update(0.1), ("CLOSED", True))

    def test_tracking_loss_resets_consecutive_frame_count(self):
        self.tracker.update(0.1)
        self.assertEqual(self.tracker.update(None), ("TRACKING LOST", False))
        self.assertEqual(self.tracker.consecutive_closed, 0)
        self.assertFalse(self.tracker.alert_triggered)


class SoundManagerTests(unittest.TestCase):
    def test_missing_sound_file_is_reported_without_raising(self):
        manager = SoundManager("missing-alert-sound.aiff")
        with patch("builtins.print") as print_mock:
            self.assertTrue(manager.play_sound())
            manager._playback_thread.join(timeout=2)

        print_mock.assert_called_once_with(
            "Alert sound file not found: missing-alert-sound.aiff"
        )

    def test_play_requests_share_one_active_thread(self):
        manager = SoundManager("unused")
        started = threading.Event()
        release = threading.Event()

        def wait_for_release():
            started.set()
            release.wait(timeout=2)

        with patch.object(manager, "_play", side_effect=wait_for_release):
            try:
                self.assertTrue(manager.play_sound())
                self.assertTrue(started.wait(timeout=1))
                active_thread = manager._playback_thread

                for _ in range(20):
                    self.assertFalse(manager.play_sound())
                self.assertIs(manager._playback_thread, active_thread)
            finally:
                release.set()
                if manager._playback_thread:
                    manager._playback_thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
