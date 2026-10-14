--
-- 06: Tablas para la orquestación con n8n y rol fim_n8n
--
-- n8n orquesta y decide; el monitor ejecuta. n8n nunca toca archivos: deja la
-- decisión humana en la BD y el monitor (fim_user) la ejecuta y lo registra.
-- Todas las tablas son de solo-agregar, igual que registros_archivos.
--
--   notificaciones          n8n avisó de un evento (la fecha sirve para medir el tiempo hasta la alerta)
--   decisiones              lo que decidió la persona, una sola por evento
--   ejecuciones             el monitor ejecutó una decisión
--   ventanas_mantenimiento  cambios autorizados de antemano (PB-A)
--   accesos_rechazados      intentos de decidir desde una cuenta de Telegram que no es la autorizada
--
-- Hay que correrla como superusuario (después de la 05 fim_user no puede crear tablas):
--   sudo -u postgres psql -v ON_ERROR_STOP=1 -d fim_db < sql/06_orquestacion.sql
-- El rol fim_n8n se crea sin contraseña; se la ponés vos con:
--   sudo -u postgres psql -d fim_db -c '\password fim_n8n'
--

BEGIN;

CREATE TABLE public.notificaciones (
    id serial PRIMARY KEY,
    evento_id integer NOT NULL REFERENCES public.registros_archivos (id),
    canal character varying(30) NOT NULL,
    detalle text,
    fecha timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE public.decisiones (
    id serial PRIMARY KEY,
    -- Una sola decisión por evento: si llega otra por el otro canal, la BD la rechaza
    evento_id integer NOT NULL UNIQUE REFERENCES public.registros_archivos (id),
    -- Modo automático (ya restaurado): INCIDENTE o AUTORIZADO.
    -- Modo aprobación (pendiente):     RESTAURAR o ACEPTAR.
    decision character varying(20) NOT NULL
        CHECK (decision IN ('INCIDENTE', 'AUTORIZADO', 'RESTAURAR', 'ACEPTAR')),
    decidido_por text NOT NULL,
    canal character varying(30) NOT NULL,
    fecha timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE public.ejecuciones (
    id serial PRIMARY KEY,
    decision_id integer NOT NULL UNIQUE REFERENCES public.decisiones (id),
    resultado character varying(30) NOT NULL CHECK (resultado IN ('EJECUTADA', 'RECHAZADA', 'ERROR')),
    detalle text,
    fecha timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE public.ventanas_mantenimiento (
    id serial PRIMARY KEY,
    -- Archivo o directorio, con ruta absoluta
    ruta text NOT NULL CHECK (ruta LIKE '/%'),
    motivo text NOT NULL,
    autorizado_por text NOT NULL,
    desde timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    hasta timestamp with time zone NOT NULL,
    CHECK (hasta > desde)
);

CREATE TABLE public.accesos_rechazados (
    id serial PRIMARY KEY,
    canal character varying(30) NOT NULL,
    remitente_id text,
    remitente_usuario text,
    contenido text,
    fecha timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Rol de n8n: lee lo que necesita para armar la alerta y solo agrega filas en sus tablas.
-- No puede modificar ni borrar nada, ni escribir en registros_archivos.
CREATE ROLE fim_n8n LOGIN;
GRANT CONNECT ON DATABASE fim_db TO fim_n8n;
GRANT USAGE ON SCHEMA public TO fim_n8n;
GRANT SELECT ON public.registros_archivos, public.baseline_vigente, public.notificaciones,
                public.decisiones, public.ejecuciones, public.ventanas_mantenimiento TO fim_n8n;
GRANT INSERT ON public.notificaciones, public.decisiones, public.ventanas_mantenimiento,
                public.accesos_rechazados TO fim_n8n;
GRANT USAGE ON SEQUENCE public.notificaciones_id_seq, public.decisiones_id_seq,
                        public.ventanas_mantenimiento_id_seq, public.accesos_rechazados_id_seq TO fim_n8n;

-- El monitor lee decisiones y ventanas, y registra las ejecuciones.
GRANT SELECT ON public.decisiones, public.ventanas_mantenimiento, public.ejecuciones,
                public.notificaciones TO fim_user;
GRANT INSERT ON public.ejecuciones TO fim_user;
GRANT USAGE ON SEQUENCE public.ejecuciones_id_seq TO fim_user;

COMMIT;
