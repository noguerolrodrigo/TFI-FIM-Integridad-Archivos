"""Mide MTTD, MTTR y las latencias de alerta y de ejecución del FIM, con repeticiones.

Uso:
    python scripts/medir_metricas.py --repeticiones 50
    python scripts/medir_metricas.py --telegram-real --repeticiones 10

Modo normal (simulado): todo corre contra la base fim_pruebas, en carpetas de /tmp, con el monitor
real (monitor_fim.py) como proceso aparte y el n8n de pruebas con Telegram simulado
(scripts/n8n_de_pruebas.sh). No escribe nada en fim_db: lo verifica al empezar y al terminar.

Modo --telegram-real: usa la instalación de verdad (tu monitor, n8n y bot) sobre
directorio_prueba/config_test.txt. Solo lee fim_db; las filas las registra tu monitor.

Definiciones (t0 = instante en que el script terminó la escritura, después de close):
    mttd_ms            t0 -> fila de detección en registros_archivos
    mttr_bd_ms         t0 -> fila RESTAURADO
    mttr_disco_ms      t0 -> el script ve el archivo otra vez como en la baseline
    contencion_ms      t0 -> el archivo nuevo ya no está en el directorio (archivo nuevo)
    alerta_ms          fila de detección -> fila en notificaciones (n8n ya mandó el mensaje)
    ejecucion_ms       fila en decisiones -> fila en ejecuciones (sin tiempo humano)
Los tiempos de la BD y los del script salen del mismo reloj: todo corre en la misma máquina.
"""
import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime

import psycopg2

PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROYECTO)
import config  # noqa: E402  (credenciales de la BD desde el .env)

PYTHON = os.path.join(PROYECTO, "venv", "bin", "python")
BASE_PRUEBAS = "fim_pruebas"
CARPETA = "/tmp/fim_medicion"
RESULTADOS = os.path.join(PROYECTO, "resultados")
N8N_PRUEBAS = os.path.join(PROYECTO, "scripts", "n8n_de_pruebas.sh")

ESPERA_MAXIMA = 15      # segundos que se espera cada cosa antes de anotarla como faltante
SONDEO = 0.001          # cada cuánto se mira el disco (1 ms)
PAUSA_ENTRE = 0.5       # pausa entre repeticiones, para que no se pisen


def conectar(base):
    conexion = psycopg2.connect(host=config.DB_HOST, database=base, user=config.DB_USER,
                                password=config.DB_PASS)
    conexion.autocommit = True
    return conexion


def consultar(conexion, query, parametros=()):
    with conexion.cursor() as cursor:
        cursor.execute(query, parametros)
        return cursor.fetchall() if cursor.description else None


def esperar(condicion, maximo=ESPERA_MAXIMA, pausa=SONDEO):
    """Repite condicion() hasta que devuelva algo verdadero. Devuelve (valor, instante) o (None, None)."""
    limite = time.time() + maximo
    while time.time() < limite:
        valor = condicion()
        if valor:
            return valor, time.time()
        time.sleep(pausa)
    return None, None


def sha256_bytes(contenido):
    return hashlib.sha256(contenido).hexdigest()


def ms(desde, hasta):
    return round((hasta - desde) * 1000, 3)


class Medicion:
    """Una corrida: guarda cada valor medido como una fila (caso, repetición, métrica, valor)."""

    def __init__(self, conexion):
        self.conexion = conexion
        self.filas = []

    def anotar(self, caso, repeticion, metrica, valor_ms, evento_id=None, observacion=""):
        self.filas.append({"caso": caso, "repeticion": repeticion, "metrica": metrica,
                           "valor_ms": "" if valor_ms is None else valor_ms,
                           "evento_id": "" if evento_id is None else evento_id,
                           "observacion": observacion})
        texto = "FALTA" if valor_ms is None else f"{valor_ms:9.1f} ms"
        print(f"    {caso:<13} #{repeticion:<3} {metrica:<14} {texto} {observacion}")

    # --- Búsquedas en la BD ----------------------------------------------------------------

    def deteccion(self, evento, ruta, t0, hash_esperado=None):
        """Primera fila de ese evento para esa ruta registrada después de t0 (y con ese hash, si se da)."""
        def buscar():
            filas = consultar(self.conexion, """
                SELECT id, extract(epoch FROM fecha_registro) FROM registros_archivos
                WHERE evento = %s AND ruta_completa = %s AND fecha_registro >= to_timestamp(%s)
                  AND (%s IS NULL OR hash_sha256 = %s)
                ORDER BY id LIMIT 1""", (evento, ruta, t0 - 0.05, hash_esperado, hash_esperado))
            return filas[0] if filas else None
        fila, _ = esperar(buscar, pausa=0.005)
        return fila

    def restaurado(self, ruta, despues_de_id):
        def buscar():
            filas = consultar(self.conexion, """
                SELECT id, extract(epoch FROM fecha_registro) FROM registros_archivos
                WHERE evento = 'RESTAURADO' AND ruta_completa = %s AND id > %s ORDER BY id LIMIT 1""",
                (ruta, despues_de_id))
            return filas[0] if filas else None
        fila, _ = esperar(buscar, pausa=0.005)
        return fila

    def notificacion(self, evento_id, maximo=ESPERA_MAXIMA):
        def buscar():
            filas = consultar(self.conexion, "SELECT extract(epoch FROM fecha) FROM notificaciones "
                                             "WHERE evento_id = %s ORDER BY id LIMIT 1", (evento_id,))
            return filas[0][0] if filas else None
        fecha, _ = esperar(buscar, maximo=maximo, pausa=0.01)
        return fecha

    # --- Un caso completo -----------------------------------------------------------------

    def registrar_caso(self, caso, k, evento, ruta, t0, hash_esperado, restaurado_en_disco,
                       espera_restauracion=True, con_alerta=True):
        """Busca las filas de un cambio ya hecho y anota sus latencias."""
        if restaurado_en_disco is not None:
            metrica = "contencion_ms" if caso == "archivo_nuevo" else "mttr_disco_ms"
            self.anotar(caso, k, metrica, ms(t0, restaurado_en_disco))
        else:
            self.anotar(caso, k, "mttr_disco_ms", None, observacion="el disco no volvió a la baseline")

        fila = self.deteccion(evento, ruta, t0, hash_esperado)
        if not fila:
            self.anotar(caso, k, "mttd_ms", None, observacion=f"sin fila {evento}")
            return None
        evento_id, fecha_deteccion = fila[0], float(fila[1])
        self.anotar(caso, k, "mttd_ms", ms(t0, fecha_deteccion), evento_id)

        if espera_restauracion:
            restauracion = self.restaurado(ruta, evento_id)
            self.anotar(caso, k, "mttr_bd_ms", ms(t0, float(restauracion[1])) if restauracion else None,
                        evento_id, "" if restauracion else "sin fila RESTAURADO")
        if con_alerta:
            fecha = self.notificacion(evento_id)
            self.anotar(caso, k, "alerta_ms", ms(fecha_deteccion, float(fecha)) if fecha else None,
                        evento_id, "" if fecha else "sin fila en notificaciones")
        return evento_id


# --- Modo simulado ------------------------------------------------------------------------

def entorno_simulado():
    entorno = dict(os.environ)
    entorno.update({
        "DB_NAME": BASE_PRUEBAS,
        "RUTAS_MONITOREADAS": f"{CARPETA}/vigilado",
        "DIR_BOVEDA": f"{CARPETA}/boveda",
        "DIR_CUARENTENA": f"{CARPETA}/cuarentena",
        "DIR_LOGS": f"{CARPETA}/logs",
        "MODO_RESTAURACION": "automatica",
        "N8N_WEBHOOK_URL": "http://localhost:5690/webhook/fim-evento",
        "N8N_WEBHOOK_SECRETO": "secreto-de-pruebas",
        "PYTHONUNBUFFERED": "1",
    })
    return entorno


def preparar_archivos():
    """Crea el directorio vigilado con un archivo por caso."""
    shutil.rmtree(CARPETA, ignore_errors=True)
    vigilado = f"{CARPETA}/vigilado"
    os.makedirs(vigilado)
    lineas = [f"opcion_{i} = valor_{i}  # configuración de ejemplo\n" for i in range(50)]
    texto = "".join(lineas).encode("utf-8")                  # ~2 KB
    archivos = {
        "texto": ("texto.conf", texto),
        "binario": ("binario.bin", os.urandom(1024 * 1024)),  # 1 MB
        "permisos": ("permisos.conf", texto),
        "borrado": ("borrado.conf", texto),
        "decision": ("decision.conf", texto),
    }
    rutas = {}
    for caso, (nombre, contenido) in archivos.items():
        ruta = os.path.join(vigilado, nombre)
        with open(ruta, "wb") as f:
            f.write(contenido)
        os.chmod(ruta, 0o644)
        rutas[caso] = ruta
    return rutas


def max_id_fim_db():
    conexion = conectar(config.DB_NAME)
    try:
        return consultar(conexion, "SELECT COALESCE(max(id), 0) FROM registros_archivos")[0][0]
    finally:
        conexion.close()


def arrancar_monitor(entorno):
    log = open(f"{CARPETA}/monitor.log", "w")
    proceso = subprocess.Popen([PYTHON, os.path.join(PROYECTO, "monitor_fim.py")], cwd=PROYECTO,
                               env=entorno, stdout=log, stderr=subprocess.STDOUT)
    listo, _ = esperar(lambda: "Esperando decisiones" in open(f"{CARPETA}/monitor.log").read(),
                       maximo=30, pausa=0.2)
    if not listo:
        proceso.terminate()
        sys.exit("[!] El monitor no arrancó; ver /tmp/fim_medicion/monitor.log")
    return proceso


def medir_simulado(repeticiones, salida):
    if config.DB_NAME == BASE_PRUEBAS:
        sys.exit("[!] El .env apunta a fim_pruebas: no se puede verificar que fim_db quede intacta.")
    id_fim_db_antes = max_id_fim_db()

    print("[*] Preparando fim_pruebas, n8n de pruebas y archivos...")
    subprocess.run([os.path.join(PROYECTO, "scripts", "preparar_bd_pruebas.sh")], check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run([N8N_PRUEBAS, "iniciar"], check=True)
    rutas = preparar_archivos()
    entorno = entorno_simulado()
    subprocess.run([PYTHON, os.path.join(PROYECTO, "generar_baseline.py")], cwd=PROYECTO, env=entorno,
                   check=True, stdout=subprocess.DEVNULL)
    monitor = arrancar_monitor(entorno)
    conexion = conectar(BASE_PRUEBAS)
    medicion = Medicion(conexion)
    inicio = datetime.now().astimezone()

    try:
        for k in range(1, repeticiones + 1):
            print(f"[*] Repetición {k}/{repeticiones}")
            medir_texto(medicion, k, rutas["texto"])
            medir_binario(medicion, k, rutas["binario"])
            medir_permisos(medicion, k, rutas["permisos"])
            medir_borrado(medicion, k, rutas["borrado"])
            medir_archivo_nuevo(medicion, k, os.path.dirname(rutas["texto"]))
        print("[*] Latencia de ejecución de decisiones")
        for k in range(1, repeticiones + 1):
            medir_ejecucion(medicion, k, rutas["decision"])
    finally:
        monitor.terminate()
        monitor.wait(10)
        conexion.close()
        subprocess.run([N8N_PRUEBAS, "detener"], check=False)

    id_fim_db_despues = max_id_fim_db()
    guardar(medicion.filas, salida, "metricas", inicio, {
        "modo": "simulado (fim_pruebas, n8n de pruebas, Telegram simulado)",
        "repeticiones": repeticiones,
        "tamanos": {"texto": "2 KB aprox.", "binario": "1 MB"},
        "fim_db_max_id_antes": id_fim_db_antes,
        "fim_db_max_id_despues": id_fim_db_despues,
        "fim_db_intacta": id_fim_db_antes == id_fim_db_despues,
    })
    if id_fim_db_antes != id_fim_db_despues:
        print("[!] ATENCIÓN: fim_db cambió durante la medición (ver el .json de entorno).")


def contenido_actual(ruta):
    with open(ruta, "rb") as f:
        return f.read()


def medir_texto(medicion, k, ruta):
    original = contenido_actual(ruta)
    inodo = os.stat(ruta).st_ino
    agregado = f"intruso = medicion texto {k} {uuid.uuid4().hex}\n".encode("utf-8")
    with open(ruta, "ab") as f:
        f.write(agregado)
    t0 = time.time()
    # La restauración reemplaza el archivo por otro (os.replace): cambia el inodo
    _, en_disco = esperar(lambda: os.path.exists(ruta) and os.stat(ruta).st_ino != inodo)
    medicion.registrar_caso("texto", k, "MODIFICADO", ruta, t0, sha256_bytes(original + agregado), en_disco)
    verificar_baseline(ruta, original)


def medir_binario(medicion, k, ruta):
    original = contenido_actual(ruta)
    inodo = os.stat(ruta).st_ino
    nuevo = os.urandom(len(original))
    with open(ruta, "r+b") as f:
        f.write(nuevo)
    t0 = time.time()
    _, en_disco = esperar(lambda: os.path.exists(ruta) and os.stat(ruta).st_ino != inodo)
    medicion.registrar_caso("binario", k, "MODIFICADO", ruta, t0, sha256_bytes(nuevo), en_disco)
    verificar_baseline(ruta, original)


def medir_permisos(medicion, k, ruta):
    os.chmod(ruta, 0o777)
    t0 = time.time()
    _, en_disco = esperar(lambda: (os.stat(ruta).st_mode & 0o7777) == 0o644)
    medicion.registrar_caso("permisos", k, "PERMISOS", ruta, t0, None, en_disco)
    time.sleep(PAUSA_ENTRE)


def medir_borrado(medicion, k, ruta):
    original = contenido_actual(ruta)
    os.remove(ruta)
    t0 = time.time()
    _, en_disco = esperar(lambda: os.path.exists(ruta))
    medicion.registrar_caso("borrado", k, "ELIMINADO", ruta, t0, None, en_disco)
    verificar_baseline(ruta, original)


def medir_archivo_nuevo(medicion, k, carpeta):
    ruta = os.path.join(carpeta, f"nuevo_{k}_{uuid.uuid4().hex[:8]}.sh")
    contenido = f"#!/bin/sh\necho medicion {k} {uuid.uuid4().hex}\n".encode("utf-8")
    with open(ruta, "wb") as f:
        f.write(contenido)
    t0 = time.time()
    _, en_disco = esperar(lambda: not os.path.exists(ruta))
    medicion.registrar_caso("archivo_nuevo", k, "CREADO", ruta, t0, sha256_bytes(contenido), en_disco,
                            espera_restauracion=False)
    time.sleep(PAUSA_ENTRE)


def verificar_baseline(ruta, original):
    """Espera a que el archivo vuelva a tener el contenido original antes de la siguiente repetición."""
    esperar(lambda: os.path.exists(ruta) and contenido_actual(ruta) == original, pausa=0.01)
    time.sleep(PAUSA_ENTRE)


def medir_ejecucion(medicion, k, ruta):
    """Genera un evento, inserta la decisión como lo haría n8n y mide hasta que el monitor la ejecuta."""
    original = contenido_actual(ruta)
    inodo = os.stat(ruta).st_ino
    agregado = f"cambio para decidir {k} {uuid.uuid4().hex}\n".encode("utf-8")
    with open(ruta, "ab") as f:
        f.write(agregado)
    t0 = time.time()
    esperar(lambda: os.path.exists(ruta) and os.stat(ruta).st_ino != inodo)
    fila = medicion.deteccion("MODIFICADO", ruta, t0, sha256_bytes(original + agregado))
    if not fila:
        medicion.anotar("decision", k, "ejecucion_ms", None, observacion="no se detectó el cambio")
        return
    # Se espera la alerta para que la decisión no compita con el workflow de n8n
    medicion.notificacion(fila[0])
    decision = "INCIDENTE" if k % 2 else "AUTORIZADO"
    (decision_id, fecha_decision), = consultar(medicion.conexion, """
        INSERT INTO decisiones (evento_id, decision, decidido_por, canal)
        VALUES (%s, %s, 'medicion', 'script') RETURNING id, extract(epoch FROM fecha)""", (fila[0], decision))

    def ejecutada():
        filas = consultar(medicion.conexion, "SELECT extract(epoch FROM fecha), resultado FROM ejecuciones "
                                             "WHERE decision_id = %s", (decision_id,))
        return filas[0] if filas else None
    ejecucion, _ = esperar(ejecutada, pausa=0.01)
    if ejecucion:
        medicion.anotar("decision", k, "ejecucion_ms", ms(float(fecha_decision), float(ejecucion[0])),
                        fila[0], f"{decision} {ejecucion[1]}")
    else:
        medicion.anotar("decision", k, "ejecucion_ms", None, fila[0], f"{decision} sin ejecución")
    # Si fue AUTORIZADO, el cambio pasó a la baseline: se espera a que el disco quede estable
    time.sleep(PAUSA_ENTRE)


# --- Modo Telegram real -------------------------------------------------------------------

def medir_telegram_real(repeticiones, salida, intervalo=15):
    ruta = os.path.join(config.RUTAS_MONITOREADAS[0], "config_test.txt")
    conexion = conectar(config.DB_NAME)
    medicion = Medicion(conexion)
    inicio = datetime.now().astimezone()
    print(f"[*] Muestra con Telegram real sobre {ruta} ({repeticiones} alertas, cada {intervalo} s)")
    try:
        for k in range(1, repeticiones + 1):
            original = contenido_actual(ruta)
            inodo = os.stat(ruta).st_ino
            agregado = f"medición alerta real #{k} ({inicio:%d/%m/%Y %H:%M})\n".encode("utf-8")
            with open(ruta, "ab") as f:
                f.write(agregado)
            t0 = time.time()
            _, en_disco = esperar(lambda: os.path.exists(ruta) and os.stat(ruta).st_ino != inodo)
            fila = medicion.deteccion("MODIFICADO", ruta, t0, sha256_bytes(original + agregado))
            if not fila:
                sys.exit("[!] No apareció la detección en fim_db. ¿Está corriendo el monitor?")
            evento_id, fecha_deteccion = fila[0], float(fila[1])
            medicion.anotar("telegram_real", k, "mttd_ms", ms(t0, fecha_deteccion), evento_id)
            if en_disco:
                medicion.anotar("telegram_real", k, "mttr_disco_ms", ms(t0, en_disco), evento_id)
            fecha = medicion.notificacion(evento_id, maximo=60)
            medicion.anotar("telegram_real", k, "alerta_ms", ms(fecha_deteccion, float(fecha)) if fecha else None,
                            evento_id, "" if fecha else "sin fila en notificaciones")
            if k < repeticiones:
                time.sleep(intervalo)
    finally:
        conexion.close()
    guardar(medicion.filas, salida, "alerta_telegram_real", inicio, {
        "modo": "Telegram real (instalación de fim_db, monitor y n8n reales)",
        "repeticiones": repeticiones, "archivo": ruta, "intervalo_s": intervalo,
        "eventos": sorted({f["evento_id"] for f in medicion.filas if f["evento_id"] != ""}),
    })


# --- Salida -------------------------------------------------------------------------------

def version(comando):
    try:
        return subprocess.run(comando, capture_output=True, text=True, timeout=30).stdout.strip().splitlines()[0]
    except Exception:
        return "desconocida"


def guardar(filas, salida, prefijo, inicio, datos):
    os.makedirs(salida, exist_ok=True)
    sello = inicio.strftime("%Y%m%d_%H%M%S")
    archivo_csv = os.path.join(salida, f"{prefijo}_{sello}.csv")
    with open(archivo_csv, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=["caso", "repeticion", "metrica", "valor_ms", "evento_id",
                                                 "observacion"])
        escritor.writeheader()
        escritor.writerows(filas)

    conexion = conectar(BASE_PRUEBAS if prefijo == "metricas" else config.DB_NAME)
    version_pg = consultar(conexion, "SHOW server_version")[0][0]
    conexion.close()
    datos.update({
        "inicio": inicio.isoformat(), "fin": datetime.now().astimezone().isoformat(),
        "python": platform.python_version(), "postgresql": version_pg,
        "n8n": version(["bash", "-c", '. "$HOME/.nvm/nvm.sh" >/dev/null && nvm use 24 >/dev/null && n8n --version']),
        "kernel": platform.release(), "procesadores": os.cpu_count(),
        "cpu": version(["bash", "-c", "grep -m1 'model name' /proc/cpuinfo | cut -d: -f2"]),
        "watchdog": version([PYTHON, "-c", "import watchdog.version as v; print(v.VERSION_STRING)"]),
    })
    archivo_json = os.path.join(salida, f"entorno_{prefijo}_{sello}.json")
    with open(archivo_json, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    faltantes = sum(1 for fila in filas if fila["valor_ms"] == "")
    print(f"[*] {len(filas)} valores en {archivo_csv} ({faltantes} faltantes). Entorno en {archivo_json}")


def main():
    # Que los mensajes salgan en orden aunque se mezclen con los de los subprocesos
    sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repeticiones", type=int, default=50)
    parser.add_argument("--telegram-real", action="store_true",
                        help="muestra con la instalación real y el bot de verdad (lee fim_db)")
    parser.add_argument("--salida", default=RESULTADOS, help="carpeta para el CSV (por defecto resultados/)")
    argumentos = parser.parse_args()
    if argumentos.telegram_real:
        medir_telegram_real(argumentos.repeticiones, argumentos.salida)
    else:
        medir_simulado(argumentos.repeticiones, argumentos.salida)


if __name__ == "__main__":
    main()
