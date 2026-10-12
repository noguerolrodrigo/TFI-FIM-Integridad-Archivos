import os
import shutil

import boveda
from hashes import get_sha256


def test_archivo_nuevo_se_registra_como_creado_y_va_a_cuarentena(entorno_monitor):
    entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    nuevo = entorno_monitor.ruta("backdoor.sh")
    with open(nuevo, "w") as f:
        f.write("#!/bin/sh\n")
    hash_nuevo = get_sha256(nuevo)

    entorno_monitor.evento_creado(nuevo)

    assert not os.path.exists(nuevo)
    registro, = entorno_monitor.eventos
    assert registro["evento"] == "CREADO"
    assert registro["hash_anterior"] is None
    assert get_sha256(registro["ruta_cuarentena"]) == hash_nuevo


def test_archivo_borrado_se_registra_como_eliminado_y_se_restaura(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    hash_baseline = entorno_monitor.baseline[ruta]
    os.remove(ruta)

    entorno_monitor.evento_eliminado(ruta)

    assert get_sha256(ruta) == hash_baseline
    eliminado, restaurado = entorno_monitor.eventos
    assert eliminado["evento"] == "ELIMINADO"
    assert eliminado["hash_sha256"] is None
    assert eliminado["hash_anterior"] == hash_baseline
    assert eliminado["ruta_cuarentena"] is None
    assert restaurado["evento"] == "RESTAURADO"
    assert restaurado["hash_sha256"] == hash_baseline


def test_borrar_un_archivo_que_no_esta_en_la_baseline_no_registra_nada(entorno_monitor):
    entorno_monitor.evento_eliminado(entorno_monitor.ruta("nunca_existio.txt"))

    assert entorno_monitor.eventos == []


def test_archivo_movido_se_registra_se_restaura_y_el_destino_va_a_cuarentena(entorno_monitor):
    origen = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    hash_baseline = entorno_monitor.baseline[origen]
    destino = entorno_monitor.ruta("config.viejo")
    os.rename(origen, destino)

    entorno_monitor.evento_movido(origen, destino)

    assert get_sha256(origen) == hash_baseline
    assert not os.path.exists(destino)
    assert entorno_monitor.tipos_de_evento() == ["MOVIDO", "RESTAURADO", "CREADO"]
    movido, _, creado = entorno_monitor.eventos
    assert destino in movido["detalles_diff"]
    assert creado["ruta_completa"] == destino
    assert origen in creado["detalles_diff"]


def test_reemplazo_por_renombrado_se_detecta_como_modificado(entorno_monitor):
    # Así guardan sed -i y varios editores: escriben un temporal y lo renombran encima del original
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    hash_baseline = entorno_monitor.baseline[ruta]
    temporal = entorno_monitor.ruta("sedAbC123")
    with open(temporal, "w") as f:
        f.write("contenido del atacante\n")
    os.rename(temporal, ruta)

    entorno_monitor.evento_movido(temporal, ruta)

    assert get_sha256(ruta) == hash_baseline
    assert entorno_monitor.tipos_de_evento() == ["MODIFICADO", "RESTAURADO"]


def test_eliminado_con_la_boveda_alterada_no_se_restaura(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    with open(boveda.ruta_en_boveda(ruta), "w") as f:
        f.write("respaldo envenenado\n")
    os.remove(ruta)

    entorno_monitor.evento_eliminado(ruta)

    assert not os.path.exists(ruta)
    registro, = entorno_monitor.eventos
    assert registro["evento"] == "ELIMINADO"
    assert "BÓVEDA NO CONFIABLE" in registro["detalles_diff"]


def test_directorio_borrado_restaura_los_archivos_de_la_baseline(entorno_monitor):
    uno = entorno_monitor.crear_en_baseline("conf.d/uno.conf", b"uno\n")
    dos = entorno_monitor.crear_en_baseline("conf.d/dos.conf", b"dos\n")
    afuera = entorno_monitor.crear_en_baseline("afuera.conf", b"afuera\n")
    shutil.rmtree(entorno_monitor.ruta("conf.d"))

    entorno_monitor.evento_eliminado(entorno_monitor.ruta("conf.d"), es_directorio=True)

    assert get_sha256(uno) == entorno_monitor.baseline[uno]
    assert get_sha256(dos) == entorno_monitor.baseline[dos]
    assert sorted(entorno_monitor.tipos_de_evento()) == ["ELIMINADO", "ELIMINADO", "RESTAURADO", "RESTAURADO"]
    assert all(e["ruta_completa"] != afuera for e in entorno_monitor.eventos)


def test_la_restauracion_no_dispara_eventos_falsos(entorno_monitor):
    # Al restaurar, watchdog avisa del temporal y del renombrado: no tienen que generar registros
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    temporal = entorno_monitor.ruta(boveda.PREFIJO_TEMPORAL + "config.txt")

    entorno_monitor.evento_creado(temporal)
    entorno_monitor.evento_modificado(temporal)
    entorno_monitor.evento_movido(temporal, ruta)

    assert entorno_monitor.eventos == []
