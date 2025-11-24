"""Client de démonstration pour les flux OAuth2 du TP.

Lancez les services puis exécutez :

    python scripts/oauth_client.py --username alice --password passw0rd

Le script illustre un flux Authorization Code + PKCE et un flux Client Credentials.
"""

import argparse
import base64
import os
import secrets
import string
import hashlib
from urllib.parse import parse_qs, urlparse

import requests

AUTH_SERVER = os.environ.get("AUTH_SERVICE_URL", "http://127.0.0.1:5002")


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def build_pkce_pair():
    verifier = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(64))
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = _base64url(digest)
    return verifier, challenge


def run_pkce_flow(username: str, password: str):
    client_id = "student-spa"
    redirect_uri = "http://127.0.0.1:9000/callback"
    scope = "openid profile orders"
    code_verifier, code_challenge = build_pkce_pair()

    session = requests.Session()
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    auth_page = session.get(f"{AUTH_SERVER}/oauth/authorize", params=params, allow_redirects=False)
    if auth_page.status_code != 200:
        raise RuntimeError(f"Erreur lors de la récupération de la page de consentement ({auth_page.status_code})")

    payload = {"username": username, "password": password, "confirm": "yes"}
    consent_resp = session.post(
        f"{AUTH_SERVER}/oauth/authorize",
        params=params,
        data=payload,
        allow_redirects=False,
    )
    if "Location" not in consent_resp.headers:
        raise RuntimeError("Aucun code renvoyé, vérifiez les identifiants ou le consentement.")

    location = consent_resp.headers["Location"]
    code = parse_qs(urlparse(location).query).get("code", [None])[0]
    if not code:
        raise RuntimeError("Impossible d'extraire le code d'autorisation.")

    token_resp = session.post(
        f"{AUTH_SERVER}/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "code_verifier": code_verifier,
        },
    )
    token_resp.raise_for_status()
    print("Token Authorization Code + PKCE :", token_resp.json())


def run_client_credentials():
    token_resp = requests.post(
        f"{AUTH_SERVER}/oauth/token",
        data={"grant_type": "client_credentials", "scope": "orders"},
        auth=("orders-cron", "orders-secret"),
    )
    token_resp.raise_for_status()
    print("Token Client Credentials :", token_resp.json())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True, help="Utilisateur pour le flux PKCE")
    parser.add_argument("--password", required=True, help="Mot de passe pour le flux PKCE")
    args = parser.parse_args()

    run_pkce_flow(args.username, args.password)
    run_client_credentials()
