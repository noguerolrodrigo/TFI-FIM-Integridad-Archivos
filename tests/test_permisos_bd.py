import psycopg2
import pytest

import bd

# Comprueban que la cuenta del agente no puede alterar el historial (migración 05).
# No modifican nada: consultan permisos, y los UPDATE/DELETE de prueba llevan WHERE false.


@pytest.fixture
def migracion_05_aplicada():
    try:
        (es_duenio,), = bd.ejecutar(
            "SELECT pg_get_userbyid(relowner) = current_user FROM pg_class "
            "WHERE oid = 'public.registros_archivos'::regclass")
    except psycopg2.Error as e:
        pytest.skip(f"PostgreSQL no disponible: {e}")
    if es_duenio:
        pytest.skip("Falta aplicar sql/05_permisos_minimos.sql (el usuario todavía es dueño de la tabla)")
    yield
    bd.cerrar()


def tiene_permiso(permiso):
    return bd.ejecutar("SELECT has_table_privilege('public.registros_archivos', %s)", (permiso,))[0][0]


def test_puede_leer_y_agregar(migracion_05_aplicada):
    assert tiene_permiso("SELECT")
    assert tiene_permiso("INSERT")
    assert bd.ejecutar("SELECT has_table_privilege('public.baseline_vigente', 'SELECT')")[0][0]
    assert bd.ejecutar("SELECT has_sequence_privilege('public.registros_archivos_id_seq', 'USAGE')")[0][0]


@pytest.mark.parametrize("permiso", ["UPDATE", "DELETE", "TRUNCATE"])
def test_no_tiene_permisos_para_alterar_el_historial(migracion_05_aplicada, permiso):
    assert not tiene_permiso(permiso)


@pytest.mark.parametrize("consulta", [
    "UPDATE registros_archivos SET notificado = notificado WHERE false",
    "DELETE FROM registros_archivos WHERE false",
])
def test_postgres_rechaza_modificar_o_borrar(migracion_05_aplicada, consulta):
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        bd.ejecutar(consulta)


def test_no_es_duenio_de_la_base_ni_puede_crear_objetos(migracion_05_aplicada):
    # El dueño de la base es dueño del esquema public y podría borrar la tabla
    (es_duenio_de_la_base,), = bd.ejecutar(
        "SELECT pg_get_userbyid(datdba) = current_user FROM pg_database WHERE datname = current_database()")
    assert not es_duenio_de_la_base
    assert not bd.ejecutar("SELECT has_schema_privilege('public', 'CREATE')")[0][0]
