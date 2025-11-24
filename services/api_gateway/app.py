import os

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://127.0.0.1:5002")
USER_SERVICE_URL = os.environ.get("USER_SERVICE_URL", "http://127.0.0.1:5001")
ORDERS_SERVICE_URL = os.environ.get("ORDERS_SERVICE_URL", "http://127.0.0.1:5003")


def _forward_json(method, url, *, headers=None, json_body=None):
    try:
        resp = requests.request(
            method,
            url,
            headers=headers,
            json=json_body,
            timeout=3,
        )
    except requests.RequestException as exc:
        return None, (jsonify({"error": f"service unavailable: {exc}"}), 503)
    return resp, None


def _introspect_oauth(token: str):
    try:
        resp = requests.post(
            f"{AUTH_SERVICE_URL}/oauth/introspect",
            data={"token": token},
            timeout=3,
        )
    except requests.RequestException:
        return None

    if resp.status_code != 200:
        return None

    data = resp.json()
    if not data.get("active"):
        return None

    return data.get("username") or data.get("client_id")


def _validate_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, (jsonify({"error": "Authorization: Bearer <token> required"}), 401)

    token = auth_header.split(" ", 1)[1]

    # Essai OAuth2 (tokens issus d'Authlib)
    oauth_identity = _introspect_oauth(token)
    if oauth_identity:
        return oauth_identity, None

    # Fallback pour les anciens JWT utilisés par le front
    resp, error = _forward_json(
        "POST",
        f"{AUTH_SERVICE_URL}/auth/validate",
        json_body={"token": token},
    )
    if error:
        return None, error

    payload = resp.json()
    if resp.status_code != 200 or not payload.get("valid"):
        return None, (jsonify({"error": payload.get("error", "invalid token")}), 401)

    return payload["username"], None


@app.route("/register", methods=["POST"])
def register():
    body = request.get_json() or {}
    resp, error = _forward_json("POST", f"{USER_SERVICE_URL}/users", json_body=body)
    if error:
        return error
    return jsonify(resp.json()), resp.status_code


@app.route("/login", methods=["POST"])
def login():
    body = request.get_json() or {}
    resp, error = _forward_json("POST", f"{AUTH_SERVICE_URL}/auth/login", json_body=body)
    if error:
        return error
    return jsonify(resp.json()), resp.status_code


@app.route("/refresh", methods=["POST"])
def refresh():
    body = request.get_json() or {}
    resp, error = _forward_json("POST", f"{AUTH_SERVICE_URL}/auth/refresh", json_body=body)
    if error:
        return error
    return jsonify(resp.json()), resp.status_code


@app.route("/orders", methods=["GET", "POST"])
def orders():
    username, error = _validate_token()
    if error:
        return error

    headers = {"X-User": username}
    if request.method == "GET":
        resp, proxy_error = _forward_json("GET", f"{ORDERS_SERVICE_URL}/orders", headers=headers)
    else:
        resp, proxy_error = _forward_json(
            "POST",
            f"{ORDERS_SERVICE_URL}/orders",
            headers=headers,
            json_body=request.get_json() or {},
        )

    if proxy_error:
        return proxy_error

    return jsonify(resp.json()), resp.status_code


if __name__ == "__main__":
    app.run(port=5000, debug=True)
