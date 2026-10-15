#!/usr/bin/env bash
#
# Deja la base fim_pruebas vacía y con el mismo esquema que fim_db, para pruebas de punta a punta.
# Uso: ./scripts/preparar_bd_pruebas.sh
#
# fim_pruebas es de fim_user (se creó con: sudo -u postgres createdb -O fim_user fim_pruebas), así que
# acá sí puede crear y borrar tablas. Se aplican las migraciones 01 a 04 y las tablas de la 06; la 05
# (dueños y permisos) y el rol fim_n8n son propios de fim_db y no hacen falta para probar.
#
set -euo pipefail

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_PRUEBAS="${BASE_PRUEBAS:-fim_pruebas}"

leer_env() {
    grep -E "^$1=" "$PROYECTO/.env" | tail -n 1 | cut -d= -f2- | tr -d '\r'
}
export PGPASSWORD="$(leer_env DB_PASS)"
PSQL=(psql -q -X -v ON_ERROR_STOP=1 -h "$(leer_env DB_HOST)" -U "$(leer_env DB_USER)" -d "$BASE_PRUEBAS")

{
    echo "SET client_min_messages = warning;"
    echo "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
    cat "$PROYECTO/sql/01_schema.sql"
    echo "SELECT pg_catalog.set_config('search_path', 'public', false);"
    cat "$PROYECTO/sql/02_baseline_versionada.sql" \
        "$PROYECTO/sql/03_fecha_con_zona.sql" \
        "$PROYECTO/sql/04_evidencia.sql"
    # De la 06 solo las tablas: el rol y los permisos son de fim_db
    sed '/^-- Rol de n8n/,$d' "$PROYECTO/sql/06_orquestacion.sql"
    echo "COMMIT;"
} | "${PSQL[@]}" > /dev/null

echo "[*] $BASE_PRUEBAS lista: esquema de fim_db, sin datos."
