#!/usr/bin/env python3
"""OráculoRFIR · cosecha de exámenes antiguos (anteriores a los del portal) en webs y paquetes .zip de terceros.
Se ejecuta en GitHub Actions (allí hay red):  python3 scripts/rfir_cosecha.py
Lee «_cosecha» de data/fuentes_externas.json:
  · "sitios": webs dedicadas que se recorren (y sus subpáginas de exámenes) en busca de enlaces a .pdf y .zip;
  · "paginas": noticias sueltas de las que solo se toman sus enlaces a .pdf y .zip;
  · "ficheros": enlaces directos a .pdf o .zip.
Descarga cada fichero, abre los .zip y mira DENTRO de cada PDF qué es:
  · cuaderno: su portada es de Física y dice «PRUEBAS SELECTIVAS AAAA» (examen de enero de AAAA+1);
  · plantilla: tiene una tabla de respuestas legible; el año sale de su texto o, si no lo dice, del nombre del fichero.
El resultado (candidatos por año) va a /tmp/cosecha.json; rfir_externos.py lo usa después y hace las comprobaciones de siempre
(año del propio cuaderno, versión 0, preguntas anunciadas, plantilla que cubra el 90 %, no repetir plantilla)."""
import io, json, re, sys, html, hashlib, pathlib, zipfile, urllib.parse, unicodedata
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import rfir_externos as X
import rfir_datos as M
R = pathlib.Path(__file__).resolve().parent.parent
TMP = pathlib.Path('/tmp/cosecha'); TMP.mkdir(parents=True, exist_ok=True)
PORTADA = re.compile(r'fisic|radiof')
OTRAS = re.compile(r'\b(medicina|medicos|enfermeria|farmacia|farmaceuticos|psicologia|psicologos|biologia|biologos|quimica|quimicos)\b')
MAX_PAGINAS, MAX_FICHEROS = 80, 250


def norm(t): return unicodedata.normalize('NFD', t.lower()).encode('ascii', 'ignore').decode()


def enlaces(url, txt):
    out = set()
    for h in re.findall(r'''href\s*=\s*["']([^"'#]+)''', txt, re.I):
        u = urllib.parse.urljoin(url, html.unescape(h.strip()))
        if u.startswith('http'): out.add(u)
    return out


def es_fichero(u):
    l = u.lower().split('?')[0]
    return l.endswith(('.pdf', '.zip')) or '/descargas/' in l or 'drive.google.com/uc' in l or 'drive.google.com/file/d/' in l


def recorre(sitios, paginas):
    """«sitios»: webs dedicadas, se recorren con sus subpáginas de exámenes (un nivel); «paginas»: noticias sueltas, solo sus enlaces."""
    vistas, ficheros, cola = set(), [], [(p, 0) for p in sitios] + [(p, 1) for p in paginas]
    while cola and len(vistas) < MAX_PAGINAS:
        u, prof = cola.pop(0)
        if u in vistas: continue
        vistas.add(u)
        try: t = X.baja(u).decode('utf-8', 'ignore')
        except Exception as e: print('  página ✕', u, e); continue
        ls = enlaces(u, t); nf = 0
        for l in sorted(ls):
            if es_fichero(l):
                if l not in ficheros: ficheros.append(l); nf += 1
            elif prof == 0 and urllib.parse.urlparse(l).netloc == urllib.parse.urlparse(u).netloc and re.search(r'exam|cuaderno|respuesta|plantilla|descarg|convocatoria|rfir', l, re.I):
                cola.append((l, 1))
        print(f'  página {u}: {nf} ficheros nuevos')
    return ficheros


def pdfs_de(u):
    """[(nombre, bytes)] de un enlace: el propio PDF o los PDF de dentro de un .zip (también .zip dentro de .zip)."""
    b = X.baja(u)
    if b[:4] == b'%PDF': return [(urllib.parse.unquote(u.split('?')[0].rsplit('/', 1)[-1]), b)]
    if b[:2] == b'PK':
        out, pila = [], [(u.rsplit('/', 1)[-1], b)]
        while pila:
            nom, zb = pila.pop()
            with zipfile.ZipFile(io.BytesIO(zb)) as z:
                for i in z.infolist():
                    n = i.filename
                    try: n = n.encode('cp437').decode('utf-8')
                    except Exception: pass
                    if i.file_size > 60_000_000: continue
                    d = z.read(i)
                    if d[:4] == b'%PDF': out.append((n, d))
                    elif d[:2] == b'PK': pila.append((n, d))
        return out
    raise ValueError('ni PDF ni ZIP (' + b[:60].decode('utf-8', 'ignore').strip().replace('\n', ' ') + ')')


def clasifica(nombre, b):
    p = TMP / (hashlib.sha1(b).hexdigest()[:16] + '.pdf'); p.write_bytes(b)
    try: tx = M.texto_pdf(str(p), columnas=False)
    except Exception as e: return None, None, f'no se lee ({e})', p
    cab = norm(tx[:1500]); todo = norm(tx)
    if len(tx.strip()) < 200: return None, None, 'escaneado sin texto', p
    ya = X.anio_examen(tx)
    if ya and re.search(r'cuaderno de examen', cab):
        if not PORTADA.search(cab): return None, None, f'cuaderno de otra titulación ({ya})', p
        return 'cuaderno', [ya], f'cuaderno {ya}', p
    r = M.parse_plantilla(tx, 260, 5) or {}
    r4 = M.parse_plantilla(tx, 260, 4) or {}
    if max(len(r), len(r4)) >= 150:
        if OTRAS.search(cab) and not PORTADA.search(cab): return None, None, 'plantilla de otra titulación', p
        if 'provisional' in todo[:3000] and 'definitiv' not in todo[:3000]: return None, None, 'plantilla provisional', p
        c = re.search(r'convocatoria\s*:?\s*(20\d\d)', todo) or re.search(r'pruebas\s+selectivas\s+(20\d\d)', todo)
        if c: ys = [int(c.group(1)) + 1]
        else:
            nums = sorted({int(a) for a in re.findall(r'(?<!\d)(20[0-2]\d)(?!\d)', nombre)})
            ys = sorted({y for a in nums for y in (a, a + 1)})   # el nombre puede llevar el año del examen o el de la convocatoria
        return ('plantilla', ys, f'plantilla {ys or "sin año"}', p) if ys else (None, None, 'plantilla sin año reconocible', p)
    return None, None, 'no parece cuaderno ni plantilla', p


def main():
    F = json.loads((R / 'data' / 'fuentes_externas.json').read_text(encoding='utf-8'))
    C = F.get('_cosecha', {})
    fich = list(dict.fromkeys(C.get('ficheros', []) + recorre(C.get('sitios', []), C.get('paginas', []))))[:MAX_FICHEROS]
    print(f'{len(fich)} ficheros candidatos')
    cand, vistos, orig = {}, set(), {}
    for u in fich:
        try: lista = pdfs_de(u)
        except Exception as e: print('  ✕', u, e); continue
        for nombre, b in lista:
            h = hashlib.sha1(b).hexdigest()
            if h in vistos: continue
            vistos.add(h)
            tipo, ys, nota, p = clasifica(nombre, b)
            print(f'  {nombre[:70]:70s} → {nota}   ({u[:90]})')
            if not tipo: continue
            orig[p.as_uri()] = u if nombre == urllib.parse.unquote(u.split('?')[0].rsplit('/', 1)[-1]) else f'{u} :: {nombre}'
            for y in ys:
                e = cand.setdefault(str(y), {'cuaderno': [], 'plantilla': []})
                # los que llevan el año en el texto, primero
                (e[tipo].insert(0, p.as_uri()) if len(ys) == 1 else e[tipo].append(p.as_uri()))
    pathlib.Path('/tmp/cosecha.json').write_text(json.dumps({**cand, '_origen': orig}, indent=1), encoding='utf-8')
    print('\nResumen de la cosecha:')
    for y in sorted(cand, key=int): print(f"  {y}: {len(cand[y]['cuaderno'])} cuadernos, {len(cand[y]['plantilla'])} plantillas")


if __name__ == '__main__':
    main()
