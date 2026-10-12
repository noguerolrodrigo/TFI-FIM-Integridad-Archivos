import boveda
import monitor_fim
from hashes import get_sha256

HASH_A = "a" * 64
HASH_B = "b" * 64
BASELINE = {"hash": HASH_A, "permisos": "644", "owner": "1000"}


def con_baseline(monkeypatch, baseline):
    monkeypatch.setattr(monitor_fim, "obtener_baseline", lambda ruta: baseline)


def test_sin_cambios_si_todo_coincide_con_la_baseline(monkeypatch):
    con_baseline(monkeypatch, BASELINE)

    assert monitor_fim.verificar("./x.txt", HASH_A, "1000", "644") == (monitor_fim.SIN_CAMBIOS, BASELINE)


def test_modificado_si_el_hash_no_coincide(monkeypatch):
    con_baseline(monkeypatch, BASELINE)

    assert monitor_fim.verificar("./x.txt", HASH_B, "1000", "644") == (monitor_fim.MODIFICADO, BASELINE)


def test_modificado_tiene_prioridad_sobre_permisos(monkeypatch):
    con_baseline(monkeypatch, BASELINE)

    assert monitor_fim.verificar("./x.txt", HASH_B, "1000", "777")[0] == monitor_fim.MODIFICADO


def test_permisos_si_cambio_el_modo_con_el_mismo_contenido(monkeypatch):
    con_baseline(monkeypatch, BASELINE)

    assert monitor_fim.verificar("./x.txt", HASH_A, "1000", "777") == (monitor_fim.PERMISOS, BASELINE)


def test_permisos_si_cambio_el_propietario(monkeypatch):
    con_baseline(monkeypatch, BASELINE)

    assert monitor_fim.verificar("./x.txt", HASH_A, "0", "644") == (monitor_fim.PERMISOS, BASELINE)


def test_creado_si_el_archivo_no_figura_en_la_baseline(monkeypatch):
    con_baseline(monkeypatch, None)

    assert monitor_fim.verificar("./nuevo.txt", HASH_B, "1000", "644") == (monitor_fim.CREADO, None)


def test_eliminado_si_figura_en_la_baseline_y_no_esta_en_disco(monkeypatch):
    con_baseline(monkeypatch, BASELINE)

    assert monitor_fim.verificar("./x.txt", None, "N/A", "N/A") == (monitor_fim.ELIMINADO, BASELINE)


def test_sin_cambios_si_no_esta_en_la_baseline_ni_en_disco(monkeypatch):
    con_baseline(monkeypatch, None)

    assert monitor_fim.verificar("./x.txt", None, "N/A", "N/A") == (monitor_fim.SIN_CAMBIOS, None)


def test_el_respaldo_es_confiable_si_coincide_con_la_baseline(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    archivo = tmp_path / "config.txt"
    archivo.write_text("estado cero\n")
    hash_baseline = get_sha256(str(archivo))
    boveda.respaldar(str(archivo))

    assert monitor_fim.respaldo_confiable(str(archivo), hash_baseline)


def test_el_respaldo_alterado_no_es_confiable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    archivo = tmp_path / "config.txt"
    archivo.write_text("estado cero\n")
    hash_baseline = get_sha256(str(archivo))
    respaldo = boveda.respaldar(str(archivo))

    with open(respaldo, "w") as f:
        f.write("respaldo envenenado\n")

    assert not monitor_fim.respaldo_confiable(str(archivo), hash_baseline)


def test_sin_respaldo_no_es_confiable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert not monitor_fim.respaldo_confiable(str(tmp_path / "config.txt"), HASH_A)
