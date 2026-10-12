import os

import pytest

import boveda
from filtros import es_ignorado


@pytest.mark.parametrize("nombre", [
    ".config.txt.swp", ".config.txt.swo", "config.txt~", "descarga.tmp",
    boveda.PREFIJO_TEMPORAL + "config.txt", "./directorio_prueba/sub/.x.swp",
])
def test_ignora_temporales(nombre):
    assert es_ignorado(nombre)


@pytest.mark.parametrize("nombre", [
    "config.txt", "script.sh", "tmp", "swp", "archivo.tmp.conf", "./directorio.tmp/config.txt",
])
def test_no_ignora_archivos_normales(nombre):
    assert not es_ignorado(nombre)


def test_el_temporal_de_un_editor_no_genera_eventos(entorno_monitor):
    entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    temporal = entorno_monitor.ruta(".config.txt.swp")
    with open(temporal, "w") as f:
        f.write("datos de vim\n")

    entorno_monitor.evento_creado(temporal)
    entorno_monitor.evento_modificado(temporal)
    os.remove(temporal)
    entorno_monitor.evento_eliminado(temporal)

    assert entorno_monitor.eventos == []
    assert os.listdir("./cuarentena") == []
