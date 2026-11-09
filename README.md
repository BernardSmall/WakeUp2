# WakeUp2

WakeUp2 is a locally hosted eye-closure monitoring dashboard. A Python backend owns the webcam, runs MediaPipe Face Mesh, calculates the original six-point Eye Aspect Ratio (EAR), and streams processed frames and real detection measurements to a React dashboard. Video is not uploaded or saved.

> **Safety:** WakeUp2 is an experimental computer-vision project, not a certified or medically validated safety device. It is not suitable for safety-critical driver monitoring and must not replace proper rest.

## Features

- Live webcam preview with eye contours and locally drawn EAR overlay
- Real-time eye status, left/right/mean EAR, closure duration, and session alert count
- Time-based closure threshold and one alert per continuous closure event
- Browser-generated audio alert with enable, volume, and test controls
- macOS camera discovery with device names and stable AVFoundation identifiers
- Camera switching while monitoring, with resource cleanup and rollback on failure
- EAR trend chart based on measured values
- Local monitoring history with session configuration and alert timestamps
- Validated, persisted settings for threshold, closure duration, camera device, landmarks, and audio
- Responsive dashboard with Dashboard, Monitoring History, Settings, and About views
- Local SQLite session persistence; no raw webcam recordings

## Architecture

```text
React + TypeScript + Vite
  ├─ HTTP API for controls, settings, and history
  ├─ WebSocket for live monitoring metrics (5 updates/second)
  └─ HTTP MJPEG stream for a single processed camera feed
                  │
FastAPI on 127.0.0.1:8000
  └─ One camera/MediaPipe worker thread
       ├─ AVFoundation device discovery and OpenCV camera capture
       ├─ MediaPipe Face Mesh and original eye landmark mapping
       ├─ EAR and closure state machine
       └─ SQLite session history
```

The browser generates audio only after a user action starts monitoring or tests the sound. Browser/OS audio restrictions can still suppress playback. The backend does not play audio, avoiding duplicate alarms.

## Technology

- Python 3.10, FastAPI, Uvicorn, OpenCV, MediaPipe Face Mesh, NumPy
- React 18, TypeScript, Vite, Tailwind CSS, Lucide React, Recharts
- SQLite for local session summaries and alert timestamps

MediaPipe 0.10.21 is pinned because it supports the existing `mp.solutions.face_mesh` API; MediaPipe 1.2.x does not. OpenCV is installed through only `opencv-contrib-python` to avoid conflicting distributions. The pinned NumPy and OpenCV builds support Apple Silicon with Python 3.10.

On macOS, PyObjC's AVFoundation binding supplies camera names and stable device identifiers without opening cameras during refresh. OpenCV still captures the selected device by its current AVFoundation enumeration index; that index is refreshed from the stable identifier on startup and is not treated as a persistent identity.

## Prerequisites

- macOS on Apple Silicon or Intel
- Python 3.10
- Node.js and npm
- Webcam permission for Terminal or VS Code

## Installation

From the repository root:

```bash
python3.10 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If reusing an environment containing both OpenCV Python distributions, remove them before installing:

```bash
python -m pip uninstall -y opencv-python opencv-contrib-python
python -m pip install -r requirements.txt
```

Install the frontend dependencies:

```bash
cd frontend
npm install
cd ..
```

## Run locally

Use two terminals from the repository root.

**Terminal 1 — backend**

```bash
source venv/bin/activate
python -m pip install -r requirements.txt
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — frontend**

```bash
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The backend binds to loopback only; Vite proxies API and WebSocket requests locally.

On first camera use, grant access in **System Settings → Privacy & Security → Camera** to the terminal or app running the backend. `python camera_check.py` can help diagnose camera access.

## Detection and settings

The dashboard Settings page changes these persisted local settings:

| Setting | Default | Description |
| --- | ---: | --- |
| EAR threshold | `0.20` | Mean EAR below the threshold is considered closed. |
| Eye-closure alert duration | `1.5 s` | Continuous closed-eye duration before a drowsiness alert. |
| Camera device | First available camera, unless a saved device is available | Choose by the macOS device name in Settings. Selection is saved locally and can be changed while monitoring; WakeUp2 verifies the replacement before confirming it. |
| Landmark overlay | On | Draw eye contours on the streamed frame. |
| Browser audio alerts | On | Play a browser-generated tone after the user starts monitoring. |
| Alert volume | `50%` | Relative Web Audio gain level. |

Closure timing uses a monotonic clock, so the alert threshold is time-based rather than tied to camera frame rate. Missing face/landmark measurements do not count as closure and reset the continuous event. A new alert can occur after the eyes reopen and a new closure reaches the threshold.

To try the detector, start monitoring in a well-lit room, center your face, observe the live EAR and eye state, then close your eyes briefly and reopen them. The live chart and status reflect actual backend detections. Face pose, camera placement, lighting, and individual features affect accuracy.

## Testing

Backend unit and mocked camera lifecycle tests:

```bash
source venv/bin/activate
python -m unittest discover -s tests -v
```

Frontend type-check and production build:

```bash
cd frontend
npm run build
```

Run dependency consistency checks with `python -m pip check` and `cd frontend && npm audit`.

## Local data and privacy

Session summaries, alert timestamps, and settings are stored under the ignored `data-local/` directory. The application does not persist webcam frames. Monitoring History can clear local session records after confirmation. The backend API is intended for loopback use only.

## Troubleshooting

- **`mp.solutions` or Face Mesh is missing:** activate `venv`, then reinstall `requirements.txt`; the app requires MediaPipe 0.10.21.
- **OpenCV import errors or conflicts:** uninstall both OpenCV variants and reinstall the pinned manifest so only `opencv-contrib-python` is installed.
- **Camera unavailable or permission denied:** allow camera access to Terminal/VS Code, close other camera apps, and select an available device in Settings.
- **Camera list is empty:** confirm that macOS recognizes the camera and grant Camera access to the terminal or app running the backend. Install `requirements.txt` again to ensure the AVFoundation binding is present, then refresh the device list.
- **A saved camera is disconnected:** WakeUp2 selects an available camera on startup and displays a notice in Settings. Reconnect the preferred device and refresh to select it again.
- **Dashboard says backend reconnecting:** ensure Uvicorn is running at `127.0.0.1:8000`.
- **No face or tracking lost:** improve lighting, face the camera, and avoid obscuring the eye area.
- **No audio:** click Start Monitoring or Test Audio to satisfy browser audio activation; check browser and macOS output/mute settings. Audible alerts cannot be guaranteed if the browser or OS suppresses sound.
- **No history records:** a session is persisted when monitoring stops or the camera worker exits; start and stop a session to create a record.

## Project layout

- `backend/` — FastAPI API, camera worker, detection, settings, and local history
- `frontend/` — React dashboard, chart, API/WebSocket client, and styles
- `tests/` — existing CLI regression tests and backend logic/lifecycle tests
- `anti_sleep_eyes.py` — retained standalone webcam prototype
- `camera_check.py` — webcam diagnostic
- `requirements.txt` — exact Python runtime dependency versions

## Screenshots

Screenshots to be added after a successful camera run on the target Mac.
