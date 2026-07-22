"""
kuendigung.py – Kündigungs-/Rücknahme-Schreiben aus Word-Vorlage erzeugen,
als PDF speichern und als Outlook-Entwurf mit Anhang öffnen.

Das Füllen der Vorlage läuft über docxtpl und ist plattformneutral: Linux und
Windows verwenden denselben Weg, es wird weder Word noch COM benötigt. Nur die
optionalen Schritte danach sind plattformgebunden:
  - PDF über Word-COM (`convert_to_pdf`, nur Windows-Desktop) oder über
    LibreOffice (`convert_to_pdf_soffice`, beide Plattformen – die Web-API
    benutzt ausschließlich diesen Weg)
  - Outlook-Entwurf über COM (`create_outlook_draft`, nur Windows-Desktop)

Platzhalter in den Vorlagen (Jinja-Syntax):
  {{ nummer }} – GSM-Nummer
  {{ datum }}  – heutiges Datum als DD.MM.YYYY

Vorlagen ohne `{{ datum }}` werden weiterhin unterstützt: dort wird ein
vorhandenes Datum im Format DD.MM.YYYY nachträglich aktualisiert.
"""

import logging
import os
import re
import unicodedata
from pathlib import Path
from datetime import datetime, date

import docx
from docxtpl import DocxTemplate

from modules.paths import DATA_DIR

logger = logging.getLogger(__name__)

BASE_DIR      = DATA_DIR
TEMPLATE_DIR  = BASE_DIR / "Dokumente"
OUTPUT_DIR    = BASE_DIR / "Kuendigungen"

TEMPLATES = {
    "kuendigung": TEMPLATE_DIR / "vorlage_kuendigung.docx",
    "ruecknahme": TEMPLATE_DIR / "vorlage_ruecknahme.docx",
}

# Bis einschließlich v1.0 enthielten die Dateinamen Umlaute. Linux speichert
# sie als NFC, macOS und einzelne Windows-Werkzeuge als NFD; beim Kopieren des
# Datenordners zwischen den Systemen schlug der Zugriff dadurch fehl. Die alten
# Namen bleiben übergangsweise lesbar, damit eine bestehende Installation nach
# einem Update nicht stehenbleibt.
LEGACY_TEMPLATES = {
    "kuendigung": "vorlage_kündigung.docx",
    "ruecknahme": "vorlage_rücknahme.docx",
}

SUBJECTS = {
    "kuendigung": "Kündigung GSM {gsm}",
    "ruecknahme": "Rücknahme Kündigung GSM {gsm}",
}

DEFAULT_TO = "nicole.dieckmann@zinxs.com"

BODIES = {
    "kuendigung": (
        "Hallo liebe Nicole,\n\n"
        "anbei die Kündigung für die GSM-Nummer {gsm} – magst du dich bitte "
        "wieder darum kümmern?\n\n"
        "Danke dir und ganz liebe Grüße\n"
        "Holger"
    ),
    "ruecknahme": (
        "Hallo liebe Nicole,\n\n"
        "anbei die Rücknahme der Kündigung für die GSM-Nummer {gsm} – magst "
        "du dich bitte wieder darum kümmern?\n\n"
        "Danke dir und ganz liebe Grüße\n"
        "Holger"
    ),
}

_DATE_RE = re.compile(r"\d{2}\.\d{2}\.\d{4}")


def _update_date_paragraph(paragraph) -> None:
    """Ersetzt ein Datum im Format DD.MM.YYYY durch das heutige Datum."""
    if not paragraph.runs or not _DATE_RE.search(paragraph.text):
        return
    new_text = _DATE_RE.sub(date.today().strftime("%d.%m.%Y"), paragraph.text)
    if new_text != paragraph.text:
        paragraph.runs[0].text = new_text
        for r in paragraph.runs[1:]:
            r.text = ""


def _update_dates_in_document(path: Path) -> None:
    """Aktualisiert Datumsangaben in Vorlagen ohne `{{ datum }}`-Platzhalter."""
    doc = docx.Document(str(path))
    for p in doc.paragraphs:
        _update_date_paragraph(p)
    doc.save(str(path))


def resolve_template(kind: str) -> Path:
    """Liefert den Pfad der Vorlage und akzeptiert übergangsweise den alten Namen."""
    if kind not in TEMPLATES:
        raise ValueError(f"Unbekannter Schreiben-Typ: {kind}")
    template = TEMPLATES[kind]
    if template.exists():
        return template

    legacy_name = LEGACY_TEMPLATES[kind]
    for form in ("NFC", "NFD"):
        legacy = template.parent / unicodedata.normalize(form, legacy_name)
        if legacy.exists():
            logger.warning(
                "Alte Vorlage %s verwendet. Bitte in %s umbenennen; die "
                "Unterstützung der Umlaut-Namen entfällt in einer späteren Version.",
                legacy.name, template.name,
            )
            return legacy
    raise FileNotFoundError(f"Vorlage nicht gefunden: {template}")


def generate_letter(kind: str, gsm: str) -> Path:
    """Füllt die Vorlage aus und speichert sie als neue .docx. Gibt den Pfad zurück."""
    template = resolve_template(kind)
    gsm = (gsm or "").strip() or "unbekannt"

    tpl = DocxTemplate(str(template))
    # docxtpl setzt Platzhalter zusammen, die Word über mehrere Runs verteilt
    # hat; Absätze und Tabellen werden gleichermaßen erfasst.
    variables = tpl.get_undeclared_template_variables()
    tpl.render({"nummer": gsm, "datum": date.today().strftime("%d.%m.%Y")})

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"{kind}_{gsm}_{ts}.docx"
    tpl.save(str(out_path))

    if "datum" not in variables:
        logger.info("Vorlage %s hat keinen {{ datum }}-Platzhalter; Datum wird "
                    "ersatzweise über das Format DD.MM.YYYY aktualisiert.", template.name)
        _update_dates_in_document(out_path)

    logger.info("Schreiben erzeugt: %s", out_path.name)
    return out_path


def convert_to_pdf(docx_path: Path) -> Path:
    """Konvertiert eine .docx über installiertes MS Word (COM) zu PDF.

    Nutzt Dispatch() statt DispatchEx(): eine isolierte Word-Instanz
    (DispatchEx) kann bei OneDrive-Pfaden mit Leerzeichen/Sonderzeichen
    keinen Zugriff auf die Datei bekommen ("Datei nicht gefunden").
    """
    import time
    import win32com.client

    docx_path = docx_path.resolve()
    pdf_path = docx_path.with_suffix(".pdf")
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    try:
        wdoc = word.Documents.Open(
            str(docx_path), ReadOnly=False, ConfirmConversions=False,
            AddToRecentFiles=False,
        )
        try:
            # Vereinzelt ist das COM-Objekt direkt nach Open() noch nicht
            # vollständig bereit (SaveAs wirft dann AttributeError) – kurz
            # warten und erneut versuchen.
            last_exc = None
            for attempt in range(3):
                try:
                    wdoc.SaveAs(str(pdf_path), FileFormat=17)  # wdFormatPDF
                    last_exc = None
                    break
                except AttributeError as exc:
                    last_exc = exc
                    logger.warning("SaveAs-Versuch %d fehlgeschlagen, erneut …", attempt + 1)
                    time.sleep(0.7)
            if last_exc:
                raise last_exc
        finally:
            wdoc.Close(False)
    finally:
        word.Quit()
    return pdf_path


def convert_to_pdf_soffice(docx_path: Path) -> Path:
    """Konvertiert eine .docx über LibreOffice (headless) zu PDF – für den
    Linux-Server (statt Word-COM). Nutzt ein eigenes, temporäres LibreOffice-
    Profil, damit es nicht mit einer offenen LibreOffice-Sitzung kollidiert."""
    import shutil
    import subprocess
    import tempfile

    docx_path = Path(docx_path).resolve()
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError("LibreOffice (soffice) nicht gefunden – bitte installieren.")

    outdir = docx_path.parent
    with tempfile.TemporaryDirectory(prefix="mobilfunk_soffice_") as profile:
        cmd = [
            soffice,
            f"-env:UserInstallation={Path(profile).resolve().as_uri()}",
            "--headless", "--nologo", "--nofirststartwizard",
            "--convert-to", "pdf", "--outdir", str(outdir), str(docx_path),
        ]
        # HOME auf das Temp-Profil setzen: der Dienstbenutzer (z. B. 'mobilfunk')
        # hat kein nutzbares Home; ohne HOME kann LibreOffice scheitern.
        env = dict(os.environ, HOME=profile)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
    pdf_path = docx_path.with_suffix(".pdf")
    if not pdf_path.exists():
        raise RuntimeError(
            "PDF-Erzeugung fehlgeschlagen"
            + (f": {proc.stderr.strip()}" if proc.stderr else ".")
        )
    logger.info("PDF erzeugt (LibreOffice): %s", pdf_path.name)
    return pdf_path


def create_outlook_draft(pdf_path: Path, subject: str, body: str = "", to: str = "") -> None:
    """Öffnet einen Outlook-Mail-Entwurf mit PDF-Anhang (nicht automatisch gesendet)."""
    import win32com.client

    outlook = win32com.client.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)  # olMailItem
    mail.Subject = subject
    if body:
        mail.Body = body
    if to:
        mail.To = to
    mail.Attachments.Add(str(pdf_path))
    mail.Display()


def create_and_open(kind: str, gsm: str, name: str = "", to: str = "") -> Path:
    """Kompletter Ablauf: Vorlage füllen → PDF erzeugen → Outlook-Entwurf öffnen."""
    docx_path = generate_letter(kind, gsm)
    pdf_path = convert_to_pdf(docx_path)
    gsm_txt = gsm or "unbekannt"
    subject = SUBJECTS[kind].format(gsm=gsm_txt)
    body = BODIES[kind].format(gsm=gsm_txt)
    create_outlook_draft(pdf_path, subject=subject, body=body, to=to or DEFAULT_TO)
    return pdf_path
