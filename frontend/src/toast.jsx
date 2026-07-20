import { useState, useEffect } from 'react'

// Minimales Toast-System ohne Abhängigkeiten. Komponenten rufen toast(msg, typ),
// die <ToastHost/> (einmal in App gemountet) zeigt die Meldungen dezent an.
let idCounter = 0
const listeners = new Set()

export function toast(message, type = 'info') {
  const item = { id: ++idCounter, message, type }
  listeners.forEach((fn) => fn(item))
}
export const toastError = (m) => toast(m, 'error')
export const toastOk = (m) => toast(m, 'ok')

export function ToastHost() {
  const [items, setItems] = useState([])
  useEffect(() => {
    const add = (item) => {
      setItems((cur) => [...cur, item])
      const ms = item.type === 'error' ? 6000 : 3500
      setTimeout(() => setItems((cur) => cur.filter((x) => x.id !== item.id)), ms)
    }
    listeners.add(add)
    return () => listeners.delete(add)
  }, [])

  function dismiss(id) { setItems((cur) => cur.filter((x) => x.id !== id)) }

  return (
    <div className="toasthost">
      {items.map((t) => (
        <div key={t.id} className={'toast ' + t.type} onClick={() => dismiss(t.id)} role="status">
          {t.message}
        </div>
      ))}
    </div>
  )
}
