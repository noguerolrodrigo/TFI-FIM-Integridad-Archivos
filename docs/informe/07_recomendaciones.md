# CAPÍTULO 7: Recomendaciones

Las recomendaciones se dividen en dos grupos: las que corresponde aplicar antes de usar el sistema en
un entorno productivo y las líneas de trabajo futuro que surgen de las limitaciones del Capítulo 6.

## 7.1 Para un uso en producción

1. **Ejecutar el monitor como servicio y con los permisos necesarios.** Para vigilar directorios del
   sistema y reponer el propietario de los archivos, el monitor debe ejecutarse con permisos de
   superusuario, como servicio del sistema operativo, para que se reinicie solo ante una falla y al
   arrancar el equipo. Antes de hacerlo, debe evaluarse vigilando directorios del sistema, algo que no
   formó parte de este trabajo.
2. **Proteger la bóveda.** Ubicar la copia confiable en otro equipo, o al menos hacer que pertenezca a
   un usuario distinto del que puede modificar los archivos vigilados, de modo que comprometer un
   archivo no permita también alterar su copia.
3. **Proteger el registro también frente al administrador de la base de datos.** El registro es de
   solo-agregar para las cuentas de la aplicación. Para que lo sea también frente al superusuario,
   puede enviarse una copia de los eventos a un almacenamiento externo de solo escritura.
4. **Elegir el modo de restauración según el sistema.** En servidores donde los cambios legítimos son
   frecuentes, conviene usar el modo de aprobación o las ventanas de mantenimiento, para no revertir el
   trabajo de los administradores. Donde los cambios legítimos son raros, la restauración automática
   reduce el tiempo de exposición.
5. **Revisar los patrones ignorados.** Mantener la lista de archivos temporales lo más acotada posible,
   y revisar periódicamente la cuarentena y el directorio vigilado en busca de archivos con esos
   nombres.
6. **Reducir la dependencia del plan gratuito de ngrok.** Para un uso continuo, conviene evaluar un
   dominio propio con un proxy inverso y certificado TLS, en el que las reglas de filtrado se apliquen
   sobre la ruta tal como llega. Mientras tanto, el enlace local sigue disponible como respaldo.

## 7.2 Trabajo futuro

1. **Reinsertar los eventos pendientes.** Al recuperar la conexión con la base de datos, el monitor
   debería reinsertar los eventos guardados en el registro local, conservando su fecha original.
2. **Evitar la ejecución repetida de decisiones.** Registrar que una decisión está en curso antes de
   ejecutarla, o hacer que aceptar un cambio dos veces no genere una versión de línea base de más.
3. **Aplicar las decisiones sin consulta periódica.** En PostgreSQL, el comando `NOTIFY` envía una
   notificación asíncrona a las sesiones que ejecutaron `LISTEN` sobre el mismo canal, y puede
   ubicarse en un disparador de la tabla para avisar de sus cambios (PostgreSQL Global Development
   Group, s.f.). Un disparador sobre la tabla `decisiones` permitiría que el monitor aplique cada
   decisión apenas se registra, en lugar de consultar cada 2 s. Su efecto debería medirse.
4. **Capturar la evidencia completa en escrituras largas.** Se podría guardar la evidencia cuando el
   programa termina de escribir el archivo, sin demorar la restauración, y medir cuánto cambia el
   tiempo de exposición.
5. **Manejar los directorios movidos.** Detectar y aislar el directorio nuevo que queda vacío cuando se
   mueve un directorio entero.
6. **Ampliar la evaluación.** Repetir las mediciones en un servidor con disco nativo, con directorios
   de miles de archivos, con ráfagas de cambios simultáneos y con actualizaciones reales de paquetes,
   para medir los falsos positivos en un sistema en operación.
7. **Probar los casos pendientes.** Verificar de punta a punta el aviso de 24 horas sin decisión y el
   funcionamiento con permisos de superusuario sobre directorios del sistema.
