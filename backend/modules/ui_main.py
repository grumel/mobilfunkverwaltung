"""
ui_main.py – Hauptfenster der Mobilfunkverwaltung.

Verbesserungen:
- Suche in allen Tabs (Teilnehmer, Offene Prüfungen)
- Sortierrichtungs-Pfeil in Spaltenköpfen
- Export als Excel (.xlsx)
- verified-Status per Doppelklick auf OK-Spalte umschalten
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont
import logging
from datetime import datetime
from pathlib import Path

from modules import database as db
from modules.ui_editor import EditorWindow, FIELD_ORDER, ALWAYS_READONLY
from modules import vodafone_import, syno_import, syno_enrich, master_import, kuendigung, neuvertrag
from modules.ui_settings import SettingsDialog
from modules import theme, settings_store, auth
from modules.version import __version__, __app_name__, __build_date__, __author__

logger = logging.getLogger(__name__)

DATE_FIELDS = {"vertragsbeginn", "vertragsende", "kuendigung", "start_syno", "start_syno2", "created_at", "updated_at"}

PARTICIPANT_COLUMNS = [
    ("master_id",      "Nr.",           45),
    ("gsm",            "GSM",          115),
    ("name",           "Name",         150),
    ("plant",          "Werk",          80),
    ("konto",          "Konto",         95),
    ("tarif",          "Tarif",        125),
    ("sim_nummer",     "SIM-Nr.",      130),
    ("telefon",        "Telefon",       90),
    ("vertragsbeginn", "Vtg.-Beginn",   85),
    ("vertragsende",   "Vtg.-Ende",     85),
    ("kuendigung",     "Kündigung",     85),
    ("syno",           "Syno 1",       120),
    ("start_syno",     "Syno 1 seit",   85),
    ("syno2",          "Syno 2",       120),
    ("start_syno2",    "Syno 2 seit",   85),
    ("verified",       "OK",            35),
    ("bemerkung",      "Bemerkung",    180),
]

OPEN_CHECK_COLUMNS = [
    ("master_id",      "Nr.",           45),
    ("gsm",            "GSM",          115),
    ("name",           "Name",         150),
    ("plant",          "Werk",          80),
    ("konto",          "Konto",         95),
    ("tarif",          "Tarif",        125),
    ("vertragsbeginn", "Vtg.-Beginn",   85),
    ("vertragsende",   "Vtg.-Ende",     85),
    ("pruefung_grund", "Prüfungsnotiz", 180),
    ("bemerkung",      "Bemerkung",    160),
]

DUPLICATE_COLUMNS = [
    ("master_id", "Nr.",   45),
    ("name",      "Name", 180),
    ("gsm",       "GSM",  120),
    ("plant",     "Werk",  80),
    ("konto",     "Konto", 90),
    ("tarif",     "Tarif", 110),
]

UNMATCHED_COLUMNS = [
    ("id",          "ID",          40),
    ("quelle",      "Quelle",      70),
    ("gsm",         "GSM",        120),
    ("benutzer",    "Benutzer",   160),
    ("geraet",      "Gerät",      160),
    ("startdatum",  "Startdatum",  90),
    ("importdatum", "Importiert", 130),
]


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _fmt_date(value):
    if not value:
        return ""
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return str(value)


def _parse_input_date(text: str) -> str | None:
    """Eingabe 'TT.MM.JJJJ' (auch 'JJJJ-MM-TT') → ISO 'JJJJ-MM-TT' oder None."""
    s = (text or "").strip()
    if not s:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _row_values(row, col_keys):
    values = []
    for k in col_keys:
        v = row[k] if k in row.keys() else ""
        if k in DATE_FIELDS:
            v = _fmt_date(v)
        elif k == "verified":
            v = "✓" if v else "✗"
        else:
            v = str(v) if v is not None else ""
        values.append(v)
    return tuple(values)


def _is_telekom(row) -> bool:
    """True, wenn der Datensatz zum Provider Telekom gehört."""
    try:
        return "provider" in row.keys() and (row["provider"] or "") == "Telekom"
    except Exception:
        return False


def _make_treeview(parent, columns):
    col_ids = [c[0] for c in columns]
    tv = ttk.Treeview(parent, columns=col_ids, show="headings", selectmode="browse")
    last = columns[-1][0]
    for col_id, heading, width in columns:
        tv.heading(col_id, text=heading)
        tv.column(col_id, width=width, minwidth=max(30, width // 2),
                  stretch=(col_id == last))
    return tv


_PADDING = 22  # extra Pixel links+rechts pro Zelle


def _apply_column_visibility(tv: ttk.Treeview, columns: list, settings_key: str):
    """Setzt versteckte Spalten auf width=0 gemäß gespeicherter Einstellung."""
    vis = settings_store.get().get("column_visibility", {}).get(settings_key, {})
    for col_id, _heading, orig_w in columns:
        if not vis.get(col_id, True):
            tv.column(col_id, width=0, minwidth=0, stretch=False)


def _autoresize_columns(tv: ttk.Treeview):
    """Passt jede Spalte auf die Breite des längsten Inhalts (inkl. Kopf) an.

    Misst mit der tatsächlich gerenderten Treeview-Schrift (siehe theme.py:
    Treeview nutzt "Segoe UI 10", nicht das kleinere TkDefaultFont) – sonst
    werden Zellen leicht zu schmal berechnet und lange Werte (z.B. GSM-
    Nummern) am rechten Rand abgeschnitten.
    """
    try:
        f = tkfont.Font(font=("Segoe UI", 10))
        f_bold = tkfont.Font(font=("Segoe UI", 10, "bold"))
    except Exception:
        return
    for col in tv["columns"]:
        if tv.column(col, "width") == 0:
            continue  # versteckte Spalte nicht vergrößern
        heading = tv.heading(col, "text").rstrip(" ▲▼")
        max_w = f_bold.measure(heading) + _PADDING
        for iid in tv.get_children():
            cell = tv.set(iid, col)
            w = f.measure(str(cell)) + _PADDING
            if w > max_w:
                max_w = w
        tv.column(col, width=max_w)


def _add_scrollbars(frame, tv):
    ys = ttk.Scrollbar(frame, orient="vertical",   command=tv.yview)
    xs = ttk.Scrollbar(frame, orient="horizontal", command=tv.xview)
    tv.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
    tv.grid(row=0, column=0, sticky="nsew")
    ys.grid(row=0, column=1, sticky="ns")
    xs.grid(row=1, column=0, sticky="ew")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    return xs


# ---------------------------------------------------------------------------
# Spaltenfilter-Leiste
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Sortierung mit Richtungspfeil
# ---------------------------------------------------------------------------

class _Sorter:
    """Verwaltet Sortierstatus, zeigt Pfeil im Spaltenkopf und persistiert den Zustand."""

    # Tags mit Vorrang – bleiben beim Neu-Streifen erhalten
    _KEEP_TAGS = ("has_task", "task_reminder")

    def __init__(self, tv: ttk.Treeview, columns,
                 on_change=None, initial_state: tuple | None = None,
                 stripe: tuple | None = None):
        self._tv           = tv
        self._col_headings = {c[0]: c[1] for c in columns}
        self._current_col  = None
        self._reverse      = False
        self._on_change    = on_change
        self._stripe       = stripe   # (Tag gerade Zeile, Tag ungerade Zeile)
        for col_id in self._col_headings:
            tv.heading(col_id, command=lambda c=col_id: self.sort(c))
        if initial_state:
            self._current_col, self._reverse = initial_state
            self._apply(notify=False)

    def sort(self, col: str):
        if self._current_col == col:
            self._reverse = not self._reverse
        else:
            self._current_col = col
            self._reverse = False
        self._apply(notify=True)

    def reapply(self):
        """Sortierung erneut anwenden (nach Datenneuladung), ohne Zustand zu ändern."""
        if self._current_col:
            self._apply(notify=False)

    def get_state(self) -> tuple | None:
        if self._current_col:
            return (self._current_col, self._reverse)
        return None

    def restripe(self):
        """Vergibt die Zebra-Streifung nach der aktuellen Zeilenreihenfolge neu.

        Markierungen mit Vorrang (offene Aufgabe, Such-Erinnerung) bleiben
        unangetastet und zählen für den Streifenrhythmus nicht mit.
        """
        if not self._stripe:
            return
        even, odd = self._stripe
        for idx, iid in enumerate(self._tv.get_children("")):
            keep = [t for t in self._tv.item(iid, "tags") if t in self._KEEP_TAGS]
            if keep:
                self._tv.item(iid, tags=tuple(keep))
                continue
            st = odd if idx % 2 else even
            self._tv.item(iid, tags=(st,) if st else ())

    def _apply(self, notify: bool = True):
        tv  = self._tv
        col = self._current_col
        if not col:
            return

        def sort_key(iid):
            val = tv.set(iid, col)
            try:
                return (0, int(val))
            except (ValueError, TypeError):
                return (1, val.lower())

        items = sorted(tv.get_children(""), key=sort_key, reverse=self._reverse)
        for idx, iid in enumerate(items):
            tv.move(iid, "", idx)
        # Zebra-Streifung an die neue Reihenfolge anpassen
        self.restripe()

        for c, label in self._col_headings.items():
            if c == col:
                arrow = " ▲" if not self._reverse else " ▼"
                tv.heading(c, text=label + arrow, command=lambda x=c: self.sort(x))
            else:
                tv.heading(c, text=label, command=lambda x=c: self.sort(x))

        if notify and self._on_change:
            self._on_change(col, self._reverse)


# ---------------------------------------------------------------------------
# Hauptfenster
# ---------------------------------------------------------------------------

class MainWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        s = auth.get_session()
        user_info = f" – {s.username} ({auth.ROLE_LABELS.get(s.role, s.role)})" if s else ""
        root.title(f"{__app_name__} v{__version__}{user_info}")
        root.geometry("1200x700")
        root.minsize(900, 500)

        cfg = settings_store.get()
        theme.apply(root, dark=cfg.get("dark_mode", False))
        self._dark_var = tk.BooleanVar(value=cfg.get("dark_mode", False))

        # Fenstergröße wiederherstellen
        if geo := cfg.get("window_geometry"):
            try:
                root.geometry(geo)
            except Exception:
                pass

        # Refs für theme-sensitive nicht-ttk Widgets (werden in _build_* befüllt)
        self._incomplete_legend_refs: list[tuple[tk.Label, str]] = []

        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Control-f>", lambda e: self._focus_global_search())

        self._build_menu()
        self._build_global_search_bar()
        self._build_statusbar()
        self._build_notebook()
        self.refresh_all()
        self._check_expiry_on_startup()

    # ------------------------------------------------------------------
    # Menü
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Globale Suche – immer sichtbare Leiste oben
    # ------------------------------------------------------------------

    def _build_global_search_bar(self):
        bar = ttk.Frame(self.root, padding=(8, 6, 8, 4))
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="🔍 Globale Suche:").pack(side="left")
        self._global_search_var = tk.StringVar()
        self._global_search_entry = ttk.Entry(
            bar, textvariable=self._global_search_var, width=45)
        self._global_search_entry.pack(side="left", padx=(6, 6))
        self._global_search_entry.bind(
            "<Return>", lambda e: self._open_global_search(self._global_search_var.get().strip()))
        ttk.Button(
            bar, text="Suchen", style="Accent.TButton",
            command=lambda: self._open_global_search(self._global_search_var.get().strip())
        ).pack(side="left")
        ttk.Label(bar, text="(alle Register, Offene Prüfungen, Nicht zugeordnet – Strg+F)",
                  style="Dim.TLabel").pack(side="left", padx=(10, 0))
        # Aufgaben-Knopf oben rechts (Badge zeigt offene Aufgaben)
        self._tasks_btn = ttk.Button(bar, text="Aufgaben", style="Big.TButton",
                                     command=self._open_tasks_window)
        self._tasks_btn.pack(side="right")

    def _focus_global_search(self):
        self._global_search_entry.focus_set()
        self._global_search_entry.select_range(0, "end")

    # ------------------------------------------------------------------
    # Statusleiste
    # ------------------------------------------------------------------

    def _build_statusbar(self):
        ttk.Separator(self.root, orient="horizontal").pack(side="bottom", fill="x")
        bar = ttk.Frame(self.root, style="Statusbar.TFrame")
        bar.pack(side="bottom", fill="x", padx=8, pady=2)

        self._sb_total_var      = tk.StringVar(value="")
        self._sb_open_var       = tk.StringVar(value="")
        self._sb_lastimport_var = tk.StringVar(value="")

        ttk.Label(bar, textvariable=self._sb_total_var,
                  style="Statusbar.TLabel").pack(side="left")
        ttk.Separator(bar, orient="vertical",
                      style="Statusbar.TSeparator").pack(side="left", fill="y", padx=8, pady=1)
        ttk.Label(bar, textvariable=self._sb_open_var,
                  style="Statusbar.TLabel").pack(side="left")
        ttk.Separator(bar, orient="vertical",
                      style="Statusbar.TSeparator").pack(side="left", fill="y", padx=8, pady=1)
        ttk.Label(bar, textvariable=self._sb_lastimport_var,
                  style="Statusbar.TLabel").pack(side="left")

        # Version / Datum / Autor – rechts außen im Rand
        ttk.Label(bar, text=f"© {__author__}  ·  v{__version__} ({__build_date__})",
                  style="Statusbar.TLabel").pack(side="right")

    def _update_statusbar(self):
        try:
            with db.read_connection() as conn:
                s = db.get_stats(conn)
                last_row = conn.execute(
                    "SELECT zeitpunkt FROM import_log "
                    "WHERE quelle IN ('Vodafone','Syno') "
                    "ORDER BY id DESC LIMIT 1"
                ).fetchone()
            total      = s.get("total", 0)
            open_count = s.get("zur_pruefung", 0)
            self._sb_total_var.set(f"Teilnehmer: {total}")
            self._sb_open_var.set(f"Offene Prüfungen: {open_count}")
            if last_row:
                ts = str(last_row[0])[:16]
                self._sb_lastimport_var.set(f"Letzter Import: {ts}")
            else:
                self._sb_lastimport_var.set("Noch kein Import")
        except Exception as exc:
            logger.debug("Statusleiste konnte nicht aktualisiert werden: %s", exc)

    def _update_task_button(self):
        try:
            with db.read_connection() as conn:
                n = db.count_open_tasks(conn)
            self._tasks_btn.configure(text=f"Aufgaben ({n})" if n else "Aufgaben")
        except Exception as exc:
            logger.debug("Aufgaben-Button konnte nicht aktualisiert werden: %s", exc)
        try:
            m = len(self._tv_neuvertrag.get_children())
            self._neuvertrag_btn.configure(text=f"Neuvertrag ({m})" if m else "Neuvertrag")
        except Exception as exc:
            logger.debug("Neuvertrag-Button konnte nicht aktualisiert werden: %s", exc)

    # ------------------------------------------------------------------
    # Tab-Badges
    # ------------------------------------------------------------------

    def _update_tab_badges(self):
        counts = {
            self._tab_telekom:       (len(self._tv_telekom.get_children()),   "Telekom"),
            self._tab_o2:            (len(self._tv_o2.get_children()),        "O2"),
            self._tab_ohnesim:       (len(self._tv_ohnesim.get_children()),   "Ohne SIM"),
            self._tab_frei:          (len(self._tv_frei.get_children()),      "Frei"),
            self._tab_open_checks:   (len(self._open_data),                   "Offene Prüfungen"),
            self._tab_unmatched:     (len(self._tv_unmatched.get_children()), "Nicht zugeordnet"),
            self._tab_incomplete:    (len(self._tv_incomplete.get_children()), "Unvollständig"),
            self._tab_duplicates:    (len(self._tv_duplicates.get_children()), "Duplikate"),
        }
        for tab_frame, (count, base_title) in counts.items():
            label = f"{base_title} ({count})" if count else base_title
            try:
                self.notebook.tab(tab_frame, text=label)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_theme(self):
        dark = self._dark_var.get()
        cfg = settings_store.get()
        cfg["dark_mode"] = dark
        settings_store.save(cfg)
        theme.apply(self.root, dark)
        p = theme.current()
        # Nicht-ttk Widgets manuell aktualisieren
        try:
            self._stat_canvas.configure(bg=p["stat_canvas_bg"])
        except Exception:
            pass
        try:
            self._log_text.configure(background=p["log_bg"], foreground=p["log_fg"])
        except Exception:
            pass
        for lbl, key in self._incomplete_legend_refs:
            try:
                lbl.configure(background=p[key], foreground=p["legend_fg"])
            except Exception:
                pass
        for w, kind in getattr(self, "_stat_tile_refs", []):
            try:
                if kind == "tile":
                    w.configure(bg=p["tile_bg"], highlightbackground=p["tile_border_color"])
                elif kind == "num":
                    w.configure(bg=p["tile_bg"], fg=p["accent"])
                else:
                    w.configure(bg=p["tile_bg"], fg=p["tile_fg_dim"])
            except Exception:
                pass
        self._retag_all()

    def _retag_all(self):
        p = theme.current()
        try:
            self._tv_ablauf.tag_configure("soon",   background=p["tag_soon"])
            self._tv_ablauf.tag_configure("urgent", background=p["tag_urgent"])
        except Exception:
            pass
        try:
            self._tv_incomplete.tag_configure("missing_gsm",   background=p["tag_missing_gsm"])
            self._tv_incomplete.tag_configure("missing_plant", background=p["tag_missing_plant"])
            self._tv_incomplete.tag_configure("missing_konto", background=p["tag_missing_konto"])
        except Exception:
            pass
        try:
            self._tv_werk.tag_configure("warn", background=p["tag_warn"])
        except Exception:
            pass
        try:
            self._tv_duplicates.tag_configure("odd", background=p["tag_odd_dup"])
        except Exception:
            pass
        # Telekom-Markierung (zart grün) in allen Ansichten
        for tv in (self._tv_telekom, self._tv_duplicates, self._tv_incomplete,
                   self._tv_neuvertrag, self._tv_ablauf):
            try:
                tv.tag_configure("telekom", background=p["tag_telekom"])
            except Exception:
                pass
        try:
            self._tv_telekom.tag_configure("telekom_z", background=p["tag_telekom_z"])
        except Exception:
            pass
        try:
            self._tv_frei.tag_configure("frei",   background=p["tag_frei"])
            self._tv_frei.tag_configure("frei_z", background=p["tag_frei_z"])
        except Exception:
            pass
        try:
            self._tv_o2.tag_configure("o2",   background=p["tag_o2"])
            self._tv_o2.tag_configure("o2_z", background=p["tag_o2_z"])
        except Exception:
            pass
        try:
            self._tv_ohnesim.tag_configure("ohnesim",   background=p["tag_ohnesim"])
            self._tv_ohnesim.tag_configure("ohnesim_z", background=p["tag_ohnesim_z"])
        except Exception:
            pass
        for tv in (self._tv_participants, self._tv_telekom, self._tv_open,
                   self._tv_frei, self._tv_o2, self._tv_ohnesim,
                   self._tv_incomplete, self._tv_duplicates):
            try:
                tv.tag_configure("task_reminder", background=p["tag_task"])
                tv.tag_configure("has_task", background=p["tag_has_task_bg"],
                                 foreground=p["tag_has_task_fg"],
                                 font=("Segoe UI", 10, "bold"))
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Fenster-Zustand
    # ------------------------------------------------------------------

    def _on_close(self):
        cfg = settings_store.get()
        cfg["window_geometry"] = self.root.geometry()
        # Sortierstatus der Haupttabs merken
        sort = cfg.setdefault("sort_state", {})
        for key, sorter in [
            ("participants", self._sorter_participants),
            ("open_checks",  self._sorter_open),
            ("telekom",      self._sorter_telekom),
            ("o2",           self._sorter_o2),
            ("ohnesim",      self._sorter_ohnesim),
            ("frei",         self._sorter_frei),
        ]:
            state = sorter.get_state()
            sort[key] = {"col": state[0], "rev": state[1]} if state else None
        settings_store.save(cfg)
        self.root.destroy()

    def _save_sort(self, key: str, col: str, rev: bool):
        cfg = settings_store.get()
        cfg.setdefault("sort_state", {})[key] = {"col": col, "rev": rev}
        settings_store.save(cfg)

    def _make_sorter(self, tv, key: str, stripe: tuple) -> "_Sorter":
        """Sorter mit persistiertem Sortierstatus (settings.json → sort_state)."""
        cfg = settings_store.get().get("sort_state", {}).get(key)
        return _Sorter(
            tv, PARTICIPANT_COLUMNS,
            on_change=lambda c, r: self._save_sort(key, c, r),
            initial_state=(cfg["col"], cfg["rev"]) if cfg else None,
            stripe=stripe,
        )

    # ------------------------------------------------------------------
    # Ablauf-Benachrichtigung
    # ------------------------------------------------------------------

    def _check_expiry_on_startup(self):
        try:
            with db.read_connection() as conn:
                s = db.get_stats(conn)
            count = s.get("ablauf_30", 0)
            if count <= 0:
                return
            bar = tk.Frame(self.root, bg=theme.current()["warn_banner_bg"], cursor="hand2")
            p = theme.current()
            msg = f"⚠  {count} Vertrag{'  laufen' if count > 1 else ' läuft'} in den nächsten 30 Tagen ab"
            lbl = tk.Label(bar, text=msg, bg=p["warn_banner_bg"], fg=p["warn_banner_fg"],
                           font=("Segoe UI", 9, "bold"), anchor="w", padx=10)
            close_btn = tk.Label(bar, text="✕", bg=p["warn_banner_bg"], fg=p["warn_banner_fg"],
                                 font=("Segoe UI", 9, "bold"), padx=8, cursor="hand2")
            lbl.pack(side="left", fill="x", expand=True, pady=3)
            close_btn.pack(side="right", pady=3)
            bar.pack(fill="x", after=self.root.winfo_children()[0])

            def _goto_stats(e=None):
                self._show_tool_window(self._win_statistics)
                bar.destroy()

            lbl.bind("<Button-1>", _goto_stats)
            close_btn.bind("<Button-1>", lambda e: bar.destroy())
        except Exception as exc:
            logger.debug("Ablauf-Check fehlgeschlagen: %s", exc)

    # ------------------------------------------------------------------
    # Menü
    # ------------------------------------------------------------------

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        session = auth.get_session()
        can_write = session.can("write") if session else False
        can_admin = session.can("admin") if session else False
        _dis = lambda: "normal" if can_write else "disabled"
        _adm = lambda: "normal" if can_admin else "disabled"

        # Importe sind nur für Administratoren zugänglich
        # (Masterbestand-Import bewusst nicht mehr im Menü – Bestand ist sauber;
        #  die Funktion _import_master bleibt für den Notfall im Code erhalten.)
        import_menu = tk.Menu(menubar, tearoff=0)
        import_menu.add_command(label="Vodafone importieren …",
                                command=self._import_vodafone, state=_adm())
        import_menu.add_command(label="Syno importieren …",
                                command=self._import_syno,     state=_adm())
        import_menu.add_separator()
        import_menu.add_command(label="Syno-Datei anreichern … (vor Import)",
                                command=self._enrich_syno,     state=_adm())
        menubar.add_cascade(label="Import", menu=import_menu)

        export_menu = tk.Menu(menubar, tearoff=0)
        export_menu.add_command(label="Teilnehmer als Excel exportieren …", command=self._export_excel)
        export_menu.add_command(label="Teilnehmer als CSV exportieren …",   command=self._export_csv)
        export_menu.add_separator()
        export_menu.add_command(label="Drucken / PDF-Vorschau …",           command=self._export_print)
        menubar.add_cascade(label="Export", menu=export_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Datenbank-Backup erstellen",
                               command=self._manual_backup, state=_adm())
        tools_menu.add_command(label="Backup wiederherstellen …",
                               command=self._restore_backup, state=_adm())
        tools_menu.add_separator()
        tools_menu.add_command(label="Benutzerverwaltung …",
                               command=self._open_usermgmt, state=_adm())
        tools_menu.add_separator()
        tools_menu.add_command(label="Abmelden", command=self._logout)
        menubar.add_cascade(label="Extras", menu=tools_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_checkbutton(label="Dark Mode",
                                  variable=self._dark_var,
                                  command=self._apply_theme)
        menubar.add_cascade(label="Ansicht", menu=view_menu)

        menubar.add_command(label="Einstellungen",
                            command=lambda: SettingsDialog(self.root),
                            state=_adm())

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Hilfe anzeigen", command=self._show_help)
        help_menu.add_separator()
        help_menu.add_command(label="Über …", command=self._show_about)
        menubar.add_cascade(label="?", menu=help_menu)

        self.root.config(menu=menubar)

    # ------------------------------------------------------------------
    # Notebook
    # ------------------------------------------------------------------

    def _build_notebook(self):
        # Untere Knopfleiste (über der Statusleiste), rechts außen
        bottom_bar = ttk.Frame(self.root)
        bottom_bar.pack(side="bottom", fill="x", padx=6)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=6, pady=6)

        self._tab_participants  = self._build_tab_participants()
        self._tab_telekom       = self._build_tab_telekom()
        self._tab_o2            = self._build_tab_o2()
        self._tab_ohnesim       = self._build_tab_ohnesim()
        self._tab_frei          = self._build_tab_frei()
        self._tab_open_checks   = self._build_tab_open_checks()
        self._tab_unmatched     = self._build_tab_unmatched()
        self._tab_incomplete    = self._build_tab_incomplete()
        self._tab_werk_overview = self._build_tab_werk_overview()
        self._tab_duplicates    = self._build_tab_duplicates()

        self.notebook.add(self._tab_participants,  text="Vodafone")
        self.notebook.add(self._tab_telekom,       text="Telekom")
        self.notebook.add(self._tab_o2,            text="O2")
        self.notebook.add(self._tab_ohnesim,       text="Ohne SIM")
        self.notebook.add(self._tab_frei,          text="Frei")
        self.notebook.add(self._tab_duplicates,    text="Duplikate")
        self.notebook.add(self._tab_open_checks,   text="Offene Prüfungen")
        self.notebook.add(self._tab_unmatched,     text="Nicht zugeordnet")
        self.notebook.add(self._tab_incomplete,    text="Unvollständig")
        self.notebook.add(self._tab_werk_overview, text="Werk-Übersicht")

        # Statistik, Importhistorie, Audit-Log und Neuvertrag als eigene
        # Fenster, erreichbar über die untere Knopfleiste
        self._win_statistics = self._make_tool_window("Statistik",      self._build_tab_statistics, 1020, 620)
        self._win_import_log = self._make_tool_window("Importhistorie", self._build_tab_import_log,  950, 500)
        self._win_audit_log  = self._make_tool_window("Audit-Log",      self._build_tab_audit_log,   950, 450)
        self._win_neuvertrag = self._make_tool_window("Neuvertrag",     self._build_tab_neuvertrag,  980, 560)
        self._win_quality    = self._make_tool_window("Datenqualität",  self._build_tab_quality,     900, 560)

        is_admin = auth.get_session() and auth.get_session().can("admin")
        self._neuvertrag_btn = ttk.Button(
            bottom_bar, text="Neuvertrag", style="Big.TButton",
            command=lambda: self._show_tool_window(self._win_neuvertrag))
        self._neuvertrag_btn.pack(side="right", padx=(6, 0), pady=(2, 6))
        if is_admin:
            ttk.Button(bottom_bar, text="Audit-Log", style="Big.TButton",
                       command=lambda: self._show_tool_window(self._win_audit_log)
                       ).pack(side="right", padx=(6, 0), pady=(2, 6))
        ttk.Button(bottom_bar, text="Importhistorie", style="Big.TButton",
                   command=lambda: self._show_tool_window(self._win_import_log)
                   ).pack(side="right", padx=(6, 0), pady=(2, 6))
        ttk.Button(bottom_bar, text="Datenqualität", style="Big.TButton",
                   command=lambda: (self._load_quality(),
                                    self._show_tool_window(self._win_quality))
                   ).pack(side="right", padx=(6, 0), pady=(2, 6))
        ttk.Button(bottom_bar, text="Statistik", style="Big.TButton",
                   command=lambda: self._show_tool_window(self._win_statistics)
                   ).pack(side="right", padx=(6, 0), pady=(2, 6))

    def _make_tool_window(self, title: str, build_fn, w: int, h: int) -> tk.Toplevel:
        """Erzeugt ein verstecktes Werkzeug-Fenster; Schließen blendet nur aus."""
        win = tk.Toplevel(self.root)
        win.title(title)
        theme.center_window(win, w, h, self.root)
        win.minsize(600, 300)
        build_fn(win).pack(fill="both", expand=True)
        win.protocol("WM_DELETE_WINDOW", win.withdraw)
        win.bind("<Escape>", lambda e: win.withdraw())
        win.withdraw()
        return win

    def _show_tool_window(self, win: tk.Toplevel):
        win.deiconify()
        win.lift()
        win.focus_set()

    # ------------------------------------------------------------------
    # Tab 1: Vodafone (Teilnehmer)
    # ------------------------------------------------------------------

    def _build_tab_participants(self) -> ttk.Frame:
        frame = ttk.Frame(self.notebook)

        # -- Treeview zuerst erzeugen (Filter-Leiste braucht die Referenz) --
        tv_frame = ttk.Frame(frame)
        self._tv_participants = _make_treeview(tv_frame, PARTICIPANT_COLUMNS)
        self._tv_participants["selectmode"] = "extended"
        self._tv_participant_cols = [c[0] for c in PARTICIPANT_COLUMNS]
        _apply_column_visibility(self._tv_participants, PARTICIPANT_COLUMNS, "participants")
        _sort_cfg = settings_store.get().get("sort_state", {}).get("participants")
        _sort_init = (_sort_cfg["col"], _sort_cfg["rev"]) if _sort_cfg else None
        self._sorter_participants = _Sorter(
            self._tv_participants, PARTICIPANT_COLUMNS,
            on_change=lambda c, r: self._save_sort("participants", c, r),
            initial_state=_sort_init,
            stripe=(None, "zebra"),
        )

        # -- Toolbar --
        toolbar = ttk.Frame(frame)
        ttk.Label(toolbar, text="Suche:").pack(side="left")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._apply_participant_filter())
        self._search_entry = ttk.Entry(toolbar, textvariable=self._search_var, width=28)
        self._search_entry.pack(side="left", padx=(4, 8))
        # Strg+F öffnet die globale Suche (in __init__ global gebunden)

        ttk.Button(toolbar, text="Zurücksetzen",
                   command=self._reset_filter).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(toolbar, text="+ Neu", style="Accent.TButton",
                   command=self._new_participant).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Zusammenführen …",
                   command=lambda: self._merge_selected(self._tv_participants)
                   ).pack(side="left", padx=2)
        self._status_var = tk.StringVar()
        ttk.Label(toolbar, textvariable=self._status_var,
                  style="Dim.TLabel", width=18, anchor="e").pack(side="right", padx=(8, 4))

        toolbar.pack(fill="x", padx=8, pady=(8, 0))
        tv_frame.pack(fill="both", expand=True, padx=8, pady=(3, 8))

        _add_scrollbars(tv_frame, self._tv_participants)

        self._tv_participants.bind("<Double-1>", self._on_participant_double_click)
        self._tv_participants.bind("<Button-3>", self._on_participant_rclick)
        return frame

    # ------------------------------------------------------------------
    # Tab: Neuvertrag
    # ------------------------------------------------------------------

    def _build_tab_neuvertrag(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent)

        form = ttk.LabelFrame(frame, text="Neuvertrag bestellen", padding=12)
        form.pack(fill="x", padx=8, pady=8)

        werke = sorted(set(settings_store.get().get("konto_plant", {}).values()))

        ttk.Label(form, text="Werk:").grid(row=0, column=0, sticky="e", padx=(0, 8), pady=4)
        self._nv_werk_var = tk.StringVar()
        werk_combo = ttk.Combobox(form, textvariable=self._nv_werk_var, state="readonly",
                                  values=werke, width=30)
        werk_combo.grid(row=0, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Tarif:").grid(row=1, column=0, sticky="e", padx=(0, 8), pady=4)
        self._nv_tarif_var = tk.StringVar()
        with db.read_connection() as conn:
            tarife = sorted({
                r["tarif"] for r in conn.execute(
                    "SELECT DISTINCT tarif FROM participants WHERE tarif IS NOT NULL AND tarif != ''"
                ).fetchall()
            })
        ttk.Combobox(form, textvariable=self._nv_tarif_var, values=tarife, width=40).grid(
            row=1, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Name:").grid(row=2, column=0, sticky="e", padx=(0, 8), pady=4)
        self._nv_name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self._nv_name_var, width=40).grid(
            row=2, column=1, sticky="w", pady=4)

        ttk.Button(form, text="Neuvertrag bestellen & Mail an Nicole", style="Accent.TButton",
                  command=self._submit_neuvertrag).grid(
            row=3, column=1, sticky="w", pady=(10, 0))

        list_frame = ttk.LabelFrame(frame, text="Bestellte Neuverträge", padding=8)
        list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        cols = [
            ("master_id", "Nr.", 45), ("name", "Name", 180), ("plant", "Werk", 100),
            ("konto", "Konto", 100), ("tarif", "Tarif", 220), ("created_at", "Bestellt am", 140),
        ]
        self._tv_neuvertrag = _make_treeview(list_frame, cols)
        self._tv_neuvertrag_cols = [c[0] for c in cols]
        _add_scrollbars(list_frame, self._tv_neuvertrag)
        self._tv_neuvertrag.bind(
            "<Double-1>",
            lambda e: EditorWindow(self.root, int(self._tv_neuvertrag.focus()),
                                   on_save_callback=self.refresh_all)
            if self._tv_neuvertrag.focus() else None,
        )
        self._tv_neuvertrag.bind("<Button-3>", self._on_neuvertrag_rclick)
        return frame

    def _on_neuvertrag_rclick(self, event):
        tv = self._tv_neuvertrag
        iid = tv.identify_row(event.y)
        if iid:
            tv.selection_set(iid)
        self._show_context_menu(event, tv, iid,
                                actions=[
                                    ("Bearbeiten",   lambda: EditorWindow(self.root, int(iid), on_save_callback=self.refresh_all)),
                                    None,
                                    ("Zu Aufgabe …", lambda: self._create_task_dialog(int(iid))),
                                ])
        return "break"

    def _load_neuvertrag(self):
        tv = self._tv_neuvertrag
        tv.delete(*tv.get_children())
        with db.read_connection() as conn:
            rows = db.get_neuvertraege(conn)
        tv.tag_configure("telekom", background=theme.current()["tag_telekom"])
        for row in rows:
            tag = ("telekom",) if _is_telekom(row) else ()
            tv.insert("", "end", iid=str(row["id"]),
                      values=_row_values(row, self._tv_neuvertrag_cols), tags=tag)
        _autoresize_columns(tv)

    def _submit_neuvertrag(self):
        werk = self._nv_werk_var.get().strip()
        tarif = self._nv_tarif_var.get().strip()
        name = self._nv_name_var.get().strip()
        if not werk or not tarif or not name:
            messagebox.showinfo("Hinweis", "Bitte Werk, Tarif und Name ausfüllen.",
                                parent=self.root)
            return

        konto_plant = settings_store.get().get("konto_plant", {})
        konto = next((k for k, v in konto_plant.items() if v == werk), None)
        if not konto:
            messagebox.showerror(
                "Kein Konto gefunden",
                f"Für das Werk '{werk}' ist kein Konto in den Einstellungen "
                "(Werk-Konto-Zuordnung) hinterlegt.",
                parent=self.root,
            )
            return

        if not messagebox.askyesno(
            "Neuvertrag bestellen",
            f"Neuvertrag anlegen und Mail an Nicole senden für:\n\n"
            f"  Name:  {name}\n  Werk:  {werk}\n  Konto: {konto}\n  Tarif: {tarif}\n\n"
            "Fortfahren?",
            parent=self.root,
        ):
            return

        try:
            neuvertrag.create_email_draft(name, werk, konto, tarif)
        except Exception as exc:
            logger.exception("Neuvertrag-Mail fehlgeschlagen")
            messagebox.showerror(
                "Fehler",
                f"Mail konnte nicht erzeugt werden:\n{exc}\n\n"
                "Hinweis: Für den E-Mail-Entwurf wird Microsoft Outlook (Desktop) benötigt.",
                parent=self.root,
            )
            return

        heute = datetime.now().strftime("%d.%m.%Y")
        try:
            with db.transaction() as conn:
                pid = db.insert_participant(conn, {
                    "name": name,
                    "plant": werk,
                    "konto": konto,
                    "tarif": tarif,
                    "verified": 0,
                    "provider": "Vodafone",
                    "pruefung_grund": f"Neuvertrag - Mail an Nicole gesendet am {heute}",
                    "bemerkung": "Neuvertrag bestellt, noch nicht bei Vodafone aktiv",
                })
                db.log_import(
                    conn, "GUI", "NEUVERTRAG",
                    f"ID={pid} Name={name} Werk={werk} Konto={konto} Tarif={tarif}",
                    participant_id=pid,
                )
        except Exception as exc:
            messagebox.showerror(
                "Mail erzeugt, aber Datenbankfehler",
                f"Der E-Mail-Entwurf wurde geöffnet, aber der Eintrag konnte nicht "
                f"gespeichert werden:\n{exc}",
                parent=self.root,
            )
            return

        self._nv_werk_var.set("")
        self._nv_tarif_var.set("")
        self._nv_name_var.set("")
        self.refresh_all()
        messagebox.showinfo(
            "Neuvertrag bestellt",
            "Der Eintrag wurde angelegt und der Mail-Entwurf ist geöffnet.",
            parent=self.root,
        )

    # ------------------------------------------------------------------
    # Tab: Telekom
    # ------------------------------------------------------------------

    def _build_tab_telekom(self) -> ttk.Frame:
        frame = ttk.Frame(self.notebook)

        tv_frame = ttk.Frame(frame)
        self._tv_telekom = _make_treeview(tv_frame, PARTICIPANT_COLUMNS)
        self._tv_telekom["selectmode"] = "extended"
        self._tv_telekom_cols = [c[0] for c in PARTICIPANT_COLUMNS]
        self._sorter_telekom = self._make_sorter(self._tv_telekom, "telekom",
                                                 ("telekom", "telekom_z"))

        toolbar = ttk.Frame(frame)
        ttk.Label(toolbar, text="Suche:").pack(side="left")
        self._telekom_search_var = tk.StringVar()
        self._telekom_search_var.trace_add("write", lambda *_: self._filter_telekom())
        ttk.Entry(toolbar, textvariable=self._telekom_search_var,
                  width=28).pack(side="left", padx=(4, 8))
        ttk.Button(toolbar, text="+ Neu", style="Accent.TButton",
                   command=self._new_participant).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Zusammenführen …",
                   command=lambda: self._merge_selected(self._tv_telekom)
                   ).pack(side="left", padx=2)
        self._telekom_status_var = tk.StringVar()
        ttk.Label(toolbar, textvariable=self._telekom_status_var,
                  style="Dim.TLabel", width=18, anchor="e").pack(side="right", padx=(8, 4))

        toolbar.pack(fill="x", padx=8, pady=(8, 0))
        tv_frame.pack(fill="both", expand=True, padx=8, pady=(3, 8))
        _add_scrollbars(tv_frame, self._tv_telekom)

        self._tv_telekom.bind("<Double-1>", self._on_telekom_double_click)
        self._tv_telekom.bind("<Button-3>", self._on_telekom_rclick)
        return frame

    def _load_telekom(self):
        tv = self._tv_telekom
        tv.delete(*tv.get_children())
        with db.read_connection() as conn:
            rows = db.get_all_participants(conn, provider="Telekom")
        p = theme.current()
        tv.tag_configure("telekom",   background=p["tag_telekom"])
        tv.tag_configure("telekom_z", background=p["tag_telekom_z"])
        task_ids = self._task_marker(tv)
        for i, row in enumerate(rows):
            tag = ("has_task",) if row["id"] in task_ids else \
                  (("telekom_z",) if i % 2 == 1 else ("telekom",))
            tv.insert("", "end", iid=str(row["id"]),
                      values=_row_values(row, self._tv_telekom_cols), tags=tag)
        self._telekom_status_var.set(f"{len(rows)} Teilnehmer")
        _autoresize_columns(tv)
        self._sorter_telekom.reapply()

    def _filter_telekom(self):
        term = self._telekom_search_var.get().strip().lower()
        tv = self._tv_telekom
        tv.delete(*tv.get_children())
        with db.read_connection() as conn:
            rows = db.get_all_participants(conn, provider="Telekom")
        p = theme.current()
        tv.tag_configure("telekom",       background=p["tag_telekom"])
        tv.tag_configure("telekom_z",     background=p["tag_telekom_z"])
        tv.tag_configure("task_reminder", background=p["tag_task"])
        task_ids = self._task_marker(tv)
        fields = ("name", "gsm", "plant", "konto", "tarif", "bemerkung")
        i = 0
        shown_ids = set()
        for row in rows:
            if term and not any(term in str(row[k] or "").lower() for k in fields):
                continue
            tag = ("has_task",) if row["id"] in task_ids else \
                  (("telekom_z",) if i % 2 == 1 else ("telekom",))
            tv.insert("", "end", iid=str(row["id"]),
                      values=_row_values(row, self._tv_telekom_cols), tags=tag)
            shown_ids.add(row["id"])
            i += 1
        if term:
            with db.read_connection() as conn:
                task_rows = db.get_participants_with_open_tasks(conn)
            for row in task_rows:
                if row["id"] in shown_ids:
                    continue
                if any(term in str(row[k] or "").lower() for k in fields):
                    tv.insert("", "end", iid=str(row["id"]),
                              values=_row_values(row, self._tv_telekom_cols),
                              tags=("has_task",))
                    i += 1
        self._telekom_status_var.set(f"{i} Teilnehmer")

    def _on_telekom_double_click(self, event):
        tv = self._tv_telekom
        iid = tv.identify_row(event.y)
        if iid:
            EditorWindow(self.root, int(iid), on_save_callback=self.refresh_all)

    def _on_telekom_rclick(self, event):
        tv = self._tv_telekom
        region = tv.identify_region(event.x, event.y)
        on_heading = (
            region == "heading"
            or (region not in ("cell", "tree") and not tv.identify_row(event.y))
        )
        if on_heading and tv.identify_column(event.x):
            self._show_column_toggle_menu(event, tv, PARTICIPANT_COLUMNS, "telekom")
            return "break"
        iid = tv.identify_row(event.y)
        if iid:
            tv.selection_set(iid)
        self._show_context_menu(event, tv, iid,
                                actions=[
                                    ("Bearbeiten",              lambda: EditorWindow(self.root, int(iid), on_save_callback=self.refresh_all)),
                                    None,
                                    ("Zu Vodafone verschieben", lambda: self._move_to_provider(int(iid), "Vodafone")),
                                    ("Zu O2 verschieben",       lambda: self._move_to_provider(int(iid), "O2")),
                                    ("Nach 'Ohne SIM' verschieben", lambda: self._move_to_provider(int(iid), "Ohne SIM")),
                                    ("Nach 'Frei' verschieben", lambda: self._move_to_provider(int(iid), "Frei")),
                                    None,
                                    ("Zu Aufgabe …",            lambda: self._create_task_dialog(int(iid))),
                                    None,
                                    ("GSM kopieren",            lambda: self._copy_cell(tv, iid, "gsm")),
                                    ("Name kopieren",           lambda: self._copy_cell(tv, iid, "name")),
                                    None,
                                    ("Eintrag löschen",         lambda: self._ctx_delete(int(iid))),
                                ])
        return "break"

    # ------------------------------------------------------------------
    # Tab: Frei
    # ------------------------------------------------------------------

    def _build_tab_frei(self) -> ttk.Frame:
        frame = ttk.Frame(self.notebook)

        tv_frame = ttk.Frame(frame)
        self._tv_frei = _make_treeview(tv_frame, PARTICIPANT_COLUMNS)
        self._tv_frei["selectmode"] = "extended"
        self._tv_frei_cols = [c[0] for c in PARTICIPANT_COLUMNS]
        self._sorter_frei = self._make_sorter(self._tv_frei, "frei",
                                              ("frei", "frei_z"))

        toolbar = ttk.Frame(frame)
        ttk.Label(toolbar, text="Suche:").pack(side="left")
        self._frei_search_var = tk.StringVar()
        self._frei_search_var.trace_add("write", lambda *_: self._filter_frei())
        ttk.Entry(toolbar, textvariable=self._frei_search_var,
                  width=28).pack(side="left", padx=(4, 8))
        ttk.Button(toolbar, text="Zusammenführen …",
                   command=lambda: self._merge_selected(self._tv_frei)
                   ).pack(side="left", padx=2)
        self._frei_status_var = tk.StringVar()
        ttk.Label(toolbar, textvariable=self._frei_status_var,
                  style="Dim.TLabel", width=18, anchor="e").pack(side="right", padx=(8, 4))

        toolbar.pack(fill="x", padx=8, pady=(8, 0))
        tv_frame.pack(fill="both", expand=True, padx=8, pady=(3, 8))
        _add_scrollbars(tv_frame, self._tv_frei)

        self._tv_frei.bind("<Double-1>", self._on_frei_double_click)
        self._tv_frei.bind("<Button-3>", self._on_frei_rclick)
        return frame

    def _load_frei(self):
        tv = self._tv_frei
        tv.delete(*tv.get_children())
        with db.read_connection() as conn:
            rows = db.get_all_participants(conn, provider="Frei")
        p = theme.current()
        tv.tag_configure("frei",   background=p["tag_frei"])
        tv.tag_configure("frei_z", background=p["tag_frei_z"])
        task_ids = self._task_marker(tv)
        for i, row in enumerate(rows):
            tag = ("has_task",) if row["id"] in task_ids else \
                  (("frei_z",) if i % 2 == 1 else ("frei",))
            tv.insert("", "end", iid=str(row["id"]),
                      values=_row_values(row, self._tv_frei_cols), tags=tag)
        self._frei_status_var.set(f"{len(rows)} frei")
        _autoresize_columns(tv)
        self._sorter_frei.reapply()

    def _filter_frei(self):
        term = self._frei_search_var.get().strip().lower()
        tv = self._tv_frei
        tv.delete(*tv.get_children())
        with db.read_connection() as conn:
            rows = db.get_all_participants(conn, provider="Frei")
        p = theme.current()
        tv.tag_configure("frei",   background=p["tag_frei"])
        tv.tag_configure("frei_z", background=p["tag_frei_z"])
        task_ids = self._task_marker(tv)
        i = 0
        for row in rows:
            if term and not any(term in str(row[k] or "").lower()
                                for k in ("name", "gsm", "plant", "konto", "tarif", "bemerkung")):
                continue
            tag = ("has_task",) if row["id"] in task_ids else \
                  (("frei_z",) if i % 2 == 1 else ("frei",))
            tv.insert("", "end", iid=str(row["id"]),
                      values=_row_values(row, self._tv_frei_cols), tags=tag)
            i += 1
        self._frei_status_var.set(f"{i} frei")

    def _on_frei_double_click(self, event):
        tv = self._tv_frei
        iid = tv.identify_row(event.y)
        if iid:
            EditorWindow(self.root, int(iid), on_save_callback=self.refresh_all)

    def _on_frei_rclick(self, event):
        tv = self._tv_frei
        region = tv.identify_region(event.x, event.y)
        on_heading = (
            region == "heading"
            or (region not in ("cell", "tree") and not tv.identify_row(event.y))
        )
        if on_heading and tv.identify_column(event.x):
            self._show_column_toggle_menu(event, tv, PARTICIPANT_COLUMNS, "frei")
            return "break"
        iid = tv.identify_row(event.y)
        if iid:
            tv.selection_set(iid)
        self._show_context_menu(event, tv, iid,
                                actions=[
                                    ("Bearbeiten",              lambda: EditorWindow(self.root, int(iid), on_save_callback=self.refresh_all)),
                                    None,
                                    ("Zu Vodafone verschieben", lambda: self._move_to_provider(int(iid), "Vodafone")),
                                    ("Zu Telekom verschieben",  lambda: self._move_to_provider(int(iid), "Telekom")),
                                    ("Zu O2 verschieben",       lambda: self._move_to_provider(int(iid), "O2")),
                                    ("Nach 'Ohne SIM' verschieben", lambda: self._move_to_provider(int(iid), "Ohne SIM")),
                                    None,
                                    ("Zu Aufgabe …",            lambda: self._create_task_dialog(int(iid))),
                                    None,
                                    ("GSM kopieren",            lambda: self._copy_cell(tv, iid, "gsm")),
                                    ("Name kopieren",           lambda: self._copy_cell(tv, iid, "name")),
                                    None,
                                    ("Eintrag löschen",         lambda: self._ctx_delete(int(iid))),
                                ])
        return "break"

    def _move_unmatched_to_provider(self, uid: int, provider: str):
        with db.read_connection() as conn:
            unmatched_rows = db.get_all_unmatched(conn)
        unmatched = next((r for r in unmatched_rows if r["id"] == uid), None)
        if not unmatched:
            return
        if not messagebox.askyesno(
            f"Nach '{provider}' verschieben",
            f"Gerät '{unmatched['geraet'] or '-'}' (GSM {unmatched['gsm'] or '-'}) "
            f"als Eintrag bei '{provider}' anlegen?",
            parent=self.root,
        ):
            return
        try:
            with db.transaction() as conn:
                pid = db.insert_participant(conn, {
                    "name": unmatched["benutzer"],
                    "gsm": unmatched["gsm"],
                    "syno": unmatched["geraet"],
                    "start_syno": unmatched["startdatum"],
                    "verified": 0,
                    "pruefung_grund": f"Als '{provider}' markiert (aus Nicht zugeordnet)",
                    "bemerkung": f"Quelle: {unmatched['quelle'] or '-'}",
                })
                db.set_provider(conn, pid, provider)
                db.delete_unmatched_device(conn, uid)
                db.log_import(conn, "GUI", provider.upper(),
                              f"Unmatched ID={uid} -> {provider} ID={pid}", participant_id=pid)
            self.refresh_all()
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc), parent=self.root)

    # ------------------------------------------------------------------
    # Tab: O2
    # ------------------------------------------------------------------

    def _build_tab_o2(self) -> ttk.Frame:
        frame = ttk.Frame(self.notebook)

        tv_frame = ttk.Frame(frame)
        self._tv_o2 = _make_treeview(tv_frame, PARTICIPANT_COLUMNS)
        self._tv_o2["selectmode"] = "extended"
        self._tv_o2_cols = [c[0] for c in PARTICIPANT_COLUMNS]
        self._sorter_o2 = self._make_sorter(self._tv_o2, "o2", ("o2", "o2_z"))

        toolbar = ttk.Frame(frame)
        ttk.Label(toolbar, text="Suche:").pack(side="left")
        self._o2_search_var = tk.StringVar()
        self._o2_search_var.trace_add("write", lambda *_: self._filter_o2())
        ttk.Entry(toolbar, textvariable=self._o2_search_var,
                  width=28).pack(side="left", padx=(4, 8))
        ttk.Button(toolbar, text="+ Neu", style="Accent.TButton",
                   command=self._new_participant).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Zusammenführen …",
                   command=lambda: self._merge_selected(self._tv_o2)
                   ).pack(side="left", padx=2)
        self._o2_status_var = tk.StringVar()
        ttk.Label(toolbar, textvariable=self._o2_status_var,
                  style="Dim.TLabel", width=18, anchor="e").pack(side="right", padx=(8, 4))

        toolbar.pack(fill="x", padx=8, pady=(8, 0))
        tv_frame.pack(fill="both", expand=True, padx=8, pady=(3, 8))
        _add_scrollbars(tv_frame, self._tv_o2)

        self._tv_o2.bind("<Double-1>", self._on_o2_double_click)
        self._tv_o2.bind("<Button-3>", self._on_o2_rclick)
        return frame

    def _load_o2(self):
        tv = self._tv_o2
        tv.delete(*tv.get_children())
        with db.read_connection() as conn:
            rows = db.get_all_participants(conn, provider="O2")
        p = theme.current()
        tv.tag_configure("o2",   background=p["tag_o2"])
        tv.tag_configure("o2_z", background=p["tag_o2_z"])
        task_ids = self._task_marker(tv)
        for i, row in enumerate(rows):
            tag = ("has_task",) if row["id"] in task_ids else \
                  (("o2_z",) if i % 2 == 1 else ("o2",))
            tv.insert("", "end", iid=str(row["id"]),
                      values=_row_values(row, self._tv_o2_cols), tags=tag)
        self._o2_status_var.set(f"{len(rows)} Teilnehmer")
        _autoresize_columns(tv)
        self._sorter_o2.reapply()

    def _filter_o2(self):
        term = self._o2_search_var.get().strip().lower()
        tv = self._tv_o2
        tv.delete(*tv.get_children())
        with db.read_connection() as conn:
            rows = db.get_all_participants(conn, provider="O2")
        p = theme.current()
        tv.tag_configure("o2",   background=p["tag_o2"])
        tv.tag_configure("o2_z", background=p["tag_o2_z"])
        tv.tag_configure("task_reminder", background=p["tag_task"])
        task_ids = self._task_marker(tv)
        fields = ("name", "gsm", "plant", "konto", "tarif", "bemerkung")
        i = 0
        shown_ids = set()
        for row in rows:
            if term and not any(term in str(row[k] or "").lower() for k in fields):
                continue
            tag = ("has_task",) if row["id"] in task_ids else \
                  (("o2_z",) if i % 2 == 1 else ("o2",))
            tv.insert("", "end", iid=str(row["id"]),
                      values=_row_values(row, self._tv_o2_cols), tags=tag)
            shown_ids.add(row["id"])
            i += 1
        if term:
            with db.read_connection() as conn:
                task_rows = db.get_participants_with_open_tasks(conn)
            for row in task_rows:
                if row["id"] in shown_ids:
                    continue
                if any(term in str(row[k] or "").lower() for k in fields):
                    tv.insert("", "end", iid=str(row["id"]),
                              values=_row_values(row, self._tv_o2_cols),
                              tags=("has_task",))
                    i += 1
        self._o2_status_var.set(f"{i} Teilnehmer")

    def _on_o2_double_click(self, event):
        tv = self._tv_o2
        iid = tv.identify_row(event.y)
        if iid:
            EditorWindow(self.root, int(iid), on_save_callback=self.refresh_all)

    def _on_o2_rclick(self, event):
        tv = self._tv_o2
        region = tv.identify_region(event.x, event.y)
        on_heading = (
            region == "heading"
            or (region not in ("cell", "tree") and not tv.identify_row(event.y))
        )
        if on_heading and tv.identify_column(event.x):
            self._show_column_toggle_menu(event, tv, PARTICIPANT_COLUMNS, "o2")
            return "break"
        iid = tv.identify_row(event.y)
        if iid:
            tv.selection_set(iid)
        self._show_context_menu(event, tv, iid,
                                actions=[
                                    ("Bearbeiten",              lambda: EditorWindow(self.root, int(iid), on_save_callback=self.refresh_all)),
                                    None,
                                    ("Zu Vodafone verschieben", lambda: self._move_to_provider(int(iid), "Vodafone")),
                                    ("Zu Telekom verschieben",  lambda: self._move_to_provider(int(iid), "Telekom")),
                                    ("Nach 'Ohne SIM' verschieben", lambda: self._move_to_provider(int(iid), "Ohne SIM")),
                                    ("Nach 'Frei' verschieben", lambda: self._move_to_provider(int(iid), "Frei")),
                                    None,
                                    ("Zu Aufgabe …",            lambda: self._create_task_dialog(int(iid))),
                                    None,
                                    ("GSM kopieren",            lambda: self._copy_cell(tv, iid, "gsm")),
                                    ("Name kopieren",           lambda: self._copy_cell(tv, iid, "name")),
                                    None,
                                    ("Eintrag löschen",         lambda: self._ctx_delete(int(iid))),
                                ])
        return "break"

    # ------------------------------------------------------------------
    # Tab: Ohne SIM (Geräte ohne Mobilfunkvertrag, z. B. Teams-only)
    # ------------------------------------------------------------------

    def _build_tab_ohnesim(self) -> ttk.Frame:
        frame = ttk.Frame(self.notebook)

        tv_frame = ttk.Frame(frame)
        self._tv_ohnesim = _make_treeview(tv_frame, PARTICIPANT_COLUMNS)
        self._tv_ohnesim["selectmode"] = "extended"
        self._tv_ohnesim_cols = [c[0] for c in PARTICIPANT_COLUMNS]
        self._sorter_ohnesim = self._make_sorter(self._tv_ohnesim, "ohnesim",
                                                 ("ohnesim", "ohnesim_z"))

        toolbar = ttk.Frame(frame)
        ttk.Label(toolbar, text="Suche:").pack(side="left")
        self._ohnesim_search_var = tk.StringVar()
        self._ohnesim_search_var.trace_add("write", lambda *_: self._filter_ohnesim())
        ttk.Entry(toolbar, textvariable=self._ohnesim_search_var,
                  width=28).pack(side="left", padx=(4, 8))
        ttk.Button(toolbar, text="+ Neu", style="Accent.TButton",
                   command=self._new_participant).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Zusammenführen …",
                   command=lambda: self._merge_selected(self._tv_ohnesim)
                   ).pack(side="left", padx=2)
        self._ohnesim_status_var = tk.StringVar()
        ttk.Label(toolbar, textvariable=self._ohnesim_status_var,
                  style="Dim.TLabel", width=18, anchor="e").pack(side="right", padx=(8, 4))

        toolbar.pack(fill="x", padx=8, pady=(8, 0))
        tv_frame.pack(fill="both", expand=True, padx=8, pady=(3, 8))
        _add_scrollbars(tv_frame, self._tv_ohnesim)

        self._tv_ohnesim.bind("<Double-1>", self._on_ohnesim_double_click)
        self._tv_ohnesim.bind("<Button-3>", self._on_ohnesim_rclick)
        return frame

    def _load_ohnesim(self):
        tv = self._tv_ohnesim
        tv.delete(*tv.get_children())
        with db.read_connection() as conn:
            rows = db.get_all_participants(conn, provider="Ohne SIM")
        p = theme.current()
        tv.tag_configure("ohnesim",   background=p["tag_ohnesim"])
        tv.tag_configure("ohnesim_z", background=p["tag_ohnesim_z"])
        task_ids = self._task_marker(tv)
        for i, row in enumerate(rows):
            tag = ("has_task",) if row["id"] in task_ids else \
                  (("ohnesim_z",) if i % 2 == 1 else ("ohnesim",))
            tv.insert("", "end", iid=str(row["id"]),
                      values=_row_values(row, self._tv_ohnesim_cols), tags=tag)
        self._ohnesim_status_var.set(f"{len(rows)} Teilnehmer")
        _autoresize_columns(tv)
        self._sorter_ohnesim.reapply()

    def _filter_ohnesim(self):
        term = self._ohnesim_search_var.get().strip().lower()
        tv = self._tv_ohnesim
        tv.delete(*tv.get_children())
        with db.read_connection() as conn:
            rows = db.get_all_participants(conn, provider="Ohne SIM")
        p = theme.current()
        tv.tag_configure("ohnesim",   background=p["tag_ohnesim"])
        tv.tag_configure("ohnesim_z", background=p["tag_ohnesim_z"])
        task_ids = self._task_marker(tv)
        fields = ("name", "gsm", "plant", "konto", "tarif", "bemerkung")
        i = 0
        shown_ids = set()
        for row in rows:
            if term and not any(term in str(row[k] or "").lower() for k in fields):
                continue
            tag = ("has_task",) if row["id"] in task_ids else \
                  (("ohnesim_z",) if i % 2 == 1 else ("ohnesim",))
            tv.insert("", "end", iid=str(row["id"]),
                      values=_row_values(row, self._tv_ohnesim_cols), tags=tag)
            shown_ids.add(row["id"])
            i += 1
        if term:
            with db.read_connection() as conn:
                task_rows = db.get_participants_with_open_tasks(conn)
            for row in task_rows:
                if row["id"] in shown_ids:
                    continue
                if any(term in str(row[k] or "").lower() for k in fields):
                    tv.insert("", "end", iid=str(row["id"]),
                              values=_row_values(row, self._tv_ohnesim_cols),
                              tags=("has_task",))
                    i += 1
        self._ohnesim_status_var.set(f"{i} Teilnehmer")

    def _on_ohnesim_double_click(self, event):
        tv = self._tv_ohnesim
        iid = tv.identify_row(event.y)
        if iid:
            EditorWindow(self.root, int(iid), on_save_callback=self.refresh_all)

    def _on_ohnesim_rclick(self, event):
        tv = self._tv_ohnesim
        region = tv.identify_region(event.x, event.y)
        on_heading = (
            region == "heading"
            or (region not in ("cell", "tree") and not tv.identify_row(event.y))
        )
        if on_heading and tv.identify_column(event.x):
            self._show_column_toggle_menu(event, tv, PARTICIPANT_COLUMNS, "ohnesim")
            return "break"
        iid = tv.identify_row(event.y)
        if iid:
            tv.selection_set(iid)
        self._show_context_menu(event, tv, iid,
                                actions=[
                                    ("Bearbeiten",              lambda: EditorWindow(self.root, int(iid), on_save_callback=self.refresh_all)),
                                    None,
                                    ("Zu Vodafone verschieben", lambda: self._move_to_provider(int(iid), "Vodafone")),
                                    ("Zu Telekom verschieben",  lambda: self._move_to_provider(int(iid), "Telekom")),
                                    ("Zu O2 verschieben",       lambda: self._move_to_provider(int(iid), "O2")),
                                    ("Nach 'Frei' verschieben", lambda: self._move_to_provider(int(iid), "Frei")),
                                    None,
                                    ("Zu Aufgabe …",            lambda: self._create_task_dialog(int(iid))),
                                    None,
                                    ("GSM kopieren",            lambda: self._copy_cell(tv, iid, "gsm")),
                                    ("Name kopieren",           lambda: self._copy_cell(tv, iid, "name")),
                                    None,
                                    ("Eintrag löschen",         lambda: self._ctx_delete(int(iid))),
                                ])
        return "break"

    # ------------------------------------------------------------------
    # Tab 2: Offene Prüfungen
    # ------------------------------------------------------------------

    def _build_tab_open_checks(self) -> ttk.Frame:
        frame = ttk.Frame(self.notebook)

        tv_frame = ttk.Frame(frame)
        self._tv_open = _make_treeview(tv_frame, OPEN_CHECK_COLUMNS)
        self._tv_open["selectmode"] = "extended"
        self._tv_open_cols = [c[0] for c in OPEN_CHECK_COLUMNS]
        _s2 = settings_store.get().get("sort_state", {}).get("open_checks")
        self._sorter_open = _Sorter(
            self._tv_open, OPEN_CHECK_COLUMNS,
            on_change=lambda c, r: self._save_sort("open_checks", c, r),
            initial_state=(_s2["col"], _s2["rev"]) if _s2 else None,
            stripe=(None, "zebra"),
        )

        toolbar = ttk.Frame(frame)
        ttk.Button(toolbar, text="Als geprüft markieren ✓", style="Accent.TButton",
                   command=self._mark_verified).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Bearbeiten",
                   command=self._edit_open_check).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Zusammenführen …",
                   command=lambda: self._merge_selected(self._tv_open)
                   ).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Label(toolbar, text="Suche:").pack(side="left", padx=(0, 2))
        self._open_search_var = tk.StringVar()
        self._open_search_var.trace_add("write", lambda *_: self._filter_open_checks())
        ttk.Entry(toolbar, textvariable=self._open_search_var,
                  width=24).pack(side="left", padx=(0, 4))
        self._open_count_var = tk.StringVar()
        ttk.Label(toolbar, textvariable=self._open_count_var,
                  style="Dim.TLabel").pack(side="right")

        toolbar.pack(fill="x", padx=6, pady=(6, 0))
        tv_frame.pack(fill="both", expand=True, padx=6, pady=(2, 6))

        _add_scrollbars(tv_frame, self._tv_open)

        self._tv_open.bind("<Double-1>", self._on_open_double_click)
        self._tv_open.bind("<Button-3>", self._on_open_rclick)
        return frame

    # ------------------------------------------------------------------
    # Tab 3: Nicht zugeordnet
    # ------------------------------------------------------------------

    def _build_tab_unmatched(self) -> ttk.Frame:
        frame = ttk.Frame(self.notebook)

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", padx=6, pady=(6, 0))
        ttk.Button(toolbar, text="Manuell zuordnen …", style="Accent.TButton",
                   command=self._assign_unmatched).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Eintrag löschen",    command=self._delete_unmatched).pack(side="left", padx=2)

        tv_frame = ttk.Frame(frame)
        tv_frame.pack(fill="both", expand=True, padx=6, pady=6)

        self._tv_unmatched = _make_treeview(tv_frame, UNMATCHED_COLUMNS)
        self._tv_unmatched_cols = [c[0] for c in UNMATCHED_COLUMNS]
        _add_scrollbars(tv_frame, self._tv_unmatched)
        self._tv_unmatched.bind("<Button-3>", self._on_unmatched_rclick)

        return frame

    def _on_unmatched_rclick(self, event):
        tv = self._tv_unmatched
        iid = tv.identify_row(event.y)
        if iid:
            tv.selection_set(iid)
        self._show_context_menu(event, tv, iid,
                                actions=[
                                    ("Manuell zuordnen …",      lambda: self._assign_unmatched()),
                                    ("Nach 'Frei' verschieben", lambda: self._move_unmatched_to_provider(int(iid), "Frei")),
                                    ("Nach O2 verschieben",     lambda: self._move_unmatched_to_provider(int(iid), "O2")),
                                    ("Nach 'Ohne SIM' verschieben", lambda: self._move_unmatched_to_provider(int(iid), "Ohne SIM")),
                                    None,
                                    ("Zu Aufgabe …",       lambda: self._create_task_from_unmatched(int(iid))),
                                    None,
                                    ("Eintrag löschen",    lambda: self._delete_unmatched()),
                                ])
        return "break"

    # ------------------------------------------------------------------
    # Tab: Duplikate
    # ------------------------------------------------------------------

    def _build_tab_duplicates(self) -> ttk.Frame:
        frame = ttk.Frame(self.notebook)

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", padx=6, pady=(6, 0))
        ttk.Button(toolbar, text="Aktualisieren", command=self._load_duplicates).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Bearbeiten",    command=self._edit_duplicate).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Zusammenführen …", command=self._merge_duplicates).pack(side="left", padx=2)
        self._dup_count_var = tk.StringVar(value="")
        ttk.Label(toolbar, textvariable=self._dup_count_var,
                  style="Dim.TLabel").pack(side="right")

        tv_frame = ttk.Frame(frame)
        tv_frame.pack(fill="both", expand=True, padx=6, pady=6)
        self._tv_duplicates = _make_treeview(tv_frame, DUPLICATE_COLUMNS)
        self._tv_duplicates["selectmode"] = "extended"
        self._tv_dup_cols   = [c[0] for c in DUPLICATE_COLUMNS]
        _add_scrollbars(tv_frame, self._tv_duplicates)
        self._tv_duplicates.bind("<Double-1>", lambda e: self._edit_duplicate())
        self._tv_duplicates.bind("<Button-3>", self._on_duplicates_rclick)
        return frame

    def _on_duplicates_rclick(self, event):
        tv = self._tv_duplicates
        iid = tv.identify_row(event.y)
        if iid:
            tv.selection_set(iid)
        self._show_context_menu(event, tv, iid,
                                actions=[
                                    ("Bearbeiten",   lambda: EditorWindow(self.root, int(iid), on_save_callback=self.refresh_all)),
                                    None,
                                    ("Zu Aufgabe …", lambda: self._create_task_dialog(int(iid))),
                                ])
        return "break"

    # ------------------------------------------------------------------
    # Tab: Statistik
    # ------------------------------------------------------------------

    def _build_tab_statistics(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent)

        # Oberer Bereich: Kennzahl-Kacheln (flache Karten)
        card_frame = ttk.Frame(frame, padding=(8, 10, 8, 6))
        card_frame.pack(fill="x")
        p = theme.current()
        self._stat_labels: dict[str, tk.StringVar] = {}
        self._stat_tile_refs: list[tuple[tk.Widget, str]] = []
        for key, title in [
            ("total",        "Teilnehmer gesamt"),
            ("verified",     "Geprüft"),
            ("zur_pruefung", "Zur Prüfung"),
            ("ohne_gsm",     "Ohne GSM"),
            ("mit_syno",     "Mit Syno-Gerät"),
            ("abgelaufen",   "Verträge abgelaufen"),
        ]:
            var = tk.StringVar(value="–")
            self._stat_labels[key] = var
            cell = tk.Frame(card_frame, bg=p["tile_bg"],
                            highlightbackground=p["tile_border_color"],
                            highlightthickness=1)
            cell.pack(side="left", padx=(0, 10), pady=2)
            num = tk.Label(cell, textvariable=var, font=("Segoe UI", 20, "bold"),
                           fg=p["accent"], bg=p["tile_bg"])
            num.pack(padx=18, pady=(10, 0))
            lbl = tk.Label(cell, text=title, font=("Segoe UI", 9),
                           fg=p["tile_fg_dim"], bg=p["tile_bg"])
            lbl.pack(padx=18, pady=(0, 10))
            self._stat_tile_refs += [(cell, "tile"), (num, "num"), (lbl, "lbl")]
            if key == "abgelaufen":
                for w in (cell, num, lbl):
                    w.configure(cursor="hand2")
                    w.bind("<Button-1>", lambda e: self._show_expired_contracts())
                lbl.configure(font=("Segoe UI", 9, "underline"))

        # Mittlerer Bereich: Ablaufende Verträge (90 Tage)
        mid = ttk.Frame(frame)
        mid.pack(fill="both", expand=True, padx=8, pady=4)
        mid.columnconfigure(0, weight=1)
        mid.columnconfigure(1, weight=1)
        mid.rowconfigure(0, weight=1)

        ablauf_frame = ttk.LabelFrame(mid, text="Verträge ablaufend (90 Tage)", padding=4)
        ablauf_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        ablauf_cols = ("name", "plant", "vertragsende")
        self._tv_ablauf = ttk.Treeview(ablauf_frame, columns=ablauf_cols, show="headings", height=12)
        self._tv_ablauf.heading("name",         text="Name")
        self._tv_ablauf.heading("plant",        text="Werk")
        self._tv_ablauf.heading("vertragsende", text="Vertragsende")
        self._tv_ablauf.column("name",         width=160)
        self._tv_ablauf.column("plant",        width=80)
        self._tv_ablauf.column("vertragsende", width=100)
        p = theme.current()
        self._tv_ablauf.tag_configure("soon",    background=p["tag_soon"])
        self._tv_ablauf.tag_configure("urgent",  background=p["tag_urgent"])
        self._tv_ablauf.tag_configure("telekom", background=p["tag_telekom"])
        ys_a = ttk.Scrollbar(ablauf_frame, orient="vertical", command=self._tv_ablauf.yview)
        self._tv_ablauf.configure(yscrollcommand=ys_a.set)
        self._tv_ablauf.pack(side="left", fill="both", expand=True)
        ys_a.pack(side="right", fill="y")

        # Rechts: Werke als horizontale Balken
        werk_frame = ttk.LabelFrame(mid, text="Teilnehmer je Werk", padding=4)
        werk_frame.grid(row=0, column=1, sticky="nsew")
        self._stat_canvas = tk.Canvas(werk_frame,
                                      background=theme.current()["stat_canvas_bg"],
                                      highlightthickness=0)
        self._stat_canvas.pack(fill="both", expand=True)

        ttk.Button(frame, text="Aktualisieren", command=self._load_statistics).pack(pady=4)
        return frame

    # ------------------------------------------------------------------
    # Tab 5: Importhistorie
    # ------------------------------------------------------------------

    def _build_tab_import_log(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent)

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", padx=6, pady=(6, 0))
        ttk.Button(toolbar, text="Aktualisieren",         command=self._refresh_import_log).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Als Datei speichern …", command=self._save_log).pack(side="left", padx=2)

        text_frame = ttk.Frame(frame)
        text_frame.pack(fill="both", expand=True, padx=6, pady=6)

        p = theme.current()
        self._log_text = tk.Text(text_frame, wrap="none", font=("Courier New", 9),
                                 state="disabled",
                                 background=p["log_bg"], foreground=p["log_fg"])
        ys = ttk.Scrollbar(text_frame, orient="vertical",   command=self._log_text.yview)
        xs = ttk.Scrollbar(text_frame, orient="horizontal", command=self._log_text.xview)
        self._log_text.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self._log_text.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)

        return frame

    # ------------------------------------------------------------------
    # Tab: Audit-Log (nur Admin)
    # ------------------------------------------------------------------

    def _build_tab_audit_log(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent)
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", padx=6, pady=(6, 0))
        ttk.Button(toolbar, text="Aktualisieren",
                   command=self._load_audit_log).pack(side="left", padx=2)

        tv_frame = ttk.Frame(frame)
        tv_frame.pack(fill="both", expand=True, padx=6, pady=6)
        cols = [
            ("zeitpunkt", "Zeitpunkt",   140),
            ("username",  "Benutzer",    110),
            ("aktion",    "Aktion",      120),
            ("details",   "Details",     380),
        ]
        self._tv_audit = ttk.Treeview(tv_frame,
                                      columns=[c[0] for c in cols],
                                      show="headings", selectmode="browse")
        for col_id, heading, width in cols:
            self._tv_audit.heading(col_id, text=heading)
            self._tv_audit.column(col_id, width=width, minwidth=40)
        ys = ttk.Scrollbar(tv_frame, orient="vertical",   command=self._tv_audit.yview)
        xs = ttk.Scrollbar(tv_frame, orient="horizontal", command=self._tv_audit.xview)
        self._tv_audit.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self._tv_audit.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        tv_frame.rowconfigure(0, weight=1)
        tv_frame.columnconfigure(0, weight=1)
        return frame

    def _load_audit_log(self):
        if not hasattr(self, "_tv_audit"):
            return
        tv = self._tv_audit
        tv.delete(*tv.get_children())
        with db.read_connection() as conn:
            rows = db.get_audit_log(conn, limit=2000)
        for row in rows:
            tv.insert("", "end", values=(
                row["zeitpunkt"],
                row["username"] or "–",
                row["aktion"],
                row["details"] or "",
            ))

    # ------------------------------------------------------------------
    # Tab: Unvollständige Einträge
    # ------------------------------------------------------------------

    def _build_tab_incomplete(self) -> ttk.Frame:
        frame = ttk.Frame(self.notebook)

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", padx=6, pady=(6, 0))
        ttk.Button(toolbar, text="Bearbeiten", command=self._edit_incomplete).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Zusammenführen …",
                   command=lambda: self._merge_selected(self._tv_incomplete)
                   ).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Aktualisieren", command=self._load_incomplete).pack(side="left", padx=2)
        self._incomplete_count_var = tk.StringVar()
        ttk.Label(toolbar, textvariable=self._incomplete_count_var,
                  style="Dim.TLabel").pack(side="right")

        tv_frame = ttk.Frame(frame)
        tv_frame.pack(fill="both", expand=True, padx=6, pady=6)

        self._tv_incomplete = _make_treeview(tv_frame, PARTICIPANT_COLUMNS)
        self._tv_incomplete["selectmode"] = "extended"
        self._tv_incomplete_cols = [c[0] for c in PARTICIPANT_COLUMNS]
        p = theme.current()
        self._tv_incomplete.tag_configure("missing_gsm",   background=p["tag_missing_gsm"])
        self._tv_incomplete.tag_configure("missing_plant", background=p["tag_missing_plant"])
        self._tv_incomplete.tag_configure("missing_konto", background=p["tag_missing_konto"])
        _Sorter(self._tv_incomplete, PARTICIPANT_COLUMNS)
        _add_scrollbars(tv_frame, self._tv_incomplete)
        self._tv_incomplete.bind("<Double-1>", lambda e: self._edit_incomplete())
        self._tv_incomplete.bind("<Button-3>", self._on_incomplete_rclick)

        # Legende
        leg = ttk.Frame(frame)
        leg.pack(fill="x", padx=6, pady=(0, 4))
        p = theme.current()
        for key, label_text in [
            ("legend_bg_gsm",   "Kein GSM"),
            ("legend_bg_plant", "Kein Werk"),
            ("legend_bg_konto", "Kein Konto"),
        ]:
            lbl = tk.Label(leg, text=f"  {label_text}  ",
                           background=p[key], foreground=p["legend_fg"],
                           relief="flat", font=("Segoe UI", 8))
            lbl.pack(side="left", padx=2)
            self._incomplete_legend_refs.append((lbl, key))

        return frame

    # ------------------------------------------------------------------
    # Tab: Werk-Übersicht
    # ------------------------------------------------------------------

    def _build_tab_werk_overview(self) -> ttk.Frame:
        frame = ttk.Frame(self.notebook)

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", padx=6, pady=(6, 0))
        ttk.Button(toolbar, text="Aktualisieren", command=self._load_werk_overview).pack(side="left", padx=2)

        cols = [
            ("werk",          "Werk",              140),
            ("gesamt",        "Gesamt",             70),
            ("ungeprueft",    "Ungeprüft",          80),
            ("ohne_vodafone", "Ohne Vodafone",     100),
        ]
        tv_frame = ttk.Frame(frame)
        tv_frame.pack(fill="both", expand=True, padx=6, pady=6)

        self._tv_werk = ttk.Treeview(tv_frame, columns=[c[0] for c in cols],
                                     show="headings", selectmode="browse")
        for col_id, heading, width in cols:
            self._tv_werk.heading(col_id, text=heading)
            self._tv_werk.column(col_id, width=width, anchor="center" if col_id != "werk" else "w")

        self._tv_werk.tag_configure("warn", background=theme.current()["tag_warn"])

        ys = ttk.Scrollbar(tv_frame, orient="vertical", command=self._tv_werk.yview)
        self._tv_werk.configure(yscrollcommand=ys.set)
        self._tv_werk.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        tv_frame.rowconfigure(0, weight=1)
        tv_frame.columnconfigure(0, weight=1)

        # Summenzeile
        self._werk_summary_var = tk.StringVar()
        ttk.Label(frame, textvariable=self._werk_summary_var,
                  style="Dim.TLabel").pack(padx=6, pady=(0, 4), anchor="w")

        return frame

    # ------------------------------------------------------------------
    # Daten laden
    # ------------------------------------------------------------------

    # Sichere Standardwerte, damit Filter-Methoden nie AttributeError werfen
    _open_data: list = []

    def refresh_all(self):
        for fn in (self._load_participants, self._load_neuvertrag, self._load_telekom, self._load_o2,
                   self._load_ohnesim, self._load_frei,
                   self._load_open_checks,
                   self._load_unmatched,
                   self._load_incomplete, self._load_werk_overview,
                   self._load_duplicates, self._load_statistics,
                   self._refresh_import_log,
                   self._load_audit_log):
            try:
                fn()
            except Exception as exc:
                logger.error("refresh_all: %s fehlgeschlagen: %s", fn.__name__, exc)
        self._update_tab_badges()
        self._update_statusbar()
        self._update_task_button()
        self._retag_all()

    def _task_marker(self, tv) -> set:
        """Konfiguriert die auffällige 'has_task'-Markierung auf tv und liefert
        die IDs aller Teilnehmer mit offener Aufgabe."""
        p = theme.current()
        tv.tag_configure("has_task", background=p["tag_has_task_bg"],
                         foreground=p["tag_has_task_fg"],
                         font=("Segoe UI", 10, "bold"))
        with db.read_connection() as conn:
            return db.get_open_task_participant_ids(conn)

    def _load_participants(self, rows=None, extra_ids=None):
        tv = self._tv_participants
        tv.delete(*tv.get_children())
        with db.read_connection() as conn:
            if rows is None:
                rows = db.get_all_participants(conn)
            task_ids = db.get_open_task_participant_ids(conn)
        extra_ids = extra_ids or set()
        p = theme.current()
        tv.tag_configure("zebra",         background=p["tag_zebra"])
        tv.tag_configure("task_reminder", background=p["tag_task"])
        tv.tag_configure("has_task", background=p["tag_has_task_bg"],
                         foreground=p["tag_has_task_fg"],
                         font=("Segoe UI", 10, "bold"))
        for i, row in enumerate(rows):
            z = i % 2 == 1
            if row["id"] in task_ids:
                # Offene Aufgabe → auffällig rot (hat Vorrang)
                tag = ("has_task",)
            elif row["id"] in extra_ids:
                tag = ("task_reminder",)
            else:
                tag = ("zebra",) if z else ()
            tv.insert("", "end", iid=str(row["id"]),
                      values=_row_values(row, self._tv_participant_cols),
                      tags=tag)
        self._status_var.set(f"{len(tv.get_children())} Teilnehmer")
        _autoresize_columns(tv)
        self._sorter_participants.reapply()

    # Cache für Filter
    _all_participants_cache: list = []

    def _apply_participant_filter(self):
        term = self._search_var.get().strip().lower()

        with db.read_connection() as conn:
            rows = db.get_all_participants(conn)

        extra_ids: set = set()
        if term:
            rows = [r for r in rows if any(
                term in str(r[k] or "").lower()
                for k in ("name", "gsm", "plant", "konto", "tarif", "bemerkung", "syno", "syno2")
            )]
            existing_ids = {r["id"] for r in rows}
            with db.read_connection() as conn:
                task_rows = db.get_participants_with_open_tasks(conn)
            for r in task_rows:
                if r["id"] in existing_ids:
                    continue
                if any(term in str(r[k] or "").lower()
                       for k in ("name", "gsm", "plant", "konto", "tarif", "bemerkung", "syno", "syno2")):
                    rows.append(r)
                    extra_ids.add(r["id"])
        self._load_participants(rows, extra_ids=extra_ids)

    def _reset_filter(self):
        self._search_var.set("")
        self._load_participants()

    def _load_open_checks(self):
        tv = self._tv_open
        tv.delete(*tv.get_children())
        with db.read_connection() as conn:
            self._open_data = db.get_unverified_participants(conn)
        p = theme.current()
        tv.tag_configure("zebra", background=p["tag_zebra"])
        task_ids = self._task_marker(tv)
        for i, row in enumerate(self._open_data):
            tag = ("has_task",) if row["id"] in task_ids else \
                  (("zebra",) if i % 2 == 1 else ())
            tv.insert("", "end", iid=str(row["id"]),
                      values=_row_values(row, self._tv_open_cols), tags=tag)
        self._open_count_var.set(f"{len(self._open_data)} offene Prüfungen")
        _autoresize_columns(tv)
        self._sorter_open.reapply()

    def _filter_open_checks(self):
        term = self._open_search_var.get().strip().lower()
        tv = self._tv_open
        tv.delete(*tv.get_children())
        p = theme.current()
        tv.tag_configure("task_reminder", background=p["tag_task"])
        task_ids = self._task_marker(tv)
        fields = ("name", "gsm", "plant", "konto", "bemerkung")
        shown_ids = set()
        for row in self._open_data:
            if term and not any(term in str(row[k] or "").lower() for k in fields):
                continue
            tag = ("has_task",) if row["id"] in task_ids else ()
            tv.insert("", "end", iid=str(row["id"]),
                      values=_row_values(row, self._tv_open_cols), tags=tag)
            shown_ids.add(row["id"])
        if term:
            with db.read_connection() as conn:
                task_rows = db.get_participants_with_open_tasks(conn)
            for row in task_rows:
                if row["id"] in shown_ids:
                    continue
                if any(term in str(row[k] or "").lower() for k in fields):
                    tv.insert("", "end", iid=str(row["id"]),
                              values=_row_values(row, self._tv_open_cols),
                              tags=("has_task",))

    def _load_unmatched(self):
        tv = self._tv_unmatched
        tv.delete(*tv.get_children())
        with db.read_connection() as conn:
            data = db.get_all_unmatched(conn)
        for row in data:
            tv.insert("", "end", iid=str(row["id"]),
                      values=_row_values(row, self._tv_unmatched_cols))
        _autoresize_columns(tv)

    def _refresh_import_log(self):
        with db.read_connection() as conn:
            rows = db.get_import_log(conn, limit=2000)
        lines = [f"{r['zeitpunkt']}  [{r['quelle']}]  {r['aktion']}: {r['details'] or ''}"
                 for r in rows]
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.insert("1.0", "\n".join(lines))
        self._log_text.configure(state="disabled")

    def _load_incomplete(self):
        tv = self._tv_incomplete
        tv.delete(*tv.get_children())
        with db.read_connection() as conn:
            rows = db.get_incomplete_participants(conn)
        tv.tag_configure("telekom", background=theme.current()["tag_telekom"])
        task_ids = self._task_marker(tv)
        for row in rows:
            if row["id"] in task_ids:
                tag = ("has_task",)
            else:
                if not row["gsm"]:
                    tag = ("missing_gsm",)
                elif not row["plant"]:
                    tag = ("missing_plant",)
                else:
                    tag = ("missing_konto",)
                if _is_telekom(row):
                    tag = ("telekom",) + tag
            tv.insert("", "end", iid=str(row["id"]),
                      values=_row_values(row, self._tv_incomplete_cols), tags=tag)
        self._incomplete_count_var.set(f"{len(rows)} unvollständige Einträge")
        _autoresize_columns(tv)

    def _edit_incomplete(self):
        sel = self._tv_incomplete.selection()
        if not sel:
            messagebox.showinfo("Hinweis", "Bitte einen Eintrag auswählen.", parent=self.root)
            return
        EditorWindow(self.root, int(sel[0]), on_save_callback=self.refresh_all)

    def _load_werk_overview(self):
        tv = self._tv_werk
        tv.delete(*tv.get_children())
        with db.read_connection() as conn:
            rows = db.get_werk_overview(conn)
        gesamt_total = ungeprueft_total = ohne_voda_total = 0
        for row in rows:
            tag = ("warn",) if row["ungeprueft"] > 0 or row["ohne_vodafone"] > 0 else ()
            tv.insert("", "end", values=(
                row["werk"], row["gesamt"], row["ungeprueft"],
                row["ohne_vodafone"],
            ), tags=tag)
            gesamt_total    += row["gesamt"]
            ungeprueft_total += row["ungeprueft"]
            ohne_voda_total += row["ohne_vodafone"]
        self._werk_summary_var.set(
            f"Gesamt: {gesamt_total} Teilnehmer  |  "
            f"{ungeprueft_total} ungeprüft  |  "
            f"{ohne_voda_total} ohne Vodafone-Eintrag"
        )
        _autoresize_columns(tv)

    # ------------------------------------------------------------------
    # Teilnehmer-Tab
    # ------------------------------------------------------------------

    def _new_participant(self):
        EditorWindow(self.root, None, on_save_callback=self.refresh_all)

    # _on_participant_double_click is defined earlier (with inline-edit logic)

    # -- Inline-Edit -------------------------------------------------------

    _INLINE_EDITABLE = {"bemerkung", "tarif", "syno", "syno2", "plant"}

    def _on_participant_double_click(self, event):
        tv = self._tv_participants
        col = tv.identify_column(event.x)
        col_idx = int(col.replace("#", "")) - 1
        if not (0 <= col_idx < len(self._tv_participant_cols)):
            return
        col_key = self._tv_participant_cols[col_idx]
        sel = tv.selection()
        if not sel:
            return

        if col_key == "verified":
            self._toggle_verified(int(sel[0]), self._load_participants)
        elif col_key in self._INLINE_EDITABLE:
            self._start_inline_edit(tv, sel[0], col, col_key)
        else:
            EditorWindow(self.root, int(sel[0]), on_save_callback=self.refresh_all)

    def _start_inline_edit(self, tv: ttk.Treeview, iid: str,
                            col_id: str, col_key: str):
        bbox = tv.bbox(iid, col_id)
        if not bbox:
            return
        x, y, w, h = bbox
        current = tv.set(iid, col_id)
        old_val = current
        var = tk.StringVar(value=current)
        entry = ttk.Entry(tv, textvariable=var)
        entry.place(x=x, y=y, width=max(w, 120), height=h)
        entry.focus_set()
        entry.select_range(0, "end")

        def _save(event=None):
            if not entry.winfo_exists():
                return
            new_val = var.get().strip()
            pid = int(iid)
            try:
                with db.transaction() as conn:
                    db.update_participant_fields(conn, pid, {col_key: new_val or None})
                    db.log_import(conn, "GUI", "INLINE_EDIT",
                                  f"ID={pid} {col_key}={new_val!r}",
                                  participant_id=pid)
                tv.set(iid, col_id, new_val)
                if new_val != old_val:
                    self._show_undo_toast(pid, col_key, old_val)
            except Exception as exc:
                messagebox.showerror("Fehler", str(exc), parent=self.root)
            entry.destroy()

        def _cancel(event=None):
            if entry.winfo_exists():
                entry.destroy()

        entry.bind("<Return>",   _save)
        entry.bind("<FocusOut>", _save)
        entry.bind("<Escape>",   _cancel)

    def _show_undo_toast(self, pid: int, field: str, old_val: str):
        if hasattr(self, "_undo_toast") and self._undo_toast.winfo_exists():
            self._undo_toast.destroy()
        p = theme.current()
        toast = tk.Frame(self.root, bg=p["heading_bg"], relief="solid", bd=1)
        tk.Label(toast, text="Gespeichert  –", bg=p["heading_bg"],
                 fg=p["fg"], font=("Segoe UI", 9)).pack(side="left", padx=(8, 4), pady=4)
        undo_lbl = tk.Label(toast, text="Rückgängig", bg=p["heading_bg"],
                            fg=p["accent"], font=("Segoe UI", 9, "underline"),
                            cursor="hand2")
        undo_lbl.pack(side="left", padx=(0, 8), pady=4)
        toast.place(relx=0.5, rely=1.0, anchor="s", y=-34)
        self._undo_toast = toast

        def _undo(event=None):
            try:
                with db.transaction() as conn:
                    db.update_participant_fields(conn, pid, {field: old_val or None})
                    db.log_import(conn, "GUI", "UNDO_INLINE",
                                  f"ID={pid} {field} wiederhergestellt auf {old_val!r}",
                                  participant_id=pid)
                self._load_participants()
            except Exception as exc:
                messagebox.showerror("Fehler", str(exc), parent=self.root)
            if toast.winfo_exists():
                toast.destroy()
            try:
                self.root.unbind("<Control-z>")
            except Exception:
                pass

        undo_lbl.bind("<Button-1>", _undo)
        self.root.bind("<Control-z>", _undo)
        toast.after(5000, lambda: toast.destroy() if toast.winfo_exists() else None)

    # -- Kontextmenü -------------------------------------------------------

    def _on_participant_rclick(self, event):
        tv = self._tv_participants
        region = tv.identify_region(event.x, event.y)
        on_heading = (
            region == "heading"
            or (region not in ("cell", "tree") and not tv.identify_row(event.y))
        )
        if on_heading and tv.identify_column(event.x):
            self._show_column_toggle_menu(event, tv, PARTICIPANT_COLUMNS, "participants")
            return "break"
        iid = tv.identify_row(event.y)
        if iid:
            tv.selection_set(iid)
        self._show_context_menu(event, tv, iid,
                                actions=[
                                    ("Bearbeiten",            lambda: EditorWindow(self.root, int(iid), on_save_callback=self.refresh_all)),
                                    ("Als geprüft markieren", lambda: self._toggle_verified(int(iid), self._load_participants)),
                                    None,
                                    ("Zu Telekom verschieben", lambda: self._move_to_provider(int(iid), "Telekom")),
                                    ("Zu O2 verschieben",       lambda: self._move_to_provider(int(iid), "O2")),
                                    ("Nach 'Ohne SIM' verschieben", lambda: self._move_to_provider(int(iid), "Ohne SIM")),
                                    ("Nach 'Frei' verschieben", lambda: self._move_to_provider(int(iid), "Frei")),
                                    None,
                                    ("Kündigung erstellen …",           lambda: self._create_kuendigung(int(iid), "kuendigung")),
                                    ("Kündigung zurücknehmen …",        lambda: self._create_kuendigung(int(iid), "ruecknahme")),
                                    None,
                                    ("Zu Aufgabe …",          lambda: self._create_task_dialog(int(iid))),
                                    None,
                                    ("GSM kopieren",          lambda: self._copy_cell(tv, iid, "gsm")),
                                    ("Name kopieren",         lambda: self._copy_cell(tv, iid, "name")),
                                    None,
                                    ("Eintrag löschen",       lambda: self._ctx_delete(int(iid))),
                                ])
        return "break"

    def _create_kuendigung(self, pid: int, kind: str):
        with db.read_connection() as conn:
            row = db.get_participant_by_id(conn, pid)
        if row is None:
            messagebox.showerror("Fehler", "Teilnehmer nicht gefunden.", parent=self.root)
            return
        gsm = row["gsm"] or ""
        name = row["name"] or ""
        titel = "Kündigung erstellen" if kind == "kuendigung" else "Kündigung zurücknehmen"
        if not messagebox.askyesno(
            titel,
            f"{titel} für:\n\n  Name: {name or '-'}\n  GSM:  {gsm or '-'}\n\n"
            "Es wird ein PDF erzeugt und als Outlook-Entwurf geöffnet "
            "(noch nicht gesendet). Fortfahren?",
            parent=self.root,
        ):
            return
        try:
            pdf_path = kuendigung.create_and_open(kind, gsm, name=name)
        except FileNotFoundError as exc:
            messagebox.showerror("Vorlage fehlt", str(exc), parent=self.root)
            return
        except Exception as exc:
            logger.exception("Kündigungsschreiben fehlgeschlagen")
            messagebox.showerror(
                "Fehler",
                f"Schreiben konnte nicht erzeugt werden:\n{exc}\n\n"
                "Hinweis: Für die PDF-Erzeugung wird Microsoft Word,\n"
                "für den E-Mail-Entwurf Microsoft Outlook (Desktop) benötigt.",
                parent=self.root,
            )
            return
        with db.transaction() as conn:
            db.log_import(
                conn, "GUI", "KUENDIGUNG" if kind == "kuendigung" else "RUECKNAHME",
                f"ID={pid} GSM={gsm} Schreiben erzeugt: {pdf_path.name}",
                participant_id=pid,
            )
        messagebox.showinfo(
            titel, f"PDF erzeugt: {pdf_path.name}\nOutlook-Entwurf wurde geöffnet.",
            parent=self.root,
        )

    def _show_column_toggle_menu(self, event, tv: ttk.Treeview,
                                  columns: list, settings_key: str):
        cfg = settings_store.get()
        vis = cfg.setdefault("column_visibility", {}).setdefault(settings_key, {})
        orig_widths = {c[0]: c[2] for c in columns}

        def _save():
            settings_store.save(cfg)

        last_col = columns[-1][0]

        def _toggle(col_id, var):
            if var.get():
                tv.column(col_id, width=orig_widths[col_id],
                          minwidth=max(30, orig_widths[col_id] // 2),
                          stretch=(col_id == last_col))
                vis[col_id] = True
            else:
                tv.column(col_id, width=0, minwidth=0, stretch=False)
                vis[col_id] = False
            _save()

        p = theme.current()
        menu = tk.Menu(self.root, tearoff=0)
        try:
            menu.configure(bg=p["bg_widget"], fg=p["fg"],
                           activebackground=p["select_bg"],
                           activeforeground=p["select_fg"])
        except Exception:
            pass
        menu.add_command(label="Spalten ein-/ausblenden:", state="disabled")
        menu.add_separator()
        for col_id, heading, _ in columns:
            var = tk.BooleanVar(value=vis.get(col_id, True))
            menu.add_checkbutton(label=heading, variable=var,
                                 command=lambda c=col_id, v=var: _toggle(c, v))
        menu.tk_popup(event.x_root, event.y_root)

    def _show_context_menu(self, event, tv, iid, actions):
        menu = tk.Menu(self.root, tearoff=0)
        p = theme.current()
        try:
            menu.configure(bg=p["bg_widget"], fg=p["fg"],
                           activebackground=p["select_bg"],
                           activeforeground=p["select_fg"])
        except Exception:
            pass
        # "Zelle kopieren" – kopiert die angeklickte Zelle (in allen Tabs verfügbar)
        if iid:
            _col = tv.identify_column(event.x)
            menu.add_command(
                label="Zelle kopieren",
                command=lambda: self._copy_clicked_cell(tv, iid, _col))
            menu.add_separator()
        for item in actions:
            if item is None:
                menu.add_separator()
            else:
                label, cmd = item
                menu.add_command(label=label, command=cmd)
        menu.tk_popup(event.x_root, event.y_root)

    def _copy_cell(self, tv: ttk.Treeview, iid: str, col_key: str):
        idx = self._tv_participant_cols.index(col_key)
        val = tv.set(iid, tv["columns"][idx])
        self.root.clipboard_clear()
        self.root.clipboard_append(val)

    def _copy_clicked_cell(self, tv: ttk.Treeview, iid: str, col: str):
        """Kopiert den Inhalt der angeklickten Zelle in die Zwischenablage
        und zeigt eine kurze Bestätigung – tab-übergreifend."""
        try:
            idx = int(str(col).replace("#", "")) - 1
        except (TypeError, ValueError):
            return
        cols = tv["columns"]
        if not iid or not (0 <= idx < len(cols)):
            return
        val = tv.set(iid, cols[idx])
        self.root.clipboard_clear()
        self.root.clipboard_append(val or "")
        self._show_copy_toast(val)

    def _show_copy_toast(self, value: str):
        """Kleiner, selbst-verschwindender Hinweis 'Kopiert: …'."""
        if hasattr(self, "_copy_toast") and self._copy_toast.winfo_exists():
            self._copy_toast.destroy()
        shown = value if value else "(leer)"
        if len(shown) > 60:
            shown = shown[:57] + "…"
        p = theme.current()
        toast = tk.Frame(self.root, bg=p["heading_bg"], relief="solid", bd=1)
        tk.Label(toast, text=f"Kopiert:  {shown}", bg=p["heading_bg"],
                 fg=p["fg"], font=("Segoe UI", 9)).pack(padx=10, pady=4)
        toast.place(relx=0.5, rely=1.0, anchor="s", y=-34)
        self._copy_toast = toast
        toast.after(1800,
                    lambda: toast.destroy() if toast.winfo_exists() else None)

    # ------------------------------------------------------------------
    # Datenqualität
    # ------------------------------------------------------------------

    def _build_tab_quality(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent)
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", padx=8, pady=(8, 0))
        ttk.Button(toolbar, text="Erneut prüfen", style="Accent.TButton",
                   command=self._load_quality).pack(side="left")
        self._quality_count_var = tk.StringVar()
        ttk.Label(toolbar, textvariable=self._quality_count_var,
                  style="Dim.TLabel").pack(side="right")
        ttk.Label(frame, text="Doppelklick öffnet den Datensatz zum Bearbeiten.",
                  style="Dim.TLabel").pack(anchor="w", padx=8, pady=(4, 0))

        tv_frame = ttk.Frame(frame)
        tv_frame.pack(fill="both", expand=True, padx=8, pady=8)
        cols = [("kategorie", "Befund",   230),
                ("master_id", "Nr.",       50),
                ("name",      "Name",     170),
                ("provider",  "Register", 100),
                ("plant",     "Werk",      90),
                ("konto",     "Konto",     95),
                ("gsm",       "GSM",      120)]
        tv = ttk.Treeview(tv_frame, columns=[c[0] for c in cols],
                          show="headings", selectmode="browse")
        for col_id, heading, width in cols:
            tv.heading(col_id, text=heading)
            tv.column(col_id, width=width, minwidth=40)
        ys = ttk.Scrollbar(tv_frame, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=ys.set)
        tv.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        self._tv_quality = tv

        def _open(event=None):
            iid = tv.focus()
            if iid and iid.isdigit():
                EditorWindow(self.root, int(iid), on_save_callback=lambda: (
                    self.refresh_all(), self._load_quality()))
        tv.bind("<Double-1>", _open)
        return frame

    def _load_quality(self):
        tv = getattr(self, "_tv_quality", None)
        if tv is None:
            return
        tv.delete(*tv.get_children())
        p = theme.current()
        tv.tag_configure("kat", background=p["heading_bg"],
                         foreground=p["heading_fg"], font=("Segoe UI", 10, "bold"))
        konto_plant = settings_store.get().get("konto_plant", {})
        with db.read_connection() as conn:
            res = db.data_quality_check(conn, konto_plant)
        total = 0
        for kat, rows in res.items():
            # Kategorie-Kopfzeile
            tv.insert("", "end", iid=f"kat_{kat}", tags=("kat",),
                      values=(f"{kat}  ({len(rows)})", "", "", "", "", "", ""))
            for r in rows:
                total += 1
                tv.insert("", "end", iid=str(r["id"]),
                          values=("", r["master_id"] or "", r["name"] or "",
                                  r["provider"] or "", r["plant"] or "",
                                  r["konto"] or "", r["gsm"] or ""))
        self._quality_count_var.set(
            f"{total} Befund(e)" if total else "Keine Auffälligkeiten gefunden")

    # ------------------------------------------------------------------
    # Aufgaben
    # ------------------------------------------------------------------

    def _create_task_dialog(self, pid: int):
        """Kontextmenü 'Zu Aufgabe …': Teilnehmerdaten übernehmen + Kommentar."""
        with db.read_connection() as conn:
            part = db.get_participant_by_id(conn, pid)
        if part is None:
            messagebox.showerror("Fehler", "Teilnehmer nicht gefunden.", parent=self.root)
            return
        self._show_task_dialog({
            "id":    pid,
            "name":  part["name"], "gsm":   part["gsm"],
            "plant": part["plant"], "konto": part["konto"],
            "tarif": part["tarif"],
        })

    def _create_task_from_unmatched(self, uid: int):
        """'Zu Aufgabe …' im Tab 'Nicht zugeordnet' – Gerät ohne Teilnehmer-Bezug.

        Passt Name/GSM eindeutig zu einem bestehenden Teilnehmer, wird die
        Aufgabe automatisch mit diesem verknüpft (inkl. Werk/Konto/Tarif).
        """
        with db.read_connection() as conn:
            rows = db.get_all_unmatched(conn)
            row = next((r for r in rows if r["id"] == uid), None)
            if row is None:
                messagebox.showerror("Fehler", "Eintrag nicht gefunden.", parent=self.root)
                return
            match = db.find_unique_participant(conn, row["gsm"], row["benutzer"])
        if match is not None:
            self._show_task_dialog({
                "id":    match["id"],
                "name":  match["name"], "gsm":  match["gsm"],
                "plant": match["plant"], "konto": match["konto"],
                "tarif": match["tarif"],
                "geraet": row["geraet"],
                "hint":  f"Automatisch verknüpft mit Teilnehmer Nr. {match['master_id'] or match['id']}",
            })
        else:
            self._show_task_dialog({
                "id":    None,
                "name":  row["benutzer"], "gsm": row["gsm"],
                "plant": None, "konto": None, "tarif": None,
                "geraet": row["geraet"],
            })

    def _show_task_dialog(self, data: dict):
        """Dialog 'Aufgabe anlegen'. data: name/gsm/plant/konto/tarif,
        id = Teilnehmer-ID oder None, optional geraet (aus 'Nicht zugeordnet')."""
        s = auth.get_session()
        if not (s and s.can("write")):
            messagebox.showinfo("Keine Berechtigung",
                                "Zum Anlegen von Aufgaben ist Schreibzugriff nötig.",
                                parent=self.root)
            return

        win = tk.Toplevel(self.root)
        win.title("Aufgabe anlegen")
        win.transient(self.root)
        theme.center_window(win, 460, 340, self.root)
        win.grab_set()

        frame = ttk.Frame(win, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        info = [("Name:", data["name"] or ""),
                ("GSM:",  data["gsm"] or "")]
        if data.get("geraet"):
            info.append(("Gerät:", data["geraet"]))
        if data["id"] is not None:
            info += [("Werk:",  data["plant"] or ""),
                     ("Konto:", data["konto"] or ""),
                     ("Tarif:", data["tarif"] or "")]
        for r, (lbl, val) in enumerate(info):
            ttk.Label(frame, text=lbl, style="Dim.TLabel").grid(
                row=r, column=0, sticky="ne", padx=(0, 8), pady=1)
            ttk.Label(frame, text=val).grid(row=r, column=1, sticky="w", pady=1)

        base = len(info)
        if data.get("hint"):
            ttk.Label(frame, text="✓ " + data["hint"],
                      foreground=theme.current()["accent"]).grid(
                row=base, column=0, columnspan=2, sticky="w", pady=(6, 0))
            base += 1

        ttk.Label(frame, text="Aufgabe / Kommentar:").grid(
            row=base, column=0, columnspan=2, sticky="w", pady=(10, 2))
        p = theme.current()
        txt = tk.Text(frame, height=5, wrap="word", font=("Segoe UI", 10),
                      background=p["bg_widget"], foreground=p["fg"])
        txt.grid(row=base + 1, column=0, columnspan=2, sticky="nsew")
        frame.rowconfigure(base + 1, weight=1)
        if data.get("geraet"):
            txt.insert("1.0", f"Gerät: {data['geraet']}\n")

        # Fälligkeit + Priorität
        meta = ttk.Frame(frame)
        meta.grid(row=base + 2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Label(meta, text="Fällig am (TT.MM.JJJJ):").pack(side="left")
        faellig_var = tk.StringVar()
        ttk.Entry(meta, textvariable=faellig_var, width=12).pack(side="left", padx=(4, 12))
        prio_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(meta, text="Hohe Priorität", variable=prio_var).pack(side="left")

        btns = ttk.Frame(frame)
        btns.grid(row=base + 3, column=0, columnspan=2, sticky="e", pady=(10, 0))

        def _save(event=None):
            kommentar = txt.get("1.0", "end").strip()
            if not kommentar:
                messagebox.showinfo("Hinweis", "Bitte die Aufgabe beschreiben.", parent=win)
                return
            faellig = _parse_input_date(faellig_var.get())
            if faellig_var.get().strip() and not faellig:
                messagebox.showinfo("Hinweis",
                                    "Fälligkeitsdatum bitte als TT.MM.JJJJ angeben "
                                    "(oder leer lassen).", parent=win)
                return
            with db.transaction() as conn:
                db.create_task(conn, data, kommentar,
                               created_by=s.username if s else None,
                               faellig_am=faellig, prioritaet=1 if prio_var.get() else 0)
                db.log_import(conn, "Aufgabe", "CREATE",
                              f"Aufgabe für '{data['name']}' angelegt: {kommentar[:100]}",
                              participant_id=data["id"])
            win.destroy()
            self._refresh_tasks_window()
            self.refresh_all()   # rote Markierung in allen Tabs sofort zeigen

        ttk.Button(btns, text="Aufgabe anlegen", style="Accent.TButton",
                   command=_save).pack(side="left", padx=4)
        ttk.Button(btns, text="Abbrechen", command=win.destroy).pack(side="left")
        win.bind("<Escape>", lambda e: win.destroy())
        win.bind("<Control-s>", _save)
        txt.focus_set()

    def _refresh_tasks_window(self):
        """Aufgabenfenster neu laden, falls es geöffnet ist."""
        try:
            if self._tasks_win is not None and self._tasks_win.winfo_exists():
                self._tasks_reload()
        except Exception:
            pass

    def _open_tasks_window(self):
        if getattr(self, "_tasks_win", None) is not None and self._tasks_win.winfo_exists():
            self._tasks_win.lift()
            self._tasks_win.focus_set()
            self._tasks_reload()
            return

        win = tk.Toplevel(self.root)
        win.title("Aufgaben")
        theme.center_window(win, 980, 440, self.root)
        win.minsize(720, 300)
        self._tasks_win = win

        toolbar = ttk.Frame(win, padding=(8, 8, 8, 0))
        toolbar.pack(fill="x")
        show_done_var = tk.BooleanVar(value=False)
        count_var = tk.StringVar()

        tv_frame = ttk.Frame(win, padding=8)
        tv_frame.pack(fill="both", expand=True)
        cols = [("erledigt",   "Status",       60),
                ("prio",       "Prio",          45),
                ("faellig",    "Fällig",        90),
                ("name",       "Name",        150),
                ("gsm",        "GSM",         105),
                ("plant",      "Werk",         85),
                ("kommentar",  "Aufgabe",     300),
                ("created_at", "Angelegt",    100),
                ("created_by", "Von",          85),
                ("done_at",    "Erledigt am", 100)]
        tv = ttk.Treeview(tv_frame, columns=[c[0] for c in cols],
                          show="headings", selectmode="browse")
        for col_id, heading, width in cols:
            tv.heading(col_id, text=heading)
            tv.column(col_id, width=width, minwidth=40)
        ys = ttk.Scrollbar(tv_frame, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=ys.set)
        tv.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")

        p = theme.current()
        tv.tag_configure("done", foreground=p["fg_dim"])
        tv.tag_configure("overdue", background=p["tag_has_task_bg"],
                         foreground=p["tag_has_task_fg"], font=("Segoe UI", 10, "bold"))
        tv.tag_configure("soon", background=p["tag_soon"])

        tasks_by_id: dict[int, object] = {}
        full_rows: list = []
        search_var = tk.StringVar()
        sort_state = {"col": None, "rev": False}
        col_headings = {c[0]: c[1] for c in cols}

        def _g(row, key, default=None):
            return row[key] if key in row.keys() else default

        def _sort_key(row):
            col = sort_state["col"]
            if col == "erledigt":   return (0, _g(row, "erledigt", 0) or 0)
            if col == "prio":       return (0, _g(row, "prioritaet", 0) or 0)
            if col == "faellig":    v = _g(row, "faellig_am", "") or ""; return (0 if v else 1, v)
            if col == "created_at": return (0, str(_g(row, "created_at", "") or ""))
            if col == "done_at":    v = str(_g(row, "done_at", "") or ""); return (0 if v else 1, v)
            mapping = {"name": "name", "gsm": "gsm", "plant": "plant",
                       "kommentar": "kommentar", "created_by": "created_by"}
            val = (_g(row, mapping.get(col, "name"), "") or "").lower()
            return (0, val)

        def _render():
            from datetime import date
            today = date.today().isoformat()
            term = search_var.get().strip().lower()
            tv.delete(*tv.get_children())
            tasks_by_id.clear()

            rows = list(full_rows)
            if term:
                rows = [r for r in rows if any(
                    term in str(_g(r, k, "") or "").lower()
                    for k in ("name", "gsm", "plant", "kommentar", "created_by"))]
            if sort_state["col"]:
                rows.sort(key=_sort_key, reverse=sort_state["rev"])

            open_count = overdue_count = 0
            for row in rows:
                tasks_by_id[row["id"]] = row
                done = bool(row["erledigt"])
                if not done:
                    open_count += 1
                faellig = _g(row, "faellig_am", "") or ""
                prio = _g(row, "prioritaet", 0) or 0
                if done:
                    tag = ("done",)
                elif faellig and faellig < today:
                    tag = ("overdue",); overdue_count += 1
                elif faellig and faellig == today:
                    tag = ("soon",)
                else:
                    tag = ()
                tv.insert("", "end", iid=str(row["id"]), tags=tag,
                          values=("✓" if done else "offen",
                                  "★" if prio else "",
                                  _fmt_date(faellig),
                                  row["name"] or "", row["gsm"] or "",
                                  row["plant"] or "",
                                  (row["kommentar"] or "").replace("\n", "  "),
                                  str(row["created_at"] or "")[:16],
                                  row["created_by"] or "",
                                  str(row["done_at"] or "")[:16]))
            msg = f"{open_count} offene Aufgaben"
            if overdue_count:
                msg += f"  ·  {overdue_count} überfällig"
            if term:
                msg += f"  ·  {len(rows)} gefiltert"
            count_var.set(msg)

        def _reload():
            full_rows.clear()
            with db.read_connection() as conn:
                full_rows.extend(db.get_tasks(conn, include_done=show_done_var.get()))
            _render()
        self._tasks_reload = _reload

        def _sort_by(col):
            if sort_state["col"] == col:
                sort_state["rev"] = not sort_state["rev"]
            else:
                sort_state["col"] = col
                sort_state["rev"] = False
            for c, label in col_headings.items():
                arrow = (" ▲" if not sort_state["rev"] else " ▼") if c == col else ""
                tv.heading(c, text=label + arrow)
            _render()

        for col_id, heading, _w in cols:
            tv.heading(col_id, text=heading, command=lambda c=col_id: _sort_by(c))
        search_var.trace_add("write", lambda *_: _render())

        def _selected_task():
            sel = tv.selection()
            if not sel:
                messagebox.showinfo("Hinweis", "Bitte eine Aufgabe auswählen.", parent=win)
                return None
            return tasks_by_id.get(int(sel[0]))

        def _need_write() -> bool:
            s = auth.get_session()
            if not (s and s.can("write")):
                messagebox.showinfo("Keine Berechtigung",
                                    "Dafür ist Schreibzugriff nötig.", parent=win)
                return False
            return True

        def _toggle_done():
            task = _selected_task()
            if task is None or not _need_write():
                return
            with db.transaction() as conn:
                db.set_task_done(conn, task["id"], not bool(task["erledigt"]))
            _reload()
            self.refresh_all()

        def _edit_comment():
            task = _selected_task()
            if task is None or not _need_write():
                return
            dlg = tk.Toplevel(win)
            dlg.title("Aufgabe bearbeiten")
            dlg.transient(win)
            theme.center_window(dlg, 440, 280, win)
            dlg.grab_set()
            pal = theme.current()
            txt = tk.Text(dlg, height=6, wrap="word", font=("Segoe UI", 10),
                          background=pal["bg_widget"], foreground=pal["fg"])
            txt.pack(fill="both", expand=True, padx=10, pady=(10, 4))
            txt.insert("1.0", task["kommentar"] or "")

            meta = ttk.Frame(dlg)
            meta.pack(fill="x", padx=10, pady=(0, 4))
            ttk.Label(meta, text="Fällig am (TT.MM.JJJJ):").pack(side="left")
            f_var = tk.StringVar(value=_fmt_date(
                task["faellig_am"] if "faellig_am" in task.keys() else ""))
            ttk.Entry(meta, textvariable=f_var, width=12).pack(side="left", padx=(4, 12))
            pr_var = tk.BooleanVar(value=bool(
                task["prioritaet"] if "prioritaet" in task.keys() else 0))
            ttk.Checkbutton(meta, text="Hohe Priorität", variable=pr_var).pack(side="left")

            bt = ttk.Frame(dlg)
            bt.pack(pady=(0, 8))

            def _save(event=None):
                faellig = _parse_input_date(f_var.get())
                if f_var.get().strip() and not faellig:
                    messagebox.showinfo("Hinweis", "Datum bitte als TT.MM.JJJJ.",
                                        parent=dlg)
                    return
                with db.transaction() as conn:
                    db.update_task_details(conn, task["id"],
                                           txt.get("1.0", "end").strip(),
                                           faellig, 1 if pr_var.get() else 0)
                dlg.destroy()
                _reload()
                self.refresh_all()
            ttk.Button(bt, text="Speichern", style="Accent.TButton",
                       command=_save).pack(side="left", padx=4)
            ttk.Button(bt, text="Abbrechen", command=dlg.destroy).pack(side="left")
            dlg.bind("<Escape>", lambda e: dlg.destroy())
            dlg.bind("<Control-s>", _save)
            txt.focus_set()

        def _delete():
            task = _selected_task()
            if task is None or not _need_write():
                return
            if not messagebox.askyesno("Aufgabe löschen",
                                       f"Aufgabe zu '{task['name']}' wirklich löschen?",
                                       parent=win):
                return
            with db.transaction() as conn:
                db.delete_task(conn, task["id"])
            _reload()
            self.refresh_all()

        def _open_participant(event=None):
            task = _selected_task()
            if task is None or not task["participant_id"]:
                return
            with db.read_connection() as conn:
                part = db.get_participant_by_id(conn, int(task["participant_id"]))
            if part is None:
                messagebox.showinfo("Hinweis",
                                    "Der zugehörige Teilnehmer existiert nicht mehr.",
                                    parent=win)
                return
            EditorWindow(self.root, int(task["participant_id"]),
                         on_save_callback=self.refresh_all)

        ttk.Button(toolbar, text="Erledigt ⇄", style="Accent.TButton",
                   command=_toggle_done).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Bearbeiten …",           command=_edit_comment).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Löschen",                command=_delete).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Teilnehmer öffnen",      command=_open_participant).pack(side="left", padx=2)
        ttk.Checkbutton(toolbar, text="Erledigte anzeigen", variable=show_done_var,
                        command=_reload).pack(side="left", padx=12)
        ttk.Label(toolbar, textvariable=count_var,
                  style="Dim.TLabel").pack(side="right")
        ttk.Entry(toolbar, textvariable=search_var, width=22).pack(side="right", padx=(4, 8))
        ttk.Label(toolbar, text="Suche:").pack(side="right")

        tv.bind("<Double-1>", _open_participant)
        win.bind("<Escape>", lambda e: win.destroy())
        _reload()



    def _ctx_delete(self, pid: int):
        if not auth.get_session() or not auth.get_session().can("delete"):
            messagebox.showwarning("Keine Berechtigung",
                                   "Löschen erfordert Admin-Berechtigung.",
                                   parent=self.root)
            return
        with db.read_connection() as conn:
            row = db.get_participant_by_id(conn, pid)
        name = row["name"] if row else f"ID {pid}"
        if not messagebox.askyesno("Löschen bestätigen",
                                    f"Wirklich löschen?\n{name}",
                                    parent=self.root):
            return
        try:
            s = auth.get_session()
            with db.transaction() as conn:
                db.delete_participant(conn, pid)
                db.log_import(conn, "GUI", "DELETE", f"ID={pid} {name} gelöscht")
                db.log_audit(conn, s.user_id, s.username,
                             "DELETE", f"Teilnehmer '{name}' (ID={pid}) gelöscht",
                             table_name="participants", record_id=pid)
            self.refresh_all()
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc), parent=self.root)

    def _toggle_verified(self, pid: int, reload_fn):
        try:
            with db.read_connection() as conn:
                row = db.get_participant_by_id(conn, pid)
            if row is None:
                reload_fn()
                return
            new_val = 0 if row["verified"] else 1
            with db.transaction() as conn:
                db.set_verified(conn, pid, new_val)
                db.log_import(conn, "GUI", "VERIFIED",
                              f"ID={pid} verified={new_val} per Klick")
            reload_fn()
            self._load_open_checks()
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc), parent=self.root)

    # ------------------------------------------------------------------
    # Offene Prüfungen
    # ------------------------------------------------------------------

    def _get_selected_id(self, tv) -> int | None:
        sel = tv.selection()
        if not sel:
            messagebox.showinfo("Hinweis", "Bitte einen Eintrag auswählen.", parent=self.root)
            return None
        return int(sel[0])

    def _on_open_double_click(self, event):
        tv = self._tv_open
        col = tv.identify_column(event.x)
        col_idx = int(col.replace("#", "")) - 1
        if 0 <= col_idx < len(self._tv_open_cols) and \
                self._tv_open_cols[col_idx] == "verified":
            sel = tv.selection()
            if sel:
                self._toggle_verified(int(sel[0]), self._load_open_checks)
            return
        self._edit_open_check()

    def _on_open_rclick(self, event):
        tv = self._tv_open
        iid = tv.identify_row(event.y)
        if iid:
            tv.selection_set(iid)
        self._show_context_menu(event, tv, iid,
                                actions=[
                                    ("Bearbeiten",              lambda: self._edit_open_check()),
                                    None,
                                    ("Zu Telekom verschieben",  lambda: self._move_to_provider(int(iid), "Telekom")),
                                    ("Zu O2 verschieben",       lambda: self._move_to_provider(int(iid), "O2")),
                                    ("Nach 'Ohne SIM' verschieben", lambda: self._move_to_provider(int(iid), "Ohne SIM")),
                                    ("Nach 'Frei' verschieben", lambda: self._move_to_provider(int(iid), "Frei")),
                                    None,
                                    ("Zu Aufgabe …",            lambda: self._create_task_dialog(int(iid))),
                                    None,
                                    ("Als geprüft markieren",   lambda: self._toggle_verified(int(iid), self._load_open_checks)),
                                ])
        return "break"

    def _on_incomplete_rclick(self, event):
        tv = self._tv_incomplete
        iid = tv.identify_row(event.y)
        if iid:
            tv.selection_set(iid)
        self._show_context_menu(event, tv, iid,
                                actions=[
                                    ("Bearbeiten",              lambda: EditorWindow(self.root, int(iid), on_save_callback=self.refresh_all)),
                                    None,
                                    ("Zu Telekom verschieben",  lambda: self._move_to_provider(int(iid), "Telekom")),
                                    ("Zu O2 verschieben",       lambda: self._move_to_provider(int(iid), "O2")),
                                    ("Nach 'Ohne SIM' verschieben", lambda: self._move_to_provider(int(iid), "Ohne SIM")),
                                    ("Nach 'Frei' verschieben", lambda: self._move_to_provider(int(iid), "Frei")),
                                    None,
                                    ("Zu Aufgabe …",            lambda: self._create_task_dialog(int(iid))),
                                    None,
                                    ("Eintrag löschen",         lambda: self._ctx_delete(int(iid))),
                                ])
        return "break"

    def _move_to_provider(self, pid: int, provider: str):
        try:
            with db.transaction() as conn:
                db.set_provider(conn, pid, provider)
                db.log_import(conn, "GUI", "PROVIDER",
                              f"ID={pid} → {provider}")
            self.refresh_all()
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc), parent=self.root)

    def _mark_verified(self):
        sel = self._tv_open.selection()
        if not sel:
            messagebox.showinfo("Hinweis", "Bitte mindestens einen Eintrag auswählen.",
                                parent=self.root)
            return
        try:
            with db.transaction() as conn:
                for iid in sel:
                    db.set_verified(conn, int(iid), 1)
                db.log_import(conn, "GUI", "VERIFIED",
                              f"{len(sel)} Einträge als geprüft markiert")
            self._load_open_checks()
            self._load_participants()
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc), parent=self.root)

    def _edit_open_check(self):
        sel = self._tv_open.selection()
        if len(sel) != 1:
            messagebox.showinfo("Hinweis", "Bitte genau einen Eintrag auswählen.",
                                parent=self.root)
            return
        EditorWindow(self.root, int(sel[0]), on_save_callback=self.refresh_all)

    # ------------------------------------------------------------------
    # Nicht zugeordnet
    # ------------------------------------------------------------------

    def _assign_unmatched(self):
        uid = self._get_selected_id(self._tv_unmatched)
        if uid is None:
            return
        with db.read_connection() as conn:
            unmatched_rows = db.get_all_unmatched(conn)
        unmatched = next((r for r in unmatched_rows if r["id"] == uid), None)
        if not unmatched:
            return
        dialog = _AssignDialog(self.root, unmatched)
        self.root.wait_window(dialog)
        if dialog.selected_pid:
            try:
                with db.transaction() as conn:
                    db.update_participant_fields(conn, dialog.selected_pid, {
                        "syno": unmatched["geraet"], "start_syno": unmatched["startdatum"],
                    })
                    db.delete_unmatched_device(conn, uid)
                    db.log_import(conn, "GUI", "ASSIGN",
                                  f"Unmatched ID={uid} -> Teilnehmer ID={dialog.selected_pid}")
                messagebox.showinfo("Erfolg", "Gerät erfolgreich zugeordnet.", parent=self.root)
                self.refresh_all()
            except Exception as exc:
                messagebox.showerror("Fehler", str(exc), parent=self.root)

    def _delete_unmatched(self):
        uid = self._get_selected_id(self._tv_unmatched)
        if uid is None:
            return
        if not messagebox.askyesno("Löschen bestätigen",
                                   "Eintrag wirklich löschen?", parent=self.root):
            return
        try:
            with db.transaction() as conn:
                db.delete_unmatched_device(conn, uid)
                db.log_import(conn, "GUI", "DELETE_UNMATCHED", f"ID={uid} gelöscht")
            self._load_unmatched()
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc), parent=self.root)

    # ------------------------------------------------------------------
    # Export Excel
    # ------------------------------------------------------------------

    def _export_excel(self):
        # Aktuell sichtbare (gefilterte) IDs aus der Treeview lesen
        visible_ids = [int(iid) for iid in self._tv_participants.get_children()]
        if not visible_ids:
            messagebox.showinfo("Hinweis", "Keine Zeilen zum Exportieren vorhanden.", parent=self.root)
            return

        path = filedialog.asksaveasfilename(
            parent=self.root, title="Teilnehmer exportieren",
            defaultextension=".xlsx",
            filetypes=[("Excel-Dateien", "*.xlsx"), ("Alle Dateien", "*.*")],
        )
        if not path:
            return
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
        except ImportError:
            messagebox.showerror("Fehler", "openpyxl nicht installiert.", parent=self.root)
            return
        try:
            with db.read_connection() as conn:
                id_set = set(visible_ids)
                all_rows = db.get_all_participants(conn)
            rows = [r for r in all_rows if r["id"] in id_set]
            # Reihenfolge der Treeview beibehalten
            order = {iid: i for i, iid in enumerate(visible_ids)}
            rows.sort(key=lambda r: order.get(r["id"], 9999))

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Teilnehmer"

            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill("solid", fgColor="2E4057")

            headers = [c[1] for c in PARTICIPANT_COLUMNS]
            ws.append(headers)
            for col_idx, _ in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")

            unverified_fill = PatternFill("solid", fgColor="FFFFF59D")
            for row in rows:
                values = []
                for k in self._tv_participant_cols:
                    v = row[k] if k in row.keys() else None
                    if k in DATE_FIELDS:
                        v = _fmt_date(v) if v else ""
                    elif k == "verified":
                        v = "Ja" if v else "Nein"
                    else:
                        v = str(v) if v is not None else ""
                    values.append(v)
                ws.append(values)
                if not row["verified"]:
                    for col_idx in range(1, len(values) + 1):
                        ws.cell(row=ws.max_row, column=col_idx).fill = unverified_fill

            # Spaltenbreiten anpassen
            for col_idx, (_, _, width) in enumerate(PARTICIPANT_COLUMNS, 1):
                ws.column_dimensions[
                    openpyxl.utils.get_column_letter(col_idx)
                ].width = max(10, width // 7)

            wb.save(path)
            messagebox.showinfo("Exportiert",
                                f"{len(rows)} Datensätze exportiert:\n{path}", parent=self.root)
        except Exception as exc:
            messagebox.showerror("Exportfehler", str(exc), parent=self.root)

    def _load_duplicates(self):
        tv = self._tv_duplicates
        tv.delete(*tv.get_children())
        with db.read_connection() as conn:
            rows = db.get_duplicates_detail(conn)
        task_ids = self._task_marker(tv)
        prev_name = None
        for row in rows:
            norm = (row["name"] or "").strip().lower()
            if row["id"] in task_ids:
                tag = ("has_task",)
            else:
                tag = ("odd",) if norm != prev_name else ()
                if _is_telekom(row):
                    tag = ("telekom",) + tag
            tv.insert("", "end", iid=str(row["id"]),
                      values=_row_values(row, self._tv_dup_cols), tags=tag)
            prev_name = norm
        self._tv_duplicates.tag_configure("odd",     background=theme.current()["tag_odd_dup"])
        self._tv_duplicates.tag_configure("telekom", background=theme.current()["tag_telekom"])
        n = len(rows)
        self._dup_count_var.set(f"{n} Einträge mit doppeltem Namen" if n else "Keine Duplikate gefunden")
        _autoresize_columns(tv)

    def _edit_duplicate(self):
        sel = self._tv_duplicates.selection()
        if not sel:
            messagebox.showinfo("Hinweis", "Bitte einen Eintrag auswählen.", parent=self.root)
            return
        EditorWindow(self.root, int(sel[0]), on_save_callback=self.refresh_all)

    def _merge_duplicates(self):
        self._merge_selected(self._tv_duplicates)

    def _merge_selected(self, tv: ttk.Treeview):
        """Führt 2+ ausgewählte Teilnehmer (Mehrfachauswahl) zusammen.
        Funktioniert in allen Teilnehmer-Tabs – die iids sind Teilnehmer-IDs."""
        sel = tv.selection()
        if len(sel) < 2:
            messagebox.showinfo("Hinweis",
                                "Bitte mindestens 2 Einträge auswählen (Strg/Umschalt+Klick).",
                                parent=self.root)
            return
        with db.read_connection() as conn:
            rows = [db.get_participant_by_id(conn, int(pid)) for pid in sel]
        rows = [r for r in rows if r is not None]
        if len(rows) < 2:
            messagebox.showerror("Fehler", "Ausgewählte Einträge konnten nicht geladen werden.",
                                 parent=self.root)
            return
        _MergeDialog(self.root, rows, on_merged=self.refresh_all)

    def _load_statistics(self):
        with db.read_connection() as conn:
            s = db.get_stats(conn)

        # Kacheln aktualisieren
        for key, var in self._stat_labels.items():
            var.set(str(s.get(key, "–")))

        # Ablauf-Liste
        tv = self._tv_ablauf
        tv.delete(*tv.get_children())
        from datetime import date, timedelta
        in_30 = (date.today() + timedelta(days=30)).isoformat()
        for row in s["ablauf_liste"]:
            tag = ("urgent",) if row["vertragsende"] <= in_30 else ("soon",)
            if _is_telekom(row):
                tag = ("telekom",) + tag
            tv.insert("", "end", values=(
                row["name"], row["plant"] or "",
                _fmt_date(row["vertragsende"]),
            ), tags=tag)

        # Balken-Chart Werke
        canvas = self._stat_canvas
        canvas.delete("all")
        canvas.update_idletasks()
        cw = canvas.winfo_width() or 300
        ch = canvas.winfo_height() or 200
        werke = list(s["werke"])
        if not werke:
            return
        max_n = max(r["n"] for r in werke)
        bar_h = max(14, min(28, (ch - 20) // max(len(werke), 1)))
        pad_l, pad_r, pad_t = 110, 30, 10
        bar_w = cw - pad_l - pad_r
        colors = theme.current()["chart_colors"].split(",")
        for i, row in enumerate(werke):
            y1 = pad_t + i * (bar_h + 4)
            y2 = y1 + bar_h
            w  = int(bar_w * row["n"] / max_n) if max_n else 0
            color = colors[i % len(colors)]
            canvas.create_text(pad_l - 6, (y1 + y2) // 2,
                               text=row["werk"], anchor="e", font=("Segoe UI", 8))
            canvas.create_rectangle(pad_l, y1, pad_l + w, y2, fill=color, outline="")
            canvas.create_text(pad_l + w + 4, (y1 + y2) // 2,
                               text=str(row["n"]), anchor="w", font=("Segoe UI", 8))

    def _show_expired_contracts(self):
        win = tk.Toplevel(self.root)
        win.title("Abgelaufene Verträge")
        theme.center_window(win, 780, 500, self.root)
        p = theme.current()

        with db.read_connection() as conn:
            rows = db.get_expired_contracts(conn)

        ttk.Label(win, text=f"{len(rows)} abgelaufene Verträge",
                  style="Dim.TLabel").pack(anchor="w", padx=10, pady=(10, 4))

        tv_frame = ttk.Frame(win)
        tv_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cols = [("name", "Name", 180), ("gsm", "GSM", 120), ("plant", "Werk", 100),
                ("konto", "Konto", 90), ("provider", "Provider", 80),
                ("vertragsende", "Vertragsende", 100)]
        tv = ttk.Treeview(tv_frame, columns=[c[0] for c in cols], show="headings")
        for col_id, heading, width in cols:
            tv.heading(col_id, text=heading)
            tv.column(col_id, width=width, minwidth=30)
        ys = ttk.Scrollbar(tv_frame, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=ys.set)
        tv.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        tv_frame.rowconfigure(0, weight=1)
        tv_frame.columnconfigure(0, weight=1)
        tv.tag_configure("telekom", background=p["tag_telekom"])
        tv.tag_configure("frei",    background=p["tag_frei"])

        for row in rows:
            tag = ()
            if row["provider"] == "Telekom":
                tag = ("telekom",)
            elif row["provider"] == "Frei":
                tag = ("frei",)
            tv.insert("", "end", iid=str(row["id"]), values=(
                row["name"] or "", row["gsm"] or "", row["plant"] or "",
                row["konto"] or "", row["provider"] or "Vodafone",
                _fmt_date(row["vertragsende"]),
            ), tags=tag)

        ttk.Label(win, text="Doppelklick → Teilnehmer bearbeiten",
                  style="Dim.TLabel").pack(pady=(0, 6))

        def _on_double(event):
            iid = tv.focus()
            if iid:
                EditorWindow(self.root, int(iid), on_save_callback=self.refresh_all)

        tv.bind("<Double-1>", _on_double)

    def _manual_backup(self):
        try:
            dest = db.create_backup()
            s = auth.get_session()
            if s:
                with db.transaction() as conn:
                    db.log_audit(conn, s.user_id, s.username,
                                 "BACKUP", f"Manuelles Backup: {dest}")
            messagebox.showinfo("Backup erstellt",
                                f"Datenbank gesichert:\n{dest}", parent=self.root)
        except Exception as exc:
            messagebox.showerror("Backup fehlgeschlagen", str(exc), parent=self.root)

    def _restore_backup(self):
        if not self._require_admin():
            return
        backups = db.list_backups()
        if not backups:
            messagebox.showinfo("Kein Backup",
                                "Es sind keine Sicherungen vorhanden.", parent=self.root)
            return

        win = tk.Toplevel(self.root)
        win.title("Backup wiederherstellen")
        win.transient(self.root)
        theme.center_window(win, 560, 400, self.root)
        win.grab_set()
        ttk.Label(win, text="Sicherung auswählen (neueste zuerst):",
                  padding=(12, 10, 12, 4)).pack(anchor="w")

        tv_frame = ttk.Frame(win, padding=(12, 0, 12, 8))
        tv_frame.pack(fill="both", expand=True)
        tv = ttk.Treeview(tv_frame, columns=("zeit", "groesse", "datei"),
                          show="headings", selectmode="browse")
        tv.heading("zeit", text="Zeitpunkt"); tv.column("zeit", width=150)
        tv.heading("groesse", text="Größe");  tv.column("groesse", width=90, anchor="e")
        tv.heading("datei", text="Datei");     tv.column("datei", width=280)
        ys = ttk.Scrollbar(tv_frame, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=ys.set)
        tv.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        paths = {}
        for f, size, mtime in backups:
            iid = str(f)
            paths[iid] = f
            tv.insert("", "end", iid=iid, values=(
                mtime.strftime("%d.%m.%Y %H:%M:%S"),
                f"{size/1024:.0f} KB", f.name))
        first = tv.get_children()
        if first:
            tv.selection_set(first[0])

        def _do_restore():
            sel = tv.selection()
            if not sel:
                messagebox.showinfo("Hinweis", "Bitte eine Sicherung auswählen.", parent=win)
                return
            bpath = paths[sel[0]]
            if not messagebox.askyesno(
                "Backup wiederherstellen",
                f"Der AKTUELLE Datenbankstand wird durch diese Sicherung ersetzt:\n\n"
                f"  {bpath.name}\n\n"
                "Der jetzige Stand wird zuvor automatisch gesichert (Datei "
                "'…_vor-restore_…').\n\nWiederherstellen?",
                icon="warning", parent=win):
                return
            try:
                safety = db.restore_backup(bpath)
                s = auth.get_session()
                if s:
                    with db.transaction() as conn:
                        db.log_audit(conn, s.user_id, s.username, "RESTORE",
                                     f"Backup {bpath.name} zurückgespielt "
                                     f"(vorher gesichert: {safety.name})")
            except Exception as exc:
                logger.exception("Restore fehlgeschlagen")
                messagebox.showerror("Wiederherstellung fehlgeschlagen",
                                     str(exc), parent=win)
                return
            win.destroy()
            self.refresh_all()
            messagebox.showinfo(
                "Wiederhergestellt",
                f"Die Sicherung wurde eingespielt.\n\nDer vorige Stand liegt als\n"
                f"{safety.name}\nim Ordner backups/.", parent=self.root)

        btns = ttk.Frame(win, padding=(12, 0, 12, 12))
        btns.pack(fill="x")
        ttk.Button(btns, text="Wiederherstellen", style="Accent.TButton",
                   command=_do_restore).pack(side="right", padx=(4, 0))
        ttk.Button(btns, text="Abbrechen", command=win.destroy).pack(side="right")

    def _open_usermgmt(self):
        from modules.ui_usermgmt import UserManagementDialog
        UserManagementDialog(self.root)

    def _logout(self):
        if not messagebox.askyesno("Abmelden",
                                   "Wirklich abmelden?\nDie Anwendung wird neu gestartet.",
                                   parent=self.root):
            return
        s = auth.get_session()
        if s:
            try:
                with db.transaction() as conn:
                    db.log_audit(conn, s.user_id, s.username, "LOGOUT", "Abgemeldet")
            except Exception:
                pass
        auth.set_session(None)
        self.root.destroy()
        # Neustart der Anwendung (gebaute EXE vs. Python-Start berücksichtigen)
        import subprocess, sys
        if getattr(sys, "frozen", False):
            subprocess.Popen([sys.executable])
        else:
            subprocess.Popen([sys.executable] + sys.argv)
        sys.exit(0)

    # ------------------------------------------------------------------
    # Export CSV
    # ------------------------------------------------------------------

    def _export_csv(self):
        import csv
        visible_ids = [int(iid) for iid in self._tv_participants.get_children()]
        if not visible_ids:
            messagebox.showinfo("Hinweis", "Keine Zeilen zum Exportieren.", parent=self.root)
            return
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Teilnehmer als CSV exportieren",
            defaultextension=".csv",
            filetypes=[("CSV-Dateien", "*.csv"), ("Alle Dateien", "*.*")],
        )
        if not path:
            return
        try:
            with db.read_connection() as conn:
                all_rows = db.get_all_participants(conn)
            id_set = set(visible_ids)
            rows = [r for r in all_rows if r["id"] in id_set]
            order = {iid: i for i, iid in enumerate(visible_ids)}
            rows.sort(key=lambda r: order.get(r["id"], 9999))
            col_keys = [c[0] for c in PARTICIPANT_COLUMNS]
            headers  = [c[1] for c in PARTICIPANT_COLUMNS]
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(headers)
                for row in rows:
                    values = []
                    for k in col_keys:
                        v = row[k] if k in row.keys() else None
                        if k in DATE_FIELDS:
                            v = _fmt_date(v) if v else ""
                        elif k == "verified":
                            v = "Ja" if v else "Nein"
                        else:
                            v = str(v) if v is not None else ""
                        values.append(v)
                    writer.writerow(values)
            messagebox.showinfo(
                "Exportiert", f"{len(rows)} Datensätze exportiert:\n{path}", parent=self.root)
        except Exception as exc:
            messagebox.showerror("Exportfehler", str(exc), parent=self.root)

    # ------------------------------------------------------------------
    # Export Drucken / HTML
    # ------------------------------------------------------------------

    def _export_print(self):
        import tempfile, webbrowser
        visible_ids = [int(iid) for iid in self._tv_participants.get_children()]
        if not visible_ids:
            messagebox.showinfo("Hinweis", "Keine Zeilen vorhanden.", parent=self.root)
            return
        try:
            with db.read_connection() as conn:
                all_rows = db.get_all_participants(conn)
            id_set = set(visible_ids)
            rows = [r for r in all_rows if r["id"] in id_set]
            order = {iid: i for i, iid in enumerate(visible_ids)}
            rows.sort(key=lambda r: order.get(r["id"], 9999))
            col_keys = [c[0] for c in PARTICIPANT_COLUMNS]
            headers  = [c[1] for c in PARTICIPANT_COLUMNS]
            header_cells = "".join(f"<th>{h}</th>" for h in headers)
            html_rows = []
            for row in rows:
                cells = []
                for k in col_keys:
                    v = row[k] if k in row.keys() else None
                    if k in DATE_FIELDS:
                        v = _fmt_date(v) if v else ""
                    elif k == "verified":
                        v = "✓" if v else "✗"
                    else:
                        v = str(v) if v is not None else ""
                    cells.append(f"<td>{v}</td>")
                bg = "#fff9c4" if not row["verified"] else ""
                style = f' style="background:{bg}"' if bg else ""
                html_rows.append(f"<tr{style}>{''.join(cells)}</tr>")
            now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
            html = (
                "<!DOCTYPE html><html lang='de'><head><meta charset='utf-8'>"
                "<title>Mobilfunkverwaltung – Teilnehmerliste</title>"
                "<style>"
                "body{font-family:Segoe UI,Arial,sans-serif;font-size:10pt}"
                "h1{font-size:14pt;margin-bottom:4px}"
                "p.meta{color:#666;font-size:9pt;margin:0 0 12px}"
                "table{border-collapse:collapse;width:100%}"
                "th{background:#2563EB;color:white;padding:4px 8px;text-align:left;font-size:9pt}"
                "td{padding:3px 8px;border-bottom:1px solid #ddd;font-size:9pt}"
                "tr:nth-child(even){background:#f8f9fa}"
                "@media print{@page{margin:1cm}}"
                "</style></head><body>"
                "<h1>Mobilfunkverwaltung – Teilnehmerliste</h1>"
                f"<p class='meta'>Exportiert: {now_str} &nbsp;|&nbsp; {len(rows)} Einträge</p>"
                f"<table><thead><tr>{header_cells}</tr></thead><tbody>"
                + "".join(html_rows)
                + "</tbody></table></body></html>"
            )
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".html", encoding="utf-8", delete=False
            ) as f:
                f.write(html)
                tmp_path = f.name
            webbrowser.open(f"file:///{tmp_path.replace(chr(92), '/')}")
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc), parent=self.root)

    # ------------------------------------------------------------------
    # Importhistorie speichern
    # ------------------------------------------------------------------

    def _save_log(self):
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Importprotokoll speichern",
            defaultextension=".txt",
            filetypes=[("Textdatei", "*.txt"), ("Alle Dateien", "*.*")],
        )
        if not path:
            return
        try:
            Path(path).write_text(self._log_text.get("1.0", "end"), encoding="utf-8")
            messagebox.showinfo("Gespeichert", f"Protokoll gespeichert:\n{path}", parent=self.root)
        except Exception as exc:
            messagebox.showerror("Fehler", str(exc), parent=self.root)

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def _require_admin(self) -> bool:
        """Importe sind Administratoren vorbehalten (Absicherung zusätzlich zur
        Menüsperre). Zeigt bei fehlender Berechtigung einen Hinweis."""
        s = auth.get_session()
        if s and s.can("admin"):
            return True
        messagebox.showinfo(
            "Keine Berechtigung",
            "Importe dürfen nur von Administratoren durchgeführt werden.",
            parent=self.root)
        return False

    def _backup_or_confirm(self) -> bool:
        """Erstellt vor einem Import ein Backup. Schlägt es fehl, wird NICHT
        stillschweigend weitergemacht, sondern gefragt. Rückgabe: fortfahren?"""
        try:
            dest = db.create_backup()
            logger.info("Backup vor Import erstellt: %s", dest)
            return True
        except Exception as exc:
            logger.error("Backup vor Import fehlgeschlagen: %s", exc)
            return messagebox.askyesno(
                "Backup fehlgeschlagen",
                "Vor dem Import konnte KEIN Sicherungsbackup erstellt werden:\n\n"
                f"{exc}\n\n"
                "Ohne Backup fortzufahren ist riskant – bei einem Fehler lässt\n"
                "sich der vorige Stand nicht wiederherstellen.\n\n"
                "Trotzdem ohne Backup fortfahren?",
                icon="warning", parent=self.root,
            )

    def _run_import(self, label: str, import_fn):
        if not self._require_admin():
            return
        path = filedialog.askopenfilename(
            parent=self.root, title=f"{label} auswählen",
            filetypes=[("Excel-Dateien", "*.xlsx *.xls"), ("Alle Dateien", "*.*")],
        )
        if not path:
            return
        if not self._backup_or_confirm():
            return
        try:
            result = import_fn(path)
        except Exception as exc:
            logger.exception("Importfehler: %s", label)
            messagebox.showerror("Importfehler", str(exc), parent=self.root)
            return
        try:
            self._show_import_result(
                label,
                result.get("log_lines", []),
                warnings=result.get("warnings"),
                stats=result,
            )
        except Exception as exc:
            logger.exception("Importprotokoll konnte nicht angezeigt werden: %s", exc)
            messagebox.showinfo(
                "Import abgeschlossen",
                "Der Import ist abgeschlossen, das Protokollfenster konnte "
                "aber nicht angezeigt werden. Details siehe Importhistorie/Logs.",
                parent=self.root)
        self.refresh_all()

    def _show_import_result(self, title: str, log_lines: list,
                             warnings: list | None = None,
                             stats: dict | None = None):
        win = tk.Toplevel(self.root)
        win.title(f"Importprotokoll – {title}")
        theme.center_window(win, 800, 580, self.root)
        win.resizable(True, True)

        # --- Kennzahl-Kacheln ---
        if stats:
            # Vodafone: updated/created/skipped/errors
            # Syno:     matched_gsm/matched_name/neu_angelegt/skipped/errors
            is_master = "imported" in stats and "matched_gsm" not in stats and "updated" not in stats
            is_syno = "matched_gsm" in stats
            if is_master:
                tiles = [
                    ("Importiert",    stats.get("imported",   0),        "#2E6DA4"),
                    ("Doppelte GSM",  stats.get("duplicates", 0),        "#F39C12"),
                    ("Zur Prüfung",   stats.get("review",     0),        "#E67E22"),
                    ("Übersprungen",  stats.get("skipped",    0),        "#888888"),
                    ("Fehler",        len(stats.get("errors", [])),      "#C0392B"),
                ]
            elif is_syno:
                tiles = [
                    ("GSM-Matches",       stats.get("matched_gsm", 0),  "#2E6DA4"),
                    ("Name-Matches",      stats.get("matched_name", 0), "#2E6DA4"),
                    ("Bereits vorhanden", stats.get("duplicate", 0),    "#888888"),
                    ("Kein freier Slot",  stats.get("slots_full", 0),   "#F39C12"),
                    ("Nicht zugeordnet",  stats.get("unmatched", 0),    "#E67E22"),
                    ("Übersprungen",      stats.get("skipped", 0),      "#888888"),
                    ("Fehler",            len(stats.get("errors", [])), "#C0392B"),
                ]
            else:
                tiles = [
                    ("Aktualisiert", stats.get("updated", 0),      "#2E6DA4"),
                    ("Neu angelegt", stats.get("created", 0),      "#5A9A3A"),
                    ("Änderungen",   len(stats.get("changes", [])),"#2E6DA4"),
                    ("Zur Prüfung",  stats.get("review",  0),      "#E67E22"),
                    ("Übersprungen", stats.get("skipped", 0),      "#888888"),
                    ("Fehler",       len(stats.get("errors", [])), "#C0392B"),
                ]
            p = theme.current()
            card_row = ttk.Frame(win, padding=(8, 8, 8, 4))
            card_row.pack(fill="x")
            for tile_label, tile_val, tile_color in tiles:
                cell = tk.Frame(card_row, bg=p["tile_bg"],
                                relief="solid", bd=int(p["tile_border"]),
                                highlightbackground=p["tile_border_color"])
                cell.pack(side="left", padx=6, pady=4, ipadx=10, ipady=6)
                tk.Label(cell, text=str(tile_val),
                         font=("Segoe UI", 18, "bold"),
                         fg=tile_color, bg=p["tile_bg"]).pack()
                tk.Label(cell, text=tile_label,
                         font=("Segoe UI", 8),
                         fg=p["tile_fg_dim"], bg=p["tile_bg"]).pack()
            ttk.Separator(win, orient="horizontal").pack(fill="x", padx=8, pady=(0, 4))

        # --- Warnungs-Banner bei Duplikaten ---
        if warnings:
            p2 = theme.current()
            banner = tk.Label(
                win,
                text=f"⚠  {len(warnings)} doppelte GSM-Nummer(n) übersprungen – Details im Protokoll",
                background=p2["warn_banner_bg"], foreground=p2["warn_banner_fg"],
                font=("Segoe UI", 9, "bold"), anchor="w", padx=8, pady=4,
            )
            banner.pack(fill="x", padx=8, pady=(0, 4))

        # --- Hinweis-Banner: Zeilen zur Prüfung abgelegt ---
        review_n = (stats or {}).get("review", 0)
        if review_n:
            p3 = theme.current()
            tk.Label(
                win,
                text=(f"⚠  {review_n} Zeile(n) konnten nicht sicher importiert "
                      f"werden und liegen zur Prüfung im Tab 'Nicht zugeordnet'."),
                background=p3["warn_banner_bg"], foreground=p3["warn_banner_fg"],
                font=("Segoe UI", 9, "bold"), anchor="w", padx=8, pady=4,
            ).pack(fill="x", padx=8, pady=(0, 4))

        frame = ttk.Frame(win, padding=8)
        frame.pack(fill="both", expand=True)

        text = tk.Text(frame, wrap="none", font=("Courier New", 9))
        text.tag_configure("warn", foreground="#B8860B")
        ys = ttk.Scrollbar(frame, orient="vertical",   command=text.yview)
        xs = ttk.Scrollbar(frame, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        text.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        for line in log_lines:
            tag = ("warn",) if ("Doppelte GSM" in line or "WARN" in line.upper()
                                or "doppelte" in line.lower()) else ()
            text.insert("end", line + "\n", tag)
        text.configure(state="disabled")
        ttk.Button(win, text="Schließen", command=win.destroy).pack(pady=6)

    # ------------------------------------------------------------------
    # Globale Suche
    # ------------------------------------------------------------------

    def _open_global_search(self, initial_term: str = ""):
        win = tk.Toplevel(self.root)
        win.title("Globale Suche")
        theme.center_window(win, 820, 540, self.root)
        p = theme.current()

        top = ttk.Frame(win, padding=(10, 10, 10, 6))
        top.pack(fill="x")
        ttk.Label(top, text="Suche:").pack(side="left")
        var = tk.StringVar(value=initial_term)
        entry = ttk.Entry(top, textvariable=var, width=40)
        entry.pack(side="left", padx=(6, 8))
        ttk.Button(top, text="Suchen",
                   command=lambda: _run()).pack(side="left")
        count_lbl = ttk.Label(top, text="", style="Dim.TLabel")
        count_lbl.pack(side="left", padx=12)

        tv_frame = ttk.Frame(win)
        tv_frame.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        cols = [("kategorie", "Kategorie", 130),
                ("name",      "Name",      180),
                ("gsm",       "GSM",       120),
                ("plant",     "Werk",       80),
                ("konto",     "Konto",      90),
                ("tarif",     "Tarif",     120),
                ("bemerkung", "Bemerkung", 180)]
        tv = ttk.Treeview(tv_frame, columns=[c[0] for c in cols],
                          show="headings", selectmode="browse")
        for col_id, heading, width in cols:
            tv.heading(col_id, text=heading)
            tv.column(col_id, width=width, minwidth=30)
        ys = ttk.Scrollbar(tv_frame, orient="vertical",   command=tv.yview)
        xs = ttk.Scrollbar(tv_frame, orient="horizontal", command=tv.xview)
        tv.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        tv.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        tv_frame.rowconfigure(0, weight=1)
        tv_frame.columnconfigure(0, weight=1)

        # Kategorie-Tags
        tv.tag_configure("Teilnehmer",       background=p["tree_bg"])
        tv.tag_configure("Telekom",          background=p["tag_telekom"])
        tv.tag_configure("O2",               background=p["tag_o2"])
        tv.tag_configure("Ohne SIM",         background=p["tag_ohnesim"])
        tv.tag_configure("Frei",             background=p["tag_frei"])
        tv.tag_configure("Offene Prüfungen", background=p["tag_urgent"])
        tv.tag_configure("Nicht zugeordnet", background=p["tag_warn"])

        ttk.Label(win, text="Doppelklick → Tab öffnen und Eintrag markieren",
                  style="Dim.TLabel").pack(pady=(0, 6))

        self._gs_tv = tv  # für Double-Click

        def _run():
            term = var.get().strip()
            if len(term) < 2:
                count_lbl.configure(text="Mindestens 2 Zeichen eingeben")
                return
            tv.delete(*tv.get_children())
            with db.read_connection() as conn:
                results = db.search_global(conn, term)
            total = 0
            for kat, rows in results.items():
                for row in rows:
                    vals = [kat,
                            row["name"] if "name" in row.keys() else "",
                            row["gsm"]  if "gsm"  in row.keys() else "",
                            row["plant"] if "plant" in row.keys() else "",
                            row["konto"] if "konto" in row.keys() else "",
                            row["tarif"] if "tarif" in row.keys() else "",
                            row["bemerkung"] if "bemerkung" in row.keys() else ""]
                    tv.insert("", "end", iid=f"{kat}_{row['id']}",
                              values=vals, tags=(kat,))
                    total += 1
            count_lbl.configure(text=f"{total} Treffer")

        def _on_double(event):
            iid = tv.focus()
            if not iid:
                return
            kat = tv.set(iid, "kategorie")
            raw_id = iid.split("_", 1)[1]
            tab_map = {
                "Teilnehmer":       (self._tab_participants,  [self._tv_participants, self._tv_open]),
                "Telekom":          (self._tab_telekom,       [self._tv_telekom]),
                "O2":               (self._tab_o2,            [self._tv_o2]),
                "Ohne SIM":         (self._tab_ohnesim,       [self._tv_ohnesim]),
                "Frei":             (self._tab_frei,          [self._tv_frei]),
                "Offene Prüfungen": (self._tab_open_checks,   [self._tv_open]),
                "Nicht zugeordnet": (self._tab_unmatched,     [self._tv_unmatched]),
            }
            if kat in tab_map:
                tab, treeviews = tab_map[kat]
                self.notebook.select(tab)
                for tv2 in treeviews:
                    if tv2.exists(raw_id):
                        tv2.selection_set(raw_id)
                        tv2.see(raw_id)
                        break
            win.destroy()

        tv.bind("<Double-1>", _on_double)
        entry.bind("<Return>", lambda e: _run())
        entry.focus_set()
        entry.select_range(0, "end")
        if initial_term.strip():
            _run()

    # ------------------------------------------------------------------
    # Import-Vorschau
    # ------------------------------------------------------------------

    def _show_import_preview(self, preview: dict) -> bool:
        """Zeigt Vorschau-Dialog. Gibt True zurück wenn Nutzer bestätigt."""
        win = tk.Toplevel(self.root)
        win.title("Vodafone Import – Vorschau")
        theme.center_window(win, 640, 460, self.root)
        win.grab_set()
        p = theme.current()

        # Kacheln
        tiles = [
            ("Aktualisiert", preview.get("updated", 0),         p["accent"]),
            ("Neu angelegt", preview.get("created", 0),         "#5A9A3A"),
            ("Übersprungen", preview.get("skipped", 0),         p["fg_dim"]),
            ("Fehler",       len(preview.get("errors", [])),    "#C0392B"),
        ]
        card_row = ttk.Frame(win, padding=(10, 10, 10, 4))
        card_row.pack(fill="x")
        for tile_label, tile_val, tile_color in tiles:
            cell = tk.Frame(card_row, bg=p["tile_bg"], relief="solid",
                            bd=int(p["tile_border"]),
                            highlightbackground=p["tile_border_color"])
            cell.pack(side="left", padx=6, pady=4, ipadx=12, ipady=6)
            tk.Label(cell, text=str(tile_val), font=("Segoe UI", 18, "bold"),
                     fg=tile_color, bg=p["tile_bg"]).pack()
            tk.Label(cell, text=tile_label, font=("Segoe UI", 8),
                     fg=p["tile_fg_dim"], bg=p["tile_bg"]).pack()

        ttk.Separator(win, orient="horizontal").pack(fill="x", padx=10)

        # Neue Einträge
        new_entries = preview.get("new_entries", [])
        lbl_text = (f"Neue Einträge ({len(new_entries)}):"
                    if new_entries else "Keine neuen Einträge.")
        ttk.Label(win, text=lbl_text, style="Dim.TLabel").pack(
            anchor="w", padx=12, pady=(6, 2))

        if new_entries:
            tv_frame = ttk.Frame(win)
            tv_frame.pack(fill="both", expand=True, padx=10, pady=(0, 4))
            cols = [("gsm", "GSM", 130), ("konto", "Konto", 100),
                    ("tarif", "Tarif", 140), ("plant", "Werk", 100)]
            tv = ttk.Treeview(tv_frame, columns=[c[0] for c in cols],
                              show="headings", height=8)
            for col_id, heading, width in cols:
                tv.heading(col_id, text=heading)
                tv.column(col_id, width=width)
            ys = ttk.Scrollbar(tv_frame, orient="vertical", command=tv.yview)
            tv.configure(yscrollcommand=ys.set)
            tv.grid(row=0, column=0, sticky="nsew")
            ys.grid(row=0, column=1, sticky="ns")
            tv_frame.rowconfigure(0, weight=1)
            tv_frame.columnconfigure(0, weight=1)
            for e in new_entries[:100]:
                tv.insert("", "end", values=(
                    e.get("gsm", ""), e.get("konto", ""),
                    e.get("tarif", ""), e.get("plant", ""),
                ))

        # Buttons
        confirmed = tk.BooleanVar(value=False)
        btn_frame = ttk.Frame(win, padding=(10, 6, 10, 10))
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="Import durchführen",
                   command=lambda: (confirmed.set(True), win.destroy())
                   ).pack(side="right", padx=4)
        ttk.Button(btn_frame, text="Abbrechen",
                   command=win.destroy).pack(side="right")
        win.wait_window()
        return confirmed.get()

    def _import_vodafone(self):
        if not self._require_admin():
            return
        path = filedialog.askopenfilename(
            parent=self.root, title="Vodafone-Export auswählen",
            filetypes=[("Excel-Dateien", "*.xlsx *.xls"), ("Alle Dateien", "*.*")],
        )
        if not path:
            return
        try:
            preview = vodafone_import.run_vodafone_import(path, dry_run=True)
        except Exception as exc:
            messagebox.showerror("Importfehler", str(exc), parent=self.root)
            return
        # Unsichere Struktur (Spaltenköpfe passen nicht) → nachfragen
        hw = preview.get("header_warnings") or []
        if hw:
            if not messagebox.askyesno(
                "Spaltenköpfe weichen ab",
                "Die Spaltenüberschriften der Datei entsprechen nicht der "
                "erwarteten Struktur:\n\n  • " + "\n  • ".join(hw[:8]) +
                "\n\nEin Import mit falscher Spaltenzuordnung kann Daten "
                "verfälschen. Spaltenindizes ggf. unter Einstellungen prüfen.\n\n"
                "Trotzdem fortfahren?",
                icon="warning", parent=self.root):
                return
        if not self._show_import_preview(preview):
            return
        if not self._backup_or_confirm():
            return
        try:
            result = vodafone_import.run_vodafone_import(path)
        except Exception as exc:
            logger.exception("Vodafone-Import fehlgeschlagen")
            messagebox.showerror("Importfehler", str(exc), parent=self.root)
            return
        try:
            self._show_import_result("Vodafone-Export", result.get("log_lines", []),
                                     warnings=result.get("warnings"), stats=result)
        except Exception as exc:
            logger.exception("Importprotokoll konnte nicht angezeigt werden: %s", exc)
        self.refresh_all()

    def _import_master(self):
        if not self._require_admin():
            return
        if not messagebox.askyesno(
            "Masterbestand importieren",
            "ACHTUNG: Dieser Import löscht ALLE bestehenden Teilnehmer\n"
            "und ersetzt sie durch die Daten der Excel-Datei.\n\n"
            "Vor dem Import wird automatisch ein Backup erstellt.\n\n"
            "Fortfahren?",
            icon="warning",
            parent=self.root,
        ):
            return
        path = filedialog.askopenfilename(
            parent=self.root, title="Masterbestand-Excel auswählen",
            filetypes=[("Excel-Dateien", "*.xlsx *.xls"), ("Alle Dateien", "*.*")],
        )
        if not path:
            return
        # Pflicht-Backup VOR dem Löschen aller Teilnehmer (destruktiver Import)
        if not self._backup_or_confirm():
            return
        try:
            result = master_import.run_master_import(path)
        except Exception as exc:
            logger.exception("Master-Import fehlgeschlagen")
            messagebox.showerror(
                "Importfehler",
                f"Der Masterimport ist fehlgeschlagen und wurde vollständig "
                f"zurückgerollt – der bisherige Bestand bleibt unverändert.\n\n{exc}",
                parent=self.root)
            return
        try:
            self._show_import_result(
                "Masterbestand",
                result.get("log_lines", []),
                warnings=result.get("warnings"),
                stats=result,
            )
        except Exception as exc:
            logger.exception("Importprotokoll konnte nicht angezeigt werden: %s", exc)
        self.refresh_all()

    def _import_syno(self):
        self._run_import("Syno-Export", syno_import.run_syno_import)

    def _enrich_syno(self):
        if not self._require_admin():
            return
        path = filedialog.askopenfilename(
            parent=self.root, title="Syno-Datei zum Anreichern auswählen",
            filetypes=[("Excel-Dateien", "*.xlsx *.xls"), ("Alle Dateien", "*.*")],
        )
        if not path:
            return
        try:
            result = syno_enrich.run_syno_enrich(path)
        except Exception as exc:
            logger.exception("Syno-Anreicherung fehlgeschlagen")
            messagebox.showerror("Fehler", str(exc), parent=self.root)
            return
        out = result["out_path"]
        msg = (
            f"Anreicherung abgeschlossen:\n\n"
            f"  GSM ergänzt:      {result['fixed_gsm']}\n"
            f"  GSM korrigiert:   {result['changed_gsm']}\n"
            f"  Namen ergänzt:    {result['fixed_name']}\n"
            f"  Kein Treffer:     {result['no_match']} (gelb markiert)\n\n"
            f"Gespeichert als:\n{out.name}\n\n"
            f"Bitte die gelb markierten Zeilen manuell prüfen,\n"
            f"dann die angereicherte Datei importieren."
        )
        messagebox.showinfo("Syno-Anreicherung", msg, parent=self.root)

    # ------------------------------------------------------------------
    # Hilfe
    # ------------------------------------------------------------------

    def _show_help(self):
        win = tk.Toplevel(self.root)
        win.title("Hilfe – Mobilfunkverwaltung")
        theme.center_window(win, 680, 700, self.root)
        win.resizable(True, True)
        frame = ttk.Frame(win)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, wrap="word", font=("Segoe UI", 10), padx=14, pady=12)
        ys = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=ys.set)
        ys.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        text.insert("1.0", """\
MOBILFUNKVERWALTUNG – ANLEITUNG
================================

GRUNDPRINZIP
------------
Jeder Teilnehmer/Vertrag gehört zu genau EINEM Register (Vodafone,
Telekom, O2, Ohne SIM oder Frei). Verschieben zwischen den Registern:
Rechtsklick auf den Eintrag → "Zu … verschieben".

Die Tabs Duplikate, Offene Prüfungen, Nicht zugeordnet und Unvollständig
sind KEINE eigenen Bestände, sondern automatische Arbeitslisten – dort
erscheint, was Aufmerksamkeit braucht, und verschwindet von selbst,
sobald der Grund behoben ist.


DIE REGISTER (Bestände)
-----------------------

VODAFONE
  Der Hauptbestand. Hier landen automatisch:
  • alle Einträge aus dem Masterbestand-Import
  • neue GSM-Nummern aus dem Vodafone-Import, die im Bestand fehlen
    (mit Status ✗ = ungeprüft und Hinweis in der Bemerkung)
  • Neuverträge aus dem Neuvertrag-Formular

TELEKOM / O2
  Verträge bei anderen Providern. Einträge kommen NUR durch manuelles
  Verschieben hierher (Rechtsklick). Die Register haben eigene Farben
  (Telekom grün, O2 blau) – auch die Import-Abgleiche berücksichtigen
  diese Teilnehmer.

OHNE SIM
  Geräte ohne Mobilfunkvertrag, z. B. reine Teams-Telefone oder
  WLAN-Geräte. Manuell hierher verschieben, damit sie den
  Vodafone-Bestand nicht verfälschen. Farbe: orange.

FREI
  Verträge/Geräte, die aktuell niemandem zugeordnet sind und wieder
  vergeben werden können (z. B. nach Austritt). Einträge kommen per
  Rechtsklick hierher – oder direkt aus "Nicht zugeordnet"
  (legt dann einen neuen Teilnehmer an). Farbe: violett.


DIE ARBEITSLISTEN (automatisch)
-------------------------------

DUPLIKATE
  Automatisch: alle Teilnehmer, deren Name (normalisiert) mehrfach
  vorkommt – über alle Register hinweg. Zur Bereinigung:
  "Zusammenführen …" verschmilzt 2+ ausgewählte Einträge zu einem.
  Verschwindet, sobald der Name nur noch einmal vorkommt.

OFFENE PRÜFUNGEN
  Automatisch: alle Vodafone-Einträge mit Status ✗ (ungeprüft).
  Ein Eintrag bekommt ✗, wenn:
  • Masterbestand-Import: Zeile war in der Excel-Datei gelb markiert
  • Vodafone-Import: GSM-Nummer war neu (nicht im Bestand)
  • Vodafone-Import: Konto und Werk passen nicht zur hinterlegten
    Zuordnung (Einstellungen → Werk-Konto-Mapping)
  • Manuell: Checkbox "Zur Prüfung vormerken" im Bearbeiten-Fenster
  Erledigen: Doppelklick auf die ✓/✗-Spalte oder "Als geprüft
  markieren" – der Eintrag verschwindet aus der Liste (bleibt aber
  natürlich im Register).

NICHT ZUGEORDNET
  Automatisch: Geräte aus dem Syno-Import, die keinem Teilnehmer
  zugeordnet werden konnten (kein GSM-Treffer und kein eindeutiger
  Namens-Treffer). Das Gerät wartet hier, bis Sie entscheiden:
  • "Manuell zuordnen …" – Gerät einem bestehenden Teilnehmer geben
  • "Nach 'Frei'/O2/'Ohne SIM' verschieben" – legt neuen Teilnehmer an
  • "Zu Aufgabe …" – Klärfall als Aufgabe festhalten
  • "Eintrag löschen" – wenn irrelevant
  Unterschied zu Offene Prüfungen: dort existiert der Teilnehmer schon,
  hier ist nur das Gerät bekannt, der Besitzer nicht.

UNVOLLSTÄNDIG
  Automatisch: Einträge (alle Register), bei denen Pflichtfelder fehlen.
  Die Farbe zeigt, WAS fehlt:
    rot  = GSM-Nummer fehlt
    gelb = Werk fehlt
    blau = Konto fehlt
  Felder nachtragen → Eintrag verschwindet von selbst.

WERK-ÜBERSICHT
  Kennzahlen je Standort: Gesamt, Ungeprüft, ohne Vodafone-Vertrag.
  "(kein Werk)" = Einträge, bei denen das Feld Werk leer ist – diese
  stehen auch im Tab Unvollständig.


FARB-LEGENDE
------------
  ROT + fette Schrift  = zu diesem Teilnehmer gibt es eine OFFENE
                         AUFGABE (gilt in allen Tabs, Vorrang vor allem)
  grün / blau / orange / violett = Registerfarbe (Telekom / O2 /
                         Ohne SIM / Frei)
  gelb (Suchtreffer)   = Eintrag gehört nicht zur Basisliste des Tabs,
                         wurde aber wegen einer offenen Aufgabe gefunden
  rot/gelb/blau (Tab Unvollständig) = fehlendes Feld, siehe oben


AUFGABEN  (Knopf oben rechts, Zähler = offene Aufgaben)
-------------------------------------------------------
Rechtsklick auf einen Teilnehmer (in jedem Tab) → "Zu Aufgabe …":
übernimmt die Stammdaten, im Kommentarfeld beschreiben Sie die Aufgabe.
Der Teilnehmer wird überall ROT markiert, bis die Aufgabe erledigt ist.
Auch aus "Nicht zugeordnet" möglich – passt Name/GSM eindeutig zu einem
Teilnehmer, wird die Aufgabe automatisch mit ihm verknüpft.
Optional: Fälligkeitsdatum und hohe Priorität. Überfällige Aufgaben
werden im Aufgabenfenster rot hervorgehoben, heute fällige gelb.
Im Aufgabenfenster: Erledigt umschalten, Bearbeiten (auch Fälligkeit/
Priorität), Löschen, Doppelklick öffnet den Teilnehmer. Klick auf einen
Spaltenkopf sortiert (▲/▼), das Suchfeld filtert nach Name/GSM/Werk/Text.
Jede Aufgabe erscheint zusätzlich in der Historie des Teilnehmers.


GLOBALE SUCHE  (Leiste oben, Strg+F)
------------------------------------
Durchsucht alle Register, Offene Prüfungen und Nicht zugeordnet in
einem Rutsch (Name, GSM, Werk, Konto, Tarif, SIM, Syno-Geräte,
Bemerkung). Doppelklick auf einen Treffer springt in den richtigen
Tab und markiert den Eintrag. Die Tab-Suchen durchsuchen dagegen nur
den jeweiligen Tab.


IMPORT  (Menü → Import, nur Administratoren)
--------------------------------------------
Vodafone:       Monatlicher Abgleich der Vertragsdaten (Tarif, Konto,
                SIM, Laufzeit) per GSM-Nummer. Name, Werk und Bemerkung
                werden NIE überschrieben. Unbekannte Nummern → neuer
                Eintrag mit ✗ in Offene Prüfungen. Werk wird aus dem
                Konto-Mapping abgeleitet; bei Widerspruch → Prüfhinweis.

Syno:           Geräteabgleich per GSM (bevorzugt) oder Name. Jeder
                Teilnehmer hat ZWEI Geräte-Slots (Syno 1 / Syno 2):
                der Import füllt nur LEERE Slots – vorhandene Geräte
                werden nie überschrieben, doppelte Geräte übersprungen.
                Zwei Zeilen mit gleicher Nummer füllen Slot 1 und 2.
                Kein Treffer → "Nicht zugeordnet".

Syno anreichern: Prüft die Syno-Datei VOR dem Import gegen den Bestand
                und ergänzt fehlende Namen/GSM (farbig markierte Kopie).
                Gelb = kein Treffer, bitte manuell prüfen.

Vor jedem Import wird automatisch ein Datenbank-Backup erstellt
(Ordner backups/, die letzten 10 werden behalten). Schlägt das Backup
fehl, wird nachgefragt statt still fortzufahren.

Sicherheit: Zeilen, die nicht sauber importiert werden können, gehen
NICHT verloren – sie landen zur Prüfung im Tab "Nicht zugeordnet"
(Quelle "…-Fehler"). Passen die Spaltenköpfe der Vodafone-Datei nicht
zur erwarteten Struktur, wird vor dem Import gewarnt und nachgefragt.


EINZEL-ABGLEICH  (im Bearbeiten-Fenster)
----------------------------------------
"Vodafone …" / "Syno …": sucht NUR diesen einen Datensatz in einer
Exportdatei und füllt die Formularfelder (bei Syno beide Geräte).
Nichts wird sofort gespeichert – erst prüfen, dann "Speichern".


KNOPFLEISTE UNTEN RECHTS
------------------------
Statistik:      Kennzahl-Kacheln, ablaufende Verträge (90 Tage,
                Kachel "abgelaufen" ist klickbar), Teilnehmer je Werk.
Datenqualität:  Automatische Prüfung auf typische Probleme (Konto passt
                nicht zum Werk, Platzhalter-Nummern, Gerät ohne GSM,
                abgelaufen-aber-aktiv, kein Werk). Doppelklick öffnet den
                Datensatz. "Erneut prüfen" aktualisiert.
Importhistorie: Protokoll aller Importe und Änderungen, als .txt
                speicherbar.
Audit-Log:      Anmeldungen und Benutzeränderungen (nur Admins).
Neuvertrag:     Formular "Neuvertrag bestellen" (legt Eintrag an und
                öffnet Mail an Nicole) + Liste der Bestellungen.


BACKUP & WIEDERHERSTELLEN  (Menü → Extras, nur Administratoren)
---------------------------------------------------------------
"Datenbank-Backup erstellen" sichert den aktuellen Stand.
"Backup wiederherstellen …" spielt eine frühere Sicherung zurück –
der jetzige Stand wird davor automatisch gesichert (…_vor-restore_…),
sodass sich auch die Wiederherstellung rückgängig machen lässt.


BENUTZER & ANMELDUNG  (Menü → Extras, nur Administratoren)
----------------------------------------------------------
Rollen:  Administrator (alles) · Schreib-Benutzer (lesen, bearbeiten,
importieren) · Lese-Benutzer (nur lesen/exportieren).

Windows-Anmeldung (SSO): Ist beim Benutzer ein "Windows-Login"
hinterlegt, meldet die App den angemeldeten Windows-Benutzer
automatisch an – ohne Login-Fenster, funktioniert auch offline.
Strg-Taste beim Start gedrückt halten → Login-Fenster erzwingen.


TASTENKÜRZEL
------------
  Strg+F   Globale Suche fokussieren
  Strg+S   Speichern (Bearbeiten-Fenster, Aufgaben-Dialog)
  Esc      Fenster schließen
  Strg+Z   Letzte Inline-Bearbeitung rückgängig (5 s nach Speichern)

Doppelklick auf Zeile = Bearbeiten · Doppelklick auf ✓/✗ = Prüfstatus
umschalten · Rechtsklick auf Spaltenkopf = Spalten ein-/ausblenden ·
Klick auf Spaltenkopf = sortieren (▲/▼)
""")
        text.configure(state="disabled")
        ttk.Button(win, text="Schließen", command=win.destroy).pack(pady=6)

    def _show_about(self):
        win = tk.Toplevel(self.root)
        win.title(f"Über {__app_name__}")
        win.resizable(False, False)
        win.grab_set()
        p = theme.current()
        outer = tk.Frame(win, bg=p["bg"], padx=32, pady=24)
        outer.pack(fill="both", expand=True)
        tk.Label(outer, text=__app_name__, font=("Segoe UI", 16, "bold"),
                 bg=p["bg"], fg=p["fg"]).pack()
        tk.Label(outer, text=f"Version {__version__}", font=("Segoe UI", 11),
                 bg=p["bg"], fg=p["accent"]).pack(pady=(2, 0))
        tk.Label(outer, text=f"Stand: {__build_date__}", font=("Segoe UI", 9),
                 bg=p["bg"], fg=p["fg_dim"]).pack(pady=(0, 16))
        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=(0, 12))
        tk.Label(outer,
                 text="Verwaltung von Mobilfunkverträgen und Teilnehmerdaten.\n"
                      "Import: Vodafone, Syno\n"
                      "Export: Excel, CSV, HTML/Druck",
                 font=("Segoe UI", 9), bg=p["bg"], fg=p["fg"],
                 justify="center").pack()
        ttk.Button(outer, text="Schließen", command=win.destroy).pack(pady=(16, 0))
        win.update_idletasks()
        theme.center_window(win, win.winfo_reqwidth(), win.winfo_reqheight(), self.root)


# ---------------------------------------------------------------------------
# Dialog: manuelle Zuordnung
# ---------------------------------------------------------------------------

class _AssignDialog(tk.Toplevel):
    def __init__(self, parent, unmatched_row):
        super().__init__(parent)
        self.title("Gerät manuell zuordnen")
        theme.center_window(self, 600, 500, parent)
        self.minsize(500, 400)
        self.grab_set()
        self.selected_pid: int | None = None

        ttk.Label(self, justify="left", padding=10, text=(
            f"Gerät: {unmatched_row['geraet'] or '–'}\n"
            f"GSM: {unmatched_row['gsm'] or '–'}\n"
            f"Benutzer: {unmatched_row['benutzer'] or '–'}"
        )).pack(anchor="w")

        ttk.Label(self, text="Teilnehmer suchen:", padding=(10, 0)).pack(anchor="w")
        search_var = tk.StringVar()
        ttk.Entry(self, textvariable=search_var, width=50).pack(padx=10, pady=4)

        # Buttons zuerst am unteren Rand packen → bleiben immer sichtbar
        btn_frame = ttk.Frame(self)
        btn_frame.pack(side="bottom", fill="x", padx=10, pady=8)

        def _confirm():
            sel = tv.selection()
            if not sel:
                messagebox.showinfo("Hinweis", "Bitte Teilnehmer auswählen.", parent=self)
                return
            self.selected_pid = int(sel[0])
            self.destroy()

        ttk.Button(btn_frame, text="Zuordnen",  command=_confirm).pack(side="right", padx=4)
        ttk.Button(btn_frame, text="Abbrechen", command=self.destroy).pack(side="right")

        tv_frame = ttk.Frame(self)
        tv_frame.pack(fill="both", expand=True, padx=10, pady=(0, 4))
        cols = [("id","ID",40),("name","Name",200),("gsm","GSM",130),("plant","Werk",90)]
        col_ids = [c[0] for c in cols]
        tv = ttk.Treeview(tv_frame, columns=col_ids, show="headings", selectmode="browse")
        for col_id, heading, width in cols:
            tv.heading(col_id, text=heading)
            tv.column(col_id, width=width, minwidth=40)
        ys = ttk.Scrollbar(tv_frame, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=ys.set)
        tv.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")

        tv.bind("<Double-1>", lambda e: _confirm())

        def _search(*_):
            tv.delete(*tv.get_children())
            term = search_var.get().strip()
            with db.read_connection() as conn:
                rows = db.search_participants(conn, term) if term else db.get_all_participants(conn)
            for r in rows:
                tv.insert("", "end", iid=str(r["id"]),
                          values=(r["id"], r["name"] or "", r["gsm"] or "", r["plant"] or ""))

        search_var.trace_add("write", _search)
        _search()


# ---------------------------------------------------------------------------
# Dialog: Duplikate zusammenführen
# ---------------------------------------------------------------------------

class _MergeDialog(tk.Toplevel):
    """Führt 2+ ausgewählte Teilnehmer-Datensätze zu einem zusammen.

    Pro Feld kann gewählt werden, welcher der Quell-Datensätze den Wert
    liefert (Vorbelegung: erster nicht-leerer Wert). Der gewählte
    Ziel-Datensatz behält seine ID, alle anderen werden nach dem
    Zusammenführen gelöscht.
    """

    def __init__(self, parent, rows: list, on_merged=None):
        super().__init__(parent)
        self.title(f"{len(rows)} Einträge zusammenführen")
        self._rows = rows
        self._on_merged = on_merged
        self._fields = [(f, l) for f, l in FIELD_ORDER if f not in ALWAYS_READONLY]
        self._choice_vars: dict[str, tk.IntVar] = {}

        self.resizable(True, True)
        self.grab_set()

        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        ids_txt = ", ".join(f"ID {r['id']} (Master {r['master_id'] or '-'})" for r in rows)
        ttk.Label(outer, text=f"Ausgewählt: {ids_txt}",
                  style="Dim.TLabel", wraplength=760, justify="left").pack(anchor="w", pady=(0, 8))

        # Ziel-Datensatz (bleibt erhalten, andere werden gelöscht)
        target_row = ttk.Frame(outer)
        target_row.pack(fill="x", pady=(0, 8))
        ttk.Label(target_row, text="Ziel-Datensatz (bleibt erhalten):").pack(side="left")
        self._target_id = rows[0]["id"]
        target_display_var = tk.StringVar()
        target_combo = ttk.Combobox(
            target_row, textvariable=target_display_var, state="readonly", width=40,
            values=[f"ID {r['id']} – {r['name'] or '(kein Name)'} (Master {r['master_id'] or '-'})"
                    for r in rows],
        )
        target_combo.current(0)
        target_combo.pack(side="left", padx=(6, 0))

        def _on_target_change(_evt=None):
            idx = target_combo.current()
            self._target_id = rows[idx]["id"]
        target_combo.bind("<<ComboboxSelected>>", _on_target_change)

        # Scroll-Bereich mit Feldtabelle
        canvas_frame = ttk.Frame(outer)
        canvas_frame.pack(fill="both", expand=True)
        canvas = tk.Canvas(canvas_frame, highlightthickness=0,
                           background=theme.current()["bg"])
        vs = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vs.set)
        canvas.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        table = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=table, anchor="nw")
        table.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        ttk.Label(table, text="Feld", font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        for c, row in enumerate(rows, start=1):
            ttk.Label(table, text=f"ID {row['id']}", font=("Segoe UI", 9, "bold")).grid(
                row=0, column=c, sticky="w", padx=10, pady=4)

        for r_idx, (field, label) in enumerate(self._fields, start=1):
            ttk.Label(table, text=label).grid(row=r_idx, column=0, sticky="w", padx=4, pady=2)
            var = tk.IntVar(value=0)
            self._choice_vars[field] = var
            # Vorbelegung: erster nicht-leerer Wert
            default_set = False
            for c, row in enumerate(rows):
                val = row[field] if field in row.keys() else None
                if val not in (None, "") and not default_set:
                    var.set(c)
                    default_set = True
            for c, row in enumerate(rows):
                val = row[field] if field in row.keys() else None
                text = str(val) if val not in (None, "") else "–"
                ttk.Radiobutton(table, text=text, variable=var, value=c,
                               width=28).grid(row=r_idx, column=c + 1, sticky="w", padx=10, pady=2)

        btn_frame = ttk.Frame(outer)
        btn_frame.pack(fill="x", pady=(10, 0))
        ttk.Button(btn_frame, text="Zusammenführen", command=self._confirm).pack(side="right", padx=4)
        ttk.Button(btn_frame, text="Abbrechen", command=self.destroy).pack(side="right")

        self.update_idletasks()
        w = min(1000, self.winfo_reqwidth())
        h = min(700, self.winfo_reqheight())
        theme.center_window(self, w, h, parent)

    def _confirm(self):
        target_id = self._target_id
        other_ids = [r["id"] for r in self._rows if r["id"] != target_id]

        merged: dict = {}
        for field, _label in self._fields:
            chosen_idx = self._choice_vars[field].get()
            val = self._rows[chosen_idx][field] if field in self._rows[chosen_idx].keys() else None
            merged[field] = val

        if not messagebox.askyesno(
            "Zusammenführen bestätigen",
            f"Datensatz ID {target_id} wird mit den gewählten Werten aktualisiert.\n"
            f"Danach werden folgende Datensätze gelöscht: {', '.join(str(i) for i in other_ids)}\n\n"
            "Diese Aktion kann nicht rückgängig gemacht werden. Fortfahren?",
            icon="warning", parent=self,
        ):
            return

        try:
            with db.transaction() as conn:
                # Erst löschen, dann aktualisieren – sonst kann ein gewählter
                # GSM-Wert eines noch existierenden "anderen" Datensatzes
                # einen UNIQUE-Constraint-Fehler auslösen.
                for oid in other_ids:
                    db.delete_participant(conn, oid)
                db.update_participant_fields(conn, target_id, merged)
                db.log_import(
                    conn, "GUI", "MERGE",
                    f"IDs {other_ids} in ID {target_id} zusammengeführt",
                    participant_id=target_id,
                )
        except Exception as exc:
            messagebox.showerror("Fehler beim Zusammenführen", str(exc), parent=self)
            return

        if self._on_merged:
            self._on_merged()
        self.destroy()
