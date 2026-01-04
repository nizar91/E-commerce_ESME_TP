
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

## 1️⃣ Déploiement automatisé Docker + AWS

Pour éviter toute machine virtuelle locale, le pipeline repose désormais sur :

1. **Terraform** → provisionne uniquement l’infrastructure AWS (RDS PostgreSQL + SG).
2. **Ansible** → tourne en local (`inventory/inventory.py`) et prépare un fichier `.env` avant de lancer `docker compose up`.
3. **Docker** → exécute les quatre microservices sur ta machine.

### Pré-requis

* Docker Desktop + l’extension `docker compose`.
* Terraform ≥ 1.5, Ansible ≥ 2.15, AWS CLI configuré (`aws configure` ou variables `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`).
* Collection Ansible Docker : `ansible-galaxy collection install -r ansible_ecommerce/requirements.yml`.

### Lancement

```bash
# 1) Initialiser Terraform et définir les identifiants DB (via TF_VAR_db_username / TF_VAR_db_password)
cd terraform
terraform init

# 2) Déploiement complet (depuis la racine du repo)
python deploy.py deploy

# 3) Tester rapidement
python deploy.py test  # effectue un curl http://127.0.0.1:5000
```

Le script `deploy.py` enchaîne `terraform apply` puis `ansible-playbook`, lequel génère `.env` et effectue `docker compose up -d --build`.

### Arrêt / nettoyage

```
python deploy.py destroy  # docker compose down + terraform destroy
```

> ℹ️ Les scripts historiques (`start_all_services.py`, lancement manuel avec `python auth_service.py`, etc.) restent disponibles pour un usage purement local, mais la voie recommandée du TP est le pipeline Terraform → Ansible → Docker décrit ci-dessus.

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
