#!/usr/bin/env python3
"""Dynamic inventory that exposes the local Docker host plus RDS outputs."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TERRAFORM_DIR = ROOT / "terraform"


def get_terraform_outputs() -> dict:
    try:
        result = subprocess.check_output(
            ["terraform", "output", "-json"],
            cwd=TERRAFORM_DIR,
        )
    except subprocess.CalledProcessError as exc:
        print(f"Erreur lors de 'terraform output -json' : {exc}", file=sys.stderr)
        sys.exit(1)

    return json.loads(result)


def main() -> None:
    outputs = get_terraform_outputs()

    rds_endpoint = outputs["rds_endpoint"]["value"]
    rds_port = outputs["rds_port"]["value"]
    rds_db_name = outputs["rds_db_name"]["value"]
    rds_username = outputs["rds_username"]["value"]
    rds_password = outputs["rds_password"]["value"]

    ports = {
        "front": 5000,
        "gateway": 5003,
        "auth": 5002,
        "orders": 5001,
    }

    project_dir = ROOT.as_posix()
    line = (
        "localhost "
        "ansible_connection=local "
        f"compose_project_dir='{project_dir}' "
        f"front_port={ports['front']} "
        f"gateway_port={ports['gateway']} "
        f"auth_port={ports['auth']} "
        f"orders_port={ports['orders']} "
        f"rds_endpoint={rds_endpoint} "
        f"rds_port={rds_port} "
        f"rds_db_name={rds_db_name} "
        f"rds_username={rds_username} "
        f"rds_password={rds_password}"
    )

    inventory = "[local_docker]\n" + line + "\n"
    sys.stdout.write(inventory)


if __name__ == "__main__":
    main()
