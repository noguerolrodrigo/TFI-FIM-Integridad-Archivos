import os
import shutil
import config

# La carpeta de la bóveda sale de la configuración (DIR_BOVEDA). Las funciones aceptan
# otra carpeta por parámetro, que es lo que usan los tests.

# Prefijo de los temporales que crea la restauración (el monitor los ignora)
PREFIJO_TEMPORAL = ".fim_tmp_"

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

def restaurar(ruta, boveda=None):
    """Repone el archivo desde la bóveda. Lanza FileNotFoundError si no hay respaldo."""
    respaldo = ruta_en_boveda(ruta, boveda)
    carpeta, nombre = os.path.split(os.path.abspath(ruta))
    os.makedirs(carpeta, exist_ok=True)

    # Se copia a un temporal en la misma carpeta y se renombra encima del original:
    # el renombrado es atómico, así que el archivo nunca falta ni queda a medio escribir.
    temporal = os.path.join(carpeta, PREFIJO_TEMPORAL + nombre)
    shutil.copy2(respaldo, temporal)
    os.replace(temporal, ruta)

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
