import json
import os

import bd
import config
import monitor_fim
from hashes import get_sha256


def test_con_la_bd_caida_guarda_evidencia_y_no_restaura(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    with open(ruta, "a") as f:
        f.write("intruso\n")
    hash_alterado = get_sha256(ruta)
    entorno_monitor.bd_caida = True

    entorno_monitor.evento_modificado(ruta)

    # No se restaura: sin baseline no se sabe si el cambio es legítimo
    assert get_sha256(ruta) == hash_alterado
    assert entorno_monitor.eventos == []

    pendiente, = entorno_monitor.pendientes()
    assert pendiente["evento"] == "SIN_VERIFICAR"
    assert pendiente["hash_sha256"] == hash_alterado
    assert "+intruso" in pendiente["detalles_diff"]
    assert "fecha_registro" in pendiente
    assert get_sha256(pendiente["ruta_cuarentena"]) == hash_alterado


def test_con_la_bd_caida_un_archivo_igual_a_la_boveda_no_genera_evidencia(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    entorno_monitor.bd_caida = True

    entorno_monitor.evento_modificado(ruta)

    assert entorno_monitor.pendientes() == []
    assert os.listdir("./cuarentena") == []


def test_si_falla_el_insert_el_evento_queda_en_el_log_local(monkeypatch):
    def falla(query, parametros=None):
        raise ConnectionError("BD caída (simulada)")

    monkeypatch.setattr(bd, "ejecutar", falla)

    monitor_fim.log_to_db("config.txt", "./config.txt", "a" * 64, "MODIFICADO", "el diff",
                          hash_anterior="b" * 64, ruta_cuarentena="./cuarentena/x")

    with open(config.ARCHIVO_PENDIENTES, encoding="utf-8") as f:
        pendiente = json.loads(f.readline())
    assert pendiente["evento"] == "MODIFICADO"
    assert pendiente["hash_sha256"] == "a" * 64
    assert pendiente["hash_anterior"] == "b" * 64
    assert pendiente["detalles_diff"] == "el diff"
