import os
import sqlite3
from flask import Flask, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")


def init_db():
    """Create the SQLite database if it does not exist yet and seed demo data."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """
    )
    conn.commit()

    # Ensure demo user for OAuth client tests exists.
    cur.execute("SELECT 1 FROM users WHERE username = ?", ("alice",))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            ("alice", generate_password_hash("passw0rd")),
        )
        conn.commit()

    conn.close()


def get_user(username: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, username, password FROM users WHERE username = ?", (username.lower(),))
    row = cur.fetchone()
    conn.close()
    return row


@app.route("/users", methods=["POST"])
def create_user():
    payload = request.get_json() or {}
    username = (payload.get("username") or "").strip().lower()
    password = payload.get("password")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )
        conn.commit()
        user_id = cur.lastrowid
        conn.close()
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 409

    return jsonify({"id": user_id, "username": username}), 201


@app.route("/users/<username>", methods=["GET"])
def fetch_user(username):
    row = get_user(username)
    if not row:
        return jsonify({"error": "user not found"}), 404
    _, stored_username, _ = row
    return jsonify({"username": stored_username})


@app.route("/users/verify", methods=["POST"])
def verify_credentials():
    payload = request.get_json() or {}
    username = (payload.get("username") or "").strip().lower()
    password = payload.get("password") or ""

    row = get_user(username)
    if not row:
        return jsonify({"valid": False}), 401

    _, _, stored_password = row
    if not check_password_hash(stored_password, password):
        return jsonify({"valid": False}), 401

    return jsonify({"valid": True, "username": username})


if __name__ == "__main__":
    init_db()
    app.run(port=5001, debug=True)
