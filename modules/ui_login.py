"""
ui_login.py – Login-Dialog beim Anwendungsstart.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from modules import database as db
from modules import auth, theme


class LoginDialog(tk.Toplevel):
    """Modaler Login-Dialog. Nach erfolgreichem Login wird auth.set_session() aufgerufen."""

    def __init__(self, parent: tk.Tk):
        super().__init__(parent)
        self.title("Anmelden – Mobilfunkverwaltung")
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._cancelled = False

        self._build_ui()
        theme.center_window(self, 360, 260, parent)

    def _build_ui(self):
        p = theme.current()
        outer = tk.Frame(self, bg=p["bg"], padx=32, pady=24)
        outer.pack(fill="both", expand=True)

        tk.Label(outer, text="Mobilfunkverwaltung",
                 font=("Segoe UI", 13, "bold"),
                 bg=p["bg"], fg=p["fg"]).pack(pady=(0, 4))
        tk.Label(outer, text="Bitte anmelden",
                 font=("Segoe UI", 9), bg=p["bg"],
                 fg=p["fg_dim"]).pack(pady=(0, 16))

        form = ttk.Frame(outer)
        form.pack(fill="x")

        ttk.Label(form, text="Benutzername:").grid(
            row=0, column=0, sticky="e", padx=(0, 8), pady=4)
        self._user_var = tk.StringVar()
        user_entry = ttk.Entry(form, textvariable=self._user_var, width=22)
        user_entry.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="Passwort:").grid(
            row=1, column=0, sticky="e", padx=(0, 8), pady=4)
        self._pass_var = tk.StringVar()
        pass_entry = ttk.Entry(form, textvariable=self._pass_var,
                               show="•", width=22)
        pass_entry.grid(row=1, column=1, sticky="ew", pady=4)
        form.columnconfigure(1, weight=1)

        self._err_var = tk.StringVar()
        err_lbl = tk.Label(outer, textvariable=self._err_var,
                           font=("Segoe UI", 9), bg=p["bg"], fg="#C0392B")
        err_lbl.pack(pady=(8, 0))

        btn_frame = ttk.Frame(outer)
        btn_frame.pack(fill="x", pady=(12, 0))
        ttk.Button(btn_frame, text="Abbrechen",
                   command=self._on_close).pack(side="right", padx=(4, 0))
        ttk.Button(btn_frame, text="Anmelden",
                   command=self._login).pack(side="right")

        user_entry.focus_set()
        user_entry.bind("<Return>", lambda e: pass_entry.focus_set())
        pass_entry.bind("<Return>", lambda e: self._login())

    def _login(self):
        username = self._user_var.get().strip()
        password = self._pass_var.get()
        if not username:
            self._err_var.set("Bitte Benutzernamen eingeben.")
            return
        with db.read_connection() as conn:
            row = db.get_user_by_name(conn, username)
        if not row or not row["active"]:
            self._err_var.set("Benutzername oder Passwort falsch.")
            return
        if not auth.verify_password(password, row["password_hash"]):
            self._err_var.set("Benutzername oder Passwort falsch.")
            return

        session = auth.Session(
            user_id=row["id"],
            username=row["username"],
            role=row["role"],
        )
        auth.set_session(session)

        # Letzten Login-Zeitpunkt aktualisieren
        try:
            from datetime import datetime
            with db.transaction() as conn:
                db.update_user(conn, row["id"], {
                    "last_login": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
        except Exception:
            pass

        # Erstes Login mit Standard-Passwort → Passwort-Änderung erzwingen
        if row["force_pw_change"]:
            if not self._force_change_password(row["id"]):
                auth.set_session(None)
                return

        self.destroy()

    def _force_change_password(self, user_id: int) -> bool:
        """Zeigt Passwort-Änderungsdialog. Gibt True zurück wenn erfolgreich."""
        win = tk.Toplevel(self)
        win.title("Passwort ändern")
        win.resizable(False, False)
        win.grab_set()
        p = theme.current()
        outer = tk.Frame(win, bg=p["bg"], padx=24, pady=20)
        outer.pack(fill="both", expand=True)
        tk.Label(outer, text="Erstes Login – bitte Passwort ändern",
                 font=("Segoe UI", 10, "bold"),
                 bg=p["bg"], fg=p["fg"]).pack(pady=(0, 12))
        form = ttk.Frame(outer)
        form.pack(fill="x")
        ttk.Label(form, text="Neues Passwort:").grid(
            row=0, column=0, sticky="e", padx=(0, 8), pady=4)
        new_var = tk.StringVar()
        new_e = ttk.Entry(form, textvariable=new_var, show="•", width=22)
        new_e.grid(row=0, column=1, sticky="ew")
        ttk.Label(form, text="Wiederholen:").grid(
            row=1, column=0, sticky="e", padx=(0, 8), pady=4)
        rep_var = tk.StringVar()
        ttk.Entry(form, textvariable=rep_var, show="•", width=22).grid(
            row=1, column=1, sticky="ew")
        form.columnconfigure(1, weight=1)
        err_var = tk.StringVar()
        tk.Label(outer, textvariable=err_var, bg=p["bg"],
                 fg="#C0392B", font=("Segoe UI", 9)).pack(pady=(6, 0))
        result = tk.BooleanVar(value=False)

        def _save():
            pw = new_var.get()
            if len(pw) < 6:
                err_var.set("Mindestens 6 Zeichen erforderlich.")
                return
            if pw != rep_var.get():
                err_var.set("Passwörter stimmen nicht überein.")
                return
            try:
                with db.transaction() as conn:
                    db.update_user(conn, user_id, {
                        "password_hash": auth.hash_password(pw),
                        "force_pw_change": 0,
                    })
            except Exception as exc:
                err_var.set(str(exc))
                return
            result.set(True)
            win.destroy()

        btn = ttk.Frame(outer)
        btn.pack(fill="x", pady=(12, 0))
        ttk.Button(btn, text="Speichern", command=_save).pack(side="right")
        new_e.focus_set()
        win.update_idletasks()
        theme.center_window(win, win.winfo_reqwidth(), win.winfo_reqheight(), self)
        win.wait_window()
        return result.get()

    def _on_close(self):
        self._cancelled = True
        self.destroy()

    @property
    def cancelled(self) -> bool:
        return self._cancelled
