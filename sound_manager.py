import os
import platform
import subprocess
import threading

from settings import ALERT_SOUND_PATH


if platform.system() == "Windows":
    import winsound


class SoundManager:
    def __init__(self, sound_file=ALERT_SOUND_PATH):
        self.sound_file = sound_file
        self._lock = threading.Lock()
        self._playback_thread = None

    def play_sound(self):
        """Start one non-blocking playback, ignoring requests while it is active."""
        with self._lock:
            if self._playback_thread and self._playback_thread.is_alive():
                return False

            self._playback_thread = threading.Thread(target=self._play, daemon=True)
            self._playback_thread.start()
            return True

    def _play(self):
        if not os.path.isfile(self.sound_file):
            print(f"Alert sound file not found: {self.sound_file}")
            return

        system = platform.system()
        if system == "Darwin":
            command = ["afplay", self.sound_file]
            try:
                result = subprocess.run(command, check=False)
            except FileNotFoundError:
                print("Cannot play alert: macOS 'afplay' command was not found.")
                return
            if result.returncode:
                print(f"Alert playback failed with exit code {result.returncode}.")
        elif system == "Windows":
            winsound.PlaySound(self.sound_file, winsound.SND_FILENAME)
        else:
            print(f"Sound playback is unsupported on {system}.")
