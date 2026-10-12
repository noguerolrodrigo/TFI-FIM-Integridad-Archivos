import hashlib
import os
import stat

import pytest

import boveda


def sha256(ruta):
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def permisos(ruta):
    return stat.S_IMODE(os.stat(ruta).st_mode)


@pytest.fixture
def entorno(tmp_path):
    """Un directorio vigilado y una bóveda, los dos vacíos y temporales."""
    vigilado = tmp_path / "vigilado"
    vigilado.mkdir()
    return vigilado, str(tmp_path / "boveda")


def test_el_respaldo_espeja_la_ruta_absoluta(entorno):
    vigilado, dir_boveda = entorno
    archivo = vigilado / "config.txt"
    archivo.write_text("estado cero\n")

    destino = boveda.respaldar(str(archivo), dir_boveda)

    assert destino == os.path.join(dir_boveda, str(archivo).lstrip("/"))
    assert sha256(destino) == sha256(archivo)
    assert boveda.tiene_respaldo(str(archivo), dir_boveda)


def test_restaura_un_archivo_de_texto_modificado(entorno):
    vigilado, dir_boveda = entorno
    archivo = vigilado / "config.txt"
    archivo.write_text("estado cero\n")
    boveda.respaldar(str(archivo), dir_boveda)

    archivo.write_text("estado cero\nlinea del atacante\n")
    boveda.restaurar(str(archivo), dir_boveda)

    assert archivo.read_text() == "estado cero\n"


def test_restaura_un_binario_sin_corromperlo(entorno):
    vigilado, dir_boveda = entorno
    archivo = vigilado / "programa.bin"
    # Todos los bytes posibles: incluye secuencias que no son UTF-8 válido
    archivo.write_bytes(bytes(range(256)) * 4)
    hash_original = sha256(archivo)
    boveda.respaldar(str(archivo), dir_boveda)

    archivo.write_bytes(b"\x00\xff basura")
    boveda.restaurar(str(archivo), dir_boveda)

    assert sha256(archivo) == hash_original


def test_restaura_los_permisos(entorno):
    vigilado, dir_boveda = entorno
    archivo = vigilado / "script.sh"
    archivo.write_text("#!/bin/sh\necho hola\n")
    os.chmod(archivo, 0o755)
    boveda.respaldar(str(archivo), dir_boveda)

    archivo.write_text("#!/bin/sh\nrm -rf /\n")
    os.chmod(archivo, 0o777)
    boveda.restaurar(str(archivo), dir_boveda)

    assert permisos(archivo) == 0o755


def test_restaura_un_archivo_borrado(entorno):
    vigilado, dir_boveda = entorno
    archivo = vigilado / "config.txt"
    archivo.write_text("estado cero\n")
    boveda.respaldar(str(archivo), dir_boveda)

    archivo.unlink()
    boveda.restaurar(str(archivo), dir_boveda)

    assert archivo.read_text() == "estado cero\n"


def test_la_restauracion_no_deja_temporales(entorno):
    vigilado, dir_boveda = entorno
    archivo = vigilado / "config.txt"
    archivo.write_text("estado cero\n")
    boveda.respaldar(str(archivo), dir_boveda)

    boveda.restaurar(str(archivo), dir_boveda)

    assert os.listdir(vigilado) == ["config.txt"]


def test_sin_respaldo_no_restaura_ni_crea_el_archivo(entorno):
    vigilado, dir_boveda = entorno
    archivo = vigilado / "nuevo.txt"

    assert not boveda.tiene_respaldo(str(archivo), dir_boveda)
    with pytest.raises(FileNotFoundError):
        boveda.restaurar(str(archivo), dir_boveda)
    assert not archivo.exists()


def test_limpia_los_respaldos_que_ya_no_estan_en_la_baseline(entorno):
    vigilado, dir_boveda = entorno
    vigente = vigilado / "vigente.txt"
    viejo = vigilado / "viejo.txt"
    vigente.write_text("sigo en la baseline\n")
    viejo.write_text("me sacaron de la baseline\n")
    boveda.respaldar(str(vigente), dir_boveda)
    boveda.respaldar(str(viejo), dir_boveda)

    borrados = boveda.limpiar_huerfanos(str(vigilado), [str(vigente)], dir_boveda)

    assert borrados == 1
    assert boveda.tiene_respaldo(str(vigente), dir_boveda)
    assert not boveda.tiene_respaldo(str(viejo), dir_boveda)
