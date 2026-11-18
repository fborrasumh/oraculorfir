# OráculoRFIR

Qué asignaturas caerán en el RFIR 2027 (Física, sábado 23 de enero de 2027), estimado a partir de los exámenes RFIR oficiales, con simulacros de preguntas oficiales y un generador de preguntas nuevas revisadas por varios agentes de IA. Aplicación web de un solo fichero.

**Usar la app:** https://fborrasumh.github.io/oraculorfir/
**Idiomas:** español (por defecto), inglés y portugués. Se cambia en el selector de la barra superior o con `?lang=en` / `?lang=pt` en la URL. Las preguntas del RFIR se muestran siempre en español.

Forma parte de la familia [Oráculo](https://fborrasumh.github.io/oraculo/) (MIR, EIR, FIR, PIR, BIR, QIR y RFIR). Es la misma app que [OráculoFIR](https://github.com/fborrasumh/oraculofir), adaptada a la titulación de Física: asignaturas, palabras clave, prompts de los agentes y preguntas de demostración propias.

## Qué hace

1. **Predicción por asignatura** (Matemáticas y Métodos numéricos, Mecánica y Física general, Electromagnetismo y Electrónica, Óptica y Ondas, Termodinámica y Física estadística, Física cuántica, atómica y molecular…): cuántas preguntas tendrá cada una en 2027 sobre 200, con un intervalo del 80 %. Media ponderada en la que los años recientes pesan más (semivida de 4 años), más la mitad de la tendencia lineal.
2. **Cuánto fiarse:** validación a ciegas en los tres últimos RFIR, frente a dos referencias sencillas (repetir el año anterior y la media de todos los años).
3. **Simulacro probable** con preguntas oficiales en la proporción prevista, puntuado como el RFIR (+3, −1, 0) y con reloj opcional (270 minutos para 210 preguntas).
4. **Reto diario**, igual para todo el mundo, con racha y resultado en emojis.
5. **Generador con un panel de cinco agentes** (redactor, dos resolutores a ciegas, Contradictor y Lista de control) con la clave de IA de cada persona; exporta a Word, CSV y Moodle (GIFT).
6. **Examen RFIR 2027 completo con IA**, «¿Por qué?» en cada pregunta corregida, repaso espaciado de fallos, banco por año y buscador, instalable y sin conexión.

## Lo que no hace

- **No predice preguntas concretas**, solo cuántas tendrá cada asignatura.
- **La clasificación por asignatura es automática** (IA con el secreto `OPENAI_API_KEY`, o palabras clave de `data/asignaturas.json` si no hay clave) y se equivoca en algunas preguntas.
- **Que el panel apruebe una pregunta no garantiza que sea correcta.** Las únicas respuestas con respaldo oficial son las de las preguntas oficiales.
- Herramienta independiente, sin relación con el Ministerio de Sanidad.

## Datos

Mientras no exista `data/rfir.json`, la app funciona en **modo demostración**: recuentos ficticios y 12 preguntas escritas para la demo, ambos marcados como tales.

El flujo **Actions → «Datos RFIR»** (`.github/workflows/datos-rfir.yml`) se lanza solo la primera vez que se sube y después a mano (**Run workflow**):

1. `scripts/rfir_fetch.py --api` abre el portal FSE con Chromium, obtiene su token anónimo y pide a su API, convocatoria a convocatoria, el cuaderno de la versión 0 y la hoja de respuestas definitiva. El código de titulación de Física se prueba entre «R», «RF», «FI», «FS», «FIS», «RFIR» y se acepta solo si la portada del cuaderno es de Física.
2. `scripts/rfir_externos.py` completa años antiguos con las URL de `data/fuentes_externas.json` (vacío por ahora: añade copias de los cuadernos y plantillas oficiales si quieres más años).
3. `scripts/rfir_datos.py` extrae preguntas, opciones y respuesta oficial y escribe `data/rfir.json` y `data/informe.md`.
4. `scripts/rfir_clasifica_ia.py` asigna la asignatura de cada pregunta con IA (secreto `OPENAI_API_KEY`).

Con el paso `calibrar`, `scripts/rfir_calibracion.py` mide el panel de agentes con 100 preguntas oficiales y guarda `data/calibracion.json`. Con `imagenes`, se bajan los cuadernillos de imágenes.

**Revisa a mano al menos 20 preguntas por año contra el PDF antes de dar los datos por buenos.**

## Desarrollo y pruebas

```bash
python3 scripts/i18n_fuente.py     # regenera src/i18n.js (diccionarios en/pt)
python3 build.py                   # monta index.html
node tests/test_nucleo.js          # lógica pura
python3 tests/test_datos.py        # extractor de PDF
python3 tests/smoke_test.py        # la app en Chromium con IA simulada
```

## Autoría

Fernando Borrás Rocher (ORCID 0000-0002-5519-4573), Universidad Miguel Hernández de Elche. Licencia MIT.
