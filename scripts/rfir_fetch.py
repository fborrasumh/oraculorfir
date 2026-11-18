#!/usr/bin/env python3
"""OráculoRFIR · descarga los exámenes RFIR (titulación Física) oficiales del portal FSE del Ministerio de Sanidad.

Pensado para ejecutarse en GitHub Actions (allí hay red hacia sanidad.gob.es):
    python3 scripts/rfir_fetch.py --descubrir     # abre el portal con Chromium, recorre sus desplegables y anota los PDF
    python3 scripts/rfir_fetch.py --descargar     # baja a data/raw/<año>/ el cuaderno (versión 0) y la plantilla definitiva

El portal es una aplicación web (Angular) sin lista pública de enlaces, así que el descubrimiento es heurístico:
registra todas las respuestas JSON y todos los enlaces a PDF, y deduce año y tipo de documento por el texto y la URL.
Lo que deduzca se guarda en data/fuentes.json. Si algo sale mal, edita ese fichero a mano (las entradas con
"origen": "manual" nunca se sobrescriben) y vuelve a lanzar solo --descargar.
Las capturas y el HTML del portal se guardan en data/raw/_debug/ para poder ajustar el script."""
import argparse, json, re, sys, pathlib, time, unicodedata

R = pathlib.Path(__file__).resolve().parent.parent
RAW = R / 'data' / 'raw'; DEBUG = RAW / '_debug'; FUENTES = R / 'data' / 'fuentes.json'
PORTAL = 'https://fse.sanidad.gob.es/fseweb/#/principal/datosAnteriores/cuadernosExamen'
ANIO_MIN, ANIO_MAX = 2007, 2026
PDF_RX = re.compile(r'https?://[^\s"\'<>]+?\.pdf(?:\?[^\s"\'<>]*)?', re.I)


def carga_fuentes():
    return json.loads(FUENTES.read_text(encoding='utf-8')) if FUENTES.exists() else {}


def guarda_fuentes(f):
    FUENTES.write_text(json.dumps(dict(sorted(f.items())), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def tipo_de(txt):
    t = unicodedata.normalize('NFD', txt.lower()).encode('ascii', 'ignore').decode()
    if re.search(r'imag', t): return 'imagenes'
    if re.search(r'plantilla|respuesta|correct|soluc', t): return 'plantilla'
    if re.search(r'cuaderno|examen|preguntas|cuestionario', t): return 'cuaderno'
    return None


def anio_de(txt):
    """Año del EXAMEN. «2025-2026» o «2025/2026» → 2026 (la convocatoria 2025/26 se examina en enero de 2026)."""
    m = re.search(r'(20\d\d)\s*[-/_]\s*(20\d\d|\d\d)\b', txt)
    if m: a = m.group(2); return int(a) if len(a) == 4 else 2000 + int(a)
    ys = [int(y) for y in re.findall(r'(?<!\d)(20\d\d)(?!\d)', txt) if ANIO_MIN <= int(y) <= ANIO_MAX]
    return max(ys) if ys else None


def es_titulacion(txt):
    t = txt.lower()
    return bool(re.search(r'f[ií]sica|radiof|\brfir\b|_rfir|rfir_|/rfir', t))


def puntua_version(txt):
    """Preferimos la versión 0 del cuaderno: es la que numera la plantilla en primera columna."""
    t = txt.lower()
    if re.search(r'v(ersi[oó]n)?[\s_-]*0\b|_v0|v0_', t): return 2
    if re.search(r'v(ersi[oó]n)?[\s_-]*[1-4]\b', t): return 0
    return 1


def anota(cands, url, contexto):
    ctx = f'{url} {contexto}'
    tp, an = tipo_de(ctx), anio_de(ctx)
    if not tp or not an or not es_titulacion(ctx): return
    if tp == 'plantilla' and re.search(r'provisional', ctx, re.I): tp = 'plantilla_provisional'
    cands.append({'anio': an, 'tipo': tp, 'url': url, 'version': puntua_version(ctx), 'ctx': contexto[:200]})


def descubrir():
    from playwright.sync_api import sync_playwright
    DEBUG.mkdir(parents=True, exist_ok=True)
    cands, jsons = [], []

    def busca_en_json(o, ctx=''):
        if isinstance(o, dict):
            texto = ' '.join(str(v) for v in o.values() if isinstance(v, (str, int)))
            for v in o.values():
                if isinstance(v, str) and (v.lower().endswith('.pdf') or '.pdf?' in v.lower()): anota(cands, v, texto)
                else: busca_en_json(v, texto)
        elif isinstance(o, list):
            for v in o: busca_en_json(v, ctx)

    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(locale='es-ES')

        def on_resp(r):
            try:
                if 'json' in (r.headers.get('content-type') or ''):
                    j = r.json(); jsons.append({'url': r.url, 'json': j}); busca_en_json(j)
            except Exception: pass
        pg.on('response', on_resp)
        pg.goto(PORTAL, wait_until='networkidle', timeout=90000); time.sleep(3)

        def recoge(etq):
            for a in pg.query_selector_all('a[href]'):
                try:
                    href = a.get_attribute('href') or ''; txt = (a.inner_text() or '') + ' ' + (a.get_attribute('title') or '')
                    fila = a.evaluate("e => (e.closest('tr,li,mat-card,.card,div') || e).innerText.slice(0, 300)")
                    if '.pdf' in href.lower() or re.search(r'descarg|documento|fichero', href, re.I):
                        anota(cands, pg.evaluate('u => new URL(u, location.href).href', href), f'{txt} {fila} {etq}')
                except Exception: pass
            for u in PDF_RX.findall(pg.content()): anota(cands, u, etq)
        recoge('inicio')
        # recorre desplegables (nativos y de Angular Material) y pulsa «Buscar/Consultar» tras cada opción
        sels = pg.query_selector_all('select')
        for s in sels:
            for o in s.query_selector_all('option'):
                v = o.get_attribute('value'); t = o.inner_text()
                try: s.select_option(v); _pulsa(pg); recoge(t)
                except Exception: pass
        n_mat = len(pg.query_selector_all('mat-select, [role=combobox]'))
        for i in range(n_mat):
            try:
                c = pg.query_selector_all('mat-select, [role=combobox]')[i]; c.click(); time.sleep(0.8)
                n_op = len(pg.query_selector_all('mat-option, [role=option]'))
                pg.keyboard.press('Escape')
                for k in range(n_op):
                    c = pg.query_selector_all('mat-select, [role=combobox]')[i]; c.click(); time.sleep(0.6)
                    ops = pg.query_selector_all('mat-option, [role=option]')
                    if k >= len(ops): break
                    t = ops[k].inner_text(); ops[k].click(); time.sleep(0.8); _pulsa(pg); recoge(t)
            except Exception: pass
        # volcado legible en el registro de Actions (los artefactos no siempre se pueden descargar)
        print('== URL final:', pg.url, '| título:', pg.title())
        print('== Texto visible (inicio):'); print((pg.inner_text('body') or '')[:4000])
        print('== Controles:', [(e.evaluate('e=>e.tagName'), (e.inner_text() or '')[:60]) for e in pg.query_selector_all('button, select, mat-select, [role=combobox], [role=tab], a[href]')][:80])
        print('== Respuestas JSON:'); [print('  ', j['url'], json.dumps(j['json'], ensure_ascii=False)[:600]) for j in jsons[:40]]
        pg.screenshot(path=str(DEBUG / 'portal.png'), full_page=True)
        (DEBUG / 'portal.html').write_text(pg.content(), encoding='utf-8')
        b.close()
    (DEBUG / 'respuestas_json.json').write_text(json.dumps(jsons, ensure_ascii=False)[:5_000_000], encoding='utf-8')
    (DEBUG / 'candidatos.json').write_text(json.dumps(cands, ensure_ascii=False, indent=1), encoding='utf-8')
    # elige por año y tipo: mejor versión; para plantilla, la definitiva
    f = carga_fuentes()
    for c in sorted(cands, key=lambda c: -c['version']):
        if c['tipo'] == 'plantilla_provisional': continue
        e = f.setdefault(str(c['anio']), {'origen': 'descubierto'})
        if e.get('origen') == 'manual' or c['tipo'] in e: continue
        e[c['tipo']] = c['url']
    guarda_fuentes(f)
    print(f'{len(cands)} candidatos · años con cuaderno: {sorted(k for k, v in f.items() if "cuaderno" in v)}')
    print(f'Años sin cuaderno: {[a for a in range(ANIO_MIN, ANIO_MAX + 1) if "cuaderno" not in f.get(str(a), {})]}')


def _pulsa(pg):
    for txt in ('Buscar', 'Consultar', 'Aceptar', 'Mostrar'):
        btn = pg.query_selector(f'button:has-text("{txt}")')
        if btn:
            try: btn.click(); pg.wait_for_load_state('networkidle', timeout=15000); time.sleep(1)
            except Exception: pass
            return


def descargar(imagenes=False):
    from playwright.sync_api import sync_playwright
    f = carga_fuentes(); hechos, fallos = [], []
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(locale='es-ES')
        try: ctx.new_page().goto(PORTAL, wait_until='networkidle', timeout=90000)   # cookies de sesión, por si el portal las pide
        except Exception: pass
        for anio, e in sorted(f.items()):
            for tp in ('cuaderno', 'plantilla') + (('imagenes',) if imagenes else ()):
                u = e.get(tp)
                if not u: continue
                dst = RAW / anio / f'{tp}.pdf'
                if dst.exists() and dst.stat().st_size > 100_000: continue   # un PDF de imágenes de pocos KB es una respuesta vacía: se vuelve a pedir
                try:
                    r = ctx.request.get(u, timeout=120000)
                    body = r.body()
                    if r.status != 200 or not body.startswith(b'%PDF'): raise RuntimeError(f'HTTP {r.status}, {len(body)} bytes, no es PDF')
                    dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(body); hechos.append(f'{anio}/{tp}')
                except Exception as ex: fallos.append(f'{anio}/{tp}: {ex}')
        b.close()
    print('Descargados:', ', '.join(hechos) or 'ninguno'); print('Fallos:', *fallos, sep='\n  ')


API = 'https://fse.sanidad.gob.es/hera/api/datos/convocatoria/'


def _b64_pdf(o):
    """Busca dentro de la respuesta JSON el PDF en base64 (empieza por «JVBER», que es «%PDF»)."""
    if isinstance(o, str): return o if o.startswith('JVBER') else None
    if isinstance(o, dict): o = list(o.values())
    if isinstance(o, list):
        for v in o:
            r = _b64_pdf(v)
            if r: return r
    return None


TITULACIONES = ('R', 'RF', 'FI', 'FS', 'FIS', 'RFIR')   # código de Física en la API del portal (Medicina «M», Enfermería «E»); se comprueba con el PDF


def _es_cuaderno_titulacion(pdf):
    """El PDF descargado debe ser un cuaderno de Física (y no de Medicina u otra titulación): se mira la portada."""
    import io, pdfplumber
    with pdfplumber.open(io.BytesIO(pdf)) as d:
        tx = (d.pages[0].extract_text() or '').lower()
    import unicodedata
    tx = unicodedata.normalize('NFD', tx).encode('ascii', 'ignore').decode()
    return bool(re.search(r'fisic|radiof', tx[:800]))


def api(titulacion=None, imagenes=False):
    """Descarga por la API del portal FSE (la misma que usa su web, con su token anónimo):
    getAnyos → para cada convocatoria: cuaderno versión 0 (PDF) y hoja de respuestas (JSON).
    La «convocatoria N» se examina en enero de N+1: se guarda en data/raw/<N+1>/."""
    import base64
    from playwright.sync_api import sync_playwright
    hecho, fallos = [], []
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(locale='es-ES'); pg = ctx.new_page(); auth = {}
        pg.on('request', lambda r: auth.setdefault('h', r.headers.get('authorization')) if '/hera/api/' in r.url and r.headers.get('authorization') else None)
        pg.goto(PORTAL, wait_until='networkidle', timeout=90000); time.sleep(3)
        if not auth.get('h'): raise SystemExit('No se obtuvo el token anónimo del portal')
        H = {'Authorization': auth['h'], 'Accept': 'application/json'}
        get = lambda ruta: ctx.request.get(API + ruta, headers=H, timeout=180000)
        anyos = get('getAnyos').json(); print('Convocatorias disponibles en el portal:', anyos)
        if not titulacion:   # se prueba cada código con la última convocatoria hasta dar con un cuaderno de Física
            for cod in TITULACIONES:
                try:
                    b64 = _b64_pdf(get(f'getDatosCuadernosExamen?titulacion={cod}&anyo={max(anyos)}&version=0&opcionSelect=C').json())
                    if b64 and _es_cuaderno_titulacion(base64.b64decode(b64)): titulacion = cod; break
                    print(f'  titulación «{cod}»: no devuelve un cuaderno de Física')
                except Exception as e: print(f'  titulación «{cod}»: {e}')
            if not titulacion: raise SystemExit('Ningún código de titulación devuelve el cuaderno de Física: lanza el paso «sondear» y pásalo con --titulacion')
        print('Titulación usada:', titulacion)
        for an in sorted(anyos):
            d = RAW / str(an + 1); d.mkdir(parents=True, exist_ok=True)
            (d / 'convocatoria.txt').write_text(f'convocatoria {an}/{an + 1} · titulación {titulacion}\n', encoding='utf-8')
            for op, nombre in (('C', 'cuaderno'),) + ((('I', 'imagenes'),) if imagenes else ()):
                dst = d / f'{nombre}.pdf'
                if dst.exists() and dst.stat().st_size > 100_000: continue   # un PDF de imágenes de pocos KB es una respuesta vacía: se vuelve a pedir
                try:
                    r = get(f'getDatosCuadernosExamen?titulacion={titulacion}&anyo={an}&version=0&opcionSelect={op}')
                    if op == 'I': print(f'  imágenes {an}: HTTP {r.status}, {len(r.body()) // 1024} KB')
                    j = r.json(); b64 = _b64_pdf(j)
                    if not b64: raise RuntimeError('sin PDF en la respuesta: ' + str(j)[:300])
                    dst.write_bytes(base64.b64decode(b64)); hecho.append(f'{an + 1}/{nombre}')
                except Exception as e: fallos.append(f'{an}/{nombre}: {e}')
            try:
                r = get(f'getHojaRespuestas?titulacion={titulacion}&anyo={an}&version=0')
                j = r.json(); b64 = _b64_pdf(j)
                if b64: (d / 'plantilla.pdf').write_bytes(base64.b64decode(b64)); hecho.append(f'{an + 1}/plantilla.pdf')
                else: (d / 'respuestas.json').write_text(json.dumps(j, ensure_ascii=False), encoding='utf-8'); hecho.append(f'{an + 1}/respuestas.json')
                print(f'  hoja de respuestas {an}:', json.dumps(j, ensure_ascii=False)[:500] if not b64 else 'PDF')
            except Exception as e: fallos.append(f'{an}/respuestas: {e}')
        b.close()
    print('Descargados:', ', '.join(hecho) or 'ninguno'); print('Fallos:', *fallos, sep='\n  ')


def sondear():
    """Pulsa «Ver» (cuaderno y hoja de respuestas) y anota cada petición a la API, para conocer la URL de descarga."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(locale='es-ES', accept_downloads=True); pg = ctx.new_page()
        log = []
        def on_req(r):
            if '/hera/' in r.url and 'i18n' not in r.url:
                h = {k: ('***' if k.lower() == 'authorization' else v) for k, v in r.headers.items() if k.lower() in ('authorization', 'accept', 'content-type')}
                log.append(f'REQ {r.method} {r.url} {h} {(r.post_data or "")[:300]}')
        def on_resp(r):
            if '/hera/' in r.url and 'i18n' not in r.url:
                log.append(f'RESP {r.status} {r.url} {r.headers.get("content-type")} {r.headers.get("content-disposition")}')
        ctx.on('request', on_req); ctx.on('response', on_resp)
        ctx.on('page', lambda np: log.append(f'POPUP {np.url}'))
        pg.on('download', lambda d: log.append(f'DOWNLOAD {d.url} {d.suggested_filename}'))
        pg.goto(PORTAL, wait_until='networkidle', timeout=90000); time.sleep(3)
        log.append('---- pulsar Ver (cuaderno) ----')
        for etiqueta in ('Cuaderno de texto', 'Hoja de respuestas'):
            try:
                pg.get_by_text(etiqueta, exact=True).first.click(); time.sleep(1)
                with pg.expect_popup(timeout=8000) as pop:
                    pg.get_by_role('button', name='Ver').click()
                np = pop.value; time.sleep(3); log.append(f'POPUP URL {etiqueta}: {np.url}')
            except Exception as e:
                log.append(f'sin popup ({etiqueta}): {type(e).__name__}'); time.sleep(3)
            log.append(f'---- tras {etiqueta} ----')
        html = pg.inner_html('body')
        i = html.find('Titulaci'); log.append('HTML del formulario: ' + re.sub(r'\s+', ' ', html[i - 200:i + 3000]) if i > 0 else 'sin formulario')
        print('\n'.join(log)); b.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--descubrir', action='store_true'); ap.add_argument('--descargar', action='store_true'); ap.add_argument('--sondear', action='store_true'); ap.add_argument('--api', action='store_true', help='descarga por la API del portal (recomendado)')
    ap.add_argument('--imagenes', action='store_true', help='baja también los cuadernillos de imágenes (pesan mucho)')
    ap.add_argument('--titulacion', help='código de Física en la API del portal (si no se da, se prueba entre TITULACIONES)')
    a = ap.parse_args()
    if a.sondear: sondear(); sys.exit(0)
    if a.api: api(a.titulacion, imagenes=a.imagenes); sys.exit(0)
    if not (a.descubrir or a.descargar): a.descubrir = a.descargar = True
    if a.descubrir: descubrir()
    if a.descargar: descargar(a.imagenes)
