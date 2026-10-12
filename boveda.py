import os
import shutil

# Carpeta donde se guarda la copia confiable de cada archivo de la baseline
DIRECTORIO_BOVEDA = "./boveda"

# Prefijo de los temporales que crea la restauración (el monitor los ignora)
PREFIJO_TEMPORAL = ".fim_tmp_"

def ruta_en_boveda(ruta, boveda=DIRECTORIO_BOVEDA):
    """Devuelve dónde va el respaldo de un archivo: su ruta absoluta espejada dentro de la bóveda."""
    return os.path.join(boveda, os.path.abspath(ruta).lstrip(os.sep))

def tiene_respaldo(ruta, boveda=DIRECTORIO_BOVEDA):
    """Indica si el archivo tiene una copia en la bóveda."""
    return os.path.isfile(ruta_en_boveda(ruta, boveda))

def respaldar(ruta, boveda=DIRECTORIO_BOVEDA):
    """Copia el archivo a la bóveda byte a byte, conservando permisos y fechas."""
    destino = ruta_en_boveda(ruta, boveda)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    shutil.copy2(ruta, destino)
    return destino

def restaurar(ruta, boveda=DIRECTORIO_BOVEDA):
    """Repone el archivo desde la bóveda. Lanza FileNotFoundError si no hay respaldo."""
    respaldo = ruta_en_boveda(ruta, boveda)
    carpeta, nombre = os.path.split(os.path.abspath(ruta))
    os.makedirs(carpeta, exist_ok=True)

    # Se copia a un temporal en la misma carpeta y se renombra encima del original:
    # el renombrado es atómico, así que el archivo nunca falta ni queda a medio escribir.
    temporal = os.path.join(carpeta, PREFIJO_TEMPORAL + nombre)
    shutil.copy2(respaldo, temporal)
    os.replace(temporal, ruta)
