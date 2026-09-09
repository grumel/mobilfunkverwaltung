#!/usr/bin/env node
// Dependency-freier Integritätscheck für den gebauten React-Client.
// Prüft keine Darstellung und verändert keine Quelldateien.

import { existsSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

// fileURLToPath statt new URL(...).pathname: Unter Windows liefert .pathname
// einen fuehrenden Schraegstrich vor dem Laufwerksbuchstaben (z. B.
// "/C:/..."), was existsSync/resolve nicht als gueltigen Pfad erkennen.
const root = resolve(fileURLToPath(new URL('..', import.meta.url)))
const frontend = join(root, 'frontend')
const index = join(frontend, 'dist', 'index.html')

if (!existsSync(index)) throw new Error('frontend/dist/index.html fehlt; zuerst npm run build ausführen')
const html = readFileSync(index, 'utf8')
const assets = [...html.matchAll(/(?:src|href)="([^"]+)"/g)]
  .map(([, value]) => value)
  .filter((value) => value.startsWith('/assets/'))
for (const asset of assets) {
  if (!existsSync(join(frontend, 'dist', asset.slice(1)))) throw new Error(`Build-Asset fehlt: ${asset}`)
}

const requiredSources = [
  'src/main.jsx', 'src/App.jsx', 'src/api.js',
  'src/components/Login.jsx', 'src/components/Shell.jsx',
  'src/components/Participants.jsx', 'src/components/Documents.jsx',
]
for (const source of requiredSources) {
  if (!existsSync(join(frontend, source))) throw new Error(`Frontend-Quelle fehlt: ${source}`)
}

const api = readFileSync(join(frontend, 'src', 'api.js'), 'utf8')
for (const method of ['me', 'version', 'login', 'logout', 'participants', 'summary', 'documents']) {
  if (!new RegExp(`\\b${method}\\s*:`).test(api)) throw new Error(`API-Client-Methode fehlt: ${method}`)
}
if (!api.includes("credentials: 'same-origin'")) throw new Error('same-origin Credentials fehlen')
if (!api.includes('FormData')) throw new Error('Multipart-Upload-Unterstützung fehlt')

console.log(`Frontend regression check passed (${assets.length} build assets).`)
