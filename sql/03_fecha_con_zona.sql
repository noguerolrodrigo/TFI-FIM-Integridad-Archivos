--
-- 03: fecha_registro con zona horaria (TIMESTAMPTZ)
--
-- TIMESTAMP sin zona guarda "la hora del reloj" sin decir de dónde: la misma
-- columna tenía filas en UTC y filas en hora de Mendoza. TIMESTAMPTZ guarda un
-- instante exacto, que es lo que hace falta para medir MTTD y MTTR.
--
-- Las filas con id <= 17 se insertaron antes de configurar la zona de la base
-- (ALTER DATABASE fim_db SET timezone, 12/10/2026 04:43), o sea en UTC.
-- Las posteriores están en hora de Mendoza.
--
-- Aplicar con:
--   psql -v ON_ERROR_STOP=1 -h localhost -U fim_user -d fim_db -f sql/03_fecha_con_zona.sql
--

BEGIN;

-- La vista usa la columna: hay que quitarla para cambiar el tipo y volver a crearla
DROP VIEW public.baseline_vigente;

ALTER TABLE public.registros_archivos
    ALTER COLUMN fecha_registro TYPE timestamp with time zone
    USING CASE
        WHEN id <= 17 THEN fecha_registro AT TIME ZONE 'UTC'
        ELSE fecha_registro AT TIME ZONE 'America/Argentina/Mendoza'
    END;

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
