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

## 4. Importar los workflows

Con n8n **detenido** (Ctrl+C en la terminal donde corre):

```bash
./n8n/importar_workflows.sh
./n8n/iniciar_n8n.sh
```

El script importa los JSON de esta carpeta, les pone el id que tienen en tu instalación las
credenciales del paso 3 (las busca por nombre; nunca lee sus datos) y los publica. Al arrancar,
n8n tarda unos segundos más en activar los webhooks.

Para que el monitor avise a n8n, el `.env` tiene que tener
`N8N_WEBHOOK_URL=http://localhost:5678/webhook/fim-evento`.

## Workflows

| Archivo | Qué hace |
|---|---|
| `PB-B_deteccion_respuesta.json` | Recibe el aviso del monitor, valida el secreto, lee el evento y su historial de la BD, manda la alerta por Telegram con el diff y espera la decisión con links locales (van como texto para copiar: Telegram no linkea `localhost`). También confirma por Telegram cuando el monitor ejecutó la decisión. |
| `PB-A_baseline_autorizada.json` | Formulario en <http://localhost:5678/form/fim-ventana> para abrir una ventana de mantenimiento. Pide sesión iniciada en n8n y registra quién la abrió. |
| `respaldo_notificaciones.json` | Cada minuto reenvía a PB-B los eventos de la última hora que quedaron sin notificar (por ejemplo, si n8n estaba apagado). |

### Qué opciones trae cada alerta

| El monitor... | Opciones |
|---|---|
| restauró solo (modo automático) o aisló un archivo nuevo | *Fue un incidente* / *Era un cambio autorizado* |
| dejó el archivo esperando (modo aprobación) | *Restaurar* / *Aceptar cambio* |
| registró un cambio dentro de una ventana de mantenimiento | *Pasar a la baseline* / *Restaurar* |

Los links van como texto para copiar y pegar en el navegador de la PC (Telegram no linkea
`localhost`), valen 24 h y llevan una firma que genera n8n,
así que no se pueden adivinar. Se puede decidir una sola vez por evento: la BD rechaza una segunda
decisión.

## Seguridad

- n8n no corre comandos ni toca archivos: inserta la decisión y la ejecuta el monitor.
- El webhook del monitor exige el header `X-FIM-Secreto` (si no coincide, responde 403) y solo
  recibe el id del evento: el contenido de la alerta sale siempre de la BD.
- El rol `fim_n8n` solo puede leer y agregar filas en sus tablas (migración 06).

Los secretos que usan los workflows se leen de variables de entorno (`$env`) que pone
`iniciar_n8n.sh`; las credenciales se referencian por nombre.
