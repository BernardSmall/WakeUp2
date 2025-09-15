import cv2
import numpy as np
import threading
import time
import os
from math import hypot
import mediapipe as mp
from sound_manager import SoundManager  # Import SoundManager class

# ---------- Config (tune these if needed) ----------
EAR_THRESHOLD = 0.2        # Lower to make the detection more sensitive to closed eyes
CLOSED_FRAMES_TRIGGER = 12 # How many consecutive frames ≈ ~0.4s at 30fps
DRAW_OVERLAY = True        # Turn off if you want max performance
CAM_INDEX = 0              # Default camera
FLASH_DURATION = 1         # Duration for flashing (in seconds)
MESSAGE_DURATION = 2       # Duration for each message in seconds
# ---------------------------------------------------

mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,     # Gives iris landmarks
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# MediaPipe FaceMesh landmark indices (common pairs for EAR)
LEFT_EYE  = [33, 160, 158, 133, 153, 144]   # [p1, p2, p3, p4, p5, p6]
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
    """Alternates screen color between red and black for the flashing effect."""
    if flashing:
        frame[:] = (0, 0, 255)  # Red
    else:
        frame[:] = frame  # Return to normal frame
    return frame

def main():
    # Prompt user for sound selection
    print("Choose an alert sound:")
    print("1: Default Sound (Ping)")
    print("2: Attention-grabbing Sound (Glass)")
    print("3: Calming Sound (Submarine)")

    sound_choice = input("Enter the number for your choice (1/2/3): ")
    
    sound_dict = {
        '1': 'default',
        '2': 'alert',
        '3': 'calming'
    }
    
    sound_type = sound_dict.get(sound_choice, 'default')  # Default to 'default' if invalid input
    print(f"You selected: {sound_type} sound")

    # Prompt user for volume control
    volume = int(input("Set volume (0-100): "))
    while volume < 0 or volume > 100:
        print("Invalid volume level. Please select a value between 0 and 100.")
        volume = int(input("Set volume (0-100): "))

    # Initialize SoundManager with the user-selected volume
    sound_manager = SoundManager(volume=volume)  # Set volume to user input
    sound_manager.select_sound(sound_type)  # Set sound based on user choice

    # Try different camera indices (0, 1, 2)
    cap = None
    for idx in range(3):
        cap = cv2.VideoCapture(idx, cv2.CAP_AVFOUNDATION)
        if cap.isOpened():
            print(f"Camera opened successfully with index {idx}.")
            break
        else:
            print(f"Failed to open camera with index {idx}. Trying next.")

    if not cap.isOpened():
        print("Could not open camera. Check macOS Camera permissions for your terminal/IDE.")
        return

    # Set the camera resolution to a lower value (640x480)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    consecutive_closed = 0
    last_alert_time = 0
    flashing = False
    flash_timer = time.time()
    message_timer = 0
    show_message = False
    message_type = ""  # "WAKE UP!" or "Buzzer vibrates 💡"

    fps_smoother = []
    last_t = time.time()

    # Create the window first
    cv2.namedWindow("Anti-Sleep Eyes", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Anti-Sleep Eyes", 640, 480)  # Resize for macOS

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame.")
            break
        else:
            print(f"Frame captured successfully. Dimensions: {frame.shape}")

        # Flip for a mirror view
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        results = face_mesh.process(rgb)

        ear_left, ear_right, ear_mean = None, None, None
        eyes_closed = False

        if results.multi_face_landmarks:
            lm = results.multi_face_landmarks[0].landmark

            ear_left  = eye_aspect_ratio(lm, LEFT_EYE,  w, h)
            ear_right = eye_aspect_ratio(lm, RIGHT_EYE, w, h)
            ear_mean  = (ear_left + ear_right) / 2.0

            eyes_closed = ear_mean < EAR_THRESHOLD
            consecutive_closed = consecutive_closed + 1 if eyes_closed else 0

            # Draw overlay
            if DRAW_OVERLAY:
                for idxs in (LEFT_EYE, RIGHT_EYE):
                    for i in range(len(idxs)-1):
                        p1 = (int(lm[idxs[i]].x * w), int(lm[idxs[i]].y * h))
                        p2 = (int(lm[idxs[i+1]].x * w), int(lm[idxs[i+1]].y * h))
                        cv2.line(frame, p1, p2, (0, 255, 0), 1)
                txt = f"EAR L:{ear_left:.2f} R:{ear_right:.2f} Mean:{ear_mean:.2f}"
                cv2.putText(frame, txt, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

        # Trigger alert
        now = time.time()
        if consecutive_closed >= CLOSED_FRAMES_TRIGGER:
            sound_manager.play_sound()  # Play custom sound

            # Flash the screen for a defined duration
            if now - flash_timer > FLASH_DURATION:
                flashing = not flashing  # Toggle flashing
                flash_timer = time.time()  # Reset timer

            frame = flash_screen(frame, flashing)

            # Show the "WAKE UP!" message for 2 seconds
            if not show_message:
                message_type = "WAKE UP!"
                message_timer = time.time()
                show_message = True

        # Display messages based on timer
        if show_message:
            if message_type == "WAKE UP!" and (time.time() - message_timer) > MESSAGE_DURATION:
                message_type = "Buzzer vibrates 💡"
                message_timer = time.time()

            # Display the message
            if message_type == "WAKE UP!":
                cv2.putText(frame, "WAKE UP!", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 3)
            elif message_type == "Buzzer vibrates 💡":
                cv2.putText(frame, "Buzzer vibrates 💡", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,255), 3)

            # Stop showing message after it's displayed for 2 seconds
            if (time.time() - message_timer) > MESSAGE_DURATION * 2:
                show_message = False

        # FPS (rough)
        t = time.time()
        fps_smoother.append(1.0 / max(1e-6, (t - last_t)))
        if len(fps_smoother) > 30:
            fps_smoother.pop(0)
        last_t = t
        if DRAW_OVERLAY:
            fps_txt = f"FPS: {np.mean(fps_smoother):.1f}"
            cv2.putText(frame, fps_txt, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 2)

        # Display the frame
        cv2.imshow("Anti-Sleep Eyes", frame)
        cv2.waitKey(1)  # Necessary to refresh the window

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
