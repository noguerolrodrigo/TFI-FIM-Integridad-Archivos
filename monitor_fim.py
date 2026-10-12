import time
import hashlib
import psycopg2
import difflib
import os
import shutil  # NUEVO: Librería para mover archivos a cuarentena
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

# Carpeta que vamos a vigilar
PATH_TO_WATCH = "./directorio_prueba"

# Memoria RAM para comparar archivos (el Diff)
memoria_archivos = {}

def leer_archivo_texto(ruta):
    """Lee el contenido de un archivo."""
    try:
        with open(ruta, 'r', encoding='utf-8', errors='ignore') as f:
            return f.readlines()
    except Exception:
        return []

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
            h = get_sha256(ruta)
            
            lineas_nuevas = leer_archivo_texto(ruta)
            lineas_viejas = memoria_archivos.get(ruta, [])
            
            # Sacar el Diff exacto (la evidencia)
            texto_diff = ""
            if lineas_viejas:
                diff_gen = difflib.unified_diff(lineas_viejas, lineas_nuevas, fromfile='Antes', tofile='Ahora')
                texto_diff = ''.join(list(diff_gen))
            else:
                texto_diff = "Contenido modificado. (Sin registro previo en memoria)."
                
            memoria_archivos[ruta] = lineas_nuevas
            
            # Guardamos en BD si hubo cambios reales
            if texto_diff:
                log_to_db(nombre, ruta, h, 'MODIFICADO', texto_diff)
                print(f"[!] ALERTA: Archivo MODIFICADO -> {nombre}")
                print(f"Evidencia:\n{texto_diff}\n")

                # --- INICIO RESPUESTA AUTOMATIZADA ---
                print("[*] Iniciando protocolo de Respuesta Automatizada...")

                # 1. CUARENTENA: Movemos el archivo infectado a la carpeta segura
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                ruta_cuarentena = f"./cuarentena/{nombre}_infectado_{timestamp}.txt"
                
                try:
                    # Movemos el archivo modificado
                    shutil.move(ruta, ruta_cuarentena)
                    print(f"[+] AISLAMIENTO EXITOSO: Archivo movido a {ruta_cuarentena}")
                    
                    # 2. RESTAURACIÓN: Reescribimos el archivo original usando la memoria RAM
                    with open(ruta, 'w', encoding='utf-8') as f:
                        f.writelines(lineas_viejas)
                    print(f"[+] RESTAURACIÓN EXITOSA: El archivo original ha sido recuperado.")
                    
                    # Restauramos la memoria interna para que siga vigilando correctamente
                    memoria_archivos[ruta] = lineas_viejas
                    print("-" * 50)
                    
                except Exception as e:
                    print(f"[-] Error en la respuesta automatizada: {e}")
                # --- FIN RESPUESTA AUTOMATIZADA ---

if __name__ == "__main__":
    # Pre-cargar memoria con el estado inicial
    for root, dirs, files in os.walk(PATH_TO_WATCH):
        for file in files:
            ruta = os.path.join(root, file)
            memoria_archivos[ruta] = leer_archivo_texto(ruta)

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