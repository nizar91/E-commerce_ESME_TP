# TP1 - Architecture Multi-Services

Ce depot illustre le passage d'une application Flask monolithique vers une architecture multi-services. On obtient :

- **Un front Flask (app.py)** : il ne fait plus que servir l'interface HTML et consommer la Gateway.
- **Une Gateway HTTP** : point d'entree unique qui valide les JWT et distribue vers les autres services.
- **Trois services metier** : Auth, User et Orders, chacun avec sa responsabilite propre.

Chaque composant reste volontairement simple (Flask + SQLite/JSON) pour se concentrer sur la separation des roles et la communication via HTTP/JWT.

## Vue d'ensemble

| Service        | Port par defaut | Role principal |
|----------------|-----------------|----------------|
| API Gateway    | 5000            | Point d'entree unique, valide les tokens via le service Auth et route les requetes vers les autres services |
| Auth Service   | 5002            | Gere l'authentification, delegue la verification des identifiants au User Service et genere/valide les JWT |
| User Service   | 5001            | Stocke les profils utilisateurs (SQLite) et expose les operations de creation + verification des mots de passe haches |
| Orders Service | 5003            | Fournit l'API metier protegee (lecture/ecriture de commandes) et attend que la Gateway lui transmette l'utilisateur authentifie |

Flux type :

1. **Inscription** : le client appelle `POST /register` (Gateway) -> la Gateway relaye vers `User Service` pour creer un utilisateur (mot de passe hache PBKDF2).
2. **Connexion** : `POST /login` (Gateway) -> relais vers `Auth Service` -> ce dernier verifie les identifiants aupres du `User Service` puis genere un JWT.
3. **Appel metier** : le client appelle `GET/POST /orders` avec `Authorization: Bearer <token>` -> la Gateway valide le token aupres du `Auth Service`, injecte `X-User` dans la requete et la transmet a `Orders Service`.

## Installation rapide

```bash
python -m venv env
source env/bin/activate            # sous Windows : .\env\Scripts\activate
pip install -r requirements.txt
```

## Demarrer les services
Lancer chaque service dans un terminal dedie (l'ordre n'a pas d'importance, mais la Gateway necessite que les autres soient deja prets) :

```bash
python services/user_service/app.py
python services/auth_service/app.py
python services/orders_service/app.py
python services/api_gateway/app.py
```

> Les ports et URLs des dependances peuvent etre modifies via les variables d'environnement `USER_SERVICE_URL`, `AUTH_SERVICE_URL`, `ORDERS_SERVICE_URL`, `JWT_SECRET`, etc.
> Le service Auth accepte en plus `TOKEN_EXP_MINUTES` et `REFRESH_TOKEN_EXP_MINUTES`.

### Script helper (Windows/PowerShell)
Pour automatiser l'ouverture des consoles :

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_stack.ps1 -Services  # lance user -> auth -> orders -> gateway
powershell -ExecutionPolicy Bypass -File scripts/run_stack.ps1 -Front     # ouvre l'UI Flask
```

Chaque commande ouvre une nouvelle fenetre PowerShell dédiée qui reste attachée au service lancé.

## Lancer le front Flask
Une fois les services operationnels, demarre l'interface (ex-mono, desormais front-only). Elle dialogue exclusivement avec la Gateway :

```bash
python app.py
```

Par defaut elle cible `http://127.0.0.1:5000`. Pour pointer vers une autre instance de gateway, defini `GATEWAY_URL` avant de lancer `app.py`. L'application tourne sur `http://127.0.0.1:8000` (configurable via `FLASK_RUN_PORT` ou en adaptant `app.run`).

### Parcours utilisateur via le front
1. Ouvre `http://127.0.0.1:8000`.
2. Clique sur **Inscription** pour creer un compte (derriere, le front appelle `POST /register` de la Gateway).
3. Connecte-toi : le front recupere un JWT via `POST /login` et le stocke en session.
4. Commande un article depuis la page d'accueil : le front poste sur `POST /orders` via la Gateway, token en header.
5. Consulte **Voir mes commandes** : appel `GET /orders` securise.

Le front conserve aussi le refresh token fourni par le service Auth. Si l'API renvoie `401` parce que le JWT a expire, il appelle automatiquement `POST /refresh` via la Gateway pour obtenir un nouveau duo (access + refresh) sans redemander le mot de passe.

Tous les formulaires HTML passent donc par la Gateway, ce qui permet de presenter la separation front/back lors de la restitution.

## Nouvelle brique Authorization Server (Authlib)
Le service `auth_service` expose maintenant un serveur OAuth2 propulsé par Authlib avec :

- **Authorization Code + PKCE** (client `student-spa`, redirect `http://127.0.0.1:9000/callback`). PKCE est exigé uniquement pour les clients publics (sans secret) afin d'éviter le vol de code d'autorisation.
- **Client Credentials** (client `orders-cron` avec secret `orders-secret`).
- **Ecran de consentement** (template `templates/consent.html`) demandant la connexion puis l'approbation de la portée demandée.
- **Endpoint d'introspection** (`POST /oauth/introspect`) utilisé par la gateway avant de retomber sur l'ancien `/auth/validate`.

Pour tester rapidement sans navigateur, un client Python est fourni :

```bash
python scripts/oauth_client.py --username <user> --password <pwd>
```

Le script réalise un flux Authorization Code + PKCE avec consentement programmatique, puis un flux Client Credentials.

## Utilisation (exemple CURL)

```bash
# 1. Creer un utilisateur
curl -X POST http://127.0.0.1:5000/register \
     -H "Content-Type: application/json" \
     -d '{"username":"victor","password":"superpass"}'

# 2. Obtenir un JWT + refresh token
LOGIN=$(curl -s -X POST http://127.0.0.1:5000/login \
     -H "Content-Type: application/json" \
     -d '{"username":"victor","password":"superpass"}')
TOKEN=$(echo $LOGIN | jq -r .token)
REFRESH=$(echo $LOGIN | jq -r .refresh_token)

# 2bis. Renouveler un JWT grace au refresh token
curl -X POST http://127.0.0.1:5000/refresh \
     -H "Content-Type: application/json" \
     -d "{\"refresh_token\":\"$REFRESH\"}"

# 3. Creer une commande
curl -X POST http://127.0.0.1:5000/orders \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"item":"Livre","quantity":2}'

# 4. Lister les commandes de l'utilisateur authentifie
curl -X GET http://127.0.0.1:5000/orders \
     -H "Authorization: Bearer $TOKEN"
```

## Points a mettre en avant lors de la restitution
- **Responsabilites claires** : chaque service a un perimetre reduit (auth, profils, commandes) et peut evoluer/etre deploye independamment.
- **Securite** : le User Service ne renvoie jamais les mots de passe, seulement des hashes PBKDF2 ; les JWT sont signes cote Auth Service ; la Gateway est le seul point expose et filtre les requetes.
- **Communication inter-services** : tous les echanges se font via HTTP interne (`requests` cote serveur), ce qui facilite l'observabilite et permet d'ajouter du monitoring ou du circuit breaking.
- **Extensibilite** : on peut brancher facilement un client web/mobile sur la Gateway, ou greffer de nouveaux services (ex : catalogue) en conservant le meme mecanisme de validation JWT.

Ce TP fournit ainsi une base pour discuter scalabilite (multiplication des instances par service), resilience (timeouts + gestion d'erreurs deja esquissees) et bonnes pratiques de securite elementaires.
