'''Ce fichier implémente le microservice Orders, qui :

- reçoit les commandes uniquement depuis le Gateway (et jamais directement depuis le client final),
- simule un paiement (réussite 80% du temps),
- enregistre les commandes dans un fichier JSON qui sert de petite base de données,
- renvoie le statut au Gateway.'''

# orders_service.py
from flask import Flask, request, jsonify
import json
import datetime
import random
import os

# --- 1. Initialisation de l'API ---
orders_app = Flask(__name__)

# --- Configuration des fichiers de données ---
DATA_DIR = 'data'
ORDERS_FILE = os.path.join(DATA_DIR, 'orders.json')
DEFAULT_ORDERS = {}

# --- Fonctions de gestion des fichiers JSON (Base de données du service) ---

def load_data(filename):
    """Charge les données depuis un fichier JSON donné."""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {} 
    except json.JSONDecodeError:
        return {}

def save_data(data, filename):
    """Sauvegarde les données dans un fichier JSON donné."""
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def initialize_orders_file():
    """Ensure the data directory and orders.json exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(ORDERS_FILE):
        print(f"Création initiale de {ORDERS_FILE} pour Orders Service...")
        save_data(DEFAULT_ORDERS, ORDERS_FILE)

initialize_orders_file()


# --- ROUTE : API pour soumettre une commande (POST /orders) ---
# NOTE: Cette route est exposée au Gateway, PAS au client final.
@orders_app.route('/orders', methods=['POST'])
def create_order():
    # Mouchard 1 : Voir si la requête arrive
    print("Requête reçue au Orders Service.")
    # 1. Le Gateway nous a déjà passé les données et a validé le token
    data = request.get_json()
    user = data.get('user')
    cart_items = data.get('items', [])
    
    if not user or not cart_items:
        # Erreur si les données envoyées par le Gateway sont incomplètes
        return jsonify({"message": "Données de commande manquantes.", "status": "error"}), 400
    
    # 2. Logique de paiement et d'enregistrement (Remplacement de process_payment)
    total_amount = round(sum(item['total_price'] for item in cart_items), 2)
    
    # Simuler un succès 4 fois sur 5
    if random.random() < 0.8:
        # PAIEMENT RÉUSSI (et Enregistrement)
        try:
            #Mouchard 2 : Ou suis-je et ou j'écris ?
            cwd = os.getcwd()
            abs_path = os.path.abspath(ORDERS_FILE)
            print(f"--- TENTATIVE ECRITURE ---")
            print(f"Dossier actuel : {cwd}")
            print(f"Chemin fichier cible : {abs_path}")

            orders_data = load_data(ORDERS_FILE)
            
            if user not in orders_data:
                 orders_data[user] = []
            
            # Créer la nouvelle commande
            new_order = {
                "order_id": str(datetime.datetime.now().timestamp()).replace('.', ''), 
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total": total_amount,
                "items": cart_items 
            }
            
            orders_data[user].append(new_order)
            save_data(orders_data, ORDERS_FILE)

            print(f"--- ECRITURE SUCCES ---") # Confirmation
            
            return jsonify({
                "message": "Commande enregistrée.",
                "status": "ok",
                "order_id": new_order["order_id"]
            }, 201)
            
        except Exception as e:
            print(f"Erreur d'enregistrement JSON: {e}")
            return jsonify({"message": "Erreur d'enregistrement interne.", "status": "error"}, 500)
        
    else:
        # PAIEMENT ÉCHOUÉ (Simulé)
        return jsonify({"message": "Paiement rejeté (simulé).", "status": "error"}, 200)

if __name__ == '__main__':
    # Le Orders Service s'exécute sur le port 5001
    print("Orders Service démarré sur http://localhost:5001")
    orders_app.run(debug=True, port=5001, host='0.0.0.0')
