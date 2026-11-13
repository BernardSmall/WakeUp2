import platform

import cv2


def capture_backends() -> tuple[int, ...]:
    system = platform.system()
    if system == "Darwin":
        return (cv2.CAP_AVFOUNDATION, cv2.CAP_ANY)
    if system == "Windows":
        return (cv2.CAP_DSHOW, cv2.CAP_MSMF)
    return (cv2.CAP_ANY,)


def open_camera(index: int):
    for backend in capture_backends():
        capture = None
        try:
            capture = cv2.VideoCapture(index, backend)
            if not capture.isOpened():
                capture.release()
                continue
            for _ in range(3):
                ok, _frame = capture.read()
                if ok:
                    return capture
            capture.release()
        except cv2.error:
            if capture is not None:
                capture.release()
    return None
