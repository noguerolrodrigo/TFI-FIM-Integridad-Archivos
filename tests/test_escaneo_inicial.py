import os

import pytest

import monitor_fim
from hashes import get_sha256


def test_detecta_y_restaura_lo_que_cambio_con_el_monitor_apagado(entorno_monitor):
    intacto = entorno_monitor.crear_en_baseline("intacto.txt", b"sin tocar\n")
    alterado = entorno_monitor.crear_en_baseline("alterado.txt", b"estado cero\n")
    hash_baseline = get_sha256(alterado)
    with open(alterado, "a") as f:
        f.write("cambio hecho con el monitor apagado\n")

    monitor_fim.escaneo_inicial()

    assert get_sha256(alterado) == hash_baseline
    assert [e["ruta_completa"] for e in entorno_monitor.eventos] == [alterado]
    assert get_sha256(intacto) == entorno_monitor.baseline[intacto]


def test_aisla_un_archivo_que_aparecio_con_el_monitor_apagado(entorno_monitor):
    entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    nuevo = entorno_monitor.ruta("backdoor.sh")
    with open(nuevo, "w") as f:
        f.write("#!/bin/sh\n")

    monitor_fim.escaneo_inicial()

    assert not os.path.exists(nuevo)
    assert [e["ruta_completa"] for e in entorno_monitor.eventos] == [nuevo]
    assert len(os.listdir("./cuarentena")) == 1


def test_sin_diferencias_no_registra_nada(entorno_monitor):
    entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")

    monitor_fim.escaneo_inicial()

    assert entorno_monitor.eventos == []


def test_sin_baseline_el_monitor_no_arranca(entorno_monitor):
    # Sin baseline todo parecería "archivo nuevo" y terminaría en cuarentena
    suelto = entorno_monitor.ruta("suelto.txt")
    with open(suelto, "w") as f:
        f.write("todavía no pasó por la baseline\n")

    with pytest.raises(SystemExit):
        monitor_fim.escaneo_inicial()

    assert os.path.exists(suelto)


def test_con_la_bd_caida_el_escaneo_no_toca_nada(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    entorno_monitor.bd_caida = True

    monitor_fim.escaneo_inicial()

    assert os.path.exists(ruta)
    assert entorno_monitor.eventos == []
