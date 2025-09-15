# 💤 WakeUp2 – Computer Vision Anti-Sleep System

A Python application that uses **OpenCV** and **MediaPipe** to monitor eye activity in real time and detect drowsiness.  
If closed eyes are detected for too long, the system plays an alarm sound and flashes a warning on screen — helping prevent accidents due to microsleep or fatigue.  

---

## ✨ Features
- 👀 **Eye Tracking** – Uses MediaPipe Face Mesh to calculate Eye Aspect Ratio (EAR).  
- 🚨 **Sleep Alert** – Plays a loud sound and flashes the screen if eyes remain closed for several frames.  
- 🖥 **Real-Time Detection** – Runs from your webcam in real time.  
- ⚙️ **Configurable Thresholds** – Adjust EAR sensitivity and frame duration to tune drowsiness detection.  
- 🎵 **Sound Manager** – Modular system to play alerts (easily swap with custom sounds).  

---

## 📂 Project Structure
WakeUp2/
│
├── anti_sleep_eyes.py # Main detection script
├── camera_check.py # Helper to verify webcam
├── sound_manager.py # Plays alarm sounds
├── settings.py # Config (thresholds, timings)
├── requirements.txt # Dependencies
└── README.md # Project documentation


> Note: `venv/` and `__pycache__/` are intentionally ignored — they will be recreated on your system.

---

## 🚀 Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/<your-username>/WakeUp2.git
cd WakeUp2

2. Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
venv\Scripts\activate     # On Windows

3. Install dependencies
pip install -r requirements.txt

4. Run the program
python anti_sleep_eyes.py

⚙️ Configuration

You can tweak detection behavior in settings.py:

EAR_THRESHOLD → Lower = more sensitive

CLOSED_FRAMES_TRIGGER → Number of consecutive closed frames before alarm

FLASH_DURATION → Flash timing for on-screen warning

🛠 Requirements

Python 3.9+

OpenCV

MediaPipe

NumPy

Install with:

pip install opencv-python mediapipe numpy

📌 Notes

Do not commit your venv/ or __pycache__/ folders — they are ignored automatically.

For large datasets or models, place them in data-local/ (not tracked by Git).

📜 License

This project is licensed under the MIT License — free to use and modify.
