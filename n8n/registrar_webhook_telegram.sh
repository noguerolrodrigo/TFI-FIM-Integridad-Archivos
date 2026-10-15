#!/usr/bin/env bash
#
# Le dice a Telegram adónde mandar los toques de los botones.
#   Uso: ./n8n/registrar_webhook_telegram.sh            registra el webhook (con el túnel ngrok arriba)
#        ./n8n/registrar_webhook_telegram.sh --borrar   lo borra (queda solo el link local)
#
# - La URL pública la toma del agente de ngrok que está corriendo (API local en 127.0.0.1:4040).
# - Registra el secret_token: Telegram lo manda en el header X-Telegram-Bot-Api-Secret-Token y el
#   workflow rechaza (403) lo que no lo traiga.
# - Solo pide los toques de botones (allowed_updates = callback_query).
# - El token del bot nunca aparece en pantalla ni en la línea de comandos: curl lo lee por stdin.
#
set -euo pipefail

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

leer_env() {
    grep -E "^$1=" "$PROYECTO/.env" | tail -n 1 | cut -d= -f2- | tr -d '\r'
}

TOKEN="$(leer_env TELEGRAM_BOT_TOKEN)"
SECRETO="$(leer_env TELEGRAM_WEBHOOK_SECRETO)"
SUFIJO="$(leer_env TELEGRAM_WEBHOOK_SUFIJO)"
for variable in TOKEN SECRETO SUFIJO; do
    if [ -z "${!variable}" ]; then
        echo "[!] Falta un valor en el .env (TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRETO o TELEGRAM_WEBHOOK_SUFIJO)." >&2
        exit 1
    fi
done

# Llama a un método de la Bot API sin poner el token en la línea de comandos
telegram() {
    local metodo="$1"; shift
    printf 'url = "https://api.telegram.org/bot%s/%s"\n' "$TOKEN" "$metodo" | curl -s -K - "$@"
}

# Muestra la respuesta de Telegram tapando el sufijo de la URL
mostrar() {
    python3 -c '
import json, sys
r = json.load(sys.stdin)
sufijo = sys.argv[1]
texto = json.dumps(r, ensure_ascii=False, indent=2).replace(sufijo, "<sufijo>")
print(texto)' "$SUFIJO"
}

if [ "${1:-}" = "--borrar" ]; then
    telegram deleteWebhook --data-urlencode "drop_pending_updates=true" | mostrar
    exit 0
fi

PUBLICA="$(curl -s http://127.0.0.1:4040/api/tunnels | python3 -c '
import json, sys
tuneles = json.load(sys.stdin).get("tunnels", [])
print(next((t["public_url"] for t in tuneles if t["public_url"].startswith("https://")), ""))' 2>/dev/null || true)"
if [ -z "$PUBLICA" ]; then
    echo "[!] No encuentro el túnel de ngrok. Arrancalo con ./n8n/iniciar_ngrok.sh en otra terminal." >&2
    exit 1
fi

echo "[*] Registrando el webhook en $PUBLICA/webhook/telegram-<sufijo>"
telegram setWebhook \
    --data-urlencode "url=$PUBLICA/webhook/telegram-$SUFIJO" \
    --data-urlencode "secret_token=$SECRETO" \
    --data-urlencode 'allowed_updates=["callback_query"]' \
    --data-urlencode "drop_pending_updates=true" | mostrar
echo "[*] Estado según Telegram:"
telegram getWebhookInfo | mostrar
