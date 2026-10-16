"""Mide los falsos positivos que generan editores reales al guardar un archivo vigilado.

Uso: python scripts/medir_falsos_positivos.py --ediciones 20

Abre vim y nano en una pseudo-terminal y les tipea teclas de verdad (agregar una línea al final,
guardar y salir), con su configuración por defecto. Cuenta las alertas que registra el monitor real
en fim_pruebas por cada edición:
    esperada   la primera detección MODIFICADO del archivo editado (el cambio real)
    espurias   todo lo demás: archivos temporales del editor (.swp, ~, 4913), MOVIDO o ELIMINADO
               intermedios del guardado y detecciones repetidas del mismo archivo
Se hacen dos corridas: A con el filtro de temporales (PATRONES_IGNORADOS por defecto) y B sin
filtro (los temporales de la propia restauración se ignoran siempre). El monitor corre en modo
aprobación, para no restaurar en medio del guardado del editor. No se usa n8n: una alerta es una
fila de evento en registros_archivos.

Escribe resultados/falsos_positivos_<fecha>.csv (una fila por edición) y
resultados/resumen_falsos_positivos_<fecha>.md.
"""
import argparse
import csv
import os
import pty
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime

import psycopg2

PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROYECTO)
import config  # noqa: E402

PYTHON = os.path.join(PROYECTO, "venv", "bin", "python")
CARPETA = "/tmp/fim_falsos_positivos"
RESULTADOS = os.path.join(PROYECTO, "resultados")
EVENTOS = ("MODIFICADO", "CREADO", "ELIMINADO", "MOVIDO", "PERMISOS")
ASENTAMIENTO = 1.5   # segundos que se espera después de cada edición para que lleguen todos los eventos

# Teclas para agregar una línea al final, guardar y salir
TECLAS = {
    "vim": lambda texto: ["G", "o", texto, "\x1b", ":wq\r"],
    # nano: Alt+/ va al final, Ctrl+O guarda (Enter confirma el nombre), Ctrl+X sale
    "nano": lambda texto: ["\x1b/", texto, "\x0f", "\r", "\x18"],
}
COMANDOS = {"vim": ["vim"], "nano": ["nano"]}

CORRIDAS = {
    "A_con_filtro": None,                 # PATRONES_IGNORADOS por defecto
    "B_sin_filtro": "__ningun_patron__",  # un patrón que no coincide con nada
}


def conectar():
    conexion = psycopg2.connect(host=config.DB_HOST, database="fim_pruebas", user=config.DB_USER,
                                password=config.DB_PASS)
    conexion.autocommit = True
    return conexion


def consultar(conexion, query, parametros=()):
    with conexion.cursor() as cursor:
        cursor.execute(query, parametros)
        return cursor.fetchall()


def editar(editor, ruta, texto, casa):
    """Corre el editor en una pseudo-terminal y le tipea las teclas. Devuelve (salió_bien, detalle)."""
    pid, terminal = pty.fork()
    if pid == 0:
        os.chdir(os.path.dirname(ruta))
        entorno = {"HOME": casa, "PATH": os.environ["PATH"], "TERM": "xterm", "LANG": "C.UTF-8"}
        os.execvpe(COMANDOS[editor][0], COMANDOS[editor] + [os.path.basename(ruta)], entorno)

    def leer_pantalla(segundos):
        limite = time.time() + segundos
        while time.time() < limite:
            try:
                os.set_blocking(terminal, False)
                os.read(terminal, 65536)
            except (BlockingIOError, OSError):
                pass
            time.sleep(0.02)

    leer_pantalla(0.6)   # que el editor termine de abrir
    for tecla in TECLAS[editor](texto):
        os.write(terminal, tecla.encode("utf-8"))
        leer_pantalla(0.25)
    limite = time.time() + 10
    while time.time() < limite:
        terminado, estado = os.waitpid(pid, os.WNOHANG)
        if terminado:
            os.close(terminal)
            codigo = os.waitstatus_to_exitcode(estado)
            return codigo == 0, f"código {codigo}"
        leer_pantalla(0.1)
    os.kill(pid, 9)
    os.waitpid(pid, 0)
    os.close(terminal)
    return False, "el editor no terminó: se lo cortó"


def corrida(nombre, patron, ediciones, filas):
    print(f"[*] Corrida {nombre}")
    subprocess.run([os.path.join(PROYECTO, "scripts", "preparar_bd_pruebas.sh")], check=True,
                   stdout=subprocess.DEVNULL)
    shutil.rmtree(CARPETA, ignore_errors=True)
    vigilado, casa = f"{CARPETA}/vigilado", f"{CARPETA}/casa"
    os.makedirs(vigilado)
    os.makedirs(casa)
    archivos = {}
    for editor in COMANDOS:
        ruta = os.path.join(vigilado, f"{editor}.conf")
        with open(ruta, "w") as f:
            f.write("".join(f"opcion_{i} = {i}\n" for i in range(20)))
        archivos[editor] = ruta

    entorno = dict(os.environ, DB_NAME="fim_pruebas", RUTAS_MONITOREADAS=vigilado,
                   DIR_BOVEDA=f"{CARPETA}/boveda", DIR_CUARENTENA=f"{CARPETA}/cuarentena",
                   DIR_LOGS=f"{CARPETA}/logs", MODO_RESTAURACION="aprobacion", N8N_WEBHOOK_URL="",
                   PYTHONUNBUFFERED="1")
    if patron:
        entorno["PATRONES_IGNORADOS"] = patron
    subprocess.run([PYTHON, os.path.join(PROYECTO, "generar_baseline.py")], cwd=PROYECTO, env=entorno,
                   check=True, stdout=subprocess.DEVNULL)
    log = open(f"{CARPETA}/monitor_{nombre}.log", "w")
    monitor = subprocess.Popen([PYTHON, os.path.join(PROYECTO, "monitor_fim.py")], cwd=PROYECTO, env=entorno,
                               stdout=log, stderr=subprocess.STDOUT)
    time.sleep(3)
    conexion = conectar()
    try:
        for editor, ruta in archivos.items():
            for k in range(1, ediciones + 1):
                (ultimo,), = consultar(conexion, "SELECT COALESCE(max(id), 0) FROM registros_archivos")
                texto = f"linea_agregada_{k} = {editor}"
                salio_bien, detalle_editor = editar(editor, ruta, texto, casa)
                time.sleep(ASENTAMIENTO)
                guardado = os.path.exists(ruta) and texto in open(ruta, errors="replace").read()
                eventos = consultar(conexion, """
                    SELECT evento, nombre_archivo FROM registros_archivos
                    WHERE id > %s AND evento IN %s ORDER BY id""", (ultimo, EVENTOS))
                esperada = 0
                espurias = []
                for evento, archivo in eventos:
                    if not esperada and evento == "MODIFICADO" and archivo == os.path.basename(ruta):
                        esperada = 1
                    else:
                        espurias.append(f"{evento} {archivo}")
                filas.append({"corrida": nombre, "editor": editor, "edicion": k,
                              "alertas_totales": len(eventos), "esperadas": esperada,
                              "espurias": len(espurias), "detalle_espurias": "; ".join(espurias),
                              "editor_salio_bien": salio_bien, "cambio_guardado": guardado,
                              "observacion": "" if salio_bien else detalle_editor})
                print(f"    {nombre} {editor:<4} #{k:<3} alertas {len(eventos)} (espurias {len(espurias)})"
                      f"{'' if salio_bien and guardado else '  ¡el editor no guardó o no salió bien!'}")
    finally:
        monitor.terminate()
        monitor.wait(10)
        conexion.close()


def resumir(filas, archivo_md):
    with open(archivo_md, "w", encoding="utf-8") as f:
        f.write("| Corrida | Editor | Ediciones | Alertas | Esperadas | Espurias | Tasa de falsos positivos "
                "| Ediciones con problemas del editor |\n|---|---|---:|---:|---:|---:|---:|---:|\n")
        for corrida_ in CORRIDAS:
            for editor in COMANDOS:
                grupo = [x for x in filas if x["corrida"] == corrida_ and x["editor"] == editor]
                if not grupo:
                    continue
                total = sum(x["alertas_totales"] for x in grupo)
                espurias = sum(x["espurias"] for x in grupo)
                problemas = sum(1 for x in grupo if not (x["editor_salio_bien"] and x["cambio_guardado"]))
                tasa = f"{100 * espurias / total:.1f} %" if total else "—"
                f.write(f"| {corrida_} | {editor} | {len(grupo)} | {total} | "
                        f"{sum(x['esperadas'] for x in grupo)} | {espurias} | {tasa} | {problemas} |\n")
        f.write("\nTasa de falsos positivos = alertas espurias / alertas totales.\n\n"
                "Tipos de alertas espurias por corrida y editor:\n\n")
        for corrida_ in CORRIDAS:
            for editor in COMANDOS:
                tipos = Counter(d for x in filas if x["corrida"] == corrida_ and x["editor"] == editor
                                for d in filter(None, x["detalle_espurias"].split("; ")))
                if tipos:
                    f.write(f"- {corrida_}, {editor}: " +
                            ", ".join(f"{t} ({n})" for t, n in tipos.most_common()) + "\n")


def main():
    sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--ediciones", type=int, default=20)
    parser.add_argument("--salida", default=RESULTADOS)
    argumentos = parser.parse_args()
    for editor in COMANDOS:
        if not shutil.which(COMANDOS[editor][0]):
            sys.exit(f"[!] Falta {editor}")

    inicio = datetime.now().astimezone()
    filas = []
    for nombre, patron in CORRIDAS.items():
        corrida(nombre, patron, argumentos.ediciones, filas)

    os.makedirs(argumentos.salida, exist_ok=True)
    sello = inicio.strftime("%Y%m%d_%H%M%S")
    archivo_csv = os.path.join(argumentos.salida, f"falsos_positivos_{sello}.csv")
    with open(archivo_csv, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)
    archivo_md = os.path.join(argumentos.salida, f"resumen_falsos_positivos_{sello}.md")
    resumir(filas, archivo_md)
    versiones = {e: subprocess.run([e, "--version"], capture_output=True, text=True).stdout.splitlines()[0]
                 for e in COMANDOS}
    with open(archivo_md, "a", encoding="utf-8") as f:
        f.write(f"\nEditores: {versiones['vim']}; {versiones['nano']}. Configuración por defecto (sin vimrc ni "
                f"nanorc propios). Monitor en modo aprobación. Fecha: {inicio:%d/%m/%Y %H:%M}.\n")
    print(f"[*] Resultados en {archivo_csv} y {archivo_md}")
    print(open(archivo_md, encoding="utf-8").read())


if __name__ == "__main__":
    main()
