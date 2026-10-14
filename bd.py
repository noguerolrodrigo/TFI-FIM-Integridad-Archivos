import threading

import psycopg2
import config

# Única conexión del proceso: se abre la primera vez que hace falta
_conexion = None

# El monitor usa la conexión desde dos hilos (eventos y decisiones): de a uno por vez.
# Quien necesite varias consultas en una misma transacción también lo toma.
candado = threading.RLock()

def conectar():
    """Devuelve la conexión a la BD. La abre la primera vez y la reabre si se cerró."""
    global _conexion
    if _conexion is None or _conexion.closed:
        _conexion = psycopg2.connect(host=config.DB_HOST, database=config.DB_NAME,
                                     user=config.DB_USER, password=config.DB_PASS)
    return _conexion

def cerrar():
    """Cierra la conexión (si quedó rota, simplemente la descarta)."""
    global _conexion
    if _conexion is not None:
        try:
            _conexion.close()
        except Exception:
            pass
    _conexion = None

def ejecutar(query, parametros=None):
    """Ejecuta una consulta, confirma y devuelve las filas (None si la consulta no devuelve nada).

    Si la conexión se cayó (por ejemplo, se reinició PostgreSQL), reconecta y reintenta una vez.
    """
    with candado:
        return _ejecutar(query, parametros)

def _ejecutar(query, parametros):
    for intento in (1, 2):
        try:
            conn = conectar()
            with conn.cursor() as cursor:
                cursor.execute(query, parametros)
                filas = cursor.fetchall() if cursor.description else None
            conn.commit()
            return filas
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            # Conexión rota: se descarta y, si era el primer intento, se prueba con una nueva
            cerrar()
            if intento == 2:
                raise
        except Exception:
            # Error de la consulta en sí: se deshace para dejar la conexión usable
            conn.rollback()
            raise
