import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_INDEX = ROOT / "frontend" / "dist" / "index.html"


@unittest.skipUnless(FRONTEND_INDEX.is_file(), "Build the frontend before testing static serving.")
class StaticApplicationTests(unittest.TestCase):
    def test_frontend_and_api_are_served_and_server_shuts_down(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        base_url = f"http://127.0.0.1:{port}"
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    self.fail(f"Uvicorn exited with status {process.returncode}.")
                try:
                    with urlopen(f"{base_url}/api/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except (OSError, URLError):
                    time.sleep(0.1)
            else:
                self.fail("FastAPI did not become ready.")

            with urlopen(f"{base_url}/", timeout=2) as response:
                self.assertIn(b"WakeUp2", response.read())
            with urlopen(f"{base_url}/settings", timeout=2) as response:
                self.assertIn(b"WakeUp2", response.read())
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

        self.assertIsNotNone(process.returncode)
