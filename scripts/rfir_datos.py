#!/usr/bin/env python3
"""OráculoRFIR · de los PDF oficiales a data/rfir.json (sin red).

    python3 scripts/rfir_datos.py                 # lee data/raw/<año>/{cuaderno,plantilla}.pdf
    python3 scripts/rfir_datos.py --solo-informe  # vuelve a clasificar y a escribir el informe con lo ya extraído

Para cada año:
  1. extrae el texto del cuaderno (versión 0) y de la plantilla DEFINITIVA de respuestas (pdfplumber);
  2. separa preguntas y opciones (parse_cuaderno) y lee la respuesta correcta de cada número (parse_plantilla);
  3. clasifica cada pregunta en una asignatura con las palabras clave de data/asignaturas.json (clasifica);
  4. escribe data/rfir.json (lo que lee la app) y data/informe.md (qué se extrajo y qué falló, año a año).
Nada se inventa: una pregunta sin respuesta en la plantilla queda con correcta=null y no entra en simulacros."""
import argparse, json, re, sys, unicodedata, datetime, pathlib

R = pathlib.Path(__file__).resolve().parent.parent
RAW, OUT = R / 'data' / 'raw', R / 'data'


def norm(s):
    s = unicodedata.normalize('NFD', str(s or '').lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9ñ]+', ' ', s).strip()


# ── 1 · cuaderno ───────────────────────────────────────────────────────────────────────────────
RUIDO = re.compile(r'^\s*(-?\s*\d+\s*-|\d+\s*/\s*\d+|p[aá]gina\s*:?(\s*\d+.*)?|\d+\s+de\s+\d+|:\s*\d+\s+de\s+\d+|\)\d+/\d+-+\d+-+\w+-+\(|\(-+\w+-+\d+-+\d+/\d+\(|versi[oó]n\s*:?\s*\d+.*|rfir\s*20\d\d.*|radiof[ií]sica\s*$|f[ií]sica\s*$|f[ií]sicos\s*$|cuaderno de examen.*|ministerio de sanidad.*|pruebas selectivas.*)\s*$', re.I)
NUM = re.compile(r'^\s*(\d{1,3})\s*[.)]\s*(.*)$')


SIN_PUNTO = re.compile(r'^\s*(\d{1,3})\s+([A-ZÁÉÍÓÚÑ¿].*)$')   # número de pregunta sin punto: solo si es justo la siguiente


def limpia_lineas(texto):
    return [l.rstrip() for l in texto.replace('\r', '').split('\n') if l.strip() and not RUIDO.match(l)]


def _contiene(largo, corto):
    """¿Están las cifras de «corto» en orden dentro de «largo», con una o dos de más?"""
    if not 0 < len(largo) - len(corto) <= 2: return False
    it = iter(largo); return all(c in it for c in corto)


SIMBOLO = {**{0xF000 + ord(c): c for c in '0123456789.,()+=*/:;<>[] '},   # fuente Symbol: cifras y signos en el área privada (el resto, p. ej. flechas, se deja)
           **{0xF000 + ord(a): g for a, g in zip('abgdezhqiklmnxprstufcywABGDEZHQIKLMNXPRSTUFCYW', 'αβγδεζηθικλμνξπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΠΡΣΤΥΦΧΨΩ')}}


def parse_cuaderno(texto, nopt):
    """Máquina de estados: pregunta q → enunciado → opciones 1..nopt → pregunta q+1.
    Un número de línea es opción si es la siguiente opción esperada; es pregunta nueva si es q+1 y ya están todas las opciones."""
    qs, cur, campo = [], None, None
    for l in limpia_lineas(texto):
        m4 = re.match(r'^\s*(\d{4,5})(?=\s*[.)])', l)
        if m4 and cur is not None and len(cur['opciones']) == nopt and _contiene(m4.group(1), str(cur['n'] + 1)):
            l = str(cur['n'] + 1) + l[m4.end():]   # «1317.» → «137.»
        m = NUM.match(l)
        if not m and cur is not None and len(cur['opciones']) == nopt:   # errata del PDF: «165 La terapia…» sin punto
            m2 = SIN_PUNTO.match(l)
            if m2 and int(m2.group(1)) == cur['n'] + 1: m = m2
        if m:
            n, resto = int(m.group(1)), m.group(2).strip()
            sig_q = (qs[-1]['n'] + 1 if qs else 1) if cur is None else cur['n'] + 1
            if cur is not None and len(cur['opciones']) < nopt and n == len(cur['opciones']) + 1 and campo is not None:
                cur['opciones'].append(resto); campo = 'opcion'; continue
            if n != sig_q and cur is not None and len(cur['opciones']) == nopt and _contiene(str(n), str(sig_q)):
                n = sig_q   # número impreso dos veces con desplazamiento («1317.» por «137.»)
            if n == sig_q and cur is not None and nopt < n and len(cur['opciones']) < nopt and len(resto) > 15 and campo == 'opcion':
                qs.append(cur); cur = None   # la anterior no tiene sus opciones numeradas (fórmulas dibujadas): se descarta y se sigue
            if n == sig_q and (cur is None or len(cur['opciones']) == nopt):
                if cur is not None: qs.append(cur)
                cur = {'n': n, 'enunciado': resto, 'opciones': []}; campo = 'enunciado'; continue
        if cur is None: continue
        if campo == 'enunciado': cur['enunciado'] = (cur['enunciado'] + ' ' + l.strip()).strip()
        elif campo == 'opcion': cur['opciones'][-1] = (cur['opciones'][-1] + ' ' + l.strip()).strip()
    if cur is not None: qs.append(cur)
    une = lambda x: re.sub(r'(\w)- (?=[a-záéíóúñü])', r'\1', re.sub(r'\s+', ' ', x)).strip()   # «alér- gica» → «alérgica» (guion de fin de línea)
    for q in qs:
        q['enunciado'] = une(q['enunciado'])
        q['opciones'] = [re.sub(r'\s+-(\s*\d{1,3})?(\s*-)?$', '', une(o)) for o in q['opciones']]   # pie de página «- 3 -» pegado a la última opción
        q['imagen'] = bool(re.search(r'\bimagen(?:es)?\s*(?:n\s*[ºo°.]*\s*)?\d', q['enunciado'], re.I))   # solo «imagen nº 3»: «imagen corporal» o «la figura de Nightingale» no llevan imagen
    return [q for q in qs if len(q['opciones']) == nopt]


def mejor_cuaderno(texto):
    """Los RFIR antiguos tienen 5 opciones y los recientes 4, y la portada trae instrucciones numeradas («1. Compruebe…»).
    Se prueba a empezar en cada una de las primeras líneas «1.» y con 4 y 5 opciones; gana lo que extrae más preguntas."""
    ls = texto.replace('\r', '').split('\n')
    inicios = [i for i, l in enumerate(ls) if NUM.match(l) and int(NUM.match(l).group(1)) == 1][:12] or [0]
    mejor = ([], 4)
    cinco = sum(1 for l in ls if re.match(r'^\s*5\s*[.)]\s', l))   # muchas líneas «5.» → examen de 5 opciones (RFIR antiguos)
    q_aprox = max(1, sum(1 for l in ls if re.match(r'^\s*1\s*[.)]\s', l)))
    opciones = (5,) if cinco >= 0.6 * q_aprox else (4, 5)
    for i in inicios:
        t = '\n'.join(ls[i:])
        for nopt in opciones:
            qs = parse_cuaderno(t, nopt)
            if qs and len(qs) >= len(mejor[0]): mejor = (qs, nopt)   # empate → el inicio más tardío (se salta la portada)
    return mejor


# ── 2 · plantilla ──────────────────────────────────────────────────────────────────────────────
TOK = re.compile(r'ANULADA|ANUL\.?|(?<![\d/])\d{1,3}(?![\d/])', re.I)   # números enteros de 1-3 cifras: «2008» o «07/04» no se trocean   # un guion NO es anulada: «reserva (176 - 185)» lo confundía


def _val(tk, nopt):
    if tk.upper().startswith('ANUL'): return 0          # 0 = anulada
    v = int(tk); return v if 1 <= v <= nopt else None


def parse_plantilla(texto, n_preg, nopt):
    """Devuelve {n: correcta (1..nopt) | 0 (anulada)} con la estrategia que cubre más números 1..n_preg.
    A) parejas «número respuesta» seguidas (tablas a varias columnas);
    B) una fila por pregunta con una columna por versión: se toma la primera (versión 0)."""
    expl = re.findall(r'pregunta\s+(\d{1,3})\s*,\s*(?:respuesta\s+(\d)|(anulada))', texto, re.I)   # «pregunta 176, respuesta 2» / «pregunta 10, anulada»
    if len(expl) >= 0.5 * n_preg:
        return {int(q): (0 if an else int(r)) for q, r, an in expl if 1 <= int(q) <= n_preg and (an or 1 <= int(r) <= nopt)}
    lineas = [TOK.findall(l) for l in texto.split('\n')]
    A, B = {}, {}
    for tks in lineas:
        for i in range(0, len(tks) - 1, 2):
            if tks[i].isdigit():
                q, v = int(tks[i]), _val(tks[i + 1], nopt)
                if 1 <= q <= n_preg and v is not None and q not in A: A[q] = v
        if len(tks) >= 2 and tks[0].isdigit():
            q, v = int(tks[0]), _val(tks[1], nopt)
            if 1 <= q <= n_preg and v is not None and q not in B: B[q] = v
    # C) tabla «V RC V RC…» donde la anulada es un HUECO («106 158 5»: la 106 no tiene respuesta). Tras un número de pregunta,
    #    el siguiente número es su respuesta solo si está entre 1 y nopt; si no, es la pregunta de la columna siguiente.
    C = {}
    for tks in lineas:
        i = 0
        while i < len(tks):
            if not tks[i].isdigit(): i += 1; continue
            q = int(tks[i]); sig = tks[i + 1] if i + 1 < len(tks) else None
            if sig is not None and (sig.upper().startswith('ANUL') or (sig.isdigit() and 1 <= int(sig) <= nopt)):
                v = _val(sig, nopt); i += 2
            else: v = 0; i += 1
            if 1 <= q <= n_preg and q not in C: C[q] = v
    cubre = lambda d: sum(1 for i in range(1, n_preg + 1) if i in d)
    if cubre(C) >= max(cubre(A), cubre(B)) and re.search(r'\bRC\b', texto): return C
    por_versiones = len(set(re.findall(r'\bV\s?([0-4])\b', texto, re.I))) >= 2   # cabecera «V0 V1 V2…»
    if por_versiones and cubre(B) >= 0.9 * cubre(A): return B
    return A if cubre(A) >= cubre(B) else B


def parse_respuestas_json(filas):
    """Hoja de respuestas de la API del portal (de la versión pedida, la 0): la tabla viene en columnas,
    cada fila trae pares V_k (nº de pregunta) / RC_k (respuesta) para k = 0..4 → preguntas 1-42, 43-84, 85-126…
    Devuelve {n: correcta | 0 si anulada (respuesta en blanco)}."""
    out = {}
    for f in filas:
        for k in range(10):
            if f'V_{k}' not in f: continue
            q, rc = str(f.get(f'V_{k}', '')).strip(), str(f.get(f'RC_{k}', '')).strip()
            if q.isdigit(): out[int(q)] = int(rc) if rc in ('1', '2', '3', '4', '5') else 0
    return out


# ── 3 · clasificación por palabras clave ─────────────────────────────────────────────────────────
def carga_asignaturas():
    return json.loads((OUT / 'asignaturas.json').read_text(encoding='utf-8'))['asignaturas']


def clasifica(q, asigs):
    """Puntúa cada asignatura: palabra clave en el enunciado = 2 × nº de palabras de la clave; en las opciones = 1 ×.
    Devuelve (id, confianza 0-1). Sin coincidencias → ('otras', 0)."""
    en, op = ' ' + norm(q['enunciado']) + ' ', ' ' + norm(' '.join(q['opciones'])) + ' '
    pts = {}
    for a in asigs:
        s = 0
        for kw in a['kw']:
            k = norm(kw); w = len(k.split())
            rx = re.compile(r'(?<![a-z0-9])' + re.escape(k))
            s += 2 * w * len(rx.findall(en)) + w * len(rx.findall(op))
        if s: pts[a['id']] = s * a.get('peso', 1)   # asignaturas con palabras muy generales (imagen, anatomía…) pesan menos
    if not pts: return 'otras', 0.0
    orden = sorted(pts.items(), key=lambda x: -x[1])
    total = sum(pts.values())
    return orden[0][0], round(orden[0][1] / total, 2)


# ── 4 · montaje ────────────────────────────────────────────────────────────────────────────────
def _dos_columnas(pg):
    """¿Página maquetada a dos columnas? Casi ninguna palabra cruza el centro y las dos mitades tienen texto."""
    ws = pg.extract_words(); mid = pg.width / 2
    if len(ws) < 40: return False
    ws = [w for w in ws if sum(c.isalpha() for c in w['text']) >= 3] or ws   # sin las letras sueltas de estructuras y fórmulas dibujadas
    if len(ws) < 30: return False
    cruza = sum(1 for w in ws if w['x0'] < mid < w['x1']); izq = sum(1 for w in ws if w['x1'] <= mid)
    r = izq / len(ws)
    return cruza / len(ws) < 0.02 and (0.2 < r < 0.8 or (cruza == 0 and 0.05 < r < 0.95))   # una columna casi vacía (estructuras o figuras dibujadas) sigue siendo dos columnas


def _medianil(pg):
    """Dónde partir una página a dos columnas: el hueco vertical sin letras más cercano al centro (sin contar cabecera ni pie,
    que suelen ir centrados). Los números de pregunta de la columna derecha a veces asoman a la izquierda de la mitad exacta."""
    w, h = pg.width, pg.height; ocup = [0] * (int(w) + 2)
    for c in pg.chars:
        if c['text'].strip() and 0.07 * h < c['top'] < 0.93 * h:
            for x in range(max(0, int(c['x0'])), min(len(ocup), int(c['x1']) + 1)): ocup[x] += 1
    libres = [x for x in range(int(w * 0.38), int(w * 0.62)) if ocup[x] == 0]
    tramos, ini = [], None
    for a, b in zip(libres, libres[1:] + [None]):
        ini = a if ini is None else ini
        if b != a + 1:
            if a - ini >= 3: tramos.append((ini, a))
            ini = None
    if not tramos: return w / 2
    i, f = min(tramos, key=lambda t: (0 if t[0] <= w / 2 <= t[1] else min(abs(t[0] - w / 2), abs(t[1] - w / 2)), -(t[1] - t[0])))
    return (i + f) / 2


def texto_pdf(p, columnas=True):
    """Texto en orden de lectura: si la página va a dos columnas, primero la izquierda y luego la derecha.
    columnas=False para tablas (plantillas): partir la página por la mitad separaría números de sus respuestas."""
    import pdfplumber
    out = []
    with pdfplumber.open(p) as pdf:
        for pg in pdf.pages:
            pg = pg.dedupe_chars()   # caracteres impresos dos veces con un leve desplazamiento («1317..» en vez de «137.»)
            pies = [round(w['top']) for w in pg.extract_words() if w['top'] > 0.85 * pg.height and re.match(r'p[aá]gina', w['text'], re.I)]
            if pies:   # pie «Página: 3 de 20» centrado: al partir la página quedaría «Págin» en una columna y «a: 3 de 20» en la otra
                pg = pg.filter(lambda o: not (o.get('object_type') == 'char' and any(abs(o['top'] - t) < 3 for t in pies)))
            if columnas and _dos_columnas(pg):
                w, h = pg.width, pg.height; x = _medianil(pg)
                out += [pg.crop((0, 0, x, h)).extract_text() or '', pg.crop((x, 0, w, h)).extract_text() or '']
            else: out.append(pg.extract_text() or '')
    return '\n'.join(out).translate(SIMBOLO)


def procesa_anio(anio, d):
    inf = {'anio': anio, 'ok': False}
    cu, pl = d / 'cuaderno.pdf', d / 'plantilla.pdf'
    if not cu.exists(): inf['error'] = 'falta cuaderno.pdf'; return [], inf
    tx = (d / 'cuaderno.txt').read_text(encoding='utf-8') if (d / 'cuaderno.txt').exists() else texto_pdf(cu)
    (d / 'cuaderno.txt').write_text(tx, encoding='utf-8')
    qs, nopt = mejor_cuaderno(tx)
    fuente = 'tercero' if (d / 'origen.txt').exists() else 'portal'
    inf.update(preguntas=len(qs), opciones=nopt, fuente=fuente)
    if not qs: inf['error'] = 'no se reconocieron preguntas en el cuaderno'; return [], inf
    resp = {}
    if (d / 'respuestas_cruce.json').exists():   # años sin plantilla legible: cruce por texto con una transcripción validada (scripts/rfir_cruce_og.py)
        resp = {int(k): v for k, v in json.loads((d / 'respuestas_cruce.json').read_text(encoding='utf-8')).items()}
    elif (d / 'respuestas.json').exists():   # hoja de respuestas de la API del portal: filas {V_0: nº de pregunta en la versión 0, RC_0: respuesta}
        resp = parse_respuestas_json(json.loads((d / 'respuestas.json').read_text(encoding='utf-8')))
    elif pl.exists() or (d / 'plantilla.txt').exists():
        tp = (d / 'plantilla.txt').read_text(encoding='utf-8') if (d / 'plantilla.txt').exists() else texto_pdf(pl, columnas=False)
        (d / 'plantilla.txt').write_text(tp, encoding='utf-8')
        resp = parse_plantilla(tp, max(q['n'] for q in qs), nopt)
    inf['con_respuesta'] = sum(1 for q in qs if resp.get(q['n']))
    inf['anuladas'] = sum(1 for q in qs if resp.get(q['n']) == 0)
    huecos = [i for i in range(1, max(q['n'] for q in qs) + 1) if i not in {q['n'] for q in qs}]
    inf['huecos'] = huecos[:30]
    out = []
    for q in qs:
        r = resp.get(q['n'])
        img = None
        if q['imagen']:   # «Pregunta vinculada a la imagen nº 5» → data/img/<año>/5.jpg, si existe
            mi = re.search(r'imagen(?:es)?\s*(?:n\s*[ºo°.]*\s*)?(\d{1,3})', q['enunciado'], re.I)
            if mi and (OUT / 'img' / str(anio) / f'{int(mi.group(1))}.jpg').exists(): img = f'data/img/{anio}/{int(mi.group(1))}.jpg'
        if (OUT / 'img' / str(anio) / f"q{q['n']}.jpg").exists():   # estructura o figura dibujada dentro del cuaderno (scripts/rfir_figuras.py)
            img = f"data/img/{anio}/q{q['n']}.jpg"; q['imagen'] = True
        if any(not o.strip() for o in q['opciones']): q['imagen'] = True   # opciones dibujadas (estructuras, fórmulas): fuera de los simulacros salvo que haya figura
        out.append({'id': f"{anio}-{q['n']:03d}", 'anio': anio, 'n': q['n'], 'enunciado': q['enunciado'], 'opciones': q['opciones'],
                    'correcta': r if r else None, 'anulada': r == 0, 'imagen': q['imagen'], 'fuente': fuente, **({'img': img} if img else {})})
    inf['ok'] = True
    return out, inf


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--solo-informe', action='store_true'); a = ap.parse_args()
    asigs = carga_asignaturas()
    preg, informes = [], []
    for d in sorted(p for p in RAW.glob('20[0-9][0-9]') if p.is_dir() and any(p.iterdir())):
        anio = int(d.name)
        try: qs, inf = procesa_anio(anio, d)
        except Exception as e: qs, inf = [], {'anio': anio, 'ok': False, 'error': f'{type(e).__name__}: {e}'}
        preg += qs; informes.append(inf)
    ia = json.loads((OUT / 'clasificacion_ia.json').read_text(encoding='utf-8')) if (OUT / 'clasificacion_ia.json').exists() else {}
    for q in preg:
        if q['id'] in ia: q['asig'], q['conf'], q['metodo'] = ia[q['id']], 1.0, 'ia'
        else: q['asig'], q['conf'] = clasifica(q, asigs); q['metodo'] = 'palabras'
    datos = {'generado': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
             'fuente': 'Cuadernos de examen y plantillas definitivas de respuestas del Ministerio de Sanidad (fse.sanidad.gob.es)',
             'clasificacion': 'IA (data/clasificacion_ia.json) cuando existe; si no, palabras clave (data/asignaturas.json)',
             'asignaturas': [{'id': x['id'], 'nombre': x['nombre']} for x in asigs] + [{'id': 'otras', 'nombre': 'Sin clasificar'}],
             'examenes': informes, 'preguntas': preg}
    ver = json.loads((OUT / 'verificacion.json').read_text(encoding='utf-8')) if (OUT / 'verificacion.json').exists() else {}
    for i in informes:
        v = ver.get(str(i['anio']))
        if not v or not i.get('ok'): continue
        mias = sorted(q['n'] for q in preg if q['anio'] == i['anio'] and q['anulada'] and q['n'] <= v.get('hasta', 999))
        pub = sorted(v['anuladas']); cb = {int(k): c for k, c in v.get('cambios', {}).items()}
        res = {q['n']: q['correcta'] for q in preg if q['anio'] == i['anio']}
        cb_ok = all(res.get(k) == c for k, c in cb.items())
        i['cotejo'] = {'publicadas': pub, 'extraidas': mias, 'coincide': mias == pub and cb_ok, 'cambios_ok': cb_ok, 'n_cambios': len(cb), 'fuente': v['fuente']}
    datos_cotejo = True
    (OUT / 'rfir.json').write_text(json.dumps(datos, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    # informe legible
    L = ['# Informe de extracción · OráculoRFIR', '', f"Generado: {datos['generado']}", '',
         '| Año | Preguntas | Opciones | Con respuesta | Anuladas | Cotejo con lo publicado | Estado |', '|---|---|---|---|---|---|---|']
    for i in informes:
        L.append(f"| {i['anio']}{' (copia)' if i.get('fuente') == 'tercero' else ''} | {i.get('preguntas', 0)} | {i.get('opciones', '')} | {i.get('con_respuesta', 0)} | {i.get('anuladas', 0)} | {(('✓ anuladas' + (f" y {i['cotejo']['n_cambios']} cambios" if i['cotejo']['n_cambios'] else '')) if i['cotejo']['coincide'] else '✕ publicadas ' + str(i['cotejo']['publicadas']) + ' · extraídas ' + str(i['cotejo']['extraidas']) + ('' if i['cotejo']['cambios_ok'] else ' · cambios NO')) if i.get('cotejo') else '—'} | {'✓' if i['ok'] else '✕ ' + i.get('error', '')} |")
    sc = sum(1 for q in preg if q['asig'] == 'otras')
    nia = sum(1 for q in preg if q.get('metodo') == 'ia')
    L += ['', f'Preguntas totales: {len(preg)} · clasificadas con IA: {nia} · sin clasificar: {sc} ({(sc / max(1, len(preg))):.0%})', '',
          'Revisa a mano al menos 20 preguntas por año contra el PDF antes de fiarte de los datos.']
    (OUT / 'informe.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
    print('\n'.join(L))
    return 0 if preg else 1


if __name__ == '__main__':
    sys.exit(main())
