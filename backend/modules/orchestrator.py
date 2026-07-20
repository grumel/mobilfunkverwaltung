"""
orchestrator.py – Startlogik der Anwendung.

Verantwortlichkeiten:
- Logging konfigurieren
- Datenbank initialisieren
- Hauptfenster starten
"""

import logging
import sys
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path

from modules import database as db
from modules import settings_store, auth
from modules.paths import DATA_DIR, RESOURCE_DIR
from modules.ui_main import MainWindow


def _check_db_integrity(logger) -> bool:
    """PRAGMA integrity_check – True wenn OK, False bei Korruption."""
    try:
        with db.read_connection() as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if result == "ok":
            logger.info("DB-Integritätsprüfung: OK")
            return True
        logger.error("DB-Integrität fehlerhaft: %s", result)
        return False
    except Exception as exc:
        logger.error("DB-Integritätsprüfung fehlgeschlagen: %s", exc)
        return False


def _auto_backup(logger) -> None:
    """Tägliches Auto-Backup beim Start, falls letztes Backup > 24 h alt ist."""
    backup_dir = db.DB_PATH.parent / "backups"
    if backup_dir.exists():
        existing = sorted(backup_dir.glob(f"{db.DB_PATH.stem}_*.db"))
        if existing:
            mtime = existing[-1].stat().st_mtime
            if datetime.now() - datetime.fromtimestamp(mtime) < timedelta(hours=24):
                logger.info("Auto-Backup: kein Backup nötig (letztes < 24 h).")
                return
    try:
        dest = db.create_backup()
        logger.info("Auto-Backup erstellt: %s", dest)
    except Exception as exc:
        logger.warning("Auto-Backup fehlgeschlagen: %s", exc)


def configure_logging():
    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "mobilfunk.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(log_file), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def start():
    configure_logging()
    logger = logging.getLogger(__name__)

    settings_store.load()
    logger.info("Einstellungen geladen.")

    try:
        db.init_db()
        logger.info("Datenbank bereit.")
    except Exception as exc:
        logger.critical("Datenbankinitialisierung fehlgeschlagen: %s", exc)
        sys.exit(1)

    # Standard-Admin anlegen falls keine Benutzer vorhanden
    db.ensure_default_admin()

    # Auto-Backup (einmal täglich)
    _auto_backup(logger)

    # DB-Integritätsprüfung
    if not _check_db_integrity(logger):
        import tkinter.messagebox as _mb
        root_tmp = tk.Tk()
        root_tmp.withdraw()
        _mb.showerror(
            "Datenbankfehler",
            "Die Datenbank ist möglicherweise beschädigt!\n\n"
            "Bitte prüfe das Log und stelle ggf. ein Backup wieder her.\n"
            "(Backups befinden sich im Ordner 'backups/')",
        )
        root_tmp.destroy()

    root = tk.Tk()
    root.withdraw()

    # Login vor dem Hauptfenster
    from modules.ui_login import LoginDialog
    from modules import theme as _theme
    _theme.apply(root, settings_store.get().get("dark_mode", False))

    # 1) Windows-SSO: angemeldeten Windows-Benutzer automatisch übernehmen
    #    (überspringbar durch gedrückte Strg-Taste beim Start)
    sso_source = None
    if not auth.sso_override_requested():
        win_user = auth.current_windows_user()
        if win_user:
            try:
                with db.read_connection() as conn:
                    urow = db.get_user_by_windows_login(conn, win_user)
            except Exception as exc:
                logger.warning("SSO-Abfrage fehlgeschlagen: %s", exc)
                urow = None
            if urow:
                auth.set_session(auth.Session(
                    user_id=urow["id"], username=urow["username"], role=urow["role"]))
                sso_source = win_user
                logger.info("Windows-SSO: '%s' → App-Benutzer '%s' (Rolle: %s)",
                            win_user, urow["username"], urow["role"])

    # 2) Kein SSO-Treffer → normaler Login-Dialog (lokaler Rückfall)
    if auth.get_session() is None:
        login = LoginDialog(root)
        root.wait_window(login)
    if auth.get_session() is None:
        logger.info("Login abgebrochen – App wird beendet.")
        root.destroy()
        sys.exit(0)
    s = auth.get_session()
    logger.info("Angemeldet als '%s' (Rolle: %s)", s.username, s.role)
    try:
        with db.transaction() as conn:
            if sso_source:
                db.update_user(conn, s.user_id, {
                    "last_login": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
                db.log_audit(conn, s.user_id, s.username, "LOGIN_SSO",
                             f"Windows-SSO als '{sso_source}' (Rolle: {s.role})")
            else:
                db.log_audit(conn, s.user_id, s.username, "LOGIN",
                             f"Anmeldung erfolgreich (Rolle: {s.role})")
    except Exception as exc:
        logger.warning("Audit-Login-Eintrag fehlgeschlagen: %s", exc)

    # Lock-Datei setzen (Schutz bei OneDrive / Netzwerk-Ablage)
    import tkinter.messagebox as _mb
    lock_info = db.acquire_lock(s.username)
    if lock_info:
        other   = lock_info.get("benutzer", "?")
        host    = lock_info.get("rechner",  "?")
        since   = lock_info.get("seit",     "?")
        proceed = _mb.askyesno(
            "Datenbank bereits geöffnet",
            f"Die Datenbank wird möglicherweise gerade von\n\n"
            f"  Benutzer:  {other}\n"
            f"  Rechner:   {host}\n"
            f"  Seit:      {since}\n\n"
            f"verwendet.\n\n"
            f"Gleichzeitiges Speichern kann zu Datenverlust führen.\n\n"
            f"Trotzdem öffnen?",
        )
        if not proceed:
            logger.info("Start abgebrochen – DB bereits von '%s' geöffnet.", other)
            root.destroy()
            sys.exit(0)
        db._write_lock(s.username)
        logger.warning("Lock übernommen trotz aktivem Lock von '%s' (%s).", other, host)

    def _on_close():
        db.release_lock()
        logger.info("Lock freigegeben. App wird beendet.")
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_close)

    # Fenster-Icon setzen
    icon_path = RESOURCE_DIR / "assets" / "icon.ico"
    if icon_path.exists():
        try:
            root.iconbitmap(str(icon_path))
        except Exception as exc:
            logger.warning("Icon konnte nicht gesetzt werden: %s", exc)

    try:
        app = MainWindow(root)
    except Exception as exc:
        logger.critical("Fehler beim Aufbau des Hauptfensters: %s", exc, exc_info=True)
        db.release_lock()
        sys.exit(1)

    root.deiconify()
    root.mainloop()
