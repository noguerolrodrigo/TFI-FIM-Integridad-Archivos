import os

import config


def test_una_ruta_relativa_se_resuelve_desde_la_carpeta_del_proyecto():
    assert config.ruta_absoluta("./directorio_prueba") == os.path.join(config.RAIZ, "directorio_prueba")


def test_una_ruta_absoluta_queda_igual():
    assert config.ruta_absoluta("/etc") == "/etc"


def test_varias_rutas_separadas_por_dos_puntos():
    assert config.leer_rutas("/etc: /usr/bin :") == ["/etc", "/usr/bin"]


def test_patrones_separados_por_coma():
    assert config.leer_patrones("*.swp, *~ ,") == ["*.swp", "*~"]


def test_dentro_de_no_confunde_nombres_parecidos():
    assert config.dentro_de("/etc/ssh/sshd_config", "/etc")
    assert config.dentro_de("/etc", "/etc")
    assert not config.dentro_de("/etcetera/x", "/etc")
