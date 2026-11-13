import platform
from dataclasses import dataclass


@dataclass(frozen=True)
class CameraDevice:
    camera_id: str
    name: str
    index: int


def discover_cameras() -> tuple[list[CameraDevice], str | None]:
    system = platform.system()
    if system == "Darwin":
        return _discover_macos_cameras()
    if system == "Windows":
        return _discover_windows_cameras()
    return [], "Camera discovery is supported on macOS and Windows only."


def _discover_macos_cameras() -> tuple[list[CameraDevice], str | None]:
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


def _discover_windows_cameras() -> tuple[list[CameraDevice], str | None]:
    try:
        import comtypes
        from pygrabber.dshow_graph import FilterGraph
    except ImportError:
        return [], (
            "Windows camera discovery is unavailable. Install the project requirements "
            "and restart WakeUp2."
        )

    initialized_com = False
    try:
        comtypes.CoInitialize()
        initialized_com = True
        names = FilterGraph().get_input_devices()
        occurrences: dict[str, int] = {}
        cameras = []
        for index, name in enumerate(names):
            name = str(name).strip()
            occurrences[name] = occurrences.get(name, 0) + 1
            suffix = f"#{occurrences[name]}" if names.count(name) > 1 else ""
            cameras.append(
                CameraDevice(
                    camera_id=f"directshow:{name}{suffix}",
                    name=name,
                    index=index,
                )
            )
        return cameras, None
    except Exception as error:
        return [], f"Windows could not enumerate camera devices: {error}"
    finally:
        if initialized_com:
            comtypes.CoUninitialize()
