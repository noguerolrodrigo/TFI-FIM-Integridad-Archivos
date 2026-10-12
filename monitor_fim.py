import time
import difflib
import os
import sys
import threading
import shutil  # NUEVO: Librería para mover archivos a cuarentena
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import bd
import boveda
import pendientes
from hashes import get_sha256

# Carpeta que vamos a vigilar
PATH_TO_WATCH = "./directorio_prueba"

# Carpeta donde se guarda la evidencia de los archivos alterados
DIRECTORIO_CUARENTENA = "./cuarentena"

# Resultados posibles de comparar un archivo con la baseline
SIN_CAMBIOS = "SIN_CAMBIOS"
MODIFICADO = "MODIFICADO"
FUERA_DE_BASELINE = "FUERA_DE_BASELINE"

# El escaneo inicial y los eventos de watchdog corren en hilos distintos:
# el candado hace que los archivos se procesen de a uno
candado = threading.Lock()

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

def rutas_de_la_baseline():
    """Devuelve las rutas de todos los archivos de la baseline vigente."""
    filas = bd.ejecutar("SELECT ruta_completa FROM baseline_vigente ORDER BY ruta_completa")
    return [fila[0] for fila in filas]

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

def leer_owner_y_permisos(ruta):
    """Devuelve (owner, permisos) del archivo, o ("N/A", "N/A") si no se puede leer."""
    try:
        stats = os.stat(ruta)
        return str(stats.st_uid), oct(stats.st_mode)[-3:]
    except Exception:
        return "N/A", "N/A"

def nueva_ruta_cuarentena(nombre):
    """Arma el nombre de la copia en cuarentena y crea la carpeta si hace falta."""
    os.makedirs(DIRECTORIO_CUARENTENA, exist_ok=True)
    # El nombre lleva microsegundos para que dos eventos seguidos no se pisen
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return os.path.join(DIRECTORIO_CUARENTENA, f"{timestamp}_{nombre}")

def log_to_db(nombre_archivo, ruta_completa, hash_sha256, evento, detalles_diff="",
              hash_anterior=None, ruta_cuarentena=None):
    """Guarda el evento y la evidencia en PostgreSQL. Si la BD falla, lo deja en el log local."""
    owner, permisos = leer_owner_y_permisos(ruta_completa)
    try:
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
        pendientes.guardar({
            "evento": evento, "nombre_archivo": nombre_archivo, "ruta_completa": ruta_completa,
            "hash_sha256": hash_sha256, "hash_anterior": hash_anterior, "detalles_diff": detalles_diff,
            "owner_archivo": owner, "permisos": permisos, "ruta_cuarentena": ruta_cuarentena,
            "motivo": str(e),
        })
        print(f"[*] Evento guardado en {pendientes.ARCHIVO_PENDIENTES}")

def guardar_sin_verificar(nombre, ruta, hash_actual, error):
    """Sin acceso a la baseline no se sabe si el cambio es legítimo: se guarda la evidencia y no se restaura."""
    respaldo = boveda.ruta_en_boveda(ruta)
    hash_boveda = get_sha256(respaldo)

    # Si el archivo es igual a su copia en la bóveda, lo más probable es que no haya cambiado
    if hash_actual == hash_boveda:
        return

    ruta_cuarentena = nueva_ruta_cuarentena(nombre)
    shutil.copy2(ruta, ruta_cuarentena)

    if hash_boveda is None:
        texto_diff = "Sin copia en la bóveda para comparar."
    else:
        texto_diff = calcular_diff(respaldo, ruta)

    owner, permisos = leer_owner_y_permisos(ruta)
    pendientes.guardar({
        "evento": "SIN_VERIFICAR", "nombre_archivo": nombre, "ruta_completa": ruta,
        "hash_sha256": hash_actual, "hash_boveda": hash_boveda, "detalles_diff": texto_diff,
        "owner_archivo": owner, "permisos": permisos, "ruta_cuarentena": ruta_cuarentena,
        "motivo": str(error),
    })
    print(f"[+] Evidencia copiada a {ruta_cuarentena} y evento guardado en {pendientes.ARCHIVO_PENDIENTES}")

def procesar(ruta):
    """Compara un archivo con la baseline y, si hubo un cambio, lo registra y responde.

    La llaman los eventos de watchdog y el escaneo inicial: el evento es solo el disparador.
    """
    with candado:
        nombre = os.path.basename(ruta)

        # Los temporales de la restauración son nuestros: no son un ataque
        if nombre.startswith(boveda.PREFIJO_TEMPORAL):
            return

        h = get_sha256(ruta)

        # El archivo ya no está (por ejemplo, lo acabamos de mover a cuarentena)
        if h is None:
            return

        # La verdad está en la baseline de la BD
        try:
            estado, hash_baseline = verificar(ruta, h)
        except Exception as e:
            print(f"[!] ALERTA: no se pudo consultar la baseline para verificar {nombre}: {e}")
            print("    Sin baseline no se restaura. Revisá que PostgreSQL esté levantado.")
            guardar_sin_verificar(nombre, ruta, h, e)
            return

        if estado == SIN_CAMBIOS:
            return

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

        ruta_cuarentena = nueva_ruta_cuarentena(nombre)

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

def escaneo_inicial():
    """Al arrancar, compara la baseline vigente contra el disco.

    Detecta lo que cambió mientras el monitor estaba apagado. Cada diferencia se trata
    igual que un evento en tiempo real.
    """
    try:
        rutas = set(rutas_de_la_baseline())
    except Exception as e:
        print(f"[!] No se pudo hacer el escaneo inicial (sin acceso a la baseline): {e}")
        return

    if not rutas:
        print("[!] No hay baseline: ejecutá generar_baseline.py antes de iniciar el monitor.")
        sys.exit(1)

    # Se suman los archivos que están en disco aunque no figuren en la baseline
    for root, dirs, files in os.walk(PATH_TO_WATCH):
        for file in files:
            rutas.add(os.path.join(root, file))

    print(f"[*] Escaneo inicial: verificando {len(rutas)} archivo(s) contra la baseline...")
    for ruta in sorted(rutas):
        procesar(ruta)
    print("[*] Escaneo inicial terminado.")

class FIMEventHandler(FileSystemEventHandler):
    """Manejador de los eventos de Watchdog"""

    def on_modified(self, event):
        if not event.is_directory:
            procesar(event.src_path)

if __name__ == "__main__":
    print(f"[*] Iniciando Motor FIM en tiempo real sobre: {PATH_TO_WATCH}")
    event_handler = FIMEventHandler()
    observer = Observer()
    observer.schedule(event_handler, PATH_TO_WATCH, recursive=True)

    # Primero se empieza a escuchar y después se escanea: así no queda ninguna ventana sin cubrir
    observer.start()
    try:
        escaneo_inicial()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Motor FIM detenido.")
    finally:
        observer.stop()
        observer.join()
        bd.cerrar()
