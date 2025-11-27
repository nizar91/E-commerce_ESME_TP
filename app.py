import base64
import hashlib
import os
import secrets
import string
from functools import wraps
from urllib.parse import urlencode

import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "front-secret")

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:5000")
AUTH_SERVER_URL = os.environ.get("AUTH_SERVICE_URL", "http://127.0.0.1:5002")
OAUTH_CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID", "student-spa")
OAUTH_SCOPE = os.environ.get("OAUTH_SCOPE", "openid profile orders")
OAUTH_REDIRECT_URI = os.environ.get("OAUTH_REDIRECT_URI", "http://127.0.0.1:8000/callback")

# Liste d'articles affiches sur l'interface
ARTICLES = [
    {"id": 1, "name": "Article 1"},
    {"id": 2, "name": "Article 2"},
    {"id": 3, "name": "Article 3"},
]


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _generate_code_verifier(length: int = 64) -> str:
    alphabet = string.ascii_letters + string.digits + "-._~"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _build_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return _base64url(digest)


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "token" not in session:
            flash("Merci de vous connecter pour acceder a cette page.", "error")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapper


def call_gateway(method: str, path: str, **kwargs):
    """Helper pour appeler le Gateway avec gestion d'erreurs."""
    url = f"{GATEWAY_URL}{path}"
    try:
        response = requests.request(method, url, timeout=5, **kwargs)
        return response, None
    except requests.RequestException as exc:
        return None, f"Gateway injoignable ({exc})"


def refresh_access_token():
    refresh_token = session.get("refresh_token")
    if not refresh_token:
        session.clear()
        return False, "Session expiree, merci de vous reconnecter."

    try:
        resp = requests.post(
            f"{AUTH_SERVER_URL}/oauth/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": OAUTH_CLIENT_ID,
            },
            timeout=5,
        )
    except requests.RequestException as exc:
        session.clear()
        return False, f"Serveur OAuth injoignable ({exc})"

    if resp.status_code != 200:
        session.clear()
        try:
            payload = resp.json()
            message = payload.get("error_description") or payload.get("error")
        except ValueError:
            message = "Impossible de renouveler la session."
        return False, message or "Impossible de renouveler la session."

    data = resp.json()
    session["token"] = data.get("access_token") or data.get("token")
    session["refresh_token"] = data.get("refresh_token")
    return True, None


def gateway_authenticated_request(method: str, path: str, *, json_body=None):
    if "token" not in session:
        return None, "Session expiree, merci de vous reconnecter."

    request_kwargs = {}
    if json_body is not None:
        request_kwargs["json"] = json_body

    def _perform_request():
        headers = {"Authorization": f"Bearer {session.get('token', '')}"}
        return call_gateway(method, path, headers=headers, **request_kwargs)

    resp, error = _perform_request()
    if resp is not None and resp.status_code == 401:
        refreshed, refresh_error = refresh_access_token()
        if not refreshed:
            return None, refresh_error
        resp, error = _perform_request()

    return resp, error


@app.route("/", methods=["GET"])
def login():
    success_message = request.args.get("success")
    error_message = request.args.get("error")
    return render_template("login.html", success=success_message, error=error_message)


@app.route("/oauth/start")
def oauth_start():
    code_verifier = _generate_code_verifier()
    code_challenge = _build_code_challenge(code_verifier)
    state = secrets.token_urlsafe(32)

    session["oauth_state"] = state
    session["oauth_verifier"] = code_verifier

    params = {
        "response_type": "code",
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "scope": OAUTH_SCOPE,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    authorize_url = f"{AUTH_SERVER_URL}/oauth/authorize?{urlencode(params)}"
    return redirect(authorize_url)


@app.route("/callback")
def oauth_callback():
    error = request.args.get("error")
    if error:
        description = request.args.get("error_description", "Authentification annulee.")
        return redirect(url_for("login", error=description))

    state = request.args.get("state")
    if not state or state != session.get("oauth_state"):
        session.clear()
        flash("Etat OAuth invalide, merci de recommencer.", "error")
        return redirect(url_for("login"))

    code = request.args.get("code")
    code_verifier = session.get("oauth_verifier")
    if not code or not code_verifier:
        session.clear()
        flash("Code OAuth manquant, merci de recommencer.", "error")
        return redirect(url_for("login"))

    try:
        token_resp = requests.post(
            f"{AUTH_SERVER_URL}/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": OAUTH_REDIRECT_URI,
                "client_id": OAUTH_CLIENT_ID,
                "code_verifier": code_verifier,
            },
            timeout=5,
        )
    except requests.RequestException as exc:
        session.clear()
        flash(f"Serveur OAuth injoignable ({exc})", "error")
        return redirect(url_for("login"))

    if token_resp.status_code != 200:
        session.clear()
        try:
            payload = token_resp.json()
            message = payload.get("error_description") or payload.get("error")
        except ValueError:
            message = "Echec de l'echantillonnage du token."
        flash(message or "Echec lors de la recuperation du token.", "error")
        return redirect(url_for("login"))

    data = token_resp.json()
    access_token = data.get("access_token") or data.get("token")
    if not access_token:
        session.clear()
        flash("Token acces introuvable dans la reponse OAuth.", "error")
        return redirect(url_for("login"))

    session["token"] = access_token
    session["refresh_token"] = data.get("refresh_token")
    session["username"] = data.get("username") or session.get("username") or "utilisateur"
    session.pop("oauth_state", None)
    session.pop("oauth_verifier", None)

    return redirect(url_for("home"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Deconnexion effectuee.", "success")
    return redirect(url_for("login"))


@app.route("/home")
@login_required
def home():
    username = session.get("username", "")
    return render_template("home.html", username=username, articles=ARTICLES)


@app.route("/buy/<int:article_id>", methods=["POST"])
@login_required
def buy(article_id):
    article = next((a for a in ARTICLES if a["id"] == article_id), None)
    if not article:
        return "Article introuvable", 404

    resp, error = gateway_authenticated_request(
        "POST",
        "/orders",
        json_body={"item": article["name"], "quantity": 1},
    )

    if error:
        return render_template("buy.html", username=session.get("username"), article=article, error=error)

    if resp.status_code >= 400:
        payload = resp.json()
        return render_template(
            "buy.html",
            username=session.get("username"),
            article=article,
            error=payload.get("error", "Echec lors de la creation de la commande."),
        )

    return render_template("buy.html", username=session.get("username"), article=article)


@app.route("/purchases")
@login_required
def view_purchases():
    resp, error = gateway_authenticated_request("GET", "/orders")

    if error:
        return render_template("purchases.html", username=session.get("username"), purchases=[], error=error)

    if resp.status_code != 200:
        payload = resp.json()
        return render_template(
            "purchases.html",
            username=session.get("username"),
            purchases=[],
            error=payload.get("error", "Impossible de recuperer les commandes."),
        )

    orders = resp.json().get("orders", [])
    return render_template("purchases.html", username=session.get("username"), purchases=orders)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""

        if not username or not password:
            return render_template("register.html", error="Merci de renseigner tous les champs.")

        if password != confirm:
            return render_template("register.html", error="Les mots de passe ne correspondent pas.")

        resp, error = call_gateway("POST", "/register", json={"username": username, "password": password})
        if error:
            return render_template("register.html", error=error)

        if resp.status_code != 201:
            payload = resp.json()
            return render_template("register.html", error=payload.get("error", "Impossible de creer le compte."))

        success_msg = "Compte cree, vous pouvez vous connecter."
        return redirect(url_for("login", success=success_msg))

    return render_template("register.html")


if __name__ == "__main__":
    app.run(port=8000, debug=True)
