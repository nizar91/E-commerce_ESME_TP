'''Crée l’objet Flask.
Importe les routes définies dans views.py.
Cette structure permet de séparer logique de l’application et exécution.'''

from flask import Flask
app= Flask(__name__)
from app import views