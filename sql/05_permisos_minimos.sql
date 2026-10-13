--
-- 05: Permisos mínimos para fim_user (registro de solo-agregar)
--
-- Hasta acá fim_user era dueño de la tabla y de la base, así que podía modificar
-- o borrar el historial. Después de esta migración solo puede leer y agregar filas.
--
-- No alcanza con un REVOKE: el dueño de una tabla siempre puede devolverse los
-- permisos, y el dueño de la base es dueño del esquema public y puede borrar
-- cualquier tabla. Por eso la tabla, la vista y la base pasan a ser de postgres.
--
-- Hay que correrla como superusuario. El usuario postgres no puede leer archivos
-- dentro de /home, así que el archivo se le pasa por entrada estándar:
--   sudo -u postgres psql -v ON_ERROR_STOP=1 -d fim_db < sql/05_permisos_minimos.sql
--
-- Límite: el registro queda inmutable para la cuenta del agente (fim_user),
-- no para el superusuario de PostgreSQL.
--

BEGIN;

-- 1. fim_user deja de ser dueño (la secuencia del id cambia de dueño junto con la tabla)
ALTER TABLE public.registros_archivos OWNER TO postgres;
ALTER VIEW public.baseline_vigente OWNER TO postgres;
ALTER DATABASE fim_db OWNER TO postgres;

-- 2. Se le quita todo...
REVOKE ALL ON DATABASE fim_db FROM fim_user;
REVOKE ALL ON SCHEMA public FROM fim_user;
REVOKE ALL ON public.registros_archivos FROM fim_user;
REVOKE ALL ON public.baseline_vigente FROM fim_user;
REVOKE ALL ON SEQUENCE public.registros_archivos_id_seq FROM fim_user;

-- 3. ...y se le da solo lo que necesitan generar_baseline.py y monitor_fim.py:
--    leer, agregar filas y pedir el siguiente id. Sin UPDATE, DELETE ni TRUNCATE.
GRANT CONNECT ON DATABASE fim_db TO fim_user;
GRANT USAGE ON SCHEMA public TO fim_user;
GRANT SELECT, INSERT ON public.registros_archivos TO fim_user;
GRANT SELECT ON public.baseline_vigente TO fim_user;
GRANT USAGE, SELECT ON SEQUENCE public.registros_archivos_id_seq TO fim_user;

COMMIT;
