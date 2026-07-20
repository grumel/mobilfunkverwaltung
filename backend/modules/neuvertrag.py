"""
neuvertrag.py – Bestellung eines Neuvertrags: E-Mail an Nicole generieren.

Öffnet einen Outlook-Entwurf (nicht automatisch gesendet) mit Betreff
"NV - <Name>" und einem persönlichen Anschreiben mit Werk, Konto und Tarif.
"""

import logging

from modules import kuendigung  # DEFAULT_TO wiederverwenden

logger = logging.getLogger(__name__)

DEFAULT_TO = kuendigung.DEFAULT_TO


def build_subject(name: str) -> str:
    return f"NV - {name}"


def build_body(name: str, werk: str, konto: str, tarif: str) -> str:
    return (
        "Hallo liebe Nicole,\n\n"
        f"ich hätte gerne einen Neuvertrag für {name}.\n\n"
        f"Werk:  {werk}\n"
        f"Konto: {konto}\n"
        f"Tarif: {tarif}\n\n"
        "Magst du dich bitte um die Erstellung kümmern?\n\n"
        "Danke dir und ganz liebe Grüße\n"
        "Holger"
    )


def create_email_draft(name: str, werk: str, konto: str, tarif: str, to: str = "") -> None:
    """Öffnet einen Outlook-Mail-Entwurf (nicht automatisch gesendet)."""
    import win32com.client

    outlook = win32com.client.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)  # olMailItem
    mail.Subject = build_subject(name)
    mail.Body = build_body(name, werk, konto, tarif)
    mail.To = to or DEFAULT_TO
    mail.Display()
