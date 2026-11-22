import os
import stat

import pytest

import boveda
import config
import monitor_fim
import restaurar
from hashes import get_sha256

# Hallazgo n1 de la segunda instancia: la restauración crea un archivo nuevo (un temporal que se
# renombra encima del original) y ese archivo nace con el dueño del proceso. Si el archivo de la
# baseline era de otro usuario, hay que reponerle el dueño antes del renombrado.

# Un uid cualquiera que no es el del proceso que corre los tests
OTRO_UID = 12345 if os.geteuid() != 12345 else 12346


class FchownSimulado:
    """Hace de os.fchown: anota los pedidos sin cambiar nada (o falla como a un usuario común)."""

    def __init__(self, permitido=True):
        self.permitido = permitido
        self.pedidos = []   # (inodo del archivo abierto, uid, gid)

    def __call__(self, descriptor, uid, gid):
        self.pedidos.append((os.fstat(descriptor).st_ino, uid, gid))
        if not self.permitido:
            raise PermissionError(1, "Operation not permitted")


@pytest.fixture
def fchown(monkeypatch):
    simulado = FchownSimulado()
    monkeypatch.setattr(os, "fchown", simulado)
    return simulado


@pytest.fixture
def fchown_sin_permiso(monkeypatch):
    simulado = FchownSimulado(permitido=False)
    monkeypatch.setattr(os, "fchown", simulado)
    return simulado


@pytest.fixture
def entorno(tmp_path):
    """Un directorio vigilado y una bóveda, los dos vacíos y temporales."""
    vigilado = tmp_path / "vigilado"
    vigilado.mkdir()
    return vigilado, str(tmp_path / "boveda")


def alterar(ruta):
    with open(ruta, "a") as f:
        f.write("intruso\n")
    return get_sha256(ruta)


# --- La función de la bóveda ---

# La prueba del tribunal: archivo de la baseline de otro usuario, restaurar y mirar el dueño.
# Cambiar el dueño de un archivo de verdad solo lo puede hacer root.
@pytest.mark.skipif(os.geteuid() != 0, reason="cambiar el dueño de un archivo de verdad requiere root")
def test_como_root_el_archivo_restaurado_queda_con_el_propietario_de_la_baseline(entorno):
    vigilado, dir_boveda = entorno
    archivo = vigilado / "programa"
    archivo.write_text("#!/bin/sh\necho hola\n")
    os.chown(archivo, OTRO_UID, -1)
    os.chmod(archivo, 0o4755)   # con setuid: cambiar el dueño lo borra, así que tiene que reponerse después
    boveda.respaldar(str(archivo), dir_boveda)

    archivo.write_text("#!/bin/sh\nrm -rf /\n")
    os.chown(archivo, 0, -1)
    repuesto = boveda.restaurar(str(archivo), dir_boveda, owner=str(OTRO_UID))

    assert repuesto
    assert archivo.read_text() == "#!/bin/sh\necho hola\n"
    assert os.stat(archivo).st_uid == OTRO_UID
    assert stat.S_IMODE(os.stat(archivo).st_mode) == 0o4755


def test_la_restauracion_pide_el_propietario_de_la_baseline_sobre_el_temporal(entorno, fchown):
    vigilado, dir_boveda = entorno
    archivo = vigilado / "config.txt"
    archivo.write_text("estado cero\n")
    boveda.respaldar(str(archivo), dir_boveda)
    archivo.write_text("estado cero\nlinea del atacante\n")

    repuesto = boveda.restaurar(str(archivo), dir_boveda, owner=str(OTRO_UID))

    assert repuesto
    assert archivo.read_text() == "estado cero\n"
    # Un solo pedido, sobre el archivo que terminó en la ruta (el temporal antes del renombrado),
    # con el uid de la baseline y sin tocar el grupo (la baseline no lo registra)
    assert fchown.pedidos == [(os.stat(archivo).st_ino, OTRO_UID, -1)]


def test_sin_permiso_para_cambiar_el_propietario_igual_se_restaura_y_se_avisa(entorno, fchown_sin_permiso):
    vigilado, dir_boveda = entorno
    archivo = vigilado / "config.txt"
    archivo.write_text("estado cero\n")
    os.chmod(archivo, 0o640)
    boveda.respaldar(str(archivo), dir_boveda)
    archivo.write_text("estado cero\nlinea del atacante\n")

    repuesto = boveda.restaurar(str(archivo), dir_boveda, owner=str(OTRO_UID))

    assert not repuesto
    assert archivo.read_text() == "estado cero\n"
    assert stat.S_IMODE(os.stat(archivo).st_mode) == 0o640
    assert os.listdir(vigilado) == ["config.txt"]
    assert len(fchown_sin_permiso.pedidos) == 1


def test_si_el_propietario_ya_es_el_de_la_baseline_no_se_pide_nada(entorno, fchown):
    vigilado, dir_boveda = entorno
    archivo = vigilado / "config.txt"
    archivo.write_text("estado cero\n")
    boveda.respaldar(str(archivo), dir_boveda)
    archivo.write_text("otra cosa\n")

    assert boveda.restaurar(str(archivo), dir_boveda, owner=str(os.geteuid()))
    assert boveda.restaurar(str(archivo), dir_boveda, owner="N/A")
    assert boveda.restaurar(str(archivo), dir_boveda)

    assert fchown.pedidos == []


# --- Los tres caminos que usan esa función: el monitor, restaurar.py y aceptar un cambio ---

def test_el_monitor_restaura_con_el_propietario_de_la_baseline(entorno_monitor, fchown):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    entorno_monitor.baseline[ruta]["owner"] = str(OTRO_UID)
    alterar(ruta)

    entorno_monitor.evento_modificado(ruta)

    assert get_sha256(ruta) == entorno_monitor.hash_baseline(ruta)
    assert entorno_monitor.tipos_de_evento() == ["MODIFICADO", "RESTAURADO"]
    assert fchown.pedidos == [(os.stat(ruta).st_ino, OTRO_UID, -1)]
    assert "propietario" not in entorno_monitor.eventos[1]["detalles_diff"]


def test_el_monitor_restaura_un_archivo_borrado_con_el_propietario_de_la_baseline(entorno_monitor, fchown):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    entorno_monitor.baseline[ruta]["owner"] = str(OTRO_UID)
    os.remove(ruta)

    entorno_monitor.evento_eliminado(ruta)

    assert entorno_monitor.tipos_de_evento() == ["ELIMINADO", "RESTAURADO"]
    assert fchown.pedidos == [(os.stat(ruta).st_ino, OTRO_UID, -1)]


def test_el_monitor_sin_permiso_restaura_el_contenido_y_anota_que_falta_el_propietario(
        entorno_monitor, fchown_sin_permiso):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    entorno_monitor.baseline[ruta]["owner"] = str(OTRO_UID)
    alterar(ruta)

    entorno_monitor.evento_modificado(ruta)

    assert get_sha256(ruta) == entorno_monitor.hash_baseline(ruta)
    assert entorno_monitor.tipos_de_evento() == ["MODIFICADO", "RESTAURADO"]
    assert f"No se pudo reponer el propietario (uid {OTRO_UID})" in entorno_monitor.eventos[1]["detalles_diff"]


def test_restaurar_py_tambien_repone_el_propietario(entorno_monitor, fchown, monkeypatch):
    monkeypatch.setattr(config, "MODO_RESTAURACION", "aprobacion")
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    entorno_monitor.baseline[ruta]["owner"] = str(OTRO_UID)
    alterar(ruta)
    entorno_monitor.evento_modificado(ruta)
    assert fchown.pedidos == []   # en modo aprobación todavía no se restauró

    assert restaurar.restaurar(ruta) == 0

    assert get_sha256(ruta) == entorno_monitor.hash_baseline(ruta)
    assert fchown.pedidos == [(os.stat(ruta).st_ino, OTRO_UID, -1)]


def test_aceptar_un_cambio_reaplica_la_version_con_el_propietario_que_tenia(entorno_monitor, fchown):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    hash_aceptado = alterar(ruta)
    entorno_monitor.evento_modificado(ruta)
    d = entorno_monitor.decision(1, "ACEPTAR")
    d["owner"] = str(OTRO_UID)   # el archivo alterado que vio la persona era de otro usuario

    assert monitor_fim.ejecutar_decision(d) == "EJECUTADA"

    assert get_sha256(ruta) == hash_aceptado
    assert fchown.pedidos == [(os.stat(ruta).st_ino, OTRO_UID, -1)]
    assert "propietario" not in entorno_monitor.ejecuciones[0][2]


def test_aceptar_un_cambio_sin_permiso_lo_aplica_y_anota_que_falta_el_propietario(
        entorno_monitor, fchown_sin_permiso):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    hash_aceptado = alterar(ruta)
    entorno_monitor.evento_modificado(ruta)
    d = entorno_monitor.decision(1, "ACEPTAR")
    d["owner"] = str(OTRO_UID)

    assert monitor_fim.ejecutar_decision(d) == "EJECUTADA"

    assert get_sha256(ruta) == hash_aceptado
    assert f"No se pudo reponer el propietario (uid {OTRO_UID})" in entorno_monitor.ejecuciones[0][2]
