--
-- 02: Baseline versionada (una sola baseline vigente por archivo)
--
-- Cada corrida de generar_baseline.py inserta sus filas BASELINE con un número
-- de versión nuevo. La baseline vigente es la de la versión más alta; las
-- anteriores quedan como historial. No se borra ni se actualiza ninguna fila
-- de aquí en adelante: el registro es de solo-agregar.
--
-- Aplicar con:
--   psql -v ON_ERROR_STOP=1 -h localhost -U fim_user -d fim_db -f sql/02_baseline_versionada.sql
--

BEGIN;

ALTER TABLE public.registros_archivos
    ADD COLUMN version_baseline integer;

-- Numera las baselines que ya existían: la primera corrida de cada archivo es
-- la versión 1, la segunda la 2, etc. (única vez que se hace un UPDATE).
UPDATE public.registros_archivos r
SET version_baseline = n.version
FROM (
    SELECT id, row_number() OVER (PARTITION BY ruta_completa ORDER BY id) AS version
    FROM public.registros_archivos
    WHERE evento = 'BASELINE'
) n
WHERE r.id = n.id;

-- Un archivo no puede aparecer dos veces en la misma versión de la baseline
CREATE UNIQUE INDEX registros_baseline_unica
    ON public.registros_archivos (ruta_completa, version_baseline)
    WHERE evento = 'BASELINE';

-- La baseline vigente: las filas BASELINE de la versión más alta
CREATE VIEW public.baseline_vigente AS
SELECT id, nombre_archivo, ruta_completa, hash_sha256, owner_archivo, permisos,
       version_baseline, fecha_registro
FROM public.registros_archivos
WHERE evento = 'BASELINE'
  AND version_baseline = (
      SELECT max(version_baseline)
      FROM public.registros_archivos
      WHERE evento = 'BASELINE'
  );

COMMIT;
