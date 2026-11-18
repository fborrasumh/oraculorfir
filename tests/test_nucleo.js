// Pruebas de la lógica pura de OráculoRFIR:  node tests/test_nucleo.js
const M = require('../src/nucleo.js');
let ok = true; const check = (n, c, x = '') => { ok = ok && !!c; console.log((c ? '✓ ' : '✕ ') + n, x); };

// recuentos sintéticos: «A» estable en 30, «B» sube 2 por año, «C» baja, «D» aparece a saltos
const c = {}; for (let y = 2015; y <= 2026; y++) c[y] = {A: 30, B: 10 + 2 * (y - 2015), C: 40 - 2 * (y - 2015), D: y % 3 === 0 ? 6 : 0, E: 120};
const p = M.predice(c, 2027);
const f = id => p.filas.find(x => x.id === id);
check('la predicción suma 200', Math.abs(p.filas.reduce((a, x) => a + x.n, 0) - 200) < 1e-6);
check('detecta tendencia que sube y que baja', f('B').tend === 'sube' && f('C').tend === 'baja' && f('A').tend === 'estable', `${f('B').tend} ${f('C').tend} ${f('A').tend}`);
check('lo que sube se predice por encima de su media y lo que baja por debajo', f('B').n > (10 + 21) / 2 / 210 * 200 * 1.1 && f('C').n < 29 / 210 * 200);
check('intervalo contiene la estimación', p.filas.every(x => x.lo <= x.n && x.n <= x.hi + 0.5));
check('nunca negativo', p.filas.every(x => x.n >= 0 && x.lo >= 0));
check('solo usa años anteriores al objetivo', M.predice(c, 2020).anios.at(-1) === 2019);
const v = M.valida(c);
check('validación a ciegas en los 3 últimos años', v && v.porAnio.map(o => o.anio).join() === '2024,2025,2026', JSON.stringify(v && v.porAnio.map(o => o.anio)));
check('con tendencias claras el método mejora a «repetir el año anterior» o a la media', v.mae < Math.max(v.maeAnterior, v.maeMedia), `mae ${v.mae.toFixed(2)} ant ${v.maeAnterior.toFixed(2)} media ${v.maeMedia.toFixed(2)}`);
const ruido = {}; const r0 = M.rng('ruido'); for (let y = 2015; y <= 2026; y++) { ruido[y] = {}; 'ABCDEFGH'.split('').forEach(k => ruido[y][k] = Math.round(25 + (r0() - 0.5) * 30)); }
const vr = M.valida(ruido); check('con puro ruido no presume: fiabilidad media o baja', vr.nivel !== 'alta', vr.nivel);
// reparto y simulacro reproducible
const rep = M.reparto(p.filas, 25); check('reparto entero suma exactamente n', Object.values(rep).reduce((a, b) => a + b, 0) === 25);
const banco = []; ['A', 'B', 'C', 'E'].forEach(a => { for (let i = 0; i < 40; i++) banco.push({id: a + i, anio: 2020, asig: a, enunciado: 'x', opciones: ['1', '2', '3', '4'], correcta: 1 + i % 4, anulada: i === 3, imagen: i === 5}); });
const s1 = M.simulacro(banco, p.filas, 25, 'semilla'), s2 = M.simulacro(banco, p.filas, 25, 'semilla'), s3 = M.simulacro(banco, p.filas, 25, 'otra');
check('mismo enlace → mismo examen', s1.map(q => q.id).join() === s2.map(q => q.id).join() && s1.length === 25);
check('otra semilla → otro examen', s1.map(q => q.id).join() !== s3.map(q => q.id).join());
check('sin anuladas, sin imagen y sin repetidas', s1.every(q => !q.anulada && !q.imagen) && new Set(s1.map(q => q.id)).size === 25);
check('filtrar por asignatura', M.simulacro(banco, p.filas, 10, 'x', ['B']).every(q => q.asig === 'B'));
// puntuación RFIR
const qs = [{id: 1, asig: 'A', correcta: 1}, {id: 2, asig: 'A', correcta: 2}, {id: 3, asig: 'B', correcta: 3}];
const sc = M.puntua(qs, {1: 1, 2: 4});
check('puntuación +3/−1/0 y neta', sc.ac === 1 && sc.fa === 1 && sc.bl === 1 && sc.puntos === 2 && sc.neta === 0.67, JSON.stringify(sc));
// reto
check('número de reto', M.numReto('2026-11-15') === 1 && M.numReto('2027-01-23') === 70);
check('días hasta el RFIR', M.diasHastaRFIR(new Date('2027-01-22T14:00:00+01:00')) === 1 && M.diasHastaRFIR(new Date('2027-02-01')) === 0);
check('texto para compartir sin desvelar respuestas', M.textoCompartirReto(5, ['ok', 'ko', 'bl'], {ac: 1}, 10, 'u').includes('🟩🟥⬜ 1/3'));
// generador: comprobaciones de código
const g = {enunciado: 'Varón de 60 años con dolor torácico de dos horas y elevación del ST en cara inferior, ¿qué haría?', opciones: ['Angioplastia primaria', 'Alta', 'Observar', 'Ergometría'], correcta: 1};
check('formato correcto pasa', M.revisaFormato(g).length === 0);
check('formato: detecta opciones repetidas, clave fuera de rango y «ninguna de las anteriores»', M.revisaFormato({...g, opciones: ['a', 'a', 'Ninguna de las anteriores', 'b'], correcta: 7}).length === 3, JSON.stringify(M.revisaFormato({...g, opciones: ['a', 'a', 'Ninguna de las anteriores', 'b'], correcta: 7})));
check('detecta copia de una pregunta del banco', M.parecidoBanco(g, [{id: 'x', enunciado: g.enunciado + ' Señale la correcta.'}]) && !M.parecidoBanco(g, [{id: 'y', enunciado: 'Niña de 3 años con fiebre y exantema'}]));
const pm = M.permuta(g, M.rng(3)); check('permutación: cada opción barajada vuelve a su número original', pm.opciones.every((o, k) => g.opciones[pm.aOriginal(k + 1) - 1] === o));
check('veredicto 3/3, 2/3, 1/3', M.veredicto(2, [2, 2]) === 'aceptada' && M.veredicto(2, [2, 3]) === 'dudosa' && M.veredicto(2, [1, 0]) === 'descartada');
check('GIFT para Moodle', M.aGIFT([g]).includes('=Angioplastia primaria') && M.aGIFT([g]).includes('~Alta'));
// contexto de años anteriores
const bq = [
  {id: 'a', anio: 2025, asig: 'cardio', enunciado: 'Paciente con fibrilación auricular y...', opciones: ['a', 'b', 'c', 'd'], correcta: 1},
  {id: 'b', anio: 2024, asig: 'cardio', enunciado: 'Fibrilacion auricular paroxística', opciones: ['Anticoagular', 'b', 'c', 'd'], correcta: 1},
  {id: 'c', anio: 2012, asig: 'cardio', enunciado: 'Endocarditis por estreptococo', opciones: ['a', 'b', 'c', 'd'], correcta: 2},
  {id: 'd', anio: 2011, asig: 'cardio', enunciado: 'Endocarditis infecciosa', opciones: ['a', 'b', 'c', 'd'], correcta: 2},
  {id: 'e', anio: 2010, asig: 'cardio', enunciado: 'Sospecha de endocarditis', opciones: ['a', 'b', 'c', 'd'], correcta: 2},
  {id: 'f', anio: 2025, asig: 'neuro', enunciado: 'Fibrilación auricular e ictus', opciones: ['a', 'b', 'c', 'd'], correcta: 3}];
const tr = M.temasRecurrentes(bq, 'cardio', ['fibrilación auricular', 'fibrilacion auricular', 'endocarditis', 'pericarditis'], 2026);
check('temas: cuenta por asignatura, sin tildes, con último año', tr.total === 5 && tr.frecuentes[0].tema === 'endocarditis' && tr.frecuentes[0].n === 3 && tr.frecuentes[1].n === 2 && tr.frecuentes[1].ultimo === 2025, JSON.stringify(tr.frecuentes));
check('temas olvidados: ≥3 preguntas y ≥4 años sin salir', tr.olvidados.map(x => x.tema).join() === 'endocarditis');
check('el mismo tema con y sin tilde cuenta una vez', tr.frecuentes.filter(f => f.tema.startsWith('fibril')).length === 1);
const ej = M.ejemplosRecientes(bq, 'cardio', 2, M.rng(1)); check('ejemplos: recientes primero', ej.every(q => q.anio >= 2021), JSON.stringify(ej.map(q => q.anio)));
// repaso espaciado
let e = M.registra(null, false, '2026-11-16'); check('fallo → caja 0, vuelve mañana', e.caja === 0 && e.prox === '2026-11-17' && e.ko === 1);
e = M.registra(e, true, '2026-11-17'); check('acierto en repaso → caja 1, a los 1 día', e.caja === 1 && e.prox === '2026-11-18');
e = M.registra(e, true, '2026-11-18'); check('caja 2 → 3 días', e.caja === 2 && e.prox === '2026-11-21');
let d = M.registra(null, true, '2026-11-16'); check('acierto a la primera: no entra en repaso', d.caja === null && d.prox === null && d.ok === 1);
let z = {caja: 4, prox: '2026-12-01', v: 5, ok: 4, ko: 1}; z = M.registra(z, true, '2026-12-01'); check('caja 5 = dominada: sale del repaso', z.caja === 5 && z.prox === null);
check('pendientes de hoy, los más atrasados primero', M.pendientes({a: {prox: '2026-11-18', caja: 1}, b: {prox: '2026-11-15', caja: 0}, c: {prox: '2026-12-01', caja: 2}, d: {prox: null}}, '2026-11-18').join() === 'b,a');
// plan
const pq = [{id: 'x1', asig: 'A'}, {id: 'x2', asig: 'A'}, {id: 'y1', asig: 'B'}];
const H = {x1: {ok: 2, ko: 6}, x2: {ok: 0, ko: 2}, y1: {ok: 1, ko: 0}};
const pl = M.plan(H, pq, [{id: 'A', n: 10}, {id: 'B', n: 20}], 8);
check('plan: esperadas × tasa de fallo, y «sin datos» si hay pocas respuestas', pl[0].id === 'A' && Math.abs(pl[0].enJuego - 8) < 1e-9 && pl[1].datos === false, JSON.stringify(pl));
// búsqueda y aviso
check('búsqueda sin tildes y por varias palabras', M.busca([{id: 1, anio: 2020, asig: 'c', enunciado: 'Fibrilación auricular paroxística', opciones: []}, {id: 2, anio: 2020, asig: 'c', enunciado: 'Asma', opciones: []}], 'fibrilacion paroxistica').length === 1);
check('enlace para avisar de un error', M.urlAviso('a/b', {id: '2020-001', anio: 2020, n: 1, asig: 'c', enunciado: 'x', correcta: 2}).startsWith('https://github.com/a/b/issues/new?labels=error-pregunta&title=Error%20en%20RFIR%202020'));
// panel de revisión
check('estilo: correcta mucho más larga', M.revisaEstilo({opciones: ['Sí.', 'No.', 'Quizá.', 'La respuesta correcta y muy detallada con todos los matices necesarios'], correcta: 4}).length === 1);
check('estilo: absolutos solo en distractores', M.revisaEstilo({opciones: ['Siempre es así', 'Nunca ocurre', 'Depende del contexto clínico', 'Opción razonable'], correcta: 3}).some(a => a.includes('absolutos')));
check('estilo: pregunta equilibrada sin avisos', M.revisaEstilo({opciones: ['Angioplastia primaria', 'Fibrinólisis inmediata', 'Tratamiento conservador', 'Cirugía urgente'], correcta: 1}).length === 0);
check('panel: aceptada solo si todo cuadra', M.veredictoPanel(2, [2, 2], {contra: {veredicto: 'ok'}, lista: {veredicto: 'ok'}}) === 'aceptada');
check('panel: el Contradictor «dudosa» la deja en dudosa aunque coincidan', M.veredictoPanel(2, [2, 2], {contra: {veredicto: 'dudosa'}, lista: {veredicto: 'ok'}}) === 'dudosa');
check('panel: «mala» del Contradictor descarta; «mala» de la Lista deja dudosa', M.veredictoPanel(2, [2, 2], {contra: {veredicto: 'mala'}, lista: {veredicto: 'ok'}}) === 'descartada' && M.veredictoPanel(2, [2, 2], {contra: {veredicto: 'ok'}, lista: {veredicto: 'mala'}}) === 'dudosa' && M.veredictoPanel(2, [1, 3]) === 'descartada');
check('panel: aviso de estilo → dudosa', M.veredictoPanel(2, [2, 2], {contra: {veredicto: 'ok'}, lista: {veredicto: 'ok'}, estilo: ['x']}) === 'dudosa');
const fil = [{res: [1, 1], buena: {clave: 1, contra: 'ok', lista: 'ok', estilo: []}, mala: {clave: 3, contra: 'mala', lista: 'ok', estilo: []}},
             {res: [2, 2], buena: {clave: 2, contra: 'dudosa', lista: 'ok', estilo: []}, mala: {clave: 2, contra: 'ok', lista: 'ok', estilo: []}}];
const mt = M.metricas(fil);
check('métricas: aceptación con clave buena y errónea por configuración', mt.A.ta === 1 && mt.A.fa === 0.5 && mt.B.ta === 0.5 && mt.B.fa === 0.5 && mt.C.ta === 0.5 && mt.precisionAcuerdo === 1, JSON.stringify(mt));
console.log(ok ? '\nTODO OK' : '\nHAY FALLOS'); process.exit(ok ? 0 : 1);
