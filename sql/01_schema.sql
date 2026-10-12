--
-- PostgreSQL database dump
--

\restrict sVpxC5dz27oiidyphMc17cV4PMuISyewx3wzGEQ3VyMjwwispBP5Z6lo5OCp8Rc

-- Dumped from database version 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: registros_archivos; Type: TABLE; Schema: public; Owner: fim_user
--

CREATE TABLE public.registros_archivos (
    id integer NOT NULL,
    nombre_archivo character varying(255),
    ruta_completa text,
    hash_sha256 character varying(64),
    evento character varying(50),
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    notificado boolean DEFAULT false,
    detalles_diff text,
    owner_archivo character varying(100),
    permisos character varying(20)
);


ALTER TABLE public.registros_archivos OWNER TO fim_user;

--
-- Name: registros_archivos_id_seq; Type: SEQUENCE; Schema: public; Owner: fim_user
--

CREATE SEQUENCE public.registros_archivos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.registros_archivos_id_seq OWNER TO fim_user;

--
-- Name: registros_archivos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: fim_user
--

ALTER SEQUENCE public.registros_archivos_id_seq OWNED BY public.registros_archivos.id;


--
-- Name: registros_archivos id; Type: DEFAULT; Schema: public; Owner: fim_user
--

ALTER TABLE ONLY public.registros_archivos ALTER COLUMN id SET DEFAULT nextval('public.registros_archivos_id_seq'::regclass);


--
-- Name: registros_archivos registros_archivos_pkey; Type: CONSTRAINT; Schema: public; Owner: fim_user
--

ALTER TABLE ONLY public.registros_archivos
    ADD CONSTRAINT registros_archivos_pkey PRIMARY KEY (id);


--
-- PostgreSQL database dump complete
--

\unrestrict sVpxC5dz27oiidyphMc17cV4PMuISyewx3wzGEQ3VyMjwwispBP5Z6lo5OCp8Rc

