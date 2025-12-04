# Image Python
FROM python:3.9-slim

# Dossier de travail dans le conteneur
WORKDIR /app

# Installation des dépendances système nécessaires
RUN apt-get update && apt-get install -y curl build-essential

# Copie des dépendances et installation
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code
COPY . .

EXPOSE 5002

# Commande de lancement
CMD ["python", "auth_service.py"]