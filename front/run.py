'''Sert à lancer le serveur Flask.
Comme on importe app depuis le package app, Flask connaît toutes les routes définies dans views.py.'''

from app import app
app.run(debug = True, port=5000, host='0.0.0.0')