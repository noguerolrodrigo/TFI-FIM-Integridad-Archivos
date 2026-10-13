import json
import os
from datetime import datetime
import config

def guardar(evento, archivo=None):
    """Agrega el evento al log local (una línea JSON), con la fecha y hora con zona en que ocurrió."""
    archivo = archivo or config.ARCHIVO_PENDIENTES
    os.makedirs(os.path.dirname(archivo), exist_ok=True)
    registro = {"fecha_registro": datetime.now().astimezone().isoformat()}
    registro.update(evento)
    with open(archivo, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return registro
