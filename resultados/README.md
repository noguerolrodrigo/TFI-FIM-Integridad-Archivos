# Resultados medidos (Paso 4)

Todos los números de esta carpeta salen de los scripts de `scripts/` y quedan en los CSV tal como
se midieron: no se descartaron ni se repitieron valores. Los resúmenes `.md` y los gráficos se
regeneran con `scripts/resumir_metricas.py`.

## Entorno

Intel(R) Core(TM) 7 240H (16 procesadores), Ubuntu en WSL2 (kernel 6.6.87.2-microsoft-standard-WSL2),
Python 3.12.3, PostgreSQL 16.15, watchdog 6.0.0,
n8n 2.41.4. Mediciones simuladas: base `fim_pruebas`, n8n de pruebas y Telegram simulado;
`fim_db` sin cambios (44 → 44). Muestra real: la
instalación de verdad, con el bot de Telegram: 10 detecciones en `fim_db` (ids
45, 47, 49, 51, 53, 55, 57, 59, 61, 63), todas cerradas como incidente desde el celular.

## Definiciones

`t0` es el instante en que el script terminó de escribir. Todos los tiempos salen del mismo reloj.

- **MTTD**: `t0` → fila de detección en `registros_archivos` (el valor es el inicio de la transacción
  del INSERT, así que incluye inotify, watchdog, hash y consulta de la baseline).
- **MTTR (disco)**: `t0` → el archivo vuelve a estar como en la baseline (o el archivo nuevo deja de
  estar, porque ya se aisló).
- **Alerta**: fila de detección → fila en `notificaciones` (n8n ya mandó el mensaje).
- **Ejecución**: fila en `decisiones` → fila en `ejecuciones` (sin el tiempo de la persona).

## 1. MTTD, MTTR y alerta (50 repeticiones por caso)

Archivo: `metricas_20261015_232407.csv`; gráfico: `grafico_20261015_232407.png`.

| Caso | Métrica | n | Faltantes | Media | Mediana | p95 | Mín. | Máx. |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Texto (2 KB) | MTTD | 50 | 0 | 5.3 | 5.6 | 7.2 | 1.5 | 8.2 |
| Texto (2 KB) | MTTR (disco) | 50 | 0 | 44.0 | 47.3 | 50.9 | 7.5 | 52.8 |
| Texto (2 KB) | MTTR (fila RESTAURADO) | 50 | 0 | 44.5 | 47.8 | 51.6 | 8.4 | 54.4 |
| Texto (2 KB) | Alerta | 50 | 0 | 133.1 | 124.3 | 141.3 | 55.0 | 606.2 |
| Binario (1 MB) | MTTD | 50 | 0 | 7.4 | 7.2 | 9.1 | 3.1 | 26.2 |
| Binario (1 MB) | MTTR (disco) | 50 | 0 | 46.6 | 52.3 | 56.1 | 11.2 | 62.9 |
| Binario (1 MB) | MTTR (fila RESTAURADO) | 50 | 0 | 49.9 | 55.7 | 59.4 | 12.7 | 66.1 |
| Binario (1 MB) | Alerta | 50 | 0 | 126.2 | 129.5 | 150.0 | 87.3 | 213.4 |
| Permisos | MTTD | 50 | 0 | 5.0 | 5.2 | 6.6 | 1.2 | 6.8 |
| Permisos | MTTR (disco) | 50 | 0 | 41.3 | 44.3 | 50.8 | 5.7 | 54.1 |
| Permisos | MTTR (fila RESTAURADO) | 50 | 0 | 41.3 | 44.7 | 51.2 | 5.2 | 54.2 |
| Permisos | Alerta | 50 | 0 | 122.3 | 124.7 | 138.6 | 77.5 | 178.6 |
| Borrado | MTTD | 50 | 0 | 4.7 | 4.7 | 6.7 | 1.2 | 7.1 |
| Borrado | MTTR (disco) | 50 | 0 | 47.5 | 45.1 | 52.4 | 4.7 | 396.4 |
| Borrado | MTTR (fila RESTAURADO) | 50 | 0 | 48.2 | 45.5 | 53.1 | 4.4 | 401.2 |
| Borrado | Alerta | 50 | 0 | 134.2 | 124.0 | 139.9 | 56.5 | 770.1 |
| Archivo nuevo | MTTD | 50 | 0 | 4.8 | 4.8 | 6.2 | 1.3 | 6.9 |
| Archivo nuevo | Aislamiento | 50 | 0 | 38.7 | 44.4 | 49.3 | 5.8 | 53.3 |
| Archivo nuevo | Alerta | 50 | 0 | 125.2 | 124.3 | 136.3 | 69.8 | 331.9 |
| Decisión | Ejecución | 50 | 0 | 1013.7 | 938.6 | 1951.7 | 133.7 | 2041.5 |
| COMMIT en reposo | COMMIT | 50 | 0 | 35.3 | 37.9 | 42.4 | 3.2 | 44.2 |
| COMMIT en ráfaga | COMMIT | 50 | 0 | 1.9 | 1.8 | 3.1 | 1.1 | 4.0 |

**Lectura:**
- La detección tarda pocos milisegundos en todos los casos: mediana 5,4 ms.
- La restauración (o el aislamiento) lleva una mediana de 45,4 ms, y casi
  todo ese tiempo es el COMMIT de PostgreSQL de la fila de detección. El monitor guarda la
  evidencia antes de restaurar, y en el disco virtual de WSL2 ese COMMIT tarda mediana
  37,9 ms con el disco en reposo y
  1,8 ms en ráfaga (las filas COMMIT
  de la tabla).
- La ejecución de una decisión queda entre 0 y ~2 s (mediana 938,6 ms), porque
  el monitor busca decisiones cada 2 s.
- **Valores atípicos:** la repetición 49 tuvo una pausa general (un borrado restaurado en 396 ms y
  alertas de 770 y 332 ms, con la detección en 2,4 ms). La primera alerta de la corrida (606 ms)
  es el arranque en frío del workflow de n8n. Quedan en los datos.

## 2. Alerta con Telegram real (10 repeticiones)

Archivo: `alerta_telegram_real_20261016_000516.csv`.

| Caso | Métrica | n | Faltantes | Media | Mediana | p95 | Mín. | Máx. |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Telegram real | MTTD | 10 | 0 | 8.2 | 5.2 | 23.5 | 2.7 | 35.2 |
| Telegram real | MTTR (disco) | 10 | 0 | 37.3 | 47.4 | 51.5 | 6.7 | 52.5 |
| Telegram real | Alerta | 10 | 0 | 1108.1 | 1105.4 | 1258.6 | 983.2 | 1294.0 |

De la escritura a que n8n confirma el mensaje en Telegram: mediana 1,11 s
(entre 0,99 y 1,30 s). La diferencia con la
alerta simulada (mediana 124,7 ms) es el viaje a los servidores de Telegram.

## 3. Falsos positivos con editores reales (20 ediciones por editor)

Archivo: `falsos_positivos_20261015_233331.csv`.

| Corrida | Editor | Ediciones | Alertas | Esperadas | Espurias | Tasa de falsos positivos | Ediciones con problemas del editor |
|---|---|---:|---:|---:|---:|---:|---:|
| A_con_filtro | vim | 20 | 20 | 20 | 0 | 0.0 % | 0 |
| A_con_filtro | nano | 20 | 20 | 20 | 0 | 0.0 % | 0 |
| B_sin_filtro | vim | 20 | 40 | 20 | 20 | 50.0 % | 0 |
| B_sin_filtro | nano | 20 | 60 | 20 | 40 | 66.7 % | 0 |

Tasa de falsos positivos = alertas espurias / alertas totales.

Tipos de alertas espurias por corrida y editor:

- B_sin_filtro, vim: CREADO .vim.conf.swp (20)
- B_sin_filtro, nano: CREADO .nano.conf.swp (40)

Editores: VIM - Vi IMproved 9.1 (2024 Jan 02, compiled Aug 24 2026 22:13:04);  GNU nano, version 7.2. Sin configuración personal: rige la del sistema (Ubuntu: /etc/nanorc trae 'set locking', que crea los .swp de nano; vim usa backupcopy=yes, que guarda sobre el mismo archivo). Monitor en modo aprobación. Fecha: 15/10/2026 23:33.

## 4. Comparación con un escaneo periódico (tipo cron)

Archivo: `escaneo_periodico_20261015_235418.csv`.

Copia de /etc: 719 archivos legibles, 1.1 MB. Fecha: 15/10/2026 23:54.

**Duración medida de un escaneo completo (S)**, 20 veces: mediana 9.7 ms, p95 10.6 ms, mínimo 9.2 ms, máximo 11.5 ms.

**Validación con T = 10 s** (30 cambios en instantes al azar): detección media medida 4.45 s (mediana 4.29 s, máximo 9.10 s). La fórmula T/2 + S da 5.01 s.

**Cálculo teórico con el S medido** (no medido para estos T):

| Período T | Detección media ≈ T/2 + S | Detección máxima ≈ T + S |
|---|---:|---:|
| 10 s (medido arriba) | 5.0 s | 10.0 s |
| 1 min | 30.0 s | 60.0 s |
| 5 min | 150.0 s | 300.0 s |
| 1 h | 1800.0 s | 3600.0 s |

S se toma completo como cota superior: en un escaneo real el archivo cambiado puede aparecer antes del final del recorrido.

Con el monitor por eventos, la detección tiene una mediana de 5,4 ms,
contra 4,29 s medidos con un escaneo cada 10 s y ≈ 30,0 s
calculados para un cron de 1 minuto.

## 5. Comparación con la tabla del documento de diseño (.docx)

La tabla de resultados del documento "Orquestación de Playbooks ... con n8n" era **simulada**: sus
números fueron supuestos, no medidos. Se muestra al lado solo para dejar en claro qué cambió; los
números del FIM son los **medidos** en este paso.

| Métrica | .docx, manual (supuesto) | .docx, n8n (supuesto) | FIM, medido |
|---|---:|---:|---:|
| Tiempo hasta detectar | 12 min | 4 min | 5,4 ms hasta registrar la detección; 1,11 s hasta la alerta en Telegram (medianas) |
| Tiempo hasta restaurar | 45 min | 25 min | 45,4 ms en modo automático (mediana) |
| Falsos positivos | 10 % | 5 % | 0 % con el filtro de temporales; 50 % (vim) y 66,7 % (nano) sin el filtro |

Las definiciones no son idénticas, así que no se calcula un porcentaje de mejora:

- El .docx medía el MTTR desde la alerta y suponía una aprobación humana antes de restaurar.
- En modo aprobación, el tiempo hasta restaurar depende de la persona y no se midió. Lo que sí
  se midió es lo que agrega el sistema una vez que la persona decide: mediana
  938,6 ms.
- La tasa de falsos positivos del FIM es la de dos editores en un caso controlado, no la de un
  servidor en producción.
