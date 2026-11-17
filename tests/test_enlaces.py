import os

import boveda
from hashes import get_sha256

# Hallazgo M2 de la devolución del tribunal: la restauración no tiene que seguir enlaces simbólicos.


def test_restaurar_no_escribe_a_traves_de_un_enlace_puesto_en_el_temporal(tmp_path):
    # Prueba de concepto del tribunal: el atacante deja de antemano, con el nombre que tenía el
    # temporal de la restauración, un enlace a un archivo de afuera del directorio vigilado
    vigilado = tmp_path / "vigilado"
    vigilado.mkdir()
    dir_boveda = str(tmp_path / "boveda")
    archivo = vigilado / "app.conf"
    archivo.write_text("estado cero\n")
    boveda.respaldar(str(archivo), dir_boveda)

    victima = tmp_path / "victima.txt"
    victima.write_text("archivo de afuera: no se toca\n")
    os.symlink(victima, vigilado / ".fim_tmp_app.conf")

    archivo.write_text("estado cero\nlinea del atacante\n")
    boveda.restaurar(str(archivo), dir_boveda)

    assert victima.read_text() == "archivo de afuera: no se toca\n"
    assert not os.path.islink(archivo)
    assert archivo.read_text() == "estado cero\n"


def test_el_monitor_restaura_sin_tocar_el_archivo_de_afuera(entorno_monitor, tmp_path):
    ruta = entorno_monitor.crear_en_baseline("app.conf", b"estado cero\n")
    victima = tmp_path / "victima.txt"
    victima.write_text("archivo de afuera: no se toca\n")
    os.symlink(victima, entorno_monitor.ruta(".fim_tmp_app.conf"))

    with open(ruta, "a") as f:
        f.write("linea del atacante\n")
    entorno_monitor.evento_modificado(ruta)

    assert victima.read_text() == "archivo de afuera: no se toca\n"
    assert not os.path.islink(ruta)
    assert get_sha256(ruta) == entorno_monitor.hash_baseline(ruta)
