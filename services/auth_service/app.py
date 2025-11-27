import os
import secrets
from datetime import datetime, timedelta, UTC
from typing import Dict, Optional

import jwt
import requests
from authlib.integrations.flask_oauth2 import AuthorizationServer
from authlib.oauth2.rfc6749 import grants
from authlib.oauth2.rfc7636 import CodeChallenge
from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    session,
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMPLATES_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "templates"))

os.environ.setdefault("AUTHLIB_INSECURE_TRANSPORT", "1")

app = Flask(__name__, template_folder=TEMPLATES_DIR)
app.secret_key = os.environ.get("FLASK_SECRET", "front-secret")

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRATION_MINUTES = int(os.environ.get("TOKEN_EXP_MINUTES", "3"))
REFRESH_TOKEN_EXPIRATION_MINUTES = int(
    os.environ.get("REFRESH_TOKEN_EXP_MINUTES", "1440")
)  # 24h
USER_SERVICE_URL = os.environ.get("USER_SERVICE_URL", "http://127.0.0.1:5001")

refresh_tokens: Dict[str, Dict] = {}  # token -> {"sub": username, "exp": datetime}
authorization_codes: Dict[str, "AuthorizationCodeData"] = {}
issued_tokens: Dict[str, Dict] = {}


class InMemoryClient:
    def __init__(self, **kwargs):
        self.client_id = kwargs.get("client_id")
        self.client_secret = kwargs.get("client_secret")
        self.redirect_uris = kwargs.get("redirect_uris", [])
        self.grant_types = kwargs.get("grant_types", [])
        self.response_types = kwargs.get("response_types", [])
        self.scope = kwargs.get("scope", "")
        self.token_endpoint_auth_method = kwargs.get(
            "token_endpoint_auth_method", "client_secret_basic"
        )
        self.client_name = kwargs.get("client_name", self.client_id)

    def check_redirect_uri(self, uri: str) -> bool:
        return uri in self.redirect_uris

    def get_default_redirect_uri(self) -> Optional[str]:
        return self.redirect_uris[0] if self.redirect_uris else None

    def check_client_secret(self, secret: Optional[str]) -> bool:
        return self.client_secret == secret

    def check_token_endpoint_auth_method(self, method: str) -> bool:
        return method == self.token_endpoint_auth_method

    def check_endpoint_auth_method(self, method: str, endpoint: str) -> bool:
        # Authlib expects this helper when validating token requests.
        if endpoint == "token":
            return self.check_token_endpoint_auth_method(method)
        return method == self.token_endpoint_auth_method

    def check_response_type(self, response_type: str) -> bool:
        return response_type in self.response_types

    def check_grant_type(self, grant_type: str) -> bool:
        return grant_type in self.grant_types

    def get_allowed_scope(self, scope: str) -> str:
        allowed = set((self.scope or "").split())
        requested = set((scope or "").split())
        return " ".join(sorted(allowed & requested))

    def check_requested_scopes(self, scopes):
        allowed = set((self.scope or "").split())
        return set(scopes).issubset(allowed)


class AuthorizationCodeData:
    def __init__(
        self,
        code: str,
        client_id: str,
        redirect_uri: Optional[str],
        scope: str,
        user,
        code_challenge: Optional[str] = None,
        code_challenge_method: Optional[str] = None,
    ):
        self.code = code
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.user = user
        self.code_challenge = code_challenge
        self.code_challenge_method = code_challenge_method

    def get_redirect_uri(self):
        return self.redirect_uri

    def get_scope(self):
        return self.scope

    def get_client_id(self):
        return self.client_id

    def get_user(self):
        return self.user


OAUTH_CLIENTS: Dict[str, InMemoryClient] = {
    "student-spa": InMemoryClient(
        client_id="student-spa",
        client_secret=None,
        client_name="Front Demo PKCE",
        redirect_uris=[
            "http://127.0.0.1:9000/callback",
            "http://127.0.0.1:8000/callback",
        ],
        grant_types=["authorization_code"],
        response_types=["code"],
        scope="openid profile orders",
        token_endpoint_auth_method="none",
    ),
    "orders-cron": InMemoryClient(
        client_id="orders-cron",
        client_secret="orders-secret",
        client_name="Orders automation",
        redirect_uris=["http://localhost/cli"],
        grant_types=["client_credentials"],
        response_types=[],
        scope="orders",
        token_endpoint_auth_method="client_secret_basic",
    ),
}

authorization_server = AuthorizationServer()


def query_client(client_id):
    return OAUTH_CLIENTS.get(client_id)


def save_token(token_data, request):
    expires_at = datetime.now(UTC) + timedelta(seconds=token_data.get("expires_in", 0))
    token_data["expires_at"] = expires_at
    token_data["username"] = getattr(request.user, "username", None)
    issued_tokens[token_data["access_token"]] = token_data


class AuthorizationCodeGrant(grants.AuthorizationCodeGrant):
    TOKEN_ENDPOINT_AUTH_METHODS = ["client_secret_basic", "none"]

    def save_authorization_code(self, code, request):
        request_data = getattr(request, "data", {}) or {}
        stored_code = AuthorizationCodeData(
            code=code,
            client_id=request.client.client_id,
            redirect_uri=request.redirect_uri,
            scope=request.scope,
            user=request.user,
            code_challenge=getattr(request, "code_challenge", None)
            or request_data.get("code_challenge"),
            code_challenge_method=getattr(request, "code_challenge_method", None)
            or request_data.get("code_challenge_method"),
        )
        authorization_codes[code] = stored_code
        return stored_code

    def query_authorization_code(self, code, client):
        stored = authorization_codes.get(code)
        if stored and stored.client_id == client.client_id:
            return stored
        return None

    def delete_authorization_code(self, authorization_code):
        authorization_codes.pop(authorization_code.code, None)

    def authenticate_user(self, authorization_code):
        return authorization_code.user

    def should_require_code_challenge(self, client):
        # PKCE est obligatoire pour les clients publics (pas de secret)
        return client.token_endpoint_auth_method == "none"


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


def _verify_user(username: str, password: str) -> bool:
    try:
        verify_resp = requests.post(
            f"{USER_SERVICE_URL}/users/verify",
            json={"username": username, "password": password},
            timeout=3,
        )
    except requests.RequestException:
        return False
    return verify_resp.status_code == 200


def _current_user():
    username = session.get("username")
    return type("User", (), {"username": username}) if username else None


authorization_server.init_app(app, query_client=query_client, save_token=save_token)
authorization_server.register_grant(AuthorizationCodeGrant, [CodeChallenge(required=True)])
authorization_server.register_grant(grants.ClientCredentialsGrant)


@app.route("/auth/login", methods=["POST"])
def login():
    payload = request.get_json() or {}
    username = (payload.get("username") or "").strip().lower()
    password = payload.get("password") or ""

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    if not _verify_user(username, password):
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


@app.route("/oauth/authorize", methods=["GET", "POST"])
def authorize():
    user = _current_user()
    if request.method == "GET":
        try:
            grant = authorization_server.get_consent_grant(end_user=user)
        except Exception as exc:  # pragma: no cover - simple demo handling
            return authorization_server.handle_error_response(request=request, error=exc)
        return render_template(
            "consent.html", user=user, grant=grant, client=grant.client
        )

    if not user:
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        if not username or not password or not _verify_user(username, password):
            grant = authorization_server.get_consent_grant(end_user=None)
            return render_template(
                "consent.html",
                user=None,
                grant=grant,
                client=grant.client,
                error="Identifiants invalides",
            )
        session["username"] = username
        user = _current_user()

    confirmed = request.form.get("confirm") == "yes"
    return authorization_server.create_authorization_response(
        grant_user=user if confirmed else None
    )


@app.route("/oauth/token", methods=["POST"])
def issue_token():
    return authorization_server.create_token_response()


@app.route("/oauth/introspect", methods=["POST"])
def introspect():
    token = request.form.get("token") or ""
    token_data = issued_tokens.get(token)
    now = datetime.now(UTC)

    if not token_data or token_data.get("expires_at", now) <= now:
        return jsonify({"active": False})

    return jsonify(
        {
            "active": True,
            "client_id": token_data.get("client_id"),
            "username": token_data.get("username"),
            "scope": token_data.get("scope"),
            "exp": int(token_data.get("expires_at").timestamp()),
        }
    )


@app.route("/oauth/logout", methods=["POST"])
def oauth_logout():
    session.clear()
    return jsonify({"logout": True})


if __name__ == "__main__":
    app.run(port=5002, debug=True)
