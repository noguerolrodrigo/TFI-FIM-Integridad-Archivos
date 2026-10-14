import psycopg2
import pytest

import bd

# Comprueban los permisos de la migración 06 consultando el catálogo desde fim_user.
# No modifican nada y se saltean mientras la migración no esté aplicada.

TABLAS_NUEVAS = ["notificaciones", "decisiones", "ejecuciones", "ventanas_mantenimiento", "accesos_rechazados"]


@pytest.fixture
def migracion_06_aplicada():
    try:
        (existe,), = bd.ejecutar("SELECT to_regclass('public.decisiones') IS NOT NULL")
    except psycopg2.Error as e:
        pytest.skip(f"PostgreSQL no disponible: {e}")
    if not existe:
        pytest.skip("Falta aplicar sql/06_orquestacion.sql")
    yield
    bd.cerrar()


def permiso(rol, tabla, privilegio):
    return bd.ejecutar("SELECT has_table_privilege(%s, %s, %s)", (rol, f"public.{tabla}", privilegio))[0][0]


@pytest.mark.parametrize("tabla", ["notificaciones", "decisiones", "ventanas_mantenimiento", "accesos_rechazados"])
def test_n8n_puede_agregar_en_sus_tablas(migracion_06_aplicada, tabla):
    assert permiso("fim_n8n", tabla, "INSERT")


@pytest.mark.parametrize("tabla", TABLAS_NUEVAS + ["registros_archivos"])
@pytest.mark.parametrize("privilegio", ["UPDATE", "DELETE", "TRUNCATE"])
def test_n8n_no_puede_modificar_ni_borrar(migracion_06_aplicada, tabla, privilegio):
    assert not permiso("fim_n8n", tabla, privilegio)


@pytest.mark.parametrize("tabla", ["registros_archivos", "ejecuciones"])
def test_n8n_no_escribe_lo_que_registra_el_monitor(migracion_06_aplicada, tabla):
    assert not permiso("fim_n8n", tabla, "INSERT")


def test_el_monitor_lee_decisiones_y_registra_ejecuciones(migracion_06_aplicada):
    assert permiso("fim_user", "decisiones", "SELECT")
    assert permiso("fim_user", "ventanas_mantenimiento", "SELECT")
    assert permiso("fim_user", "ejecuciones", "INSERT")
    assert not permiso("fim_user", "decisiones", "INSERT")


def test_una_sola_decision_por_evento(migracion_06_aplicada):
    (es_unica,), = bd.ejecutar("""
        SELECT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'public.decisiones'::regclass AND contype = 'u'
              AND conkey = ARRAY[(SELECT attnum FROM pg_attribute
                                  WHERE attrelid = 'public.decisiones'::regclass AND attname = 'evento_id')]
        )""")
    assert es_unica
