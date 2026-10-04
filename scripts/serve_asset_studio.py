#!/usr/bin/env python3
"""Start, stop, or inspect the loopback-only static C64 Asset Studio."""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parents[1]
RUNTIME = ROOT / "build" / "asset-studio"
PID_FILE = RUNTIME / "server.pid"
LOG_FILE = RUNTIME / "server.log"


class StudioHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        super().end_headers()


def pid_is_studio(pid: int) -> bool:
    try:
        command = Path(f"/proc/{pid}/cmdline").read_text(errors="ignore")
    except FileNotFoundError:
        return False
    return str(Path(__file__).resolve()) in command and "--serve" in command


def live_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
    except (OSError, ValueError):
        PID_FILE.unlink(missing_ok=True)
        return None
    if not pid_is_studio(pid):
        PID_FILE.unlink(missing_ok=True)
        return None
    return pid


def serve(port: int) -> int:
    handler = lambda *args, **kwargs: StudioHandler(*args, directory=str(ROOT), **kwargs)
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        print(f"http://127.0.0.1:{port}/", flush=True)
        server.serve_forever()
    return 0


def wait_for_http(port: int, process: subprocess.Popen[bytes]) -> None:
    url = f"http://127.0.0.1:{port}/"
    for _ in range(30):
        if process.poll() is not None:
            raise RuntimeError(f"server exited; see {LOG_FILE}")
        try:
            with urllib.request.urlopen(url, timeout=0.2) as response:
                if response.status == 200 and response.headers.get("Cache-Control") == "no-store, max-age=0":
                    return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"server did not become ready; see {LOG_FILE}")


def start(port: int) -> int:
    if pid := live_pid():
        print(f"running: pid {pid} http://127.0.0.1:{port}/")
        return 0
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("ab") as log:
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--serve", "--port", str(port)],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    PID_FILE.write_text(f"{process.pid}\n")
    try:
        wait_for_http(port, process)
    except Exception:
        process.terminate()
        PID_FILE.unlink(missing_ok=True)
        raise
    print(f"started: pid {process.pid} http://127.0.0.1:{port}/")
    return 0


def stop() -> int:
    pid = live_pid()
    if pid is None:
        print("stopped")
        return 0
    os.kill(pid, signal.SIGTERM)
    for _ in range(30):
        try:
            os.kill(pid, 0)
        except OSError:
            PID_FILE.unlink(missing_ok=True)
            print("stopped")
            return 0
        time.sleep(0.1)
    raise RuntimeError(f"pid {pid} did not stop")


def status(port: int) -> int:
    if pid := live_pid():
        print(f"running: pid {pid} http://127.0.0.1:{port}/")
        return 0
    print("stopped")
    return 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--serve":
        parser = argparse.ArgumentParser()
        parser.add_argument("--serve", action="store_true")
        parser.add_argument("--port", type=int, default=8042)
        return serve(parser.parse_args(argv).port)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "stop", "status"))
    parser.add_argument("--port", type=int, default=8042)
    args = parser.parse_args(argv)
    if args.command == "start":
        return start(args.port)
    if args.command == "stop":
        return stop()
    return status(args.port)


if __name__ == "__main__":
    raise SystemExit(main())
