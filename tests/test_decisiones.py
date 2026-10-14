import os
import stat
import threading
import time

import pytest

import boveda
import config
import monitor_fim
from hashes import get_sha256


def modo(ruta):
    return stat.S_IMODE(os.stat(ruta).st_mode)


def alterar(ruta, texto="cambio\n"):
    with open(ruta, "a") as f:
        f.write(texto)
    return get_sha256(ruta)


def evento_id(entorno, tipo):
    return next(e["id"] for e in entorno.eventos if e["evento"] == tipo)


# --- Modo automático: el monitor ya restauró y la persona decide después ---

def test_incidente_cierra_sin_tocar_el_archivo(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    alterar(ruta)
    entorno_monitor.evento_modificado(ruta)
    d = entorno_monitor.decision(evento_id(entorno_monitor, "MODIFICADO"), "INCIDENTE")

    assert monitor_fim.ejecutar_decision(d) == "EJECUTADA"

    assert get_sha256(ruta) == entorno_monitor.hash_baseline(ruta)
    assert entorno_monitor.versiones == 0
    assert entorno_monitor.ejecuciones[0][:2] == (1, "EJECUTADA")


def test_autorizado_reaplica_la_version_de_cuarentena_y_actualiza_solo_ese_archivo(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    otro = entorno_monitor.crear_en_baseline("otro.txt", b"otro\n")
    hash_otro = entorno_monitor.hash_baseline(otro)
    hash_aceptado = alterar(ruta, "cambio del administrador\n")
    entorno_monitor.evento_modificado(ruta)
    assert get_sha256(ruta) == entorno_monitor.hash_baseline(ruta) != hash_aceptado   # ya se restauró
    d = entorno_monitor.decision(evento_id(entorno_monitor, "MODIFICADO"), "AUTORIZADO")

    assert monitor_fim.ejecutar_decision(d) == "EJECUTADA"

    assert get_sha256(ruta) == hash_aceptado
    assert entorno_monitor.hash_baseline(ruta) == hash_aceptado
    assert get_sha256(boveda.ruta_en_boveda(ruta)) == hash_aceptado
    assert entorno_monitor.hash_baseline(otro) == hash_otro
    assert "Baseline versión 1" in entorno_monitor.ejecuciones[0][2]


def test_despues_de_aceptar_el_archivo_queda_protegido_con_la_version_nueva(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    hash_aceptado = alterar(ruta)
    entorno_monitor.evento_modificado(ruta)
    monitor_fim.ejecutar_decision(entorno_monitor.decision(evento_id(entorno_monitor, "MODIFICADO"), "AUTORIZADO"))
    entorno_monitor.evento_modificado(ruta)   # el evento que genera la propia reaplicación
    cantidad = len(entorno_monitor.eventos)
    alterar(ruta, "otro intruso\n")

    entorno_monitor.evento_modificado(ruta)

    assert get_sha256(ruta) == hash_aceptado
    assert entorno_monitor.tipos_de_evento()[cantidad:] == ["MODIFICADO", "RESTAURADO"]


def test_archivo_nuevo_autorizado_vuelve_de_cuarentena_y_entra_en_la_baseline(entorno_monitor):
    entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    nuevo = entorno_monitor.ruta("nuevo.conf")
    with open(nuevo, "w") as f:
        f.write("configuración nueva\n")
    hash_nuevo = get_sha256(nuevo)
    entorno_monitor.evento_creado(nuevo)
    assert not os.path.exists(nuevo)

    monitor_fim.ejecutar_decision(entorno_monitor.decision(evento_id(entorno_monitor, "CREADO"), "AUTORIZADO"))

    assert get_sha256(nuevo) == hash_nuevo
    assert entorno_monitor.hash_baseline(nuevo) == hash_nuevo


def test_archivo_nuevo_incidente_queda_en_cuarentena(entorno_monitor):
    entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    nuevo = entorno_monitor.ruta("backdoor.sh")
    with open(nuevo, "w") as f:
        f.write("#!/bin/sh\n")
    entorno_monitor.evento_creado(nuevo)

    monitor_fim.ejecutar_decision(entorno_monitor.decision(evento_id(entorno_monitor, "CREADO"), "INCIDENTE"))

    assert not os.path.exists(nuevo)
    assert nuevo not in entorno_monitor.baseline


def test_borrado_autorizado_vuelve_a_borrar_y_sale_de_la_baseline(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("viejo.conf", b"ya no se usa\n")
    os.remove(ruta)
    entorno_monitor.evento_eliminado(ruta)
    assert os.path.exists(ruta)   # el monitor lo restauró

    monitor_fim.ejecutar_decision(entorno_monitor.decision(evento_id(entorno_monitor, "ELIMINADO"), "AUTORIZADO"))

    assert not os.path.exists(ruta)
    assert ruta not in entorno_monitor.baseline
    assert not boveda.tiene_respaldo(ruta)


def test_permisos_autorizados_se_reaplican_y_pasan_a_la_baseline(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("script.sh", b"#!/bin/sh\n", modo=0o644)
    os.chmod(ruta, 0o755)
    entorno_monitor.evento_modificado(ruta)
    assert modo(ruta) == 0o644   # el monitor lo repuso

    monitor_fim.ejecutar_decision(entorno_monitor.decision(evento_id(entorno_monitor, "PERMISOS"), "AUTORIZADO"))

    assert modo(ruta) == 0o755
    assert entorno_monitor.baseline[ruta]["permisos"] == "755"


# --- Modo aprobación: el archivo quedó alterado esperando la decisión ---

@pytest.fixture
def modo_aprobacion(monkeypatch):
    monkeypatch.setattr(config, "MODO_RESTAURACION", "aprobacion")


def test_restaurar_desde_telegram_deja_constancia_de_quien_aprobo(entorno_monitor, modo_aprobacion):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    alterar(ruta)
    entorno_monitor.evento_modificado(ruta)
    d = entorno_monitor.decision(evento_id(entorno_monitor, "MODIFICADO"), "RESTAURAR",
                                 decidido_por="rodrigo", canal="telegram")

    assert monitor_fim.ejecutar_decision(d) == "EJECUTADA"

    assert get_sha256(ruta) == entorno_monitor.hash_baseline(ruta)
    restaurado = entorno_monitor.eventos[-1]
    assert restaurado["evento"] == "RESTAURADO"
    assert "aprobación de rodrigo (telegram)" in restaurado["detalles_diff"]


def test_aceptar_cambio_deja_el_archivo_y_actualiza_la_baseline(entorno_monitor, modo_aprobacion):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    hash_aceptado = alterar(ruta)
    entorno_monitor.evento_modificado(ruta)

    monitor_fim.ejecutar_decision(entorno_monitor.decision(evento_id(entorno_monitor, "MODIFICADO"), "ACEPTAR"))

    assert get_sha256(ruta) == hash_aceptado
    assert entorno_monitor.hash_baseline(ruta) == hash_aceptado


# --- Validaciones ---

def test_no_acepta_si_la_copia_de_cuarentena_fue_alterada(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    alterar(ruta)
    entorno_monitor.evento_modificado(ruta)
    d = entorno_monitor.decision(evento_id(entorno_monitor, "MODIFICADO"), "AUTORIZADO")
    with open(d["ruta_cuarentena"], "a") as f:
        f.write("algo que no se mostró en la alerta\n")

    assert monitor_fim.ejecutar_decision(d) == "RECHAZADA"

    assert get_sha256(ruta) == entorno_monitor.hash_baseline(ruta)
    assert entorno_monitor.versiones == 0


def test_rechaza_una_ruta_fuera_de_las_monitoreadas(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    alterar(ruta)
    entorno_monitor.evento_modificado(ruta)
    d = entorno_monitor.decision(evento_id(entorno_monitor, "MODIFICADO"), "AUTORIZADO")
    d["ruta"] = "/etc/passwd"

    assert monitor_fim.ejecutar_decision(d) == "RECHAZADA"
    assert entorno_monitor.versiones == 0


def test_rechaza_decidir_sobre_un_evento_que_no_es_un_cambio(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    alterar(ruta)
    entorno_monitor.evento_modificado(ruta)
    d = entorno_monitor.decision(evento_id(entorno_monitor, "RESTAURADO"), "AUTORIZADO")

    assert monitor_fim.ejecutar_decision(d) == "RECHAZADA"


def test_avisa_a_n8n_el_resultado_de_la_ejecucion(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    alterar(ruta)
    entorno_monitor.evento_modificado(ruta)
    eid = evento_id(entorno_monitor, "MODIFICADO")

    monitor_fim.ejecutar_decision(entorno_monitor.decision(eid, "INCIDENTE", decision_id=9))

    assert entorno_monitor.avisos[-1] == {"tipo": "ejecucion", "decision_id": 9, "evento_id": eid,
                                          "resultado": "EJECUTADA"}


def test_el_hilo_no_ejecuta_dos_veces_la_misma_decision(entorno_monitor, monkeypatch):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    alterar(ruta)
    entorno_monitor.evento_modificado(ruta)
    d = entorno_monitor.decision(evento_id(entorno_monitor, "MODIFICADO"), "AUTORIZADO")
    # La BD sigue devolviendo la decisión como pendiente (por ejemplo, si no se pudo registrar la ejecución)
    monkeypatch.setattr(monitor_fim, "decisiones_pendientes", lambda: [dict(d)])
    monkeypatch.setattr(monitor_fim, "INTERVALO_DECISIONES", 0.01)

    detener = threading.Event()
    hilo = threading.Thread(target=monitor_fim.vigilar_decisiones, args=(detener,))
    hilo.start()
    time.sleep(0.2)
    detener.set()
    hilo.join(2)

    assert entorno_monitor.versiones == 1
    assert len(entorno_monitor.ejecuciones) == 1
