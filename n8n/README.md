# Orquestación con n8n

n8n recibe los avisos del monitor, manda las alertas por Telegram y registra la decisión de la
persona en la BD. **No toca archivos ni corre comandos**: lo que n8n decide lo ejecuta el monitor
(`monitor_fim.py`), que es el que tiene permisos sobre los archivos vigilados.

```
monitor_fim.py ──POST {evento_id}──▶ n8n (PB-B) ──▶ Telegram: alerta con diff + opciones
      ▲                                │
      │                                └──▶ INSERT decisiones (fim_n8n)
      └──── cada 2 s lee decisiones nuevas, las ejecuta e inserta en ejecuciones (fim_user)
```

## 1. Instalación (una sola vez, sin sudo)

n8n 2.x necesita Node 24. Se instala con nvm en el usuario, sin tocar el Node del sistema ni el
`.bashrc`:

```bash
curl -fsSL -o /tmp/instalar_nvm.sh https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh
PROFILE=/dev/null bash /tmp/instalar_nvm.sh
export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"
nvm install 24
npm install -g n8n@2.41.4
```

La versión de n8n está fijada a propósito: los workflows exportados se probaron con esa versión.

## 2. Arrancar n8n

```bash
./n8n/iniciar_n8n.sh
```

- Abre n8n en <http://localhost:5678> (también desde el navegador de Windows).
- Los datos de n8n (workflows y credenciales cifradas) quedan en `~/n8n_fim/.n8n`, fuera del repo.
- n8n arranca con un entorno limpio: del `.env` solo recibe `TELEGRAM_CHAT_ID`,
  `N8N_WEBHOOK_SECRETO` y `TELEGRAM_WEBHOOK_SECRETO`. Nunca recibe `DB_PASS` ni el token del bot.
- Telemetría, avisos de versión y API pública de n8n quedan apagados.

## 3. Configuración en el navegador (una sola vez)

1. **Cuenta de usuario.** La primera vez n8n pide crear la cuenta dueña (owner). Usar una
   contraseña fuerte: es lo que protege el editor.
2. **Credencial de Telegram.** *Overview → Create → Credential → Telegram API*.
   - Nombre: `Telegram FIM`
   - Access Token: el valor de `TELEGRAM_BOT_TOKEN` del `.env`.
3. **Credencial de Postgres.** *Create → Credential → Postgres*.
   - Nombre: `Postgres FIM (fim_n8n)`
   - Host `localhost`, Database `fim_db`, User `fim_n8n`, Password: la de `fim_n8n`, Port `5432`,
     SSL `disable`.

Los nombres tienen que ser exactamente esos: los workflows buscan las credenciales por nombre.

Los secretos que usan los workflows se leen de variables de entorno (`$env`) que pone
`iniciar_n8n.sh`; las credenciales se referencian por nombre.
