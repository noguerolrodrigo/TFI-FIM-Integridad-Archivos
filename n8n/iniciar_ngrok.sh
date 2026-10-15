#!/usr/bin/env bash
#
# Publica en internet el webhook de Telegram de n8n, y nada más.   Uso: ./n8n/iniciar_ngrok.sh
#
# - Usa el dominio gratuito asignado a la cuenta de ngrok (el authtoken se carga una vez con
#   "ngrok config add-authtoken").
# - La Traffic Policy (n8n/ngrok_politica.yml) deja pasar solo POST /webhook/telegram-<sufijo>.
# - n8n tiene que estar corriendo (./n8n/iniciar_n8n.sh) en otra terminal.
#
set -euo pipefail

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUERTO=5678

leer_env() {
    grep -E "^$1=" "$PROYECTO/.env" | tail -n 1 | cut -d= -f2- | tr -d '\r'
}

SUFIJO="$(leer_env TELEGRAM_WEBHOOK_SUFIJO)"
if [ -z "$SUFIJO" ]; then
    echo "[!] Falta TELEGRAM_WEBHOOK_SUFIJO en el .env (generarlo con: openssl rand -hex 16)." >&2
    exit 1
fi
if ! curl -s -o /dev/null "http://localhost:$PUERTO/healthz"; then
    echo "[!] n8n no está corriendo en el puerto $PUERTO. Arrancalo con ./n8n/iniciar_n8n.sh." >&2
    exit 1
fi

# La política completa con el sufijo va a un archivo temporal que solo puede leer este usuario
umask 077
POLITICA="$(mktemp)"
trap 'rm -f "$POLITICA"' EXIT
sed "s/__TELEGRAM_WEBHOOK_SUFIJO__/$SUFIJO/" "$PROYECTO/n8n/ngrok_politica.yml" > "$POLITICA"

echo "[*] Túnel ngrok hacia n8n (solo el webhook de Telegram). Ctrl+C para cerrarlo."
echo "    Con el túnel arriba, registrá el webhook con ./n8n/registrar_webhook_telegram.sh"
ngrok http "$PUERTO" --traffic-policy-file "$POLITICA"
