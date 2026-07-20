"""
ui_settings.py – Einstellungsdialog der Mobilfunkverwaltung.

Tabs:
  1. Werk-Konto-Zuordnung  – bearbeitbare Tabelle
  2. Vodafone-Spalten      – Spaltenindizes für den Vodafone-Import
  3. Syno-Spalten          – Spaltenindizes für den Syno-Import
  4. Hilfe                 – Kurzdokumentation
"""

import tkinter as tk
from tkinter import ttk, messagebox
import copy

from modules import settings_store, theme


def _col_letter(idx: int) -> str:
    """Wandelt 0-basierten Spaltenindex in Excel-Buchstaben um (0→A, 25→Z, 26→AA …)."""
    result = ""
    idx += 1
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        result = chr(65 + rem) + result
    return result


# ---------------------------------------------------------------------------
# Hauptdialog
# ---------------------------------------------------------------------------

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Einstellungen")
        theme.center_window(self, 720, 540, parent)
        self.minsize(600, 420)
        self.grab_set()
        self.resizable(True, True)

        # Lokale Kopie; wird erst beim Speichern übernommen
        self._data = copy.deepcopy(settings_store.get())

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=(8, 0))

        nb.add(self._build_konto_plant(nb),    text="Werk-Konto")
        nb.add(self._build_voda_columns(nb),   text="Vodafone-Spalten")
        nb.add(self._build_syno_columns(nb),   text="Syno-Spalten")
        nb.add(self._build_help(nb),           text="Hilfe")

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=8, pady=8)
        ttk.Button(btn_frame, text="Speichern", command=self._save).pack(side="right", padx=4)
        ttk.Button(btn_frame, text="Abbrechen", command=self.destroy).pack(side="right")

    # ------------------------------------------------------------------
    # Tab 1: Werk-Konto-Zuordnung
    # ------------------------------------------------------------------

    def _build_konto_plant(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=10)

        ttk.Label(frame, text=(
            "Ordnet Kontonummern den Werken zu. Wird beim Vodafone-Import\n"
            "zur Plausibilitätsprüfung und zur automatischen Werk-Ableitung verwendet."
        ), justify="left", foreground="gray").pack(anchor="w", pady=(0, 8))

        tv_frame = ttk.Frame(frame)
        tv_frame.pack(fill="both", expand=True)

        cols = ("konto", "plant")
        self._tv_kp = ttk.Treeview(tv_frame, columns=cols, show="headings",
                                    selectmode="browse")
        self._tv_kp.heading("konto", text="Kontonummer")
        self._tv_kp.heading("plant", text="Werk")
        self._tv_kp.column("konto", width=160)
        self._tv_kp.column("plant", width=200)

        ys = ttk.Scrollbar(tv_frame, orient="vertical", command=self._tv_kp.yview)
        self._tv_kp.configure(yscrollcommand=ys.set)
        self._tv_kp.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")

        self._tv_kp.bind("<Double-1>", lambda e: self._edit_konto_plant())

        btn = ttk.Frame(frame)
        btn.pack(fill="x", pady=(6, 0))
        ttk.Button(btn, text="Hinzufügen",   command=self._add_konto_plant).pack(side="left", padx=2)
        ttk.Button(btn, text="Bearbeiten",   command=self._edit_konto_plant).pack(side="left", padx=2)
        ttk.Button(btn, text="Löschen",      command=self._del_konto_plant).pack(side="left", padx=2)

        self._refresh_kp_table()
        return frame

    def _refresh_kp_table(self):
        self._tv_kp.delete(*self._tv_kp.get_children())
        for konto, plant in sorted(self._data["konto_plant"].items(),
                                   key=lambda x: x[1]):
            self._tv_kp.insert("", "end", iid=konto, values=(konto, plant))

    def _add_konto_plant(self):
        _KontoPlantDialog(self, "", "", self._on_kp_save)

    def _edit_konto_plant(self):
        sel = self._tv_kp.selection()
        if not sel:
            return
        konto = sel[0]
        plant = self._data["konto_plant"].get(konto, "")
        _KontoPlantDialog(self, konto, plant, self._on_kp_save, edit_konto=konto)

    def _del_konto_plant(self):
        sel = self._tv_kp.selection()
        if not sel:
            return
        konto = sel[0]
        plant = self._data["konto_plant"].get(konto, "")
        if messagebox.askyesno("Löschen",
                               f"Konto {konto} ({plant}) wirklich entfernen?",
                               parent=self):
            del self._data["konto_plant"][konto]
            self._refresh_kp_table()

    def _on_kp_save(self, old_konto: str, new_konto: str, plant: str):
        if old_konto and old_konto != new_konto:
            del self._data["konto_plant"][old_konto]
        self._data["konto_plant"][new_konto] = plant
        self._refresh_kp_table()

    # ------------------------------------------------------------------
    # Tab 2: Vodafone-Spalten
    # ------------------------------------------------------------------

    def _build_voda_columns(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=10)

        ttk.Label(frame, text=(
            "Spaltenindizes (0-basiert) in der Vodafone-Exportdatei.\n"
            "Spalte A = 0, B = 1, C = 2 … M = 12 usw."
        ), justify="left", foreground="gray").pack(anchor="w", pady=(0, 12))

        VODA_FIELDS = [
            ("konto",          "Konto (Kundennummer)"),
            ("gsm",            "GSM / Teilnehmernummer"),
            ("rahmenvertrag",  "Rahmenvertragsnummer"),
            ("sim",            "SIM-Seriennummer"),
            ("tarif",          "Tarifbezeichnung"),
            ("vertragsbeginn", "Vertragsbeginn"),
            ("vertragsende",   "Vertragsende"),
            ("kuendigung",     "Kündigungsdatum"),
        ]
        self._voda_vars = self._build_column_form(frame, "vodafone_columns", VODA_FIELDS)
        return frame

    # ------------------------------------------------------------------
    # Tab 3: Syno-Spalten
    # ------------------------------------------------------------------

    def _build_syno_columns(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=10)

        ttk.Label(frame, text=(
            "Spaltenindizes (0-basiert) in der Syno-Exportdatei.\n"
            "Spalte A = 0, B = 1, C = 2 … M = 12 usw."
        ), justify="left", foreground="gray").pack(anchor="w", pady=(0, 12))

        SYNO_FIELDS = [
            ("startdatum", "Auftragsdatum / Startdatum"),
            ("syno",       "Gerätemodell"),
            ("name",       "Gerätebenutzer (für Namens-Matching)"),
            ("rufnummer",  "Rufnummer / GSM"),
        ]
        self._syno_vars = self._build_column_form(frame, "syno_columns", SYNO_FIELDS)
        return frame

    def _build_column_form(self, parent, section: str, fields: list) -> dict:
        """Erstellt ein Formular mit Spalten-Index-Einträgen. Gibt {key: IntVar} zurück."""
        inner = ttk.Frame(parent)
        inner.pack(anchor="w")
        vars_: dict = {}

        for key, label in fields:
            row = ttk.Frame(inner)
            row.pack(fill="x", pady=3)

            ttk.Label(row, text=label + ":", width=34, anchor="w").pack(side="left")

            var = tk.IntVar(value=self._data[section].get(key, 0))
            vars_[key] = var

            spinbox = ttk.Spinbox(row, from_=0, to=99, width=5,
                                  textvariable=var)
            spinbox.pack(side="left", padx=(0, 6))

            letter_lbl = ttk.Label(row, text="", foreground="#555", width=6)
            letter_lbl.pack(side="left")

            def _update_letter(v=var, lbl=letter_lbl):
                try:
                    lbl.config(text=f"= Spalte {_col_letter(v.get())}")
                except Exception:
                    pass

            var.trace_add("write", lambda *_, fn=_update_letter: fn())
            _update_letter()

        return vars_

    # ------------------------------------------------------------------
    # Tab 4: Hilfe
    # ------------------------------------------------------------------

    def _build_help(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=10)
        text = tk.Text(frame, wrap="word", font=("Segoe UI", 9),
                       background="#FAFAFA", relief="flat")
        ys = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=ys.set)
        text.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")

        text.insert("1.0", """\
EINSTELLUNGEN – MOBILFUNKVERWALTUNG
=====================================

WERK-KONTO-ZUORDNUNG
---------------------
Ordnet jeder Vodafone-Kontonummer ein Werk (Plant) zu.

Wird beim Vodafone-Import für zwei Zwecke verwendet:

1. Plausibilitätsprüfung:
   Wenn der importierte Datensatz ein anderes Werk hat als hier
   hinterlegt, wird verified=✗ gesetzt und ein Hinweis in die
   Bemerkung geschrieben.

2. Werk-Ableitung für neue Einträge:
   Wenn eine Vodafone-GSM noch nicht im Bestand ist, wird das Werk
   automatisch aus der Kontonummer abgeleitet.

Hinzufügen: Kontonummer und Werkname eingeben, Speichern.
Bearbeiten: Doppelklick auf eine Zeile oder Schaltfläche.
Löschen:    Zeile auswählen → Löschen.


VODAFONE-SPALTEN
-----------------
Definiert, in welcher Spalte (0-basiert) der Vodafone-Export
die jeweiligen Felder enthält.

Beispiel:  Spalte A = Index 0,  M = Index 12,  P = Index 15.

Falls Vodafone das Exportformat ändert, nur hier die Nummern
anpassen – kein Code-Änderung nötig.

Wichtig: Zeile 1 wird als Kopfzeile übersprungen.
Der Import prüft die Kopfzeile automatisch und warnt bei
auffälligen Abweichungen.


SYNO-SPALTEN
-------------
Analog zu Vodafone-Spalten, aber für die Syno-Exportdatei.

Standardmäßig:
  Auftragsdatum  = A (0)
  Gerätemodell   = M (12)
  Gerätebenutzer = N (13)   ← für Namens-Matching
  Rufnummer      = P (15)   ← für GSM-Matching


ALLGEMEIN
----------
Einstellungen werden in settings.json im Programmverzeichnis
gespeichert und beim Start automatisch geladen.

Änderungen werden erst nach Klick auf "Speichern" wirksam.
""")
        text.configure(state="disabled")
        return frame

    # ------------------------------------------------------------------
    # Speichern
    # ------------------------------------------------------------------

    def _save(self):
        # Vodafone-Spalten übernehmen
        if hasattr(self, "_voda_vars"):
            for key, var in self._voda_vars.items():
                try:
                    self._data["vodafone_columns"][key] = int(var.get())
                except (ValueError, tk.TclError):
                    messagebox.showerror("Ungültiger Wert",
                                         f"Vodafone-Spalte '{key}': kein gültiger Wert.",
                                         parent=self)
                    return

        # Syno-Spalten übernehmen
        if hasattr(self, "_syno_vars"):
            for key, var in self._syno_vars.items():
                try:
                    self._data["syno_columns"][key] = int(var.get())
                except (ValueError, tk.TclError):
                    messagebox.showerror("Ungültiger Wert",
                                         f"Syno-Spalte '{key}': kein gültiger Wert.",
                                         parent=self)
                    return

        try:
            settings_store.save(self._data)
            messagebox.showinfo("Gespeichert",
                                "Einstellungen gespeichert.\n"
                                "Änderungen gelten ab dem nächsten Import.",
                                parent=self)
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc), parent=self)


# ---------------------------------------------------------------------------
# Hilfsdialog: Konto-Werk bearbeiten
# ---------------------------------------------------------------------------

class _KontoPlantDialog(tk.Toplevel):
    def __init__(self, parent, konto: str, plant: str,
                 on_save_callback, edit_konto: str = ""):
        super().__init__(parent)
        self.title("Konto-Werk-Zuordnung")
        theme.center_window(self, 360, 160, parent)
        self.resizable(False, False)
        self.grab_set()

        self._callback = on_save_callback
        self._edit_konto = edit_konto

        form = ttk.Frame(self, padding=16)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Kontonummer:", width=16, anchor="e").grid(
            row=0, column=0, padx=(0, 8), pady=6, sticky="e")
        self._konto_var = tk.StringVar(value=konto)
        ttk.Entry(form, textvariable=self._konto_var, width=24).grid(
            row=0, column=1, sticky="ew")

        ttk.Label(form, text="Werk:", width=16, anchor="e").grid(
            row=1, column=0, padx=(0, 8), pady=6, sticky="e")
        self._plant_var = tk.StringVar(value=plant)
        ttk.Entry(form, textvariable=self._plant_var, width=24).grid(
            row=1, column=1, sticky="ew")

        form.columnconfigure(1, weight=1)

        btn = ttk.Frame(self, padding=(16, 0, 16, 12))
        btn.pack(fill="x")
        ttk.Button(btn, text="Übernehmen", command=self._apply).pack(side="right", padx=4)
        ttk.Button(btn, text="Abbrechen",  command=self.destroy).pack(side="right")

    def _apply(self):
        konto = self._konto_var.get().strip()
        plant = self._plant_var.get().strip()
        if not konto or not plant:
            messagebox.showwarning("Fehlende Eingabe",
                                   "Bitte Kontonummer und Werk eingeben.", parent=self)
            return
        self._callback(self._edit_konto, konto, plant)
        self.destroy()
