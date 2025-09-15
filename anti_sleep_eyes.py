import cv2
import numpy as np
import time
from math import hypot
import mediapipe as mp
from sound_manager import SoundManager  # Use the simple version with default Ping.wav

# ---------- Config ----------
EAR_THRESHOLD = 0.2
CLOSED_FRAMES_TRIGGER = 12
DRAW_OVERLAY = True
CAM_INDEX = 0
FLASH_DURATION = 1
MESSAGE_DURATION = 2
# ---------------------------

mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

LEFT_EYE  = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]

def euclidean(p1, p2):
    return hypot(p1[0]-p2[0], p1[1]-p2[1])

def eye_aspect_ratio(landmarks, eye_indices, w, h):
    pts = [(int(landmarks[i].x * w), int(landmarks[i].y * h)) for i in eye_indices]
    p1, p2, p3, p4, p5, p6 = pts
    horiz = euclidean(p1, p4)
    vert1 = euclidean(p2, p6)
    vert2 = euclidean(p3, p5)
    if horiz == 0:
        return 0.0
    return (vert1 + vert2) / (2.0 * horiz)

def flash_screen(frame, flashing):
    if flashing:
        frame[:] = (0, 0, 255)
    return frame

def main():
    # Initialize SoundManager with default Ping.wav
    sound_manager = SoundManager("Ping.wav")

    # Open camera
    cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_ANY)
    if not cap.isOpened():
        print("Cannot open camera")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    consecutive_closed = 0
    flashing = False
    flash_timer = time.time()
    show_message = False
    message_timer = 0
    message_type = ""

    cv2.namedWindow("Anti-Sleep Eyes", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Anti-Sleep Eyes", 640, 480)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)

        eyes_closed = False

        if results.multi_face_landmarks:
            lm = results.multi_face_landmarks[0].landmark
            ear_left  = eye_aspect_ratio(lm, LEFT_EYE,  w, h)
            ear_right = eye_aspect_ratio(lm, RIGHT_EYE, w, h)
            ear_mean  = (ear_left + ear_right) / 2.0
            eyes_closed = ear_mean < EAR_THRESHOLD
            consecutive_closed = consecutive_closed + 1 if eyes_closed else 0

            if DRAW_OVERLAY:
                for idxs in (LEFT_EYE, RIGHT_EYE):
                    for i in range(len(idxs)-1):
                        p1 = (int(lm[idxs[i]].x * w), int(lm[idxs[i]].y * h))
                        p2 = (int(lm[idxs[i+1]].x * w), int(lm[idxs[i+1]].y * h))
                        cv2.line(frame, p1, p2, (0, 255, 0), 1)
                txt = f"EAR L:{ear_left:.2f} R:{ear_right:.2f} Mean:{ear_mean:.2f}"
                cv2.putText(frame, txt, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

        # Alert trigger
        now = time.time()
        if consecutive_closed >= CLOSED_FRAMES_TRIGGER:
            sound_manager.play_sound()

            if now - flash_timer > FLASH_DURATION:
                flashing = not flashing
                flash_timer = now

            frame = flash_screen(frame, flashing)

            if not show_message:
                message_type = "WAKE UP!"
                message_timer = now
                show_message = True

        if show_message:
            if message_type == "WAKE UP!" and (time.time() - message_timer) > MESSAGE_DURATION:
                message_type = "Buzzer vibrates 💡"
                message_timer = now

            if message_type == "WAKE UP!":
                cv2.putText(frame, "WAKE UP!", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 3)
            elif message_type == "Buzzer vibrates 💡":
                cv2.putText(frame, "Buzzer vibrates 💡", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,255), 3)

            if (time.time() - message_timer) > MESSAGE_DURATION * 2:
                show_message = False

        cv2.imshow("Anti-Sleep Eyes", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
