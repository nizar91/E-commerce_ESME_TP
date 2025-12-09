# auth_service_stateful.py
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify
from authlib.jose import jwt, JoseError
import sqlite3
from flask_bcrypt import Bcrypt
from functools import wraps

# --- 1. Initialisation de l'API ---
auth_app = Flask(__name__)
auth_app.config['SECRET_KEY'] = 'SuperSecretKeyPourTP'
bcrypt = Bcrypt(auth_app)

# --- 2. Base de données SQLite ---
DATABASE_NAME = 'users.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Crée les tables si elles n'existent pas."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            token TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            token TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()

def get_user_by_username(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, password_hash FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    return user

def add_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    try:
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed_password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def check_password(hashed_password, password):
    return bcrypt.check_password_hash(hashed_password.encode('utf-8'), password)

# Initialisation DB
init_db()

# ================================
#  ROUTE DE SANTÉ
# ================================
@auth_app.route('/health', methods=['GET'])
def health_check():
    """Route simple pour vérifier la santé du service."""
    return jsonify({"status": "healthy"}), 200


# ================================
#  Décorateur d'authentification
# ================================
# Vérifie que le token est valide et présent en base de données
def require_auth(func):
    """Vérifie que le token envoyé dans le header Authorization est valide et présent en base."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"message": "Token manquant"}), 401

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({"message": "Format du token invalide"}), 401

        token = parts[1]

        try:
            payload = jwt.decode(token, auth_app.config['SECRET_KEY'])
        except JoseError:
            return jsonify({"message": "Token invalide ou expiré"}), 401

        # Vérification stateful : token présent en base et non expiré
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM access_tokens WHERE token = ?", (token,))
        record = cursor.fetchone()
        conn.close()

        if not record:
            return jsonify({"message": "Token révoqué ou inconnu"}), 401

        if datetime.fromisoformat(record["expires_at"]) < datetime.now(timezone.utc):
            return jsonify({"message": "Token expiré"}), 401

        return func(payload, *args, **kwargs)
    return wrapper

# ================================
#  ROUTES PUBLIQUES
# ================================

@auth_app.route('/auth/register', methods=['POST'])
def register():
    """Inscription utilisateur"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if get_user_by_username(username):
        return jsonify({"message": "Ce nom d'utilisateur existe déjà."}), 409

    if add_user(username, password):
        return jsonify({"message": "Inscription réussie."}), 201
    else:
        return jsonify({"message": "Erreur interne."}), 500

@auth_app.route('/auth/login', methods=['POST'])
def login():
    """Connexion utilisateur, génération access + refresh token"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user_record = get_user_by_username(username)
    if not user_record or not check_password(user_record['password_hash'], password):
        return jsonify({"message": "Identifiants incorrects."}), 401

    now = datetime.now(timezone.utc)

    # --- Access token stateful ---
    access_payload = {
        "user": username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=30)).timestamp())
    }
    access_header = {"alg": "HS256"}
    access_token = jwt.encode(access_header, access_payload, auth_app.config['SECRET_KEY']).decode()

    # Stocker en base
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO access_tokens (username, token, expires_at)
        VALUES (?, ?, ?)
    """, (username, access_token, str(now + timedelta(minutes=30))))
    conn.commit()

    # --- Refresh token ---
    refresh_payload = {
        "user": username,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=7)).timestamp())
    }
    refresh_header = {"alg": "HS256"}
    refresh_token = jwt.encode(refresh_header, refresh_payload, auth_app.config['SECRET_KEY']).decode()

    cursor.execute("""
        INSERT INTO refresh_tokens (username, token, expires_at)
        VALUES (?, ?, ?)
    """, (username, refresh_token, str(now + timedelta(days=7))))
    conn.commit()
    conn.close()

    return jsonify({
        "message": "Connexion réussie.",
        "access_token": access_token,
        "refresh_token": refresh_token
    }), 200

# ================================
#  ROUTES PROTÉGÉES
# ================================

@auth_app.route('/auth/validate', methods=['POST'])
@require_auth
# Cette fonction vérifie le token via Auth Service
def validate_token(payload):
    """Validation JWT (pour API Gateway)"""
    return jsonify({"message": "Token valide", "user": payload["user"]}), 200

@auth_app.route('/auth/refresh', methods=['POST'])
def refresh_token():
    """Rafraîchissement du token access"""
    data = request.get_json() or {}
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        return jsonify({"message": "Refresh token manquant"}), 400

    # Décodage et vérification
    try:
        decoded = jwt.decode(refresh_token, auth_app.config['SECRET_KEY'])
    except JoseError:
        return jsonify({"message": "Refresh token invalide ou expiré"}), 401

    if decoded.get("type") != "refresh" or "user" not in decoded:
        return jsonify({"message": "Refresh token invalide"}), 401

    username = decoded["user"]

    # Vérification en base
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM refresh_tokens WHERE username=? AND token=?", (username, refresh_token))
    record = cursor.fetchone()
    conn.close()

    if not record:
        return jsonify({"message": "Refresh token inconnu"}), 401

    now = datetime.now(timezone.utc)

    # --- Nouveau access token ---
    new_access_payload = {
        "user": username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=30)).timestamp())
    }
    new_access_token = jwt.encode({"alg": "HS256"}, new_access_payload, auth_app.config['SECRET_KEY']).decode()

    # Stockage en base
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO access_tokens (username, token, expires_at)
        VALUES (?, ?, ?)
    """, (username, new_access_token, str(now + timedelta(minutes=30))))
    conn.commit()
    conn.close()

    return jsonify({"access_token": new_access_token}), 200

@auth_app.route('/auth/logout', methods=['POST'])
@require_auth
# Vérifie que le token est valide et présent en base de données
def logout(payload):
    """Déconnexion utilisateur (révocation access + refresh token)"""
    data = request.get_json()
    refresh_token = data.get("refresh_token")
    auth_header = request.headers.get("Authorization")
    access_token = auth_header.split(" ")[1] if auth_header else None

    conn = get_db_connection()
    cursor = conn.cursor()

    if access_token:
        cursor.execute("DELETE FROM access_tokens WHERE token=?", (access_token,))
    if refresh_token:
        cursor.execute("DELETE FROM refresh_tokens WHERE token=?", (refresh_token,))

    conn.commit()
    conn.close()

    return jsonify({"message": f"Utilisateur {payload['user']} déconnecté avec succès."}), 200

# --- Lancement du service ---
if __name__ == '__main__':
    auth_app.run(debug=True, port=5002, host='0.0.0.0')
