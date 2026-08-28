Dokumentvorlagen (Word) fuer Kuendigung und Ruecknahme
======================================================

Hier hinein gehoeren genau diese zwei Dateien:

    vorlage_kuendigung.docx
    vorlage_ruecknahme.docx

Sie werden beim Installieren (install.ps1 bzw. Mobilfunkverwaltung.cmd)
automatisch nach

    %PROGRAMDATA%\Mobilfunkverwaltung\Dokumente\

kopiert - aber nur, wenn dort noch keine gleichnamige Datei liegt
(vorhandene, echte Vorlagen werden nie ueberschrieben).

Platzhalter in den Vorlagen (Jinja/docxtpl-Syntax):
    {{ nummer }}   - GSM-Rufnummer
    {{ datum }}    - heutiges Datum als TT.MM.JJJJ
