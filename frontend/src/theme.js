// Hell/Dunkel-Umschaltung. Setzt data-theme am <html>-Element und merkt sich
// die Wahl in localStorage. Ohne Wahl richtet es sich nach dem System.
const KEY = 'mdw-theme'

export function getTheme() {
  const saved = localStorage.getItem(KEY)
  if (saved === 'dark' || saved === 'light') return saved
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t)
  localStorage.setItem(KEY, t)
}

export function toggleTheme() {
  const next = getTheme() === 'dark' ? 'light' : 'dark'
  applyTheme(next)
  return next
}
