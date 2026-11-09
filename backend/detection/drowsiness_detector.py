from datetime import datetime, timezone
from typing import Optional


class DrowsinessDetector:
    """Track a continuous closure and emit one alert when its time threshold is met."""

    def __init__(self):
        self.closed_since: Optional[float] = None
        self.consecutive_closed_frames = 0
        self.alert_triggered = False

    def reset(self):
        self.closed_since = None
        self.consecutive_closed_frames = 0
        self.alert_triggered = False

    def update(self, ear_mean, threshold, duration_trigger, now):
        if ear_mean is None or ear_mean >= threshold:
            self.reset()
            return {
                "eye_status": "TRACKING LOST" if ear_mean is None else "OPEN",
                "closure_duration_seconds": 0.0,
                "consecutive_closed_frames": 0,
                "alert_triggered": False,
                "alert_at": None,
            }

        if self.closed_since is None:
            self.closed_since = now
            self.consecutive_closed_frames = 1
        else:
            self.consecutive_closed_frames += 1

        closure_duration = max(0.0, now - self.closed_since)
        alert = closure_duration >= duration_trigger and not self.alert_triggered
        if alert:
            self.alert_triggered = True

        return {
            "eye_status": "CLOSED",
            "closure_duration_seconds": closure_duration,
            "consecutive_closed_frames": self.consecutive_closed_frames,
            "alert_triggered": alert,
            "alert_at": datetime.now(timezone.utc) if alert else None,
        }
