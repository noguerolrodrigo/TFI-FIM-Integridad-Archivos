import os
import shutil
import stat
import tempfile
import config

# La carpeta de la bóveda sale de la configuración (DIR_BOVEDA). Las funciones aceptan
# otra carpeta por parámetro, que es lo que usan los tests.

# Prefijo de los temporales que crea la restauración. El resto del nombre es aleatorio, y el
# prefijo solo sirve para reconocerlos a simple vista: el monitor no ignora nada por llevarlo.
PREFIJO_TEMPORAL = ".fim_tmp_"

# Rutas de los temporales que este proceso tiene creados en este momento
temporales_propios = set()

def ruta_en_boveda(ruta, boveda=None):
    """Devuelve dónde va el respaldo de un archivo: su ruta absoluta espejada dentro de la bóveda."""
    return os.path.join(boveda or config.DIRECTORIO_BOVEDA, os.path.abspath(ruta).lstrip(os.sep))

def tiene_respaldo(ruta, boveda=None):
    """Indica si el archivo tiene una copia en la bóveda."""
    return os.path.isfile(ruta_en_boveda(ruta, boveda))

def respaldar(ruta, boveda=None):
    """Copia el archivo a la bóveda byte a byte, conservando permisos y fechas."""
    destino = ruta_en_boveda(ruta, boveda)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    shutil.copy2(ruta, destino)
    return destino

def restaurar(ruta, boveda=None, owner=None):
    """Repone el archivo desde la bóveda. Lanza FileNotFoundError si no hay respaldo.

    owner es el uid que tiene que quedar como dueño (el de la baseline). Devuelve False si el
    contenido se repuso pero el dueño no se pudo cambiar.
    """
    return reponer_desde(ruta_en_boveda(ruta, boveda), ruta, owner)

def reponer_propietario(descriptor, owner):
    """Deja el archivo abierto a nombre del uid pedido. Devuelve False si no se pudo.

    owner llega como lo guarda la baseline: el uid en texto, o "N/A" si no se pudo leer.
    """
    if owner is None or not str(owner).isdigit():
        return True
    uid = int(owner)
    if os.fstat(descriptor).st_uid == uid:
        return True
    try:
        # Cambiar el dueño de un archivo solo lo puede hacer root. El grupo no se toca (-1):
        # la baseline no lo registra.
        os.fchown(descriptor, uid, -1)
        return True
    except OSError:
        return False

def reponer_desde(origen, ruta, owner=None):
    """Copia origen sobre ruta (bytes, permisos y fechas) sin que el archivo quede a medio escribir.

    Si se pasa owner (uid), el archivo queda a nombre de ese usuario. Devuelve False si eso no
    se pudo (falta root): el contenido se repone igual.
    """
    carpeta, nombre = os.path.split(os.path.abspath(ruta))
    os.makedirs(carpeta, exist_ok=True)

    # Se copia a un temporal en la misma carpeta y se renombra encima del original:
    # el renombrado es atómico, así que el archivo nunca falta ni queda a medio escribir.
    with open(origen, "rb") as fuente:
        # mkstemp elige un nombre aleatorio y crea el archivo con O_CREAT | O_EXCL | O_NOFOLLOW:
        # si en ese nombre ya hay algo (por ejemplo un enlace simbólico puesto por un atacante),
        # falla y prueba con otro en vez de escribir a través del enlace.
        descriptor, temporal = tempfile.mkstemp(prefix=PREFIJO_TEMPORAL, dir=carpeta)
        temporales_propios.add(temporal)
        try:
            # Todo se hace sobre el descriptor ya abierto, no sobre el nombre: aunque alguien
            # cambie lo que hay en ese nombre, se sigue escribiendo en el archivo que se creó.
            with os.fdopen(descriptor, "wb") as destino:
                shutil.copyfileobj(fuente, destino)
                destino.flush()
                datos = os.fstat(fuente.fileno())
                # El temporal nace a nombre del usuario que corre el monitor. El dueño se repone
                # antes del renombrado, para que el archivo nunca aparezca en su ruta con otro
                # dueño, y antes de los permisos, porque cambiar el dueño borra el bit setuid.
                propietario_repuesto = reponer_propietario(destino.fileno(), owner)
                os.fchmod(destino.fileno(), stat.S_IMODE(datos.st_mode))
                os.utime(destino.fileno(), ns=(datos.st_atime_ns, datos.st_mtime_ns))
            # os.replace renombra el nombre, sin seguir enlaces: si ruta es un enlace, lo reemplaza
            os.replace(temporal, ruta)
            return propietario_repuesto
        except BaseException:
            if os.path.lexists(temporal):
                os.unlink(temporal)
            raise
        finally:
            temporales_propios.discard(temporal)

def quitar(ruta, boveda=None):
    """Borra el respaldo de un archivo que salió de la baseline (si lo había)."""
    respaldo = ruta_en_boveda(ruta, boveda)
    if os.path.isfile(respaldo):
        os.remove(respaldo)

def limpiar_huerfanos(directorio, rutas_vigentes, boveda=None):
    """Borra de la bóveda los respaldos de ese directorio que ya no están en la baseline vigente."""
    vigentes = {ruta_en_boveda(ruta, boveda) for ruta in rutas_vigentes}
    borrados = 0
    for root, dirs, files in os.walk(ruta_en_boveda(directorio, boveda)):
        for file in files:
            respaldo = os.path.join(root, file)
            if respaldo not in vigentes:
                os.remove(respaldo)
                borrados += 1
    return borrados
