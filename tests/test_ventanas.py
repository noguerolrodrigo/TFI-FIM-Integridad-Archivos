import os
import stat

import config
import monitor_fim
from hashes import get_sha256


def alterar(ruta):
    with open(ruta, "a") as f:
        f.write("cambio del administrador\n")
    return get_sha256(ruta)


def test_un_cambio_dentro_de_una_ventana_se_registra_y_no_se_restaura(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    entorno_monitor.ventanas.append((7, ruta))
    hash_nuevo = alterar(ruta)

    entorno_monitor.evento_modificado(ruta)

    assert get_sha256(ruta) == hash_nuevo
    registro, = entorno_monitor.eventos
    assert registro["evento"] == "MODIFICADO"
    assert "ventana de mantenimiento #7" in registro["detalles_diff"]
    assert "+cambio del administrador" in registro["detalles_diff"]
    assert get_sha256(registro["ruta_cuarentena"]) == hash_nuevo
    assert entorno_monitor.avisos[0]["resultado"] == "AUTORIZADO"


def test_una_ventana_sobre_un_directorio_cubre_los_archivos_de_adentro(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("conf.d/app.conf", b"estado cero\n")
    entorno_monitor.ventanas.append((1, entorno_monitor.ruta("conf.d")))
    hash_nuevo = alterar(ruta)

    entorno_monitor.evento_modificado(ruta)

    assert get_sha256(ruta) == hash_nuevo


def test_una_ventana_no_cubre_un_directorio_de_nombre_parecido(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("conf.d2/app.conf", b"estado cero\n")
    entorno_monitor.ventanas.append((1, entorno_monitor.ruta("conf.d")))
    alterar(ruta)

    entorno_monitor.evento_modificado(ruta)

    assert get_sha256(ruta) == entorno_monitor.hash_baseline(ruta)


def test_fuera_de_la_ventana_se_restaura_como_siempre(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    otro = entorno_monitor.crear_en_baseline("otro.txt", b"otro\n")
    entorno_monitor.ventanas.append((1, otro))
    alterar(ruta)

    entorno_monitor.evento_modificado(ruta)

    assert get_sha256(ruta) == entorno_monitor.hash_baseline(ruta)
    assert entorno_monitor.tipos_de_evento() == ["MODIFICADO", "RESTAURADO"]


def test_dentro_de_la_ventana_el_mismo_cambio_se_registra_una_sola_vez(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    entorno_monitor.ventanas.append((1, ruta))
    alterar(ruta)

    entorno_monitor.evento_modificado(ruta)
    entorno_monitor.evento_modificado(ruta)

    assert len(entorno_monitor.eventos) == 1


def test_un_borrado_dentro_de_la_ventana_no_se_restaura(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("viejo.conf", b"ya no se usa\n")
    entorno_monitor.ventanas.append((1, ruta))
    os.remove(ruta)

    entorno_monitor.evento_eliminado(ruta)

    assert not os.path.exists(ruta)
    assert entorno_monitor.tipos_de_evento() == ["ELIMINADO"]


def test_un_archivo_nuevo_dentro_de_la_ventana_no_va_a_cuarentena(entorno_monitor):
    entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    entorno_monitor.ventanas.append((1, entorno_monitor.directorio))
    nuevo = entorno_monitor.ruta("nuevo.conf")
    with open(nuevo, "w") as f:
        f.write("configuración nueva\n")

    entorno_monitor.evento_creado(nuevo)

    assert os.path.exists(nuevo)
    assert entorno_monitor.tipos_de_evento() == ["CREADO"]


def test_un_chmod_dentro_de_la_ventana_no_se_repone(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("script.sh", b"#!/bin/sh\n", modo=0o644)
    entorno_monitor.ventanas.append((1, ruta))
    os.chmod(ruta, 0o755)

    entorno_monitor.evento_modificado(ruta)

    assert stat.S_IMODE(os.stat(ruta).st_mode) == 0o755
    assert entorno_monitor.tipos_de_evento() == ["PERMISOS"]


def test_si_no_se_pueden_consultar_las_ventanas_se_responde_igual(entorno_monitor, monkeypatch):
    def falla():
        raise ConnectionError("tabla inexistente (simulada)")

    monkeypatch.setattr(monitor_fim, "ventanas_vigentes", falla)
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    alterar(ruta)

    entorno_monitor.evento_modificado(ruta)

    assert get_sha256(ruta) == entorno_monitor.hash_baseline(ruta)
