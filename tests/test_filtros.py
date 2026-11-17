import os

import pytest

import boveda
from filtros import es_ignorado


@pytest.mark.parametrize("nombre", [
    ".config.txt.swp", ".config.txt.swo", "config.txt~", "descarga.tmp", "./directorio_prueba/sub/.x.swp",
])
def test_ignora_temporales(nombre):
    assert es_ignorado(nombre)


@pytest.mark.parametrize("nombre", [
    "config.txt", "script.sh", "tmp", "swp", "archivo.tmp.conf", "./directorio.tmp/config.txt",
    boveda.PREFIJO_TEMPORAL + "config.txt",   # el prefijo de la restauración no alcanza para ser ignorado
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


def test_solo_ignora_el_temporal_de_la_restauracion_mientras_es_propio(tmp_path, monkeypatch):
    temporal = str(tmp_path / (boveda.PREFIJO_TEMPORAL + "a1b2c3d4"))
    assert not es_ignorado(temporal)

    monkeypatch.setattr(boveda, "temporales_propios", {temporal})
    assert es_ignorado(temporal)


def test_la_restauracion_registra_su_temporal_solo_mientras_dura(tmp_path, monkeypatch):
    archivo = tmp_path / "config.txt"
    archivo.write_text("estado cero\n")
    dir_boveda = str(tmp_path / "boveda")
    boveda.respaldar(str(archivo), dir_boveda)

    # Se mira el registro justo cuando el temporal reemplaza al original
    vistos = []
    replace_real = os.replace

    def replace_espiado(origen, destino):
        vistos.append((es_ignorado(origen), os.path.basename(origen)))
        replace_real(origen, destino)

    monkeypatch.setattr(os, "replace", replace_espiado)
    boveda.restaurar(str(archivo), dir_boveda)

    ignorado, nombre = vistos[0]
    assert ignorado
    assert nombre.startswith(boveda.PREFIJO_TEMPORAL) and nombre != boveda.PREFIJO_TEMPORAL + "config.txt"
    assert boveda.temporales_propios == set()


def test_un_archivo_con_el_prefijo_de_la_restauracion_se_detecta(entorno_monitor):
    # Antes cualquier .fim_tmp_* era invisible para el monitor (hallazgo M2 del tribunal)
    entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    intruso = entorno_monitor.ruta(boveda.PREFIJO_TEMPORAL + "puerta_trasera.sh")
    with open(intruso, "w") as f:
        f.write("#!/bin/sh\n")

    entorno_monitor.evento_creado(intruso)

    assert entorno_monitor.tipos_de_evento() == ["CREADO"]
    assert not os.path.exists(intruso)
    assert len(os.listdir("./cuarentena")) == 1
