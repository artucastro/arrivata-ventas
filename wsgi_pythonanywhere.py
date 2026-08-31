"""
Contenido para el archivo WSGI de PythonAnywhere.

En PythonAnywhere: pestaña Web -> "WSGI configuration file" -> borrar todo y
pegar esto, ajustando USER si tu usuario no es 'artucastro'.
"""
import sys

USER = 'artucastro'
PROJECT = f'/home/{USER}/arrivata-ventas'

if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

# app.py ya hace load_dotenv() apuntando a PROJECT/.env, así que las variables
# (FLASK_SECRET_KEY, APP_USER, APP_PASSWORD, FLASK_DEBUG, ...) se leen de ahí.
from app import app as application  # noqa: E402
