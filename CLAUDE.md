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
- `config.py`: toda la configuración sale del `.env` (ver `.env.example`): `RUTAS_MONITOREADAS`
  (varios directorios separados por `:`), `DIR_BOVEDA`, `DIR_CUARENTENA`, `DIR_LOGS`,
  `PATRONES_IGNORADOS` y `MODO_RESTAURACION`. Las rutas se guardan absolutas; las relativas se
  resuelven desde la carpeta del proyecto. Por defecto se vigila `./directorio_prueba`.
- `generar_baseline.py`: recorre las rutas monitoreadas, calcula SHA-256, owner (uid) y permisos
  octales, inserta eventos `BASELINE` en `registros_archivos` con un `version_baseline` nuevo en cada
  corrida y copia cada archivo a la bóveda. Hay que volver a correrlo si cambian las rutas.
- `boveda.py`: respaldo en disco. `respaldar()` copia con `shutil.copy2`; `restaurar()` repone con un
  temporal `.fim_tmp_*` + `os.replace` (atómico); `limpiar_huerfanos()` saca lo que ya no está en la
  baseline vigente. La bóveda espeja la ruta absoluta del archivo y está en `.gitignore`.
- `bd.py`: una sola conexión reutilizable a PostgreSQL (`conectar()`, `ejecutar()` con reconexión).
- `hashes.py`: `get_sha256()`. `metadatos.py`: `leer_owner_y_permisos()` (uid y modo octal, con el
  dígito de setuid si lo hay). `filtros.py`: `PATRONES_IGNORADOS` y `es_ignorado()` (temporales de
  editores y de la restauración). Los tres los comparten la baseline y el monitor.
- `pendientes.py`: log local `logs/eventos_pendientes.jsonl` para eventos que no llegaron a la BD.
- `notificador.py`: después de cada evento, POST `{tipo, evento_id, resultado}` a `N8N_WEBHOOK_URL`
  con el header `X-FIM-Secreto`, en un hilo aparte (timeout 2 s). Sin esa variable no avisa.
- `monitor_fim.py`: watchdog sobre las rutas monitoreadas con `on_created`, `on_modified`,
  `on_deleted` y `on_moved`. Todos llaman a `procesar(ruta)`: el evento es solo el disparador y
  `verificar()` clasifica comparando el disco con `baseline_vigente` (hash, permisos y owner):
  `MODIFICADO`, `CREADO`, `ELIMINADO`, `MOVIDO` o `PERMISOS`.
  - Respuesta: copia de evidencia a `./cuarentena/{fecha}_{nombre}` y restauración desde la bóveda
    (solo si la copia de la bóveda tiene el hash de la baseline), con una fila `RESTAURADO`.
    `CREADO` se mueve a cuarentena. `PERMISOS` se repone con chmod/chown (chown requiere root).
  - Al arrancar hace un escaneo inicial de la baseline contra el disco. No arranca si la baseline
    vigente no tiene archivos de las rutas monitoreadas, ni si la bóveda, la cuarentena o los logs
    están dentro de un directorio vigilado.
  - `MODO_RESTAURACION=automatica` (por defecto) restaura solo. Con `aprobacion` registra y guarda
    la evidencia pero no restaura: la restauración la dispara `restaurar.py <ruta>`, que deja en la
    fila `RESTAURADO` quién aprobó. `CREADO` va a cuarentena en los dos modos.
  - Con la BD caída no restaura: copia la evidencia y deja el evento como `SIN_VERIFICAR` en el
    log local. Falta reinsertar esos eventos cuando vuelve la BD.
  - **Ventanas de mantenimiento** (`ventanas_mantenimiento`): un cambio dentro de una ventana vigente
    se registra con su diff y copia en cuarentena, pero no se restaura (resultado `AUTORIZADO`).
  - **Ejecutor de decisiones**: un hilo lee cada 2 s la tabla `decisiones` (las inserta n8n) y las
    ejecuta: `INCIDENTE` (nada), `RESTAURAR` (desde la bóveda), `ACEPTAR`/`AUTORIZADO` (la versión
    que vio la persona pasa a la baseline de ese archivo solo, vía
    `generar_baseline.actualizar_archivo()`). Registra en `ejecuciones` y avisa a n8n.
  Esta respuesta automatizada es posterior al informe de avance.
- `sql/01_schema.sql`: esquema real exportado con pg_dump. La tabla tiene una columna `notificado`
  (boolean, default false) pensada para n8n que todavía no se usa.
- `sql/02_baseline_versionada.sql`: columna `version_baseline`, índice único (ruta, versión) y vista
  `baseline_vigente` (filas `BASELINE` de la versión más alta). El registro es de solo-agregar:
  no se hace UPDATE ni DELETE.
- `sql/03_fecha_con_zona.sql`: `fecha_registro` es TIMESTAMPTZ.
- `sql/04_evidencia.sql`: columnas `hash_anterior` y `ruta_cuarentena`.
- `sql/05_permisos_minimos.sql`: tabla, vista y base pasan a ser de `postgres`; a `fim_user` le
  quedan solo SELECT e INSERT. Se corre como superusuario:
  `sudo -u postgres psql -v ON_ERROR_STOP=1 -d fim_db < sql/05_permisos_minimos.sql`.
  Una vez aplicada, las migraciones nuevas también hay que correrlas como `postgres`, y `fim_user`
  ya no puede marcar `notificado` (para n8n: un rol aparte con UPDATE solo sobre esa columna).
- `sql/06_orquestacion.sql`: tablas `notificaciones`, `decisiones` (una por evento), `ejecuciones`,
  `ventanas_mantenimiento`, `accesos_rechazados` y rol `fim_n8n` (solo SELECT e INSERT en sus tablas).
- `n8n/`: `iniciar_n8n.sh` (n8n 2.41.4 con Node 24 de nvm, entorno limpio, datos en `~/n8n_fim`),
  `importar_workflows.sh`, `README.md` (instalación y configuración en el navegador) y los workflows
  `PB-B_deteccion_respuesta.json`, `PB-B_decision_telegram.json`, `PB-A_baseline_autorizada.json`,
  `respaldo_notificaciones.json`. n8n orquesta y decide; nunca toca archivos ni corre comandos.
- Botones de Telegram (extensión A): `n8n/iniciar_ngrok.sh` publica con el dominio gratuito de ngrok
  solo `POST /webhook/telegram-<sufijo>` (`n8n/ngrok_politica.yml`); `n8n/registrar_webhook_telegram.sh`
  registra el webhook con `secret_token`. El workflow valida el secreto y que el toque venga de
  `TELEGRAM_CHAT_ID` (otras cuentas van a `accesos_rechazados`). El sufijo y los secretos están solo
  en el `.env`.
- `scripts/preparar_bd_pruebas.sh`: deja `fim_pruebas` con el esquema de `fim_db`, vacía.
- Mediciones (Paso 4), todas contra `fim_pruebas` salvo la muestra real:
  - `scripts/n8n_de_pruebas.sh iniciar|detener`: n8n descartable (puerto 5690, datos en /tmp) con
    Telegram simulado (`scripts/telegram_falso.py`).
  - `scripts/medir_metricas.py --repeticiones 50`: MTTD, MTTR (BD y disco), alerta, ejecución y
    costo del COMMIT. `--telegram-real --repeticiones 10`: muestra con el bot real (lee `fim_db`).
  - `scripts/medir_falsos_positivos.py --ediciones 20`: vim y nano con y sin filtro de temporales.
  - `scripts/medir_escaneo_periodico.py`: escaneo completo de una copia de /etc y cron de 10 s.
  - `scripts/resumir_metricas.py <csv>`: resumen (media, mediana, p95, mín., máx.) y gráfico.
  - `scripts/armar_readme_resultados.py`: arma `resultados/README.md` desde los CSV.
  - Resultados versionados en `resultados/` (CSV, resúmenes, gráficos, entorno). La lectura y la
    comparación con la tabla supuesta del .docx están en `resultados/README.md`.
- `tests/`: pytest (`pytest` desde la raíz). Los del monitor usan una baseline en memoria
  (`tests/conftest.py`); los de conexión solo hacen SELECT y se saltean si PostgreSQL no está;
  `test_integracion_bd.py` usa `fim_pruebas`, nunca `fim_db`.
- `.gitattributes` fija los saltos de línea en LF.
- Plan de mejoras del motor en 12 commits (Paso 2) terminado el 13/10/2026.
- Paso 3 (n8n) terminado: commits 1 a 8 el 15/10/2026 (link local) y extensión A (9a a 9d) el
  mismo día. Prueba real hecha el 15/10/2026: evento #43 (MODIFICADO, restaurado en el mismo
  segundo), decisión #3 "Fue un incidente" tomada desde el celular con los botones de Telegram
  (el pedido entra por los servidores de Telegram y el túnel ngrok, sin que el celular tenga que
  estar en la misma red), ejecutada 0,6 s después. NO afirmar en el informe que fue por 4G o sin
  wifi: no está verificado. Figura: `docs/informe/img/ciclo_completo_evento43.png`.
- Paso 4 (medición) terminado el 16/10/2026. Medianas medidas: MTTD 5,4 ms; restauración 45,4 ms
  (casi todo es el COMMIT de PostgreSQL en el disco de WSL2: ~38 ms en reposo, ~2 ms en ráfaga);
  alerta 125 ms con Telegram simulado y 1,1 s con el real; ejecución de una decisión 0,9 s (sondeo
  de 2 s); falsos positivos 0 % con el filtro y 50–67 % sin él. Detalle en `resultados/README.md`.

## CÓDIGO CONGELADO (desde el 16/10/2026)
- No se agregan funcionalidades. Solo se aceptan arreglos de errores, cada uno en su commit, con
  test que lo cubra cuando se pueda.
- Si un arreglo toca el monitor, la baseline o los workflows, hay que volver a correr las
  mediciones afectadas y versionar los resultados nuevos sin borrar los anteriores.

## Limitaciones conocidas (declararlas en el informe)
- **Evidencia incompleta en escrituras largas o en varios pasos.** El monitor reacciona al primer
  evento de escritura y restaura enseguida; lo que el programa siga escribiendo después se pierde.
  El ataque se frena, pero la copia en cuarentena y el diff muestran solo la primera parte.
- **Carpeta movida.** Si se mueve una carpeta entera, los archivos de la baseline se restauran en
  su lugar original y los movidos van a cuarentena, pero la carpeta nueva queda vacía en el
  directorio vigilado: el monitor no borra directorios.
- **Temporales ignorados.** Un archivo malicioso cuyo nombre coincida con `PATRONES_IGNORADOS`
  (por ejemplo `algo.tmp`) no se detecta. Es el costo de bajar los falsos positivos.
- **BD caída.** Sin acceso a la baseline no se restaura: se guarda la evidencia y el evento queda
  en `logs/eventos_pendientes.jsonl`. Todavía no se reinsertan cuando vuelve la BD.
- **Bóveda en el mismo equipo.** La bóveda está en el mismo disco y con el mismo usuario que los
  archivos vigilados. Se mitiga verificando su hash contra la baseline antes de restaurar; en
  producción debería estar en otro equipo o ser de root.
- **Propietario.** Reponer el dueño de un archivo (`chown`) requiere correr como root; sin root
  el cambio se registra pero no se repone.
- **Inmutabilidad.** El registro es de solo-agregar para la cuenta del agente (`fim_user`), no
  para el superusuario de PostgreSQL.
- **Solo directorios.** `RUTAS_MONITOREADAS` acepta directorios, no archivos sueltos.
- **Decisión repetida.** Si el monitor ejecuta una decisión pero no puede registrarla en
  `ejecuciones` (BD caída en ese instante), al reiniciarse la vuelve a ejecutar. Restaurar o cerrar
  dos veces no cambia nada; aceptar dos veces genera una versión de baseline de más.
- **Ventanas que vencen.** Lo que se cambió dentro de una ventana y no se pasó a la baseline vuelve a
  tratarse como cambio no autorizado en el próximo evento o escaneo.
- **Links locales.** Con la opción de link local solo se decide desde la PC donde corre n8n.
- **Resultado reconstruido.** Cuando el respaldo reenvía un evento, deduce el resultado de la BD; un
  cambio de propietario que no se pudo reponer (sin root) aparece como pendiente.
- **Espera de 24 h sin probar.** El aviso de "pasaron 24 h sin decisión" no se probó de punta a punta.
- **Normalización de paths en ngrok.** La Traffic Policy se evalúa sobre el path normalizado y ngrok
  reenvía el path original, así que variantes como `//webhook/...`, `/%2Fwebhook/...` o
  `/./webhook/...` pasan el filtro (verificado el 15/10/2026 con un servidor descartable; también
  `req.url` viene normalizada). Evidencia de que no expone datos: contra n8n, esas variantes con POST
  dan 404 o caen en el mismo webhook de Telegram (que exige el `secret_token`); con GET devuelven solo
  la página HTML vacía del editor, sin datos de la instancia, y el editor no puede funcionar porque
  `/rest`, `/assets` y `/static` siguen bloqueados. Mitigación: la única ruta permitida lleva un
  sufijo aleatorio de 32 caracteres, así que hay que adivinarlo para llegar siquiera a esa página.
- **Mediciones en WSL2.** Los tiempos son de una notebook con WSL2; el COMMIT de PostgreSQL
  (~38 ms con el disco en reposo) domina el MTTR y sería distinto en un servidor con disco nativo.
  Hubo una pausa general en una repetición (396 ms) que quedó en los datos.
- **Plan gratuito de ngrok.** Depende de un tercero y de sus límites (20 000 pedidos y 1 GB al mes);
  si el túnel no está, los botones no funcionan y queda el link local.

## Stack
- Python 3 + venv: watchdog 6, psycopg2-binary, python-dotenv (ver requirements.txt)
- PostgreSQL local: base `fim_db`, usuario `fim_user`, credenciales en `.env` (plantilla: `.env.example`)
- n8n 2.41.4 sobre Node 24 (nvm, sin tocar el Node 20 del sistema); ver `n8n/README.md`
- Ubuntu en WSL2 sobre Windows

## Entorno — importante
- El proyecto vive en `~/proyecto_fim` dentro de WSL. No mover a `/mnt/c/...`: inotify no recibe
  eventos fiables de archivos del lado Windows.
- En WSL los servicios no arrancan solos: `sudo service postgresql start` antes de trabajar.
- Activar el entorno: `source venv/bin/activate`.
- `.env`, `venv/`, `cuarentena/`, `boveda/` y `logs/` están en `.gitignore`. Nunca commitear credenciales.
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
