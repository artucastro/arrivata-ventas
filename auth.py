"""Autenticación de Arrivata Sales.

Reemplaza el login HTTP Basic compartido (APP_USER/APP_PASSWORD) por sesiones
de Flask-Login con dos roles:

  'admin'  -> cuenta individual (usuario + contraseña propios, hasheada con
              werkzeug). Acceso completo. Se crean con scripts/manage_users.py
              (tabla `users`).
  'viewer' -> una única contraseña compartida (env VIEWER_PASSWORD), sin
              usuario ni fila en la tabla `users` — repartida a mano por
              Arturo a quien corresponda. Solo lectura: nunca pasa las
              validaciones de @admin_required.

Ver database.py (create_user / get_user_by_username / get_user_by_id /
list_users / update_user_password) para el CRUD de la tabla `users`, y
migrations/004_add_users.sql para el esquema.
"""
import hmac
import os
from functools import wraps

from flask import abort
from flask_login import LoginManager, UserMixin, current_user

import database as db

VIEWER_PASSWORD = os.environ.get("VIEWER_PASSWORD", "").strip()

# Id de sesión sintético del rol de solo lectura (no es una fila de `users`).
_VIEWER_ID = "viewer"


class User(UserMixin):
    """Wrapper liviano sobre una fila de `users`, o el usuario sintético de
    solo lectura. `id` viaja como string en la sesión (así lo maneja
    Flask-Login) — get_user_by_id() en database.py lo vuelve a castear."""

    def __init__(self, id, username, role):
        self.id = str(id)
        self.username = username
        self.role = role

    @property
    def is_admin(self) -> bool:
        return self.role == 'admin'


VIEWER_USER = User(_VIEWER_ID, "Solo lectura", "viewer")

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Iniciá sesión para continuar."
login_manager.login_message_category = "info"


@login_manager.user_loader
def load_user(user_id):
    if user_id == _VIEWER_ID:
        return VIEWER_USER
    row = db.get_user_by_id(user_id)
    if not row:
        return None
    return User(row['id'], row['username'], row['role'])


def authenticate(username: str, password: str):
    """Login admin (usuario + contraseña propios). None si no matchea."""
    from werkzeug.security import check_password_hash
    row = db.get_user_by_username(username)
    if not row or not check_password_hash(row['password_hash'], password):
        return None
    return User(row['id'], row['username'], row['role'])


def authenticate_viewer(password: str):
    """Login de solo lectura (contraseña única compartida). None si no matchea
    o si VIEWER_PASSWORD no está configurada."""
    if not VIEWER_PASSWORD or not password:
        return None
    if hmac.compare_digest(password, VIEWER_PASSWORD):
        return VIEWER_USER
    return None


def admin_required(view):
    """Para las rutas de escritura: 403 si no hay sesión admin. El gate de
    'hace falta estar logueado' para TODO lo demás ya lo pone
    app._require_login() (before_request); esto es la capa extra de rol."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped
