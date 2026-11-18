/* ══ Núcleo de OráculoRFIR: lógica pura, sin DOM (se prueba en Node con tests/test_nucleo.js) ══
   · conteos por año y asignatura · predicción con validación a ciegas · muestreo reproducible · puntuación RFIR
   · comprobaciones del generador multiagente (formato, plagio del banco, acuerdo entre agentes) ══ */
const N_RFIR = 200;                                          // preguntas puntuables del RFIR (más 10 de reserva)
const FECHA_RFIR = '2027-01-23T14:00:00+01:00';             // Orden SND/854/2026 (BOE 10-8-2026)
const ANIO_OBJ = 2027;

/* generador pseudoaleatorio con semilla (mulberry32): mismo texto → mismo examen en cualquier móvil */
function semillaDe(s) { let h = 1779033703 ^ String(s).length; for (let i = 0; i < String(s).length; i++) { h = Math.imul(h ^ String(s).charCodeAt(i), 3432918353); h = h << 13 | h >>> 19; } return h >>> 0; }
function rng(seed) { let a = typeof seed === 'number' ? seed >>> 0 : semillaDe(seed); return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function baraja(arr, r) { const a = arr.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }

/* {año: {asig: n}} y totales por año */
function conteos(preguntas) {
  const c = {};
  for (const q of preguntas) { (c[q.anio] = c[q.anio] || {}); c[q.anio][q.asig] = (c[q.anio][q.asig] || 0) + 1; }
  return c;
}
const aniosDe = c => Object.keys(c).map(Number).sort((a, b) => a - b);
function cuotas(c) {   // proporción de cada asignatura en cada examen (los exámenes antiguos tenían 250 preguntas, los nuevos 210)
  const o = {};
  for (const y of aniosDe(c)) { const tot = Object.values(c[y]).reduce((s, v) => s + v, 0) || 1; o[y] = {}; for (const k in c[y]) o[y][k] = c[y][k] / tot; }
  return o;
}

/* Predicción para el año «obj» con los años anteriores:
   media ponderada con semivida «h» años (lo reciente pesa más) + tendencia lineal ponderada amortiguada a la mitad.
   Se renormaliza para que la suma sea N_RFIR. El intervalo combina la dispersión histórica y el azar de un recuento (Poisson). */
function predice(c, obj = ANIO_OBJ, {h = 4, amort = 0.5, n = N_RFIR, asigs} = {}) {
  const q = cuotas(c), ys = aniosDe(c).filter(y => y < obj);
  if (!ys.length) return {filas: [], anios: []};
  const ids = asigs || [...new Set(ys.flatMap(y => Object.keys(q[y])))];
  const w = ys.map(y => Math.pow(0.5, (obj - 1 - y) / h)), W = w.reduce((s, v) => s + v, 0);
  const yb = ys.reduce((s, y, i) => s + w[i] * y, 0) / W;
  const filas = ids.map(id => {
    const s = ys.map(y => q[y][id] || 0);
    const m = s.reduce((a, v, i) => a + w[i] * v, 0) / W;
    let sxx = 0, sxy = 0; ys.forEach((y, i) => { sxx += w[i] * (y - yb) ** 2; sxy += w[i] * (y - yb) * (s[i] - m); });
    const b = sxx > 0 && ys.length >= 3 ? sxy / sxx : 0;
    const p = Math.max(0, m + amort * b * (obj - yb));
    const res = ys.map((y, i) => s[i] - (m + b * (y - yb)));
    const sd = Math.sqrt(res.reduce((a, r, i) => a + w[i] * r * r, 0) / W);
    const ult = ys.slice(-3).map(y => ({anio: y, n: (c[y] || {})[id] || 0}));
    const ultimaVez = [...ys].reverse().find(y => ((c[y] || {})[id] || 0) > 0) || null;
    return {id, cuota: p, tendencia: b, sd, ult, ultimaVez};
  });
  const tot = filas.reduce((a, f) => a + f.cuota, 0) || 1;
  for (const f of filas) {
    f.cuota /= tot; f.n = f.cuota * n;
    const sdN = Math.sqrt((f.sd * n) ** 2 + f.n);           // dispersión entre años + azar de Poisson
    f.lo = Math.max(0, Math.round(f.n - 1.28 * sdN)); f.hi = Math.round(f.n + 1.28 * sdN);   // ≈ intervalo del 80 %
    f.tend = f.tendencia * n > 0.6 ? 'sube' : f.tendencia * n < -0.6 ? 'baja' : 'estable';
  }
  filas.sort((a, b) => b.n - a.n);
  return {filas, anios: ys};
}

/* Validación a ciegas: para cada uno de los «k» últimos años se predice SOLO con los anteriores y se compara con lo que salió.
   Referencias: «igual que el año anterior» y «media simple de todos los años». Error = media de |predicho − real| en preguntas. */
function valida(c, {k = 3, n = N_RFIR} = {}) {
  const ys = aniosDe(c), q = cuotas(c), out = [];
  for (const Y of ys.slice(-k)) {
    const prev = ys.filter(y => y < Y); if (prev.length < 3) continue;
    const sub = {}; prev.forEach(y => sub[y] = c[y]);
    const ids = [...new Set([...prev.flatMap(y => Object.keys(c[y])), ...Object.keys(c[Y])])];
    const p = predice(sub, Y, {n, asigs: ids}), real = id => (q[Y][id] || 0) * n;
    const pm = Object.fromEntries(p.filas.map(f => [f.id, f.n]));
    const ant = prev.at(-1), media = id => prev.reduce((a, y) => a + (q[y][id] || 0), 0) / prev.length * n;
    const err = f => ids.reduce((a, id) => a + Math.abs(f(id) - real(id)), 0) / ids.length;
    const top = [...ids].sort((a, b) => (pm[b] || 0) - (pm[a] || 0)).slice(0, 10), topReal = [...ids].sort((a, b) => real(b) - real(a)).slice(0, 10);
    out.push({anio: Y, mae: err(id => pm[id] || 0), maeAnterior: err(id => (q[ant][id] || 0) * n), maeMedia: err(media), aciertoTop10: top.filter(x => topReal.includes(x)).length});
  }
  if (!out.length) return null;
  const av = key => out.reduce((a, o) => a + o[key], 0) / out.length;
  const r = {porAnio: out, mae: av('mae'), maeAnterior: av('maeAnterior'), maeMedia: av('maeMedia'), aciertoTop10: av('aciertoTop10')};
  r.nivel = r.mae <= 0.85 * Math.min(r.maeAnterior, r.maeMedia) ? 'alta' : r.mae <= Math.min(r.maeAnterior, r.maeMedia) * 1.02 ? 'media' : 'baja';
  return r;
}

/* reparto entero de n preguntas según las cuotas (restos mayores) */
function reparto(filas, n) {
  const base = filas.map(f => ({id: f.id, x: f.cuota * n})); base.forEach(b => { b.k = Math.floor(b.x); b.r = b.x - b.k; });
  let falta = n - base.reduce((a, b) => a + b.k, 0);
  [...base].sort((a, b) => b.r - a.r).forEach(b => { if (falta > 0) { b.k++; falta--; } });
  return Object.fromEntries(base.map(b => [b.id, b.k]));
}
const utilizable = q => q && q.correcta && !q.anulada && (!q.imagen || !!q.img) && Array.isArray(q.opciones) && q.opciones.length >= 4;   // con imagen, solo si la tenemos

/* Simulacro «probable 2027»: n preguntas oficiales, en la proporción que predice el modelo; reproducible con la semilla */
function simulacro(preguntas, filas, n, semilla, soloAsig) {
  const r = rng(semilla), pool = {};
  for (const q of preguntas) if (utilizable(q) && (!soloAsig || soloAsig.includes(q.asig))) (pool[q.asig] = pool[q.asig] || []).push(q);
  const fs = filas.filter(f => pool[f.id] && (!soloAsig || soloAsig.includes(f.id)));
  if (!fs.length) return [];
  const tot = fs.reduce((a, f) => a + f.cuota, 0) || 1, rep = reparto(fs.map(f => ({id: f.id, cuota: f.cuota / tot})), n);
  let sel = [];
  for (const f of fs) sel.push(...baraja(pool[f.id], r).slice(0, rep[f.id]));
  if (sel.length < n) { const ya = new Set(sel.map(q => q.id)); sel.push(...baraja(fs.flatMap(f => pool[f.id]).filter(q => !ya.has(q.id)), r).slice(0, n - sel.length)); }
  return baraja(sel, r).slice(0, n);
}

/* Puntuación del RFIR: acierto +3, fallo −1, en blanco 0. «neta» = aciertos − fallos/3 (la escala que usa la gente) */
function puntua(qs, resp) {
  let ac = 0, fa = 0, bl = 0; const porAsig = {};
  qs.forEach(q => {
    const r = resp[q.id], a = (porAsig[q.asig] = porAsig[q.asig] || {ac: 0, fa: 0, bl: 0});
    if (!r) { bl++; a.bl++; } else if (r === q.correcta) { ac++; a.ac++; } else { fa++; a.fa++; }
  });
  return {ac, fa, bl, puntos: 3 * ac - fa, neta: Math.round((ac - fa / 3) * 100) / 100, porAsig};
}

/* reto diario: misma fecha → mismas 10 preguntas para todo el mundo (por eso se puede comparar y compartir) */
function fechaMadrid(d = new Date()) { return new Intl.DateTimeFormat('en-CA', {timeZone: 'Europe/Madrid'}).format(d); }
const RETO_INICIO = '2026-11-15';
function numReto(fecha) { return Math.round((Date.parse(fecha + 'T12:00:00Z') - Date.parse(RETO_INICIO + 'T12:00:00Z')) / 864e5) + 1; }
function diasHastaRFIR(d = new Date()) { return Math.max(0, Math.ceil((Date.parse(FECHA_RFIR) - d.getTime()) / 864e5)); }
function textoCompartirReto(num, marcas, sc, dias, url) {
  const em = marcas.map(m => m === 'ok' ? '🟩' : m === 'ko' ? '🟥' : '⬜').join('');
  return `OráculoRFIR · Reto #${num}\n${em} ${sc.ac}/${marcas.length}\n${dias ? `⏳ ${dias} días para el RFIR 2027\n` : ''}${url}`;
}

/* ── generador multiagente: lo que el código puede comprobar sin fiarse de ninguna IA ── */
const palabras = s => new Set(String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').match(/[a-zñ0-9]{4,}/g) || []);
function jaccard(a, b) { const A = palabras(a), B = palabras(b); if (!A.size || !B.size) return 0; let i = 0; A.forEach(x => { if (B.has(x)) i++; }); return i / (A.size + B.size - i); }
/* formato: enunciado razonable, 4 opciones distintas y no vacías, clave entre 1 y 4 */
function revisaFormato(g) {
  const fallos = [];
  const ops = Array.isArray(g.opciones) ? g.opciones.map(o => String(o || '').trim()) : [];
  if (String(g.enunciado || '').trim().split(/\s+/).length < 12) fallos.push('enunciado demasiado corto');
  if (ops.length !== 4 || ops.some(o => !o)) fallos.push('no tiene 4 opciones');
  if (new Set(ops.map(o => o.toLowerCase())).size !== ops.length) fallos.push('opciones repetidas');
  if (![1, 2, 3, 4].includes(Number(g.correcta))) fallos.push('respuesta correcta fuera de 1-4');
  if (ops.some(o => /todas las (anteriores|opciones)|ninguna de las anteriores/i.test(o))) fallos.push('usa «todas/ninguna de las anteriores»');
  return fallos;
}
/* ¿se parece demasiado a una pregunta oficial? (no queremos copias disfrazadas: el banco oficial ya está para practicar) */
function parecidoBanco(g, banco, umbral = 0.55) {
  let mejor = {s: 0, id: null};
  for (const q of banco) { const s = jaccard(g.enunciado, q.enunciado); if (s > mejor.s) mejor = {s, id: q.id}; }
  return mejor.s >= umbral ? mejor : null;
}
/* permutación de opciones para cada resolutor y su inversa: el resolutor no ve la clave y no puede «adivinar por posición» */
function permuta(g, r) { const idx = baraja([0, 1, 2, 3], r); return {opciones: idx.map(i => g.opciones[i]), aOriginal: k => idx[k - 1] + 1}; }
/* veredicto: aceptada si los dos resolutores, a ciegas, eligen la clave del redactor; dudosa si discrepa uno; descartada si discrepan los dos */
function veredicto(clave, respuestas) {
  const ok = respuestas.filter(x => x === clave).length;
  return ok === respuestas.length ? 'aceptada' : ok === 0 ? 'descartada' : 'dudosa';
}
/* Contexto de años anteriores para el generador: qué temas (palabras clave de la asignatura) han salido, cuántas veces y cuándo.
   anioRef = último RFIR del banco. «olvidados» = temas con ≥3 preguntas ausentes en los últimos ≥4 exámenes (heurística, no predicción). */
const sinTildes = s => ' ' + String(s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9ñ]+/g, ' ') + ' ';
function temasRecurrentes(preguntas, asig, kws, anioRef, {top = 15, hueco = 4} = {}) {
  const qs = preguntas.filter(q => q.asig === asig && q.anio), cuenta = {};
  const vistos = new Set(), unicas = (kws || []).filter(k => { const c = sinTildes(k).trim(); if (vistos.has(c)) return false; vistos.add(c); return true; });   // «disección»/«diseccion» = un tema
  const rxs = unicas.map(k => [k, new RegExp('(?<![a-z0-9])' + sinTildes(k).trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))]);
  for (const q of qs) {
    const tx = sinTildes(q.enunciado + ' ' + (q.opciones || []).join(' '));
    for (const [k, rx] of rxs) if (rx.test(tx)) { const c = (cuenta[k] = cuenta[k] || {tema: k, n: 0, anios: new Set()}); c.n++; c.anios.add(q.anio); }
  }
  const lista = Object.values(cuenta).map(c => ({tema: c.tema, n: c.n, ultimo: Math.max(...c.anios), anios: c.anios.size})).sort((a, b) => b.n - a.n || b.ultimo - a.ultimo);
  return {total: qs.length, frecuentes: lista.slice(0, top), olvidados: lista.filter(c => c.n >= 3 && anioRef - c.ultimo >= hueco).slice(0, 8)};
}
/* ejemplos oficiales para el redactor: los más recientes primero (con respuesta), sin imagen ni anuladas */
function ejemplosRecientes(preguntas, asig, n, r) {
  const ok = preguntas.filter(q => q.asig === asig && utilizable(q) && !q.imagen).sort((a, b) => b.anio - a.anio);   // el redactor no ve imágenes
  const recientes = ok.filter(q => q.anio >= (ok[0] || {anio: 0}).anio - 4);
  return baraja(recientes.length >= n ? recientes : ok, r).slice(0, n);
}

/* ── historial personal, repaso espaciado (Leitner) y plan ──
   Cada pregunta respondida guarda {v: vistas, ok, ko, caja 0-5, prox: fecha AAAA-MM-DD del próximo repaso, ult}.
   Fallo → caja 0 y vuelve mañana. Acierto en un repaso → sube de caja: 1, 3, 7, 21 y 60 días. Caja 5 = dominada (sale del repaso). */
const INTERVALOS = [1, 3, 7, 21, 60];
const sumaDias = (f, d) => new Date(Date.parse(f + 'T12:00:00Z') + d * 864e5).toISOString().slice(0, 10);
function registra(h, acierto, hoy) {
  const e = {v: 0, ok: 0, ko: 0, caja: null, prox: null, ...(h || {})}; e.v++; e.ult = hoy;
  if (acierto) {
    e.ok++;
    if (e.caja !== null) { e.caja = Math.min(5, e.caja + 1); e.prox = e.caja >= 5 ? null : sumaDias(hoy, INTERVALOS[e.caja - 1]); }
  } else { e.ko++; e.caja = 0; e.prox = sumaDias(hoy, INTERVALOS[0]); }
  return e;
}
const pendientes = (hist, hoy) => Object.entries(hist || {}).filter(([, e]) => e.prox && e.prox <= hoy).sort((a, b) => a[1].prox.localeCompare(b[1].prox) || a[1].caja - b[1].caja).map(([id]) => id);
const enRepaso = hist => Object.values(hist || {}).filter(e => e.prox).length;
/* plan: por asignatura, preguntas esperadas en 2027 × tu tasa de fallo = preguntas que hoy probablemente fallarías.
   Con menos de «minimo» respuestas no hay dato fiable: se marca «sin datos» y se pide practicar. */
function plan(hist, preguntas, filas, minimo = 8) {
  const porId = Object.fromEntries(preguntas.map(q => [q.id, q])), ag = {};
  for (const [id, e] of Object.entries(hist || {})) { const q = porId[id]; if (!q) continue; const a = (ag[q.asig] = ag[q.asig] || {v: 0, ok: 0, ko: 0}); a.ok += e.ok; a.ko += e.ko; a.v += e.ok + e.ko; }
  return filas.map(f => {
    const a = ag[f.id] || {v: 0, ok: 0, ko: 0}, tasa = a.v ? a.ko / a.v : null, datos = a.v >= minimo;
    return {id: f.id, esperadas: f.n, respondidas: a.v, aciertos: a.ok, fallos: a.ko, tasa, datos, enJuego: datos ? f.n * tasa : null};
  }).sort((x, y) => (y.datos - x.datos) || ((y.enJuego ?? 0) - (x.enJuego ?? 0)) || (y.esperadas - x.esperadas));
}
/* búsqueda en el banco: todas las palabras (sin tildes) deben aparecer en enunciado u opciones */
function busca(preguntas, texto, {asig, anio, solo} = {}) {
  const ws = sinTildes(texto).trim().split(/\s+/).filter(w => w.length > 1);
  return preguntas.filter(q => (!asig || q.asig === asig) && (!anio || q.anio === +anio) && (!solo || utilizable(q)) &&
    (!ws.length || (t => ws.every(w => t.includes(' ' + w) || t.includes(w)))(sinTildes(q.enunciado + ' ' + (q.opciones || []).join(' ')))));
}
/* enlace para avisar de un error en una pregunta: incidencia de GitHub ya rellenada (nada se envía sin que la persona lo confirme en GitHub) */
function urlAviso(repo, q, comentario = '') {
  const t = `Error en RFIR ${q.anio} · pregunta ${q.n} (${q.id})`;
  const b = `**Pregunta:** ${q.id} (RFIR ${q.anio}, nº ${q.n}, asignatura asignada: ${q.asig})\n**Respuesta que muestra la app:** ${q.correcta ?? '—'}\n\n> ${String(q.enunciado).slice(0, 600)}\n\n**Qué está mal:** ${comentario || '(describe el error: texto, opciones, respuesta, imagen o asignatura)'}\n`;
  return `https://github.com/${repo}/issues/new?labels=error-pregunta&title=${encodeURIComponent(t)}&body=${encodeURIComponent(b)}`;
}

/* ── panel de revisión (inspirado en el panel de DiagnostIA): estilo por código + veredicto combinado ── */
const ABSOLUTOS = /\b(siempre|nunca|jam[aá]s|todos|todas|ninguno|ninguna|exclusivamente|únicamente|unicamente|en ningún caso)\b/i;
/* fallos de redacción detectables sin IA (normas habituales de redacción de preguntas de examen médico) */
function revisaEstilo(g) {
  const avisos = [], ops = (g.opciones || []).map(o => String(o)), k = Number(g.correcta) - 1;
  if (ops.length === 4 && k >= 0 && k < 4) {
    const L = ops.map(o => o.length), otras = L.filter((_, i) => i !== k), media = otras.reduce((a, b) => a + b, 0) / otras.length;
    if (L[k] > 1.5 * media && L[k] === Math.max(...L) && L[k] - Math.max(...otras) > 15) avisos.push('la correcta es mucho más larga que las demás');
    const absD = ops.filter((o, i) => i !== k && ABSOLUTOS.test(o)).length;
    if (absD >= 2 && !ABSOLUTOS.test(ops[k])) avisos.push('solo los distractores usan absolutos («siempre», «nunca»…)');
  }
  return avisos;
}
/* veredicto del panel:
   · descartada: ningún resolutor elige la clave, o el Contradictor o la Lista de control la declaran «mala»;
   · dudosa: un resolutor discrepa, o el Contradictor la ve «dudosa», o la Lista pide «corregir», o hay avisos de estilo;
   · aceptada: todo lo demás (los resolutores a ciegas coinciden con la clave y nadie encuentra un problema). */
function veredictoPanel(clave, respuestas, {contra, lista, estilo = []} = {}) {
  const ok = respuestas.filter(x => x === clave).length;
  if (ok === 0) return 'descartada';
  if (contra && contra.veredicto === 'mala') return 'descartada';   // la Lista de control no descarta: con preguntas oficiales marcaba «mala» el 14 % de las buenas
  if (ok < respuestas.length || (contra && contra.veredicto === 'dudosa') || (lista && lista.veredicto !== 'ok') || estilo.length) return 'dudosa';
  return 'aceptada';
}
/* métricas de la medición: con la clave buena, % aceptado (TA); con una clave errónea, % que se cuela (FA) */
function metricas(filas) {
  const pct = (xs, f) => xs.length ? xs.filter(f).length / xs.length : null;
  const conf = {
    A: (r, v) => r.res.every(x => x === v.clave),
    B: (r, v) => r.res.every(x => x === v.clave) && v.contra === 'ok',
    C: (r, v) => veredictoPanel(v.clave, r.res, {contra: {veredicto: v.contra}, lista: {veredicto: v.lista}, estilo: v.estilo}) === 'aceptada',
    D: (r, v) => veredictoPanel(v.clave, r.res, {contra: {veredicto: v.contra}, lista: {veredicto: v.lista}, estilo: v.estilo}) !== 'descartada'   // aceptada o dudosa (se conserva para revisar)
  };
  const out = {n: filas.length};
  for (const [k, f] of Object.entries(conf)) out[k] = {ta: pct(filas, r => f(r, r.buena)), fa: pct(filas, r => f(r, r.mala))};
  out.acierto1 = pct(filas, r => r.res[0] === r.buena.clave); out.acierto2 = pct(filas, r => r.res[1] === r.buena.clave);
  const acuerdo = filas.filter(r => r.res[0] && r.res[0] === r.res[1]);
  out.acuerdo = filas.length ? acuerdo.length / filas.length : null; out.precisionAcuerdo = pct(acuerdo, r => r.res[0] === r.buena.clave);
  return out;
}

/* GIFT (formato de preguntas de Moodle) */
const giftEsc = s => String(s).replace(/([~=#{}:\\])/g, '\\$1');
function aGIFT(qs) { return qs.map((q, i) => `::OraculoRFIR ${i + 1}::${giftEsc(q.enunciado)} {\n${q.opciones.map((o, k) => `${k + 1 === q.correcta ? '=' : '~'}${giftEsc(o)}`).join('\n')}\n}`).join('\n\n') + '\n'; }

if (typeof module !== 'undefined') module.exports = {N_RFIR, FECHA_RFIR, rng, baraja, conteos, cuotas, predice, valida, reparto, simulacro, puntua, utilizable, fechaMadrid, numReto, diasHastaRFIR, textoCompartirReto, jaccard, revisaFormato, parecidoBanco, permuta, veredicto, aGIFT, temasRecurrentes, ejemplosRecientes, registra, pendientes, enRepaso, plan, busca, urlAviso, sumaDias, revisaEstilo, veredictoPanel, metricas};
