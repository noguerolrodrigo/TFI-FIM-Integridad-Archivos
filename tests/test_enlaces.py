import os

import boveda
import monitor_fim
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


def test_un_archivo_reemplazado_por_un_enlace_se_detecta_aunque_el_contenido_coincida(entorno_monitor, tmp_path):
    # El enlace apunta a una copia idéntica: el hash leído a través del enlace coincide con la
    # baseline, pero el archivo ya no es un archivo y quien controle el destino controla el contenido
    ruta = entorno_monitor.crear_en_baseline("app.conf", b"estado cero\n")
    copia = tmp_path / "copia_identica.txt"
    copia.write_bytes(b"estado cero\n")
    os.remove(ruta)
    os.symlink(copia, ruta)

    entorno_monitor.evento_creado(ruta)

    assert entorno_monitor.tipos_de_evento() == ["MODIFICADO", "RESTAURADO"]
    assert f"reemplazado por un enlace simbólico → {copia}" in entorno_monitor.eventos[0]["detalles_diff"]
    assert not os.path.islink(ruta)
    assert get_sha256(ruta) == entorno_monitor.hash_baseline(ruta)
    assert copia.read_bytes() == b"estado cero\n"


def test_la_evidencia_de_un_enlace_no_incluye_el_contenido_del_destino(entorno_monitor, tmp_path):
    # Sin esto, apuntar el enlace a un archivo ajeno haría que su contenido saliera en el diff
    ruta = entorno_monitor.crear_en_baseline("app.conf", b"estado cero\n")
    secreto = tmp_path / "secreto.txt"
    secreto.write_text("clave: 1234\n")
    os.remove(ruta)
    os.symlink(secreto, ruta)

    entorno_monitor.evento_creado(ruta)

    registro = entorno_monitor.eventos[0]
    assert registro["evento"] == "MODIFICADO"
    assert "1234" not in registro["detalles_diff"]
    assert registro["hash_sha256"] is None
    assert registro["ruta_cuarentena"] is None
    assert os.listdir("./cuarentena") == []
    assert secreto.read_text() == "clave: 1234\n"


def test_un_enlace_roto_en_lugar_de_un_archivo_de_la_baseline_tambien_se_repone(entorno_monitor, tmp_path):
    ruta = entorno_monitor.crear_en_baseline("app.conf", b"estado cero\n")
    os.remove(ruta)
    os.symlink(tmp_path / "no_existe", ruta)

    entorno_monitor.evento_creado(ruta)

    assert entorno_monitor.tipos_de_evento() == ["MODIFICADO", "RESTAURADO"]
    assert not os.path.islink(ruta)


def test_un_enlace_nuevo_se_registra_y_se_quita_sin_tocar_el_destino(entorno_monitor, tmp_path):
    entorno_monitor.crear_en_baseline("app.conf", b"estado cero\n")
    afuera = tmp_path / "afuera.txt"
    afuera.write_text("archivo de afuera\n")
    enlace = entorno_monitor.ruta("atajo.conf")
    os.symlink(afuera, enlace)

    entorno_monitor.evento_creado(enlace)

    assert entorno_monitor.tipos_de_evento() == ["CREADO"]
    assert f"enlace simbólico → {afuera}" in entorno_monitor.eventos[0]["detalles_diff"]
    assert not os.path.lexists(enlace)
    assert afuera.read_text() == "archivo de afuera\n"
    assert os.listdir("./cuarentena") == []


def test_un_enlace_pendiente_de_aprobacion_no_se_puede_aceptar_en_la_baseline(entorno_monitor, tmp_path, monkeypatch):
    monkeypatch.setattr("config.MODO_RESTAURACION", "aprobacion")
    ruta = entorno_monitor.crear_en_baseline("app.conf", b"estado cero\n")
    os.remove(ruta)
    os.symlink(tmp_path / "otro.txt", ruta)

    entorno_monitor.evento_creado(ruta)
    assert os.path.islink(ruta)   # en modo aprobación queda como está hasta que alguien decide

    assert monitor_fim.ejecutar_decision(entorno_monitor.decision(1, monitor_fim.ACEPTAR)) == "RECHAZADA"
    assert monitor_fim.ejecutar_decision(
        entorno_monitor.decision(1, monitor_fim.RESTAURAR, decision_id=2)) == "EJECUTADA"
    assert not os.path.islink(ruta)
    assert get_sha256(ruta) == entorno_monitor.hash_baseline(ruta)


def test_con_la_bd_caida_un_enlace_queda_anotado_sin_leer_el_destino(entorno_monitor, tmp_path):
    ruta = entorno_monitor.crear_en_baseline("app.conf", b"estado cero\n")
    secreto = tmp_path / "secreto.txt"
    secreto.write_text("clave: 1234\n")
    os.remove(ruta)
    os.symlink(secreto, ruta)
    entorno_monitor.bd_caida = True

    entorno_monitor.evento_creado(ruta)

    pendiente = entorno_monitor.pendientes()[0]
    assert pendiente["evento"] == "SIN_VERIFICAR"
    assert f"enlace simbólico → {secreto}" in pendiente["detalles_diff"]
    assert "1234" not in pendiente["detalles_diff"]
    assert pendiente["ruta_cuarentena"] is None
    assert os.listdir("./cuarentena") == []


def test_en_una_ventana_de_mantenimiento_el_enlace_se_registra_sin_leer_el_destino(entorno_monitor, tmp_path):
    ruta = entorno_monitor.crear_en_baseline("app.conf", b"estado cero\n")
    secreto = tmp_path / "secreto.txt"
    secreto.write_text("clave: 1234\n")
    os.remove(ruta)
    os.symlink(secreto, ruta)
    entorno_monitor.ventanas.append((7, entorno_monitor.directorio))

    entorno_monitor.evento_creado(ruta)

    registro = entorno_monitor.eventos[0]
    assert registro["evento"] == "MODIFICADO"
    assert f"enlace simbólico → {secreto}" in registro["detalles_diff"]
    assert "1234" not in registro["detalles_diff"]
    assert registro["ruta_cuarentena"] is None
    assert os.path.islink(ruta)   # autorizado: no se restaura
