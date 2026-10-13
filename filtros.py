import fnmatch
import os

import boveda
import config

# Los temporales de editores salen de la configuración (PATRONES_IGNORADOS). No se vigilan ni
# entran en la baseline, para no generar falsos positivos. Los temporales de nuestra propia
# restauración se ignoran siempre.
PATRON_RESTAURACION = boveda.PREFIJO_TEMPORAL + "*"

def es_ignorado(ruta):
    """Indica si el nombre del archivo coincide con alguno de los patrones ignorados."""
    nombre = os.path.basename(ruta)
    return any(fnmatch.fnmatch(nombre, patron) for patron in config.PATRONES_IGNORADOS + [PATRON_RESTAURACION])
