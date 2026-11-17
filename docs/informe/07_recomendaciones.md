# CAPÍTULO 7: Recomendaciones

Las recomendaciones se dividen en dos grupos: las que corresponde aplicar antes de usar el sistema en
un entorno productivo y las líneas de trabajo futuro que surgen de las limitaciones del Capítulo 6.

## 7.1 Para un uso en producción

1. **Ejecutar el monitor como servicio y, solo bajo ciertas condiciones, como superusuario.** El
   monitor debería ejecutarse como servicio del sistema operativo, para que se reinicie solo ante una
   falla y al arrancar el equipo. Vigilar directorios del sistema y reponer el propietario de los
   archivos requiere además permisos de superusuario, y con esos permisos cualquier defecto de la
   restauración tiene más alcance. Por eso, antes de ejecutarlo como superusuario deben cumplirse
   tres condiciones. Primero, que el directorio vigilado no contenga enlaces simbólicos legítimos, o
   que antes se implemente su soporte en la línea base (sección 7.2): con la versión actual, el
   monitor eliminaría los enlaces que encuentre, por lo que no debe apuntarse a `/etc` tal como está
   (en el equipo de desarrollo contiene 765 enlaces). Segundo, que se cierre el intervalo entre la
   comprobación de la carpeta y la escritura (secciones 6.4 y 7.2), o que nadie más que el
   administrador pueda escribir en los directorios vigilados. Tercero, que se evalúe el monitor
   vigilando directorios del sistema, algo que no formó parte de este trabajo.
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
   mueve un directorio entero, y revisar en el momento los enlaces que contenga.
6. **Soportar enlaces simbólicos en la línea base.** Registrar cada enlace como tal, con su destino,
   para poder vigilar directorios que los contienen (como `/etc`) y detectar si un enlace se crea, se
   borra o cambia de destino, en lugar de eliminarlos.
7. **Restaurar sin depender de los nombres de las carpetas.** Abrir la carpeta de destino tramo por
   tramo desde el directorio vigilado, sin seguir enlaces, y crear y renombrar el temporal relativo a
   ese descriptor (`dir_fd`), para eliminar el intervalo que hoy queda entre comprobar la carpeta y
   escribir. Con el mismo criterio, mover a cuarentena los archivos nuevos y leer la bóveda sin
   volver a abrir por nombre lo que ya se verificó.
8. **Ampliar la evaluación.** Repetir las mediciones en un servidor con disco nativo, con directorios
   de miles de archivos, con ráfagas de cambios simultáneos y con actualizaciones reales de paquetes,
   para medir los falsos positivos en un sistema en operación.
9. **Probar los casos pendientes.** Verificar de punta a punta el aviso de 24 horas sin decisión y el
   funcionamiento con permisos de superusuario sobre directorios del sistema.
