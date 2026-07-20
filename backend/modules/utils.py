"""
utils.py – Gemeinsame Hilfsfunktionen für alle Importmodule.
"""

import re
from datetime import datetime, date, timedelta
from unicodedata import normalize as uni_normalize


def normalize_gsm(raw) -> str | None:
    """
    Normalisiert eine GSM-Nummer auf nationales Format (0XXXXXXXXX).

    Regeln:
    - Nicht-Ziffern und nicht-+ werden entfernt (außer führendem +)
    - +49 / 0049 / 49 (wenn Länge > 10) → führende 0
    - Leere Ergebnisse → None
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None

    # GSM-Prefix entfernen, falls vorhanden
    s = re.sub(r"(?i)^gsm\s*", "", s)
    # Erlaubte Zeichen: Ziffern + führendes +
    s = re.sub(r"[^\d+]", "", s)
    if not s:
        return None

    # Ländervorwahl +49 / 0049 → 0
    if s.startswith("+49"):
        s = "0" + s[3:]
    elif s.startswith("0049"):
        s = "0" + s[4:]
    elif s.startswith("49") and len(s) >= 12:
        # z.B. 491735123456 (12 Stellen mit 49-Prefix)
        s = "0" + s[2:]

    return s if s else None


def _excel_serial_to_date(raw) -> str | None:
    """Wandelt eine Excel-Seriennummer (z. B. 45826.5909) in YYYY-MM-DD.

    Excel zählt Tage ab dem 30.12.1899. Nur numerische Werte in einem
    plausiblen Kalenderbereich (ca. 1954–2064) werden umgewandelt, damit
    keine echten Zahlenwerte fälschlich als Datum interpretiert werden.
    """
    try:
        num = float(str(raw).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None
    if not (20000 <= num <= 60000):
        return None
    return (date(1899, 12, 30) + timedelta(days=int(num))).strftime("%Y-%m-%d")


def normalize_date(raw) -> str | None:
    """Konvertiert verschiedene Datumsformate nach YYYY-MM-DD."""
    if raw is None:
        return None
    if isinstance(raw, (datetime, date)):
        return raw.strftime("%Y-%m-%d")
    # Excel-Seriennummer (Datumsspalte kam als Zahl statt als Datum)
    serial = _excel_serial_to_date(raw)
    if serial:
        return serial
    s = str(raw).strip()[:10]
    if not s:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s


def normalize_name(raw) -> str | None:
    """Normalisiert einen Namen: NFC-Unicode, Kleinschreibung, Satzzeichen und
    Bindestriche werden zu Leerzeichen ("Fels, Markus" → "fels markus",
    "Sticker-Garcia" → "sticker garcia")."""
    if not raw:
        return None
    s = uni_normalize("NFC", str(raw))
    s = s.lower().strip()
    s = re.sub(r"[,;.\-]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip() or None


def names_match(a: str | None, b: str | None) -> bool:
    """True wenn Namen gleich oder Vorname/Nachname vertauscht."""
    if not a or not b:
        return False
    if a == b:
        return True
    pa, pb = a.split(), b.split()
    if len(pa) == 2 and len(pb) == 2:
        return pa[0] == pb[1] and pa[1] == pb[0]
    return False


def name_subset_match(a: str | None, b: str | None) -> bool:
    """Toleranter Vergleich: True, wenn alle Wörter des einen Namens im anderen
    vorkommen (Reihenfolge egal), z. B. "ralf kessel" ⊆ "kessel ralf ehem patten".
    Mindestens 2 Wörter auf beiden Seiten, um Fehltreffer zu vermeiden."""
    if not a or not b:
        return False
    ta, tb = set(a.split()), set(b.split())
    if len(ta) < 2 or len(tb) < 2:
        return False
    return ta <= tb or tb <= ta
