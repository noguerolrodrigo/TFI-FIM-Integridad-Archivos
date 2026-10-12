# CLAUDE.md — TFI: Sistema FIM con extracción diferencial y orquestación n8n

## Qué es este proyecto
Trabajo Final Integrador de la Tecnicatura Universitaria en Programación (UTN Facultad Regional Mendoza).
Autor: Rodrigo Jesús Noguerol. Título: "Análisis e implementación de un Sistema Automatizado
de Monitoreo de Integridad de Archivos (FIM) con extracción diferencial en entornos Linux".

## Documentación de referencia (docs/)
- `Informe de Avance.pdf`: informe entregado (marzo 2026). Describe baseline + monitor con diff.
- `Orquestación de Playbooks ... con n8n.docx`: diseño de la etapa de respuesta automatizada con n8n
  (playbooks PB-A actualización de baseline y PB-B detección/respuesta con aprobación humana).
  OJO: su tabla de resultados es simulada; no usar esos números.
- `Proyecto_07_Integridad_Archivos.md`: consigna de la cátedra. Sirve por los criterios de evaluación
  (implementación 30, cobertura de monitoreo 25, alertas 25, documentación 20). NO copiar su esquema.

## Estado actual del código (octubre 2026)
- `generar_baseline.py`: recorre `./directorio_prueba`, calcula SHA-256, owner (uid) y permisos
  octales, inserta eventos `BASELINE` en `registros_archivos`.
- `monitor_fim.py`: watchdog sobre `./directorio_prueba`. Solo maneja `on_modified`. Guarda el
  contenido de los archivos en RAM, calcula el diff con difflib, registra `MODIFICADO` en la BD,
  mueve el archivo alterado a `./cuarentena/` y lo restaura desde la copia en RAM.
  Esta respuesta automatizada es posterior al informe de avance.
- `sql/01_schema.sql`: esquema real exportado con pg_dump. La tabla tiene una columna `notificado`
  (boolean, default false) pensada para n8n que todavía no se usa.
- Probado y funcionando el 12/10/2026.

## Stack
- Python 3 + venv: watchdog 6, psycopg2-binary, python-dotenv (ver requirements.txt)
- PostgreSQL local: base `fim_db`, usuario `fim_user`, credenciales en `.env`
- n8n (pendiente de integrar)
- Ubuntu en WSL2 sobre Windows

## Entorno — importante
- El proyecto vive en `~/proyecto_fim` dentro de WSL. No mover a `/mnt/c/...`: inotify no recibe
  eventos fiables de archivos del lado Windows.
- En WSL los servicios no arrancan solos: `sudo service postgresql start` antes de trabajar.
- Activar el entorno: `source venv/bin/activate`.
- `.env`, `venv/` y `cuarentena/` están en `.gitignore`. Nunca commitear credenciales.
- Monitorear rutas reales (`/etc`, `/usr/bin`) requiere root; para pruebas usar `./directorio_prueba`.

## Convenciones
- Código, variables, columnas y mensajes en español, como el código existente.
- Valores de `evento`: `BASELINE`, `MODIFICADO` (existentes); nuevos: `CREADO`, `ELIMINADO`, `MOVIDO`,
  `PERMISOS`, `RESTAURADO`.
- Hash SHA-256 leyendo en bloques. Diff con `difflib.unified_diff(..., fromfile='Antes', tofile='Ahora')`.
- Cambios chicos y explicables: un commit por mejora, con mensaje descriptivo en español.
  El autor tiene que poder defender cada decisión ante el tribunal.
- Cambios de esquema: archivo nuevo en `sql/` (ej. `02_...sql`), sin editar el `01`.
- Push al remoto seguido (el código ya estuvo a punto de perderse una vez).

## Honestidad académica
- MTTD, MTTR y falsos positivos se MIDEN con scripts y se guardan en CSV. No inventar ni simular números.
- Existe un proyecto aprobado de otros alumnos con un tema parecido: se pueden tomar ideas generales,
  no copiar código.
