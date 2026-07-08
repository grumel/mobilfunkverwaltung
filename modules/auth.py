"""
auth.py – Authentifizierung und Session-Verwaltung.

Rollen:
  admin  – alles erlaubt
  write  – lesen + bearbeiten + importieren, kein Löschen/Einstellungen
  read   – nur lesen und exportieren
"""

import hashlib
import hmac
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

ROLES = ("admin", "write", "read")

ROLE_LABELS = {
    "admin": "Administrator",
    "write": "Schreib-Benutzer",
    "read":  "Lese-Benutzer",
}

# Aktive Session (wird nach Login gesetzt)
_session: "Session | None" = None


@dataclass
class Session:
    user_id:  int
    username: str
    role:     str

    def can(self, permission: str) -> bool:
        """
        Berechtigungen:
          read    – alle Rollen
          write   – write + admin
          delete  – nur admin
          admin   – nur admin
        """
        if permission == "read":
            return True
        if permission == "write":
            return self.role in ("write", "admin")
        if permission in ("delete", "admin"):
            return self.role == "admin"
        return False


def current_windows_user() -> str | None:
    """SAM-Anmeldename des aktuell an Windows angemeldeten Benutzers.

    Rein lokal (kein Domänencontroller nötig, funktioniert offline).
    Gibt None zurück, wenn nicht ermittelbar (z. B. Nicht-Windows/Entwicklung).
    """
    try:
        import win32api
        name = win32api.GetUserName()
        return name.strip() or None
    except Exception as exc:
        logger.debug("Windows-Benutzer nicht ermittelbar: %s", exc)
        return os.environ.get("USERNAME") or None


def sso_override_requested() -> bool:
    """True, wenn beim Start Strg gedrückt ist → SSO überspringen, Login-Dialog
    zeigen (Notausstieg für lokale/andere Anmeldung)."""
    try:
        import win32api, win32con
        return bool(win32api.GetAsyncKeyState(win32con.VK_CONTROL) & 0x8000)
    except Exception:
        return False


def get_session() -> "Session | None":
    return _session


def set_session(session: "Session | None") -> None:
    global _session
    _session = session


def hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256 mit zufälligem Salt (stdlib, kein bcrypt nötig)."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return salt.hex() + ":" + key.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, key_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(key_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False
