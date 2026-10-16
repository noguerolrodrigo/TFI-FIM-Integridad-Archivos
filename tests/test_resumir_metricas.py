import csv
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import resumir_metricas  # noqa: E402


@pytest.mark.parametrize("p, esperado", [(0, 1), (50, 3), (100, 5), (25, 2), (95, 4.8)])
def test_percentil_con_interpolacion_lineal(p, esperado):
    assert resumir_metricas.percentil([5, 1, 4, 2, 3], p) == pytest.approx(esperado)


def test_percentil_coincide_con_numpy():
    numpy = pytest.importorskip("numpy")
    valores = [3.2, 10.5, 7.1, 4.4, 9.9, 1.0, 8.8, 6.3]
    for p in (5, 50, 90, 95, 99):
        assert resumir_metricas.percentil(valores, p) == pytest.approx(numpy.percentile(valores, p))


def escribir_csv(tmp_path, filas):
    archivo = tmp_path / "metricas_20260101_000000.csv"
    with open(archivo, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=["caso", "repeticion", "metrica", "valor_ms", "evento_id",
                                                 "observacion"])
        escritor.writeheader()
        for caso, k, metrica, valor in filas:
            escritor.writerow({"caso": caso, "repeticion": k, "metrica": metrica, "valor_ms": valor,
                               "evento_id": "", "observacion": ""})
    return archivo


def test_cuenta_los_faltantes_sin_descartarlos_en_silencio(tmp_path):
    archivo = escribir_csv(tmp_path, [("texto", 1, "mttd_ms", "2.0"), ("texto", 2, "mttd_ms", ""),
                                      ("texto", 3, "mttd_ms", "4.0")])

    fila, = resumir_metricas.resumir(resumir_metricas.leer(archivo))

    assert (fila["n"], fila["faltantes"]) == (2, 1)
    assert fila["media"] == pytest.approx(3.0)
    assert (fila["minimo"], fila["maximo"]) == (2.0, 4.0)


def test_un_grupo_sin_valores_queda_sin_estadisticos(tmp_path):
    archivo = escribir_csv(tmp_path, [("borrado", 1, "mttr_bd_ms", "")])

    fila, = resumir_metricas.resumir(resumir_metricas.leer(archivo))

    assert fila["n"] == 0 and fila["faltantes"] == 1 and fila["media"] is None


def test_el_resumen_sale_en_el_orden_de_casos_y_metricas(tmp_path):
    archivo = escribir_csv(tmp_path, [("borrado", 1, "alerta_ms", "9"), ("texto", 1, "alerta_ms", "8"),
                                      ("texto", 1, "mttd_ms", "1")])

    filas = resumir_metricas.resumir(resumir_metricas.leer(archivo))

    assert [(f["caso"], f["metrica"]) for f in filas] == [("texto", "mttd_ms"), ("texto", "alerta_ms"),
                                                          ("borrado", "alerta_ms")]


def test_resumir_dos_veces_da_lo_mismo(tmp_path):
    archivo = escribir_csv(tmp_path, [("texto", k, "mttd_ms", str(k * 1.7)) for k in range(1, 20)])

    assert resumir_metricas.resumir(resumir_metricas.leer(archivo)) == \
        resumir_metricas.resumir(resumir_metricas.leer(archivo))
