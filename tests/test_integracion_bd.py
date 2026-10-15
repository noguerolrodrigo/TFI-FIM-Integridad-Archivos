import os
import subprocess

import psycopg2
import pytest

import bd
import boveda
import config
import generar_baseline
import monitor_fim
from hashes import get_sha256

# Pruebas contra PostgreSQL real, en la base fim_pruebas (nunca en fim_db).
# Cada test parte de la base vacía con el esquema de las migraciones (scripts/preparar_bd_pruebas.sh).
# Se saltean si fim_pruebas no existe.

BASE_PRUEBAS = "fim_pruebas"
SCRIPT = os.path.join(config.RAIZ, "scripts", "preparar_bd_pruebas.sh")


@pytest.fixture
def bd_pruebas(monkeypatch):
    try:
        psycopg2.connect(host=config.DB_HOST, database=BASE_PRUEBAS, user=config.DB_USER,
                         password=config.DB_PASS).close()
    except psycopg2.Error as e:
        pytest.skip(f"No está la base {BASE_PRUEBAS}: {e}")
    subprocess.run([SCRIPT], check=True, capture_output=True)
    bd.cerrar()
    monkeypatch.setattr(config, "DB_NAME", BASE_PRUEBAS)
    monkeypatch.setattr(config, "N8N_WEBHOOK_URL", "")
    monitor_fim.avisados.clear()
    monitor_fim.decisiones_ejecutadas.clear()
    os.makedirs(config.RUTAS_MONITOREADAS[0])
    yield
    bd.cerrar()


def crear(nombre, contenido):
    ruta = os.path.join(config.RUTAS_MONITOREADAS[0], nombre)
    with open(ruta, "w") as f:
        f.write(contenido)
    return ruta


def vigente():
    return {ruta: (hash_, version) for ruta, hash_, version in
            bd.ejecutar("SELECT ruta_completa, hash_sha256, version_baseline FROM baseline_vigente")}


def test_la_baseline_de_un_solo_archivo_no_toca_los_demas(bd_pruebas):
    a = crear("a.conf", "a\n")
    b = crear("b.conf", "b\n")
    generar_baseline.generar_baseline()
    hash_b = vigente()[b][0]
    with open(a, "a") as f:
        f.write("cambio aceptado\n")

    version = generar_baseline.actualizar_archivo(a, "prueba")

    estado = vigente()
    assert version == 2
    assert estado[a] == (get_sha256(a), 2)
    assert estado[b] == (hash_b, 2)
    assert get_sha256(boveda.ruta_en_boveda(a)) == get_sha256(a)
    # La versión anterior queda como historial
    assert bd.ejecutar("SELECT count(*) FROM registros_archivos WHERE evento = 'BASELINE'")[0][0] == 4


def test_un_archivo_borrado_sale_de_la_baseline_y_de_la_boveda(bd_pruebas):
    a = crear("a.conf", "a\n")
    b = crear("b.conf", "b\n")
    generar_baseline.generar_baseline()
    os.remove(a)

    generar_baseline.actualizar_archivo(a, "prueba")

    assert set(vigente()) == {b}
    assert not boveda.tiene_respaldo(a)


def test_las_ventanas_vencidas_o_futuras_no_cuentan(bd_pruebas):
    bd.ejecutar("""INSERT INTO ventanas_mantenimiento (ruta, motivo, autorizado_por, desde, hasta) VALUES
        ('/vigente', 'm', 'r', now() - interval '1 min', now() + interval '10 min'),
        ('/vencida', 'm', 'r', now() - interval '20 min', now() - interval '10 min'),
        ('/futura',  'm', 'r', now() + interval '10 min', now() + interval '20 min')""")

    assert [ruta for _, ruta in monitor_fim.ventanas_vigentes()] == ["/vigente"]


def test_de_punta_a_punta_modificacion_decision_y_ejecucion(bd_pruebas):
    ruta = crear("config.conf", "estado cero\n")
    generar_baseline.generar_baseline()
    with open(ruta, "a") as f:
        f.write("cambio del administrador\n")
    hash_aceptado = get_sha256(ruta)

    # 1. El monitor detecta, registra y restaura
    assert monitor_fim.procesar(ruta) == "RESTAURADO"
    (evento_id, hash_anterior, cuarentena), = bd.ejecutar(
        "SELECT id, hash_anterior, ruta_cuarentena FROM registros_archivos WHERE evento = 'MODIFICADO'")
    assert hash_anterior == vigente()[ruta][0]
    assert get_sha256(cuarentena) == hash_aceptado

    # 2. n8n inserta la decisión (acá la insertamos a mano)
    bd.ejecutar("INSERT INTO decisiones (evento_id, decision, decidido_por, canal) "
                "VALUES (%s, 'AUTORIZADO', 'rodrigo', 'prueba')", (evento_id,))
    pendiente, = monitor_fim.decisiones_pendientes()
    assert pendiente["evento_id"] == evento_id and pendiente["ruta"] == ruta

    # 3. El monitor la ejecuta y lo deja registrado
    assert monitor_fim.ejecutar_decision(pendiente) == "EJECUTADA"
    assert get_sha256(ruta) == hash_aceptado
    assert vigente()[ruta][0] == hash_aceptado
    (resultado,), = bd.ejecutar("SELECT resultado FROM ejecuciones")
    assert resultado == "EJECUTADA"
    assert monitor_fim.decisiones_pendientes() == []


def test_la_bd_rechaza_una_segunda_decision_sobre_el_mismo_evento(bd_pruebas):
    ruta = crear("config.conf", "estado cero\n")
    generar_baseline.generar_baseline()
    with open(ruta, "a") as f:
        f.write("intruso\n")
    monitor_fim.procesar(ruta)
    (evento_id,), = bd.ejecutar("SELECT id FROM registros_archivos WHERE evento = 'MODIFICADO'")
    bd.ejecutar("INSERT INTO decisiones (evento_id, decision, decidido_por, canal) "
                "VALUES (%s, 'INCIDENTE', 'rodrigo', 'link_local')", (evento_id,))

    with pytest.raises(psycopg2.errors.UniqueViolation):
        bd.ejecutar("INSERT INTO decisiones (evento_id, decision, decidido_por, canal) "
                    "VALUES (%s, 'AUTORIZADO', 'otro', 'telegram')", (evento_id,))
