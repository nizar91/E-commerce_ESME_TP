import os
from functools import wraps

import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "front-secret")

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:5000")

# Liste d'articles affiches sur l'interface
ARTICLES = [
    {"id": 1, "name": "Article 1"},
    {"id": 2, "name": "Article 2"},
    {"id": 3, "name": "Article 3"},
]


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

    resp, error = call_gateway("POST", "/refresh", json={"refresh_token": refresh_token})
    if error:
        session.clear()
        return False, error

    if resp.status_code != 200:
        payload = resp.json()
        session.clear()
        return False, payload.get("error", "Impossible de renouveler la session.")

    data = resp.json()
    session["token"] = data.get("token")
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


@app.route("/", methods=["GET", "POST"])
def login():
    success_message = request.args.get("success")

    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""

        if not username or not password:
            return render_template("login.html", error="Champs requis manquants.")

        resp, error = call_gateway(
            "POST", "/login", json={"username": username, "password": password}
        )
        if error:
            return render_template("login.html", error=error)

        if resp.status_code != 200:
            payload = resp.json()
            return render_template("login.html", error=payload.get("error", "Echec de connexion."))

        data = resp.json()
        session["token"] = data["token"]
        session["refresh_token"] = data.get("refresh_token")
        session["username"] = username
        return redirect(url_for("home"))

    return render_template("login.html", success=success_message)


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
