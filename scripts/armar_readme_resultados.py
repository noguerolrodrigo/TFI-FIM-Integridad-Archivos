"""Arma resultados/README.md a partir de los CSV y resúmenes más recientes de resultados/.

Uso: python scripts/armar_readme_resultados.py   (desde la raíz del proyecto)

Los números salen de los archivos; el texto de lectura es fijo y menciona los valores atípicos
observados en la corrida del 15/10/2026.
"""
import csv, glob, json, os, sys
sys.path.insert(0, "scripts")
from resumir_metricas import percentil

def ultimo(patron):
    return sorted(glob.glob(f"resultados/{patron}"))[-1]

def valores(archivo, caso=None, metrica=None):
    return [float(f["valor_ms"]) for f in csv.DictReader(open(archivo, encoding="utf-8"))
            if (caso is None or f["caso"] == caso) and (metrica is None or f["metrica"] == metrica) and f["valor_ms"] != ""]

def f1(x): return f"{x:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
def f2(x): return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

met = ultimo("metricas_*.csv"); ent = json.load(open(ultimo("entorno_metricas_*.json")))
real = ultimo("alerta_telegram_real_*.csv"); ent_real = json.load(open(ultimo("entorno_alerta_telegram_real_*.json")))
fp_md = open(ultimo("resumen_falsos_positivos_*.md"), encoding="utf-8").read()
esc = ultimo("escaneo_periodico_*.csv"); esc_md = open(ultimo("resumen_escaneo_periodico_*.md"), encoding="utf-8").read()
res_md = open(ultimo("resumen_2*.md"), encoding="utf-8").read()
res_real_md = open(ultimo("resumen_telegram_real_*.md"), encoding="utf-8").read()

casos = ["texto", "binario", "permisos", "borrado", "archivo_nuevo"]
mttd = [v for c in casos for v in valores(met, c, "mttd_ms")]
mttr = [v for c in casos for v in valores(met, c, "mttr_disco_ms") + valores(met, c, "contencion_ms")]
alerta_sim = [v for c in casos for v in valores(met, c, "alerta_ms")]
filas_real = list(csv.DictReader(open(real, encoding="utf-8")))
por_rep = {}
for f in filas_real:
    por_rep.setdefault(f["repeticion"], {})[f["metrica"]] = float(f["valor_ms"])
punta_a_punta = [r["mttd_ms"] + r["alerta_ms"] for r in por_rep.values()]
ejec = valores(met, "decision", "ejecucion_ms")
s_escaneo = valores(esc, "escaneo_completo", "duracion_ms")
cron10 = valores(esc, "cron_T10s", "deteccion_ms")
s_med = percentil(s_escaneo, 50) / 1000

texto = f"""# Resultados medidos (Paso 4)

Todos los números de esta carpeta salen de los scripts de `scripts/` y quedan en los CSV tal como
se midieron: no se descartaron ni se repitieron valores. Los resúmenes `.md` y los gráficos se
regeneran con `scripts/resumir_metricas.py`.

## Entorno

{ent['cpu'].strip()} ({ent['procesadores']} procesadores), Ubuntu en WSL2 (kernel {ent['kernel']}),
Python {ent['python']}, PostgreSQL {ent['postgresql'].split()[0]}, watchdog {ent['watchdog']},
n8n {ent['n8n']}. Mediciones simuladas: base `fim_pruebas`, n8n de pruebas y Telegram simulado;
`fim_db` sin cambios ({ent['fim_db_max_id_antes']} → {ent['fim_db_max_id_despues']}). Muestra real: la
instalación de verdad, con el bot de Telegram: {len(ent_real['eventos'])} detecciones en `fim_db` (ids
{', '.join(str(i) for i in ent_real['eventos'])}), todas cerradas como incidente desde el celular.

## Definiciones

`t0` es el instante en que el script terminó de escribir. Todos los tiempos salen del mismo reloj.

- **MTTD**: `t0` → fila de detección en `registros_archivos` (el valor es el inicio de la transacción
  del INSERT, así que incluye inotify, watchdog, hash y consulta de la baseline).
- **MTTR (disco)**: `t0` → el archivo vuelve a estar como en la baseline (o el archivo nuevo deja de
  estar, porque ya se aisló).
- **Alerta**: fila de detección → fila en `notificaciones` (n8n ya mandó el mensaje).
- **Ejecución**: fila en `decisiones` → fila en `ejecuciones` (sin el tiempo de la persona).

## 1. MTTD, MTTR y alerta (50 repeticiones por caso)

Archivo: `{os.path.basename(met)}`; gráfico: `{os.path.basename(ultimo('grafico_2*.png'))}`.

{res_md.split(chr(10)+chr(10))[0]}

**Lectura:**
- La detección tarda pocos milisegundos en todos los casos: mediana {f1(percentil(mttd, 50))} ms.
- La restauración (o el aislamiento) lleva una mediana de {f1(percentil(mttr, 50))} ms, y casi
  todo ese tiempo es el COMMIT de PostgreSQL de la fila de detección. El monitor guarda la
  evidencia antes de restaurar, y en el disco virtual de WSL2 ese COMMIT tarda mediana
  {f1(percentil(valores(met, 'commit_en_reposo', 'commit_ms'), 50))} ms con el disco en reposo y
  {f1(percentil(valores(met, 'commit_seguido', 'commit_ms'), 50))} ms en ráfaga (las filas COMMIT
  de la tabla).
- La ejecución de una decisión queda entre 0 y ~2 s (mediana {f1(percentil(ejec, 50))} ms), porque
  el monitor busca decisiones cada 2 s.
- **Valores atípicos:** la repetición 49 tuvo una pausa general (un borrado restaurado en 396 ms y
  alertas de 770 y 332 ms, con la detección en 2,4 ms). La primera alerta de la corrida (606 ms)
  es el arranque en frío del workflow de n8n. Quedan en los datos.

## 2. Alerta con Telegram real (10 repeticiones)

Archivo: `{os.path.basename(real)}`.

{res_real_md.split(chr(10)+chr(10))[0]}

De la escritura a que n8n confirma el mensaje en Telegram: mediana {f2(percentil(punta_a_punta, 50) / 1000)} s
(entre {f2(min(punta_a_punta) / 1000)} y {f2(max(punta_a_punta) / 1000)} s). La diferencia con la
alerta simulada (mediana {f1(percentil(alerta_sim, 50))} ms) es el viaje a los servidores de Telegram.

## 3. Falsos positivos con editores reales (20 ediciones por editor)

Archivo: `{os.path.basename(ultimo('falsos_positivos_*.csv'))}`.

{fp_md}
## 4. Comparación con un escaneo periódico (tipo cron)

Archivo: `{os.path.basename(esc)}`.

{esc_md}
Con el monitor por eventos, la detección tiene una mediana de {f1(percentil(mttd, 50))} ms,
contra {f2(percentil(cron10, 50) / 1000)} s medidos con un escaneo cada 10 s y ≈ {f1(60 / 2 + s_med)} s
calculados para un cron de 1 minuto.

## 5. Comparación con la tabla del documento de diseño (.docx)

La tabla de resultados del documento "Orquestación de Playbooks ... con n8n" era **simulada**: sus
números fueron supuestos, no medidos. Se muestra al lado solo para dejar en claro qué cambió; los
números del FIM son los **medidos** en este paso.

| Métrica | .docx, manual (supuesto) | .docx, n8n (supuesto) | FIM, medido |
|---|---:|---:|---:|
| Tiempo hasta detectar | 12 min | 4 min | {f1(percentil(mttd, 50))} ms hasta registrar la detección; {f2(percentil(punta_a_punta, 50) / 1000)} s hasta la alerta en Telegram (medianas) |
| Tiempo hasta restaurar | 45 min | 25 min | {f1(percentil(mttr, 50))} ms en modo automático (mediana) |
| Falsos positivos | 10 % | 5 % | 0 % con el filtro de temporales; 50 % (vim) y 66,7 % (nano) sin el filtro |

Las definiciones no son idénticas, así que no se calcula un porcentaje de mejora:

- El .docx medía el MTTR desde la alerta y suponía una aprobación humana antes de restaurar.
- En modo aprobación, el tiempo hasta restaurar depende de la persona y no se midió. Lo que sí
  se midió es lo que agrega el sistema una vez que la persona decide: mediana
  {f1(percentil(ejec, 50))} ms.
- La tasa de falsos positivos del FIM es la de dos editores en un caso controlado, no la de un
  servidor en producción.
"""
open("resultados/README.md", "w", encoding="utf-8").write(texto)
print(texto)
