"""
Ce fichier implémente un API Gateway, c’est-à-dire la porte d’entrée unique des microservices.
Il sert à :
- vérifier l’authentification (via Auth Service),
- router les requêtes vers les microservices internes,
- protéger les services internes contre les appels directs.
"""

from flask import Flask, request, jsonify
import requests

# --- Initialisation de l'API Gateway ---
gateway_app = Flask(__name__)

# --- URLs des Microservices ---
AUTH_SERVICE_URL = "http://auth:5002/auth"
ORDERS_SERVICE_URL = "http://orders:5001"


# ==================================================
#  VALIDATION DU TOKEN (appel Auth Service /validate)
# ==================================================
# Cette fonction vérifie le token JWT via Auth Service
def validate_and_get_user():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, "Token manquant ou mauvais format"

    token = auth_header.split(" ")[1]

    try:
        response = requests.post(
            f"{AUTH_SERVICE_URL}/validate",
            headers={"Authorization": f"Bearer {token}"}
        )

        if response.status_code == 200:
            return response.json().get("user"), None
        else:
            return None, response.json().get("message", "Token invalide.")

    except requests.exceptions.ConnectionError:
        return None, "Auth Service indisponible."



# ==================================================
#  ROUTE PRINCIPALE : /api/orders (POST)
# ==================================================
@gateway_app.route('/api/orders', methods=['POST'])
# cette fonction gère la soumission des commandes via le Gateway
def handle_submit_order():

    # 1. Vérifier le token
    user, error = validate_and_get_user()
    if error:
        return jsonify({"message": f"Accès refusé : {error}"}), 401

    # 2. Récupérer et enrichir le payload
    payload = request.get_json()
    if payload is None:
        return jsonify({"message": "Payload JSON manquant."}), 400

    payload["user"] = user  # sécurité : forcer l'utilisateur du token

    # 3. Envoyer la requête vers Orders Service
    try:
        response = requests.post(
            f"{ORDERS_SERVICE_URL}/orders",
            json=payload
        )

        # 4. Retourner exactement la même réponse au client
        return (
            response.content,
            response.status_code,
            response.headers.items()
        )

    except requests.exceptions.ConnectionError:
        return jsonify({"message": "Orders Service indisponible."}), 503


# ==================================================
#  DEMARRAGE DU GATEWAY
# ==================================================
if __name__ == '__main__':
    print("API Gateway démarrée sur http://localhost:5003")
    gateway_app.run(debug=True, port=5003, host='0.0.0.0')
