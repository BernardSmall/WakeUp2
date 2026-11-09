import json
import threading

from backend.config import DATA_DIR, SETTINGS_PATH, DetectionSettings


class SettingsService:
    def __init__(self):
        self._lock = threading.Lock()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if SETTINGS_PATH.is_file():
            try:
                self._settings = DetectionSettings.model_validate_json(
                    SETTINGS_PATH.read_text(encoding="utf-8")
                )
            except (OSError, ValueError):
                print(f"Invalid local settings file at {SETTINGS_PATH}; using defaults.")
                self._settings = DetectionSettings()
                self._save()
        else:
            self._settings = DetectionSettings()
            self._save()

    def get(self):
        with self._lock:
            return self._settings.model_copy()

    def update(self, settings: DetectionSettings):
        with self._lock:
            self._settings = settings.model_copy()
            self._save()
            return self._settings.model_copy()

    def _save(self):
        SETTINGS_PATH.write_text(
            json.dumps(self._settings.model_dump(), indent=2),
            encoding="utf-8",
        )
