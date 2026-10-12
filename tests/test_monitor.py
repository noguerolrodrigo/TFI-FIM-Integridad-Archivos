import os

from hashes import get_sha256


def test_una_modificacion_se_registra_una_vez_y_se_restaura(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    hash_baseline = get_sha256(ruta)
    with open(ruta, "a") as f:
        f.write("intruso\n")
    hash_alterado = get_sha256(ruta)

    entorno_monitor.evento_modificado(ruta)

    assert get_sha256(ruta) == hash_baseline
    assert entorno_monitor.tipos_de_evento() == ["MODIFICADO", "RESTAURADO"]
    registro, restauracion = entorno_monitor.eventos
    assert restauracion["hash_sha256"] == hash_baseline
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

    assert entorno_monitor.tipos_de_evento() == ["MODIFICADO", "RESTAURADO"]
    assert len(os.listdir("./cuarentena")) == 1


def test_un_evento_sin_cambio_de_contenido_no_registra_nada(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")

    entorno_monitor.evento_modificado(ruta)

    assert entorno_monitor.eventos == []
    assert os.listdir("./cuarentena") == []
