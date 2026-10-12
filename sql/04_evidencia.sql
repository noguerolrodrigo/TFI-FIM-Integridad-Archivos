--
-- 04: Evidencia completa en cada evento
--
-- hash_anterior:   el hash que tenía el archivo en la baseline vigente (el
--                  "antes"); hash_sha256 sigue siendo el hash detectado.
-- ruta_cuarentena: dónde quedó guardada la copia del archivo alterado.
--
-- Aplicar con:
--   psql -v ON_ERROR_STOP=1 -h localhost -U fim_user -d fim_db -f sql/04_evidencia.sql
--

BEGIN;

ALTER TABLE public.registros_archivos
    ADD COLUMN hash_anterior character varying(64),
    ADD COLUMN ruta_cuarentena text;

COMMIT;
