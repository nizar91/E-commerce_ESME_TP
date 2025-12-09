"""
Utility script to install every service dependency list in one go.

Usage:
    python setup_all_services.py
Optionally add --no-root to skip the root requirements file.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_pip(req_file: Path) -> None:
    """Install dependencies from the given requirements file."""
    print(f"\n>>> Installing from {req_file}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req_file)])


def main() -> None:
    parser = argparse.ArgumentParser(description="Install dependencies for every microservice.")
    parser.add_argument(
        "--no-root",
        action="store_true",
        help="Skip installing the root requirements.txt file.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    requirements = []

    if not args.no_root:
        requirements.append(project_root / "requirements.txt")

    for service in ("auth", "orders", "gateway", "front"):
        requirements.append(project_root / service / "requirements.txt")

    missing = [req for req in requirements if not req.exists()]
    if missing:
        msg = "Missing requirement files:\n" + "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(msg)

    for req in requirements:
        run_pip(req)

    print("\nAll dependencies installed successfully.")


if __name__ == "__main__":
    main()
