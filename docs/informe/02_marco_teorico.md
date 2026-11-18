# CAPÍTULO 2: Marco Teórico

Este capítulo presenta los conceptos en los que se apoya el sistema: la integridad como objetivo de
seguridad, las funciones hash, las dos formas de monitorear la integridad de archivos, la respuesta
ante un cambio, la orquestación con intervención humana, las métricas con que se evalúa, el principio
de mínimo privilegio y la exposición segura de un servicio a internet. Cierra con el estado del
arte: los antecedentes, una comparación de las herramientas existentes y el aporte de este trabajo.

## 2.1 Seguridad de la información y la tríada CIA

La seguridad de la información engloba las prácticas y tecnologías destinadas a proteger los activos
digitales contra accesos o alteraciones no autorizadas. Se organiza en torno a tres propiedades,
conocidas como tríada CIA: confidencialidad, integridad y disponibilidad (Bishop, 2003). Este trabajo se centra en la **integridad**, que busca que la información no sea modificada de
forma ilegítima y que cualquier alteración sea detectable. El sistema de este trabajo registra qué
cambió y cuándo, pero no quién lo hizo: inotify no informa el usuario ni el proceso que originó el
evento (The Linux man-pages project, 2026b), limitación que se retoma en el Capítulo 6.

## 2.2 Funciones hash criptográficas (SHA-256)

Una función hash criptográfica transforma datos de longitud arbitraria en un resumen de longitud
fija. Para la verificación de integridad interesan dos propiedades: es computacionalmente inviable
encontrar dos entradas distintas con el mismo resumen (resistencia a colisiones), y un cambio mínimo
en la entrada, aunque sea de un único bit, produce un resumen completamente distinto. Así, comparar
el resumen actual de un archivo con el registrado en la línea base permite saber si su contenido
cambió, sin guardar ni comparar el archivo completo.

El sistema utiliza SHA-256, de la familia SHA-2, que produce resúmenes de 256 bits y está especificado
en el estándar FIPS 180-4 (National Institute of Standards and Technology [NIST], 2015). El archivo se lee en bloques, de modo que el consumo de memoria
no depende de su tamaño.

## 2.3 Monitoreo de integridad de archivos (FIM)

El monitoreo de integridad de archivos consiste en registrar el estado de referencia de un conjunto de
archivos (contenido, permisos, propietario) y detectar cualquier desviación respecto de ese estado.
No impide que un archivo sea modificado: lo que aporta es **detectar** la modificación, dejar
evidencia y, si se lo configura, **responder** ante ella. Existen dos enfoques para decidir cuándo
comparar.

### 2.3.1 Escaneo periódico

En el enfoque tradicional, una tarea programada (por ejemplo, con `cron`) recorre los archivos cada
cierto período, calcula sus hashes y los compara con la línea base. Su costo es predecible y no
depende de la actividad del sistema, pero introduce una espera: un cambio solo se detecta en el
escaneo siguiente.

Si el escaneo se ejecuta cada T segundos y tarda S segundos, y un cambio ocurre en un instante
cualquiera, el tiempo hasta el próximo escaneo se distribuye de manera uniforme entre 0 y T. La
detección tarda entonces, en promedio, aproximadamente T/2 + S, y como máximo T + S. Se toma S
completo como cota superior, porque el archivo modificado puede aparecer antes del final del
recorrido. Con un período de una hora, por ejemplo, la espera media es de unos 30 minutos.

### 2.3.2 Monitoreo por eventos: inotify y watchdog

Los sistemas Linux incluyen el subsistema **inotify**, que permite a un programa suscribirse a un
directorio y recibir notificaciones del kernel cuando se crea, modifica, borra, mueve o cambia de
atributos un archivo (The Linux man-pages project, 2026b). Con este enfoque no hay que esperar al siguiente
ciclo: el programa se entera del cambio en el momento en que ocurre.

La biblioteca **watchdog** de Python ofrece una interfaz de alto nivel sobre inotify y entrega los
eventos clasificados (creación, modificación, borrado y movimiento) a manejadores definidos por el
programador. Hay dos aspectos a tener en cuenta. Un mismo cambio puede producir varios eventos (por
ejemplo, truncar un archivo y luego escribirlo), y un cambio de permisos llega como un evento de
modificación. Además, el monitor solo observa lo que ocurre mientras está en ejecución: lo que cambia
mientras está detenido debe detectarse con una verificación al arrancar. Por eso, en el sistema
desarrollado el evento se usa como disparador de una comparación con la línea base, y no como la
descripción de lo ocurrido (Capítulo 4).

## 2.4 Línea base, evidencia y respuesta

### 2.4.1 Línea base

La **línea base** es el estado de referencia contra el cual se compara: para cada archivo, su hash,
sus permisos y su propietario en un momento considerado confiable. Como los sistemas cambian de forma
legítima (actualizaciones, cambios de configuración), la línea base debe poder actualizarse de manera
autorizada. Si cada actualización genera una **versión** nueva en lugar de sobrescribir la anterior,
se conserva el historial y se puede reconstruir qué se consideraba confiable en cada momento.

### 2.4.2 Evidencia diferencial

Saber que un archivo cambió no alcanza para analizar un incidente: hace falta saber **qué** cambió.
En los archivos de texto, un algoritmo de diferencias produce la lista de líneas agregadas y quitadas.
El formato de diff unificado, que muestra cada línea cambiada con su contexto y la marca `+` o `-`, es
el que generan herramientas como `diff -u` y el módulo `difflib` de Python (Python Software
Foundation, s.f.). Para los archivos binarios no tiene sentido un diff de texto, y la evidencia es el
cambio de hash junto con una copia del archivo alterado.

### 2.4.3 Cuarentena y restauración

La respuesta ante un cambio puede incluir dos acciones:

- **Cuarentena:** conservar el archivo alterado en un lugar separado, como evidencia y para su
  análisis posterior. En el caso de un archivo nuevo y desconocido, retirarlo del directorio vigilado
  lo aísla.
- **Restauración:** volver a poner en su lugar la versión confiable del archivo. Para restaurar hace
  falta una copia confiable, cuyo contenido coincida con la línea base. Además, conviene que la
  restauración sea **atómica**: en los sistemas de archivos POSIX, renombrar un archivo sobre otro
  reemplaza el destino en una sola operación, de modo que nunca queda un archivo faltante o a medio
  escribir.

## 2.5 Orquestación de la respuesta e intervención humana

Las plataformas de orquestación, automatización y respuesta de seguridad (SOAR, por sus siglas en
inglés) coordinan las acciones que siguen a una alerta: enriquecerla con información, notificar,
ejecutar acciones y registrar lo actuado. La guía de respuesta a incidentes del NIST las menciona,
junto con las de gestión de eventos (SIEM), entre las herramientas para vigilar y correlacionar
eventos, y describe los **playbooks** como procedimientos documentados en forma de pasos o tareas
concretas para cada escenario (Nelson et al., 2025). En este
trabajo se utiliza n8n, una herramienta de automatización de flujos de trabajo distribuida con una
licencia *fair-code*, que permite instalarla en un equipo propio (n8n, s.f.), para implementar dos
playbooks: uno de detección y respuesta, y otro de
actualización autorizada de la línea base.

Una decisión central en la respuesta automatizada es cuánto se deja en manos de la máquina:

- **Respuesta automática:** minimiza el tiempo de exposición, pero puede revertir cambios legítimos.
- **Respuesta con aprobación humana:** evita ese error, pero el archivo alterado sigue activo mientras
  se espera la decisión.

En este trabajo se llama diseño con intervención humana (*human-in-the-loop*) al que combina ambas:
automatiza lo reversible y deja a una persona las decisiones que cambian lo que se considera
confiable. La misma guía recomienda revisar a mano los eventos que la automatización no alcanza a
vigilar (Nelson et al., 2025). Para que esa
intervención sea práctica, la decisión debe poder tomarse desde la propia alerta y quedar registrada
junto con quién la tomó.

## 2.6 Métricas de detección y respuesta

Para evaluar un sistema de detección y respuesta se usan, entre otras, las siguientes métricas. MTTD
y MTTR son denominaciones de uso extendido en la práctica profesional; como aquí no se adopta la
definición de una fuente en particular, lo que vale son las definiciones operativas de la
sección 3.3:

- **MTTD** (*Mean Time To Detect*, tiempo medio de detección): tiempo entre que ocurre el cambio y que
  el sistema lo detecta y lo registra.
- **MTTR** (*Mean Time To Respond* o *To Recover*): tiempo hasta que el sistema vuelve a su estado
  confiable; en este trabajo, hasta que el archivo queda restaurado.
- **Proporción de alertas espurias:** parte de las alertas emitidas que no corresponde a un cambio
  que interese señalar, como los archivos temporales que crea un editor al guardar. Una alerta
  espuria es un falso positivo, y un exceso de ellas hace que las alertas pierdan credibilidad. No
  debe confundirse con la tasa de falsos positivos en sentido estricto, que se calcula sobre los
  casos negativos y no sobre las alertas; la diferencia y la fórmula usada se precisan en la
  sección 3.3.

Aunque los nombres hablan de tiempos medios, cuando las mediciones tienen valores atípicos la
**mediana** describe mejor el comportamiento típico, y los percentiles altos, como el p95, describen el
peor caso habitual. Las definiciones operativas exactas de cada métrica en este trabajo se dan en el
Capítulo 3.

## 2.7 Mínimo privilegio y registros de solo-agregar

El principio de **mínimo privilegio** establece que cada componente debe operar con los permisos
estrictamente necesarios para su función (Saltzer y Schroeder, 1975). Aplicado a un sistema de
integridad, implica que la cuenta que registra los eventos pueda agregarlos y leerlos, pero no
modificarlos ni borrarlos, y que cada componente tenga una cuenta distinta. Si un atacante
compromete el componente que escribe el registro, no puede borrar sus rastros con esa cuenta.

Un registro de **solo-agregar** (*append-only*) es aquel en el que las entradas nunca se actualizan
ni se eliminan: un cambio se representa como una entrada nueva. Además de proteger la evidencia,
facilita la auditoría, porque el historial completo queda disponible. Esta protección es relativa a
las cuentas de la aplicación: el administrador de la base de datos conserva la capacidad de alterarla.

## 2.8 Exposición segura de servicios a internet

Para recibir avisos de un servicio externo, como los de Telegram cuando una persona toca un botón, el
servidor debe ser alcanzable desde internet. Cuando no tiene una dirección pública, se puede usar un
**túnel**: un agente que corre en el servidor crea un túnel cifrado hacia un proveedor (en este
trabajo, ngrok), que publica una dirección pública y entrega por ese túnel el tráfico que recibe, sin
necesidad de abrir puertos en el equipo ni modificar la red (ngrok, s.f.-b). Abrir un servicio a internet aumenta su superficie de ataque, por lo que se
aplican varias capas de protección:

- **Filtrado de rutas en el borde.** El proveedor del túnel puede evaluar reglas sobre cada pedido y
  rechazarlo antes de que llegue al servicio (ngrok, s.f.-a). Si solo se permite la ruta estrictamente necesaria, el resto del servicio (por
  ejemplo, su interfaz de administración) no queda expuesto. Es importante saber si las reglas se
  evalúan sobre la ruta tal como llega o sobre una versión normalizada, porque variantes codificadas
  de una ruta pueden comportarse distinto.
- **Rutas no adivinables.** Agregar a la ruta pública un componente aleatorio y largo dificulta que un
  tercero la descubra.
- **Secretos compartidos en webhooks.** El emisor y el receptor acuerdan un secreto, que viaja en cada
  pedido; el receptor rechaza los que no lo traen. La API de bots de Telegram permite registrar un
  `secret_token`, que envía en el encabezado `X-Telegram-Bot-Api-Secret-Token` de cada aviso (Telegram,
  s.f.).
- **Verificación del remitente.** Aunque el pedido sea auténtico, hay que verificar que la acción la
  haya pedido la persona autorizada, por ejemplo comparando el identificador de la cuenta de Telegram.

Estas medidas se complementan: ninguna alcanza por sí sola, y la implementación descripta en el
Capítulo 4 las combina.

## 2.9 Estado del arte: herramientas de monitoreo de integridad

### Antecedentes

La verificación de integridad de archivos como técnica de detección de intrusiones se remonta a
Tripwire, presentado por Kim y Spafford (1994) como un verificador de integridad del sistema de
archivos. Las revisiones recientes muestran que el tema sigue vigente. Peddoju et al. (2020) revisan
las herramientas de monitoreo de integridad disponibles y los enfoques que usan, y lo justifican en
que la mayoría de los ataques accede a archivos sensibles y luego altera los registros del sistema
para ocultarse. Salman et al. (2022) estudian los verificadores de integridad dentro de los sistemas
de detección de intrusiones basados en host y señalan un punto débil común: la detección depende de
una base de referencia, y quien pueda modificarla evade el control; revisan las técnicas para
protegerla y concluyen que ninguna es infalible. Ese problema es el que en este trabajo se trata con
la verificación de la bóveda contra la línea base y con las limitaciones declaradas en el
Capítulo 6.

En el plano normativo, el control SI-7 del catálogo NIST SP 800-53 pide emplear herramientas de
verificación de integridad para detectar cambios no autorizados y definir qué acciones se toman
cuando se detectan. Sus mejoras contemplan la notificación automática al personal cuando hay
discrepancias (SI-7(2)), la respuesta automática, que puede incluir revertir los cambios (SI-7(5)),
y la integración de la detección con la capacidad de respuesta a incidentes (SI-7(7)) (Joint Task
Force, 2020). La guía de respuesta a incidentes NIST SP 800-61 señala, por su parte, que muchas
organizaciones documentan sus procedimientos como *playbooks*, y recomienda usar herramientas de
gestión de eventos y de orquestación (SIEM y SOAR) para vigilar y correlacionar los eventos (Nelson
et al., 2025).

### Comparación de herramientas

La Tabla 2.1 compara las herramientas y mecanismos más citados con el sistema de este trabajo. Cada
celda resume lo que dice la documentación que se indica en la primera columna; un guion significa
que esa fuente no describe la función, no que la herramienta no pueda cumplirla con otros
componentes.

**Tabla 2.1.** Herramientas y mecanismos de monitoreo de integridad, según su documentación.

| Herramienta (fuente) | Enfoque de detección | Evidencia diferencial | Respuesta | Orquestación | Costo de adopción |
|---|---|---|---|---|---|
| Tripwire (Kim y Spafford, 1994; Tripwire, s.f.) | Compara el sistema de archivos con una base de datos al ejecutar la verificación | Informa altas, bajas y cambios de las propiedades vigiladas | — | — | Herramienta para sistemas tipo UNIX; política, configuración y claves firmadas con `twadmin` |
| AIDE (AIDE, s.f.) | Compara con una base de datos creada desde `aide.conf` (`--init`, `--check`) | Atributos y hashes que cambiaron | — (reemplazar la base de datos es una operación manual) | — | Una base de datos y el archivo de configuración `aide.conf` |
| OSSEC, módulo syscheck (OSSEC, s.f.) | Escaneo periódico (cada 6 horas por defecto) y opción de tiempo real con inotify | Diff de archivos de texto con `report_changes` | — | El servidor (*manager*) guarda los hashes y genera la alerta | Agente y servidor |
| Wazuh, módulo FIM (Wazuh Inc., s.f.-a, s.f.-b, s.f.-c, s.f.-d) | Escaneos programados y tiempo real; *who-data* con Audit o eBPF | Contenido que cambió en archivos de texto (`report_changes`); usuario y proceso (*who-data*) | Módulo de respuesta activa: ejecuta scripts en el equipo ante una alerta | La respuesta se dispara por alertas, según la regla, el nivel o el grupo | Agentes y servidor de la plataforma |
| Samhain (Wichmann, s.f.) | Escaneos completos programados; inotify opcional desde la versión 3.0, con informes inmediatos | Puede guardar el contenido de archivos chicos para ver qué cambió; no informa el diff | — | Servidor de registros central (*yule*); puede llamar a programas externos para notificar (el manual da como ejemplo el envío de un SMS) | Un equipo o cliente y servidor |
| auditd (Red Hat, 2021, 2023) | Reglas del subsistema de auditoría del kernel sobre accesos a archivos y directorios (lectura, escritura, ejecución, atributos) | Registra los accesos y permite informarlos por usuario; las páginas no mencionan contenido ni hashes | — | — | Reglas con `auditctl`; revisión con `ausearch` y `aureport` |
| fanotify (The Linux man-pages project, 2026a) | Interfaz del kernel de notificación e intercepción de eventos del sistema de archivos | — (es una interfaz, no una herramienta) | Los eventos de permiso permiten autorizar o denegar un acceso | — | Requiere programar contra la interfaz |
| Enfoques con eBPF (eBPF.io, s.f.; Tetragon, s.f.) | Programas en el kernel; Tetragon observa el acceso a archivos con ganchos y filtra en el kernel | Proceso que accedió y operación; no el contenido | — | — | Privilegios para cargar programas eBPF |
| Este trabajo | Eventos de inotify como disparador y comparación con una línea base en PostgreSQL; escaneo al arrancar | Hashes anterior y nuevo, copia del archivo y diff de texto | Restauración desde una copia verificada, cuarentena, modo de aprobación y ventanas de mantenimiento | n8n y Telegram: la persona decide desde la alerta y el monitor ejecuta | Un equipo con Python, PostgreSQL y n8n (sobre Node.js); para las alertas y los botones, una cuenta de Telegram y un túnel ngrok, que son servicios externos |

### Brecha y aporte

De la comparación surge que la detección en tiempo real y el diff de archivos de texto no son
novedades: OSSEC y Wazuh los ofrecen, y Wazuh agrega una respuesta activa basada en scripts. También
la norma contempla revertir los cambios de forma automática (SI-7(5)). Lo que la documentación
consultada no describe como un conjunto ya resuelto en una herramienta que se instala en un solo
equipo, sin agentes ni servidor central, es la combinación de tres cosas: la restauración automática desde una copia verificada contra la
línea base, la decisión de una persona tomada desde la propia alerta (confirmar el incidente,
restaurar o aceptar el cambio) con efecto sobre la línea base, y el registro de solo-agregar de todo
el recorrido. Las plataformas que más se acercan lo hacen con una arquitectura de agente y servidor.
No se afirma que este sistema consuma menos recursos que ellas: requiere cinco componentes (Python,
PostgreSQL, n8n sobre Node.js, ngrok y Telegram) y su consumo no se midió ni se comparó.

El aporte de este trabajo es, entonces, de integración y de medición, no un algoritmo nuevo: reúne
mecanismos conocidos (inotify, hashes, diff, restauración atómica, orquestación con aprobación
humana) en un sistema chico y verificable, documenta las decisiones de diseño y sus límites, y mide
con datos propios los tiempos de detección, restauración, alerta y decisión. La comparación de la
Tabla 2.1 se basa en documentación y no en pruebas de esas herramientas, que no se instalaron ni se
midieron en este trabajo.
