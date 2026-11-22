# Anexos

## Anexo A: Repositorio y versiones evaluadas

El código fuente, las migraciones de la base de datos, los workflows de n8n, los scripts de medición
y los resultados están en un repositorio público:

<https://github.com/noguerolrodrigo/TFI-FIM-Integridad-Archivos>

El informe se refiere a tres versiones del código:

**Versión medida en octubre (primera instancia).** Es el commit de congelamiento del 16 de octubre
de 2026, sobre el que se hicieron las mediciones de las secciones 5.1 a 5.8 y que auditó el
tribunal:

`81b1bc8709a2949010d4c4b97a9c5ca3a184276d`

<https://github.com/noguerolrodrigo/TFI-FIM-Integridad-Archivos/tree/81b1bc8709a2949010d4c4b97a9c5ca3a184276d>

**Versión corregida (segunda instancia).** Es el commit del 17 de noviembre de 2026 sobre el que se
hicieron las mediciones de la sección 5.9 y que auditó el tribunal en la segunda instancia:

`39c661cf99c09befb887c7a8c47e095582aa58aa`

<https://github.com/noguerolrodrigo/TFI-FIM-Integridad-Archivos/tree/39c661cf99c09befb887c7a8c47e095582aa58aa>

**Versión final (para la defensa).** Es el commit del 22 de noviembre de 2026 que cierra el código de
la aplicación. Agrega una sola corrección, la del hallazgo n1 de la devolución de la segunda
instancia:

`f2889ede7dd9ec7fdca5d9e42847321a33b5058d`

<https://github.com/noguerolrodrigo/TFI-FIM-Integridad-Archivos/tree/f2889ede7dd9ec7fdca5d9e42847321a33b5058d>

Para obtener exactamente una de esas versiones:

```bash
git clone https://github.com/noguerolrodrigo/TFI-FIM-Integridad-Archivos.git
cd TFI-FIM-Integridad-Archivos
git checkout f2889ede7dd9ec7fdca5d9e42847321a33b5058d
# o 39c661cf99c09befb887c7a8c47e095582aa58aa, o 81b1bc8709a2949010d4c4b97a9c5ca3a184276d
```

Entre una y otra hay 11 commits de código y pruebas, todos del 17 de noviembre de 2026, que
corrigen la restauración y el tratamiento de los enlaces simbólicos (hallazgo M2 de la devolución)
y ajustan una prueba que fallaba al ejecutarse como superusuario (m8): el temporal de la restauración
pasa a tener nombre aleatorio y apertura exclusiva, el filtro deja de ignorar por prefijo, los
enlaces simbólicos se detectan y no se siguen, el hash, el diff y la copia a cuarentena salen de una
sola apertura del archivo, los permisos se reponen sobre el descriptor, se comprueba la carpeta real
antes de restaurar, el generador de línea base saltea los enlaces y se agrega un candado entre el
monitor y `restaurar.py`. No cambiaron las migraciones ni los workflows de n8n. Los demás commits
posteriores al congelamiento agregan los capítulos de este informe, sus figuras, los resultados de
las corridas nuevas y un ajuste del script que arma el resumen de resultados.

Entre la versión corregida y la final hay un solo commit de código y pruebas (`f2889ed`). Hasta
entonces, la restauración dejaba el archivo a nombre del usuario que ejecuta el monitor, porque el
archivo restaurado es uno nuevo que se renombra sobre el original, y no se le reponía el
propietario. El tribunal lo comprobó ejecutando el monitor como superusuario: un archivo de la línea
base del usuario 1000 quedaba a nombre del superusuario y el evento siguiente lo informaba como un
cambio de propietario. Ahora, antes del renombrado, se aplica `os.fchown` sobre el descriptor del
temporal con el propietario de la línea base; si el monitor no tiene permiso, restaura igual y lo
deja anotado (secciones 4.3 y 6.4). El cambio alcanza al monitor, a `restaurar.py` y a la aceptación
de un cambio, y agrega 10 pruebas.

Esta corrección no afecta las mediciones del Capítulo 5, que no se repitieron. En el laboratorio
los archivos vigilados pertenecían al mismo usuario que ejecutaba el monitor, que es el mismo caso
por el que el defecto no se había manifestado: el archivo restaurado ya nacía con el propietario
correcto. En ese caso la versión final no llega a llamar a `os.fchown`; lo único que agrega a cada
restauración es una consulta del propietario del temporal (`os.fstat`) para compararlo con el de la
línea base. El costo de esa consulta no se midió.

Los fragmentos de los anexos siguientes son de la versión final, y los números de línea
corresponden a ella.

## Anexo B: Estructura del repositorio

**Tabla B.1.** Contenido del repositorio.

| Ruta | Contenido |
|---|---|
| `config.py` | Lee la configuración del archivo `.env` (Anexo C). |
| `generar_baseline.py` | Genera la línea base y la copia de cada archivo a la bóveda; actualiza la línea base de un único archivo. |
| `monitor_fim.py` | Monitor por eventos: verificación, evidencia, respuesta, escaneo inicial y ejecución de decisiones. |
| `restaurar.py` | Restauración manual desde la terminal, pensada para el modo de aprobación. No pasa por n8n ni registra una fila en `decisiones` (sección 4.7). |
| `boveda.py` | Copia confiable de los archivos y restauración atómica, con temporal de nombre aleatorio. |
| `bd.py` | Conexión a PostgreSQL, con reconexión. |
| `hashes.py`, `metadatos.py`, `filtros.py` | Cálculo de SHA-256, lectura de permisos y propietario (sin seguir enlaces), y archivos ignorados: patrones de temporales de editores y temporales propios de la restauración. |
| `pendientes.py` | Registro local de los eventos que no llegaron a la base de datos. |
| `notificador.py` | Aviso a n8n después de cada evento. |
| `sql/` | Migraciones de la base de datos, numeradas de la 01 a la 06. |
| `n8n/` | Workflows de n8n en JSON, scripts para iniciar n8n y el túnel ngrok, política del túnel y guía de instalación. |
| `scripts/` | Base de datos de pruebas, n8n de pruebas con Telegram simulado y scripts de medición y resumen. |
| `tests/` | 206 tests automatizados (pytest): 203 de la aplicación y 3 del script de intervalos de confianza. |
| `resultados/` | Mediciones en CSV, resúmenes, gráficos y descripción del entorno. |
| `directorio_prueba/` | Directorio vigilado en las pruebas. |
| `docs/` | Documentos de referencia y los capítulos de este informe. |
| `.env.example` | Plantilla de configuración, sin credenciales. |

El archivo `.env` con las credenciales reales, la bóveda, la cuarentena y los registros locales están
excluidos del repositorio (`.gitignore`).

## Anexo C: Configuración (`.env.example`)

El sistema se configura con un archivo `.env` que se crea a partir de esta plantilla. La plantilla no
contiene credenciales: la contraseña es un valor de ejemplo y los secretos están vacíos.

```ini
# Copiar a .env y completar. El .env real no se sube al repositorio.

# Conexión a PostgreSQL
DB_HOST=localhost
DB_NAME=fim_db
DB_USER=fim_user
DB_PASS=cambiar_esta_clave

# Directorios a vigilar, separados por ":". Las rutas relativas se toman desde la carpeta del proyecto.
# Ejemplo con dos directorios: RUTAS_MONITOREADAS=./directorio_prueba:./otra_carpeta_de_prueba
# No apuntar a directorios con enlaces simbólicos legítimos, como /etc (informe, secciones 6.4 y 7.1).
RUTAS_MONITOREADAS=./directorio_prueba

# Dónde se guardan la copia confiable, la evidencia y el log local.
# No pueden estar dentro de un directorio vigilado.
DIR_BOVEDA=./boveda
DIR_CUARENTENA=./cuarentena
DIR_LOGS=./logs

# Temporales de editores que no se vigilan, separados por ","
PATRONES_IGNORADOS=*.swp,*.swo,*.swx,*~,*.tmp

# automatica: el monitor restaura solo.
# aprobacion: registra, guarda la evidencia y espera la decisión de una persona
# (botones de Telegram o enlace local de la alerta; sin n8n, restaurar.py).
MODO_RESTAURACION=automatica

# Aviso a n8n después de cada evento (vacío = no se avisa). El secreto viaja en el header X-FIM-Secreto.
# Generarlo con: openssl rand -hex 24
N8N_WEBHOOK_URL=http://localhost:5678/webhook/fim-evento
N8N_WEBHOOK_SECRETO=

# Bot de Telegram para las alertas (el token se carga además como credencial en la UI de n8n)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Botones de Telegram por ngrok (extensión A). Generar cada uno con: openssl rand -hex 24 / -hex 16
# El secreto lo manda Telegram en el header X-Telegram-Bot-Api-Secret-Token; el sufijo hace que la
# única ruta pública (/webhook/telegram-<sufijo>) no se pueda adivinar.
TELEGRAM_WEBHOOK_SECRETO=
TELEGRAM_WEBHOOK_SUFIJO=
```

## Anexo D: Fragmentos clave del código

Se transcriben los fragmentos que implementan las decisiones centrales del Capítulo 4, tomados de la
versión final (Anexo A). Donde se omitieron líneas, se indica con `# [...]`. En el repositorio
algunas líneas superan los 90 caracteres; para que entren en la página sin cortes arbitrarios, en
los anexos se parten y la continuación empieza con la marca `»`, que no forma parte del código. En
los comentarios, la continuación repite el signo de comentario.

### D.1 Clasificación del cambio contra la línea base (`monitor_fim.py`, líneas 197–217)

El evento del sistema de archivos solo dispara la verificación; la clasificación sale de comparar el
estado real del archivo con la línea base vigente de la base de datos.

```python
def verificar(ruta, hash_actual, owner=None, permisos=None, es_enlace=False):
    """Compara el estado actual del archivo (hash None si no está en disco) con la baseline vigente.

    Devuelve (estado, baseline). El estado es SIN_CAMBIOS, MODIFICADO, CREADO, ELIMINADO o PERMISOS.
    Un enlace simbólico nunca coincide con la baseline, apunte a donde apunte: la baseline solo
    tiene archivos comunes.
    """
    baseline = obtener_baseline(ruta)
    if baseline is None:
        # No figura en la baseline: si existe es un archivo nuevo; si no existe, no hay nada que mirar
        return (SIN_CAMBIOS if hash_actual is None and not es_enlace else CREADO), None
    if es_enlace:
        return MODIFICADO, baseline
    if hash_actual is None:
        return ELIMINADO, baseline
    if hash_actual != baseline["hash"]:
        return MODIFICADO, baseline
    # Mismo contenido: falta ver que no le hayan cambiado los permisos o el dueño
    if (owner, permisos) != (baseline["owner"], baseline["permisos"]):
        return PERMISOS, baseline
    return SIN_CAMBIOS, baseline
```

### D.2 Los eventos como disparadores (`monitor_fim.py`, líneas 766–792)

Los cuatro manejadores de watchdog llaman a la misma función, `procesar()`.

```python
class FIMEventHandler(FileSystemEventHandler):
    """Manejador de los eventos de Watchdog"""

    def on_created(self, event):
        if not event.is_directory:
            procesar(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            procesar(event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            revisar_directorio(event.src_path)
        else:
            procesar(event.src_path)

    def on_moved(self, event):
        if event.is_directory:
            # Lo que estaba en la baseline ya no está en su lugar, y lo que llegó al destino es nuevo
            revisar_directorio(event.src_path)
            for root, dirs, files in os.walk(event.dest_path):
                for file in files:
                    procesar(os.path.join(root, file))
        else:
            procesar(event.src_path, movido_a=event.dest_path)
            procesar(event.dest_path, movido_desde=event.src_path)
```

### D.3 Evidencia y respuesta (`monitor_fim.py`, fragmentos de las líneas 422–603)

El orden es: comprobar la carpeta, abrir el archivo una sola vez sin seguir enlaces, verificar,
registrar la evidencia en la base de datos, copiarla a cuarentena y, recién después, restaurar. Solo
se restaura si la copia de la bóveda sigue teniendo el hash de la línea base y la carpeta real sigue
dentro del directorio vigilado. El `except` final solo imprime el motivo de la falla: no lo guarda
(sección 6.4).

```python
def _procesar(ruta, movido_a, movido_desde, aprobado_por):
    """Hace el trabajo de procesar(). Devuelve (resultado, id del evento registrado o None)."""
    nombre = os.path.basename(ruta)

    # Temporales de editores y de nuestra propia restauración: no se vigilan
    if es_ignorado(ruta):
        return SIN_CAMBIOS, None

    # Si una carpeta del camino es un enlace que lleva afuera del directorio vigilado, el archivo
    # de la baseline ya no está en su lugar: lo que haya del otro lado no se lee ni se toca
    carpeta_afuera = carpeta_real_fuera_de_la_raiz(ruta)

    # El archivo se abre una sola vez y sin seguir enlaces. Un enlace simbólico no se abre:
    # no se le calcula hash ni se lee o copia su destino
    descriptor, destino_enlace = (None, None) if carpeta_afuera is not None else abrir_archivo(ruta)
    try:
        return _procesar_abierto(ruta, nombre, descriptor, destino_enlace, carpeta_afuera,
                                 movido_a, movido_desde, aprobado_por)
    finally:
        if descriptor is not None:
            os.close(descriptor)

def _procesar_abierto(ruta, nombre, descriptor, destino_enlace, carpeta_afuera, movido_a, movido_desde, aprobado_por):
    """Clasifica y responde con el archivo ya abierto (descriptor es None si no está o es un enlace)."""
    if carpeta_afuera is not None:
        h, owner, permisos = None, "N/A", "N/A"
    else:
        # None si el archivo no está en disco (o si es un enlace)
        h = sha256_de_descriptor(descriptor) if descriptor is not None else None
        # [...]
        owner, permisos = leer_owner_y_permisos(ruta)

    # La verdad está en la baseline de la BD
    try:
        estado, baseline = verificar(ruta, h, owner, permisos, es_enlace=destino_enlace is not None)
    except Exception as e:
        # [...]
        guardar_sin_verificar(nombre, ruta, h, e, destino_enlace, descriptor)
        return SIN_VERIFICAR, None

    if estado == SIN_CAMBIOS:
        avisados.pop(ruta, None)
        return SIN_CAMBIOS, None

    # Cambio autorizado de antemano (PB-A): se registra con su evidencia pero no se toca el archivo
    if aprobado_por is None:
        ventana_id = ventana_que_autoriza(ruta)
        if ventana_id is not None:
            return registrar_autorizado(nombre, ruta, h, owner, permisos, estado, baseline, ventana_id, movido_a,
                                        destino_enlace, descriptor)
    # [...]
    hash_baseline = baseline["hash"] if baseline else None
    # [...]
    respaldo = boveda.ruta_en_boveda(ruta)

    # Solo se restaura si la copia de la bóveda sigue siendo la de la baseline
    restaurable = estado != CREADO and respaldo_confiable(ruta, hash_baseline)

    # La evidencia: qué pasó y, si se modificó el contenido, el Diff exacto
    # [...]
    elif destino_enlace is not None:
        texto_diff = f"El archivo de la baseline fue reemplazado por un enlace simbólico → {destino_enlace}."
    # [...]
    elif restaurable:
        texto_diff = calcular_diff(respaldo, descriptor)
    # [...]
    # Solo hay algo para guardar en cuarentena si el archivo está en disco
    ruta_cuarentena = nueva_ruta_cuarentena(nombre) if h is not None else None

    # Si viene de restaurar.py, la detección ya la registró el monitor
    evento_id = None
    if aprobado_por is None:
        evento_id = log_to_db(nombre, ruta, h, evento, texto_diff,
                              hash_anterior=hash_baseline, ruta_cuarentena=ruta_cuarentena)
    # [...]
    resultado = NO_RESTAURADO
    nota_copia = ""
    try:
        if estado == CREADO and destino_enlace is not None:
            # [...]
            if not se_restaura_ahora(aprobado_por):
                avisar_pendiente(ruta)
                return PENDIENTE, evento_id
            # unlink quita el enlace y no toca el destino; a dónde apuntaba ya quedó en el registro
            os.unlink(ruta)
            # [...]
        elif estado == CREADO:
            # Archivo que no está en la baseline: se aísla y no hay nada que restaurar.
            # Es automático en los dos modos: es una contención y se puede deshacer.
            shutil.move(ruta, ruta_cuarentena)
            # [...]
            resultado = CREADO
        else:
            if h is not None:
                # 1. CUARENTENA: Copiamos el archivo alterado tal cual (evidencia), desde el mismo
                # descriptor del que salió el hash
                nota_copia = nota_si_la_copia_difiere(h, copiar_evidencia(descriptor, ruta_cuarentena))
                # [...]
            if not restaurable:
                print("[-] NO SE RESTAURA: la bóveda no coincide con la baseline. Requiere revisión manual.")
            elif carpeta_real_fuera_de_la_raiz(ruta) is not None:
                # Se vuelve a mirar justo antes de escribir, por si la carpeta cambió mientras tanto
                # [...]
            elif not se_restaura_ahora(aprobado_por):
                avisar_pendiente(ruta)
                return PENDIENTE, evento_id
            else:
                # 2. RESTAURACIÓN: Reponemos el original desde la bóveda en disco
                # con el dueño que tiene en la baseline (el archivo repuesto es uno nuevo)
                propietario_repuesto = boveda.restaurar(ruta, owner=baseline["owner"])
                log_to_db(nombre, ruta, get_sha256(ruta), RESTAURADO,
                          f"Restaurado desde la bóveda tras un evento {evento}" + firma_de_aprobacion(aprobado_por)
                          + nota_copia + nota_si_falta_el_propietario(propietario_repuesto, baseline["owner"]),
                          hash_anterior=h, ruta_cuarentena=ruta_cuarentena)
                # [...]
                resultado = RESTAURADO
        # [...]
    except Exception as e:
        print(f"[-] Error en la respuesta automatizada: {e}")
    return resultado, evento_id
```

### D.4 Restauración atómica y temporales propios (`boveda.py`, líneas 40–96; `filtros.py`, líneas 14–19)

```python
def reponer_propietario(descriptor, owner):
    """Deja el archivo abierto a nombre del uid pedido. Devuelve False si no se pudo.

    owner llega como lo guarda la baseline: el uid en texto, o "N/A" si no se pudo leer.
    """
    if owner is None or not str(owner).isdigit():
        return True
    uid = int(owner)
    if os.fstat(descriptor).st_uid == uid:
        return True
    try:
        # Cambiar el dueño de un archivo solo lo puede hacer root. El grupo no se toca (-1):
        # la baseline no lo registra.
        os.fchown(descriptor, uid, -1)
        return True
    except OSError:
        return False

def reponer_desde(origen, ruta, owner=None):
    """Copia origen sobre ruta (bytes, permisos y fechas) sin que el archivo quede a medio escribir.

    Si se pasa owner (uid), el archivo queda a nombre de ese usuario. Devuelve False si eso no
    se pudo (falta root): el contenido se repone igual.
    """
    carpeta, nombre = os.path.split(os.path.abspath(ruta))
    os.makedirs(carpeta, exist_ok=True)

    # Se copia a un temporal en la misma carpeta y se renombra encima del original:
    # el renombrado es atómico, así que el archivo nunca falta ni queda a medio escribir.
    with open(origen, "rb") as fuente:
        # mkstemp elige un nombre aleatorio y crea el archivo con O_CREAT | O_EXCL | O_NOFOLLOW:
        # si en ese nombre ya hay algo (por ejemplo un enlace simbólico puesto por un atacante),
        # falla y prueba con otro en vez de escribir a través del enlace.
        descriptor, temporal = tempfile.mkstemp(prefix=PREFIJO_TEMPORAL, dir=carpeta)
        temporales_propios.add(temporal)
        try:
            # Todo se hace sobre el descriptor ya abierto, no sobre el nombre: aunque alguien
            # cambie lo que hay en ese nombre, se sigue escribiendo en el archivo que se creó.
            with os.fdopen(descriptor, "wb") as destino:
                shutil.copyfileobj(fuente, destino)
                destino.flush()
                datos = os.fstat(fuente.fileno())
                # El temporal nace a nombre del usuario que corre el monitor. El dueño se repone
                # antes del renombrado, para que el archivo nunca aparezca en su ruta con otro
                # dueño, y antes de los permisos, porque cambiar el dueño borra el bit setuid.
                propietario_repuesto = reponer_propietario(destino.fileno(), owner)
                os.fchmod(destino.fileno(), stat.S_IMODE(datos.st_mode))
                os.utime(destino.fileno(), ns=(datos.st_atime_ns, datos.st_mtime_ns))
            # os.replace renombra el nombre, sin seguir enlaces: si ruta es un enlace, lo reemplaza
            os.replace(temporal, ruta)
            return propietario_repuesto
        except BaseException:
            if os.path.lexists(temporal):
                os.unlink(temporal)
            raise
        finally:
            temporales_propios.discard(temporal)
```

```python
def es_ignorado(ruta):
    """Indica si es un temporal propio de la restauración o si su nombre coincide con un patrón ignorado."""
    if os.path.abspath(ruta) in boveda.temporales_propios:
        return True
    nombre = os.path.basename(ruta)
    return any(fnmatch.fnmatch(nombre, patron) for patron in config.PATRONES_IGNORADOS)
```

### D.5 Aviso a n8n (`notificador.py`, líneas 13–36)

Solo se envían tres datos: el tipo de aviso, el identificador del evento y el resultado (el aviso de
una ejecución agrega el identificador de la decisión); n8n lee el resto de la base de datos.

```python
def notificar(datos):
    """Manda los datos a n8n en un hilo aparte: nunca bloquea al monitor ni lanza excepciones.

    Si n8n no responde, el evento queda sin fila en notificaciones y lo levanta el workflow de respaldo.
    Devuelve el hilo (para los tests) o None si no hay webhook configurado.
    """
    if not config.N8N_WEBHOOK_URL:
        return None
    hilo = threading.Thread(target=_enviar, args=(config.N8N_WEBHOOK_URL, datos), daemon=True)
    hilo.start()
    return hilo

def _enviar(url, datos):
    pedido = urllib.request.Request(
        url,
        data=json.dumps(datos).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-FIM-Secreto": config.N8N_WEBHOOK_SECRETO},
        method="POST",
    )
    try:
        with urllib.request.urlopen(pedido, timeout=TIMEOUT_SEGUNDOS) as respuesta:
            respuesta.read()
    except Exception as e:
        print(f"[!] No se pudo avisar a n8n ({datos}): {e}")
```

### D.6 Ejecución de las decisiones (`monitor_fim.py`, líneas 664–683)

n8n registra la decisión de la persona en la tabla `decisiones`; el monitor la valida y la aplica.

```python
def _ejecutar_decision(d):
    """Valida la decisión y la aplica. Devuelve (resultado, detalle)."""
    if not any(config.dentro_de(d["ruta"], directorio) for directorio in config.RUTAS_MONITOREADAS):
        return "RECHAZADA", "El archivo está fuera de las rutas monitoreadas."
    if d["evento"] not in EVENTOS_DECIDIBLES:
        return "RECHAZADA", f"No se puede decidir sobre un evento {d['evento']}."

    if d["decision"] == INCIDENTE:
        return "EJECUTADA", "Cerrado como incidente: el archivo queda como en la baseline."

    if d["decision"] == RESTAURAR:
        resultado, _ = _procesar(d["ruta"], None, None, f"{d['decidido_por']} ({d['canal']})")
        if resultado in (RESTAURADO, SIN_CAMBIOS):
            return "EJECUTADA", "El archivo quedó como en la baseline."
        return "ERROR", f"No se pudo restaurar (resultado: {resultado})."

    if d["decision"] in (ACEPTAR, AUTORIZADO):
        return aceptar_cambio(d)

    return "RECHAZADA", f"Decisión desconocida: {d['decision']}."
```

### D.7 Aceptar un cambio en un único archivo (`generar_baseline.py`, líneas 97–140)

Aceptar un cambio genera una versión nueva de la línea base en la que solo cambia ese archivo; las
demás filas vigentes se copian tal cual.

```python
def actualizar_archivo(ruta, motivo):
    """Genera una versión nueva de la baseline donde solo cambia este archivo.

    Las demás filas vigentes se copian tal cual a la versión nueva; el archivo entra con su estado
    actual, o sale de la baseline si ya no existe. Así, aceptar un cambio no acepta de rebote otro
    cambio pendiente en otro archivo. Devuelve el número de la versión nueva.
    """
    ruta = os.path.abspath(ruta)
    if os.path.islink(ruta):
        raise ValueError(f"{ruta} es un enlace simbólico: la baseline solo admite archivos comunes.")
    with bd.candado:
        conn = bd.conectar()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COALESCE(MAX(version_baseline), 0) + 1 FROM registros_archivos "
                               "WHERE evento = 'BASELINE'")
                version = cursor.fetchone()[0]

                cursor.execute("""
                    INSERT INTO registros_archivos
                    (nombre_archivo, ruta_completa, hash_sha256, evento, owner_archivo, permisos, version_baseline)
                    SELECT nombre_archivo, ruta_completa, hash_sha256, 'BASELINE', owner_archivo, permisos, %s
                    FROM baseline_vigente WHERE ruta_completa <> %s
                """, (version, ruta))

                if os.path.isfile(ruta):
                    owner, permisos = leer_owner_y_permisos(ruta)
                    cursor.execute("""
                        INSERT INTO registros_archivos
                        (nombre_archivo, ruta_completa, hash_sha256, evento, owner_archivo, permisos,
                         version_baseline, detalles_diff)
                        VALUES (%s, %s, %s, 'BASELINE', %s, %s, %s, %s)
                    """, (os.path.basename(ruta), ruta, get_sha256(ruta), owner, permisos, version, motivo))
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # La bóveda acompaña a la baseline: copia nueva del archivo, o se borra si salió
    if os.path.isfile(ruta):
        boveda.respaldar(ruta)
    else:
        boveda.quitar(ruta)
    return version
```

### D.8 Apertura única sin seguir enlaces y copia de la evidencia (`monitor_fim.py`, líneas 132–173)

```python
def abrir_archivo(ruta):
    """Abre el archivo una sola vez, sin seguir enlaces. Devuelve (descriptor, destino_enlace):

    - (descriptor, None): es un archivo común. El hash, el diff y la copia a cuarentena se sacan
      todos de ese descriptor. Así se refieren al mismo archivo aunque después alguien cambie lo
      que hay en ese nombre (por otro archivo o por un enlace). Lo cierra quien llama.
    - (None, destino): es un enlace simbólico que apunta a destino. No se abre.
    - (None, None): no está en disco, no se puede leer o no es un archivo común.
    """
    try:
        # O_NOFOLLOW: si el último tramo de la ruta es un enlace, falla con ELOOP en vez de seguirlo.
        # O_NONBLOCK: no se queda esperando si lo que hay es una tubería (FIFO).
        descriptor = os.open(ruta, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as e:
        if e.errno == errno.ELOOP:
            try:
                return None, os.readlink(ruta)
            except OSError:
                pass
        return None, None
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        return None, None
    return descriptor, None

def copiar_evidencia(descriptor, destino):
    """Copia a la cuarentena el archivo ya abierto, en bloques, con sus permisos y fechas.

    Devuelve el SHA-256 de lo que copió, para poder compararlo con el hash registrado.
    """
    sha256_hash = hashlib.sha256()
    os.lseek(descriptor, 0, os.SEEK_SET)
    # "x": crea el archivo y falla si ya existía algo con ese nombre
    with open(destino, "xb") as copia:
        for bloque in iter(lambda: os.read(descriptor, 65536), b""):
            sha256_hash.update(bloque)
            copia.write(bloque)
        copia.flush()
        datos = os.fstat(descriptor)
        os.fchmod(copia.fileno(), stat.S_IMODE(datos.st_mode))
        os.utime(copia.fileno(), ns=(datos.st_atime_ns, datos.st_mtime_ns))
    return sha256_hash.hexdigest()
```

### D.9 Carpeta real del archivo (`monitor_fim.py`, líneas 182–195)

```python
def carpeta_real_fuera_de_la_raiz(ruta):
    """Si la carpeta del archivo, resolviendo enlaces, quedó fuera de su directorio vigilado,
    devuelve dónde está en realidad. Si sigue adentro (lo normal), devuelve None.

    Pasa cuando una carpeta del camino se reemplazó por un enlace simbólico: lstat y O_NOFOLLOW
    solo miran el último tramo de la ruta, no las carpetas intermedias.
    """
    for directorio in config.RUTAS_MONITOREADAS:
        if config.dentro_de(ruta, directorio):
            carpeta_real = os.path.realpath(os.path.dirname(ruta))
            if config.dentro_de(carpeta_real, os.path.realpath(directorio)):
                return None
            return carpeta_real
    return None
```

### D.10 Candado entre hilos y entre procesos (`monitor_fim.py`, líneas 50–75)

```python
# restaurar.py corre en otro proceso y también restaura: el candado de arriba no lo alcanza. Para
# que el monitor no procese un archivo mientras el otro proceso está a mitad de una restauración
# (y tome su temporal por un archivo nuevo), los dos piden además un candado del sistema operativo
# (flock) sobre este archivo de la carpeta de logs.
NOMBRE_CANDADO = "monitor.lock"
_veces_tomado = 0

@contextlib.contextmanager
def exclusion():
    """Un archivo a la vez: entre los hilos de este proceso y entre este proceso y restaurar.py."""
    global _veces_tomado
    with candado:
        descriptor = None
        if _veces_tomado == 0:
            # Solo lo pide la entrada de más afuera: como el candado de hilos, es reentrante
            carpeta = os.path.dirname(config.ARCHIVO_PENDIENTES)
            os.makedirs(carpeta, exist_ok=True)
            descriptor = os.open(os.path.join(carpeta, NOMBRE_CANDADO), os.O_RDONLY | os.O_CREAT, 0o644)
            fcntl.flock(descriptor, fcntl.LOCK_EX)   # espera si lo tiene otro proceso
        _veces_tomado += 1
        try:
            yield
        finally:
            _veces_tomado -= 1
            if descriptor is not None:
                os.close(descriptor)   # al cerrar el descriptor se suelta el candado
```

## Anexo E: Base de datos

Las migraciones están en `sql/`. La 01 es el esquema inicial exportado con `pg_dump`; las siguientes
lo amplían sin editarlo.

**Tabla E.1.** Migraciones de la base de datos.

| Migración | Qué hace |
|---|---|
| `01_schema.sql` | Tabla `registros_archivos` (esquema inicial). |
| `02_baseline_versionada.sql` | Columna `version_baseline`, índice único por ruta y versión, y vista `baseline_vigente`. |
| `03_fecha_con_zona.sql` | `fecha_registro` pasa a ser `TIMESTAMPTZ`. |
| `04_evidencia.sql` | Columnas `hash_anterior` y `ruta_cuarentena`. |
| `05_permisos_minimos.sql` | La tabla, la vista y la base pasan a ser de `postgres`; `fim_user` queda con `SELECT` e `INSERT`. |
| `06_orquestacion.sql` | Tablas `notificaciones`, `decisiones`, `ejecuciones`, `ventanas_mantenimiento` y `accesos_rechazados`, y rol `fim_n8n`. |

### E.1 Línea base vigente (`sql/02_baseline_versionada.sql`)

```sql
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
```

### E.2 Permisos mínimos de la cuenta del monitor (`sql/05_permisos_minimos.sql`)

```sql
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
```

### E.3 Decisiones, ejecuciones y rol de n8n (`sql/06_orquestacion.sql`, fragmento)

```sql
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

-- [...]

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
```

## Anexo F: Workflows de n8n y política del túnel

Los workflows están exportados en JSON en `n8n/` y se importan con `n8n/importar_workflows.sh`. Los
secretos no están en los archivos: se leen de variables de entorno, y las credenciales se referencian
por nombre.

**Tabla F.1.** Workflows de n8n.

| Workflow | Nodos | Qué hace |
|---|---|---|
| PB-B Detección y respuesta (`PB-B_deteccion_respuesta.json`) | 29 | Recibe el aviso del monitor, valida el secreto, lee el evento y su historial de la base de datos, envía la alerta por Telegram con el diff y los botones, ofrece enlaces locales de respaldo y confirma por Telegram cuando el monitor ejecutó la decisión. |
| PB-B Decisión por Telegram (`PB-B_decision_telegram.json`) | 12 | Recibe los toques de los botones (por ngrok), valida el `secret_token` y la cuenta, y registra la decisión. Los intentos desde otra cuenta quedan en `accesos_rechazados`. |
| PB-A Ventana de mantenimiento (`PB-A_baseline_autorizada.json`) | 6 | Formulario, con sesión de n8n obligatoria, para abrir una ventana de mantenimiento; registra quién la abrió. |
| Respaldo de notificaciones (`respaldo_notificaciones.json`) | 3 | Cada minuto reenvía a PB-B los eventos de la última hora que quedaron sin notificar. |

**Tabla F.2.** Opciones de cada alerta.

| El monitor... | Opciones |
|---|---|
| restauró el archivo (modo automático) o aisló un archivo nuevo | *Fue un incidente* / *Era un cambio autorizado* |
| dejó el archivo a la espera (modo aprobación) | *Restaurar* / *Aceptar cambio* |
| registró un cambio dentro de una ventana de mantenimiento | *Pasar a la baseline* / *Restaurar* |

### F.1 Política del túnel ngrok (`n8n/ngrok_politica.yml`)

El script `n8n/iniciar_ngrok.sh` reemplaza el marcador `__TELEGRAM_WEBHOOK_SUFIJO__` por el valor
del `.env` en un archivo temporal, de modo que el sufijo nunca queda en el repositorio.

```yaml
on_http_request:
  - name: solo-el-webhook-de-telegram
    expressions:
      - "req.method != 'POST' || req.url.path != '/webhook/telegram-__TELEGRAM_WEBHOOK_SUFIJO__'"
    actions:
      - type: deny
        config:
          status_code: 404
```

## Anexo G: Cómo reproducir la instalación y las mediciones

Entorno usado: Ubuntu sobre WSL2, Python 3 con un entorno virtual, PostgreSQL local y n8n 2.41.4
sobre Node 24. Las versiones exactas del entorno de medición están en `resultados/entorno_*.json`, y
la instalación de n8n se detalla en `n8n/README.md`.

### G.1 Instalación del sistema

```bash
sudo service postgresql start
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # completar credenciales y secretos

# Migraciones: de la 01 a la 04 como fim_user; la 05 y la 06, como superusuario
for m in sql/0[1-4]_*.sql; do psql -v ON_ERROR_STOP=1 -h localhost -U fim_user -d fim_db -f "$m"; done
sudo -u postgres psql -v ON_ERROR_STOP=1 -d fim_db < sql/05_permisos_minimos.sql
sudo -u postgres psql -v ON_ERROR_STOP=1 -d fim_db < sql/06_orquestacion.sql

python generar_baseline.py    # línea base y bóveda
python monitor_fim.py         # monitor
pytest                        # tests automatizados
```

### G.2 Mediciones

Todas las mediciones, salvo la muestra con Telegram real, usan la base de datos de pruebas
`fim_pruebas` y un n8n descartable con Telegram simulado, sin tocar la instalación real.

```bash
./scripts/preparar_bd_pruebas.sh       # fim_pruebas vacía, con el esquema de fim_db
./scripts/n8n_de_pruebas.sh iniciar    # n8n de pruebas (puerto 5690)

python scripts/medir_metricas.py --repeticiones 50       # MTTD, MTTR, alerta y ejecución
python scripts/medir_falsos_positivos.py --ediciones 20  # vim y nano, con y sin filtro
python scripts/medir_escaneo_periodico.py                # escaneo completo y cron de 10 s

./scripts/n8n_de_pruebas.sh detener

# Muestra con el bot real (con la instalación real en marcha; solo lee fim_db)
python scripts/medir_metricas.py --telegram-real --repeticiones 10

# Resumen (media, mediana, p95, mínimo y máximo) y gráfico de las métricas;
# README de resultados
python scripts/resumir_metricas.py resultados/metricas_<fecha>.csv
python scripts/armar_readme_resultados.py

# Intervalos de confianza de las medianas (sobre los CSV de octubre)
python scripts/intervalos_bootstrap.py
```

## Anexo H: Resultados versionados

Los datos en los que se basa el Capítulo 5 están en `resultados/`, tal como salieron de los scripts.
Los archivos con fecha de octubre corresponden a las secciones 5.1 a 5.8 y los del 17 de noviembre, a
la sección 5.9.

**Tabla H.1.** Archivos de resultados.

| Archivo | Contenido |
|---|---|
| `metricas_20261015_232407.csv` | Una fila por repetición: caso, repetición y cada latencia en ms (50 repeticiones por caso). |
| `resumen_20261015_232407.csv` / `.md` | Resumen por caso y métrica. |
| `grafico_20261015_232407.png` | Gráfico de cajas por caso (Figura 5.1). |
| `entorno_metricas_20261015_232407.json` | Versiones y características del entorno de medición. |
| `alerta_telegram_real_20261016_000516.csv` | Muestra de diez alertas con el bot real, con el identificador de cada evento. |
| `resumen_telegram_real_20261016_000516.csv` / `.md` | Resumen de la muestra real. |
| `grafico_telegram_real_20261016_000516.png` | Gráfico de la muestra real. |
| `entorno_alerta_telegram_real_20261016_000516.json` | Entorno de la muestra real. |
| `falsos_positivos_20261015_233331.csv` | Ediciones con vim y nano, con y sin filtro de temporales. |
| `resumen_falsos_positivos_20261015_233331.md` | Proporción de alertas espurias por corrida y editor (el archivo la rotula "tasa de falsos positivos"). |
| `escaneo_periodico_20261015_235418.csv` | Duración del escaneo completo y validación con un período de 10 s. |
| `resumen_escaneo_periodico_20261015_235418.md` | Resumen del escaneo periódico. |
| `metricas_20261117_195343.csv` y `metricas_20261117_200705.csv` | Corridas B1 y B2 sobre la versión corregida (sección 5.9), con el mismo formato que la de octubre. |
| `resumen_20261117_195343.csv` / `.md` y `resumen_20261117_200705.csv` / `.md` | Resumen por caso y métrica de B1 y B2. |
| `grafico_20261117_195343.png` y `grafico_20261117_200705.png` | Gráficos de cajas de B1 y B2. |
| `entorno_metricas_20261117_195343.json` y `entorno_metricas_20261117_200705.json` | Entorno de B1 y B2. |
| `falsos_positivos_20261117_200051.csv` y `resumen_falsos_positivos_20261117_200051.md` | Ediciones con vim y nano sobre la versión corregida. |
| `intervalos_bootstrap_20261015.csv` / `.md` | Intervalos de confianza del 95 % de las medianas de octubre (sección 5.10). |
| `README.md` | Lectura de los resultados, comparación con la tabla supuesta del documento de diseño y comparación entre la versión de octubre y la corregida (sección 6). |

## Anexo I: Respuesta a la devolución de la primera instancia

El tribunal pidió, junto con la versión corregida, una tabla de respuesta por cada hallazgo de la
devolución. Las páginas corresponden a este documento y los commits, al repositorio del Anexo A.
Donde una corrección no se pudo cumplir del todo, se indica en la misma fila.

**Tabla I.1.** Respuesta a cada hallazgo de la devolución.

| ID | Hallazgo | Qué se cambió | Sección y página | Commit |
|---|---|---|---|---|
| C1 | Uso no declarado de un asistente de IA generativa en el código y en la redacción. | Se agregó la Declaración de uso de herramientas de IA generativa en los preliminares: herramientas y modelos, para qué se usaron, qué hizo el autor y cómo verificó lo generado. 3.2 remite a ella y 4.10 suma las tres herramientas. | Declaración (p. 4); 3.2 (p. 23); 4.10 (p. 46) | `e04b737` |
| M1 | Marco teórico sin estado del arte y con pocas fuentes académicas. | Sección 2.9 con antecedentes, tabla comparativa de ocho herramientas y mecanismos (Tabla 2.1) y un cierre con la brecha y el aporte. Citas para Tripwire y AIDE en 1.2 y para SOAR y playbooks en 2.5. Diecisiete referencias nuevas, todas abiertas y verificadas. No se pudo cumplir del todo: se buscó y no se pudo verificar en su fuente oficial el requisito 11.5.2 de PCI DSS v4.0, una definición normativa de MTTD y MTTR, una fuente para *human-in-the-loop* ni el contenido de la guía de SIEM y SOAR de CISA; no se citan y las afirmaciones se acotaron (2.5 y 2.6). De Kim y Spafford (1994) se verificó la ficha bibliográfica, no el texto completo; de Peddoju et al. (2020) y Salman et al. (2022), los resúmenes. | 2.9 (p. 19); 1.2 (p. 12); 2.5 (p. 17); 2.6 (p. 18); Referencias (p. 70) | `7b47110`, `9875245` |
| M2 | La restauración seguía enlaces simbólicos en un temporal de nombre predecible, y ese prefijo nunca se vigilaba. | Código: temporal de nombre aleatorio con apertura exclusiva, el filtro ignora solo los temporales propios y el reemplazo de un archivo por un enlace se detecta sin seguirlo, con la prueba de concepto del tribunal como prueba automatizada. Informe: 4.3 y 4.4 explican cada medida, 5.9 mide el efecto con una nueva corrida, y los Anexos A y D se actualizaron al commit final `39c661c`. No queda cerrado del todo: 6.4 declara las limitaciones que quedan (enlaces simbólicos no soportados, intervalo entre comprobar la carpeta y escribir, escrituras que siguen sobre el mismo archivo, archivo nuevo movido por nombre, diff en memoria y lecturas por nombre) y 7.1 condiciona a ellas la ejecución como superusuario. | 4.3 (p. 33); 4.4 (p. 35); 5.9 (p. 55); 6.4 (p. 62); 7.1 (p. 67); Anexo A (p. 73); Anexo D (p. 76) | Código: `1701769`, `3b246fe`, `3a44743`. Informe: `409d553`, `05245c4`. Resultados: `da4ed7a` |
| M3 | La "tasa de falsos positivos" no era la convencional. | La métrica pasa a llamarse proporción de alertas espurias en todo el informe. 3.3 la define una sola vez, con la fórmula FP / (VP + FP), y explica la diferencia con FP / (FP + VN) y por qué acá no hay verdaderos negativos contables. Los scripts y los CSV conservan su nombre, con una nota. | Resumen (p. 2); 2.6 (p. 18); 3.3 (p. 24); 5.5 (p. 50); 5.7 (p. 52); 6.3 (p. 61) | `c7fe6bc` |
| m1 | 4.7 hablaba de dos canales de decisión y `restaurar.py` era un tercero. | 4.7 describe los tres caminos y cómo conviven con la regla de una decisión por evento. Se corrigió el comentario de `.env.example`. Que `restaurar.py` no registre una decisión ni avise a n8n queda como limitación (6.4) y como trabajo futuro (7.2). | 4.7 (p. 41); 6.4 (p. 62); 7.2 (p. 68); Anexo C (p. 75) | `2488e91`, `3cded82` |
| m2 | 4.6 y D.5 describían distinto el aviso a n8n. | Los dos textos dicen lo mismo que el código: tipo de aviso, identificador del evento y resultado. | 4.6 (p. 40); D.5 (p. 80) | `0b14bfc` |
| m3 | "Compatible con la variabilidad esperable" sin cálculo. | Se agregó el cálculo, rehecho desde el CSV: la diferencia equivale a 1,1 errores estándar. | 5.6 (p. 51) | `fd51288`, `286da13` |
| m4 | Las medianas no tenían intervalos de confianza. | Intervalos de confianza del 95 % por bootstrap para las medianas principales, en una tabla aparte (Tabla 5.13), con el método descripto en 3.6. | 3.6 (p. 28); 5.10 (p. 58) | `3eabf6f` |
| m5 | "De los 15 valores medidos": el CSV tiene 19. | Se aclara que los 15 excluyen los 4 valores del control y que el control del borrado (401,2 ms) también es máximo. | 5.8 (p. 53) | `5786f9d` |
| m6 | "Esto reduce el tiempo de análisis" no se midió. | Queda formulado como expectativa de diseño, y se dice que no se midió. | 1.3 (p. 13) | `e9028c1` |
| m7 | La afirmación sobre las PyMEs no tenía fuente. | No apareció una fuente verificable. La afirmación se acotó: es el escenario para el que se diseñó el sistema, no un dato sobre el conjunto de las PyMEs. | 1.2 (p. 12) | `6053f82` |
| m8 | Una prueba de `tests/test_permisos.py` fallaba al ejecutarse como superusuario. | La prueba se saltea con `skipif(os.geteuid() == 0)`. | Código (`tests/test_permisos.py`) | `80ba02c` |
| m9 | Las definiciones de las métricas se repetían en 3.3 y 5.1. | Quedan solo en 3.3; 5.1 remite a ellas. | 3.3 (p. 24); 5.1 (p. 47) | `daceb94` |
| f1 | Las líneas de código largas se cortaban en los anexos. | Las líneas de más de 90 caracteres se parten al armar el documento: la continuación conserva la sangría y repite el signo de comentario o empieza con la marca ». Verificado en el PDF línea por línea. | Anexo C (p. 75); Anexo D (p. 76) | `3a7401f` |
| f2 | Nombres de archivo partidos en las tablas. | El ancho de cada columna asegura primero su palabra más larga. | 3.5 (p. 27); Tabla 4.2 (p. 39); Tabla E.1 (p. 84); Tabla H.1 (p. 87) | `d83bdde` |
| f3 | Espaciado inconsistente de las unidades. | Espacio fino de no separación entre cada número y su unidad. | Todo el documento | `9c3400e` |
| f4 | Faltaban el índice de figuras, el de tablas y la lista de siglas. | Se agregaron después del índice general. | Índice de figuras (p. 9); Índice de tablas (p. 10); Lista de siglas (p. 11) | `27a7498` |
| f5 | La portada decía "Docentes" sin el rol y no había Abstract. | La portada indica los directores de tesis y el título al que se aspira. Se agregó el Abstract con sus palabras clave. | Portada (p. 1); Abstract (p. 3) | `a79a810` |
| f6 | La Figura 5.1 quedaba aplastada por un atípico y la Figura 4.3 mostraba URL firmadas. | Figura 5.1 en escala logarítmica, con el atípico anotado. Se ocultó la firma de los enlaces en las Figuras 4.2 y 4.3. | Figura 5.1 (p. 55); Figura 4.2 (p. 43); Figura 4.3 (p. 44) | `ea782d2` |

Al corregir el hallazgo M2 se revisó si el mismo problema (seguir enlaces, o verificar y usar en
momentos distintos) existía en otras partes del sistema. Se encontraron y corrigieron los defectos
de la Tabla I.2, que el tribunal no había pedido. Cada uno tiene su prueba automatizada.

**Tabla I.2.** Correcciones adicionales no pedidas.

| Defecto encontrado | Corrección | Commit |
|---|---|---|
| Si una carpeta del camino se reemplazaba por un enlace, la restauración escribía fuera del directorio vigilado. | Se comprueba la carpeta real antes de leer y antes de restaurar; si quedó afuera, no se lee ni se escribe. | `15d201d` |
| El hash, el diff y la copia a cuarentena abrían el archivo tres veces por su nombre. | Una sola apertura sin seguir enlaces; las tres lecturas salen del mismo descriptor. | `86d9c00` |
| Los permisos y el propietario se reponían por nombre, siguiendo enlaces. | Se reponen sobre el descriptor (`fchmod`, `fchown`); al aceptar un evento `PERMISOS` se comprueba que siga habiendo un archivo común. | `7110ae5` |
| El monitor podía tomar por un archivo nuevo el temporal de una restauración hecha por `restaurar.py`. | Candado entre procesos (`flock`). | `2347c6f` |
| El generador de línea base seguía los enlaces simbólicos. | Los saltea y los lista por pantalla. | `605ce54` |
| El escaneo inicial no veía los enlaces a directorios. | Los incluye entre las rutas a verificar. | `83afcf7` |
| Un enlace nuevo se eliminaba también en modo de aprobación. | En ese modo se registra, se avisa y espera la decisión. | `39c661c` |

Antes de la entrega, el autor leyó el informe completo y lo contrastó otra vez con el código del
commit `39c661c` y con los CSV. No se cambió código ni se hicieron mediciones nuevas: se corrigieron
o aclararon los puntos de la Tabla I.3. Lo referido a inotify se comprobó con el monitor sobre la
base de pruebas. También se revisó la cita de Salman et al. (2022) contra su resumen, que no requirió
cambios.

**Tabla I.3.** Ajustes de la revisión final del autor.

| Tema | Qué se ajustó | Sección | Commit |
|---|---|---|---|
| `/etc` como destino | Ya no se presenta como aplicable: la versión actual no admite los enlaces simbólicos que contiene. | 1.5; Anexo C | `9ef2684` |
| Atribución del cambio | La integridad se define como detectable; el sistema no registra qué usuario o proceso hizo el cambio. | 2.1; 6.4 | `9ef2684` |
| Costo de adopción | La fila propia de la Tabla 2.1 suma Node.js, Telegram y ngrok; "liviana" se reemplaza por "de un solo equipo" y se aclara que el consumo no se comparó. | 2.9; 6.5 | `9ef2684` |
| Escala de la evaluación | Se indica la cantidad de archivos vigilados: cinco, y dos en la corrida de editores. | 3.4; 5.8; 6.4 | `9ef2684` |
| Objetivo 3 y ruta pública | El objetivo 3 lleva la salvedad de los enlaces simbólicos; la única ruta pública se reconcilia con las variantes codificadas. | Tabla 6.1; 3.7; 4.7; 6.3 | `9ef2684` |
| Referencias | Las referencias nuevas de M1 son diecisiete. El documento de diseño se presenta como material de cátedra con valores supuestos y entra en las Referencias. | 3.6; 4.6; 5.7; Referencias; Tabla I.1 | `9ef2684` |
| Declaración de IA | Se precisa cómo se ejecutaron y revisaron las pruebas y las mediciones, y la decisión sobre las referencias no verificadas. | Declaración | `9ef2684` |
| Qué mide cada tiempo | "Tiempo real" en sentido operativo y sin umbral previo; `t0` posterior al evento del kernel; marca de detección anterior al COMMIT; alerta medida hasta que la API de Telegram acepta el mensaje. | 1.2; 1.4.1; 3.3; 5.3; 5.8 | `716131d` |
| Comparación entre corridas | El umbral de 35 ms es descriptivo; se justifica el uso de los valores de octubre y se agregan los de B2. | 5.9; 6.1 | `716131d` |
| Alcance de dos mediciones | El 0 % de alertas espurias vale para vim y nano por defecto; los 9,7 ms del escaneo no representan a `/etc` ni a `/usr/bin`. | 5.5; 5.6 | `716131d` |
| Limitaciones que faltaba declarar | Enlaces duros externos, directorios nuevos, desborde de la cola de inotify, bóveda alterada, archivos nuevos legítimos, línea base falsificable con la cuenta del monitor, diff sin enmascarar, motivo de la respuesta fallida, y repetición de alertas en modo de aprobación. | 4.4; 6.4; 7.1; 7.2; D.3 | `e7c40b2` |
