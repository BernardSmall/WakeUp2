import argparse
import platform
import re
import struct
import subprocess
import sys


def supported_python(version_info=sys.version_info) -> bool:
    major, minor = version_info[:2]
    return major == 3 and 10 <= minor <= 12 and struct.calcsize("P") == 8


def supported_node(version: str) -> bool:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.\d+(?:[-+].*)?", version.strip())
    if not match:
        return False
    major, minor = map(int, match.groups())
    return major in (22, 24) and (major != 22 or minor >= 12)


def supported_host(system: str, machine: str) -> bool:
    normalized_machine = machine.lower()
    if system == "Darwin":
        return normalized_machine in ("arm64", "aarch64", "x86_64", "amd64")
    if system == "Windows":
        return normalized_machine in ("amd64", "x86_64")
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("check", choices=("python", "node", "host"))
    parser.add_argument("--version")
    args = parser.parse_args()

    if args.check == "host":
        if supported_host(platform.system(), platform.machine()):
            print(f"Supported platform: {platform.system()} {platform.machine()}")
            return 0
        print(
            f"Unsupported platform: {platform.system()} {platform.machine()}. "
            "WakeUp2 supports Windows x64 and macOS Intel/Apple Silicon."
        )
        return 1

    if args.check == "python":
        if supported_python():
            print(f"Supported Python: {sys.version.split()[0]}")
            return 0
        print(
            f"Unsupported Python: {sys.version.split()[0]} ({struct.calcsize('P') * 8}-bit). "
            "Install 64-bit Python 3.10, 3.11, or 3.12."
        )
        return 1

    version = args.version
    if version is None:
        try:
            version = subprocess.check_output(
                ["node", "--version"], text=True, stderr=subprocess.STDOUT
            ).strip()
        except (OSError, subprocess.CalledProcessError) as error:
            print(f"Node.js could not be run: {error}")
            return 1
    if supported_node(version):
        print(f"Supported Node.js: {version}")
        return 0
    print(
        f"Unsupported Node.js: {version}. Install Node.js 22.12+ or 24.x."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
