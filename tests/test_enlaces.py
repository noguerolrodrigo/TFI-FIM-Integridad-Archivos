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


# --- Una carpeta del camino reemplazada por un enlace (variante de M2) ---

def carpeta_cambiada_por_enlace(entorno_monitor, afuera):
    """Renombra sub/ y pone en su lugar un enlace a una carpeta de afuera del directorio vigilado."""
    os.rename(entorno_monitor.ruta("sub"), entorno_monitor.ruta("sub.viejo"))
    os.symlink(afuera, entorno_monitor.ruta("sub"))


def test_no_restaura_a_traves_de_una_carpeta_reemplazada_por_un_enlace(entorno_monitor, tmp_path):
    ruta = entorno_monitor.crear_en_baseline("sub/app.conf", b"estado cero\n")
    afuera = tmp_path / "afuera"
    afuera.mkdir()
    carpeta_cambiada_por_enlace(entorno_monitor, afuera)

    assert monitor_fim.procesar(ruta) == monitor_fim.NO_RESTAURADO

    assert os.listdir(afuera) == []   # antes, la restauración escribía afuera/app.conf
    assert entorno_monitor.tipos_de_evento() == ["ELIMINADO"]
    assert f"enlace simbólico y lleva a {afuera}" in entorno_monitor.eventos[0]["detalles_diff"]
    assert entorno_monitor.avisos == [{"tipo": "evento", "evento_id": 1, "resultado": "NO_RESTAURADO"}]


def test_no_lee_a_traves_de_una_carpeta_reemplazada_por_un_enlace(entorno_monitor, tmp_path):
    ruta = entorno_monitor.crear_en_baseline("sub/app.conf", b"estado cero\n")
    afuera = tmp_path / "afuera"
    afuera.mkdir()
    (afuera / "app.conf").write_text("clave: 1234\n")
    carpeta_cambiada_por_enlace(entorno_monitor, afuera)

    assert monitor_fim.procesar(ruta) == monitor_fim.NO_RESTAURADO

    registro = entorno_monitor.eventos[0]
    assert "1234" not in registro["detalles_diff"]
    assert registro["ruta_cuarentena"] is None
    assert os.listdir("./cuarentena") == []
    assert (afuera / "app.conf").read_text() == "clave: 1234\n"


def test_al_quitar_el_enlace_de_la_carpeta_se_reponen_sus_archivos(entorno_monitor, tmp_path):
    ruta = entorno_monitor.crear_en_baseline("sub/app.conf", b"estado cero\n")
    afuera = tmp_path / "afuera"
    afuera.mkdir()
    carpeta_cambiada_por_enlace(entorno_monitor, afuera)

    entorno_monitor.evento_creado(entorno_monitor.ruta("sub"))   # el aviso de inotify por el enlace

    assert os.listdir(afuera) == []
    assert not os.path.islink(entorno_monitor.ruta("sub"))
    assert get_sha256(ruta) == entorno_monitor.hash_baseline(ruta)
    assert entorno_monitor.tipos_de_evento() == ["CREADO", "ELIMINADO", "RESTAURADO"]


def test_si_la_carpeta_se_cambia_por_un_enlace_justo_antes_de_restaurar_tampoco_escribe_afuera(
        entorno_monitor, tmp_path, monkeypatch):
    ruta = entorno_monitor.crear_en_baseline("sub/app.conf", b"estado cero\n")
    afuera = tmp_path / "afuera"
    afuera.mkdir()

    # El cambio de carpeta ocurre mientras se registra el evento, después de la primera revisión
    def registrar_y_cambiar(*args, **kwargs):
        if not os.path.islink(entorno_monitor.ruta("sub")):
            carpeta_cambiada_por_enlace(entorno_monitor, afuera)
        return entorno_monitor.registrar(*args, **kwargs)

    monkeypatch.setattr(monitor_fim, "log_to_db", registrar_y_cambiar)
    os.remove(ruta)

    assert monitor_fim.procesar(ruta) == monitor_fim.NO_RESTAURADO
    assert os.listdir(afuera) == []


def test_no_se_acepta_un_cambio_si_la_carpeta_paso_a_ser_un_enlace(entorno_monitor, tmp_path, monkeypatch):
    monkeypatch.setattr("config.MODO_RESTAURACION", "aprobacion")
    ruta = entorno_monitor.crear_en_baseline("sub/app.conf", b"estado cero\n")
    with open(ruta, "a") as f:
        f.write("cambio pendiente\n")
    entorno_monitor.evento_modificado(ruta)
    afuera = tmp_path / "afuera"
    afuera.mkdir()
    carpeta_cambiada_por_enlace(entorno_monitor, afuera)

    assert monitor_fim.ejecutar_decision(entorno_monitor.decision(1, monitor_fim.ACEPTAR)) == "RECHAZADA"
    assert os.listdir(afuera) == []


# --- Hash, diff y copia a cuarentena desde una sola apertura (TOCTOU) ---

def test_la_copia_a_cuarentena_es_del_archivo_que_se_verifico_aunque_despues_lo_cambien_por_un_enlace(
        entorno_monitor, tmp_path, monkeypatch):
    ruta = entorno_monitor.crear_en_baseline("app.conf", b"estado cero\n")
    secreto = tmp_path / "secreto.txt"
    secreto.write_text("clave: 1234\n")
    with open(ruta, "a") as f:
        f.write("linea del atacante\n")

    # El cambio por un enlace ocurre después del hash y antes de la copia a cuarentena
    def registrar_y_cambiar(*args, **kwargs):
        if args[3] == "MODIFICADO":
            os.remove(ruta)
            os.symlink(secreto, ruta)
        return entorno_monitor.registrar(*args, **kwargs)

    monkeypatch.setattr(monitor_fim, "log_to_db", registrar_y_cambiar)
    entorno_monitor.evento_modificado(ruta)

    registro = entorno_monitor.eventos[0]
    with open(registro["ruta_cuarentena"]) as f:
        assert f.read() == "estado cero\nlinea del atacante\n"
    assert get_sha256(registro["ruta_cuarentena"]) == registro["hash_sha256"]
    assert not os.path.islink(ruta)
    assert get_sha256(ruta) == entorno_monitor.hash_baseline(ruta)


def test_el_diff_es_del_archivo_que_se_verifico_aunque_despues_lo_cambien_por_un_enlace(
        entorno_monitor, tmp_path, monkeypatch):
    ruta = entorno_monitor.crear_en_baseline("app.conf", b"estado cero\n")
    secreto = tmp_path / "secreto.txt"
    secreto.write_text("clave: 1234\n")
    with open(ruta, "a") as f:
        f.write("linea del atacante\n")

    # El cambio por un enlace ocurre después del hash y antes de armar el diff
    verificar_real = monitor_fim.verificar

    def verificar_y_cambiar(*args, **kwargs):
        resultado = verificar_real(*args, **kwargs)
        os.remove(ruta)
        os.symlink(secreto, ruta)
        return resultado

    monkeypatch.setattr(monitor_fim, "verificar", verificar_y_cambiar)
    entorno_monitor.evento_modificado(ruta)

    diff = entorno_monitor.eventos[0]["detalles_diff"]
    assert "+linea del atacante" in diff
    assert "1234" not in diff


def test_si_el_archivo_sigue_cambiando_queda_anotado_que_la_copia_no_coincide_con_el_hash(
        entorno_monitor, monkeypatch):
    ruta = entorno_monitor.crear_en_baseline("app.conf", b"estado cero\n")
    with open(ruta, "a") as f:
        f.write("primera parte\n")

    def registrar_y_seguir_escribiendo(*args, **kwargs):
        if args[3] == "MODIFICADO":
            with open(ruta, "a") as f:
                f.write("segunda parte\n")
        return entorno_monitor.registrar(*args, **kwargs)

    monkeypatch.setattr(monitor_fim, "log_to_db", registrar_y_seguir_escribiendo)
    entorno_monitor.evento_modificado(ruta)

    detectado, restaurado = entorno_monitor.eventos
    hash_copia = get_sha256(detectado["ruta_cuarentena"])
    assert hash_copia != detectado["hash_sha256"]
    assert hash_copia in restaurado["detalles_diff"]


def test_la_copia_a_cuarentena_conserva_permisos_y_fecha(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("script.sh", b"#!/bin/sh\n", modo=0o750)
    with open(ruta, "a") as f:
        f.write("echo cambio\n")
    os.utime(ruta, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))

    entorno_monitor.evento_modificado(ruta)

    copia = os.stat(entorno_monitor.eventos[0]["ruta_cuarentena"])
    assert copia.st_mode & 0o7777 == 0o750
    assert copia.st_mtime_ns == 1_700_000_000_000_000_000


# --- Permisos y propietario sin seguir enlaces ---

def modo(ruta):
    return os.stat(ruta).st_mode & 0o7777


def test_reponer_permisos_no_toca_el_destino_si_cambian_el_archivo_por_un_enlace(
        entorno_monitor, tmp_path, monkeypatch):
    ruta = entorno_monitor.crear_en_baseline("app.conf", b"estado cero\n", modo=0o644)
    victima = tmp_path / "victima.txt"
    victima.write_text("archivo de afuera\n")
    os.chmod(victima, 0o600)
    os.chmod(ruta, 0o777)

    # El cambio por un enlace ocurre después de verificar y antes de reponer los permisos
    def registrar_y_cambiar(*args, **kwargs):
        if args[3] == "PERMISOS":
            os.remove(ruta)
            os.symlink(victima, ruta)
        return entorno_monitor.registrar(*args, **kwargs)

    monkeypatch.setattr(monitor_fim, "log_to_db", registrar_y_cambiar)
    entorno_monitor.evento_modificado(ruta)

    assert modo(victima) == 0o600   # antes, chmod seguía el enlace y la dejaba en 644


def test_aceptar_un_cambio_de_permisos_no_toca_el_destino_de_un_enlace(entorno_monitor, tmp_path, monkeypatch):
    monkeypatch.setattr("config.MODO_RESTAURACION", "aprobacion")
    ruta = entorno_monitor.crear_en_baseline("app.conf", b"estado cero\n", modo=0o644)
    os.chmod(ruta, 0o777)
    entorno_monitor.evento_modificado(ruta)
    assert entorno_monitor.tipos_de_evento() == ["PERMISOS"]

    # Entre la alerta y el botón, el archivo se cambia por un enlace a otro
    victima = tmp_path / "victima.txt"
    victima.write_text("archivo de afuera\n")
    os.chmod(victima, 0o600)
    os.remove(ruta)
    os.symlink(victima, ruta)
    versiones = entorno_monitor.versiones

    assert monitor_fim.ejecutar_decision(entorno_monitor.decision(1, monitor_fim.ACEPTAR)) == "RECHAZADA"
    assert modo(victima) == 0o600
    assert entorno_monitor.versiones == versiones   # no se generó una baseline nueva


def test_aceptar_un_cambio_de_permisos_sigue_funcionando_con_un_archivo_comun(entorno_monitor, monkeypatch):
    monkeypatch.setattr("config.MODO_RESTAURACION", "aprobacion")
    ruta = entorno_monitor.crear_en_baseline("app.conf", b"estado cero\n", modo=0o644)
    os.chmod(ruta, 0o600)
    entorno_monitor.evento_modificado(ruta)
    os.chmod(ruta, 0o644)   # alguien lo volvió atrás a mano antes de la decisión

    assert monitor_fim.ejecutar_decision(entorno_monitor.decision(1, monitor_fim.ACEPTAR)) == "EJECUTADA"
    assert modo(ruta) == 0o600
    assert entorno_monitor.baseline[ruta]["permisos"] == "600"


# --- Enlace a un directorio ---

def test_un_enlace_a_un_directorio_se_registra_y_se_quita_en_tiempo_real(entorno_monitor, tmp_path):
    entorno_monitor.crear_en_baseline("app.conf", b"estado cero\n")
    afuera = tmp_path / "afuera"
    afuera.mkdir()
    (afuera / "x.txt").write_text("archivo de afuera\n")
    enlace = entorno_monitor.ruta("atajo")
    os.symlink(afuera, enlace)

    entorno_monitor.evento_creado(enlace)   # watchdog lo entrega como archivo creado, no como directorio

    assert entorno_monitor.tipos_de_evento() == ["CREADO"]
    assert not os.path.lexists(enlace)
    assert os.listdir(afuera) == ["x.txt"]


def test_el_escaneo_inicial_detecta_un_enlace_a_un_directorio(entorno_monitor, tmp_path):
    entorno_monitor.crear_en_baseline("app.conf", b"estado cero\n")
    afuera = tmp_path / "afuera"
    afuera.mkdir()
    (afuera / "x.txt").write_text("archivo de afuera\n")
    enlace = entorno_monitor.ruta("atajo")
    os.symlink(afuera, enlace)

    monitor_fim.escaneo_inicial()

    assert entorno_monitor.tipos_de_evento() == ["CREADO"]
    assert f"enlace simbólico → {afuera}" in entorno_monitor.eventos[0]["detalles_diff"]
    assert not os.path.lexists(enlace)
    assert os.listdir(afuera) == ["x.txt"]
