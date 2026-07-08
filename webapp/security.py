"""
security.py – Login-Status, Rollen und Zugriffsschutz.

Rollen wie im Desktop (modules/auth.py):
  read  – alle dürfen lesen
  write – write + admin
  delete/admin – nur admin
"""

from functools import wraps

from flask import session, redirect, url_for, request, abort


def current_user():
    """Angemeldeter Benutzer als dict {id, username, role} oder None."""
    return session.get("user")


def can(permission: str) -> bool:
    u = current_user()
    if not u:
        return False
    role = u.get("role")
    if permission == "read":
        return True
    if permission == "write":
        return role in ("write", "admin")
    if permission in ("delete", "admin"):
        return role == "admin"
    return False


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("auth.login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper


def require(permission: str):
    """Decorator-Fabrik: schützt eine Route mit einer Berechtigung."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user():
                return redirect(url_for("auth.login", next=request.path))
            if not can(permission):
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return deco
