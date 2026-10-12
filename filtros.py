import fnmatch
import os

import boveda

# Archivos temporales que crean los editores al guardar, más los de nuestra propia restauración.
# No se vigilan ni entran en la baseline, para no generar falsos positivos.
PATRONES_IGNORADOS = [
    "*.swp", "*.swo", "*.swx",       # intercambio de vim
    "*~",                            # copias de respaldo de editores
    "*.tmp",                         # temporales genéricos
    boveda.PREFIJO_TEMPORAL + "*",   # temporales de la restauración del FIM
]

def es_ignorado(ruta):
    """Indica si el nombre del archivo coincide con alguno de los patrones ignorados."""
    nombre = os.path.basename(ruta)
    return any(fnmatch.fnmatch(nombre, patron) for patron in PATRONES_IGNORADOS)
