import time
import difflib
import os
import sys
import threading
import shutil  # NUEVO: Librería para mover archivos a cuarentena
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import bd
import boveda
import config
import generar_baseline
import notificador
import pendientes
from filtros import es_ignorado
from hashes import get_sha256
from metadatos import leer_owner_y_permisos

# Resultados posibles de comparar un archivo con la baseline.
# Salvo SIN_CAMBIOS, son también el valor de la columna evento.
SIN_CAMBIOS = "SIN_CAMBIOS"
MODIFICADO = "MODIFICADO"
CREADO = "CREADO"
ELIMINADO = "ELIMINADO"
MOVIDO = "MOVIDO"
PERMISOS = "PERMISOS"
RESTAURADO = "RESTAURADO"

# Otros resultados de procesar() que no son eventos de la BD
PENDIENTE = "PENDIENTE"            # detectado, esperando aprobación para restaurar
NO_RESTAURADO = "NO_RESTAURADO"    # no se pudo restaurar (bóveda no confiable, falta root, error)
SIN_VERIFICAR = "SIN_VERIFICAR"    # no se pudo consultar la baseline
AUTORIZADO = "AUTORIZADO"          # cambio dentro de una ventana de mantenimiento: no se restaura

# En modo aprobación: cambios ya avisados que siguen sin restaurar, para no repetir el registro
# cada vez que llega otro evento del mismo archivo. ruta -> (estado, hash, owner, permisos)
avisados = {}

# El escaneo inicial, los eventos de watchdog y las decisiones que llegan de n8n corren en hilos
# distintos: el candado hace que los archivos se procesen de a uno. Es reentrante porque ejecutar
# una decisión de restaurar vuelve a pasar por procesar().
candado = threading.RLock()

# Decisiones humanas (las inserta n8n en la tabla decisiones; el monitor las ejecuta)
INCIDENTE = "INCIDENTE"      # ya restaurado: fue un incidente, no se hace nada más
RESTAURAR = "RESTAURAR"      # pendiente: restaurar desde la bóveda
ACEPTAR = "ACEPTAR"          # pendiente: el cambio pasa a la baseline
# AUTORIZADO (ya restaurado, pero era un cambio autorizado) hace lo mismo que ACEPTAR
EVENTOS_DECIDIBLES = {MODIFICADO, CREADO, ELIMINADO, MOVIDO, PERMISOS}

# Cada cuánto se buscan decisiones nuevas en la BD (segundos)
INTERVALO_DECISIONES = 2

# Decisiones ya ejecutadas por este proceso, por si no se pudo registrar la ejecución en la BD
decisiones_ejecutadas = set()

def leer_archivo_texto(ruta):
    """Lee las líneas de un archivo de texto. Devuelve None si es binario o no se puede leer."""
    try:
        with open(ruta, 'rb') as f:
            contenido = f.read()
        if b'\x00' in contenido:
            return None
        return contenido.decode('utf-8').splitlines(keepends=True)
    except Exception:
        return None

def calcular_diff(ruta_antes, ruta_ahora):
    """Compara la copia de la bóveda con el archivo actual y devuelve la evidencia."""
    lineas_viejas = leer_archivo_texto(ruta_antes)
    lineas_nuevas = leer_archivo_texto(ruta_ahora)
    if lineas_viejas is None or lineas_nuevas is None:
        return "Archivo binario: no se genera diff de texto. La evidencia es el cambio de hash."
    diff_gen = difflib.unified_diff(lineas_viejas, lineas_nuevas, fromfile='Antes', tofile='Ahora')
    return ''.join(list(diff_gen))

def obtener_baseline(ruta):
    """Devuelve hash, permisos y owner del archivo en la baseline vigente de la BD, o None si no figura."""
    filas = bd.ejecutar(
        "SELECT hash_sha256, permisos, owner_archivo FROM baseline_vigente WHERE ruta_completa = %s", (ruta,))
    if not filas:
        return None
    return {"hash": filas[0][0], "permisos": filas[0][1], "owner": filas[0][2]}

def rutas_de_la_baseline():
    """Devuelve las rutas de todos los archivos de la baseline vigente."""
    filas = bd.ejecutar("SELECT ruta_completa FROM baseline_vigente ORDER BY ruta_completa")
    return [fila[0] for fila in filas]

def verificar(ruta, hash_actual, owner=None, permisos=None):
    """Compara el estado actual del archivo (hash None si no está en disco) con la baseline vigente.

    Devuelve (estado, baseline). El estado es SIN_CAMBIOS, MODIFICADO, CREADO, ELIMINADO o PERMISOS.
    """
    baseline = obtener_baseline(ruta)
    if baseline is None:
        # No figura en la baseline: si existe es un archivo nuevo; si no existe, no hay nada que mirar
        return (SIN_CAMBIOS if hash_actual is None else CREADO), None
    if hash_actual is None:
        return ELIMINADO, baseline
    if hash_actual != baseline["hash"]:
        return MODIFICADO, baseline
    # Mismo contenido: falta ver que no le hayan cambiado los permisos o el dueño
    if (owner, permisos) != (baseline["owner"], baseline["permisos"]):
        return PERMISOS, baseline
    return SIN_CAMBIOS, baseline

def ventanas_vigentes():
    """Devuelve [(id, ruta)] de las ventanas de mantenimiento abiertas en este momento."""
    return bd.ejecutar("SELECT id, ruta FROM ventanas_mantenimiento "
                       "WHERE desde <= CURRENT_TIMESTAMP AND hasta > CURRENT_TIMESTAMP ORDER BY id")

def ventana_que_autoriza(ruta):
    """Devuelve el id de una ventana vigente que cubra la ruta (el archivo o un directorio que lo
    contiene), o None. Si no se puede consultar, no hay autorización: ante la duda se responde."""
    try:
        ventanas = ventanas_vigentes()
    except Exception as e:
        print(f"[!] No se pudieron consultar las ventanas de mantenimiento: {e}")
        return None
    for ventana_id, ruta_ventana in ventanas:
        if config.dentro_de(ruta, ruta_ventana):
            return ventana_id
    return None

def respaldo_confiable(ruta, hash_baseline):
    """Indica si la copia de la bóveda existe y tiene el mismo hash que la baseline."""
    return get_sha256(boveda.ruta_en_boveda(ruta)) == hash_baseline

def nueva_ruta_cuarentena(nombre):
    """Arma el nombre de la copia en cuarentena y crea la carpeta si hace falta."""
    os.makedirs(config.DIRECTORIO_CUARENTENA, exist_ok=True)
    # El nombre lleva microsegundos para que dos eventos seguidos no se pisen
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return os.path.join(config.DIRECTORIO_CUARENTENA, f"{timestamp}_{nombre}")

def log_to_db(nombre_archivo, ruta_completa, hash_sha256, evento, detalles_diff="",
              hash_anterior=None, ruta_cuarentena=None):
    """Guarda el evento y la evidencia en PostgreSQL y devuelve su id.

    Si la BD falla, lo deja en el log local y devuelve None.
    """
    owner, permisos = leer_owner_y_permisos(ruta_completa)
    try:
        query = """
            INSERT INTO registros_archivos 
            (nombre_archivo, ruta_completa, hash_sha256, evento, detalles_diff, owner_archivo, permisos,
             hash_anterior, ruta_cuarentena) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        # Se reutiliza la conexión del proceso en vez de abrir una por evento
        filas = bd.ejecutar(query, (nombre_archivo, ruta_completa, hash_sha256, evento, detalles_diff, owner, permisos,
                            hash_anterior, ruta_cuarentena))
        return filas[0][0]
    except Exception as e:
        print(f"Error en BD: {e}")
        pendientes.guardar({
            "evento": evento, "nombre_archivo": nombre_archivo, "ruta_completa": ruta_completa,
            "hash_sha256": hash_sha256, "hash_anterior": hash_anterior, "detalles_diff": detalles_diff,
            "owner_archivo": owner, "permisos": permisos, "ruta_cuarentena": ruta_cuarentena,
            "motivo": str(e),
        })
        print(f"[*] Evento guardado en {config.ARCHIVO_PENDIENTES}")
        return None

def guardar_sin_verificar(nombre, ruta, hash_actual, error):
    """Sin acceso a la baseline no se sabe si el cambio es legítimo: se guarda la evidencia y no se restaura."""
    respaldo = boveda.ruta_en_boveda(ruta)
    hash_boveda = get_sha256(respaldo)

    # Si el archivo es igual a su copia en la bóveda, lo más probable es que no haya cambiado
    if hash_actual == hash_boveda:
        return

    ruta_cuarentena = None
    if hash_actual is None:
        texto_diff = "El archivo no está en disco."
    else:
        ruta_cuarentena = nueva_ruta_cuarentena(nombre)
        shutil.copy2(ruta, ruta_cuarentena)
        if hash_boveda is None:
            texto_diff = "Sin copia en la bóveda para comparar."
        else:
            texto_diff = calcular_diff(respaldo, ruta)

    owner, permisos = leer_owner_y_permisos(ruta)
    pendientes.guardar({
        "evento": "SIN_VERIFICAR", "nombre_archivo": nombre, "ruta_completa": ruta,
        "hash_sha256": hash_actual, "hash_boveda": hash_boveda, "detalles_diff": texto_diff,
        "owner_archivo": owner, "permisos": permisos, "ruta_cuarentena": ruta_cuarentena,
        "motivo": str(error),
    })
    print(f"[+] Evidencia en {ruta_cuarentena} y evento guardado en {config.ARCHIVO_PENDIENTES}")

def responder_a_permisos(nombre, ruta, h, owner, permisos, baseline, aprobado_por=None):
    """El contenido está intacto pero cambiaron los permisos o el dueño: se registra y se reponen.

    Devuelve (resultado, id del evento registrado).
    """
    cambios = []
    if permisos != baseline["permisos"]:
        cambios.append(f"Permisos: {baseline['permisos']} -> {permisos}.")
    if owner != baseline["owner"]:
        cambios.append(f"Propietario (uid): {baseline['owner']} -> {owner}.")
    detalle = " ".join(cambios)

    # Si viene de restaurar.py, la detección ya la registró el monitor
    evento_id = None
    if aprobado_por is None:
        evento_id = log_to_db(nombre, ruta, h, PERMISOS, detalle, hash_anterior=baseline["hash"])
        print(f"[!] ALERTA: Archivo PERMISOS -> {nombre}")
        print(f"Evidencia:\n{detalle}\n")

    if not se_restaura_ahora(aprobado_por):
        avisar_pendiente(ruta)
        return PENDIENTE, evento_id

    print("[*] Iniciando protocolo de Respuesta Automatizada...")
    resultado = NO_RESTAURADO
    try:
        os.chmod(ruta, int(baseline["permisos"], 8))
        if owner != baseline["owner"]:
            # Cambiar el dueño de un archivo solo lo puede hacer root
            os.chown(ruta, int(baseline["owner"]), -1)
        log_to_db(nombre, ruta, h, RESTAURADO,
                  "Permisos y propietario repuestos según la baseline" + firma_de_aprobacion(aprobado_por),
                  hash_anterior=h)
        print("[+] RESTAURACIÓN EXITOSA: Permisos y propietario repuestos.")
        resultado = RESTAURADO
    except PermissionError as e:
        print(f"[-] NO SE PUDO RESTAURAR (hace falta correr como root): {e}")
    except Exception as e:
        print(f"[-] Error en la respuesta automatizada: {e}")
    print("-" * 50)
    return resultado, evento_id

def se_restaura_ahora(aprobado_por):
    """En modo automático se restaura siempre; en modo aprobación, solo si alguien lo aprobó."""
    return config.MODO_RESTAURACION == "automatica" or aprobado_por is not None

def firma_de_aprobacion(aprobado_por):
    """Texto que deja constancia de quién aprobó la restauración (vacío en modo automático)."""
    if aprobado_por is None:
        return "."
    return f", con aprobación de {aprobado_por}."

def avisar_pendiente(ruta):
    print("[*] PENDIENTE DE APROBACIÓN: no se restaura. Para restaurar, ejecutá:")
    print(f"    python restaurar.py '{ruta}'")
    print("-" * 50)

def registrar_autorizado(nombre, ruta, h, owner, permisos, estado, baseline, ventana_id, movido_a=None):
    """Un cambio dentro de una ventana de mantenimiento: queda registrado con su evidencia, sin restaurar.

    Mientras el archivo siga igual, los eventos repetidos no generan otra fila.
    """
    if avisados.get(ruta) == (AUTORIZADO, h, owner, permisos):
        return AUTORIZADO, None
    avisados[ruta] = (AUTORIZADO, h, owner, permisos)

    evento = MOVIDO if estado == ELIMINADO and movido_a else estado
    hash_baseline = baseline["hash"] if baseline else None
    detalle = f"Cambio autorizado por la ventana de mantenimiento #{ventana_id}: no se restaura."
    if estado == MODIFICADO and boveda.tiene_respaldo(ruta):
        detalle += "\n" + calcular_diff(boveda.ruta_en_boveda(ruta), ruta)

    # La copia en cuarentena queda como registro de lo que se cambió (no se mueve el archivo)
    ruta_cuarentena = None
    if h is not None:
        ruta_cuarentena = nueva_ruta_cuarentena(nombre)
        shutil.copy2(ruta, ruta_cuarentena)

    evento_id = log_to_db(nombre, ruta, h, evento, detalle,
                          hash_anterior=hash_baseline, ruta_cuarentena=ruta_cuarentena)
    print(f"[*] Archivo {evento} -> {nombre}: autorizado por la ventana de mantenimiento #{ventana_id}.")
    print("-" * 50)
    return AUTORIZADO, evento_id

def procesar(ruta, movido_a=None, movido_desde=None, aprobado_por=None):
    """Compara un archivo con la baseline y, si hubo un cambio, lo registra, responde y avisa a n8n.

    La llaman los eventos de watchdog y el escaneo inicial: el evento es solo el disparador.
    movido_a y movido_desde solo agregan contexto cuando el disparador fue un movimiento.
    aprobado_por lo pasa restaurar.py: es quien autorizó la restauración en modo aprobación.
    Devuelve qué pasó: SIN_CAMBIOS, RESTAURADO, PENDIENTE, NO_RESTAURADO, CREADO o SIN_VERIFICAR.
    """
    with candado:
        resultado, evento_id = _procesar(os.path.abspath(ruta), movido_a, movido_desde, aprobado_por)

    # El aviso sale después de responder: no suma tiempo a la detección ni a la restauración
    if evento_id is not None:
        notificador.notificar({"tipo": "evento", "evento_id": evento_id, "resultado": resultado})
    return resultado

def _procesar(ruta, movido_a, movido_desde, aprobado_por):
    """Hace el trabajo de procesar(). Devuelve (resultado, id del evento registrado o None)."""
    nombre = os.path.basename(ruta)

    # Temporales de editores y de nuestra propia restauración: no se vigilan
    if es_ignorado(ruta):
        return SIN_CAMBIOS, None

    # None si el archivo no está en disco
    h = get_sha256(ruta)

    if h is None and os.path.lexists(ruta):
        if os.path.isfile(ruta):
            print(f"[!] No se pudo leer {ruta}: no se puede verificar.")
        return SIN_VERIFICAR, None

    owner, permisos = leer_owner_y_permisos(ruta)

    # La verdad está en la baseline de la BD
    try:
        estado, baseline = verificar(ruta, h, owner, permisos)
    except Exception as e:
        print(f"[!] ALERTA: no se pudo consultar la baseline para verificar {nombre}: {e}")
        print("    Sin baseline no se restaura. Revisá que PostgreSQL esté levantado.")
        guardar_sin_verificar(nombre, ruta, h, e)
        return SIN_VERIFICAR, None

    if estado == SIN_CAMBIOS:
        avisados.pop(ruta, None)
        return SIN_CAMBIOS, None

    # Cambio autorizado de antemano (PB-A): se registra con su evidencia pero no se toca el archivo
    if aprobado_por is None:
        ventana_id = ventana_que_autoriza(ruta)
        if ventana_id is not None:
            return registrar_autorizado(nombre, ruta, h, owner, permisos, estado, baseline, ventana_id, movido_a)

    # En modo aprobación el archivo queda alterado hasta que alguien aprueba:
    # el mismo cambio se registra una sola vez
    if not se_restaura_ahora(aprobado_por) and estado != CREADO:
        if avisados.get(ruta) == (estado, h, owner, permisos):
            return PENDIENTE, None
        avisados[ruta] = (estado, h, owner, permisos)

    if estado == PERMISOS:
        return responder_a_permisos(nombre, ruta, h, owner, permisos, baseline, aprobado_por)

    if estado == CREADO and aprobado_por is not None:
        print(f"[-] {ruta} no está en la baseline: no hay nada que restaurar.")
        return CREADO, None

    hash_baseline = baseline["hash"] if baseline else None

    # Un archivo de la baseline que falta porque lo movieron se registra como MOVIDO
    evento = MOVIDO if estado == ELIMINADO and movido_a else estado

    respaldo = boveda.ruta_en_boveda(ruta)

    # Solo se restaura si la copia de la bóveda sigue siendo la de la baseline
    restaurable = estado != CREADO and respaldo_confiable(ruta, hash_baseline)

    # La evidencia: qué pasó y, si se modificó el contenido, el Diff exacto
    if estado == CREADO:
        texto_diff = "Archivo que no está en la baseline vigente."
        if movido_desde:
            texto_diff += f" Llegó movido desde {movido_desde}."
    elif evento == MOVIDO:
        texto_diff = f"El archivo de la baseline fue movido a {movido_a}."
    elif estado == ELIMINADO:
        texto_diff = "El archivo de la baseline fue eliminado."
    elif restaurable:
        texto_diff = calcular_diff(respaldo, ruta)
    else:
        texto_diff = ""
    if estado != CREADO and not restaurable:
        texto_diff = (texto_diff + " BÓVEDA NO CONFIABLE: la copia de respaldo falta o no coincide "
                      "con la baseline. No se restaura.").strip()

    # Solo hay algo para guardar en cuarentena si el archivo está en disco
    ruta_cuarentena = nueva_ruta_cuarentena(nombre) if h is not None else None

    # Si viene de restaurar.py, la detección ya la registró el monitor
    evento_id = None
    if aprobado_por is None:
        evento_id = log_to_db(nombre, ruta, h, evento, texto_diff,
                              hash_anterior=hash_baseline, ruta_cuarentena=ruta_cuarentena)
        print(f"[!] ALERTA: Archivo {evento} -> {nombre}")
        print(f"Evidencia:\n{texto_diff}\n")

    # --- INICIO RESPUESTA AUTOMATIZADA ---
    print("[*] Iniciando protocolo de Respuesta Automatizada...")

    resultado = NO_RESTAURADO
    try:
        if estado == CREADO:
            # Archivo que no está en la baseline: se aísla y no hay nada que restaurar.
            # Es automático en los dos modos: es una contención y se puede deshacer.
            shutil.move(ruta, ruta_cuarentena)
            print(f"[+] AISLAMIENTO EXITOSO: Archivo fuera de la baseline movido a {ruta_cuarentena}")
            resultado = CREADO
        else:
            if h is not None:
                # 1. CUARENTENA: Copiamos el archivo alterado tal cual (evidencia)
                shutil.copy2(ruta, ruta_cuarentena)
                print(f"[+] AISLAMIENTO EXITOSO: Evidencia copiada a {ruta_cuarentena}")

            if not restaurable:
                print("[-] NO SE RESTAURA: la bóveda no coincide con la baseline. Requiere revisión manual.")
            elif not se_restaura_ahora(aprobado_por):
                avisar_pendiente(ruta)
                return PENDIENTE, evento_id
            else:
                # 2. RESTAURACIÓN: Reponemos el original desde la bóveda en disco
                boveda.restaurar(ruta)
                log_to_db(nombre, ruta, get_sha256(ruta), RESTAURADO,
                          f"Restaurado desde la bóveda tras un evento {evento}" + firma_de_aprobacion(aprobado_por),
                          hash_anterior=h, ruta_cuarentena=ruta_cuarentena)
                print(f"[+] RESTAURACIÓN EXITOSA: El archivo original ha sido recuperado.")
                resultado = RESTAURADO
        print("-" * 50)

    except Exception as e:
        print(f"[-] Error en la respuesta automatizada: {e}")
    # --- FIN RESPUESTA AUTOMATIZADA ---
    return resultado, evento_id

def decisiones_pendientes():
    """Devuelve las decisiones de la tabla decisiones que todavía no tienen fila en ejecuciones."""
    filas = bd.ejecutar("""
        SELECT d.id, d.decision, d.decidido_por, d.canal,
               r.id, r.evento, r.ruta_completa, r.hash_sha256, r.permisos, r.owner_archivo, r.ruta_cuarentena
        FROM decisiones d
        JOIN registros_archivos r ON r.id = d.evento_id
        LEFT JOIN ejecuciones e ON e.decision_id = d.id
        WHERE e.id IS NULL
        ORDER BY d.id
    """)
    campos = ["id", "decision", "decidido_por", "canal", "evento_id", "evento", "ruta", "hash",
              "permisos", "owner", "ruta_cuarentena"]
    return [dict(zip(campos, fila)) for fila in filas]

def registrar_ejecucion(decision_id, resultado, detalle):
    bd.ejecutar("INSERT INTO ejecuciones (decision_id, resultado, detalle) VALUES (%s, %s, %s)",
                (decision_id, resultado, detalle))

def aceptar_cambio(d):
    """El estado que vio la persona pasa a ser la baseline de ese archivo (y solo de ese).

    Devuelve (resultado, detalle).
    """
    ruta = d["ruta"]
    if d["evento"] in (MODIFICADO, CREADO):
        # Se repone exactamente la versión que se mostró en la alerta: la copia de cuarentena
        copia = d["ruta_cuarentena"]
        if not copia or get_sha256(copia) != d["hash"]:
            return "RECHAZADA", "La copia de cuarentena falta o no coincide con el hash del evento: no se acepta."
        boveda.reponer_desde(copia, ruta)
    elif d["evento"] in (ELIMINADO, MOVIDO):
        if os.path.lexists(ruta):
            os.remove(ruta)
    elif d["evento"] == PERMISOS:
        os.chmod(ruta, int(d["permisos"], 8))
        if leer_owner_y_permisos(ruta)[0] != d["owner"]:
            # Cambiar el dueño de un archivo solo lo puede hacer root
            os.chown(ruta, int(d["owner"]), -1)

    motivo = (f"Cambio aceptado por {d['decidido_por']} ({d['canal']}), "
              f"decisión #{d['id']} sobre el evento #{d['evento_id']}.")
    version = generar_baseline.actualizar_archivo(ruta, motivo)
    return "EJECUTADA", f"Baseline versión {version}: {motivo}"

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

def ejecutar_decision(d):
    """Ejecuta una decisión, deja constancia en ejecuciones y avisa a n8n para que confirme."""
    print(f"[*] Decisión #{d['id']}: {d['decision']} sobre el evento #{d['evento_id']} ({d['ruta']}), "
          f"de {d['decidido_por']} por {d['canal']}.")
    with candado:
        try:
            resultado, detalle = _ejecutar_decision(d)
        except Exception as e:
            resultado, detalle = "ERROR", str(e)
    decisiones_ejecutadas.add(d["id"])
    print(f"    {resultado}: {detalle}")

    try:
        registrar_ejecucion(d["id"], resultado, detalle)
    except Exception as e:
        print(f"[!] No se pudo registrar la ejecución de la decisión #{d['id']}: {e}")
    notificador.notificar({"tipo": "ejecucion", "decision_id": d["id"], "evento_id": d["evento_id"],
                           "resultado": resultado})
    return resultado

def vigilar_decisiones(detener):
    """Hilo que cada INTERVALO_DECISIONES segundos busca decisiones nuevas y las ejecuta."""
    ultimo_error = None
    while not detener.wait(INTERVALO_DECISIONES):
        try:
            pendientes = decisiones_pendientes()
            ultimo_error = None
        except Exception as e:
            # Se avisa una vez y no cada 2 segundos
            if str(e) != ultimo_error:
                print(f"[!] No se pudieron consultar las decisiones: {e}")
                ultimo_error = str(e)
            continue
        for d in pendientes:
            if d["id"] not in decisiones_ejecutadas:
                ejecutar_decision(d)

def revisar_directorio(directorio):
    """Verifica todos los archivos de la baseline que estaban dentro de un directorio borrado o movido."""
    directorio = os.path.abspath(directorio)
    try:
        rutas = [ruta for ruta in rutas_de_la_baseline() if config.dentro_de(ruta, directorio)]
    except Exception as e:
        print(f"[!] ALERTA: no se pudo consultar la baseline para revisar {directorio}: {e}")
        return
    for ruta in rutas:
        procesar(ruta)

def escaneo_inicial():
    """Al arrancar, compara la baseline vigente contra el disco.

    Detecta lo que cambió mientras el monitor estaba apagado. Cada diferencia se trata
    igual que un evento en tiempo real.
    """
    try:
        rutas = set(rutas_de_la_baseline())
    except Exception as e:
        print(f"[!] No se pudo hacer el escaneo inicial (sin acceso a la baseline): {e}")
        return

    # Sin una baseline para estas rutas, todo parecería archivo nuevo y terminaría en cuarentena
    if not any(config.dentro_de(ruta, directorio) for ruta in rutas for directorio in config.RUTAS_MONITOREADAS):
        print("[!] La baseline vigente no tiene archivos de las rutas monitoreadas.")
        print("    Ejecutá generar_baseline.py antes de iniciar el monitor.")
        sys.exit(1)

    # Se suman los archivos que están en disco aunque no figuren en la baseline
    for directorio in config.RUTAS_MONITOREADAS:
        for root, dirs, files in os.walk(directorio):
            for file in files:
                rutas.add(os.path.join(root, file))

    print(f"[*] Escaneo inicial: verificando {len(rutas)} archivo(s) contra la baseline...")
    for ruta in sorted(rutas):
        procesar(ruta)
    print("[*] Escaneo inicial terminado.")

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

def validar_configuracion():
    """Corta si el modo de restauración no existe o si la bóveda, la cuarentena o los logs
    quedaron adentro de un directorio vigilado."""
    if config.MODO_RESTAURACION not in config.MODOS_RESTAURACION:
        print(f"[!] Configuración inválida: MODO_RESTAURACION={config.MODO_RESTAURACION}.")
        print(f"    Valores posibles: {', '.join(config.MODOS_RESTAURACION)}.")
        sys.exit(1)

    propias = {"DIR_BOVEDA": config.DIRECTORIO_BOVEDA, "DIR_CUARENTENA": config.DIRECTORIO_CUARENTENA,
               "DIR_LOGS": os.path.dirname(config.ARCHIVO_PENDIENTES)}
    for nombre, carpeta in propias.items():
        for directorio in config.RUTAS_MONITOREADAS:
            if config.dentro_de(carpeta, directorio):
                print(f"[!] Configuración inválida: {nombre} ({carpeta}) está dentro del directorio vigilado")
                print(f"    {directorio}. El monitor reaccionaría a sus propios archivos.")
                sys.exit(1)

if __name__ == "__main__":
    validar_configuracion()
    print(f"[*] Modo de restauración: {config.MODO_RESTAURACION}")

    event_handler = FIMEventHandler()
    observer = Observer()
    vigilados = 0
    for directorio in config.RUTAS_MONITOREADAS:
        if os.path.isdir(directorio):
            observer.schedule(event_handler, directorio, recursive=True)
            print(f"[*] Iniciando Motor FIM en tiempo real sobre: {directorio}")
            vigilados += 1
        else:
            print(f"[!] No existe el directorio {directorio}: no se vigila.")

    if not vigilados:
        print("[!] No hay ningún directorio para vigilar. Revisá RUTAS_MONITOREADAS en el .env.")
        sys.exit(1)

    # Primero se empieza a escuchar y después se escanea: así no queda ninguna ventana sin cubrir
    observer.start()
    detener = threading.Event()
    try:
        escaneo_inicial()
        threading.Thread(target=vigilar_decisiones, args=(detener,), daemon=True).start()
        print(f"[*] Esperando decisiones de n8n (cada {INTERVALO_DECISIONES} s).")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Motor FIM detenido.")
    finally:
        detener.set()
        observer.stop()
        observer.join()
        bd.cerrar()
