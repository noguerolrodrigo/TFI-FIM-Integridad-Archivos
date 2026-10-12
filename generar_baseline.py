import os
import hashlib
import psycopg2
from dotenv import load_dotenv
import boveda

# Cargar variables de entorno del archivo .env
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

# Directorio de prueba
DIRECTORIO_A_MONITOREAR = "./directorio_prueba"

def get_sha256(filepath):
    """Calcula el hash SHA-256 de un archivo."""
    try:
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception:
        return None

def generar_baseline():
    print(f"[*] Iniciando escaneo de baseline en: {DIRECTORIO_A_MONITOREAR}")
    
    # Si la carpeta no existe, la creamos y le metemos un archivo
    if not os.path.exists(DIRECTORIO_A_MONITOREAR):
        os.makedirs(DIRECTORIO_A_MONITOREAR)
        with open(os.path.join(DIRECTORIO_A_MONITOREAR, "config_test.txt"), "w") as f:
            f.write("Archivo de configuración inicial. Estado cero.")

    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS)
        cursor = conn.cursor()
        archivos_procesados = 0
        rutas_vigentes = []

        # Cada corrida es una versión nueva: la vigente es siempre la más alta
        cursor.execute("SELECT COALESCE(MAX(version_baseline), 0) + 1 FROM registros_archivos WHERE evento = 'BASELINE'")
        version = cursor.fetchone()[0]
        print(f"[*] Versión de baseline: {version}")

        for root, dirs, files in os.walk(DIRECTORIO_A_MONITOREAR):
            for file in files:
                ruta_completa = os.path.join(root, file)
                hash_archivo = get_sha256(ruta_completa)
                
                if hash_archivo:
                    stats = os.stat(ruta_completa)
                    permisos = oct(stats.st_mode)[-3:]
                    owner = str(stats.st_uid)

                    query = """
                        INSERT INTO registros_archivos 
                        (nombre_archivo, ruta_completa, hash_sha256, evento, owner_archivo, permisos, version_baseline) 
                        VALUES (%s, %s, %s, 'BASELINE', %s, %s, %s)
                    """
                    cursor.execute(query, (file, ruta_completa, hash_archivo, owner, permisos, version))

                    # Copia confiable en disco: de acá restaura el monitor
                    boveda.respaldar(ruta_completa)
                    rutas_vigentes.append(ruta_completa)
                    archivos_procesados += 1
                    print(f"[+] Registrado: {file} -> Hash: {hash_archivo[:15]}...")

        conn.commit()
        cursor.close()
        conn.close()

        # La bóveda tiene que reflejar solo la baseline vigente
        borrados = boveda.limpiar_huerfanos(DIRECTORIO_A_MONITOREAR, rutas_vigentes)
        if borrados:
            print(f"[*] Bóveda: {borrados} respaldo(s) de archivos que ya no existen eliminado(s).")

        print(f"\n[*] Baseline versión {version} completada. {archivos_procesados} archivo(s) guardado(s).")

    except Exception as e:
        print(f"[!] Error: {e}")

if __name__ == "__main__":
    generar_baseline()