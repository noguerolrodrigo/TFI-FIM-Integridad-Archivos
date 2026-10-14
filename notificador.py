import json
import threading
import urllib.request

import config

# Aviso push a n8n: el monitor ya registró el evento en la BD y le avisa a n8n que hay algo nuevo.
# Solo se manda el id y el resultado; n8n lee el resto (archivo, hashes, diff) de la BD, así un
# POST falso no puede inventar contenido. El header secreto evita que cualquiera dispare alertas.

TIMEOUT_SEGUNDOS = 2

def notificar(datos):
    """Manda los datos a n8n en un hilo aparte: nunca bloquea al monitor ni lanza excepciones.

    Si n8n no responde, el evento queda sin fila en notificaciones y lo levanta el workflow de respaldo.
    Devuelve el hilo (para los tests) o None si no hay webhook configurado.
    """
    if not config.N8N_WEBHOOK_URL:
        return None
    hilo = threading.Thread(target=_enviar, args=(config.N8N_WEBHOOK_URL, datos), daemon=True)
    hilo.start()
    return hilo

def _enviar(url, datos):
    pedido = urllib.request.Request(
        url,
        data=json.dumps(datos).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-FIM-Secreto": config.N8N_WEBHOOK_SECRETO},
        method="POST",
    )
    try:
        with urllib.request.urlopen(pedido, timeout=TIMEOUT_SEGUNDOS) as respuesta:
            respuesta.read()
    except Exception as e:
        print(f"[!] No se pudo avisar a n8n ({datos}): {e}")
