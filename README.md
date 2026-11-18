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

Hay **25 exámenes RFIR** (2002–2026), **21 con su respuesta oficial**; en total 5.922 preguntas.
Los años sin plantilla cuentan para la predicción (cuántas preguntas tiene cada asignatura), pero no entran en los simulacros.

| Año del examen | Preguntas | Con respuesta | Cuaderno | Respuestas |
|---|---|---|---|---|
| 2002 | 260 | — | radiofisicagratis.wordpress.com | sin plantilla: solo cuenta para la predicción |
| 2003 | 260 | 240 | radiofisicagratis.wordpress.com | radiofisicagratis.wordpress.com |
| 2004 | 260 | 249 | radiofisicagratis.wordpress.com | radiofisicagratis.wordpress.com |
| 2005 | 260 | 245 | radiofisicagratis.wordpress.com | radiofisicagratis.wordpress.com |
| 2006 | 260 | 244 | radiofisicagratis.wordpress.com | radiofisicagratis.wordpress.com |
| 2007 | 259 | 247 | radiofisicagratis.wordpress.com | radiofisicagratis.wordpress.com |
| 2008 | 260 | 244 | radiofisicagratis.wordpress.com | radiofisicagratis.wordpress.com |
| 2009 | 260 | — | radiofisicagratis.wordpress.com | sin plantilla: solo cuenta para la predicción |
| 2010 | 260 | 248 | radiofisicagratis.wordpress.com | radiofisicagratis.wordpress.com |
| 2011 | 260 | 247 | radiofisicagratis.wordpress.com | radiofisicagratis.wordpress.com |
| 2012 | 260 | 241 | radiofisicagratis.wordpress.com | radiofisicagratis.wordpress.com |
| 2013 | 235 | 221 | radiofisicagratis.wordpress.com | radiofisicagratis.wordpress.com |
| 2014 | 235 | 223 | radiofisicagratis.wordpress.com | radiofisicagratis.wordpress.com |
| 2015 | 235 | 222 | radiofisicagratis.wordpress.com | radiofisicagratis.wordpress.com |
| 2016 | 235 | — | radiofisicagratis.wordpress.com | sin plantilla: solo cuenta para la predicción |
| 2017 | 235 | — | radiofisicagratis.wordpress.com | sin plantilla: solo cuenta para la predicción |
| 2018 | 235 | 225 | radiofisicagratis.wordpress.com | radiofisicagratis.wordpress.com |
| 2019 | 235 | 225 | radiofisicagratis.wordpress.com | radiofisicagratis.wordpress.com |
| 2020 | 183 | 181 | consalud.es | radiofisicagratis.wordpress.com |
| 2021 | 185 | 179 | radiofisicagratis.wordpress.com | radiofisicagratis.wordpress.com |
| 2022 | 210 | 210 | Portal FSE del Ministerio | Portal FSE del Ministerio |
| 2023 | 210 | 208 | Portal FSE del Ministerio | Portal FSE del Ministerio |
| 2024 | 210 | 208 | Portal FSE del Ministerio | Portal FSE del Ministerio |
| 2025 | 210 | 209 | Portal FSE del Ministerio | Portal FSE del Ministerio |
| 2026 | 210 | 203 | Portal FSE del Ministerio | Portal FSE del Ministerio |

**De dónde sale cada cosa**

- **Portal FSE del Ministerio de Sanidad** (2022 en adelante): `scripts/rfir_fetch.py` pide a la API de su web el cuaderno de la versión 0 y la hoja de respuestas definitiva.
- **Años anteriores**: el Ministerio ya no los publica. `scripts/rfir_cosecha.py` recorre las fuentes de `data/fuentes_externas.json` (`_cosecha`): webs, noticias, paquetes .zip y copias archivadas en la Wayback Machine. Mira dentro de cada PDF si es un cuaderno o una plantilla, de qué titulación y de qué año.
- **HEAD-QA** (Vilares y Gómez-Rodríguez, ACL 2019; v2: Correa-Guillén, Gómez-Rodríguez y Vilares, 2025; licencia MIT) guarda los cuadernos oficiales y su respuesta correcta. Se usa de dos formas: sus PDF originales pasan por las mismas comprobaciones, y sus respuestas solo se toman si el cuaderno es el mismo, pregunta a pregunta (`scripts/rfir_headqa.py`).

**Comprobaciones antes de aceptar un año copiado** (`scripts/rfir_externos.py`)

- El año del examen se lee en el propio cuaderno: «PRUEBAS SELECTIVAS 2012» es el examen de enero de 2013.
- La titulación se comprueba en la portada.
- Se prefiere la versión 0. Si solo hay otra versión, la plantilla tiene que ser de esa misma versión.
- Deben salir al menos el 90 % de las preguntas que anuncia la portada.
- La plantilla debe cubrir el 90 % de las preguntas.
- No se acepta una plantilla provisional ni una que ya se haya usado para otro año.
- **La IA resuelve 30 preguntas del cuaderno y debe coincidir con la plantilla en al menos el 60 %.** Con la plantilla de ese examen coinciden casi todas (80–100 %); con la de otro año, solo las que acierta el azar (en torno al 25 %). Así se evita emparejar una plantilla con el año equivocado cuando su nombre o su texto no lo dejan claro.

Los años copiados se marcan en la app como «tomada de una copia del cuaderno oficial».

**Revisa a mano al menos 20 preguntas por año contra el PDF antes de dar los datos por buenos.**

Mientras no exista `data/rfir.json`, la app funciona en **modo demostración**: recuentos ficticios y 12 preguntas escritas para la demo, ambos marcados como tales.

El flujo **Actions → «Datos RFIR»** (`.github/workflows/datos-rfir.yml`) lo hace todo:

- **todo**: portal, cosecha, validación, HEAD-QA, extracción y clasificación con IA.
- **cosecha**: solo los años antiguos.
- **calibrar**: mide el panel de agentes.
- **imagenes**: baja los cuadernillos de imágenes.

`scripts/rfir_clasifica_ia.py` asigna con IA la asignatura de cada pregunta (secreto `OPENAI_API_KEY`).

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
