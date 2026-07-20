"""
ui_editor.py – Bearbeitungsfenster für einen einzelnen Teilnehmer.

Alle Felder sind beschreibbar. Nur Systemfelder (Zeitstempel, verified) sind read-only.
Datumsfelder werden im Format DD.MM.YYYY angezeigt und eingegeben.
"""

import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

from modules import database as db
from modules import theme
from modules import vodafone_import, syno_import


def _is_valid_gsm(gsm: str) -> bool:
    """Grobe Prüfung: 10–15 Ziffern, optional +/00-Präfix."""
    cleaned = re.sub(r"[\s\-]", "", gsm)
    return bool(re.match(r'^(\+\d{9,14}|\d{10,15})$', cleaned))

# Anzeigereihenfolge und Labels
FIELD_ORDER = [
    ("master_id",      "Master-Nr."),
    ("gsm",            "GSM-Nummer"),
    ("name",           "Name"),
    ("plant",          "Werk (Plant)"),
    ("konto",          "Konto"),
    ("telefon",        "Telefon (alt)"),
    ("tarif",          "Tarif"),
    ("sim_nummer",     "SIM-Seriennummer"),
    ("rahmenvertrag",  "Rahmenvertrag"),
    ("startdatum",     "Erstaktivierung"),
    ("vertragsbeginn", "Vertragsbeginn"),
    ("vertragsende",   "Vertragsende"),
    ("kuendigung",     "Kündigung zu"),
    ("syno",           "Syno-Gerät 1"),
    ("start_syno",     "Syno 1 seit"),
    ("syno2",          "Syno-Gerät 2"),
    ("start_syno2",    "Syno 2 seit"),
    ("bemerkung",      "Bemerkung"),
    ("verified",       "Verifiziert"),
    ("created_at",     "Angelegt am"),
    ("updated_at",     "Zuletzt geändert"),
]

DATE_FIELDS = {"startdatum", "vertragsbeginn", "vertragsende", "kuendigung", "start_syno", "start_syno2"}
# Systemfelder sind read-only; verified wird als Checkbox separat behandelt
ALWAYS_READONLY = {"created_at", "updated_at", "verified"}


def _to_display_date(value: str | None) -> str:
    """Konvertiert YYYY-MM-DD in DD.MM.YYYY für die Anzeige."""
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return value


def _from_display_date(value: str) -> str | None:
    """Konvertiert DD.MM.YYYY zurück in YYYY-MM-DD für die Datenbank."""
    v = value.strip()
    if not v:
        return None
    try:
        return datetime.strptime(v, "%d.%m.%Y").strftime("%Y-%m-%d")
    except ValueError:
        return v  # Rohdaten beibehalten


class EditorWindow(tk.Toplevel):
    """Bearbeitungsfenster für einen Teilnehmer. participant_id=None → Neuanlage."""

    def __init__(self, parent, participant_id: int | None, on_save_callback=None):
        super().__init__(parent)
        self.participant_id = participant_id
        self.on_save_callback = on_save_callback
        self._entries: dict[str, tk.Widget] = {}
        self._is_new = participant_id is None
        self._zur_pruefung_var = tk.BooleanVar(value=False)
        self._pruefung_grund_var = tk.StringVar()

        self.title("Neuer Teilnehmer" if self._is_new else "Teilnehmer bearbeiten")
        self.resizable(True, True)
        self.grab_set()

        self._build_ui()
        self._load_data()
        theme.center_window(self, 560, 710, parent)
        self.bind("<Control-s>", lambda e: self._save())
        self.bind("<Escape>",    lambda e: self.destroy())

    def _build_ui(self):
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)

        p = theme.current()
        canvas = tk.Canvas(frame, borderwidth=0, highlightthickness=0,
                           bg=p["bg"])
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = ttk.Frame(canvas, padding=4)
        canvas_window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_frame_resize(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())

        inner.bind("<Configure>", _on_frame_resize)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        # Mausrad-Scrollen: bind_all nur wenn dieses Fenster fokussiert ist,
        # Unbind beim Verlassen oder Schließen – verhindert Konflikte bei mehreren
        # gleichzeitig offenen Editorfenstern.
        def _scroll(event):
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(-1 * (event.delta // 120), "units")
            except Exception:
                pass

        def _bind_scroll(event=None):
            canvas.bind_all("<MouseWheel>", _scroll)

        def _unbind_scroll(event=None):
            try:
                canvas.unbind_all("<MouseWheel>")
            except Exception:
                pass

        self.bind("<Enter>",   _bind_scroll)
        self.bind("<Leave>",   _unbind_scroll)
        self.bind("<FocusIn>", _bind_scroll)
        self.bind("<Destroy>", _unbind_scroll)

        for row_idx, (field, label) in enumerate(FIELD_ORDER):
            if field == "verified":
                continue  # wird als Checkbox in der Button-Leiste angezeigt

            ttk.Label(inner, text=label + ":", anchor="e", width=20).grid(
                row=row_idx, column=0, sticky="e", padx=(0, 6), pady=3
            )

            p = theme.current()
            if field == "bemerkung":
                widget = tk.Text(inner, height=3, width=38, wrap="word",
                                 background=p["bg_widget"], foreground=p["fg"],
                                 insertbackground=p["fg"],
                                 relief="flat", borderwidth=1,
                                 highlightthickness=1,
                                 highlightbackground=p["border"],
                                 highlightcolor=p["accent"])
                widget.grid(row=row_idx, column=1, sticky="ew", pady=3)
            else:
                widget = ttk.Entry(inner, width=40)
                widget.grid(row=row_idx, column=1, sticky="ew", pady=3)

            if field in ALWAYS_READONLY:
                if isinstance(widget, tk.Text):
                    widget.configure(state="disabled",
                                     background=p["heading_bg"],
                                     foreground=p["fg_dim"])
                else:
                    widget.configure(state="readonly", style="Readonly.TEntry")

            self._entries[field] = widget

        inner.columnconfigure(1, weight=1)

        # Trennlinie + Checkbox "Zur Prüfung vormerken"
        sep_frame = ttk.Frame(self, padding=(12, 4, 12, 0))
        sep_frame.pack(fill="x")
        ttk.Separator(sep_frame, orient="horizontal").pack(fill="x", pady=(0, 6))
        check_row = ttk.Frame(sep_frame)
        check_row.pack(fill="x")
        ttk.Checkbutton(
            check_row,
            text="Zur Prüfung vormerken",
            variable=self._zur_pruefung_var,
        ).pack(side="left")
        ttk.Label(check_row, text="Grund:").pack(side="left", padx=(16, 4))
        ttk.Entry(check_row, textvariable=self._pruefung_grund_var, width=30).pack(side="left", fill="x", expand=True)

        # Buttons
        btn_frame = ttk.Frame(self, padding=(12, 6, 12, 12))
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="Speichern (Strg+S)", style="Accent.TButton",
                   command=self._save).pack(side="right", padx=4)
        ttk.Button(btn_frame, text="Abbrechen (Esc)",   command=self.destroy).pack(side="right")
        if not self._is_new:
            ttk.Button(btn_frame, text="Eintrag löschen", command=self._delete_entry).pack(side="left")
            ttk.Button(btn_frame, text="Historie …",      command=self._show_history).pack(side="left", padx=(8, 0))

        # Einzel-Abgleich: Felder dieses Datensatzes aus einer Export-Datei
        # nachladen (nur ins Formular, gespeichert wird erst über "Speichern")
        import_row = ttk.Frame(self, padding=(12, 0, 12, 8))
        import_row.pack(fill="x")
        ttk.Label(import_row, text="Einzel-Abgleich:", style="Dim.TLabel").pack(side="left")
        ttk.Button(import_row, text="Vodafone …",
                   command=self._import_single_vodafone).pack(side="left", padx=(6, 2))
        ttk.Button(import_row, text="Syno …",
                   command=self._import_single_syno).pack(side="left", padx=2)

    def _load_data(self):
        if self._is_new:
            return  # Felder bleiben leer

        with db.read_connection() as conn:
            row = db.get_participant_by_id(conn, self.participant_id)
        if not row:
            messagebox.showerror("Fehler", "Datensatz nicht gefunden.", parent=self)
            self.destroy()
            return

        # Checkbox + Prüfungsgrund
        self._zur_pruefung_var.set(not row["verified"])
        grund = row["pruefung_grund"] if "pruefung_grund" in row.keys() else None
        self._pruefung_grund_var.set(grund or "")

        for field, _ in FIELD_ORDER:
            if field == "verified":
                continue
            value = row[field] if field in row.keys() else None
            widget = self._entries.get(field)
            if widget is None:
                continue

            if field in DATE_FIELDS:
                display = _to_display_date(value)
            else:
                display = str(value) if value is not None else ""

            if isinstance(widget, tk.Text):
                widget.configure(state="normal")
                widget.delete("1.0", "end")
                widget.insert("1.0", display)
                if field in ALWAYS_READONLY:
                    widget.configure(state="disabled")
            else:
                state = widget.cget("state")
                widget.configure(state="normal")
                widget.delete(0, "end")
                widget.insert(0, display)
                widget.configure(state=state)

    def _save(self):
        updated: dict = {}
        for field, label in FIELD_ORDER:
            if field in ALWAYS_READONLY:
                continue
            widget = self._entries.get(field)
            if widget is None:
                continue

            if isinstance(widget, tk.Text):
                value = widget.get("1.0", "end").strip()
            else:
                value = widget.get().strip()

            if field in DATE_FIELDS:
                value = _from_display_date(value)

            updated[field] = value if value else None

        # Checkbox: Haken = zur Prüfung (verified=0), kein Haken = geprüft (verified=1)
        updated["verified"] = 0 if self._zur_pruefung_var.get() else 1
        updated["pruefung_grund"] = self._pruefung_grund_var.get().strip() or None

        # GSM-Validierung
        gsm = (updated.get("gsm") or "").strip()
        if gsm and not _is_valid_gsm(gsm):
            if not messagebox.askyesno(
                "GSM-Nummer prüfen",
                f"Die GSM-Nummer '{gsm}' sieht ungewöhnlich aus\n"
                "(erwartet: 10–15 Ziffern, ggf. mit +/00-Präfix).\n\n"
                "Trotzdem speichern?",
                parent=self,
            ):
                return

        try:
            with db.transaction() as conn:
                if self._is_new:
                    updated.setdefault("verified", 1)
                    pid = db.insert_participant(conn, updated)
                    db.log_import(conn, "GUI", "INSERT", f"ID={pid} manuell angelegt",
                                  participant_id=pid)
                else:
                    db.update_participant_fields(conn, self.participant_id, updated)
                    db.log_import(
                        conn, "GUI", "EDIT",
                        f"ID={self.participant_id} manuell bearbeitet",
                        participant_id=self.participant_id,
                    )
            if self.on_save_callback:
                self.on_save_callback()
            self.destroy()
        except Exception as exc:
            if "UNIQUE constraint failed: participants.gsm" in str(exc):
                self._show_gsm_conflict(gsm)
            else:
                messagebox.showerror("Fehler beim Speichern", str(exc), parent=self)

    def _show_gsm_conflict(self, gsm: str):
        with db.read_connection() as conn:
            other = conn.execute(
                "SELECT id, name, master_id, plant FROM participants WHERE gsm = ?",
                (gsm,),
            ).fetchone()
        if other:
            besitzer = other["name"] or "(kein Name eingetragen)"
            messagebox.showerror(
                "GSM-Nummer bereits vergeben",
                f"Die GSM-Nummer '{gsm}' gehört bereits zu:\n\n"
                f"  Master-Nr.: {other['master_id'] or '-'}\n"
                f"  Name:       {besitzer}\n"
                f"  Werk:       {other['plant'] or '-'}\n"
                f"  DB-ID:      {other['id']}\n\n"
                "Bitte prüfen, ob es sich um denselben Teilnehmer/dieselbe SIM\n"
                "handelt (dann Einträge zusammenführen) oder eine andere\n"
                "GSM-Nummer verwenden.",
                parent=self,
            )
        else:
            messagebox.showerror(
                "GSM-Nummer bereits vergeben",
                f"Die GSM-Nummer '{gsm}' ist bereits einem anderen Teilnehmer zugeordnet.",
                parent=self,
            )

    def _apply_field_values(self, data: dict):
        """Schreibt gefundene Werte in die Formularfelder (noch nicht gespeichert)."""
        for field, value in data.items():
            widget = self._entries.get(field)
            if widget is None or field in ALWAYS_READONLY:
                continue
            display = _to_display_date(value) if field in DATE_FIELDS else (value or "")
            if isinstance(widget, tk.Text):
                widget.delete("1.0", "end")
                widget.insert("1.0", display)
            else:
                state = widget.cget("state")
                widget.configure(state="normal")
                widget.delete(0, "end")
                widget.insert(0, display)
                widget.configure(state=state)

    def _import_single_vodafone(self):
        gsm = self._entries["gsm"].get().strip()
        if not gsm:
            messagebox.showinfo("Hinweis", "Bitte zuerst eine GSM-Nummer eingeben.", parent=self)
            return
        path = filedialog.askopenfilename(
            parent=self, title="Vodafone-Exportdatei wählen",
            filetypes=[("Excel-Dateien", "*.xlsx *.xls"), ("Alle Dateien", "*.*")],
        )
        if not path:
            return
        try:
            result = vodafone_import.find_by_gsm(path, gsm)
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc), parent=self)
            return
        if not result:
            messagebox.showinfo(
                "Kein Treffer", f"Keine Zeile mit GSM '{gsm}' in der Datei gefunden.",
                parent=self,
            )
            return
        self._apply_field_values(result)
        messagebox.showinfo(
            "Vodafone-Abgleich",
            "Felder wurden mit den Daten aus der Datei aktualisiert.\n"
            "Bitte prüfen und anschließend speichern.",
            parent=self,
        )

    def _import_single_syno(self):
        gsm = self._entries["gsm"].get().strip()
        name = self._entries["name"].get().strip()
        if not gsm and not name:
            messagebox.showinfo(
                "Hinweis", "Bitte zuerst eine GSM-Nummer oder einen Namen eingeben.",
                parent=self,
            )
            return
        path = filedialog.askopenfilename(
            parent=self, title="Syno-Exportdatei wählen",
            filetypes=[("Excel-Dateien", "*.xlsx *.xls"), ("Alle Dateien", "*.*")],
        )
        if not path:
            return
        try:
            result = syno_import.find_by_gsm_or_name(path, gsm, name)
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc), parent=self)
            return
        if not result:
            messagebox.showinfo(
                "Kein Treffer",
                f"Keine passende Zeile für GSM '{gsm or '-'}' / Name '{name or '-'}' gefunden.",
                parent=self,
            )
            return
        self._apply_field_values(result)
        anzahl = 2 if result.get("syno2") else 1
        messagebox.showinfo(
            "Syno-Abgleich",
            f"{anzahl} Gerät(e) aus der Datei übernommen.\n"
            "Bitte prüfen und anschließend speichern.",
            parent=self,
        )

    def _delete_entry(self):
        if not messagebox.askyesno(
            "Eintrag löschen",
            "Diesen Eintrag endgültig löschen?\nDiese Aktion kann nicht rückgängig gemacht werden.",
            icon="warning",
            parent=self,
        ):
            return
        try:
            with db.transaction() as conn:
                db.delete_participant(conn, self.participant_id)
                db.log_import(
                    conn, "GUI", "DELETE",
                    f"ID={self.participant_id} manuell gelöscht",
                    participant_id=self.participant_id,
                )
            if self.on_save_callback:
                self.on_save_callback()
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Fehler beim Löschen", str(exc), parent=self)

    def _show_history(self):
        with db.read_connection() as conn:
            rows = db.get_participant_history(conn, self.participant_id)

        win = tk.Toplevel(self)
        win.title(f"Änderungshistorie – ID {self.participant_id}")
        theme.center_window(win, 700, 360, self)
        frame = ttk.Frame(win, padding=8)
        frame.pack(fill="both", expand=True)

        cols = ("zeitpunkt", "quelle", "aktion", "details")
        tv = ttk.Treeview(frame, columns=cols, show="headings")
        tv.heading("zeitpunkt", text="Zeitpunkt");  tv.column("zeitpunkt", width=140)
        tv.heading("quelle",    text="Quelle");     tv.column("quelle",    width=70)
        tv.heading("aktion",    text="Aktion");     tv.column("aktion",    width=80)
        tv.heading("details",   text="Details");    tv.column("details",   width=380, stretch=True)
        ys = ttk.Scrollbar(frame, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=ys.set)
        tv.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        for r in rows:
            tv.insert("", "end", values=(r["zeitpunkt"], r["quelle"], r["aktion"], r["details"] or ""))

        if not rows:
            tv.insert("", "end", values=("", "", "", "Noch keine Einträge vorhanden."))

        ttk.Button(win, text="Schließen", command=win.destroy).pack(pady=6)
