import os

from hashes import get_sha256


def test_una_modificacion_restaura_y_deja_un_solo_registro(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    hash_baseline = get_sha256(ruta)
    with open(ruta, "a") as f:
        f.write("intruso\n")
    hash_alterado = get_sha256(ruta)

    entorno_monitor.evento_modificado(ruta)

    assert get_sha256(ruta) == hash_baseline
    assert len(entorno_monitor.eventos) == 1
    registro = entorno_monitor.eventos[0]
    assert registro["evento"] == "MODIFICADO"
    assert registro["hash_sha256"] == hash_alterado
    assert registro["hash_anterior"] == hash_baseline
    assert get_sha256(registro["ruta_cuarentena"]) == hash_alterado


def test_eventos_repetidos_de_watchdog_no_duplican_el_registro(entorno_monitor):
    # inotify puede avisar varias veces por una sola escritura (por ejemplo, truncar + escribir)
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    with open(ruta, "a") as f:
        f.write("intruso\n")

    entorno_monitor.evento_modificado(ruta)
    entorno_monitor.evento_modificado(ruta)
    entorno_monitor.evento_modificado(ruta)

    assert len(entorno_monitor.eventos) == 1
    assert len(os.listdir("./cuarentena")) == 1


def test_un_evento_sin_cambio_de_contenido_no_registra_nada(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")

    entorno_monitor.evento_modificado(ruta)

    assert entorno_monitor.eventos == []
    assert os.listdir("./cuarentena") == []
