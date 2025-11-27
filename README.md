# TP Multi-Services Flask + OAuth2

Ce TP transforme l’ancienne application monolithique en une architecture lisible par service. L’objectif est de disposer d’un bac à sable pour expérimenter :

- un **front Flask** réduit à de l’UI, qui joue désormais le rôle de **client OAuth2 PKCE** ;
- une **gateway HTTP** qui devient l’unique façade publique ;
- trois micro-services spécialisés (Auth, User, Orders) faciles à comprendre et à étendre.

## 1. Architecture en un coup d’œil

| Composant         | Port | Rôle                                                                                              |
|-------------------|------|---------------------------------------------------------------------------------------------------|
| Front (`app.py`)  | 8000 | UI Flask, client OAuth2 public (PKCE). Consomme uniquement la Gateway.                            |
| API Gateway       | 5000 | Point d’entrée unique. Valide les tokens via l’Auth Service et proxifie vers User/Orders.         |
| Auth Service      | 5002 | Serveur OAuth2 (Authlib). Vérifie les identifiants via User Service et émet access/refresh tokens.|
| User Service      | 5001 | CRUD minimal sur les utilisateurs (SQLite + PBKDF2).                                              |
| Orders Service    | 5003 | API métier protégée (lecture/écriture de commandes).                                              |

**Flux global** : inscription via la Gateway → connexion OAuth2 (Authorization Code + PKCE) sur l’Auth Service → appels `/orders` avec `Authorization: Bearer <token>` via la Gateway → refresh token direct sur l’Auth Service en cas de 401.

## 2. Installation

```bash
python -m venv env
source env/bin/activate          # Windows : .\env\Scripts\activate
pip install -r requirements.txt
```

Variables d’environnement utiles (facultatives) :

- Backend : `USER_SERVICE_URL`, `ORDERS_SERVICE_URL`, `AUTH_SERVICE_URL`, `JWT_SECRET`, `TOKEN_EXP_MINUTES`, `REFRESH_TOKEN_EXP_MINUTES`…
- Front : `GATEWAY_URL` (par défaut `http://127.0.0.1:5000`), `OAUTH_CLIENT_ID`, `OAUTH_SCOPE`, `OAUTH_REDIRECT_URI`.

## 3. Démarrage des services

Chaque brique peut être lancée dans un terminal dédié :

```bash
python services/user_service/app.py
python services/auth_service/app.py
python services/orders_service/app.py
python services/api_gateway/app.py
python app.py   # front
```

Sur Windows, le helper `scripts/run_stack.ps1` ouvre les consoles automatiquement :

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_stack.ps1 -Services  # user -> auth -> orders -> gateway
powershell -ExecutionPolicy Bypass -File scripts/run_stack.ps1 -Front
```

Le front écoute sur `http://127.0.0.1:8000`. Modifiez `FLASK_RUN_PORT` ou le paramètre `app.run` si besoin.

## 4. Parcours utilisateur (front OAuth2)

1. Aller sur `http://127.0.0.1:8000`.
2. **Inscription** : formulaire → Gateway → User Service (création + hash PBKDF2).
3. **Connexion** : clic “Se connecter” → redirection vers `http://127.0.0.1:5002/oauth/authorize`. Le front génère `code_verifier`/`code_challenge` et enregistre `state` côté session.
4. Après authentification + consentement, l’Auth Service renvoie un `code`. Le front l’échange contre un `access_token` + `refresh_token` via `POST /oauth/token` (grant `authorization_code`).
5. Toute requête métier (`GET/POST /orders`) passe par la Gateway avec le token dans le header `Authorization`.
6. Si la Gateway répond 401, le front appelle `POST /oauth/token` avec `grant_type=refresh_token` pour récupérer un nouveau couple de tokens.

Le seed `alice/passw0rd` est déjà présent dans la base SQLite du User Service pour tester rapidement le flux OAuth2 (utilisé également par `scripts/oauth_client.py`).

## 5. Tester les endpoints REST

La Gateway conserve les endpoints historiques (pratique pour Postman/cURL ou des scripts) :

- `POST /register` : crée un utilisateur.
- `POST /login` : retourne un token “legacy” (non PKCE).
- `POST /refresh` : refresh côté Gateway.
- `GET/POST /orders` : lecture/écriture de commandes.

Exemple minimal :

```bash
curl -X POST http://127.0.0.1:5000/register \
     -H "Content-Type: application/json" \
     -d '{"username":"victor","password":"superpass"}'

LOGIN=$(curl -s -X POST http://127.0.0.1:5000/login \
     -H "Content-Type: application/json" \
     -d '{"username":"victor","password":"superpass"}')
TOKEN=$(echo $LOGIN | jq -r .token)

curl -X POST http://127.0.0.1:5000/orders \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"item":"Livre","quantity":2}'
```

Pour rejouer l’intégralité d’un flux OAuth2 sans passer par l’UI, un script Python est fourni :

```bash
python scripts/oauth_client.py --username alice --password passw0rd
```

Il exécute un Authorization Code + PKCE (avec consentement programmatique) puis un Client Credentials (`orders-cron`).

Cette base permet d’aborder scalabilité (multiplication des instances par service), résilience (timeouts + retries) et patterns modernes d’authentification (OAuth2 / PKCE / Client Credentials) sans se perdre dans une stack trop lourde.
