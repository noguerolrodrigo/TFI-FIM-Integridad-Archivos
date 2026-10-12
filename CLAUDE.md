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
  octales, inserta eventos `BASELINE` en `registros_archivos` con un `version_baseline` nuevo en cada
  corrida y copia cada archivo a la bóveda (`./boveda/`).
- `boveda.py`: respaldo en disco. `respaldar()` copia con `shutil.copy2`; `restaurar()` repone con un
  temporal `.fim_tmp_*` + `os.replace` (atómico); `limpiar_huerfanos()` saca lo que ya no está en la
  baseline vigente. La bóveda espeja la ruta absoluta del archivo y está en `.gitignore`.
- `monitor_fim.py`: watchdog sobre `./directorio_prueba`. Solo maneja `on_modified`. Decide si hubo
  cambio comparando el hash del archivo con el de la copia en la bóveda (todavía no consulta la BD),
  calcula el diff contra la bóveda (los binarios no generan diff de texto), registra `MODIFICADO`,
  copia el archivo alterado a `./cuarentena/{fecha}_{nombre}` y lo restaura desde la bóveda.
  Un archivo sin respaldo se mueve a cuarentena y no se recrea. Ya no guarda nada en RAM.
  Esta respuesta automatizada es posterior al informe de avance.
- `sql/01_schema.sql`: esquema real exportado con pg_dump. La tabla tiene una columna `notificado`
  (boolean, default false) pensada para n8n que todavía no se usa.
- `sql/02_baseline_versionada.sql`: columna `version_baseline`, índice único (ruta, versión) y vista
  `baseline_vigente` (filas `BASELINE` de la versión más alta). El registro es de solo-agregar:
  no se hace UPDATE ni DELETE.
- `tests/`: pytest para la bóveda y el diff (`pytest` desde la raíz del proyecto).
- Plan de mejoras en 12 commits acordado el 12/10/2026; hechos los commits 1 a 3. Pendientes:
  TIMESTAMPTZ, conexión reutilizable, verificación contra la baseline de la BD, eventos nuevos,
  permisos, temporales, configuración por `.env`, modo de restauración y permisos mínimos de `fim_user`.

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
