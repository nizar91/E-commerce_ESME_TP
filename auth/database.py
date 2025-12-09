import sqlite3
from flask_bcrypt import Bcrypt

# Nom du fichier de la base de données SQLite
DATABASE_NAME = 'users.db'

# Initialisation de Bcrypt (doit être initialisé avec l'application Flask)
# Dans ce module, on le définit comme None et on le passe par initialisation.
bcrypt = None 

def init_db(app):
    """Initialise Bcrypt et crée la table des utilisateurs si elle n'existe pas."""
    global bcrypt
    # 1. Initialiser Flask-Bcrypt
    bcrypt = Bcrypt(app)
    
    # 2. Créer la table si elle n'existe pas
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # La table 'users' stocke l'username et le HASH du mot de passe
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def get_db_connection():
    """Crée et retourne une connexion à la base de données."""
    conn = sqlite3.connect(DATABASE_NAME)
    # Permet d'accéder aux colonnes par leur nom (comme un dictionnaire)
    conn.row_factory = sqlite3.Row
    return conn

# --- Fonctions CRUD pour les utilisateurs ---

def add_user(username, password):
    """Ajoute un nouvel utilisateur avec mot de passe haché."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Hacher le mot de passe avant de l'enregistrer
    # Le .decode('utf-8') est nécessaire car generate_password_hash retourne des bytes
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)", 
            (username, hashed_password)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Erreur si l'utilisateur existe déjà (UNIQUE NOT NULL constraint)
        return False
    finally:
        conn.close()

def get_user_by_username(username):
    """Récupère un utilisateur (username et hash) par son nom."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT username, password_hash FROM users WHERE username = ?", 
        (username,)
    )
    user = cursor.fetchone()
    conn.close()
    return user # Retourne un objet Row ou None

def check_password(hashed_password, password):
    """Vérifie le mot de passe non haché avec le hash stocké."""
    # S'assurer que bcrypt est initialisé
    if bcrypt is None:
        raise RuntimeError("Bcrypt non initialisé. Appeler init_db(app) d'abord.")
        
    # La fonction check_password_hash gère la comparaison des hashes de manière sécurisée
    # Il faut encoder le hash stocké en bytes pour la comparaison
    return bcrypt.check_password_hash(hashed_password.encode('utf-8'), password)
