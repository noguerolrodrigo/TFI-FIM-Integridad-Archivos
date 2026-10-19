# CAPÍTULO 6: Conclusiones

Este capítulo responde la pregunta de investigación a partir de los resultados del Capítulo 5, revisa
el cumplimiento de los objetivos, resume los hallazgos principales y detalla las limitaciones del
sistema y de su evaluación.

## 6.1 Respuesta a la pregunta de investigación

La pregunta que guió el trabajo fue de qué manera puede desarrollarse un sistema automatizado que
detecte alteraciones de archivos en tiempo real en entornos Linux, extraiga y clasifique la evidencia
diferencial de forma inmediata y permita una respuesta controlada ante el incidente.

El trabajo muestra que es posible hacerlo con componentes de uso extendido (Python, PostgreSQL y n8n)
combinando cuatro elementos:

1. un monitor que reacciona a los eventos del kernel, pero decide comparando el estado real del
   archivo con una línea base guardada en la base de datos;
2. una copia confiable de cada archivo, verificada contra esa línea base antes de restaurar;
3. un registro de solo-agregar que guarda, junto con cada evento, su clasificación y su evidencia;
4. una orquestación en la que n8n notifica y registra la decisión de una persona, y el monitor la
   ejecuta.

En el entorno de laboratorio, sobre 250 cambios controlados de cinco tipos, el sistema registró la
detección con una mediana de 5,4 ms y dejó el archivo restaurado (o aislado, si era un archivo nuevo)
con una mediana de 45,4 ms. La alerta con la evidencia llegó a Telegram con una mediana de 1,11 s
desde la escritura del archivo, en una muestra de diez alertas con el bot real. Una vez que la persona
decide, el sistema aplica la decisión con una mediana de 938,6 ms. Todos estos valores se midieron en
una única notebook con WSL2 y sus límites se discuten en la sección 6.4.

## 6.2 Cumplimiento de los objetivos

**Tabla 6.1.** Objetivos específicos y cómo se cumplieron.

| Objetivo específico | Cumplimiento | Dónde se muestra |
|---|---|---|
| 1. Base de datos con línea base e historial de solo-agregar | Cumplido. Línea base versionada y tablas de solo-agregar. Las cuentas de la aplicación no pueden modificar ni borrar lo registrado; esto no alcanza al superusuario de PostgreSQL. | Cap. 4 (4.3 y 4.5) |
| 2. Generador de línea base con copia confiable | Cumplido. Registra hash, permisos y propietario de cada archivo, y lo copia a la bóveda. | Cap. 4 (4.3) |
| 3. Monitor por eventos con todos los tipos de cambio | Cumplido. Detecta modificaciones, creaciones, borrados, movimientos y cambios de permisos y de propietario. | Cap. 4 (4.4); Cap. 5 (5.2) |
| 4. Evidencia diferencial registrada con el evento | Cumplido, con una limitación en escrituras en varios pasos (6.4). | Cap. 4 (4.4) |
| 5. Respuesta automática o sujeta a aprobación | Cumplido. Restauración automática o con aprobación, cuarentena y ventanas de mantenimiento. Reponer el propietario requiere superusuario. | Cap. 4 (4.4) |
| 6. Notificación y decisión humana desde la alerta | Cumplido. Alerta por Telegram con botones y enlaces locales de respaldo, probada con el bot real. | Cap. 4 (4.6 y 4.7) |
| 7. Medición de tiempos y falsos positivos, y contraste con el escaneo periódico | Cumplido. Mediciones repetidas, sin descartar valores, en un único entorno. | Cap. 5 |

## 6.3 Hallazgos principales

**La ventaja del monitoreo por eventos es no esperar, no escanear más rápido.** Un escaneo completo de
719 archivos de configuración tardó una mediana de 9,7 ms; lo que hace lento al enfoque periódico es
la espera hasta el siguiente ciclo. Con un escaneo por minuto, la detección media estimada es de unos
30 s; con el monitor por eventos, la mediana medida fue de 5,4 ms. La fórmula usada para estimar el
enfoque periódico se validó con un escáner real de período corto (4,45 s medidos frente a 5,01 s
calculados).

**En este entorno, el tiempo de restauración lo domina el almacenamiento, no el FIM.** La confirmación
de la escritura en PostgreSQL tardó una mediana de 37,9 ms con el disco en reposo y de 1,8 ms en
ráfaga, y explica la mayor parte de los 45,4 ms de restauración. Esto es consecuencia de una decisión
de diseño (guardar la evidencia antes de restaurar), que prioriza no perder el registro sobre unos
milisegundos de exposición.

**El filtro de temporales elimina los falsos positivos de los editores, a un costo conocido.** Sin el
filtro, el 50,0 % de las alertas con vim y el 66,7 % con nano fueron espurias, todas por los archivos
de intercambio de los editores; con el filtro, ninguna lo fue. A cambio, un archivo malicioso con un
nombre que coincida con un patrón ignorado no se detecta.

**Separar decidir de ejecutar simplificó la seguridad.** Como n8n solo registra decisiones y el monitor
es el único componente que modifica archivos, no fue necesario habilitar en n8n la ejecución de
comandos, cada componente usa una cuenta de base de datos con permisos mínimos, y desde internet solo
es alcanzable una ruta. El costo es que la decisión se aplica cuando el monitor consulta la base de
datos, cada 2 s.

**Medir mostró problemas que la prueba manual no revelaba.** La corrida de prueba reveló dos cosas que
no se habían anticipado: el peso de la confirmación en la base de datos sobre el tiempo de
restauración, y un sesgo en la propia forma de medir la latencia de ejecución, que se corrigió antes de
la corrida definitiva.

## 6.4 Limitaciones

Las siguientes limitaciones deben tenerse en cuenta al interpretar el sistema y sus resultados.

### Detección y evidencia

- **Evidencia incompleta en escrituras en varios pasos.** El monitor reacciona al primer evento de
  escritura y restaura enseguida. Si un programa escribe en varios pasos, lo que escribe después de la
  restauración se pierde: el ataque se frena, pero la copia en cuarentena y el diff muestran solo la
  primera parte.
- **Archivos temporales ignorados.** Un archivo cuyo nombre coincida con los patrones ignorados (por
  ejemplo, `algo.tmp`) no se detecta.
- **Solo directorios.** Se vigilan directorios; no se puede configurar un archivo suelto.
- **Carpeta movida.** Si se mueve un directorio entero, sus archivos de la línea base se restauran en su
  lugar original y los movidos van a cuarentena, pero el directorio nuevo queda vacío: el monitor no
  borra directorios.

### Respuesta

- **Bóveda en el mismo equipo.** La copia confiable está en el mismo disco y pertenece al mismo usuario
  que los archivos vigilados. Verificar su hash contra la base de datos antes de restaurar impide
  restaurar una copia alterada, pero no impide que la alteren.
- **Propietario.** Reponer el propietario de un archivo requiere ejecutar el monitor como superusuario;
  sin esos permisos, el cambio se registra pero no se repone.
- **Base de datos caída.** Sin acceso a la línea base no se restaura: se guarda la evidencia y el evento
  queda en un registro local, pero esos eventos no se reinsertan automáticamente cuando vuelve la base
  de datos.
- **Decisión repetida.** Si el monitor ejecuta una decisión pero no puede registrar la ejecución (por
  ejemplo, porque la base de datos se cayó en ese instante), al reiniciarse la vuelve a ejecutar.
  Restaurar o cerrar un caso dos veces no cambia nada; aceptar un cambio dos veces genera una versión
  de línea base de más.
- **Ventanas que vencen.** Un cambio hecho dentro de una ventana de mantenimiento que no se pasó a la
  línea base vuelve a tratarse como no autorizado en el próximo evento o al reiniciar el monitor.

### Registro y seguridad

- **Inmutabilidad relativa.** El registro es de solo-agregar para las cuentas de la aplicación, no para
  el superusuario de PostgreSQL.
- **Normalización de rutas en ngrok.** Las reglas del túnel se evalúan sobre la ruta normalizada, pero
  ngrok reenvía la ruta original, por lo que algunas variantes codificadas de la ruta permitida
  atraviesan el filtro. Se verificó que no exponen datos: n8n las rechaza o devuelve una página vacía
  del editor que no puede funcionar, porque el resto de las rutas sigue bloqueado. La ruta permitida
  lleva además un sufijo aleatorio de 32 caracteres.
- **Dependencia de servicios externos.** Los botones de decisión dependen de Telegram y del plan
  gratuito de ngrok, con sus límites de uso. Si el túnel no está disponible, solo queda el enlace
  local, que únicamente funciona desde el equipo donde corre n8n.
- **Resultado reconstruido.** Cuando el flujo de respaldo reenvía un evento que no se notificó, deduce el
  resultado de la respuesta a partir de la base de datos; un cambio de propietario que no se pudo
  reponer aparece como pendiente.

### Evaluación

- **Un único entorno.** Las mediciones se hicieron en una notebook con WSL2. Los tiempos de restauración
  dependen del almacenamiento y no son extrapolables a un servidor con disco nativo.
- **Escala.** El directorio vigilado tenía pocos archivos y los cambios se aplicaron de a uno. No se
  evaluaron directorios con miles de archivos ni ráfagas de cambios simultáneos.
- **Falsos positivos.** Se midieron con dos editores en un caso controlado, no en un sistema en
  operación con actualizaciones de paquetes y otros procesos.
- **Muestra con Telegram real.** Tiene diez repeticiones y depende de la red y de un servicio externo.
- **Valores atípicos.** En una repetición se observaron demoras simultáneas en procesos independientes,
  consistentes con una pausa del entorno; la causa exacta no se verificó.
- **Aspectos no probados de punta a punta.** El aviso que se envía cuando pasan 24 horas sin decisión
  no se probó de punta a punta. Tampoco se evaluó el monitor vigilando directorios del sistema con
  permisos de superusuario.

## 6.5 Consideraciones finales

El sistema desarrollado no reemplaza a una plataforma de seguridad de propósito general, pero muestra
que un monitor de integridad liviano, construido con componentes de uso extendido, puede detectar un
cambio en milisegundos, conservar la evidencia de qué cambió, restaurar el archivo y dejar en manos de
una persona, desde su teléfono, la decisión sobre si el cambio era legítimo. Las mediciones permiten
afirmarlo con números propios, obtenidos en un entorno acotado y con sus limitaciones a la vista.
