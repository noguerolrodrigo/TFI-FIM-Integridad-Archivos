import os
import stat

import pytest

import config
import monitor_fim
import restaurar
from hashes import get_sha256


@pytest.fixture
def modo_aprobacion(monkeypatch):
    monkeypatch.setattr(config, "MODO_RESTAURACION", "aprobacion")


def alterar(ruta):
    with open(ruta, "a") as f:
        f.write("intruso\n")
    return get_sha256(ruta)


def test_en_modo_aprobacion_registra_guarda_evidencia_y_no_restaura(entorno_monitor, modo_aprobacion):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    hash_alterado = alterar(ruta)

    entorno_monitor.evento_modificado(ruta)

    assert get_sha256(ruta) == hash_alterado
    assert entorno_monitor.tipos_de_evento() == ["MODIFICADO"]
    assert get_sha256(entorno_monitor.eventos[0]["ruta_cuarentena"]) == hash_alterado


def test_en_modo_aprobacion_el_mismo_cambio_se_registra_una_sola_vez(entorno_monitor, modo_aprobacion):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    alterar(ruta)

    entorno_monitor.evento_modificado(ruta)
    entorno_monitor.evento_modificado(ruta)
    entorno_monitor.evento_modificado(ruta)

    assert entorno_monitor.tipos_de_evento() == ["MODIFICADO"]
    assert len(os.listdir(config.DIRECTORIO_CUARENTENA)) == 1


def test_en_modo_aprobacion_un_segundo_cambio_distinto_si_se_registra(entorno_monitor, modo_aprobacion):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    alterar(ruta)
    entorno_monitor.evento_modificado(ruta)
    alterar(ruta)

    entorno_monitor.evento_modificado(ruta)

    assert entorno_monitor.tipos_de_evento() == ["MODIFICADO", "MODIFICADO"]


def test_restaurar_py_restaura_y_deja_constancia_de_quien_aprobo(entorno_monitor, modo_aprobacion, monkeypatch):
    monkeypatch.setattr(restaurar.getpass, "getuser", lambda: "analista")
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    hash_alterado = alterar(ruta)
    entorno_monitor.evento_modificado(ruta)

    codigo = restaurar.restaurar(ruta)

    assert codigo == 0
    assert get_sha256(ruta) == entorno_monitor.hash_baseline(ruta)
    assert entorno_monitor.tipos_de_evento() == ["MODIFICADO", "RESTAURADO"]
    restaurado = entorno_monitor.eventos[1]
    assert "aprobación de analista (restaurar.py)" in restaurado["detalles_diff"]
    assert restaurado["hash_anterior"] == hash_alterado


def test_restaurar_py_repone_un_archivo_borrado(entorno_monitor, modo_aprobacion):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    os.remove(ruta)
    entorno_monitor.evento_eliminado(ruta)
    assert not os.path.exists(ruta)

    assert restaurar.restaurar(ruta) == 0

    assert get_sha256(ruta) == entorno_monitor.hash_baseline(ruta)
    assert entorno_monitor.tipos_de_evento() == ["ELIMINADO", "RESTAURADO"]


def test_restaurar_py_repone_permisos(entorno_monitor, modo_aprobacion):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n", modo=0o644)
    os.chmod(ruta, 0o777)
    entorno_monitor.evento_modificado(ruta)
    assert stat.S_IMODE(os.stat(ruta).st_mode) == 0o777

    assert restaurar.restaurar(ruta) == 0

    assert stat.S_IMODE(os.stat(ruta).st_mode) == 0o644
    assert entorno_monitor.tipos_de_evento() == ["PERMISOS", "RESTAURADO"]


def test_restaurar_py_no_restaura_desde_una_boveda_alterada(entorno_monitor, modo_aprobacion):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    hash_alterado = alterar(ruta)
    with open(monitor_fim.boveda.ruta_en_boveda(ruta), "w") as f:
        f.write("respaldo envenenado\n")

    assert restaurar.restaurar(ruta) == 1

    assert get_sha256(ruta) == hash_alterado


def test_restaurar_py_sobre_un_archivo_sano_no_hace_nada(entorno_monitor, modo_aprobacion):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")

    assert restaurar.restaurar(ruta) == 0

    assert entorno_monitor.eventos == []


def test_restaurar_py_no_toca_un_archivo_fuera_de_la_baseline(entorno_monitor, modo_aprobacion):
    entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    suelto = entorno_monitor.ruta("suelto.txt")
    with open(suelto, "w") as f:
        f.write("no estoy en la baseline\n")

    assert restaurar.restaurar(suelto) == 1

    assert os.path.exists(suelto)
    assert entorno_monitor.eventos == []


def test_despues_de_restaurar_un_cambio_igual_se_vuelve_a_registrar(entorno_monitor, modo_aprobacion):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    alterar(ruta)
    entorno_monitor.evento_modificado(ruta)
    restaurar.restaurar(ruta)
    entorno_monitor.evento_modificado(ruta)   # el monitor ve que volvió a coincidir con la baseline
    alterar(ruta)

    entorno_monitor.evento_modificado(ruta)

    assert entorno_monitor.tipos_de_evento() == ["MODIFICADO", "RESTAURADO", "MODIFICADO"]


def test_en_modo_aprobacion_un_archivo_nuevo_igual_va_a_cuarentena(entorno_monitor, modo_aprobacion):
    entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    nuevo = entorno_monitor.ruta("backdoor.sh")
    with open(nuevo, "w") as f:
        f.write("#!/bin/sh\n")

    entorno_monitor.evento_creado(nuevo)

    assert not os.path.exists(nuevo)
    assert entorno_monitor.tipos_de_evento() == ["CREADO"]
