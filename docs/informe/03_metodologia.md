# CAPÍTULO 3: Marco Metodológico

Este capítulo describe cómo se construyó el sistema y cómo se obtuvieron los datos que se presentan
en el Capítulo 5: el tipo y el diseño de la investigación, las métricas, las técnicas de recolección,
los instrumentos y el tratamiento de los datos.

## 3.1 Tipo de investigación

La investigación es **aplicada**, porque su producto es una solución tecnológica funcional orientada
a un problema concreto: la falta de visibilidad y de respuesta ante modificaciones no autorizadas de
archivos en servidores Linux. Es también **descriptiva**, porque caracteriza el comportamiento del
sistema construido mediante mediciones cuantitativas de sus tiempos de detección, respuesta y alerta,
y de los falsos positivos que genera en un uso controlado.

## 3.2 Diseño de la investigación

El trabajo combina un proceso de desarrollo con una evaluación experimental en laboratorio.

**Desarrollo.** Se siguió un método iterativo e incremental. Después del informe de avance, se
realizó un diagnóstico de la versión existente (descripto en el Capítulo 4), y a partir de él el
trabajo se organizó en cuatro etapas: mejoras del motor de monitoreo, orquestación de la respuesta
con n8n, medición y redacción del informe. Cada mejora se implementó como un cambio pequeño y
verificable, registrado en un commit del control de versiones y acompañado, cuando fue posible, por
pruebas automatizadas. Al finalizar la etapa de medición se congeló el código, de modo que los
resultados del Capítulo 5 correspondan a una versión fija del sistema.

**Evaluación.** La evaluación consistió en mediciones repetidas en un entorno de laboratorio
controlado, sobre la versión congelada. No se trata de un experimento con grupo de control, sino de
un estudio con condiciones controladas e iguales para todas las repeticiones. Se incluyeron dos
tipos de contraste:

- **Interno:** la misma medición con y sin el filtro de archivos temporales, para estimar el efecto
  de ese filtro sobre los falsos positivos.
- **Externo:** la comparación con un escaneo periódico de integridad (del tipo que se programa con
  `cron`), combinando un cálculo teórico con una validación empírica en un período corto.

El entorno de laboratorio se ejecutó en Ubuntu sobre el Subsistema de Windows para Linux (WSL2). Las
modificaciones "maliciosas" se aplicaron sobre un directorio de prueba y sobre una base de datos de
pruebas, de modo que no afectaran archivos del sistema ni el registro de auditoría de uso diario.

## 3.3 Variables y métricas

Las variables medidas son tiempos y conteos. En todas las mediciones de tiempo, `t0` es el instante
en que el script de medición terminó de escribir el archivo (después de cerrarlo).

- **Tiempo hasta la detección (MTTD):** desde `t0` hasta la fila de detección en la base de datos. Se
  toma la marca de tiempo que asigna PostgreSQL al registrar la fila, que corresponde al inicio de la
  transacción de inserción.
- **Tiempo hasta la restauración (MTTR):** desde `t0` hasta que el archivo vuelve a estar en disco
  como en la línea base. Para un archivo nuevo se mide el aislamiento: el instante en que el archivo
  ya no está en el directorio vigilado. Como control se registró también el tiempo hasta la fila
  `RESTAURADO` en la base de datos.
- **Latencia de alerta:** desde la fila de detección hasta la fila en la tabla `notificaciones`, que
  n8n escribe después de que Telegram aceptó el mensaje.
- **Latencia de ejecución:** desde la fila en la tabla `decisiones` hasta la fila en la tabla
  `ejecuciones`. Excluye el tiempo que la persona tarda en decidir.
- **Duración del COMMIT:** tiempo que tarda PostgreSQL en confirmar una inserción, medido con el disco
  en reposo y en ráfaga. Se incorporó después de la corrida de prueba, al detectar que explicaba
  buena parte del tiempo de restauración.
- **Tasa de falsos positivos:** alertas espurias dividido alertas totales, en un conjunto de ediciones
  legítimas de archivos vigilados.
- **Duración de un escaneo completo (S) y tiempo de detección de un escaneo periódico:** para la
  comparación con el enfoque de escaneo programado.

Como la base de datos y los scripts se ejecutan en el mismo equipo, todas las marcas de tiempo
provienen del mismo reloj y no hay desfase entre ellas.

## 3.4 Técnicas de recolección de datos

### Verificación funcional

El comportamiento del sistema se verificó con 162 pruebas automatizadas (pytest). Las pruebas del
monitor usan una línea base en memoria para no depender de la base de datos; las de integración se
ejecutan sobre una base separada (`fim_pruebas`), que un script reconstruye con el mismo esquema que
la base productiva. Además se realizaron pruebas de punta a punta con el monitor real, una instancia
de n8n descartable y un servidor que simula la API de Telegram, y una prueba con la instalación real
y el bot de Telegram.

### Ataques controlados con repeticiones

El script `scripts/medir_metricas.py` ejecuta el monitor real como un proceso aparte, apuntado a la
base `fim_pruebas` y a carpetas temporales, junto con la instancia de n8n de pruebas. En cada
repetición aplica cinco cambios controlados, uno por caso: agregar una línea a un archivo de texto de
aproximadamente 2 KB, reescribir un archivo binario de 1 MB, cambiar los permisos de un archivo (de
644 a 777), borrar un archivo y crear un archivo que no figura en la línea base. Se realizaron 50
repeticiones por caso.

Para obtener mediciones confiables se tomaron las siguientes precauciones:

- **Emparejamiento por contenido.** Cada repetición escribe un contenido único, de modo que la fila
  de la base de datos se identifica por el hash esperado y no por proximidad en el tiempo. Para el
  cambio de permisos y el borrado, que no cambian el contenido, se identifica por ruta y por ventana
  de tiempo.
- **Resolución de la medición en disco.** El estado del archivo en disco se consulta cada 1 ms. Las
  latencias tomadas de la base de datos no dependen de la frecuencia con que el script consulta, porque
  se calculan con la marca de tiempo que asigna PostgreSQL.
- **Independencia entre repeticiones.** Antes de pasar a la siguiente repetición, el script espera a
  que el archivo vuelva a la línea base, a que n8n registre la notificación y una pausa de 0,5 s. Si
  un valor no aparece en 15 s, se registra como faltante en lugar de descartarse.
- **Decisiones sin sesgo de fase.** Para medir la latencia de ejecución se insertan decisiones en la
  base de datos, del mismo modo en que lo hace n8n. Como el monitor consulta las decisiones cada 2 s,
  insertarlas siempre en el mismo punto de ese ciclo mediría siempre la misma espera. Por eso, antes
  de cada inserción se espera un tiempo aleatorio de entre 0 y 2 s, generado con una semilla fija
  (2026) para que la corrida pueda repetirse. Este sesgo se detectó en la corrida de prueba y se
  corrigió antes de la corrida definitiva.
- **Corrida de prueba.** Antes de la corrida de 50 repeticiones se hizo una de 3, que se revisó a mano
  para confirmar que cada valor tuviera su fila correspondiente en la base de datos.

### Muestra con el bot de Telegram real

Como la instancia de pruebas usa un Telegram simulado, se tomó además una muestra de 10 alertas con
la instalación de uso diario y el bot real, a intervalos de 15 s, sobre el archivo
`directorio_prueba/config_test.txt`. Cada modificación agrega una línea identificable y el script
guarda el identificador de cada evento. Es la única medición que registró filas en la base productiva.
Las diez alertas se cerraron como incidente desde el teléfono; esas decisiones no se usaron como
medición, porque incluyen el tiempo humano.

### Falsos positivos con editores reales

El script `scripts/medir_falsos_positivos.py` edita archivos vigilados con dos editores reales, vim y
nano, controlados mediante una pseudoterminal que les envía pulsaciones de teclado: ir al final del
archivo, agregar una línea, guardar y salir. Se usó la configuración del sistema, sin configuración
personal. Se realizaron 20 ediciones con cada editor en dos corridas, una con el filtro de archivos
temporales activo y otra sin él. El monitor funcionó en modo de aprobación, para no restaurar el
archivo mientras el editor lo estaba guardando. Después de cada edición se esperó 1,5 s y se contaron
las alertas registradas: la primera detección `MODIFICADO` del archivo editado se consideró esperada
y cualquier otra, espuria. También se registró si el editor terminó correctamente y si el cambio quedó
guardado.

### Comparación con un escaneo periódico

El script `scripts/medir_escaneo_periodico.py` copia los archivos legibles de `/etc` a una carpeta
temporal y mide 20 veces cuánto tarda un escaneo completo, calculando para cada archivo el hash, los
permisos y el propietario con las mismas funciones que usa el FIM. Luego ejecuta un escáner real con
un período de 10 s y aplica 30 cambios en instantes aleatorios (semilla 2026), registrando cuánto
tarda cada uno en ser detectado. Esa medición se usa para validar la estimación teórica, que luego se
aplica a períodos más largos.

### Registro del entorno

Cada corrida guarda, junto con sus datos, un archivo con la descripción del entorno: procesador,
kernel, versiones de Python, PostgreSQL, watchdog y n8n, fecha de inicio y de fin, semilla utilizada y
la verificación de que la base productiva no cambió.

## 3.5 Instrumentos

**Hardware y sistema operativo.** Notebook con procesador Intel Core 7 240H (16 procesadores lógicos),
Windows como sistema anfitrión y Ubuntu sobre WSL2 (kernel 6.6.87.2).

**Software del sistema evaluado.** Python 3.12.3, la biblioteca watchdog 6.0.0 (que usa el subsistema
inotify del kernel), PostgreSQL 16.15, n8n 2.41.4 sobre Node.js 24, la Bot API de Telegram y ngrok en
su plan gratuito.

**Software de medición y análisis.**

| Script | Uso |
|---|---|
| `scripts/preparar_bd_pruebas.sh` | Reconstruye la base `fim_pruebas` con el esquema de la productiva |
| `scripts/n8n_de_pruebas.sh` y `scripts/telegram_falso.py` | Instancia de n8n descartable con Telegram simulado |
| `scripts/medir_metricas.py` | Tiempos de detección, restauración, alerta y ejecución, y costo del COMMIT |
| `scripts/medir_falsos_positivos.py` | Falsos positivos con vim 9.1 y nano 7.2 |
| `scripts/medir_escaneo_periodico.py` | Duración de un escaneo completo y escáner periódico de 10 s |
| `scripts/resumir_metricas.py` | Estadísticos y gráficos a partir de los CSV |
| `scripts/armar_readme_resultados.py` | Resumen general de resultados a partir de los CSV |

Las pruebas automatizadas usan pytest, y los gráficos, matplotlib 3.11.2.

## 3.6 Tratamiento de los datos

- **Almacenamiento.** Cada medición se guarda en un archivo CSV, con una fila por valor medido, y se
  versiona en la carpeta `resultados/` del repositorio junto con su archivo de entorno.
- **Estadísticos.** Para cada caso y métrica se calculan la media, la mediana, el percentil 95 (p95,
  con interpolación lineal entre los valores más cercanos), el mínimo y el máximo. Se informa la
  mediana como medida principal porque es menos sensible a valores atípicos.
- **Valores atípicos y faltantes.** No se descarta ningún valor. Los atípicos se mantienen en los datos
  y en los estadísticos, y se analizan por separado. Los faltantes se cuentan y se informan.
- **Reproducibilidad.** Los resúmenes, los gráficos y el resumen general se generan con scripts a partir
  de los CSV, sin transcribir números a mano. Las esperas aleatorias usan semilla fija.
- **Uso de valores de terceros.** El documento de diseño de la etapa de orquestación incluía una tabla
  de resultados simulada. Esos valores no se usan como resultados de este trabajo: en el Capítulo 5 se
  muestran solo para contrastarlos con los medidos, aclarando que eran supuestos.

## 3.7 Resguardos

- Las pruebas de ataque se realizaron sobre un directorio de prueba y una base de datos separada, sin
  afectar archivos del sistema operativo ni el registro de auditoría de uso diario. La base productiva
  solo recibió las diez alertas de la muestra con Telegram real.
- Las credenciales y los secretos (contraseñas de la base de datos, token del bot, secretos de los
  webhooks y sufijo de la ruta pública) se guardan en un archivo `.env` que no se versiona. El
  repositorio incluye solo una plantilla sin valores.
- La exposición a internet se limitó a una única ruta, necesaria para los botones de Telegram, con las
  medidas descriptas en el Capítulo 4.
