"""Resume un CSV de scripts/medir_metricas.py: estadísticos por caso y métrica, y un gráfico.

Uso: python scripts/resumir_metricas.py resultados/metricas_<fecha>.csv

Genera, junto al CSV:
    resumen_<fecha>.csv   n, faltantes, media, mediana, p95, mínimo y máximo (ms) por caso y métrica
    resumen_<fecha>.md    la misma tabla en Markdown, para el informe
    metricas_<fecha>.png  distribución por caso de MTTD, restauración en disco, alerta y ejecución

El p95 se calcula con interpolación lineal entre los dos valores más cercanos (el mismo criterio
que numpy.percentile por defecto). Los valores faltantes no se descartan en silencio: se cuentan.
"""
import csv
import os
import sys
from collections import defaultdict

ORDEN_CASOS = ["texto", "binario", "permisos", "borrado", "archivo_nuevo", "decision", "telegram_real",
               "commit_en_reposo", "commit_seguido"]
NOMBRES_CASOS = {"texto": "Texto (2 KB)", "binario": "Binario (1 MB)", "permisos": "Permisos",
                 "borrado": "Borrado", "archivo_nuevo": "Archivo nuevo", "decision": "Decisión",
                 "telegram_real": "Telegram real", "commit_en_reposo": "COMMIT en reposo",
                 "commit_seguido": "COMMIT en ráfaga"}
ORDEN_METRICAS = ["mttd_ms", "mttr_disco_ms", "contencion_ms", "mttr_bd_ms", "alerta_ms", "ejecucion_ms",
                  "commit_ms"]
NOMBRES_METRICAS = {"mttd_ms": "MTTD", "mttr_disco_ms": "MTTR (disco)", "contencion_ms": "Aislamiento",
                    "mttr_bd_ms": "MTTR (fila RESTAURADO)", "alerta_ms": "Alerta", "ejecucion_ms": "Ejecución",
                    "commit_ms": "COMMIT"}


def percentil(valores, p):
    """Percentil p (0 a 100) con interpolación lineal. valores no puede estar vacío."""
    ordenados = sorted(valores)
    posicion = (len(ordenados) - 1) * p / 100
    abajo = int(posicion)
    arriba = min(abajo + 1, len(ordenados) - 1)
    return ordenados[abajo] + (ordenados[arriba] - ordenados[abajo]) * (posicion - abajo)


def leer(archivo):
    """Agrupa los valores por (caso, métrica). Devuelve {(caso, metrica): (valores, faltantes)}."""
    grupos = defaultdict(lambda: ([], 0))
    with open(archivo, encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            valores, faltantes = grupos[(fila["caso"], fila["metrica"])]
            if fila["valor_ms"] == "":
                grupos[(fila["caso"], fila["metrica"])] = (valores, faltantes + 1)
            else:
                valores.append(float(fila["valor_ms"]))
    return grupos


def orden(clave):
    caso, metrica = clave
    return (ORDEN_CASOS.index(caso) if caso in ORDEN_CASOS else 99,
            ORDEN_METRICAS.index(metrica) if metrica in ORDEN_METRICAS else 99)


def resumir(grupos):
    filas = []
    for (caso, metrica) in sorted(grupos, key=orden):
        valores, faltantes = grupos[(caso, metrica)]
        fila = {"caso": caso, "metrica": metrica, "n": len(valores), "faltantes": faltantes}
        if valores:
            fila.update({"media": sum(valores) / len(valores), "mediana": percentil(valores, 50),
                         "p95": percentil(valores, 95), "minimo": min(valores), "maximo": max(valores)})
        else:
            fila.update({clave: None for clave in ("media", "mediana", "p95", "minimo", "maximo")})
        filas.append(fila)
    return filas


def numero(valor):
    return "—" if valor is None else f"{valor:.1f}"


def guardar_resumen(filas, base):
    columnas = ["caso", "metrica", "n", "faltantes", "media", "mediana", "p95", "minimo", "maximo"]
    with open(f"{base}.csv", "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas)
        escritor.writeheader()
        for fila in filas:
            escritor.writerow({c: (round(fila[c], 3) if isinstance(fila[c], float) else
                                   "" if fila[c] is None else fila[c]) for c in columnas})
    with open(f"{base}.md", "w", encoding="utf-8") as f:
        f.write("| Caso | Métrica | n | Faltantes | Media | Mediana | p95 | Mín. | Máx. |\n")
        f.write("|---|---|---:|---:|---:|---:|---:|---:|---:|\n")
        for fila in filas:
            f.write(f"| {NOMBRES_CASOS.get(fila['caso'], fila['caso'])} "
                    f"| {NOMBRES_METRICAS.get(fila['metrica'], fila['metrica'])} "
                    f"| {fila['n']} | {fila['faltantes']} | {numero(fila['media'])} | {numero(fila['mediana'])} "
                    f"| {numero(fila['p95'])} | {numero(fila['minimo'])} | {numero(fila['maximo'])} |\n")
        f.write("\nValores en milisegundos. p95 con interpolación lineal.\n")


def graficar(grupos, archivo_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    superficie, tinta, tinta_suave, grilla, serie = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6"

    # Un panel por métrica, cada uno con su propia escala (nunca dos escalas en un mismo eje).
    # La restauración en disco y el aislamiento del archivo nuevo van en el mismo panel: las dos
    # miden cuándo el disco quedó otra vez como en la baseline.
    paneles = [
        ("MTTD: escritura → detección registrada", ["mttd_ms"]),
        ("Restauración en disco (archivo nuevo: aislamiento)", ["mttr_disco_ms", "contencion_ms"]),
        ("Alerta: detección → notificación de n8n", ["alerta_ms"]),
        ("Ejecución: decisión → ejecución del monitor", ["ejecucion_ms"]),
    ]
    contenido = []
    for titulo, metricas in paneles:
        datos = []
        for caso in ORDEN_CASOS:
            valores = [v for m in metricas for v in grupos.get((caso, m), ([], 0))[0]]
            if valores:
                datos.append((NOMBRES_CASOS[caso], valores))
        if datos:
            datos.reverse()  # el primer caso arriba
            contenido.append((titulo, datos))

    # Cada panel tan alto como filas tiene, para que una fila sola no quede estirada
    alturas = [len(datos) + 1.2 for _, datos in contenido]
    fig, ejes = plt.subplots(len(contenido), 1, figsize=(8, 0.42 * sum(alturas) + 0.5), facecolor=superficie,
                             squeeze=False, gridspec_kw={"height_ratios": alturas})
    for eje, (titulo, datos) in zip(ejes[:, 0], contenido):
        posiciones = range(1, len(datos) + 1)
        eje.set_facecolor(superficie)
        eje.boxplot([v for _, v in datos], positions=list(posiciones), orientation="horizontal", widths=0.45,
                    showfliers=False, patch_artist=True,
                    boxprops={"facecolor": "#d6e4f7", "edgecolor": serie, "linewidth": 1.2},
                    medianprops={"color": serie, "linewidth": 2},
                    whiskerprops={"color": serie, "linewidth": 1}, capprops={"color": serie, "linewidth": 1})
        for posicion, (_, valores) in zip(posiciones, datos):
            # Cada repetición como un punto, con un corrimiento vertical fijo para que no se tapen
            corrimientos = [((i * 37) % 21 - 10) / 60 for i in range(len(valores))]
            eje.scatter(valores, [posicion + c for c in corrimientos], s=9, color=serie, alpha=0.35,
                        linewidths=0, zorder=3)
            mediana = percentil(valores, 50)
            eje.annotate(f"mediana {mediana:.1f} ms", (max(valores), posicion), xytext=(6, 0),
                         textcoords="offset points", va="center", fontsize=8, color=tinta_suave)
        eje.set_yticks(list(posiciones), [n for n, _ in datos], fontsize=9, color=tinta)
        eje.set_title(titulo, loc="left", fontsize=10, color=tinta, pad=6)
        eje.set_xlabel("milisegundos", fontsize=8, color=tinta_suave)
        eje.tick_params(axis="x", labelsize=8, colors=tinta_suave)
        eje.tick_params(axis="y", length=0)
        eje.grid(axis="x", color=grilla, linewidth=0.8)
        eje.set_axisbelow(True)
        for lado in ("top", "right", "left"):
            eje.spines[lado].set_visible(False)
        eje.spines["bottom"].set_color(grilla)
        # Lugar a la derecha para la etiqueta de la mediana
        eje.set_xlim(0, max(max(v) for _, v in datos) * 1.4)
        eje.set_ylim(0.4, len(datos) + 0.6)
    fig.tight_layout()
    fig.savefig(archivo_png, dpi=200, facecolor=superficie)
    plt.close(fig)


def main():
    if len(sys.argv) != 2:
        sys.exit("Uso: python scripts/resumir_metricas.py resultados/metricas_<fecha>.csv")
    archivo = sys.argv[1]
    carpeta, nombre = os.path.split(os.path.abspath(archivo))
    sello = nombre.split("_", 1)[1].rsplit(".", 1)[0]
    grupos = leer(archivo)
    filas = resumir(grupos)
    guardar_resumen(filas, os.path.join(carpeta, f"resumen_{sello}"))
    graficar(grupos, os.path.join(carpeta, f"grafico_{sello}.png"))
    print(f"[*] Resumen en {carpeta}/resumen_{sello}.csv y .md; gráfico en {carpeta}/grafico_{sello}.png")


if __name__ == "__main__":
    main()
