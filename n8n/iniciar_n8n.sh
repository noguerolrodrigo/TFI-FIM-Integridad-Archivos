#!/usr/bin/env bash
#
# Levanta n8n para el FIM.   Uso: ./n8n/iniciar_n8n.sh
#
# - Usa Node 24 instalado con nvm (n8n 2.x exige Node >= 24; el Node del sistema no se toca).
# - n8n arranca con un entorno limpio: del .env solo recibe el chat_id y los secretos de los
#   webhooks. Nunca recibe DB_PASS ni el token del bot (el token se carga como credencial en la UI).
# - Los datos de n8n (workflows, credenciales cifradas y su clave) quedan en ~/n8n_fim/.n8n,
#   fuera del repositorio.
#
set -euo pipefail

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION_N8N="2.41.4"
PUERTO=5678
DATOS_N8N="$HOME/n8n_fim"

export NVM_DIR="$HOME/.nvm"
if [ ! -s "$NVM_DIR/nvm.sh" ]; then
    echo "[!] No está nvm. Ver n8n/README.md, paso 1." >&2
    exit 1
fi
. "$NVM_DIR/nvm.sh"
nvm use 24 >/dev/null

if [ "$(n8n --version 2>/dev/null)" != "$VERSION_N8N" ]; then
    echo "[!] Falta n8n $VERSION_N8N. Instalarlo con: npm install -g n8n@$VERSION_N8N" >&2
    exit 1
fi

# Lee una variable del .env sin mostrarla (tolera saltos de línea de Windows)
leer_env() {
    grep -E "^$1=" "$PROYECTO/.env" | tail -n 1 | cut -d= -f2- | tr -d '\r'
}

TELEGRAM_CHAT_ID="$(leer_env TELEGRAM_CHAT_ID)"
N8N_WEBHOOK_SECRETO="$(leer_env N8N_WEBHOOK_SECRETO)"
TELEGRAM_WEBHOOK_SECRETO="$(leer_env TELEGRAM_WEBHOOK_SECRETO)"
for variable in TELEGRAM_CHAT_ID N8N_WEBHOOK_SECRETO; do
    if [ -z "${!variable}" ]; then
        echo "[!] Falta $variable en el .env (ver .env.example)." >&2
        exit 1
    fi
done

echo "[*] n8n $VERSION_N8N en http://localhost:$PUERTO  (Ctrl+C para detenerlo)"

exec env -i \
    HOME="$HOME" PATH="$PATH" TERM="${TERM:-xterm}" LANG="${LANG:-C.UTF-8}" \
    N8N_USER_FOLDER="$DATOS_N8N" \
    N8N_PORT="$PUERTO" \
    N8N_HOST=localhost \
    N8N_EDITOR_BASE_URL="http://localhost:$PUERTO" \
    GENERIC_TIMEZONE=America/Argentina/Mendoza \
    TZ=America/Argentina/Mendoza \
    N8N_DIAGNOSTICS_ENABLED=false \
    N8N_VERSION_NOTIFICATIONS_ENABLED=false \
    N8N_PERSONALIZATION_ENABLED=false \
    N8N_PUBLIC_API_DISABLED=true \
    N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true \
    N8N_BLOCK_ENV_ACCESS_IN_NODE=false \
    FIM_URL_LOCAL="http://localhost:$PUERTO" \
    TELEGRAM_CHAT_ID="$TELEGRAM_CHAT_ID" \
    N8N_WEBHOOK_SECRETO="$N8N_WEBHOOK_SECRETO" \
    TELEGRAM_WEBHOOK_SECRETO="$TELEGRAM_WEBHOOK_SECRETO" \
    n8n start
