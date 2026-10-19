# CAPÍTULO 2: Marco Teórico

Este capítulo presenta los conceptos en los que se apoya el sistema: la integridad como objetivo de
seguridad, las funciones hash, las dos formas de monitorear la integridad de archivos, la respuesta
ante un cambio, la orquestación con intervención humana, las métricas con que se evalúa, el principio
de mínimo privilegio y la exposición segura de un servicio a internet.

## 2.1 Seguridad de la información y la tríada CIA

La seguridad de la información engloba las prácticas y tecnologías destinadas a proteger los activos
digitales contra accesos o alteraciones no autorizadas. Se organiza en torno a tres propiedades,
conocidas como tríada CIA: confidencialidad, integridad y disponibilidad (Bishop, 2003). Este trabajo se centra en la **integridad**, que busca que la información no sea modificada de
forma ilegítima y que cualquier alteración sea detectable y atribuible.

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
atributos un archivo (The Linux man-pages project, 2026). Con este enfoque no hay que esperar al siguiente
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
ejecutar acciones y registrar lo actuado. Esas secuencias se describen como **playbooks**. En este
trabajo se utiliza n8n, una herramienta de automatización de flujos de trabajo distribuida con una
licencia *fair-code*, que permite instalarla en un equipo propio (n8n, s.f.), para implementar dos
playbooks: uno de detección y respuesta, y otro de
actualización autorizada de la línea base.

Una decisión central en la respuesta automatizada es cuánto se deja en manos de la máquina:

- **Respuesta automática:** minimiza el tiempo de exposición, pero puede revertir cambios legítimos.
- **Respuesta con aprobación humana:** evita ese error, pero el archivo alterado sigue activo mientras
  se espera la decisión.

Los diseños con intervención humana (*human-in-the-loop*) combinan ambas: automatizan lo reversible y
dejan a una persona las decisiones que cambian lo que se considera confiable. Para que esa
intervención sea práctica, la decisión debe poder tomarse desde la propia alerta y quedar registrada
junto con quién la tomó.

## 2.6 Métricas de detección y respuesta

Para evaluar un sistema de detección y respuesta se usan, entre otras, las siguientes métricas:

- **MTTD** (*Mean Time To Detect*, tiempo medio de detección): tiempo entre que ocurre el cambio y que
  el sistema lo detecta y lo registra.
- **MTTR** (*Mean Time To Respond* o *To Recover*): tiempo hasta que el sistema vuelve a su estado
  confiable; en este trabajo, hasta que el archivo queda restaurado.
- **Tasa de falsos positivos:** proporción de alertas que no corresponden a un cambio que interese
  señalar, como los archivos temporales que crea un editor al guardar. Un exceso de falsos positivos
  hace que las alertas pierdan credibilidad.

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
