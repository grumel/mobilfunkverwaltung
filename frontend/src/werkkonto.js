import { api } from './api'

// Werk↔Konto-Zuordnung einmal laden und cachen (feste Paare aus den Daten).
let cache = null
let pending = null

export function loadWerkKonto() {
  if (cache) return Promise.resolve(cache)
  if (!pending) {
    pending = api.werkKonto()
      .then((d) => { cache = d; return d })
      .catch(() => ({ werk_to_konto: {}, konto_to_werk: {} }))
  }
  return pending
}
