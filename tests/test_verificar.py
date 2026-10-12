import boveda
import monitor_fim
from hashes import get_sha256

HASH_A = "a" * 64
HASH_B = "b" * 64


def test_sin_cambios_si_el_hash_coincide_con_la_baseline(monkeypatch):
    monkeypatch.setattr(monitor_fim, "obtener_baseline", lambda ruta: HASH_A)

    assert monitor_fim.verificar("./x.txt", HASH_A) == (monitor_fim.SIN_CAMBIOS, HASH_A)


def test_modificado_si_el_hash_no_coincide(monkeypatch):
    monkeypatch.setattr(monitor_fim, "obtener_baseline", lambda ruta: HASH_A)

    assert monitor_fim.verificar("./x.txt", HASH_B) == (monitor_fim.MODIFICADO, HASH_A)


def test_fuera_de_baseline_si_el_archivo_no_figura(monkeypatch):
    monkeypatch.setattr(monitor_fim, "obtener_baseline", lambda ruta: None)

    assert monitor_fim.verificar("./nuevo.txt", HASH_B) == (monitor_fim.FUERA_DE_BASELINE, None)


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
