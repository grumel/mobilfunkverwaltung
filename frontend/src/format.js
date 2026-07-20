// Zentrale Datumsformatierung: ISO (YYYY-MM-DD) -> deutsch (TT.MM.YYYY).
// Leere/fehlende Werte bleiben leer (kein Ersatzdatum). Uhrzeit-Anteile in
// Zeitstempeln (YYYY-MM-DD HH:MM:SS) bleiben unverändert erhalten.
export function fmtDate(value) {
  if (value === null || value === undefined || value === '') return ''
  return String(value).replace(/(\d{4})-(\d{2})-(\d{2})/g, '$3.$2.$1')
}

// Für Tabellenzellen: leeres Datum als Gedankenstrich anzeigen (wie übrige Spalten).
export function fmtDateCell(value) {
  const s = fmtDate(value)
  return s === '' ? '—' : s
}
