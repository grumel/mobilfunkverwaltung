#!/usr/bin/env python3
"""Erzeugt docs/ANLEITUNG.pdf aus docs/ANLEITUNG.md.

Kein generischer Markdown-Parser - deckt genau die in diesem Dokument
verwendeten Konstrukte ab: #/##/### Ueberschriften, Absaetze (ueber
Zeilenumbrueche zusammengefasst bis zur Leerzeile), GFM-Pipe-Tabellen,
"- "-Listen, "> "-Zitate, "---"-Trenner, **fett**, *kursiv*, [text](url)-Links,
`code`. Emoji/Symbole ohne WinAnsi-Deckung (siehe SYMBOL_MAP) werden ersetzt,
da die Standard-PDF-Schrift (Helvetica) sie sonst als kaputte Boxen zeigt.

Aufruf (nach jeder Aenderung an ANLEITUNG.md):
    pip install reportlab   # einmalig, falls nicht vorhanden
    python scripts/build-anleitung-pdf.py docs/ANLEITUNG.md docs/ANLEITUNG.pdf
"""
import re
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, ListFlowable, ListItem)
from reportlab.lib.enums import TA_LEFT

SRC, DST = sys.argv[1], sys.argv[2]

BLUE = colors.HexColor("#004D90")
LIGHT_BLUE = colors.HexColor("#EAF1FB")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle("H1", parent=styles["Title"], fontSize=20, spaceAfter=4,
                          textColor=BLUE, alignment=TA_LEFT))
styles.add(ParagraphStyle("H2", parent=styles["Heading1"], fontSize=15, spaceBefore=16,
                          spaceAfter=8, textColor=BLUE))
styles.add(ParagraphStyle("H3", parent=styles["Heading2"], fontSize=12.5, spaceBefore=10,
                          spaceAfter=6, textColor=colors.HexColor("#333333")))
styles.add(ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10, leading=14,
                          spaceAfter=8))
styles.add(ParagraphStyle("MyBullet", parent=styles["Body"], leftIndent=14, bulletIndent=0,
                          spaceAfter=4))
styles.add(ParagraphStyle("Quote", parent=styles["Body"], leftIndent=14, textColor=colors.HexColor("#555555"),
                          borderColor=BLUE, borderWidth=0, spaceAfter=8))
styles.add(ParagraphStyle("Cell", parent=styles["Body"], fontSize=9, leading=12, spaceAfter=0))
styles.add(ParagraphStyle("CellHead", parent=styles["Cell"], textColor=colors.white, fontName="Helvetica-Bold"))
styles.add(ParagraphStyle("Meta", parent=styles["Body"], fontSize=8.5, textColor=colors.HexColor("#777777")))


# Emoji/Sonderzeichen, die Helvetica (WinAnsi) nicht abdeckt - PDF-Ersatz.
# Der Rest (– „ … sind in WinAnsi enthalten und bleiben unveraendert.
SYMBOL_MAP = {
    "→": "->",       # →
    "↶": "",         # ↶ - im Text steht direkt daneben schon "Rueckgaengig"
    "☀": "Sonne",    # ☀ (Design-Umschalter, steht als "Mond/Sonne")
    "⚙": "",         # ⚙ - im Text steht direkt daneben schon "Einstellungen"
    "️": "",         # unsichtbarer Emoji-Variationsselektor
    "\U0001f319": "Mond",  # 🌙 (Design-Umschalter)
    "\U0001f534": "",       # 🔴 - Wort "rot" steht direkt daneben
    "\U0001f7e0": "",       # 🟠 - Wort "orange" steht direkt daneben
    "\U0001f7e2": "",       # 🟢 - Wort "gruen" steht direkt daneben
}


def inline(text: str) -> str:
    for ch, repl in SYMBOL_MAP.items():
        text = text.replace(ch, repl)
    text = re.sub(r"\s{2,}", " ", text)
    text = text.replace("&", "&amp;")
    # Markdown-Links: interne Anker (#...) -> nur Text, echte URLs -> klickbar
    def link(m):
        label, url = m.group(1), m.group(2)
        if url.startswith("#"):
            return label
        return f'<a href="{url}" color="#004D90"><u>{label}</u></a>'
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", text)  # einfaches *kursiv*
    text = re.sub(r"`([^`]+)`", r'<font face="Courier" size="9">\1</font>', text)
    return text


def split_row(line: str):
    cells = line.strip().strip("|").split("|")
    return [c.strip() for c in cells]


def is_sep_row(cells):
    return all(re.fullmatch(r":?-+:?", c) for c in cells)


def build():
    lines = open(SRC, encoding="utf-8").read().splitlines()
    story = []
    buf = []  # gesammelte Absatz-Zeilen

    def flush_para():
        if buf:
            story.append(Paragraph(inline(" ".join(buf)), styles["Body"]))
            buf.clear()

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped == "":
            flush_para()
            i += 1
            continue

        if stripped == "---":
            flush_para()
            story.append(Spacer(1, 4))
            story.append(HRFlowable(width="100%", color=colors.HexColor("#CCCCCC"), thickness=0.8))
            story.append(Spacer(1, 8))
            i += 1
            continue

        if stripped.startswith("| "):
            flush_para()
            table_lines = []
            while i < n and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            rows = [split_row(r) for r in table_lines]
            if len(rows) > 1 and is_sep_row(rows[1]):
                rows.pop(1)
            data = []
            for ridx, row in enumerate(rows):
                style = styles["CellHead"] if ridx == 0 else styles["Cell"]
                data.append([Paragraph(inline(c), style) for c in row])
            ncols = max(len(r) for r in data)
            colw = (170 * mm) / ncols
            t = Table(data, colWidths=[colw] * ncols, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BLUE]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(t)
            story.append(Spacer(1, 10))
            continue

        if stripped.startswith("# "):
            flush_para()
            story.append(Paragraph(inline(stripped[2:]), styles["H1"]))
            story.append(HRFlowable(width="100%", color=BLUE, thickness=1.4))
            story.append(Spacer(1, 10))
            i += 1
            continue
        if stripped.startswith("## "):
            flush_para()
            story.append(Paragraph(inline(stripped[3:]), styles["H2"]))
            i += 1
            continue
        if stripped.startswith("### "):
            flush_para()
            story.append(Paragraph(inline(stripped[4:]), styles["H3"]))
            i += 1
            continue

        if re.match(r"^\d+\.\s", stripped) or stripped.startswith("- "):
            flush_para()
            items = []
            while i < n and (re.match(r"^\d+\.\s", lines[i].strip()) or lines[i].strip().startswith("- ")):
                text = re.sub(r"^(\d+\.\s|- )", "", lines[i].strip())
                items.append(Paragraph(inline(text), styles["MyBullet"]))
                i += 1
            story.append(ListFlowable([ListItem(p, spaceAfter=2) for p in items],
                                      bulletType="bullet", leftIndent=16))
            story.append(Spacer(1, 6))
            continue

        if stripped.startswith("> "):
            flush_para()
            quote_lines = []
            while i < n and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            story.append(Paragraph(inline(" ".join(quote_lines)), styles["Quote"]))
            story.append(Spacer(1, 6))
            continue

        if stripped.startswith("*") and not stripped.startswith("**"):
            # Kursiver Block ueber ggf. mehrere Zeilen (*...* als Fussnote).
            flush_para()
            block = []
            while i < n and lines[i].strip() != "":
                block.append(lines[i].strip())
                if lines[i].strip().endswith("*"):
                    i += 1
                    break
                i += 1
            text = " ".join(block).strip()
            if text.startswith("*"):
                text = text[1:]
            if text.endswith("*"):
                text = text[:-1]
            story.append(Spacer(1, 10))
            story.append(Paragraph(inline(text), styles["Meta"]))
            continue

        buf.append(stripped)
        i += 1

    flush_para()
    return story


doc = SimpleDocTemplate(DST, pagesize=A4,
                        leftMargin=20 * mm, rightMargin=20 * mm,
                        topMargin=18 * mm, bottomMargin=18 * mm,
                        title="Mobilfunkverwaltung - Benutzerhandbuch")
doc.build(build())
print("PDF geschrieben:", DST)
