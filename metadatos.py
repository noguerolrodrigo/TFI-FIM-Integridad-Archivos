import os
import stat

def leer_owner_y_permisos(ruta):
    """Devuelve (owner, permisos) del archivo, o ("N/A", "N/A") si no se puede leer.

    owner es el uid y permisos el modo en octal ("644"). Si el archivo tiene setuid,
    setgid o sticky se incluye el cuarto dígito ("4755"), porque son cambios peligrosos.
    """
    try:
        stats = os.stat(ruta)
        return str(stats.st_uid), format(stat.S_IMODE(stats.st_mode), "03o")
    except Exception:
        return "N/A", "N/A"
