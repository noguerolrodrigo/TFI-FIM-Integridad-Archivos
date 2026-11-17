import fnmatch
import os

import boveda
import config

# Los temporales de editores salen de la configuración (PATRONES_IGNORADOS). No se vigilan ni
# entran en la baseline, para no generar falsos positivos.
#
# De la restauración solo se ignoran los temporales que este mismo proceso tiene creados en este
# momento (boveda.temporales_propios). No se ignora por prefijo: cualquiera puede crear un archivo
# llamado .fim_tmp_algo, y si el nombre alcanzara para ignorarlo sería una forma de esconderse.

def es_ignorado(ruta):
    """Indica si es un temporal propio de la restauración o si su nombre coincide con un patrón ignorado."""
    if os.path.abspath(ruta) in boveda.temporales_propios:
        return True
    nombre = os.path.basename(ruta)
    return any(fnmatch.fnmatch(nombre, patron) for patron in config.PATRONES_IGNORADOS)
