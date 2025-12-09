#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

# Répertoire racine du projet (E-commerce_ESME_TP)
ROOT = Path(__file__).resolve().parents[2]
TERRAFORM_DIR = ROOT / "terraform"

def get_terraform_outputs():
  try:
    result = subprocess.check_output(
      ["terraform", "output", "-json"],
      cwd=TERRAFORM_DIR
    )
  except subprocess.CalledProcessError as e:
    print(f"Erreur lors de 'terraform output -json' : {e}", file=sys.stderr)
    sys.exit(1)

  return json.loads(result)

def main():
  outputs = get_terraform_outputs()

  vm_ips = outputs["vm_ips"]["value"]
  ports = outputs["docker_ports"]["value"]

  # ⚠️ A ADAPTER : user / clé SSH pour se connecter à la VM
  ansible_user = "debian"
  ansible_ssh_key = "vm_TP3 ansible_host=192.168.10.10 ansible_user=debian ansible_ssh_private_key_file=~/.ssh/id_rsa" 

  lines = ["[ecom_vms]"]
  for idx, ip in enumerate(vm_ips, start=1):
    hostname = f"ecom-vm-{idx:02d}"
    line = (
      f"{hostname} "
      f"ansible_host={ip} "
      f"ansible_user={ansible_user} "
      f"ansible_ssh_private_key_file={ansible_ssh_key} "
      f"front_port={ports['front']} "
      f"gateway_port={ports['gateway']} "
      f"auth_port={ports['auth']} "
      f"orders_port={ports['orders']}"
    )
    lines.append(line)

  inventory = "\n".join(lines) + "\n"
  sys.stdout.write(inventory)

if __name__ == "__main__":
  main()
