import os
from dotenv import load_dotenv

# Carpeta del proyecto. Las rutas relativas de la configuración se resuelven desde acá,
# no desde la carpeta donde se ejecute el script.
RAIZ = os.path.dirname(os.path.abspath(__file__))

# Cargar variables de entorno del archivo .env
load_dotenv(os.path.join(RAIZ, ".env"))

def ruta_absoluta(ruta):
    """Convierte una ruta de la configuración en absoluta y normalizada."""
    return os.path.normpath(os.path.join(RAIZ, os.path.expanduser(ruta.strip())))

def leer_rutas(valor):
    """Convierte "ruta1:ruta2" en una lista de rutas absolutas."""
    return [ruta_absoluta(ruta) for ruta in valor.split(":") if ruta.strip()]

def leer_patrones(valor):
    """Convierte "*.swp,*~" en una lista de patrones."""
    return [patron.strip() for patron in valor.split(",") if patron.strip()]

def dentro_de(ruta, directorio):
    """Indica si la ruta es el directorio o está adentro de él."""
    return ruta == directorio or ruta.startswith(directorio.rstrip(os.sep) + os.sep)

# Conexión a PostgreSQL
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

# Directorios a vigilar, separados por ":" (como el PATH de Linux)
RUTAS_MONITOREADAS = leer_rutas(os.getenv("RUTAS_MONITOREADAS") or "./directorio_prueba")

# Copia confiable de cada archivo de la baseline
DIRECTORIO_BOVEDA = ruta_absoluta(os.getenv("DIR_BOVEDA") or "./boveda")

# Evidencia de los archivos alterados
DIRECTORIO_CUARENTENA = ruta_absoluta(os.getenv("DIR_CUARENTENA") or "./cuarentena")

# Eventos que no se pudieron guardar en la BD (una línea JSON por evento)
ARCHIVO_PENDIENTES = os.path.join(ruta_absoluta(os.getenv("DIR_LOGS") or "./logs"), "eventos_pendientes.jsonl")

# Temporales de editores que no se vigilan ni entran en la baseline, separados por ","
PATRONES_IGNORADOS = leer_patrones(os.getenv("PATRONES_IGNORADOS") or "*.swp,*.swo,*.swx,*~,*.tmp")

# Quién decide la restauración:
#   automatica: el monitor restaura apenas detecta el cambio.
#   aprobacion: el monitor registra y guarda la evidencia, y la restauración la dispara
#               una persona con restaurar.py (o n8n, después de la aprobación).
MODOS_RESTAURACION = ("automatica", "aprobacion")
MODO_RESTAURACION = (os.getenv("MODO_RESTAURACION") or "automatica").strip().lower()

# Aviso push a n8n después de cada evento. Vacío = no se avisa (el monitor funciona igual).
N8N_WEBHOOK_URL = (os.getenv("N8N_WEBHOOK_URL") or "").strip()
N8N_WEBHOOK_SECRETO = os.getenv("N8N_WEBHOOK_SECRETO") or ""
