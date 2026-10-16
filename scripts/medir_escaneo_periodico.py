"""Mide un escaneo periódico (tipo cron) para compararlo con el monitor por eventos.

Uso: python scripts/medir_escaneo_periodico.py

1. Duración de un escaneo completo (S): se copia a /tmp lo que se puede leer de /etc y se recorre
   con el mismo cálculo que el FIM (SHA-256 en bloques, permisos y propietario). 20 veces.
2. Validación empírica con período corto (T = 10 s): un escáner que corre cada T segundos y 30
   cambios hechos en instantes al azar. Se mide cuánto tarda cada cambio en ser detectado.
3. Cálculo teórico, explicado: si el escaneo corre cada T segundos y dura S, un cambio que ocurre
   en un instante al azar espera en promedio T/2 hasta el próximo escaneo, y como máximo T. Más S
   que tarda el escaneo en llegar al archivo y terminar (cota superior: se toma el escaneo entero).
       detección media ≈ T/2 + S        detección máxima ≈ T + S
   Para T = 1 min, 5 min y 1 h se informa solo la fórmula con el S medido; no se corre.

Escribe resultados/escaneo_periodico_<fecha>.csv y resultados/resumen_escaneo_periodico_<fecha>.md.
"""
import csv
import os
import random
import shutil
import sys
import threading
import time
from datetime import datetime

PROYECTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROYECTO)
sys.path.insert(0, os.path.join(PROYECTO, "scripts"))
from hashes import get_sha256  # noqa: E402
from metadatos import leer_owner_y_permisos  # noqa: E402
from resumir_metricas import percentil  # noqa: E402

CARPETA = "/tmp/fim_escaneo"
RESULTADOS = os.path.join(PROYECTO, "resultados")
REPETICIONES_DURACION = 20
PERIODO_PRUEBA = 10        # segundos
CAMBIOS_PRUEBA = 30
SEMILLA = 2026


def copiar_etc(destino):
    """Copia los archivos comunes que se pueden leer de /etc. Devuelve (cantidad, bytes)."""
    cantidad = total = 0
    for raiz, _, archivos in os.walk("/etc"):
        for nombre in archivos:
            origen = os.path.join(raiz, nombre)
            if not os.path.isfile(origen) or os.path.islink(origen) or not os.access(origen, os.R_OK):
                continue
            copia = os.path.join(destino, os.path.relpath(origen, "/etc"))
            try:
                os.makedirs(os.path.dirname(copia), exist_ok=True)
                shutil.copyfile(origen, copia)
            except OSError:
                continue
            cantidad += 1
            total += os.path.getsize(copia)
    return cantidad, total


def escanear(directorio):
    """Lo que hace un FIM por escaneo: hash, permisos y propietario de cada archivo."""
    estado = {}
    for raiz, _, archivos in os.walk(directorio):
        for nombre in archivos:
            ruta = os.path.join(raiz, nombre)
            estado[ruta] = (get_sha256(ruta), leer_owner_y_permisos(ruta))
    return estado


class EscanerPeriodico(threading.Thread):
    """Escanea cada `periodo` segundos y anota cuándo ve cambiada cada ruta."""

    def __init__(self, directorio, periodo):
        super().__init__(daemon=True)
        self.directorio, self.periodo = directorio, periodo
        self.detecciones = {}          # ruta -> instante en que terminó el escaneo que la vio cambiada
        self.detener = threading.Event()
        self.anterior = escanear(directorio)

    def run(self):
        proximo = time.time() + self.periodo
        while not self.detener.wait(max(0, proximo - time.time())):
            proximo += self.periodo
            actual = escanear(self.directorio)
            fin = time.time()
            for ruta, valor in actual.items():
                if self.anterior.get(ruta) != valor:
                    self.detecciones[ruta] = fin
            self.anterior = actual


def main():
    sys.stdout.reconfigure(line_buffering=True)
    inicio = datetime.now().astimezone()
    shutil.rmtree(CARPETA, ignore_errors=True)
    copia = os.path.join(CARPETA, "etc")
    os.makedirs(copia)
    cantidad, total = copiar_etc(copia)
    print(f"[*] Copia de /etc: {cantidad} archivos, {total / 1024 / 1024:.1f} MB")
    filas = []

    print(f"[*] Duración de un escaneo completo ({REPETICIONES_DURACION} veces)")
    duraciones = []
    for k in range(1, REPETICIONES_DURACION + 1):
        t = time.perf_counter()
        escanear(copia)
        duraciones.append((time.perf_counter() - t) * 1000)
        filas.append({"caso": "escaneo_completo", "repeticion": k, "metrica": "duracion_ms",
                      "valor_ms": round(duraciones[-1], 3), "observacion": f"{cantidad} archivos"})
        print(f"    #{k:<3} {duraciones[-1]:8.1f} ms")

    print(f"[*] Escáner periódico con T = {PERIODO_PRUEBA} s y {CAMBIOS_PRUEBA} cambios al azar")
    azar = random.Random(SEMILLA)
    archivos = sorted(os.path.join(r, n) for r, _, ns in os.walk(copia) for n in ns)
    escaner = EscanerPeriodico(copia, PERIODO_PRUEBA)
    escaner.start()
    latencias = []
    for k in range(1, CAMBIOS_PRUEBA + 1):
        time.sleep(azar.uniform(0, PERIODO_PRUEBA))      # instante al azar respecto del ciclo
        ruta = azar.choice(archivos)
        with open(ruta, "a") as f:
            f.write(f"\n# cambio de prueba {k}\n")
        t_cambio = time.time()
        while ruta not in escaner.detecciones or escaner.detecciones[ruta] < t_cambio:
            time.sleep(0.01)
        latencias.append((escaner.detecciones[ruta] - t_cambio) * 1000)
        filas.append({"caso": f"cron_T{PERIODO_PRUEBA}s", "repeticion": k, "metrica": "deteccion_ms",
                      "valor_ms": round(latencias[-1], 3), "observacion": os.path.relpath(ruta, copia)})
        print(f"    #{k:<3} detectado en {latencias[-1]:8.1f} ms")
    escaner.detener.set()

    os.makedirs(RESULTADOS, exist_ok=True)
    sello = inicio.strftime("%Y%m%d_%H%M%S")
    archivo_csv = os.path.join(RESULTADOS, f"escaneo_periodico_{sello}.csv")
    with open(archivo_csv, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=["caso", "repeticion", "metrica", "valor_ms", "observacion"])
        escritor.writeheader()
        escritor.writerows(filas)

    s_mediana, s_max = percentil(duraciones, 50), max(duraciones)
    media_medida = sum(latencias) / len(latencias)
    archivo_md = os.path.join(RESULTADOS, f"resumen_escaneo_periodico_{sello}.md")
    with open(archivo_md, "w", encoding="utf-8") as f:
        f.write(f"Copia de /etc: {cantidad} archivos legibles, {total / 1024 / 1024:.1f} MB. "
                f"Fecha: {inicio:%d/%m/%Y %H:%M}.\n\n")
        f.write("**Duración medida de un escaneo completo (S)**, 20 veces: "
                f"mediana {s_mediana:.1f} ms, p95 {percentil(duraciones, 95):.1f} ms, "
                f"mínimo {min(duraciones):.1f} ms, máximo {s_max:.1f} ms.\n\n")
        f.write(f"**Validación con T = {PERIODO_PRUEBA} s** ({CAMBIOS_PRUEBA} cambios en instantes al azar): "
                f"detección media medida {media_medida / 1000:.2f} s (mediana "
                f"{percentil(latencias, 50) / 1000:.2f} s, máximo {max(latencias) / 1000:.2f} s). "
                f"La fórmula T/2 + S da {(PERIODO_PRUEBA * 1000 / 2 + s_mediana) / 1000:.2f} s.\n\n")
        f.write("**Cálculo teórico con el S medido** (no medido para estos T):\n\n"
                "| Período T | Detección media ≈ T/2 + S | Detección máxima ≈ T + S |\n|---|---:|---:|\n")
        for nombre, segundos in (("10 s (medido arriba)", 10), ("1 min", 60), ("5 min", 300), ("1 h", 3600)):
            f.write(f"| {nombre} | {segundos / 2 + s_mediana / 1000:.1f} s | {segundos + s_max / 1000:.1f} s |\n")
        f.write("\nS se toma completo como cota superior: en un escaneo real el archivo cambiado puede "
                "aparecer antes del final del recorrido.\n")
    print(f"[*] Resultados en {archivo_csv} y {archivo_md}")
    print(open(archivo_md, encoding="utf-8").read())


if __name__ == "__main__":
    main()
