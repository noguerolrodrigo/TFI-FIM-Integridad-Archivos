#!/usr/bin/env bash
#
# n8n descartable para pruebas y mediciones, con Telegram simulado y la BD fim_pruebas.
#
#   ./scripts/n8n_de_pruebas.sh iniciar    lo levanta con los workflows del repo importados
#   ./scripts/n8n_de_pruebas.sh detener    lo apaga y borra sus datos
#
# - Corre en el puerto 5690 (el n8n real usa 5678 y su broker interno el 5679).
# - Sus datos y la clave de cifrado van a /tmp/fim_n8n_pruebas y se borran al detenerlo.
# - Telegram es simulado (scripts/telegram_falso.py): no sale ningún mensaje a internet. Lo que se
#   "mandó" queda en /tmp/fim_n8n_pruebas/telegram.jsonl.
# - La credencial de Postgres apunta a fim_pruebas con fim_user (dueño de esa base); nunca a fim_db.
# - El webhook del monitor queda en http://localhost:5690/webhook/fim-evento con el secreto
#   "secreto-de-pruebas", y el chat de Telegram simulado es el 424242.
#
set -euo pipefail

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATOS="/tmp/fim_n8n_pruebas"
PUERTO=5690
PUERTO_TELEGRAM=8081

leer_env() {
    grep -E "^$1=" "$PROYECTO/.env" | tail -n 1 | cut -d= -f2- | tr -d '\r'
}

arrancar_n8n() {
    nohup env -i HOME="$HOME" PATH="$PATH" LANG=C.UTF-8 \
        N8N_USER_FOLDER="$DATOS" N8N_PORT="$PUERTO" N8N_RUNNERS_BROKER_PORT=5691 N8N_HOST=localhost \
        N8N_EDITOR_BASE_URL="http://localhost:$PUERTO" WEBHOOK_URL="http://localhost:$PUERTO/" \
        GENERIC_TIMEZONE=America/Argentina/Mendoza TZ=America/Argentina/Mendoza \
        N8N_DIAGNOSTICS_ENABLED=false N8N_VERSION_NOTIFICATIONS_ENABLED=false \
        N8N_PERSONALIZATION_ENABLED=false N8N_PUBLIC_API_DISABLED=true N8N_BLOCK_ENV_ACCESS_IN_NODE=false \
        FIM_URL_LOCAL="http://localhost:$PUERTO" TELEGRAM_CHAT_ID=424242 \
        N8N_WEBHOOK_SECRETO=secreto-de-pruebas TELEGRAM_WEBHOOK_SECRETO=secreto-telegram-de-pruebas \
        n8n start > "$DATOS/n8n.log" 2>&1 &
    echo $! > "$DATOS/n8n.pid"
    for _ in $(seq 1 90); do
        grep -q "$1" "$DATOS/n8n.log" 2>/dev/null && return 0
        sleep 2
    done
    echo "[!] n8n de pruebas no arrancó; ver $DATOS/n8n.log" >&2
    exit 1
}

parar_n8n() {
    if [ -f "$DATOS/n8n.pid" ]; then
        kill "$(cat "$DATOS/n8n.pid")" 2>/dev/null || true
        for _ in $(seq 1 30); do curl -s -o /dev/null "http://localhost:$PUERTO/healthz" || break; sleep 1; done
        rm -f "$DATOS/n8n.pid"
    fi
}

detener() {
    parar_n8n
    if [ -f "$DATOS/telegram.pid" ]; then
        kill "$(cat "$DATOS/telegram.pid")" 2>/dev/null || true
    fi
    rm -rf "$DATOS"
    echo "[*] n8n de pruebas detenido y borrado."
}

iniciar() {
    if curl -s -o /dev/null "http://localhost:$PUERTO/healthz"; then
        echo "[!] Ya hay algo en el puerto $PUERTO. Si es un n8n de pruebas viejo: $0 detener" >&2
        exit 1
    fi
    rm -rf "$DATOS"
    mkdir -p "$DATOS"
    chmod 700 "$DATOS"

    export NVM_DIR="$HOME/.nvm"
    . "$NVM_DIR/nvm.sh"
    nvm use 24 >/dev/null

    nohup python3 "$PROYECTO/scripts/telegram_falso.py" "$PUERTO_TELEGRAM" "$DATOS/telegram.jsonl" \
        > /dev/null 2>&1 &
    echo $! > "$DATOS/telegram.pid"

    # Primer arranque: crea su base y una cuenta dueña descartable (la contraseña no se guarda)
    arrancar_n8n "Editor is now accessible"
    CLAVE="Pruebas-$(openssl rand -hex 12)"
    curl -s -o /dev/null -X POST "http://localhost:$PUERTO/rest/owner/setup" -H 'Content-Type: application/json' \
        -d "{\"email\":\"pruebas@fim.local\",\"firstName\":\"Pruebas\",\"lastName\":\"FIM\",\"password\":\"$CLAVE\"}"
    parar_n8n

    # Credenciales con los mismos nombres que las reales, apuntando a Telegram simulado y fim_pruebas
    umask 077
    python3 - "$PROYECTO/.env" "$DATOS/credenciales.json" "$PUERTO_TELEGRAM" <<'PY'
import json, sys
entorno = dict(l.rstrip("\r\n").split("=", 1) for l in open(sys.argv[1], encoding="utf-8") if "=" in l)
json.dump([
    {"id": "pruebasTelegram1", "name": "Telegram FIM", "type": "telegramApi",
     "data": {"accessToken": "TOKEN-DE-PRUEBAS", "baseUrl": f"http://127.0.0.1:{sys.argv[3]}"}},
    {"id": "pruebasPostgres1", "name": "Postgres FIM (fim_n8n)", "type": "postgres",
     "data": {"host": entorno["DB_HOST"], "database": "fim_pruebas", "user": entorno["DB_USER"],
              "password": entorno["DB_PASS"], "port": 5432, "ssl": "disable",
              "maxConnections": 10, "allowUnauthorizedCerts": False}},
], open(sys.argv[2], "w"))
PY
    N8N_USER_FOLDER="$DATOS" n8n import:credentials --input="$DATOS/credenciales.json" > /dev/null 2>&1
    rm -f "$DATOS/credenciales.json"
    DATOS_N8N="$DATOS" PUERTO="$PUERTO" "$PROYECTO/n8n/importar_workflows.sh" > "$DATOS/importacion.log" 2>&1

    arrancar_n8n "Finished building workflow dependency index"
    # Los webhooks se activan unos segundos después del arranque
    for _ in $(seq 1 30); do
        codigo="$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://localhost:$PUERTO/webhook/fim-evento")"
        [ "$codigo" = "403" ] && break
        sleep 1
    done
    echo "[*] n8n de pruebas listo en http://localhost:$PUERTO (Telegram simulado, BD fim_pruebas)."
}

case "${1:-}" in
    iniciar) iniciar ;;
    detener) detener ;;
    *) echo "Uso: $0 iniciar | detener" >&2; exit 2 ;;
esac
