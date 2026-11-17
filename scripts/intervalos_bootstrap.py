"""Intervalos de confianza del 95 % para las medianas principales, por bootstrap.

Uso: python scripts/intervalos_bootstrap.py   (desde la raíz del proyecto)

Trabaja sobre los CSV de las corridas de octubre de 2026 (commit 81b1bc8), que son los que informa
el Capítulo 5; no mide nada nuevo. Escribe en resultados/:
    intervalos_bootstrap_20261015.csv   una fila por mediana: n, mediana e intervalo
    intervalos_bootstrap_20261015.md    la misma tabla en Markdown

Método: bootstrap por percentiles. De cada muestra de n valores se sacan REMUESTRAS muestras de n
valores con reposición, se calcula la mediana de cada una y el intervalo va del percentil 2,5 al
97,5 de esas medianas. Cuando la mediana es la conjunta de varios casos, se remuestrea dentro de
cada caso (bootstrap estratificado), para respetar que cada caso aporta siempre 50 valores.
La semilla es fija, así que el resultado se puede reproducir.
"""
import csv
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from resumir_metricas import percentil

SEMILLA = 2026
REMUESTRAS = 10000
RESULTADOS = "resultados"
METRICAS = os.path.join(RESULTADOS, "metricas_20261015_232407.csv")
TELEGRAM_REAL = os.path.join(RESULTADOS, "alerta_telegram_real_20261016_000516.csv")
ESCANEO = os.path.join(RESULTADOS, "escaneo_periodico_20261015_235418.csv")
SALIDA = os.path.join(RESULTADOS, "intervalos_bootstrap_20261015")
CASOS = ["texto", "binario", "permisos", "borrado", "archivo_nuevo"]


def intervalo_bootstrap(estratos, azar, remuestras=REMUESTRAS, confianza=95):
    """Devuelve (mediana, inferior, superior) de la unión de los estratos.

    estratos es una lista de listas de valores; se remuestrea con reposición dentro de cada una.
    """
    todos = [v for estrato in estratos for v in estrato]
    medianas = []
    for _ in range(remuestras):
        muestra = [v for estrato in estratos for v in azar.choices(estrato, k=len(estrato))]
        medianas.append(percentil(muestra, 50))
    cola = (100 - confianza) / 2
    return percentil(todos, 50), percentil(medianas, cola), percentil(medianas, 100 - cola)


def leer(archivo):
    """Devuelve {(caso, metrica): {repeticion: valor}} con los valores presentes."""
    datos = {}
    with open(archivo, encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            if fila["valor_ms"] != "":
                datos.setdefault((fila["caso"], fila["metrica"]), {})[fila["repeticion"]] = float(fila["valor_ms"])
    return datos


def valores(datos, caso, metrica):
    return list(datos.get((caso, metrica), {}).values())


def main():
    met, real, esc = leer(METRICAS), leer(TELEGRAM_REAL), leer(ESCANEO)
    restauracion = {caso: valores(met, caso, "mttr_disco_ms") + valores(met, caso, "contencion_ms") for caso in CASOS}
    # Punta a punta con el bot real: detección + alerta de la misma repetición
    mttd_real, alerta_real = real[("telegram_real", "mttd_ms")], real[("telegram_real", "alerta_ms")]
    punta_a_punta = [mttd_real[r] + alerta_real[r] for r in mttd_real if r in alerta_real]

    medidas = [("Detección (MTTD), cinco casos", [valores(met, c, "mttd_ms") for c in CASOS])]
    medidas += [(f"Detección (MTTD), {c}", [valores(met, c, "mttd_ms")]) for c in CASOS]
    medidas += [("Restauración en disco, cinco casos", [restauracion[c] for c in CASOS])]
    medidas += [(f"Restauración en disco, {c}", [restauracion[c]]) for c in CASOS]
    medidas += [
        ("Alerta con Telegram simulado, cinco casos", [valores(met, c, "alerta_ms") for c in CASOS]),
        ("Ejecución de una decisión", [valores(met, "decision", "ejecucion_ms")]),
        ("COMMIT con el disco en reposo", [valores(met, "commit_en_reposo", "commit_ms")]),
        ("COMMIT en ráfaga", [valores(met, "commit_seguido", "commit_ms")]),
        ("Alerta con Telegram real", [list(alerta_real.values())]),
        ("Escritura a alerta con Telegram real", [punta_a_punta]),
        ("Escaneo completo de 719 archivos (S)", [valores(esc, "escaneo_completo", "duracion_ms")]),
        ("Detección con escaneo cada 10 s", [valores(esc, "cron_T10s", "deteccion_ms")]),
    ]

    azar = random.Random(SEMILLA)
    filas = []
    for nombre, estratos in medidas:
        mediana, inferior, superior = intervalo_bootstrap(estratos, azar)
        filas.append({"medida": nombre, "n": sum(len(e) for e in estratos), "mediana_ms": round(mediana, 1),
                      "ic95_inferior_ms": round(inferior, 1), "ic95_superior_ms": round(superior, 1)})

    with open(SALIDA + ".csv", "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(filas[0]), lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)
    with open(SALIDA + ".md", "w", encoding="utf-8") as f:
        f.write(f"Intervalos de confianza del 95 % de las medianas (bootstrap por percentiles, {REMUESTRAS} "
                f"remuestras, semilla {SEMILLA}). Valores en ms.\n\n")
        f.write("| Medida | n | Mediana | IC 95 % |\n|---|---:|---:|---:|\n")
        for fila in filas:
            f.write(f"| {fila['medida']} | {fila['n']} | {fila['mediana_ms']} | "
                    f"{fila['ic95_inferior_ms']} a {fila['ic95_superior_ms']} |\n")
    print(open(SALIDA + ".md", encoding="utf-8").read())


if __name__ == "__main__":
    main()
