"""Prueba de OráculoRFIR en un Chromium real con IA simulada:  python3 tests/smoke_test.py
Comprueba: modo demostración, predicción, simulacro reproducible por enlace, reto diario y racha, generador con panel de cinco agentes, medición con preguntas oficiales
(formato, copia del banco, discrepancias), idiomas, CSP, descargas, modo con datos «reales» sintéticos y desborde en móvil."""
import asyncio, sys, pathlib, re, json, random
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from forja_test import Harness
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = pathlib.Path('/tmp/om_test'); OUT.mkdir(exist_ok=True)

LARGO = 'Paciente de cuarenta y cinco años que consulta por un cuadro clínico de varias semanas de evolución con datos característicos; '
GEN = {'preguntas': [
    {'tema': 'buena', 'enunciado': LARGO + '¿cuál es la respuesta? (BUENA)', 'opciones': ['Distractor uno', 'CORRECTA buena', 'Distractor dos', 'Distractor tres'], 'correcta': 2, 'explicacion': 'Porque sí.', 'referencia': 'Guía X'},
    {'tema': 'formato', 'enunciado': LARGO + '¿cuál? (FORMATO)', 'opciones': ['a', 'a', 'Ninguna de las anteriores', 'b'], 'correcta': 7, 'explicacion': '', 'referencia': ''},
    {'tema': 'copia', 'enunciado': 'Dos resistencias de 6 Ω se conectan en paralelo. ¿Cuál es la resistencia equivalente?', 'opciones': ['50 %.', '25 %.', 'CORRECTA 12,5 %.', '6,25 %.'], 'correcta': 1, 'explicacion': '', 'referencia': ''},
    {'tema': 'clave mal', 'enunciado': LARGO + '¿cuál? (CLAVE MAL)', 'opciones': ['Opción que el redactor da por buena', 'Otra', 'CORRECTA de verdad', 'Otra más'], 'correcta': 1, 'explicacion': '', 'referencia': ''},
    {'tema': 'dudosa', 'enunciado': LARGO + '¿cuál? (DUDOSA)', 'opciones': ['CORRECTA según el redactor', 'ALTERNATIVA', 'Otra', 'Otra más'], 'correcta': 1, 'explicacion': '', 'referencia': ''}]}

EXAMEN = {'activo': False, 'k': 0, 'mal': False}

async def reply(prov, system, user, info):
    if 'profesor de una academia' in user: return ('j', {'clave': 'Idea clave de prueba', 'explicacion': 'Porque la oficial es la buena.', 'opciones': ['a', 'b', 'c', 'd'], 'aviso': '', 'repaso': 'Tema X'})
    if 'redactor experto' in user and 'YA REDACTADAS' not in user and '(BUENA)' not in str(GEN) or False: pass
    m = re.search(r'Redacta (\d+) preguntas NUEVAS de «([^»]+)»', user)
    if m and info.get('examen'): pass
    if m and EXAMEN['activo']:
        n = int(m.group(1)); EXAMEN['k'] += 1
        return ('j', {'preguntas': [{'tema': f'tema {EXAMEN["k"]}-{i}', 'enunciado': f'Caso clínico inventado número {EXAMEN["k"]} {i} de {m.group(2)} con datos suficientes para resolver la pregunta planteada aquí {"xyz" * (EXAMEN["k"] + i)} palabra{EXAMEN["k"]}{i}', 'opciones': [f'Distractor A{EXAMEN["k"]}{i}', f'CORRECTA {EXAMEN["k"]}{i}', f'Distractor B{EXAMEN["k"]}{i}', f'Distractor C{EXAMEN["k"]}{i}'], 'correcta': 2, 'explicacion': 'Explicación del redactor.', 'referencia': 'Guía X'} for i in range(n)]})
    if 'redactor experto' in user: return ('j', GEN)
    if 'Resuelve estas preguntas' in user:
        comision = 'comisión calificadora' in user; out = []
        for bloque in user.split('id: ')[1:]:
            ls = bloque.strip().split('\n'); qid = ls[0].strip(); ops = [l for l in ls if re.match(r'^[1-4]\. ', l)]
            marca = 'ALTERNATIVA' if (comision and 'DUDOSA' in bloque) else 'Distractor A' if EXAMEN['mal'] else 'CORRECTA'
            k = next((i + 1 for i, l in enumerate(ops) if marca in l), 0)
            out.append({'id': qid, 'opcion': k, 'seguridad': 90, 'motivo': 'ok'})
        return ('j', {'respuestas': out})
    if 'Eres el Contradictor' in user or 'Eres la Lista de control' in user:
        contra = 'Contradictor' in user; out = []
        for bloque in user.split('id: ')[1:]:
            ls = bloque.strip().split('\n'); qid = ls[0].strip(); ops = [l for l in ls if re.match(r'^[1-4]\. ', l)]
            m = re.search(r'Clave(?: del redactor)?: (\d)', bloque); k = int(m.group(1)) if m else 0
            buena = 0 < k <= len(ops) and 'CORRECTA' in ops[k - 1]
            out.append({'id': qid, 'veredicto': ('ok' if buena else 'mala') if contra else 'ok', 'problema': '' if buena else 'La clave no es la correcta', 'alternativa': 0, 'fallos': [], 'nota': ''})
        return ('j', {'revisiones': out})
    return ('t', '{}')

def datos_sinteticos():
    """rfir.json falso con 6 años × 210 preguntas, para probar el camino de «datos reales» sin red"""
    random.seed(1); asig = ['matematicas', 'mecanica', 'electromagnetismo', 'optica', 'termodinamica', 'cuantica', 'nuclear', 'otras']
    pre = []
    for y in range(2021, 2027):
        for n in range(1, 211):
            a = asig[(n * 7 + y) % len(asig)]
            pre.append({'id': f'{y}-{n:03d}', 'anio': y, 'n': n, 'enunciado': f'Enunciado oficial {y} {n} de {a}', 'opciones': ['o1', 'o2', 'o3', 'o4'], 'correcta': 1 + n % 4, 'anulada': n == 5, 'imagen': n == 6, 'asig': a, 'conf': 0.8})
    return {'generado': '2026-11-16T00:00:00+00:00', 'asignaturas': [{'id': a, 'nombre': a} for a in asig], 'examenes': [], 'preguntas': pre}

async def main():
    ok = True
    def check(nombre, cond, extra=''):
        nonlocal ok; ok &= bool(cond); print(('✓' if cond else '✕'), nombre, extra)
    async with Harness(ROOT / 'index.html', reply) as h:
        p = h.page
        check('CSP bloquea otros orígenes', await h.csp_bloquea())
        check('sin errores al cargar', not h.errors, str(h.errors))
        check('portada: cuenta atrás y aviso de demostración', re.search(r'\d+', await p.inner_text('#cuenta')) and 'demostración' in await p.inner_text('#estadoDatos'))
        await h.shot(str(OUT / '0_inicio.png'))
        # predicción
        await p.click('#btnStart'); await p.wait_for_timeout(300)
        filas = await p.locator('#tablaPred tbody tr').count()
        check('predicción: una fila por asignatura', filas >= 15, str(filas))
        check('predicción suma 200', abs(await p.evaluate('PRED.filas.reduce((a,f)=>a+f.n,0)') - 200) < 0.01)
        check('tarjeta de confianza con validación a ciegas', 'a ciegas' in await p.inner_text('#confianza'))
        await h.shot(str(OUT / '1_prediccion.png'))
        fn = await h.descarga('#btnCsvPred', str(OUT / 'pred.csv')); check('CSV de la predicción', fn.endswith('.csv') and 'Matemáticas y Métodos numéricos' in (OUT / 'pred.csv').read_text(encoding='utf-8-sig'))
        # practicar una asignatura desde la tabla
        await p.click('#tablaPred [data-practica="matematicas"]'); await p.wait_for_timeout(300)
        check('«Practicar» lleva al simulacro con la asignatura elegida', await p.evaluate('step') == 2 and await p.input_value('#simAsig') == 'matematicas')
        # simulacro probable de 10
        await p.select_option('#simAsig', 'probable'); await p.select_option('#simN', '10'); await p.click('#btnSim'); await p.wait_for_timeout(300)
        check('simulacro creado (demo: hasta 12 preguntas)', await p.evaluate('S.sim.qs.length') == 10)
        check('reloj al ritmo del RFIR', re.search(r'\d+:\d\d', await p.inner_text('#reloj') or ''))
        for i in range(10):
            await p.click('#simExamen .om-op[data-op="1"]'); await p.wait_for_timeout(60)
        await p.click('#simExamen [data-fin]'); await p.wait_for_timeout(300)
        check('corrección con aciertos, fallos y neta', await p.evaluate('S.sim.fin') and 'neta' in await p.inner_text('#simExamen'))
        sc = await p.evaluate('puntua(S.sim.qs.map(preg), S.sim.resp)')
        check('puntuación coherente (+3/−1)', sc['puntos'] == 3 * sc['ac'] - sc['fa'] and sc['ac'] + sc['fa'] + sc['bl'] == 10, str(sc))
        await h.shot(str(OUT / '2_simulacro.png'))
        # reto diario
        await p.evaluate('go(5)'); await p.wait_for_timeout(300)
        n = await p.evaluate('S.reto.qs.length'); check('reto con 10 preguntas (o las que haya)', n == 10, str(n))
        for i in range(n):
            await p.click('#retoQ .om-op[data-op="2"]'); await p.wait_for_timeout(60)
            if i < n - 1: await p.click('#retoQ [data-mov="1"]'); await p.wait_for_timeout(40)
        txt = await p.inner_text('#retoBox pre')
        check('reto terminado con texto para compartir y racha', 'Reto #' in txt and re.search('[🟩🟥]', txt) and await p.evaluate('S.racha.n') == 1, txt)
        await h.shot(str(OUT / '4_reto.png'))
        # generador con agentes
        await p.evaluate("go(3)"); await p.wait_for_timeout(200)
        await p.click('#btnGen'); await p.wait_for_selector('#mIA.on')
        await p.fill('#apiKey', 'sk-test-clave-larga-de-prueba-123'); await p.keyboard.press('Escape')
        await p.select_option('#genN', '5'); await p.click('#btnGen'); await p.wait_for_selector('#mEnvio.on')
        check('aviso previo con muestra de lo que sale', 'redactor experto' in await p.inner_text('#envioTxt'))
        await p.check('#envioOk'); await p.click('#envioSi')
        await h.esp('S.genStats !== null')
        st = await p.evaluate('S.genStats')
        check('agentes: 1 aceptada, 1 dudosa, 3 descartadas', (st['aceptadas'], st['dudosas'], st['descartadas']) == (1, 1, 3), json.dumps(st, ensure_ascii=False))
        mot = ' '.join(st['motivos'])
        check('el código descarta formato erróneo y copia del banco', 'opciones repetidas' in mot and 'se parece demasiado' in mot, mot)
        check('se descarta la clave equivocada aunque la diga el redactor', 'ninguno de los dos resolutores' in mot)
        check('cinco llamadas a la IA (redactor + 2 resolutores + Contradictor + Lista)', len(h.seen) == 5, str(len(h.seen)))
        pan = await p.evaluate("(g => [g.contra && g.contra.veredicto, g.lista && g.lista.veredicto])(S.gen.find(g=>g.estado==='aceptada'))")
        check('la aceptada lleva la revisión del Contradictor y de la Lista', pan == ['ok', 'ok'], str(pan))
        res = await p.evaluate("S.gen.find(g=>g.estado==='aceptada').resolutores.map(r=>r.opcion)")
        check('las opciones barajadas se devuelven a su número original', res == [2, 2], str(res))
        await h.shot(str(OUT / '3_generador.png'))
        fn = await h.descarga('#btnGenWord', str(OUT / 'gen.docx')); check('Word de las preguntas aceptadas', fn.endswith('.docx') and (OUT / 'gen.docx').read_bytes()[:2] == b'PK')
        fn = await h.descarga('#btnGenGift', str(OUT / 'gen.gift.txt')); check('GIFT para Moodle', '=CORRECTA buena' in (OUT / 'gen.gift.txt').read_text())
        # persistencia
        await p.reload(); await p.wait_for_timeout(700)
        check('al recargar se conservan reto, racha y preguntas', await p.evaluate('S.racha.n') == 1 and await p.evaluate('S.gen.length') == 2)
        # idiomas
        check('no faltan traducciones', await h.faltan_traducciones() == [], str(await h.faltan_traducciones()))
        await h.idioma('en'); await p.evaluate('go(1)'); await p.wait_for_timeout(300)
        th = await p.inner_text('#tablaPred thead'); check('en inglés: tabla y asignaturas traducidas', 'subject' in th.lower() and 'Mathematics and Numerical methods' in await p.inner_text('#tablaPred'))
        await h.idioma('pt'); await p.evaluate('go(5)'); await p.wait_for_timeout(300); check('en portugués: reto traducido', 'Desafio' in await p.inner_text('section[data-step="5"]'))
        await h.idioma('es')
        check('sin errores de página', not h.errors, str(h.errors))
        check('móvil sin desborde (portada)', not await h.desborde_movil())
        check('móvil sin desborde (predicción)', not await h.desborde_movil('go(1)'))
        check('móvil sin desborde (simulacro en marcha)', not await h.desborde_movil("creaSim('x',10,'probable','rfir');go(2)"))
    # ── con datos «reales» (sintéticos) servidos como data/rfir.json ──
    js = json.dumps(datos_sinteticos())
    fake = "const _f=window.fetch;window.fetch=(u,o)=>String(u).includes('data/rfir.json')?Promise.resolve(new Response(" + json.dumps(js) + ",{status:200,headers:{'content-type':'application/json'}})):_f(u,o);"
    async with Harness(ROOT / 'index.html', reply, init_scripts=[fake]) as h:
        p = h.page; await p.wait_for_timeout(500)
        check('con rfir.json: modo real', await p.evaluate('DATA.real') and 'Banco oficial' in await p.inner_text('#estadoDatos'))
        check('«Sin clasificar» no entra en la predicción', not await p.evaluate("PRED.filas.some(f=>f.id==='otras')"))
        v = await p.evaluate('VAL'); check('validación a ciegas en 2024-2026', v and [o['anio'] for o in v['porAnio']] == [2024, 2025, 2026], str(v and v['porAnio']))
        await p.evaluate("creaSim('reto-amigo', 50, 'probable', 'rfir')"); a = await p.evaluate('S.sim.qs')
        await p.evaluate("creaSim('reto-amigo', 50, 'probable', 'rfir')"); b = await p.evaluate('S.sim.qs')
        check('mismo enlace de reto → mismas 50 preguntas', a == b and len(a) == 50)
        check('sin anuladas ni con imagen en el simulacro', await p.evaluate("S.sim.qs.map(preg).every(q=>!q.anulada&&!q.imagen)"))
        url = await p.evaluate('enlaceSim(S.sim)'); check('enlace para retar', '?sim=reto-amigo&n=50' in url, url)
        await p.goto((ROOT / 'index.html').as_uri() + '?sim=reto-amigo&n=50&a=probable'); await p.wait_for_timeout(700)
        check('abrir el enlace reproduce el mismo examen', await p.evaluate('S.sim.qs') == a and await p.evaluate('step') == 2)
        await p.goto((ROOT / 'index.html').as_uri() + '?reto'); await p.wait_for_timeout(600)
        check('?reto abre el reto diario', await p.evaluate('step') == 5)
        # repaso espaciado y plan
        await p.goto((ROOT / 'index.html').as_uri()); await p.wait_for_timeout(700)
        await p.evaluate("S.prac=null;S.hist={};creaSim('plan',30,'probable','libre');go(2)"); await p.wait_for_timeout(300)
        for i in range(30):
            await p.click('#simExamen .om-op[data-op="4"]'); await p.wait_for_timeout(25)
        await p.click('#simExamen [data-fin]'); await p.wait_for_timeout(200)
        if await p.locator('#simExamen [data-fin]').count(): await p.click('#simExamen [data-fin]'); await p.wait_for_timeout(200)
        nh = await p.evaluate('Object.keys(S.hist).length'); nko = await p.evaluate('Object.values(S.hist).filter(e=>e.caja===0).length')
        check('al corregir, cada respuesta entra en el historial y los fallos en el repaso', nh == 30 and nko == await p.evaluate("S.sim.qs.filter(id=>S.sim.resp[id]!==preg(id).correcta).length"), f'{nh} {nko}')
        await p.evaluate("Object.values(S.hist).forEach(e=>{if(e.prox)e.prox='2020-01-01'});go(6)"); await p.wait_for_timeout(300)
        check('«Mi estudio»: repaso pendiente y plan con preguntas en juego', 'Para hoy: ' + str(nko) in await p.inner_text('#repasoBox') and 'Preguntas en juego' in await p.inner_text('#planBox'))
        await p.click('#btnRepaso'); await p.wait_for_timeout(200)
        q0 = await p.evaluate('S.prac.qs[0]'); ok0 = await p.evaluate(f"preg('{q0}').correcta")
        await p.click(f'#pracQ .om-op[data-op="{ok0}"]'); await p.wait_for_timeout(200)
        check('acertar en el repaso sube de caja', await p.evaluate(f"S.hist['{q0}'].caja") == 1)
        # «¿Por qué?» con IA simulada, anclado a la respuesta oficial y guardado
        await p.evaluate("localStorage.setItem('ia_openai_key','sk-test-clave-larga-de-prueba-123');ENVIO_OK=true"); h.seen.clear()
        await p.click('#pracQ [data-porque]'); await h.esp(f"!!S.explic['{q0}']")
        check('«¿Por qué?»: explicación mostrada, con la respuesta oficial en el prompt', 'Idea clave de prueba' in await p.inner_text('#pracQ') and f'Respuesta oficial: {ok0}' in h.seen[-1]['user'])
        await p.click('#pracQ [data-porque]'); await p.wait_for_timeout(150); await p.click('#pracQ [data-porque]'); await p.wait_for_timeout(150)
        check('la explicación se guarda: no se vuelve a pagar', len(h.seen) == 1, str(len(h.seen)))
        href = await p.get_attribute('#pracQ a[href*="issues/new"]', 'href'); check('«Avisar de un error» abre una incidencia rellenada', href and q0 in href)
        # banco: examen de un año y buscador
        await p.evaluate('go(7)'); await p.wait_for_timeout(300)
        await p.select_option('#bancoAnio', '2024'); await p.click('#btnAnio'); await p.wait_for_timeout(300)
        check('RFIR de un año completo, en orden', await p.evaluate('step') == 2 and await p.evaluate('S.sim.anio') == 2024 and await p.evaluate('S.sim.qs.length') == await p.evaluate("DATA.preguntas.filter(q=>q.anio===2024&&utilizable(q)).length"))
        await p.evaluate('go(7)'); await p.fill('#busTexto', 'oficial 2023'); await p.wait_for_timeout(500)
        check('buscador', '210' in await p.inner_text('#busRes') or 'preguntas oficiales' in await p.inner_text('#busRes'), await p.inner_text('#busRes'))
        await p.goto((ROOT / 'index.html').as_uri() + '?anio=2022'); await p.wait_for_timeout(700)
        check('?anio=2022 abre ese RFIR', await p.evaluate('S.sim.anio') == 2022 and await p.evaluate('step') == 2)
        # paso 4: examen RFIR 2027 generado (25 preguntas, IA simulada) y simulacro
        EXAMEN['activo'] = True; h.seen.clear()
        await p.evaluate("S.examenIA=null;ENVIO_OK=true;go(4)"); await p.wait_for_timeout(300)
        await p.select_option('#exN', '25'); await p.wait_for_timeout(100)
        check('paso 4: estimación de coste antes de empezar', 'llamadas' in await p.inner_text('#exEstima'))
        await p.click('#btnExGen'); await h.esp("S.examenIA && S.examenIA.estado==='listo'", n=240)
        X = await p.evaluate("({n:S.examenIA.preguntas.length, ia:S.examenIA.preguntas.filter(q=>q.ia).length, plan:Object.values(S.examenIA.plan).reduce((a,b)=>a+b,0), porAsig: Object.entries(S.examenIA.plan).every(([a,k])=>S.examenIA.preguntas.filter(q=>q.asig===a).length===k)})")
        check('examen de 25: todas generadas y verificadas, en la proporción predicha', X['n'] == 25 and X['ia'] == 25 and X['plan'] == 25 and X['porAsig'], str(X))
        check('cada tanda = panel de 5 llamadas', len(h.seen) % 5 == 0 and len(h.seen) >= 5, str(len(h.seen)))
        await p.click('#btnExSim'); await p.wait_for_timeout(400)
        check('el examen generado se hace como simulacro', await p.evaluate('step') == 2 and await p.evaluate('S.sim.ia') and await p.evaluate('S.sim.qs.length') == 25)
        for i in range(25):
            await p.click('#simExamen .om-op[data-op="2"]'); await p.wait_for_timeout(20)
        await p.click('#simExamen [data-fin]'); await p.wait_for_timeout(300)
        check('corrección del examen generado (todas acertadas)', await p.evaluate('puntua(S.sim.qs.map(preg), S.sim.resp).ac') == 25)
        check('las preguntas generadas no entran en el historial oficial', not await p.evaluate("S.sim.qs.some(id=>S.hist[id])"))
        await p.click('#simRev [data-porque]'); await p.wait_for_timeout(200)
        check('«Ver la explicación» muestra la del redactor sin nueva llamada', 'Explicación del redactor' in await p.inner_text('#simRev'))
        # medición con preguntas oficiales (respuesta conocida): clave buena y clave errónea
        EXAMEN['activo'] = False; h.seen.clear()
        C = await p.evaluate("""(async () => { const viejas = DATA.preguntas;
          DATA.preguntas = Array.from({length: 30}, (_, i) => ({id: 'x' + i, anio: 2020, n: i + 1, asig: 'cardio', enunciado: 'Enunciado oficial de prueba número ' + i, opciones: ['Distractor uno ' + i, 'CORRECTA ' + i, 'Distractor dos ' + i, 'Distractor tres ' + i], correcta: 2}));
          const r = await calibra(20); DATA.preguntas = viejas; delete r.filas; return r; })()""")
        check('medición: 20 preguntas, acepta las buenas y para las claves erróneas', C['n'] == 20 and C['C']['ta'] == 1 and C['C']['fa'] == 0 and C['A']['fa'] == 0, json.dumps({k: C[k] for k in ('n', 'A', 'B', 'C')}))
        check('medición: 2 tandas × (2 resolutores + 2 × panel) = 12 llamadas', len(h.seen) == 12, str(len(h.seen)))
        await p.evaluate("CALIB = " + json.dumps(C) + "; go(8)"); await p.wait_for_timeout(200)
        check('la medición se ve en «Cómo se valida»', 'Panel completo' in await p.inner_text('#valCalib'))
        # Mis generadas: todo lo generado queda en IndexedDB; un examen nuevo no borra el anterior
        check('el examen generado está en el archivo', await p.evaluate('S.archivo.length') == 1 and await p.evaluate('S.archivo[0] === S.examenIA'))
        # dos preguntas sueltas con el id antiguo (g1, g2, repetibles entre tandas): al recargar se les da uno único
        await p.evaluate("S.gen = [1, 2].map(k => ({...S.archivo[0].preguntas[k], id: 'g' + k, estado: k === 1 ? 'aceptada' : 'dudosa', ia: undefined})); guardaYa()")
        await p.reload(); await p.wait_for_timeout(800)
        ids = await p.evaluate('S.gen.map(g => g.id)')
        check('las preguntas sueltas tienen id único', len(ids) == 2 and len(set(ids)) == 2 and all(i.startswith('g-') for i in ids), str(ids))
        EXAMEN['activo'] = True
        await p.evaluate("ENVIO_OK=true;go(4)"); await p.select_option('#exN', '25'); await p.click('#btnExGen'); await h.esp("S.archivo.length===2 && S.examenIA.estado==='listo'", n=240)
        check('generar otro examen guarda el anterior', await p.evaluate('S.archivo.length') == 2)
        await p.click('#btnExBorra'); await p.wait_for_timeout(100)
        check('«Cerrar» no borra del archivo', await p.evaluate('S.examenIA') is None and await p.evaluate('S.archivo.length') == 2)
        await p.reload(); await p.wait_for_timeout(800)
        check('tras recargar siguen los 2 exámenes y las preguntas sueltas', await p.evaluate('S.archivo.length') == 2 and await p.evaluate('S.gen.length') == len(ids))
        await p.evaluate('go(9)'); await p.wait_for_timeout(200)
        check('«Mis generadas» lista los exámenes y las preguntas', await p.locator('#miasEx [data-exsim]').count() == 2 and await p.locator('#miasGen details').count() == len(ids))
        await h.shot(str(OUT / '9_mias.png'))
        await p.click('#miasEx [data-exsim] >> nth=1'); await p.wait_for_timeout(300)
        check('simulacro con un examen antiguo', await p.evaluate('step') == 2 and await p.evaluate('S.sim.qs.length') == 25 and await p.evaluate('S.sim.qs.every(id => !!preg(id))'))
        await p.evaluate('go(9)'); await p.wait_for_timeout(200)
        await p.click('#btnMiasSim'); await p.wait_for_timeout(300)
        check('simulacro con las preguntas sueltas aprobadas', await p.evaluate('S.sim.qs.length') >= 1 and await p.evaluate("S.sim.qs.every(id => preg(id) && preg(id).estado === 'aceptada')"))
        await p.evaluate('go(9)'); await p.wait_for_timeout(200)
        fn = await h.descarga('#btnMiasCopia', str(OUT / 'mias.json')); cop = json.loads((OUT / 'mias.json').read_text())
        check('copia JSON con exámenes y preguntas', len(cop['archivo']) == 2 and len(cop['gen']) == len(ids))
        await p.evaluate("S.archivo=[];S.gen=[];guarda()"); await p.set_input_files('#miasImporta', str(OUT / 'mias.json')); await p.wait_for_timeout(400)
        check('recuperar la copia', await p.evaluate('S.archivo.length') == 2 and await p.evaluate('S.gen.length') == len(ids))
        # guía de la clave
        await p.click('#btnIA'); await p.wait_for_selector('#mIA.on'); await p.click('#mIA [data-clave]'); await p.wait_for_timeout(200)
        check('guía para conseguir la clave', await p.evaluate('step') == 10 and 'platform.openai.com' in await p.inner_text('#clavePasos') and 'cinco llamadas' in await p.inner_text('#claveCoste'))
        await h.shot(str(OUT / '10_clave.png'))
        # si los agentes lo descartan todo: se completa con oficiales, marcadas
        EXAMEN['mal'] = True
        await p.evaluate("S.examenIA=null;ENVIO_OK=true;go(4)"); await p.select_option('#exN', '25'); await p.check('#exRelleno'); await p.click('#btnExGen'); await h.esp("S.examenIA && S.examenIA.estado==='listo'", n=240)
        Y = await p.evaluate("({n:S.examenIA.preguntas.length, ia:S.examenIA.preguntas.filter(q=>q.ia).length, desc:S.examenIA.motivos.length})")
        check('si los agentes discrepan, nada entra y se completa con oficiales', Y['n'] == 25 and Y['ia'] == 0 and Y['desc'] > 0, str(Y))
        EXAMEN['activo'] = False; EXAMEN['mal'] = False
        await p.evaluate('go(8)'); await p.wait_for_timeout(300)
        check('página de validación', 'a ciegas' in await p.inner_text('#valPred'))
        check('móvil sin desborde (mi estudio, banco, validación)', not await h.desborde_movil('go(6)') and not await h.desborde_movil('go(7)') and not await h.desborde_movil('go(8)'))
        check('sin errores de página (datos reales)', not h.errors, str(h.errors))
    print('\nTODO OK' if ok else '\nHAY FALLOS'); sys.exit(0 if ok else 1)

asyncio.run(main())
