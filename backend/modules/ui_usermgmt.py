"""
ui_usermgmt.py – Benutzerverwaltung (nur für Admins).
"""

import tkinter as tk
from tkinter import ttk, messagebox

from modules import database as db
from modules import auth, theme
from modules.auth import ROLE_LABELS


class UserManagementDialog(tk.Toplevel):

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Benutzerverwaltung")
        theme.center_window(self, 680, 420, parent)
        self.resizable(True, True)
        self.grab_set()
        self._build_ui()
        self._load()

    def _build_ui(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)

        tv_frame = ttk.Frame(frame)
        tv_frame.pack(fill="both", expand=True)

        cols = [
            ("username",      "Benutzername",  150),
            ("role",          "Rolle",         140),
            ("windows_login", "Windows-Login", 130),
            ("active",        "Aktiv",          50),
            ("last_login",    "Letzter Login", 140),
            ("created_at",    "Angelegt",      130),
        ]
        self._tv = ttk.Treeview(tv_frame,
                                columns=[c[0] for c in cols],
                                show="headings", selectmode="browse")
        for col_id, heading, width in cols:
            self._tv.heading(col_id, text=heading)
            self._tv.column(col_id, width=width, minwidth=40)
        ys = ttk.Scrollbar(tv_frame, orient="vertical", command=self._tv.yview)
        self._tv.configure(yscrollcommand=ys.set)
        self._tv.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        tv_frame.rowconfigure(0, weight=1)
        tv_frame.columnconfigure(0, weight=1)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=(8, 0))
        ttk.Button(btn_frame, text="+ Neuer Benutzer",
                   command=self._new_user).pack(side="left")
        ttk.Button(btn_frame, text="Bearbeiten",
                   command=self._edit_user).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Passwort ändern",
                   command=self._change_pw).pack(side="left")
        ttk.Button(btn_frame, text="Deaktivieren / Aktivieren",
                   command=self._toggle_active).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Löschen",
                   command=self._delete_user).pack(side="left")
        ttk.Button(btn_frame, text="Schließen",
                   command=self.destroy).pack(side="right")

        self._tv.bind("<Double-1>", lambda e: self._edit_user())

    def _load(self):
        self._tv.delete(*self._tv.get_children())
        with db.read_connection() as conn:
            rows = db.get_all_users(conn)
        for row in rows:
            wl = row["windows_login"] if "windows_login" in row.keys() else None
            self._tv.insert("", "end", iid=str(row["id"]), values=(
                row["username"],
                ROLE_LABELS.get(row["role"], row["role"]),
                wl or "–",
                "Ja" if row["active"] else "Nein",
                row["last_login"] or "–",
                row["created_at"],
            ))

    def _selected_id(self) -> int | None:
        sel = self._tv.selection()
        return int(sel[0]) if sel else None

    def _new_user(self):
        _UserEditDialog(self, user_id=None, on_save=self._load)

    def _edit_user(self):
        uid = self._selected_id()
        if uid is None:
            messagebox.showinfo("Hinweis", "Bitte einen Benutzer auswählen.",
                                parent=self)
            return
        _UserEditDialog(self, user_id=uid, on_save=self._load)

    def _change_pw(self):
        uid = self._selected_id()
        if uid is None:
            messagebox.showinfo("Hinweis", "Bitte einen Benutzer auswählen.",
                                parent=self)
            return
        _ChangePasswordDialog(self, user_id=uid)

    def _toggle_active(self):
        uid = self._selected_id()
        if uid is None:
            return
        session = auth.get_session()
        if session and session.user_id == uid:
            messagebox.showwarning("Hinweis",
                                   "Das eigene Konto kann nicht deaktiviert werden.",
                                   parent=self)
            return
        with db.read_connection() as conn:
            row = db.get_user_by_id(conn, uid)
        if not row:
            return
        new_val = 0 if row["active"] else 1
        with db.transaction() as conn:
            db.update_user(conn, uid, {"active": new_val})
            s = auth.get_session()
            db.log_audit(conn, s.user_id, s.username,
                         "USER_TOGGLE",
                         f"Benutzer '{row['username']}' → aktiv={new_val}")
        self._load()

    def _delete_user(self):
        uid = self._selected_id()
        if uid is None:
            return
        session = auth.get_session()
        if session and session.user_id == uid:
            messagebox.showwarning("Hinweis",
                                   "Das eigene Konto kann nicht gelöscht werden.",
                                   parent=self)
            return
        with db.read_connection() as conn:
            row = db.get_user_by_id(conn, uid)
        if not messagebox.askyesno(
            "Benutzer löschen",
            f"Benutzer '{row['username']}' wirklich löschen?\n"
            "Audit-Log-Einträge bleiben erhalten.",
            icon="warning", parent=self,
        ):
            return
        with db.transaction() as conn:
            db.delete_user(conn, uid)
            s = auth.get_session()
            db.log_audit(conn, s.user_id, s.username,
                         "USER_DELETE", f"Benutzer '{row['username']}' gelöscht")
        self._load()


class _UserEditDialog(tk.Toplevel):

    def __init__(self, parent, user_id: int | None, on_save):
        super().__init__(parent)
        self._user_id = user_id
        self._on_save = on_save
        self._is_new = user_id is None
        self.title("Neuer Benutzer" if self._is_new else "Benutzer bearbeiten")
        self.resizable(False, False)
        self.grab_set()
        self._build_ui()
        if not self._is_new:
            self._load()
        theme.center_window(self, 400, 360, parent)

    def _build_ui(self):
        p = theme.current()
        outer = ttk.Frame(self, padding=20)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Benutzername:").grid(
            row=0, column=0, sticky="e", padx=(0, 8), pady=6)
        self._name_var = tk.StringVar()
        ttk.Entry(outer, textvariable=self._name_var, width=24).grid(
            row=0, column=1, sticky="ew")

        ttk.Label(outer, text="Rolle:").grid(
            row=1, column=0, sticky="e", padx=(0, 8), pady=6)
        self._role_var = tk.StringVar(value="read")
        role_combo = ttk.Combobox(
            outer, textvariable=self._role_var,
            values=[f"{r} – {ROLE_LABELS[r]}" for r in auth.ROLES],
            state="readonly", width=23,
        )
        role_combo.grid(row=1, column=1, sticky="ew")

        # Windows-Anmeldename für automatische Anmeldung (SSO)
        ttk.Label(outer, text="Windows-Login:").grid(
            row=2, column=0, sticky="e", padx=(0, 8), pady=6)
        win_row = ttk.Frame(outer)
        win_row.grid(row=2, column=1, sticky="ew")
        win_row.columnconfigure(0, weight=1)
        self._winlogin_var = tk.StringVar()
        ttk.Entry(win_row, textvariable=self._winlogin_var).grid(
            row=0, column=0, sticky="ew")
        ttk.Button(win_row, text="Aktueller",
                   command=lambda: self._winlogin_var.set(
                       auth.current_windows_user() or "")).grid(row=0, column=1, padx=(4, 0))

        r = 3
        if self._is_new:
            ttk.Label(outer, text="Passwort:").grid(
                row=r, column=0, sticky="e", padx=(0, 8), pady=6)
            self._pw_var = tk.StringVar()
            ttk.Entry(outer, textvariable=self._pw_var,
                      show="•", width=24).grid(row=r, column=1, sticky="ew")
            ttk.Label(outer, text="Wiederholen:").grid(
                row=r + 1, column=0, sticky="e", padx=(0, 8), pady=6)
            self._pw2_var = tk.StringVar()
            ttk.Entry(outer, textvariable=self._pw2_var,
                      show="•", width=24).grid(row=r + 1, column=1, sticky="ew")
            ttk.Label(outer, text="(bei reinem Windows-Login leer lassen)",
                      style="Dim.TLabel").grid(row=r + 2, column=1, sticky="w")
            r += 3

        ttk.Label(outer, text="Aktiv:").grid(
            row=r, column=0, sticky="e", padx=(0, 8), pady=6)
        self._active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(outer, variable=self._active_var).grid(
            row=r, column=1, sticky="w")

        outer.columnconfigure(1, weight=1)

        self._err_var = tk.StringVar()
        tk.Label(outer, textvariable=self._err_var,
                 fg="#C0392B", bg=p["bg"],
                 font=("Segoe UI", 9)).grid(
            row=r + 1, column=0, columnspan=2, pady=(4, 0))

        btn = ttk.Frame(outer)
        btn.grid(row=r + 2, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btn, text="Abbrechen",
                   command=self.destroy).pack(side="right", padx=(4, 0))
        ttk.Button(btn, text="Speichern",
                   command=self._save).pack(side="right")

    def _load(self):
        with db.read_connection() as conn:
            row = db.get_user_by_id(conn, self._user_id)
        if not row:
            self.destroy()
            return
        self._name_var.set(row["username"])
        self._active_var.set(bool(row["active"]))
        role = row["role"]
        self._role_var.set(f"{role} – {ROLE_LABELS.get(role, role)}")
        wl = row["windows_login"] if "windows_login" in row.keys() else None
        self._winlogin_var.set(wl or "")

    def _save(self):
        name = self._name_var.get().strip()
        if not name:
            self._err_var.set("Benutzername darf nicht leer sein.")
            return
        role_raw = self._role_var.get().split(" – ")[0].strip()
        if role_raw not in auth.ROLES:
            self._err_var.set("Ungültige Rolle.")
            return
        active = 1 if self._active_var.get() else 0
        winlogin = self._winlogin_var.get().strip() or None

        try:
            if self._is_new:
                pw = self._pw_var.get()
                if pw or not winlogin:
                    # Passwort ist Pflicht, außer es wird ein Windows-Login hinterlegt
                    if len(pw) < 6:
                        self._err_var.set("Mindestens 6 Zeichen erforderlich "
                                          "(oder Windows-Login angeben).")
                        return
                    if pw != self._pw2_var.get():
                        self._err_var.set("Passwörter stimmen nicht überein.")
                        return
                    pw_hash = auth.hash_password(pw)
                else:
                    # Reiner SSO-Benutzer: unbenutzbares Zufalls-Passwort setzen
                    import os
                    pw_hash = auth.hash_password(os.urandom(24).hex())
                with db.transaction() as conn:
                    uid = db.create_user(conn, {
                        "username":      name,
                        "password_hash": pw_hash,
                        "role":          role_raw,
                        "active":        active,
                        "force_pw_change": 0,
                        "windows_login": winlogin,
                    })
                    s = auth.get_session()
                    db.log_audit(conn, s.user_id, s.username,
                                 "USER_CREATE",
                                 f"Neuer Benutzer '{name}' Rolle={role_raw} "
                                 f"Windows-Login={winlogin or '-'}")
            else:
                with db.transaction() as conn:
                    db.update_user(conn, self._user_id, {
                        "username":      name,
                        "role":          role_raw,
                        "active":        active,
                        "windows_login": winlogin,
                    })
                    s = auth.get_session()
                    db.log_audit(conn, s.user_id, s.username,
                                 "USER_EDIT",
                                 f"Benutzer ID={self._user_id} → name={name} "
                                 f"role={role_raw} Windows-Login={winlogin or '-'}")
        except Exception as exc:
            self._err_var.set(str(exc))
            return

        self._on_save()
        self.destroy()


class _ChangePasswordDialog(tk.Toplevel):

    def __init__(self, parent, user_id: int):
        super().__init__(parent)
        self._user_id = user_id
        self.title("Passwort ändern")
        self.resizable(False, False)
        self.grab_set()
        self._build_ui()
        theme.center_window(self, 320, 220, parent)

    def _build_ui(self):
        p = theme.current()
        outer = ttk.Frame(self, padding=20)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Neues Passwort:").grid(
            row=0, column=0, sticky="e", padx=(0, 8), pady=6)
        self._pw_var = tk.StringVar()
        new_e = ttk.Entry(outer, textvariable=self._pw_var,
                          show="•", width=22)
        new_e.grid(row=0, column=1, sticky="ew")

        ttk.Label(outer, text="Wiederholen:").grid(
            row=1, column=0, sticky="e", padx=(0, 8), pady=6)
        self._pw2_var = tk.StringVar()
        ttk.Entry(outer, textvariable=self._pw2_var,
                  show="•", width=22).grid(row=1, column=1, sticky="ew")

        outer.columnconfigure(1, weight=1)

        self._err_var = tk.StringVar()
        tk.Label(outer, textvariable=self._err_var,
                 fg="#C0392B", bg=p["bg"],
                 font=("Segoe UI", 9)).grid(
            row=2, column=0, columnspan=2, pady=(4, 0))

        btn = ttk.Frame(outer)
        btn.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btn, text="Abbrechen",
                   command=self.destroy).pack(side="right", padx=(4, 0))
        ttk.Button(btn, text="Speichern",
                   command=self._save).pack(side="right")
        new_e.focus_set()

    def _save(self):
        pw = self._pw_var.get()
        if len(pw) < 6:
            self._err_var.set("Mindestens 6 Zeichen erforderlich.")
            return
        if pw != self._pw2_var.get():
            self._err_var.set("Passwörter stimmen nicht überein.")
            return
        try:
            with db.transaction() as conn:
                db.update_user(conn, self._user_id, {
                    "password_hash":  auth.hash_password(pw),
                    "force_pw_change": 0,
                })
                s = auth.get_session()
                db.log_audit(conn, s.user_id, s.username,
                             "PW_CHANGE",
                             f"Passwort für User ID={self._user_id} geändert")
        except Exception as exc:
            self._err_var.set(str(exc))
            return
        messagebox.showinfo("Gespeichert", "Passwort wurde geändert.",
                            parent=self)
        self.destroy()
