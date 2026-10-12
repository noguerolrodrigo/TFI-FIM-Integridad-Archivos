import time
import difflib
import os
import shutil  # NUEVO: Librería para mover archivos a cuarentena
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import bd
import boveda
from hashes import get_sha256

# Carpeta que vamos a vigilar
PATH_TO_WATCH = "./directorio_prueba"

# Carpeta donde se guarda la evidencia de los archivos alterados
DIRECTORIO_CUARENTENA = "./cuarentena"

# Resultados posibles de comparar un archivo con la baseline
SIN_CAMBIOS = "SIN_CAMBIOS"
MODIFICADO = "MODIFICADO"
FUERA_DE_BASELINE = "FUERA_DE_BASELINE"

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

def obtener_baseline(ruta):
    """Devuelve el hash del archivo en la baseline vigente de la BD, o None si no figura."""
    filas = bd.ejecutar("SELECT hash_sha256 FROM baseline_vigente WHERE ruta_completa = %s", (ruta,))
    return filas[0][0] if filas else None

def verificar(ruta, hash_actual):
    """Compara el hash actual del archivo con la baseline vigente.

    Devuelve (estado, hash_baseline). El estado es SIN_CAMBIOS, MODIFICADO o FUERA_DE_BASELINE.
    """
    hash_baseline = obtener_baseline(ruta)
    if hash_baseline is None:
        return FUERA_DE_BASELINE, None
    if hash_actual == hash_baseline:
        return SIN_CAMBIOS, hash_baseline
    return MODIFICADO, hash_baseline

def respaldo_confiable(ruta, hash_baseline):
    """Indica si la copia de la bóveda existe y tiene el mismo hash que la baseline."""
    return get_sha256(boveda.ruta_en_boveda(ruta)) == hash_baseline

def log_to_db(nombre_archivo, ruta_completa, hash_sha256, evento, detalles_diff="",
              hash_anterior=None, ruta_cuarentena=None):
    """Guarda el evento y la evidencia en PostgreSQL."""
    try:
        # Obtenemos owner y permisos
        try:
            stats = os.stat(ruta_completa)
            permisos = oct(stats.st_mode)[-3:]
            owner = str(stats.st_uid)
        except:
            permisos, owner = "N/A", "N/A"

        query = """
            INSERT INTO registros_archivos 
            (nombre_archivo, ruta_completa, hash_sha256, evento, detalles_diff, owner_archivo, permisos,
             hash_anterior, ruta_cuarentena) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        # Se reutiliza la conexión del proceso en vez de abrir una por evento
        bd.ejecutar(query, (nombre_archivo, ruta_completa, hash_sha256, evento, detalles_diff, owner, permisos,
                            hash_anterior, ruta_cuarentena))
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

            # La verdad está en la baseline de la BD: el evento es solo el disparador
            try:
                estado, hash_baseline = verificar(ruta, h)
            except Exception as e:
                print(f"[!] ALERTA: no se pudo consultar la baseline para verificar {nombre}: {e}")
                print("    Sin baseline no se registra ni se restaura. Revisá que PostgreSQL esté levantado.")
                return

            # Guardamos en BD si hubo cambios reales
            if estado != SIN_CAMBIOS:
                respaldo = boveda.ruta_en_boveda(ruta)

                # Solo se restaura si la copia de la bóveda sigue siendo la de la baseline
                restaurable = estado == MODIFICADO and respaldo_confiable(ruta, hash_baseline)

                # Sacar el Diff exacto (la evidencia)
                if estado == FUERA_DE_BASELINE:
                    texto_diff = "Archivo que no está en la baseline vigente."
                elif restaurable:
                    texto_diff = calcular_diff(respaldo, ruta)
                else:
                    texto_diff = ("BÓVEDA NO CONFIABLE: la copia de respaldo falta o no coincide con la baseline. "
                                  "No se genera diff ni se restaura.")

                # El nombre lleva microsegundos para que dos eventos seguidos no se pisen
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                ruta_cuarentena = os.path.join(DIRECTORIO_CUARENTENA, f"{timestamp}_{nombre}")

                log_to_db(nombre, ruta, h, 'MODIFICADO', texto_diff,
                          hash_anterior=hash_baseline, ruta_cuarentena=ruta_cuarentena)
                print(f"[!] ALERTA: Archivo MODIFICADO -> {nombre}")
                print(f"Evidencia:\n{texto_diff}\n")

                # --- INICIO RESPUESTA AUTOMATIZADA ---
                print("[*] Iniciando protocolo de Respuesta Automatizada...")

                try:
                    if estado == FUERA_DE_BASELINE:
                        # Archivo que no está en la baseline: se aísla y no hay nada que restaurar
                        shutil.move(ruta, ruta_cuarentena)
                        print(f"[+] AISLAMIENTO EXITOSO: Archivo fuera de la baseline movido a {ruta_cuarentena}")
                    else:
                        # 1. CUARENTENA: Copiamos el archivo alterado tal cual (evidencia)
                        shutil.copy2(ruta, ruta_cuarentena)
                        print(f"[+] AISLAMIENTO EXITOSO: Evidencia copiada a {ruta_cuarentena}")

                        if restaurable:
                            # 2. RESTAURACIÓN: Reponemos el original desde la bóveda en disco
                            boveda.restaurar(ruta)
                            print(f"[+] RESTAURACIÓN EXITOSA: El archivo original ha sido recuperado.")
                        else:
                            print("[-] NO SE RESTAURA: la bóveda no coincide con la baseline. Requiere revisión manual.")
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
    bd.cerrar()