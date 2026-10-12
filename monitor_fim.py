import time
import hashlib
import psycopg2
import difflib
import os
import shutil  # NUEVO: Librería para mover archivos a cuarentena
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv
import boveda

# Cargar variables de entorno
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

# Carpeta que vamos a vigilar
PATH_TO_WATCH = "./directorio_prueba"

# Carpeta donde se guarda la evidencia de los archivos alterados
DIRECTORIO_CUARENTENA = "./cuarentena"

def leer_archivo_texto(ruta):
    """Lee las líneas de un archivo de texto. Devuelve None si es binario o no se puede leer."""
    try:
        with open(ruta, 'rb') as f:
            contenido = f.read()
        if b'\x00' in contenido:
            return None
        return contenido.decode('utf-8').splitlines(keepends=True)
    except Exception:
        return None

def calcular_diff(ruta_antes, ruta_ahora):
    """Compara la copia de la bóveda con el archivo actual y devuelve la evidencia."""
    lineas_viejas = leer_archivo_texto(ruta_antes)
    lineas_nuevas = leer_archivo_texto(ruta_ahora)
    if lineas_viejas is None or lineas_nuevas is None:
        return "Archivo binario: no se genera diff de texto. La evidencia es el cambio de hash."
    diff_gen = difflib.unified_diff(lineas_viejas, lineas_nuevas, fromfile='Antes', tofile='Ahora')
    return ''.join(list(diff_gen))

def get_sha256(filepath):
    """Calcula el hash SHA-256."""
    try:
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception:
        return None

def log_to_db(nombre_archivo, ruta_completa, hash_sha256, evento, detalles_diff=""):
    """Guarda el evento y la evidencia en PostgreSQL."""
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS)
        cursor = conn.cursor()
        
        # Obtenemos owner y permisos
        try:
            stats = os.stat(ruta_completa)
            permisos = oct(stats.st_mode)[-3:]
            owner = str(stats.st_uid)
        except:
            permisos, owner = "N/A", "N/A"

        query = """
            INSERT INTO registros_archivos 
            (nombre_archivo, ruta_completa, hash_sha256, evento, detalles_diff, owner_archivo, permisos) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (nombre_archivo, ruta_completa, hash_sha256, evento, detalles_diff, owner, permisos))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error en BD: {e}")

class FIMEventHandler(FileSystemEventHandler):
    """Manejador de los eventos de Watchdog"""
    
    def on_modified(self, event):
        if not event.is_directory:
            ruta = event.src_path
            nombre = ruta.split('/')[-1]

            # Los temporales de la restauración son nuestros: no son un ataque
            if nombre.startswith(boveda.PREFIJO_TEMPORAL):
                return

            h = get_sha256(ruta)

            # El archivo ya no está (por ejemplo, lo acabamos de mover a cuarentena)
            if h is None:
                return

            respaldo = boveda.ruta_en_boveda(ruta)
            hay_respaldo = boveda.tiene_respaldo(ruta)

            # Hubo un cambio real solo si el contenido ya no coincide con el de la bóveda
            hubo_cambio = not hay_respaldo or h != get_sha256(respaldo)

            # Guardamos en BD si hubo cambios reales
            if hubo_cambio:
                # Sacar el Diff exacto (la evidencia)
                if hay_respaldo:
                    texto_diff = calcular_diff(respaldo, ruta)
                else:
                    texto_diff = "Archivo sin respaldo en la bóveda (no está en la baseline)."

                log_to_db(nombre, ruta, h, 'MODIFICADO', texto_diff)
                print(f"[!] ALERTA: Archivo MODIFICADO -> {nombre}")
                print(f"Evidencia:\n{texto_diff}\n")

                # --- INICIO RESPUESTA AUTOMATIZADA ---
                print("[*] Iniciando protocolo de Respuesta Automatizada...")

                # El nombre lleva microsegundos para que dos eventos seguidos no se pisen
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                ruta_cuarentena = os.path.join(DIRECTORIO_CUARENTENA, f"{timestamp}_{nombre}")

                try:
                    if hay_respaldo:
                        # 1. CUARENTENA: Copiamos el archivo alterado tal cual (evidencia)
                        shutil.copy2(ruta, ruta_cuarentena)
                        print(f"[+] AISLAMIENTO EXITOSO: Evidencia copiada a {ruta_cuarentena}")

                        # 2. RESTAURACIÓN: Reponemos el original desde la bóveda en disco
                        boveda.restaurar(ruta)
                        print(f"[+] RESTAURACIÓN EXITOSA: El archivo original ha sido recuperado.")
                    else:
                        # Archivo que no está en la baseline: se aísla y no hay nada que restaurar
                        shutil.move(ruta, ruta_cuarentena)
                        print(f"[+] AISLAMIENTO EXITOSO: Archivo sin respaldo movido a {ruta_cuarentena}")
                    print("-" * 50)

                except Exception as e:
                    print(f"[-] Error en la respuesta automatizada: {e}")
                # --- FIN RESPUESTA AUTOMATIZADA ---

if __name__ == "__main__":
    os.makedirs(DIRECTORIO_CUARENTENA, exist_ok=True)

    # Avisar si hay archivos vigilados que no pasaron por la baseline
    sin_respaldo = 0
    for root, dirs, files in os.walk(PATH_TO_WATCH):
        for file in files:
            if not boveda.tiene_respaldo(os.path.join(root, file)):
                sin_respaldo += 1

    if sin_respaldo:
        print(f"[!] {sin_respaldo} archivo(s) sin respaldo en la bóveda: si se modifican van a cuarentena")
        print("    y no se restauran. Ejecutá generar_baseline.py para respaldarlos.")

    print(f"[*] Iniciando Motor FIM en tiempo real sobre: {PATH_TO_WATCH}")
    event_handler = FIMEventHandler()
    observer = Observer()
    observer.schedule(event_handler, PATH_TO_WATCH, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n[*] Motor FIM detenido.")
    observer.join()