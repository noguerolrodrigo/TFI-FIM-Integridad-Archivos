import os
import stat

from hashes import get_sha256
from metadatos import leer_owner_y_permisos


def modo(ruta):
    return stat.S_IMODE(os.stat(ruta).st_mode)


def test_metadatos_devuelve_uid_y_modo_octal(tmp_path):
    archivo = tmp_path / "a.txt"
    archivo.write_text("x")
    os.chmod(archivo, 0o640)

    assert leer_owner_y_permisos(str(archivo)) == (str(os.getuid()), "640")


def test_metadatos_incluye_el_bit_setuid(tmp_path):
    archivo = tmp_path / "programa"
    archivo.write_text("x")
    os.chmod(archivo, 0o4755)

    assert leer_owner_y_permisos(str(archivo))[1] == "4755"


def test_metadatos_de_un_archivo_que_no_existe(tmp_path):
    assert leer_owner_y_permisos(str(tmp_path / "no_existe")) == ("N/A", "N/A")


def test_chmod_se_registra_como_permisos_y_se_repone(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n", modo=0o644)
    os.chmod(ruta, 0o777)

    entorno_monitor.evento_modificado(ruta)   # un chmod llega de watchdog como "modificado"

    assert modo(ruta) == 0o644
    assert entorno_monitor.tipos_de_evento() == ["PERMISOS", "RESTAURADO"]
    registro = entorno_monitor.eventos[0]
    assert "644 -> 777" in registro["detalles_diff"]
    assert registro["ruta_cuarentena"] is None   # el contenido no cambió: no hay nada que aislar
    assert os.listdir("./cuarentena") == []


def test_agregar_setuid_a_un_ejecutable_se_detecta_y_se_repone(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("programa", b"#!/bin/sh\n", modo=0o755)
    os.chmod(ruta, 0o4755)

    entorno_monitor.evento_modificado(ruta)

    assert modo(ruta) == 0o755
    assert "755 -> 4755" in entorno_monitor.eventos[0]["detalles_diff"]


def test_contenido_y_permisos_cambiados_se_restauran_los_dos(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("script.sh", b"#!/bin/sh\necho hola\n", modo=0o755)
    with open(ruta, "a") as f:
        f.write("rm -rf /\n")
    os.chmod(ruta, 0o777)

    entorno_monitor.evento_modificado(ruta)

    assert get_sha256(ruta) == entorno_monitor.hash_baseline(ruta)
    assert modo(ruta) == 0o755
    assert entorno_monitor.tipos_de_evento() == ["MODIFICADO", "RESTAURADO"]


def test_cambio_de_propietario_sin_ser_root_se_registra_pero_no_se_puede_reponer(entorno_monitor, monkeypatch):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    entorno_monitor.baseline[ruta]["owner"] = "0"   # la baseline dice que el dueño era root

    def chown_sin_permiso(ruta, uid, gid):
        raise PermissionError("Operation not permitted")

    monkeypatch.setattr(os, "chown", chown_sin_permiso)

    entorno_monitor.evento_modificado(ruta)

    assert entorno_monitor.tipos_de_evento() == ["PERMISOS"]
    assert "Propietario" in entorno_monitor.eventos[0]["detalles_diff"]
