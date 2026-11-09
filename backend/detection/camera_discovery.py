import platform
from dataclasses import dataclass


@dataclass(frozen=True)
class CameraDevice:
    camera_id: str
    name: str
    index: int


def discover_cameras() -> tuple[list[CameraDevice], str | None]:
    if platform.system() != "Darwin":
        return [], "Camera discovery is currently supported on macOS only."

    try:
        import AVFoundation
    except ImportError:
        return [], (
            "macOS camera discovery is unavailable. Install the project requirements "
            "and restart WakeUp2."
        )

    devices = AVFoundation.AVCaptureDevice.devicesWithMediaType_(
        AVFoundation.AVMediaTypeVideo
    )
    cameras = [
        CameraDevice(
            camera_id=str(device.uniqueID()),
            name=str(device.localizedName()),
            index=index,
        )
        for index, device in enumerate(devices)
        if device.isConnected()
    ]
    return cameras, None
