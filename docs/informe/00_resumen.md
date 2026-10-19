# Resumen

Este trabajo presenta el diseño, la implementación y la evaluación de un sistema automatizado de
monitoreo de integridad de archivos (File Integrity Monitoring, FIM) para Linux. El sistema reacciona
a los eventos del kernel (inotify, mediante la biblioteca watchdog de Python) y compara el estado real
de cada archivo con una línea base versionada en PostgreSQL. Así clasifica el cambio (modificación,
creación, borrado, movimiento o cambio de permisos) y guarda la evidencia: los hashes SHA-256 anterior
y nuevo, una copia del archivo alterado y, en los archivos de texto, el diff de las líneas cambiadas.

Como respuesta, restaura el archivo desde una copia verificada contra la base de datos o lo aísla en
cuarentena, con un modo de aprobación y ventanas de mantenimiento para no revertir cambios legítimos.
Con n8n, cada alerta llega por Telegram con botones para confirmar el incidente, restaurar o aceptar
el cambio, y el monitor ejecuta la decisión. El registro es de solo-agregar y cada componente opera
con permisos mínimos.

En un laboratorio sobre WSL2, con 50 repeticiones de cinco tipos de cambio, la detección tuvo una
mediana de 5,4 ms y la restauración, de 45,4 ms, dominada por la escritura en la base de datos. La
alerta llegó a Telegram con una mediana de 1,11 s, en diez alertas con el bot real. El filtro de
archivos temporales bajó los falsos positivos de dos editores del 50,0 % y el 66,7 % al 0 %. Con un
escaneo por minuto, la detección media estimada sería de unos 30 s. Los resultados corresponden a un
único entorno y sus limitaciones se detallan en el informe.

**Palabras clave:** monitoreo de integridad de archivos, FIM, inotify, SHA-256, evidencia
diferencial, respuesta ante incidentes, n8n.
