#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1}"
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
TIMEOUT="${SMOKE_TIMEOUT:-10}"
COOKIE_JAR="$(mktemp)"
LOGIN_BODY="$(mktemp)"

fail() {
  printf '[FAIL] %s\n' "$*" >&2
  exit 1
}

check_http_200() {
  local label="$1" url="$2" output="$3" status
  status="$(curl --silent --show-error --location --max-time "$TIMEOUT" \
    --output "$output" --write-out '%{http_code}' "$url")" || \
    fail "$label ist nicht erreichbar: $url"
  [ "$status" = "200" ] || fail "$label liefert HTTP $status statt 200: $url"
  printf '[OK] %s: %s\n' "$label" "$url"
}

backend_body="$(mktemp)"
frontend_body="$(mktemp)"
trap 'rm -f "$COOKIE_JAR" "$LOGIN_BODY" "$backend_body" "$frontend_body"' EXIT

check_http_200 "Backend /api/version" "$BACKEND_URL/api/version" "$backend_body"
grep -q '"build"' "$backend_body" || fail "Backend-Antwort enthält keine Build-Information."

check_http_200 "Caddy/Frontend" "$BASE_URL/" "$frontend_body"
grep -Eqi '<!doctype html|<html' "$frontend_body" || fail "Frontend-Antwort ist kein HTML-Dokument."
if grep -Eqi '<title>[^<]*(error|fehler)|502 Bad Gateway|Internal Server Error' "$frontend_body"; then
  fail "Frontend-Antwort sieht wie eine Fehlerseite aus."
fi

if [ -n "${SMOKE_USERNAME:-}" ] || [ -n "${SMOKE_PASSWORD:-}" ]; then
  [ -n "${SMOKE_USERNAME:-}" ] && [ -n "${SMOKE_PASSWORD:-}" ] || \
    fail "SMOKE_USERNAME und SMOKE_PASSWORD müssen gemeinsam gesetzt werden."

  SMOKE_USERNAME="$SMOKE_USERNAME" SMOKE_PASSWORD="$SMOKE_PASSWORD" \
    python3 -c 'import json, os, sys; json.dump({"username": os.environ["SMOKE_USERNAME"], "password": os.environ["SMOKE_PASSWORD"]}, sys.stdout)' \
    > "$LOGIN_BODY"

  login_status="$(curl --silent --show-error --max-time "$TIMEOUT" \
    --cookie-jar "$COOKIE_JAR" --header 'Content-Type: application/json' \
    --data-binary "@$LOGIN_BODY" --output /dev/null --write-out '%{http_code}' \
    "$BASE_URL/api/login")" || fail "Login-Endpunkt ist nicht erreichbar."
  [ "$login_status" = "200" ] || fail "Login-Test liefert HTTP $login_status statt 200."

  me_status="$(curl --silent --show-error --max-time "$TIMEOUT" \
    --cookie "$COOKIE_JAR" --output /dev/null --write-out '%{http_code}' \
    "$BASE_URL/api/me")" || fail "Authentifizierter API-Test ist fehlgeschlagen."
  [ "$me_status" = "200" ] || fail "Authentifizierte API liefert HTTP $me_status statt 200."
  printf '[OK] Optionaler Login- und Session-Test\n'
else
  printf '[SKIP] Login-Test: SMOKE_USERNAME/SMOKE_PASSWORD sind nicht gesetzt.\n'
fi

printf '[PASS] Linux-Smoke-Test erfolgreich.\n'
