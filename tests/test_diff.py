import monitor_fim


def test_el_diff_muestra_la_linea_agregada(tmp_path):
    antes = tmp_path / "antes.txt"
    ahora = tmp_path / "ahora.txt"
    antes.write_text("linea1\nlinea2\n")
    ahora.write_text("linea1\nlinea2\nintruso\n")

    diff = monitor_fim.calcular_diff(str(antes), str(ahora))

    assert diff.startswith("--- Antes\n+++ Ahora\n")
    assert "+intruso\n" in diff
    assert "-linea" not in diff


def test_archivos_iguales_dan_diff_vacio(tmp_path):
    antes = tmp_path / "antes.txt"
    ahora = tmp_path / "ahora.txt"
    antes.write_text("linea1\n")
    ahora.write_text("linea1\n")

    assert monitor_fim.calcular_diff(str(antes), str(ahora)) == ""


def test_un_binario_no_genera_diff_de_texto(tmp_path):
    antes = tmp_path / "antes.bin"
    ahora = tmp_path / "ahora.bin"
    antes.write_bytes(bytes(range(256)))
    ahora.write_bytes(bytes(range(256)) + b"\x00\xff")

    diff = monitor_fim.calcular_diff(str(antes), str(ahora))

    assert diff.startswith("Archivo binario")
