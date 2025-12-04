
# 📄 **README.md — Microservices Auth + Gateway + Orders + Front (Flask)**

# 🛒 Microservices – Architecture complète (Authlib + JWT + API Gateway)

Ce projet implémente une architecture **microservices** simple et pédagogique, composée de :

* **Auth Service** : authentification + Access Token + Refresh Token (Authlib)
* **API Gateway** : point d’entrée unique, vérification des tokens
* **Orders Service** : enregistrement de commandes
* **Front Flask** : interface utilisateur (connexion, choix des produits, achat)

L’objectif est de simuler une architecture distribuée moderne, avec **sécurité**, **communication inter-services**, **gestion des tokens**, et **séparation des responsabilités**.

---

# 🧱 Architecture Globale

```
            [ Client Flask (views.py) ]
                       |
                       | 1. Login / Refresh
                       v
            [ Auth Service (Authlib) ]
                       |
                       | 2. Token (Access + Refresh)
                       v
            [ Client Flask ]
                       |
                       | 3. Appel sécurisé (Bearer <token>)
                       v
            [ API Gateway ]
                       |
                       | 4. Routage sécurisé
                       v
            [ Orders Service ]
                       |
                       | 5. Réponse commande
                       v
            [ Client Flask ]
```

---

# 🔐 Authentification — Authlib (Access Token + Refresh Token)

Le Auth Service utilise **Authlib** pour :

### ✔ signer les *Access Tokens* (valables 30 min)

### ✔ signer les *Refresh Tokens* (valides 7 jours)

### ✔ stocker les refresh tokens en base SQLite

### ✔ valider les tokens via `/auth/validate`

### ✔ permettre le renouvellement via `/auth/refresh`

### Endpoints :

| Méthode | Route            | Description                           |
| ------- | ---------------- | ------------------------------------- |
| POST    | `/auth/register` | Création de compte                    |
| POST    | `/auth/login`    | Retourne access_token + refresh_token |
| POST    | `/auth/validate` | Vérifie un Access Token (Gateway)     |
| POST    | `/auth/refresh`  | Renouvelle un Access Token            |
| POST    | `/auth/logout`   | Supprime le refresh token             |

---

# 🧩 API Gateway — Vérification et Routage

Le Gateway :

### ✔ vérifie le token avec `/auth/validate`

### ✔ bloque les requêtes non authentifiées

### ✔ enrichit la requête avec `user`

### ✔ route la requête vers le Orders Service

Endpoint principal :

| Méthode | Route         | Description          |
| ------- | ------------- | -------------------- |
| POST    | `/api/orders` | Soumission du panier |

---

# 📦 Orders Service — Enregistrement des commandes

Ce service :

✔ reçoit les commandes depuis le Gateway
✔ simule un paiement (80 % réussite)
✔ enregistre les commandes dans `orders.json`
✔ retourne `status=ok` ou `status=error`

Endpoint :

| Méthode | Route     | Description             |
| ------- | --------- | ----------------------- |
| POST    | `/orders` | Enregistre une commande |

---

# 🎨 Front Flask — Interface utilisateur

L'interface utilisateur permet :

* inscription / connexion
* affichage du catalogue
* sélection d’articles
* envoi du panier au Gateway
* gestion automatique du refresh token
  (si l’Access Token expire → renouvellé → commande retentée)

---

# ⚙️ Installation & Lancement

## 1️⃣ Installer les dépendances

Dans chaque service :

```
pip install -r requirements.txt
```

Dépendances principales :

* Flask
* Authlib
* Flask-Bcrypt
* Requests

---

## 2️⃣ Lancer les microservices

### 1. Auth Service (port 5002)

```
python auth_service.py
```

### 2. Orders Service (port 5001)

```
python orders_service.py
```

### 3. Gateway (port 5003)

```
python gateway.py
```

### 4. Application Front Flask (port 5000)

```
python run.py
```

---

# 📁 Structure du projet

```
/project
  ├── auth_service.py
  ├── orders_service.py
  ├── gateway.py
  ├── run.py (front Flask)
  ├── app/
  │    ├── views.py
  │    ├── templates/
  │    │      ├── login.html
  │    │      ├── accueil.html
  │    │      └── achat.html
  ├── users.db
  ├── orders.json
  ├── README.md
  └── requirements.txt
```

---

# 🔍 Fonctionnement détaillé

### ✔ Login

Le client envoie username + password →
Auth Service renvoie :

```json
{
  "access_token": "...",
  "refresh_token": "..."
}
```

### ✔ Appel du Gateway

Le client appelle :

```
Authorization: Bearer <access_token>
POST /api/orders
```

### ✔ Token expiré

Le Gateway retourne 401 ↓
Le front appelle `/auth/refresh` ↓
Récupère un nouveau token ↓
Ré-envoie la commande automatiquement.

---

# 🧪 Tests recommandés

* Test login + récupération des deux tokens
* Test d'accès au Gateway sans token → rejet
* Test token expiré (forcer exp=1 seconde)
* Test du refresh token
* Test suppression refresh token (logout)
* Vérifier l’enregistrement des commandes dans `orders.json`

---

# 🛡️ Sécurité

* Hash des mots de passe : **bcrypt**
* Tokens signés : **Authlib JWT (HS256)**
* Validation centralisée dans `/auth/validate`
* Refresh Tokens stockés en base pour contrôle
* Gateway obligatoire (aucun accès direct aux services internes)

---

# 🎯 Objectif pédagogique

Ce projet permet d'apprendre :

* concepts microservices
* séparation des responsabilités
* REST APIs
* Tokens JWT sécurisés (via Authlib)
* Refresh Tokens
* API Gateway
* communication inter-services
* architecture distribuée

