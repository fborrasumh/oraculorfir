/* ══ Datos: el banco oficial (data/rfir.json, lo genera la GitHub Action) o, si aún no existe, un DEMO marcado como ficticio ══ */
const ASIGS_BASE = [
  ['matematicas', 'Matemáticas y Métodos numéricos'], ['mecanica', 'Mecánica y Física general'], ['electromagnetismo', 'Electromagnetismo y Electrónica'], ['optica', 'Óptica y Ondas'], ['termodinamica', 'Termodinámica y Física estadística'], ['cuantica', 'Física cuántica, atómica y molecular'], ['nuclear', 'Física nuclear y de partículas'], ['interaccion', 'Interacción de la radiación con la materia'], ['dosimetria', 'Dosimetría e Instrumentación'], ['radiobiologia', 'Radiobiología'], ['proteccion', 'Protección radiológica y Legislación'], ['radiodiagnostico', 'Radiodiagnóstico e Imagen médica'], ['medicina_nuclear', 'Medicina nuclear'], ['radioterapia', 'Radioterapia'], ['estadistica', 'Estadística y Tratamiento de datos'],
  ['otras', 'Sin clasificar']
].map(([id, nombre]) => ({id, nombre}));

/* DEMO · preguntas ESCRITAS PARA LA DEMOSTRACIÓN (no son preguntas oficiales del RFIR); sirven para probar la app sin datos */
const DEMO_PREG = [
  ["mecanica", "Un cuerpo se deja caer desde el reposo en el vacío. Si se desprecia todo rozamiento, ¿cómo varía su velocidad con el tiempo?", ["Es constante.", "Crece linealmente con el tiempo.", "Crece con el cuadrado del tiempo.", "Decrece exponencialmente."], 2],
  ["electromagnetismo", "Dos resistencias de 6 Ω se conectan en paralelo. ¿Cuál es la resistencia equivalente?", ["3 Ω.", "6 Ω.", "12 Ω.", "36 Ω."], 1],
  ["optica", "Cuando la luz pasa de un medio a otro de mayor índice de refracción, el rayo refractado:", ["Se aleja de la normal.", "Se acerca a la normal.", "No cambia de dirección en ningún caso.", "Se refleja siempre totalmente."], 2],
  ["cuantica", "Según la relación de Planck-Einstein, la energía de un fotón es directamente proporcional a:", ["Su longitud de onda.", "Su frecuencia.", "El cuadrado de su frecuencia.", "La intensidad del haz."], 2],
  ["nuclear", "Una fuente radiactiva tiene un periodo de semidesintegración de 6 horas. ¿Qué fracción de su actividad inicial queda a las 18 horas?", ["La mitad.", "Un cuarto.", "Un octavo.", "Un dieciseisavo."], 3],
  ["nuclear", "En la desintegración beta menos, un neutrón del núcleo se transforma en:", ["Un protón, un electrón y un antineutrino.", "Un protón, un positrón y un neutrino.", "Una partícula alfa.", "Un fotón gamma y un neutrino."], 1],
  ["interaccion", "En tejido blando, ¿qué interacción de los fotones predomina en el intervalo de energías de la radioterapia con megavoltaje?", ["El efecto fotoeléctrico.", "La dispersión Compton.", "La producción de pares.", "La dispersión coherente (Rayleigh)."], 2],
  ["dosimetria", "¿Cuál es la unidad de dosis absorbida en el Sistema Internacional?", ["El sievert.", "El becquerel.", "El gray.", "El roentgen."], 3],
  ["radiobiologia", "En el modelo lineal-cuadrático, un cociente alfa/beta bajo es característico de:", ["Los tejidos de respuesta tardía.", "Los tejidos de respuesta aguda.", "Todos los tumores.", "Las células hipóxicas exclusivamente."], 1],
  ["proteccion", "¿Qué magnitud se usa para expresar el riesgo de efectos estocásticos de una exposición no uniforme del cuerpo?", ["La dosis absorbida.", "El kerma en aire.", "La dosis efectiva.", "La exposición."], 3],
  ["radiodiagnostico", "En tomografía computarizada, ¿qué valor tiene el agua en unidades Hounsfield?", ["-1000.", "0.", "+100.", "+1000."], 2],
  ["radioterapia", "En un haz de fotones de megavoltaje, la dosis máxima en profundidad no está en la superficie porque:", ["Hay que alcanzar el equilibrio electrónico.", "Los fotones se absorben solo en profundidad.", "El colimador bloquea la superficie.", "La piel no absorbe radiación."], 1]
].map(([asig, enunciado, opciones, correcta], i) => ({id: 'demo-' + (i + 1), anio: 0, n: i + 1, asig, enunciado, opciones, correcta, anulada: false, imagen: false, demo: true}));

/* DEMO · recuentos FICTICIOS de 2015 a 2026 (no son datos reales): solo para ver la predicción funcionando */
function demoConteos() {
  const base = {"matematicas": 12, "mecanica": 16, "electromagnetismo": 18, "optica": 12, "termodinamica": 10, "cuantica": 14, "nuclear": 18, "interaccion": 16, "dosimetria": 16, "radiobiologia": 8, "proteccion": 14, "radiodiagnostico": 14, "medicina_nuclear": 10, "radioterapia": 14, "estadistica": 8};
  const r = rng('demo-oraculorfir'), c = {};
  for (let y = 2015; y <= 2026; y++) {
    c[y] = {};
    for (const k in base) { const tr = k === 'radioterapia' ? (y - 2015) * 0.35 : k === 'termodinamica' ? -(y - 2015) * 0.25 : 0; c[y][k] = Math.max(0, Math.round(base[k] * 1.05 + tr + (r() - 0.5) * 5)); }
  }
  return c;
}

let DATA = {real: false, asignaturas: ASIGS_BASE, preguntas: DEMO_PREG, conteos: demoConteos(), examenes: [], generado: null};
const nombreAsig = id => t((DATA.asignaturas.find(a => a.id === id) || {nombre: id}).nombre);
/* Carga data/rfir.json (mismo origen, en GitHub Pages). Abierta como fichero local o sin datos todavía → DEMO */
async function cargaDatos() {
  try {
    const r = await fetch('data/rfir.json', {cache: 'no-cache'});
    if (!r.ok) throw 0;
    const j = await r.json();
    const ps = (j.preguntas || []).filter(q => q && q.enunciado && q.anio);
    if (ps.length < 100) throw 0;
    DATA = {real: true, asignaturas: j.asignaturas || ASIGS_BASE, preguntas: ps, conteos: conteos(ps), examenes: j.examenes || [], generado: j.generado || null, clasificacion: j.clasificacion || ''};
    try { const a = await (await fetch('data/asignaturas.json', {cache: 'no-cache'})).json(); DATA.kws = Object.fromEntries((a.asignaturas || []).map(x => [x.id, x.kw || []])); } catch { DATA.kws = {}; }
  } catch { /* se queda el DEMO */ }
  return DATA;
}
