import sys
import time
from math import hypot

import cv2
import mediapipe as mp

from settings import (
    ALERT_SOUND_PATH,
    CAM_INDEX,
    CLOSED_FRAMES_TRIGGER,
    DRAW_OVERLAY,
    EAR_THRESHOLD,
    FLASH_DURATION,
    MESSAGE_DURATION,
)
from sound_manager import SoundManager


LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]


def euclidean(p1, p2):
    return hypot(p1[0] - p2[0], p1[1] - p2[1])


def eye_aspect_ratio(landmarks, eye_indices, w, h):
    pts = [(int(landmarks[i].x * w), int(landmarks[i].y * h)) for i in eye_indices]
    p1, p2, p3, p4, p5, p6 = pts
    horiz = euclidean(p1, p4)
    if horiz == 0:
        return None

    vert1 = euclidean(p2, p6)
    vert2 = euclidean(p3, p5)
    return (vert1 + vert2) / (2.0 * horiz)


class EyeClosureTracker:
    def __init__(self, threshold=EAR_THRESHOLD, closed_frames_trigger=CLOSED_FRAMES_TRIGGER):
        self.threshold = threshold
        self.closed_frames_trigger = closed_frames_trigger
        self.consecutive_closed = 0
        self.alert_triggered = False

    def reset(self):
        self.consecutive_closed = 0
        self.alert_triggered = False

    def update(self, ear):
        if ear is None:
            self.reset()
            return "TRACKING LOST", False

        if ear >= self.threshold:
            self.reset()
            return "OPEN", False

        self.consecutive_closed += 1
        triggered = (
            self.consecutive_closed >= self.closed_frames_trigger
            and not self.alert_triggered
        )
        if triggered:
            self.alert_triggered = True
        return "CLOSED", triggered


def draw_eye_landmarks(frame, landmarks, width, height):
    for indices in (LEFT_EYE, RIGHT_EYE):
        points = [
            (int(landmarks[index].x * width), int(landmarks[index].y * height))
            for index in indices
        ]
        for start, end in zip(points, points[1:] + points[:1]):
            cv2.line(frame, start, end, (0, 255, 0), 1)


def flash_screen(frame):
    overlay = frame.copy()
    overlay[:] = (0, 0, 255)
    return cv2.addWeighted(frame, 0.7, overlay, 0.3, 0)


def main():
    sound_manager = SoundManager(ALERT_SOUND_PATH)
    tracker = EyeClosureTracker()
    backend = cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_ANY
    cap = cv2.VideoCapture(CAM_INDEX, backend)

    if not cap.isOpened():
        print(
            f"Cannot open camera {CAM_INDEX}. Check camera permissions and "
            "whether another application is using it."
        )
        cap.release()
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    flashing = False
    next_flash = 0.0
    warning_until = 0.0
    consecutive_camera_failures = 0
    tracking_error_reported = False

    try:
        cv2.namedWindow("Anti-Sleep Eyes", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Anti-Sleep Eyes", 640, 480)

        with mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        ) as face_mesh:
            while True:
                ret, frame = cap.read()
                if not ret:
                    consecutive_camera_failures += 1
                    if consecutive_camera_failures >= 10:
                        print("Camera frames could not be read after 10 attempts; stopping.")
                        break
                    time.sleep(0.1)
                    continue
                consecutive_camera_failures = 0

                frame = cv2.flip(frame, 1)
                height, width = frame.shape[:2]
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(rgb)
                ear_mean = None
                eye_status = "NO FACE"
                triggered = False

                if results.multi_face_landmarks:
                    landmarks = results.multi_face_landmarks[0].landmark
                    if len(landmarks) > max(LEFT_EYE + RIGHT_EYE):
                        try:
                            ear_left = eye_aspect_ratio(landmarks, LEFT_EYE, width, height)
                            ear_right = eye_aspect_ratio(landmarks, RIGHT_EYE, width, height)
                        except (
                            AttributeError,
                            IndexError,
                            OverflowError,
                            TypeError,
                            ValueError,
                        ) as error:
                            if not tracking_error_reported:
                                print(f"Eye landmark tracking failed; skipping frame: {error}")
                            tracking_error_reported = True
                        else:
                            tracking_error_reported = False
                            if ear_left is not None and ear_right is not None:
                                ear_mean = (ear_left + ear_right) / 2.0
                            if DRAW_OVERLAY:
                                draw_eye_landmarks(frame, landmarks, width, height)
                else:
                    tracker.reset()

                if results.multi_face_landmarks:
                    eye_status, triggered = tracker.update(ear_mean)
                now = time.monotonic()
                if triggered:
                    sound_manager.play_sound()
                    warning_until = now + MESSAGE_DURATION

                alert_active = tracker.alert_triggered
                if alert_active:
                    if now >= next_flash:
                        flashing = not flashing
                        next_flash = now + max(FLASH_DURATION, 0.1)
                    if flashing:
                        frame = flash_screen(frame)
                else:
                    flashing = False

                ear_text = f"{ear_mean:.2f}" if ear_mean is not None else "--"
                cv2.putText(
                    frame,
                    f"EAR: {ear_text}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                )
                cv2.putText(
                    frame,
                    f"Eyes: {eye_status}",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0) if eye_status == "OPEN" else (0, 0, 255),
                    2,
                )
                if alert_active or now < warning_until:
                    cv2.putText(
                        frame,
                        "DROWSINESS DETECTED - WAKE UP!",
                        (10, 100),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 0, 255),
                        2,
                    )

                cv2.imshow("Anti-Sleep Eyes", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
