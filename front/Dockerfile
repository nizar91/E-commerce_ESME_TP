FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie tout le dossier front (y compris le dossier app/)
COPY . .

EXPOSE 5000

# On lance run.py qui est à la racine de /front
CMD ["python", "run.py"]