import os
import psycopg2
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

# Única conexión del proceso: se abre la primera vez que hace falta
_conexion = None

def conectar():
    """Devuelve la conexión a la BD. La abre la primera vez y la reabre si se cerró."""
    global _conexion
    if _conexion is None or _conexion.closed:
        _conexion = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS)
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
