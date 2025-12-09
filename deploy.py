#!/usr/bin/env python3
import subprocess
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent
TERRAFORM_DIR = ROOT / "terraform"
ANSIBLE_DIR = ROOT / "ansible_ecommerce"

def run(cmd, cwd=None):
    print(f"\n>>> {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=cwd)

def terraform_apply():
    run(["terraform", "init"], cwd=TERRAFORM_DIR)
    run(["terraform", "apply", "-auto-approve"], cwd=TERRAFORM_DIR)

def terraform_destroy():
    run(["terraform", "destroy", "-auto-approve"], cwd=TERRAFORM_DIR)

def ansible_play():
    run([
        "ansible-playbook",
        "playbooks/ecommerce-playbook.yml"
    ], cwd=ANSIBLE_DIR)

def test_front():
    """
    Test simple :
    - récupère front_url depuis les outputs Terraform
    - fait un curl sur cette URL
    """
    result = subprocess.check_output(
        ["terraform", "output", "-raw", "front_url"],
        cwd=TERRAFORM_DIR
    ).decode().strip()

    print(f"\nTest HTTP sur {result}")
    try:
        run(["curl", "-f", result], cwd=ROOT)
        print("\nTest HTTP OK (code 200 attendu)")
    except subprocess.CalledProcessError:
        print("\nLe test HTTP a échoué", file=sys.stderr)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 deploy.py [deploy|destroy|test]")
        sys.exit(1)

    action = sys.argv[1]

    if action == "deploy":
        terraform_apply()
        # On laisse un peu de temps aux VMs et conteneurs pour démarrer
        time.sleep(20)
        ansible_play()
        print("\n✅ Déploiement complet terminé.")
    elif action == "destroy":
        terraform_destroy()
        print("\n🧹 Infrastructure détruite.")
    elif action == "test":
        test_front()
    else:
        print("Action inconnue. Utilise: deploy | destroy | test")
        sys.exit(1)

if __name__ == "__main__":
    main()
