"""
theme.py – Zentrales Theming für die Mobilfunkverwaltung.

Light- und Dark-Mode über ttk.Style (clam-Basis).
"""

import tkinter as tk
from tkinter import ttk

PALETTE: dict[str, dict[str, str]] = {
    "light": {
        "bg":                "#F0F2F5",
        "bg_widget":         "#FFFFFF",
        "fg":                "#1E293B",
        "fg_dim":            "#64748B",
        "accent":            "#2563EB",
        "accent_hover":      "#1D4ED8",
        "accent_fg":         "#FFFFFF",
        "select_bg":         "#2563EB",
        "select_fg":         "#FFFFFF",
        "tree_bg":           "#FFFFFF",
        "heading_bg":        "#E4E9F0",
        "heading_fg":        "#374151",
        "border":            "#D6DEE8",
        "tag_odd_dup":       "#EEF2FF",
        "tag_missing_gsm":   "#FFE4E4",
        "tag_missing_plant": "#FEF9C3",
        "tag_missing_konto": "#DBEAFE",
        "tag_warn":          "#FEF9C3",
        "tag_soon":          "#FEF9C3",
        "tag_urgent":        "#FDECEA",
        "tag_zebra":         "#F5F7FA",
        "tag_telekom":       "#E8F5E9",
        "tag_telekom_z":     "#DAECDC",
        "tag_task":          "#EDE7F6",
        "tag_has_task_bg":   "#FFD3D3",
        "tag_has_task_fg":   "#B00020",
        "tag_frei":          "#F3F0FF",
        "tag_frei_z":        "#E6DFFB",
        "tag_o2":            "#E3F2FD",
        "tag_o2_z":          "#D2E9FB",
        "tag_ohnesim":       "#FFF4E5",
        "tag_ohnesim_z":     "#FFE9CC",
        "chart_colors":      "#2E6DA4,#3A86C8,#5AA0D8,#7BBCE8",
        "stat_canvas_bg":    "#FFFFFF",
        "log_bg":            "#F8F9FB",
        "log_fg":            "#1E293B",
        "statusbar_bg":      "#E8ECF0",
        "tile_bg":           "#FFFFFF",
        "tile_border":       "1",
        "tile_border_color": "#E2E8F0",
        "tile_fg_dim":       "#64748B",
        "warn_banner_bg":    "#FEF9C3",
        "warn_banner_fg":    "#854D0E",
        "legend_bg_gsm":     "#FFE4E4",
        "legend_bg_plant":   "#FEF9C3",
        "legend_bg_konto":   "#DBEAFE",
        "legend_fg":         "#1E293B",
    },
    "dark": {
        "bg":                "#1C2128",
        "bg_widget":         "#22272E",
        "fg":                "#E6EDF3",
        "fg_dim":            "#8B98A5",
        "accent":            "#4493F8",
        "accent_hover":      "#5BA3F5",
        "accent_fg":         "#FFFFFF",
        "select_bg":         "#1F4E8C",
        "select_fg":         "#FFFFFF",
        "tree_bg":           "#22272E",
        "heading_bg":        "#2D333B",
        "heading_fg":        "#B6C1CC",
        "border":            "#444C56",
        "tag_odd_dup":       "#1C2040",
        "tag_missing_gsm":   "#4A2020",
        "tag_missing_plant": "#3A3200",
        "tag_missing_konto": "#0D2744",
        "tag_warn":          "#3A3200",
        "tag_soon":          "#3A3200",
        "tag_urgent":        "#3D1A1A",
        "tag_zebra":         "#282D34",
        "tag_telekom":       "#1E3527",
        "tag_telekom_z":     "#25402F",
        "tag_task":          "#2E2440",
        "tag_has_task_bg":   "#5A1F1F",
        "tag_has_task_fg":   "#FFB3B3",
        "tag_frei":          "#2A2540",
        "tag_frei_z":        "#332C4D",
        "tag_o2":            "#17324A",
        "tag_o2_z":          "#1E3C57",
        "tag_ohnesim":       "#3D2F1B",
        "tag_ohnesim_z":     "#4A3A23",
        "chart_colors":      "#4493F8,#5BA3F5,#74B3F8,#8DC4FB",
        "stat_canvas_bg":    "#22272E",
        "log_bg":            "#22272E",
        "log_fg":            "#E6EDF3",
        "statusbar_bg":      "#161B22",
        "tile_bg":           "#2D333B",
        "tile_border":       "1",
        "tile_border_color": "#444C56",
        "tile_fg_dim":       "#768390",
        "warn_banner_bg":    "#3A3200",
        "warn_banner_fg":    "#FFD54F",
        "legend_bg_gsm":     "#4A2020",
        "legend_bg_plant":   "#3A3200",
        "legend_bg_konto":   "#0D2744",
        "legend_fg":         "#CDD9E5",
    },
}

_mode: str = "light"


def current() -> dict[str, str]:
    return PALETTE[_mode]


def center_window(win: tk.Toplevel, w: int, h: int, parent: tk.Misc | None = None) -> None:
    """Setzt Größe+Position eines Fensters – zentriert über dem Elternfenster
    (falls angegeben und sichtbar), sonst zentriert auf dem Bildschirm.

    Ohne diese Funktion platziert Tk neue Toplevel-Fenster stur links oben.
    """
    win.update_idletasks()
    if parent is not None:
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            if pw > 1 and ph > 1:
                x = px + (pw - w) // 2
                y = py + (ph - h) // 2
                win.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
                return
        except Exception:
            pass
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")


def is_dark() -> bool:
    return _mode == "dark"


def apply(root: tk.Tk, dark: bool = False) -> None:
    global _mode
    _mode = "dark" if dark else "light"
    p = PALETTE[_mode]

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    root.configure(bg=p["bg"])

    # ── Base ────────────────────────────────────────────────────────────
    style.configure(".",
        background=p["bg"],
        foreground=p["fg"],
        troughcolor=p["bg_widget"],
        selectbackground=p["select_bg"],
        selectforeground=p["select_fg"],
        fieldbackground=p["bg_widget"],
        insertcolor=p["fg"],
        font=("Segoe UI", 10),
        borderwidth=0,
    )

    # ── Containers ──────────────────────────────────────────────────────
    style.configure("TFrame",            background=p["bg"])
    style.configure("TLabelframe",       background=p["bg"], bordercolor=p["border"])
    style.configure("TLabelframe.Label", background=p["bg"], foreground=p["fg"])
    style.configure("TLabel",            background=p["bg"], foreground=p["fg"])
    style.configure("TCheckbutton",      background=p["bg"], foreground=p["fg"])
    style.map("TCheckbutton",
        background=[("active", p["bg"]), ("hover", p["bg"])],
        foreground=[("active", p["fg"])],
    )
    style.configure("TSeparator",        background=p["border"])

    # ── Dim label (count labels, status text) ───────────────────────────
    style.configure("Dim.TLabel",
        background=p["bg"],
        foreground=p["fg_dim"],
        font=("Segoe UI", 9),
    )

    # ── Button ──────────────────────────────────────────────────────────
    style.configure("TButton",
        background=p["heading_bg"],
        foreground=p["fg"],
        bordercolor=p["border"],
        darkcolor=p["border"],
        lightcolor=p["border"],
        relief="flat",
        padding=(12, 6),
    )
    style.map("TButton",
        background=[("active", p["accent"]), ("pressed", p["select_bg"])],
        foreground=[("active", p["accent_fg"]), ("pressed", p["accent_fg"])],
        relief=[("pressed", "flat")],
    )
    # Größere Knöpfe für die untere Leiste (Aufgaben, Statistik, …)
    style.configure("Big.TButton",
        font=("Segoe UI", 11),
        padding=(18, 9),
    )
    # Akzent-Knopf für die jeweilige Hauptaktion (Speichern, + Neu, …)
    style.configure("Accent.TButton",
        background=p["accent"],
        foreground=p["accent_fg"],
        bordercolor=p["accent"],
        darkcolor=p["accent"],
        lightcolor=p["accent"],
    )
    style.map("Accent.TButton",
        background=[("active", p["accent_hover"]), ("pressed", p["select_bg"])],
        foreground=[("active", p["accent_fg"]), ("pressed", p["accent_fg"])],
    )

    # ── Entry / Combobox ────────────────────────────────────────────────
    style.configure("TEntry",
        fieldbackground=p["bg_widget"],
        foreground=p["fg"],
        insertcolor=p["fg"],
        bordercolor=p["border"],
        lightcolor=p["border"],
        darkcolor=p["border"],
        padding=(8, 5),
    )
    style.map("TEntry",
        bordercolor=[("focus", p["accent"])],
        lightcolor=[("focus", p["accent"])],
        darkcolor=[("focus", p["accent"])],
    )
    style.configure("TCombobox",
        fieldbackground=p["bg_widget"],
        foreground=p["fg"],
        selectbackground=p["select_bg"],
        selectforeground=p["select_fg"],
        bordercolor=p["border"],
        arrowcolor=p["fg"],
    )
    style.map("TCombobox",
        fieldbackground=[("readonly", p["bg_widget"])],
        foreground=[("readonly", p["fg"])],
        selectbackground=[("readonly", p["select_bg"])],
    )

    # ── Notebook ────────────────────────────────────────────────────────
    style.configure("TNotebook",
        background=p["bg"],
        borderwidth=0,
        tabmargins=(4, 4, 4, 0),
    )
    style.configure("TNotebook.Tab",
        background=p["bg"],
        foreground=p["fg_dim"],
        padding=(18, 9),
        font=("Segoe UI", 10, "bold"),
        borderwidth=0,
    )
    style.map("TNotebook.Tab",
        background=[("selected", p["accent"]), ("active", p["heading_bg"])],
        foreground=[("selected", p["accent_fg"]), ("active", p["fg"])],
        expand=[("selected", [1, 1, 1, 0])],
    )

    # ── Treeview ────────────────────────────────────────────────────────
    style.configure("Treeview",
        background=p["tree_bg"],
        foreground=p["fg"],
        fieldbackground=p["tree_bg"],
        rowheight=30,
        font=("Segoe UI", 10),
        borderwidth=0,
    )
    style.configure("Treeview.Heading",
        background=p["heading_bg"],
        foreground=p["heading_fg"],
        font=("Segoe UI", 10, "bold"),
        padding=(8, 8),
        relief="flat",
    )
    style.map("Treeview",
        background=[("selected", p["select_bg"])],
        foreground=[("selected", p["select_fg"])],
    )
    style.map("Treeview.Heading",
        background=[("active", p["accent"])],
        foreground=[("active", p["accent_fg"])],
        relief=[("active", "flat")],
    )

    # ── Scrollbar ───────────────────────────────────────────────────────
    style.configure("TScrollbar",
        background=p["bg"],
        troughcolor=p["bg_widget"],
        arrowcolor=p["fg_dim"],
        borderwidth=0,
        relief="flat",
    )
    style.map("TScrollbar",
        background=[("active", p["fg_dim"])],
    )

    # ── Statusbar ───────────────────────────────────────────────────────
    style.configure("Statusbar.TFrame",  background=p["statusbar_bg"])
    style.configure("Statusbar.TLabel",
        background=p["statusbar_bg"],
        foreground=p["fg_dim"],
        font=("Segoe UI", 10),
        padding=(4, 3),
    )
    style.configure("Statusbar.TSeparator", background=p["border"])
