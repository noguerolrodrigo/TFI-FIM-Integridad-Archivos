# Declaración de uso de herramientas de IA generativa

En este trabajo usé herramientas de inteligencia artificial (IA) generativa. Declaro cuáles fueron,
para qué las usé, qué hice yo y cómo verifiqué lo que generaron.

### Herramientas

- **Gemini (Google), asistente de chat.** Lo usé en la etapa previa, hasta el informe de avance de
  marzo de 2026, como ayuda para escribir los dos scripts originales (`generar_baseline.py` y la
  primera versión de `monitor_fim.py`) y para armar el primer borrador del informe, leyendo y
  contrastando con búsquedas propias. No tengo registrada la versión del modelo.
- **Claude Code (Anthropic).** Lo usé en la etapa de octubre y noviembre de 2026. Los modelos
  figuran en las líneas `Co-Authored-By` del historial del repositorio: Claude Opus 5.5 (commits del
  12 al 19 de octubre), Claude Fable 5.1 (del 26 de octubre al 17 de noviembre) y Claude Fable 5.2
  (17 de noviembre, correcciones de la segunda instancia).
- **Claude (Anthropic), asistente de chat.** Lo usé para planificar los pasos, redactar las
  instrucciones que le daba a Claude Code y revisar sus reportes.

### Para qué las usé

- El código del sistema, las pruebas automatizadas, los scripts de medición y los de armado del
  documento fueron generados por Claude Code a partir de mis instrucciones. En esta etapa no escribí
  el código línea por línea; al principio del trabajo modificaba los archivos a mano.
- La redacción del informe final, la búsqueda y verificación de las referencias, las figuras y los
  gráficos fueron generados por Claude Code a partir del código y de los resultados medidos. El
  primer borrador del informe lo había armado yo con ayuda de Gemini.
- Las correcciones de la segunda instancia se hicieron con las mismas herramientas.

### Qué hice yo

- Definí el tema, el alcance y los objetivos sobre la consigna de la cátedra.
- Trabajé en modo plan: la herramienta proponía y yo leía, preguntaba, y aprobaba o cambiaba cada
  paso antes de que se implementara, con un commit por cambio.
- Tomé las decisiones de diseño: Telegram como canal de alerta; los botones de decisión a través de
  un túnel ngrok; medir la latencia con el bot real además del simulado; combinar el modo automático
  con el modo de aprobación; quitar las referencias que no se pudieron verificar; y no afirmar
  condiciones de red que no había verificado.
- Hice las tareas manuales: instalar y levantar PostgreSQL y n8n, ejecutar las migraciones, crear el
  bot con BotFather, configurar ngrok, probar las alertas y los botones desde mi teléfono, y cada
  publicación al repositorio.

### Cómo verifiqué lo generado

- La batería de pruebas automatizadas se ejecutó en mi equipo y revisé sus resultados.
- Las mediciones se ejecutaron en mi equipo y revisé sus resultados; los CSV quedaron versionados. Ningún número del informe
  proviene de la herramienta sin un dato medido que lo respalde.
- Hice pruebas manuales de extremo a extremo: evento, alerta en el teléfono, decisión y
  restauración.
- Leí los reportes de cada paso y el informe completo.
- De las referencias, quedaron solo las que se pudieron abrir y verificar.

**Trazabilidad.** El historial del repositorio conserva la coautoría en cada commit hecho con la
herramienta, y los archivos `CLAUDE.md` y `docs/PROMPT_inicial.md` contienen las instrucciones que
se le dieron.

**Normativa.** No identifiqué una normativa específica de la Facultad sobre este tema. Esta
declaración sigue lo indicado por el tribunal en la devolución de la primera instancia.
