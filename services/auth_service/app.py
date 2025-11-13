import os
import secrets
from datetime import datetime, timedelta, UTC

import jwt
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRATION_MINUTES = int(os.environ.get("TOKEN_EXP_MINUTES", "3"))
REFRESH_TOKEN_EXPIRATION_MINUTES = int(os.environ.get("REFRESH_TOKEN_EXP_MINUTES", "1440"))  # 24h
USER_SERVICE_URL = os.environ.get("USER_SERVICE_URL", "http://127.0.0.1:5001")

refresh_tokens = {}  # token -> {"sub": username, "exp": datetime}


def _cleanup_refresh_tokens():
    now = datetime.now(UTC)
    expired = [token for token, meta in refresh_tokens.items() if meta["exp"] <= now]
    for token in expired:
        refresh_tokens.pop(token, None)


def _issue_token(username: str) -> str:
    payload = {
        "sub": username,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=TOKEN_EXPIRATION_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _issue_refresh_token(username: str) -> str:
    _cleanup_refresh_tokens()
    token = secrets.token_urlsafe(48)
    refresh_tokens[token] = {
        "sub": username,
        "exp": datetime.now(UTC) + timedelta(minutes=REFRESH_TOKEN_EXPIRATION_MINUTES),
    }
    return token


def _extract_token():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]
    payload = request.get_json(silent=True) or {}
    return payload.get("token")


@app.route("/auth/login", methods=["POST"])
def login():
    payload = request.get_json() or {}
    username = (payload.get("username") or "").strip().lower()
    password = payload.get("password") or ""

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    try:
        verify_resp = requests.post(
            f"{USER_SERVICE_URL}/users/verify",
            json={"username": username, "password": password},
            timeout=3,
        )
    except requests.RequestException as exc:
        return jsonify({"error": f"user service unavailable: {exc}"}), 503

    if verify_resp.status_code != 200:
        return jsonify({"error": "invalid credentials"}), 401

    token = _issue_token(username)
    refresh_token = _issue_refresh_token(username)
    return jsonify(
        {
            "token": token,
            "token_type": "Bearer",
            "refresh_token": refresh_token,
            "expires_in": TOKEN_EXPIRATION_MINUTES * 60,
        }
    )


@app.route("/auth/refresh", methods=["POST"])
def refresh():
    payload = request.get_json() or {}
    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        return jsonify({"error": "refresh_token required"}), 400

    metadata = refresh_tokens.get(refresh_token)
    if not metadata or metadata["exp"] <= datetime.now(UTC):
        refresh_tokens.pop(refresh_token, None)
        return jsonify({"error": "invalid refresh token"}), 401

    username = metadata["sub"]
    refresh_tokens.pop(refresh_token, None)
    new_refresh = _issue_refresh_token(username)
    new_access = _issue_token(username)

    return jsonify(
        {
            "token": new_access,
            "token_type": "Bearer",
            "refresh_token": new_refresh,
            "expires_in": TOKEN_EXPIRATION_MINUTES * 60,
        }
    )


@app.route("/auth/validate", methods=["POST"])
def validate():
    token = _extract_token()
    if not token:
        return jsonify({"valid": False, "error": "token required"}), 400

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return jsonify({"valid": False, "error": "token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"valid": False, "error": "invalid token"}), 401

    return jsonify({"valid": True, "username": payload["sub"]})


if __name__ == "__main__":
    app.run(port=5002, debug=True)
