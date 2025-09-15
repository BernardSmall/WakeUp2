import os  # Add this import at the top of the file
import subprocess

class SoundManager:
    def __init__(self, volume=50):
        self.volume = volume  # Default volume set to 50%
        self.sounds = {
            'default': '/System/Library/Sounds/Ping.aiff',
            'alert': '/System/Library/Sounds/Glass.aiff',  # Loud, attention-grabbing sound
            'calming': '/System/Library/Sounds/Submarine.aiff'  # Calming sound
        }
        self.current_sound = self.sounds['default']  # Default sound

    def set_volume(self, volume):
        """Sets the volume level (0-100)"""
        if 0 <= volume <= 100:
            self.volume = volume
            os.system(f"osascript -e 'set volume output volume {self.volume}'")  # Set system volume
        else:
            print("Invalid volume level. Please select a value between 0 and 100.")

    def select_sound(self, sound_type):
        """Select a sound based on the type (default, alert, calming)"""
        if sound_type in self.sounds:
            self.current_sound = self.sounds[sound_type]
            print(f"Selected sound: {self.current_sound}")
        else:
            print(f"Invalid sound type. Available options: {', '.join(self.sounds.keys())}")

    def play_sound(self):
        """Play the selected sound"""
        print(f"Playing sound: {self.current_sound}")  # For debugging
        subprocess.Popen(['afplay', self.current_sound])

    def test_sound(self):
        """Test the currently selected sound"""
        self.play_sound()
        print(f"Playing {self.current_sound} sound with volume {self.volume}%")
