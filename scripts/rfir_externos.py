#!/usr/bin/env python3
"""OráculoRFIR · RFIR antiguos (anteriores a los que ofrece el portal) desde copias de terceros de los PDF oficiales (data/fuentes_externas.json).
Se ejecuta en GitHub Actions (allí hay red):  python3 scripts/rfir_externos.py
Para cada año prueba las URL en orden y se queda con la primera que pasa las comprobaciones:
  · cuaderno: es un PDF, su portada menciona FÍSICA, es la versión 0 y se extraen al menos el 90 % de las preguntas esperadas para ese año;
  · plantilla: PDF o página web cuyas respuestas cubren al menos el 90 % de las preguntas extraídas.
Lo que no pasa se descarta y se dice en el registro. Cada año guarda su origen en data/raw/<año>/origen.txt."""
import json, os, re, sys, html, pathlib, urllib.request, urllib.parse, http.cookiejar, tempfile, unicodedata
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import rfir_datos as M
R = pathlib.Path(__file__).resolve().parent.parent; RAW = R / 'data' / 'raw'
ESPERADAS = lambda y: 260 if y <= 2013 else 235 if y <= 2019 else 185 if y <= 2021 else 210   # incluidas las de reserva; si la portada lo dice, manda la portada (anunciadas)
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'}
DUDOSAS = set()   # plantillas sin año en su texto (de la cosecha): solo valen si la IA coincide con ellas
ORIG = {}   # fichero local de la cosecha → enlace de origen (para origen.txt)
cj = http.cookiejar.CookieJar(); OP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def baja(url):
    if url.startswith('file://'): return pathlib.Path(urllib.parse.unquote(urllib.parse.urlparse(url).path)).read_bytes()   # PDF ya bajado por la cosecha
    m = re.search(r'[?&]id=([\w-]+)', url) if 'drive.google' in url else None
    if m: url = f'https://drive.usercontent.google.com/download?id={m.group(1)}&export=download&confirm=t'
    url = urllib.parse.quote(url, safe=':/?&=%#')   # tildes en el nombre («Formación-Sanitaria-Especializada.pdf»)
    b = OP.open(urllib.request.Request(url, headers=UA), timeout=120).read()
    if m and b[:4] != b'%PDF':
        # página de aviso de Drive (fichero grande): reenviar su formulario con los campos ocultos (id, export, confirm, uuid…)
        t = b.decode('utf-8', 'ignore'); f = re.search(r'<form[^>]*action="([^"]+)"[^>]*>(.*?)</form>', t, re.S)
        if f:
            campos = dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', f.group(2)))
            u2 = html.unescape(f.group(1)) + '?' + urllib.parse.urlencode(campos)
            b = OP.open(urllib.request.Request(u2, headers=UA), timeout=180).read()
        if b[:4] != b'%PDF':
            tit = re.search(r'<title>(.*?)</title>', b.decode('utf-8', 'ignore'), re.S)
            raise ValueError('Drive no da el PDF: ' + (tit.group(1).strip()[:80] if tit else b[:80].decode('utf-8', 'ignore')))
    return b


def texto_de(b, url, columnas=True):
    if b[:4] == b'%PDF':
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f: f.write(b); n = f.name
        return M.texto_pdf(n, columnas), 'pdf'
    t = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', b.decode('utf-8', 'ignore'), flags=re.S)
    t = html.unescape(re.sub(r'<(br|/tr|/li|/p|/div)[^>]*>', '\n', t)); t = re.sub(r'<[^>]+>', ' ', t)
    return t, 'html'


def carpeta_drive(fid, desfase=1):
    """Lee una carpeta pública de Drive y devuelve {(año, 'cuaderno'|'plantilla'): [url de descarga]} según el nombre de cada PDF."""
    t = OP.open(urllib.request.Request(f'https://drive.google.com/drive/folders/{fid}', headers=UA), timeout=60).read().decode('utf-8', 'ignore')
    t = t.replace('\\x22', '"').replace('\\x5b', '[').replace('\\x5d', ']').replace('\\/', '/').replace('\\u0026', '&')
    out = {}
    for fid2, nombre in re.findall(r'"([\w-]{25,60})",\["[\w-]+"\],"([^"]{4,120}?\.pdf)"', t):
        m = re.search(r'(20\d\d)', nombre); n = nombre.lower()
        if not m: continue
        n = unicodedata.normalize('NFD', n).encode('ascii', 'ignore').decode()   # «imágenes» → «imagenes»
        tipo = 'imagenes' if 'imag' in n else 'plantilla' if 'respuesta' in n or 'plantilla' in n else 'cuaderno' if 'cuaderno de examen' in n or re.search(r'examen', n) else None
        print(f'  Drive: {nombre} → {fid2} ({tipo or "se ignora"})')
        if tipo:   # el nombre puede llevar el año del examen o el de la convocatoria: se prueba en ambos y el texto del PDF decide
            out.setdefault((int(m.group(1)) + desfase, tipo), []).insert(0, f'https://drive.google.com/uc?export=download&id={fid2}')
    if not out: print('  Drive: no se reconocieron ficheros en la carpeta', fid, '· longitud de la página', len(t))
    return out


def anunciadas(tx):
    """Preguntas que anuncia la portada del cuaderno, reserva incluida: «225 preguntas más 10 de reserva» → 235."""
    m = re.search(r'(\d{2,3})\s+preguntas\s+m[aá]s\s+(\d{1,2})\s+de\s+reserva', tx, re.I)
    return int(m.group(1)) + int(m.group(2)) if m else None


def anio_examen(tx):
    """Año del EXAMEN según el propio cuaderno: «PRUEBAS SELECTIVAS 2012» se examinó en enero de 2013."""
    m = re.search(r'PRUEBAS\s+SELECTIVAS[^\d]{0,40}?(20\d\d)', tx, re.I)   # a veces se cuela otro campo de la portada («NÚMERO DE MESA:») antes del año
    return int(m.group(1)) + 1 if m else None


def plantilla_del_anio(tx, y):
    """Si la plantilla menciona años, alguno debe ser el del examen o el de su convocatoria (y−1)."""
    c = re.search(r'Convocatoria\s*:?\s*(20\d\d)', tx, re.I)
    if c: return int(c.group(1)) + 1 == y          # «Convocatoria: 2008» → examen de enero de 2009
    ys = {int(a) for a in re.findall(r'(?<!\d)(20\d\d)(?!\d)', tx)}
    return not ys or bool(ys & {y, y - 1})


def concordancia(qs, r, nopt, n=30):
    """Fracción de preguntas en que la IA (secreto OPENAI_API_KEY) elige la misma respuesta que la plantilla.
    Con la plantilla de este examen coinciden casi todas; con la de otro año, solo las que acierte el azar (~25 %).
    None si no hay clave o falla la llamada."""
    key = os.environ.get('OPENAI_API_KEY') or os.environ.get('ANTHROPIC_API_KEY')
    if not key: return None
    import random, rfir_clasifica_ia as IA
    ms = [q for q in qs if r.get(q['n']) in range(1, nopt + 1) and len(q['opciones']) == nopt]
    random.Random(7).shuffle(ms); ms = ms[:n]
    if len(ms) < 10: return None
    prompt = ('Resuelve estas preguntas de un examen oficial de Formación Sanitaria Especializada. Para cada una elige la ÚNICA opción correcta. '
              'Devuelve SOLO este JSON: {"r": {"<número de pregunta>": <opción 1-{nopt}>}}\n\n'.replace('{nopt}', str(nopt)) +
              '\n\n'.join(f"{q['n']}. {q['enunciado']}\n" + '\n'.join(f'{k + 1}. {o}' for k, o in enumerate(q['opciones'])) for q in ms))
    try:
        tx = IA.llama(prompt, key); j = json.loads(tx[tx.index('{'):tx.rindex('}') + 1]).get('r', {})
    except BaseException as e: print('  concordancia con la IA: error', e); return None
    return sum(1 for q in ms if str(j.get(str(q['n']))).strip() == str(r[q['n']])) / len(ms)


def imagenes(F):
    """Cuadernillos de imágenes de los años sin ellos (solo PDF; el año ya viene corregido por el desfase de la carpeta)."""
    for ys, e in F.items():
        if not ys.isdigit(): continue
        d = RAW / ys
        if not (d / 'cuaderno.pdf').exists() or (d / 'imagenes.pdf').exists(): continue
        for u in e.get('imagenes', []):
            try:
                b = baja(u)
                if b[:4] != b'%PDF': raise ValueError('no es un PDF')
                (d / 'imagenes.pdf').write_bytes(b); print(f'{ys} imágenes OK ({len(b) // 1024} KB) ← {u}')
                o = d / 'origen.txt'
                if o.exists(): o.write_text(o.read_text(encoding='utf-8').rstrip('\n') + f'\nimagenes: {u}\n', encoding='utf-8')
                break
            except Exception as ex: print(f'{ys} imágenes ✕ {u}: {ex}')


def main():
    F = json.loads((R / 'data' / 'fuentes_externas.json').read_text(encoding='utf-8'))
    usadas = {l.split(': ', 1)[1].strip() for o in RAW.glob('20*/origen.txt') for l in o.read_text(encoding='utf-8').splitlines() if l.startswith('plantilla: ')}
    for c in F.get('_carpetas_drive', []):
        fid = c['id'] if isinstance(c, dict) else c
        try:
            for (y, tp), us in carpeta_drive(fid, c.get('desfase', 1) if isinstance(c, dict) else 1).items():
                e = F.setdefault(str(y), {'cuaderno': [], 'plantilla': []}); e[tp] = us + e.get(tp, [])
        except Exception as ex: print('  Drive: error al leer la carpeta', fid, ex)
    cp = pathlib.Path('/tmp/cosecha.json')   # candidatos de la cosecha (scripts/rfir_cosecha.py), detrás de los de cada año
    if cp.exists():
        C = json.loads(cp.read_text(encoding='utf-8')); ORIG.update(C.pop('_origen', {}))
        for ys, e in C.items():
            f = F.setdefault(ys, {'cuaderno': [], 'plantilla': []})
            for tp in ('cuaderno', 'plantilla', 'plantilla_dudosa'):
                dst = 'plantilla' if tp == 'plantilla_dudosa' else tp
                nuevos = [u for u in e.get(tp, []) if u not in f.get(dst, [])]
                if tp == 'plantilla_dudosa': DUDOSAS.update(nuevos)
                f[dst] = f.get(dst, []) + nuevos
    if '--imagenes' in sys.argv: return imagenes(F)
    resumen = []
    for ys, e in F.items():
        if not ys.isdigit(): continue
        y = int(ys); d = RAW / ys
        if (d / 'respuestas.json').exists(): continue            # ya está del portal oficial
        qs = None; origen = []; VERC = '0'
        if (d / 'cuaderno.txt').exists():
            qs, nopt = M.mejor_cuaderno((d / 'cuaderno.txt').read_text(encoding='utf-8'))
            v0 = re.search(r'versi[oó]n\s*[:\-]?\s*(\d)', (d / 'cuaderno.txt').read_text(encoding='utf-8')[:1500], re.I); VERC = v0.group(1) if v0 else '0'
        for pasada in (0, 1):
            if pasada and qs: break
            for u in ([] if qs and len(qs) >= 0.9 * (anunciadas((d / 'cuaderno.txt').read_text(encoding='utf-8')) or ESPERADAS(y)) else e.get('cuaderno', [])):
                try:
                    b = baja(u); tx, tipo = texto_de(b, u)
                    if tipo != 'pdf': raise ValueError('no es un PDF')
                    if not re.search(r'fisic|radiof', unicodedata.normalize('NFD', tx[:1500].lower()).encode('ascii', 'ignore').decode()): raise ValueError('la portada no menciona FÍSICA')
                    ver = re.search(r'versi[oó]n\s*[:\-]?\s*(\d)', tx[:1500], re.I)
                    if ver and ver.group(1) != '0' and pasada == 0: raise ValueError(f'es la versión {ver.group(1)}: se prueba después, si no aparece la versión 0')
                    ya = anio_examen(tx)
                    if ya and ya != y: raise ValueError(f'el propio cuaderno dice que es del RFIR {ya}')
                    q2, nopt = M.mejor_cuaderno(tx); esp = anunciadas(tx) or ESPERADAS(y)
                    if len(q2) < 0.9 * esp:
                        port = re.search(r'.{0,60}preguntas.{0,60}', tx[:3000].replace('\n', ' '))
                        raise ValueError(f"solo {len(q2)} preguntas de {esp} ({nopt} opciones, última nº {max([q['n'] for q in q2] or [0])}); portada: «{port.group(0) if port else '—'}»; final: «{tx[-200:].replace(chr(10), ' / ')}»")
                    VERC = ver.group(1) if ver else '0'; d.mkdir(parents=True, exist_ok=True); (d / 'cuaderno.pdf').write_bytes(b); (d / 'cuaderno.txt').write_text(tx, encoding='utf-8'); qs = q2
                    origen.append('cuaderno: ' + ORIG.get(u, u)); print(f'{y} cuaderno OK ({len(q2)} preg., {nopt} opciones) ← {u}'); break
                except Exception as ex: print(f'{y} cuaderno ✕ {u}: {ex}')
        if not qs: resumen.append(f'{y}: sin cuaderno válido'); continue
        if not (d / 'plantilla.txt').exists():
            nmax = max(q['n'] for q in qs)
            for u in e.get('plantilla', []):
                try:
                    b = baja(u); tx, tipo = texto_de(b, u, columnas=False)
                    if tipo == 'html': i = tx.lower().find('respuesta'); tx = tx[i:] if i >= 0 else tx
                    if tipo == 'pdf' and len(tx.strip()) < 200: raise ValueError('PDF escaneado sin texto: no se lee para no arriesgar respuestas mal leídas')
                    if not plantilla_del_anio(tx, y): raise ValueError('la plantilla menciona otros años')
                    if ORIG.get(u, u) in usadas: raise ValueError('esta plantilla ya se usó para otro año')
                    r = M.parse_plantilla(tx, nmax, nopt)
                    cubre = sum(1 for q in qs if q['n'] in r); anul = sum(1 for q in qs if r.get(q['n']) == 0)
                    if cubre < 0.9 * len(qs): raise ValueError(f"respuestas para {cubre} de {len(qs)}; inicio del texto: «{tx[:700].replace(chr(10), ' / ')}»")
                    if anul > (25 if nmax > 240 else 15): raise ValueError(f'{anul} anuladas: la tabla no se ha leído bien (lo normal son menos de 10; en los exámenes de 260 preguntas, algo más)')
                    vp = re.search(r'versi[oó]n(?:\s+de\s+examen)?\s*:?\s*(\d)', tx[:800], re.I)
                    if VERC != '0' and vp and vp.group(1) != VERC: raise ValueError(f'plantilla de la versión {vp.group(1)} y el cuaderno es de la versión {VERC}')
                    conc = concordancia(qs, r, nopt)
                    if conc is None and u in DUDOSAS: raise ValueError('plantilla sin año en su texto y sin clave de IA para comprobar que es de este examen')
                    if conc is not None and conc < 0.6: raise ValueError(f'la IA solo coincide con ella en el {conc:.0%} de las preguntas: no es la plantilla de este examen')
                    (d / 'plantilla.txt').write_text(tx, encoding='utf-8')
                    if tipo == 'pdf': (d / 'plantilla.pdf').write_bytes(b)
                    usadas.add(ORIG.get(u, u)); origen.append('plantilla: ' + ORIG.get(u, u)); print(f'{y} plantilla OK ({cubre}/{len(qs)}, anuladas {sum(1 for v in r.values() if v == 0)}' + (f', la IA coincide en el {conc:.0%}' if conc is not None else '') + f') ← {ORIG.get(u, u)}'); break
                except Exception as ex: print(f'{y} plantilla ✕ {u}: {ex}')
        if origen:   # se añade a lo que ya hubiera (el cuaderno puede venir de una ejecución anterior)
            prev = [l for l in ((d / 'origen.txt').read_text(encoding='utf-8').splitlines() if (d / 'origen.txt').exists() else []) if l.startswith(('cuaderno: ', 'plantilla: '))]
            (d / 'origen.txt').write_text('Copia de terceros del documento oficial del Ministerio de Sanidad\n' + '\n'.join(dict.fromkeys(prev + origen)) + '\n', encoding='utf-8')
        resumen.append(f"{y}: cuaderno {'sí' if qs else 'no'} · plantilla {'sí' if (d / 'plantilla.txt').exists() else 'NO'}")
    print('\n'.join(resumen))


if __name__ == '__main__':
    main()
