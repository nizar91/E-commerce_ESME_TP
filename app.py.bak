from flask import Flask, render_template, request, redirect, url_for
import json, os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash  # <- hashing

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "users.db")  # chemin absolu -> évite les confusions

# Liste d'articles
ARTICLES = [
    {"id": 1, "name": "Article 1"},
    {"id": 2, "name": "Article 2"},
    {"id": 3, "name": "Article 3"},
]


# ---------- UTILITAIRES JSON (pour purchases.json) ----------

def load_json(filename):
    if not os.path.exists(filename):
        return {}
    with open(filename, "r") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)


# ---------- HACHAGE / UTILITAIRES SQLITE ----------

def hash_password(plain_password: str) -> str:
    """Retourne le hash sécurisé d'un mot de passe (PBKDF2 + SHA256)."""
    return generate_password_hash(plain_password)

def verify_password(hashed_password: str, plain_password: str) -> bool:
    """Vérifie si plain_password correspond au hashed_password."""
    return check_password_hash(hashed_password, plain_password)


def init_db():
    """Crée la base users.db + quelques utilisateurs de test si besoin."""
    print("DB PATH =", DB_NAME)
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Créer la table si elle n'existe pas
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Utilisateurs de démo (on insère des hashes, pas de texte clair)
    default_users = [
        ("victor", "1234"),
        ("kilian", "abcd"),
        ("baptiste", "pass"),
    ]

    for username, password in default_users:
        try:
            cur.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, hash_password(password))
            )
        except sqlite3.IntegrityError:
            # utilisateur déjà présent -> on ignore
            pass

    conn.commit()
    conn.close()


def migrate_plaintext_passwords():
    """
    Si tu as déjà une DB avec des mots de passe en clair, appelle cette fonction
    une seule fois pour remplacer les mots de passe par leurs hashes.
    Elle considère qu'un hash valide commence par 'pbkdf2:' (format werkzeug).
    """
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, password FROM users")
    rows = cur.fetchall()
    updated = 0
    for user_id, pwd in rows:
        if not pwd.startswith("pbkdf2:"):  # heuristique simple
            new_hash = hash_password(pwd)
            cur.execute("UPDATE users SET password = ? WHERE id = ?", (new_hash, user_id))
            updated += 1
    conn.commit()
    conn.close()
    print(f"Migrated {updated} plaintext passwords to hashed passwords.")


def create_user(username: str, plain_password: str) -> bool:
    """Crée un utilisateur avec mot de passe haché. Retourne True si OK."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                    (username, hash_password(plain_password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def check_user_credentials(username: str, password: str) -> bool:
    """Retourne True si (username, password) existent en base (vérifie hash)."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()

    if row is None:
        return False

    stored_hash = row[0]
    return verify_password(stored_hash, password)


# ---------- ROUTES FLASK ----------

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        if check_user_credentials(username, password):
            return redirect(url_for("home", username=username))
        else:
            return render_template("login.html", error="Identifiant ou mot de passe incorrect.")

    return render_template("login.html")


@app.route("/home")
def home():
    username = request.args.get("username", "")
    return render_template("home.html", username=username, articles=ARTICLES)


@app.route("/buy/<int:article_id>")
def buy(article_id):
    username = request.args.get("username", "")
    article = next((a for a in ARTICLES if a["id"] == article_id), None)

    if not article:
        return "Article introuvable", 404

    purchases = load_json("purchases.json")

    if username:
        if username not in purchases:
            purchases[username] = []
        purchases[username].append(article["name"])
        save_json("purchases.json", purchases)

    return render_template("buy.html", article=article, username=username)


@app.route("/purchases")
def view_purchases():
    username = request.args.get("username", "")
    purchases = load_json("purchases.json").get(username, [])
    return render_template("purchases.html", username=username, purchases=purchases)


if __name__ == "__main__":
    init_db()          # crée la table + utilisateurs de démonstration (hachés)
    # migrate_plaintext_passwords()  # <--- décommenter *une fois* si nécessaire
    app.run(debug=True)
