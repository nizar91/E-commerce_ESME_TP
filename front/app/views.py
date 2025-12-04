# app/views.py
from app import app
from flask import render_template, request, redirect, url_for, session
import os
import socket
import requests

# ---------------------------
# CONFIGURATION DES SERVICES
# ---------------------------
#Définit les URLs des microservices utilisés par le front Flask.
# Le front communique uniquement avec le Gateway, qui lui-même communique avec les autres services
GATEWAY_URL = "http://gateway:5003/api/orders"
AUTH_LOGIN_URL = "http://auth:5002/auth/login"
AUTH_REGISTER_URL = "http://auth:5002/auth/register"
AUTH_REFRESH_URL = "http://auth:5002/auth/refresh"

# Basculer automatiquement vers localhost si les hôtes Docker ne sont pas joignables.
def _resolve_or_local(default_host):
    try:
        socket.gethostbyname(default_host)
        return default_host
    except socket.gaierror:
        return "localhost"


GATEWAY_HOST = os.environ.get("GATEWAY_SERVICE_HOST") or _resolve_or_local("gateway")
AUTH_HOST = os.environ.get("AUTH_SERVICE_HOST") or _resolve_or_local("auth")

GATEWAY_URL = f"http://{GATEWAY_HOST}:5003/api/orders"
AUTH_LOGIN_URL = f"http://{AUTH_HOST}:5002/auth/login"
AUTH_REGISTER_URL = f"http://{AUTH_HOST}:5002/auth/register"
AUTH_REFRESH_URL = f"http://{AUTH_HOST}:5002/auth/refresh"

# Clé secrète Flask pour la session (stockage temporaire)
# Pour stocker le token JWT entre les requêtes.
app.secret_key = "SuperSecretKeyTP"


# ==========================
# 1️⃣ PAGE DE CONNEXION
# ==========================
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Page de login / inscription."""
    if request.method == 'POST':
        username = request.form.get('user')
        password = request.form.get('password')
        action = request.form.get('action')

        if not username or not password:
            return render_template('login.html', error="Veuillez remplir tous les champs.")

        # --- INSCRIPTION ---
        if action == 'register':
            try:
                r = requests.post(AUTH_REGISTER_URL, json={'username': username, 'password': password})

                if r.status_code == 201:
                    return render_template('login.html',
                                           error="✅ Inscription réussie. Connectez-vous maintenant.")
                else:
                    return render_template('login.html',
                                           error=r.json().get('message', "Erreur d'inscription."))
            except requests.exceptions.ConnectionError:
                return render_template('login.html',
                                       error="⚠️ Auth Service indisponible (port 5002).")

        # --- CONNEXION ---
        try:
            r = requests.post(AUTH_LOGIN_URL,
                              json={'username': username, 'password': password})

            if r.status_code == 200:
                session['token'] = r.json().get('access_token')
                session['refresh_token'] = r.json().get('refresh_token')
                session['user'] = username
                return redirect(url_for('accueil', user=username))

            else:
                return render_template('login.html', error="❌ Identifiants incorrects.")

        except requests.exceptions.ConnectionError:
            return render_template('login.html',
                                   error="⚠️ Auth Service indisponible (port 5002).")

    return render_template('login.html')


# ==========================
# 2️⃣ PAGE D’ACCUEIL
# ==========================
@app.route('/accueil')
def accueil():
    user = session.get('user')
    token = session.get('token')

    if not user or not token:
        return redirect(url_for('login'))

    return render_template('accueil.html', user=user, token=token)


# ==========================
# 3️⃣ SOUMISSION D’UNE COMMANDE
# ==========================
@app.route('/submit_order/<user>', methods=['POST'])
def submit_order(user):
    token = session.get('token')

    # Construction du panier
    articles = {
        'T-shirt coton premium': 24.90,
        'Jean slim indigo': 59.90,
        'Pull en laine merinos': 69.90,
        "Robe d'été fluide": 49.90,
        'Veste saharienne': 89.00,
        'Baskets de ville': 79.00,
        'Chemise classique': 44.90,
        'Sweat oversize': 39.90
    }

    items = []
    for nom, prix in articles.items():
        qte = int(request.form.get(nom, 0))
        if qte > 0:
            items.append({
                'article': nom,
                'quantity': qte,
                'unit_price': prix,
                'total_price': round(prix * qte, 2)
            })

    if not items:
        return render_template('accueil.html',
                               user=user, token=token,
                               error_message="Veuillez sélectionner au moins un article.")

    # ------------- FONCTION QUI EFFECTUE L’ENVOI AU GATEWAY -------------
    def call_gateway(token_to_use):
        headers = {'Authorization': f'Bearer {token_to_use}'}
        return requests.post(GATEWAY_URL, json={'items': items}, headers=headers)

    # Premier essai
    try:
        response = call_gateway(token)

        # Si OK → afficher résultat
        if response.status_code in (200, 201):
            return render_success(response, user, items)

        # Si 401 → peut-être token expiré → tenter refresh
        if response.status_code == 401:
            return handle_token_expired(user, items)

        # Sinon → erreur service
        return render_template('achat.html', user=user, status="error_service",
                               order_details=items)

    except requests.exceptions.ConnectionError:
        return render_template('achat.html',
                               user=user, status="error_service",
                               order_details=items)


# ==========================
# 🔧 UTILITAIRES
# ==========================

def render_success(response, user, items):
    """Analyse la réponse du Gateway après un succès."""
    try:
        data = response.json()
        if isinstance(data, list) and data:
            data = data[0]
        elif not isinstance(data, dict):
            data = {}

        status = data.get('status', 'ok')

    except Exception:
        status = "error_internal"

    return render_template('achat.html', user=user, status=status, order_details=items)


def handle_token_expired(user, items):
    """Gère le cas où le token access est expiré → effectuer refresh."""
    refresh_token = session.get('refresh_token')

    if not refresh_token:
        return render_template('achat.html', user=user, status="error_auth")

    # Appeler /auth/refresh
    try:
        r = requests.post(AUTH_REFRESH_URL,
                          json={'refresh_token': refresh_token})

        if r.status_code != 200:
            return render_template('achat.html', user=user, status="error_auth")

        # Nouveau token
        new_token = r.json().get('access_token')
        session['token'] = new_token

        # Réessayer la commande
        second_try = requests.post(GATEWAY_URL,
                                   json={'items': items},
                                   headers={'Authorization': f'Bearer {new_token}'})

        return render_success(second_try, user, items)

    except requests.exceptions.ConnectionError:
        return render_template('achat.html', user=user, status="error_service")


# ==========================
# 4️⃣ ROUTE PAR DÉFAUT
# ==========================
#Sert à rediriger vers la page de login si l'utilisateur accède à la racine.
@app.route('/')
def index():
    return redirect(url_for('login'))
