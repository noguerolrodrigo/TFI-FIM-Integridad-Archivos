import json
import os
from datetime import datetime

# Eventos que no se pudieron guardar en la BD (una línea JSON por evento)
ARCHIVO_PENDIENTES = "./logs/eventos_pendientes.jsonl"

def guardar(evento, archivo=ARCHIVO_PENDIENTES):
    """Agrega el evento al log local, con la fecha y hora (con zona) en que ocurrió."""
    os.makedirs(os.path.dirname(archivo), exist_ok=True)
    registro = {"fecha_registro": datetime.now().astimezone().isoformat()}
    registro.update(evento)
    with open(archivo, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return registro
