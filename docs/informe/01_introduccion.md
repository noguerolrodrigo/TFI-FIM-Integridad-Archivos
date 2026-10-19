# CAPÍTULO 1: Introducción

## 1.1 Contexto del problema

En la actualidad, las organizaciones dependen de infraestructuras informáticas para gestionar,
procesar y almacenar información crítica para su funcionamiento operativo y comercial. Dentro de
estas infraestructuras, la integridad de los datos es uno de los pilares de la seguridad de la
información. Los archivos de configuración del sistema operativo, los de los servicios web y los
binarios ejecutables son un objetivo frecuente de los atacantes, que buscan alterarlos de forma
silenciosa para instalar puertas traseras, desactivar controles o asegurarse la persistencia dentro
de un sistema comprometido.

## 1.2 Planteamiento del problema

A pesar de la disponibilidad de soluciones de seguridad, muchas organizaciones pequeñas y medianas no
cuentan con procesos sistemáticos que les permitan advertir a tiempo una modificación no autorizada
de sus archivos. El monitoreo de integridad de archivos (File Integrity Monitoring, FIM) se ha
abordado tradicionalmente con herramientas de código abierto como Tripwire o AIDE, que, en su uso
habitual, comparan el estado del sistema de archivos con una base de referencia en ejecuciones
programadas. Este enfoque deja una ventana de exposición entre una verificación y la siguiente:
durante ese intervalo, una alteración pasa inadvertida.

Existen herramientas que reducen esa ventana. La plataforma Wazuh, por ejemplo, incluye un módulo
de FIM que, además de los escaneos programados (cada 12 horas en su configuración por defecto),
permite el monitoreo en tiempo real de directorios en Linux y Windows y, con la opción
`report_changes`, informa el contenido exacto que cambió en un archivo de texto (Wazuh Inc., 2026).
Sin embargo, se trata de una plataforma de propósito general, cuya adopción supone desplegar y
mantener un conjunto de componentes que excede las necesidades y los recursos de muchas
organizaciones pequeñas.

Además de detectar, interesa responder. Cuando se detecta un cambio, la restauración automática del
archivo reduce el tiempo de exposición, pero también puede revertir un cambio legítimo de un
administrador; dejar la decisión en manos de una persona evita ese error, pero el archivo alterado
sigue activo mientras se espera. Un sistema de integridad útil debe permitir equilibrar ambas
opciones y dejar registro de lo que se decidió.

Frente a este escenario, la pregunta de investigación que guía el trabajo es: **¿de qué manera puede
desarrollarse un sistema automatizado que detecte alteraciones de archivos en tiempo real en
entornos Linux, extraiga y clasifique la evidencia diferencial de forma inmediata y permita una
respuesta controlada ante el incidente?**

## 1.3 Justificación y relevancia del estudio

La identificación temprana de alteraciones permite acotar el daño de una intrusión y facilita la
respuesta ante incidentes. Este trabajo se justifica por la posibilidad de construir un sistema de
monitoreo de integridad con tecnologías de código abierto y de uso extendido (Python, PostgreSQL y
la plataforma de automatización n8n), y de **medir** su desempeño en lugar de suponerlo.

Desde la perspectiva forense, el sistema guarda, junto con cada alerta, la evidencia del cambio: los
hashes anterior y nuevo, una copia del archivo alterado y, en los archivos de texto, las líneas
exactas que se agregaron o quitaron. Esto reduce el tiempo de análisis, porque quien recibe la alerta
ve qué cambió sin tener que investigarlo a mano.

El trabajo responde, además, a la consigna de la cátedra para el proyecto de integridad de archivos
(Cortez, 2024), cuyos ejes son la detección de cambios no autorizados, las alertas y la respuesta
automatizada.

## 1.4 Objetivos de la investigación

### 1.4.1 Objetivo general

Desarrollar, implementar y evaluar un sistema automatizado de monitoreo de integridad de archivos
para entornos Linux, capaz de detectar en tiempo real modificaciones no autorizadas, registrar su
evidencia diferencial, responder ante ellas y notificarlas para su decisión humana, midiendo su
desempeño.

### 1.4.2 Objetivos específicos

1. Diseñar una base de datos PostgreSQL que almacene la línea base de integridad y el historial de
   eventos como un registro de solo-agregar, en el que las cuentas de la aplicación no puedan
   modificar ni borrar lo registrado.
2. Desarrollar un generador de línea base que registre, para cada archivo vigilado, su hash SHA-256,
   sus permisos y su propietario, y que conserve una copia confiable para restaurarlo.
3. Implementar un motor de monitoreo basado en los eventos del sistema de archivos (subsistema inotify,
   mediante la biblioteca watchdog) que detecte modificaciones, creaciones, borrados, movimientos y
   cambios de permisos o de propietario.
4. Extraer la evidencia diferencial de cada cambio comparando el archivo con su copia confiable, y
   registrarla junto con el evento.
5. Implementar una respuesta ante cada cambio, con restauración automática o sujeta a aprobación,
   aislamiento en cuarentena de los archivos nuevos y mecanismos para autorizar cambios legítimos.
6. Orquestar la notificación y la decisión humana con n8n y Telegram, de modo que la persona pueda
   confirmar un incidente, restaurar o aceptar un cambio desde la propia alerta.
7. Medir los tiempos de detección, restauración, alerta y ejecución de decisiones, y la tasa de
   falsos positivos, y contrastar el enfoque por eventos con el de escaneo periódico.

## 1.5 Alcance y limitaciones

El trabajo abarca el diseño, la implementación y la evaluación de un sistema funcional en un entorno
de laboratorio: Ubuntu ejecutado sobre el Subsistema de Windows para Linux (WSL2). Los directorios a
vigilar son configurables, de modo que el sistema puede aplicarse a directorios críticos como `/etc`,
`/usr/bin` o `/var/www`; sin embargo, la evaluación se realizó sobre un directorio de prueba, y los
archivos de `/etc` solo se usaron, copiados, para medir la duración de un escaneo completo. Vigilar
directorios del sistema y reponer el propietario de un archivo requiere ejecutar el monitor con
permisos de superusuario, algo que no formó parte de la evaluación.

El sistema depende del subsistema inotify, por lo que se limita a sistemas con kernel Linux. Las
mediciones corresponden a un único equipo y a cambios aplicados de a uno; no se evaluaron
directorios con miles de archivos ni ráfagas de cambios simultáneos. Las limitaciones identificadas
durante el desarrollo y la evaluación se detallan en el Capítulo 6.
