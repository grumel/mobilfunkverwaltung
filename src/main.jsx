import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import { getTheme, applyTheme } from './theme.js'

// Theme früh anwenden (vor dem ersten Render), damit kein Aufblitzen entsteht.
applyTheme(getTheme())

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
