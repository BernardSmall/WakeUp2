import platform
import subprocess
import threading
import os
import winsound  # Only exists on Windows

class SoundManager:
    def __init__(self, sound_file="Ping.wav"):
        self.sound_file = sound_file

    def play_sound(self):
        """Play the sound in a separate thread so it doesn't block the main loop."""
        threading.Thread(target=self._play, daemon=True).start()

    def _play(self):
        if not os.path.exists(self.sound_file):
            print(f"Sound file not found: {self.sound_file}")
            return

        system = platform.system()
        if system == "Darwin":  # macOS
            subprocess.call(["afplay", self.sound_file])
        elif system == "Windows":
            winsound.PlaySound(self.sound_file, winsound.SND_FILENAME)
        else:
            print("Unsupported OS for SoundManager")
