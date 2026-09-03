"""Gestión de usuarios admin de Arrivata Sales (Arturo, Emmanuel, ...).

Uso:
    python scripts/manage_users.py create <username> [--password PASS]
    python scripts/manage_users.py passwd <username> [--password PASS]
    python scripts/manage_users.py list

Si no se pasa --password, se pide de forma oculta (no queda en el historial
de la terminal ni en logs). Mínimo 8 caracteres.

La contraseña compartida de solo lectura NO se crea acá: es la variable de
entorno VIEWER_PASSWORD en .env (ver .env.example) — no es un usuario de
la tabla `users`.

Corre contra el backend que indique DATABASE_URL (Postgres en producción,
SQLite local si no está seteada) — igual que el resto de los scripts.
"""
import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except Exception:
    pass

from werkzeug.security import generate_password_hash  # noqa: E402

import database as db  # noqa: E402

_MIN_PASSWORD_LEN = 8


def _read_password(cli_value):
    if cli_value:
        if len(cli_value) < _MIN_PASSWORD_LEN:
            sys.exit(f"La contraseña tiene que tener al menos {_MIN_PASSWORD_LEN} caracteres.")
        return cli_value
    pw1 = getpass.getpass("Contraseña: ")
    pw2 = getpass.getpass("Repetí la contraseña: ")
    if pw1 != pw2:
        sys.exit("Las contraseñas no coinciden.")
    if len(pw1) < _MIN_PASSWORD_LEN:
        sys.exit(f"La contraseña tiene que tener al menos {_MIN_PASSWORD_LEN} caracteres.")
    return pw1


def cmd_create(args):
    username = args.username.strip().lower()
    if not username:
        sys.exit("El usuario no puede estar vacío.")
    if db.get_user_by_username(username):
        sys.exit(f"Ya existe un usuario '{username}'. Usá 'passwd' para cambiarle la contraseña.")
    password = _read_password(args.password)
    user_id = db.create_user(username, generate_password_hash(password), role='admin')
    print(f"OK: usuario '{username}' creado (id={user_id}, role=admin).")


def cmd_passwd(args):
    username = args.username.strip().lower()
    if not db.get_user_by_username(username):
        sys.exit(f"No existe un usuario '{username}'. Usá 'create' para darlo de alta.")
    password = _read_password(args.password)
    db.update_user_password(username, generate_password_hash(password))
    print(f"OK: contraseña de '{username}' actualizada.")


def cmd_list(args):
    users = db.list_users()
    if not users:
        print("No hay usuarios todavía. Creá el primero con: "
              "python scripts/manage_users.py create <usuario>")
        return
    print(f"{'ID':<4} {'USUARIO':<20} {'ROL':<8} CREADO")
    for u in users:
        print(f"{u['id']:<4} {u['username']:<20} {u['role']:<8} {u['created_at']}")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    p_create = sub.add_parser('create', help='crear una cuenta admin nueva')
    p_create.add_argument('username')
    p_create.add_argument('--password', help='si no se pasa, se pide de forma oculta')
    p_create.set_defaults(func=cmd_create)

    p_passwd = sub.add_parser('passwd', help='cambiar la contraseña de una cuenta existente')
    p_passwd.add_argument('username')
    p_passwd.add_argument('--password', help='si no se pasa, se pide de forma oculta')
    p_passwd.set_defaults(func=cmd_passwd)

    p_list = sub.add_parser('list', help='listar las cuentas admin')
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    db.init_db()   # crea/migra el esquema (incluida `users`) si hace falta, antes de tocar nada
    args.func(args)


if __name__ == '__main__':
    main()
