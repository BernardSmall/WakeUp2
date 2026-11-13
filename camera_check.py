import sys

import cv2

from backend.detection.camera_discovery import discover_cameras
from backend.detection.camera_platform import open_camera


def main():
    cameras, error = discover_cameras()
    if error:
        print(error)
        return 1
    if not cameras:
        print("No camera devices were found.")
        return 1

    for camera in cameras:
        print(f"{camera.index}: {camera.name}")
    selected_index = 0
    if len(cameras) > 1:
        answer = input("Camera number to test (Enter for the first): ").strip()
        if answer:
            try:
                selected_index = int(answer)
            except ValueError:
                print("Enter one of the listed camera numbers.")
                return 1
    camera = next((device for device in cameras if device.index == selected_index), None)
    if camera is None:
        print(f"No camera has index {selected_index}.")
        return 1

    capture = open_camera(camera.index)
    if capture is None:
        print(f"Could not open {camera.name}. Check camera permissions and close other apps using it.")
        return 1

    print(f"Camera opened: {camera.name}. Press q to quit.")
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                print("Camera stopped delivering frames.")
                break
            cv2.imshow("Camera Test (press q)", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        capture.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
