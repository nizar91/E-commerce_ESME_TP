"""
Launch all microservices in the required order.

Usage:
    python start_all_services.py

Press Ctrl+C to stop every service.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class Service:
    name: str
    folder: str
    command: List[str]


SERVICES: List[Service] = [
    Service("Auth Service", "auth", [sys.executable, "auth_service.py"]),
    Service("Orders Service", "orders", [sys.executable, "orders_service.py"]),
    Service("Gateway", "gateway", [sys.executable, "gateway.py"]),
    Service("Front", "front", [sys.executable, "run.py"]),
]


def start_services() -> None:
    root = Path(__file__).resolve().parent
    processes: List[subprocess.Popen] = []

    def stop_all() -> None:
        print("\nStopping services...")
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
        # Give processes time to exit cleanly before forcing.
        time.sleep(1)
        for proc in processes:
            if proc.poll() is None:
                proc.kill()

    def handle_interrupt(signum, frame):  # type: ignore[override]
        stop_all()
        sys.exit(0)

    # Register signal handlers for Ctrl+C and Ctrl+Break (Windows).
    signal.signal(signal.SIGINT, handle_interrupt)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, handle_interrupt)  # type: ignore[attr-defined]

    creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if os.name == "nt" else 0

    try:
        for service in SERVICES:
            service_dir = root / service.folder
            print(f"\n>>> Starting {service.name} in {service_dir}")
            command = service.command
            if os.name == "nt":
                # Keep the spawned console open even if the script exits early.
                command = ["cmd", "/k", *service.command]
            proc = subprocess.Popen(
                command,
                cwd=service_dir,
                creationflags=creationflags,
            )
            processes.append(proc)
            # Give the service a moment to initialize before launching the next.
            time.sleep(1)

        print("\nAll services started. Press Ctrl+C to stop.")
        # Wait for the first process to exit; if it stops, end all.
        processes[0].wait()
    finally:
        stop_all()


if __name__ == "__main__":
    start_services()
