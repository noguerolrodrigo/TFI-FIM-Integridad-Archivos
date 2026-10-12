Arrancamos a trabajar en mi Trabajo Final Integrador. Leé CLAUDE.md, los dos scripts .py,
sql/01_schema.sql y los tres documentos de docs/. Todavía no modifiques nada.

## Paso 1 — Diagnóstico (solo lectura)
Dame un informe corto con:
1. Qué hace hoy el sistema, comparado con lo que prometen el informe de avance y el .docx de n8n.
2. Problemas y riesgos del código actual. Revisá por lo menos estos:
   - Solo detecta modificaciones: no cubre creación, borrado, movimiento ni cambios de permisos.
   - La restauración usa una copia en RAM: si el monitor se reinicia, se pierde el respaldo.
   - Nunca compara contra el hash de la baseline guardado en la BD.
   - Abre una conexión nueva a la BD por cada evento.
   - `./cuarentena` no se crea si no existe (está en .gitignore, así que un clone limpio falla).
   - La copia en cuarentena siempre termina en .txt, aunque el archivo no sea de texto.
   - La columna `notificado` no se usa.
   - `fecha_registro` es TIMESTAMP sin zona horaria.
   - Falta `observer.join()` al final.
3. Contra la consigna (docs/Proyecto_07_Integridad_Archivos.md): qué criterios ya cubro y cuáles no.

Pará acá y esperá mi OK.

## Paso 2 — Plan de mejoras del motor
En modo plan, proponé las mejoras en orden, cada una pensada como un commit separado:
- Manejar on_created, on_deleted, on_moved y cambios de permisos/propietario.
- Bóveda de respaldo en disco (copia de cada archivo al generar la baseline), para restaurar
  aunque el monitor se haya reiniciado.
- Verificación contra el hash de la baseline en la BD.
- Ignorar temporales de editores (.swp, ~, .tmp) para bajar falsos positivos.
- Conexión reutilizable a la BD; rutas a vigilar configurables por .env.
Hay una decisión de diseño que quiero discutir antes de implementar: hoy la restauración es
automática, pero el .docx propone aprobación humana antes de restaurar (nodo Wait de n8n).
Explicame pros y contras de cada opción, o de combinarlas (por ejemplo, cuarentena automática
y restauración con aprobación), y recomendame una.

## Paso 3 — Orquestación con n8n (después de las mejoras)
Basado en el .docx. Arquitectura push: el monitor registra el evento en la BD y hace un POST a un
Webhook de n8n. Workflow a construir y exportar en `n8n/`:
Webhook → consulta del historial en Postgres → If (¿cambio autorizado?) → alerta por Telegram o
Email con archivo, hashes y diff → aprobación humana (Wait) → restauración y registro en la BD.
Más el playbook PB-A para actualizar la baseline de forma autorizada.
Proponé cómo levantar n8n en WSL (Docker o npx) y conectarlo a Postgres.

## Paso 4 — Medición y pruebas
- `scripts/medir_metricas.py`: modificaciones controladas que miden en ms el tiempo desde la escritura
  hasta el registro en BD (MTTD) y hasta la restauración (MTTR). Resultados en CSV.
- Tests con pytest para hash, diff, cuarentena y restauración.
- Los números del informe final salen de esos CSV.

Reglas: trabajá paso por paso, explicame cada decisión en criollo (la tengo que defender ante el
tribunal), hacé un commit por cambio y no avances sin mi OK.
