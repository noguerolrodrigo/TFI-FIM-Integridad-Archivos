import psycopg2
import pytest

import bd


@pytest.fixture
def base_disponible():
    """Estos tests necesitan PostgreSQL levantado; si no lo está, se saltean. Solo hacen SELECT."""
    try:
        bd.ejecutar("SELECT 1")
    except psycopg2.Error as e:
        pytest.skip(f"PostgreSQL no disponible: {e}")
    yield
    bd.cerrar()


def pid_del_servidor():
    return bd.ejecutar("SELECT pg_backend_pid()")[0][0]


def test_reutiliza_la_misma_conexion(base_disponible):
    assert pid_del_servidor() == pid_del_servidor()


def test_reconecta_si_la_conexion_se_cae(base_disponible):
    pid_original = pid_del_servidor()

    # Se corta la conexión desde otra sesión, como si se reiniciara el servidor
    otra = psycopg2.connect(host=bd.DB_HOST, database=bd.DB_NAME, user=bd.DB_USER, password=bd.DB_PASS)
    with otra.cursor() as cursor:
        cursor.execute("SELECT pg_terminate_backend(%s)", (pid_original,))
    otra.close()

    assert pid_del_servidor() != pid_original


def test_un_error_de_consulta_no_rompe_la_conexion(base_disponible):
    with pytest.raises(psycopg2.Error):
        bd.ejecutar("SELECT * FROM tabla_que_no_existe")

    assert bd.ejecutar("SELECT 1") == [(1,)]
