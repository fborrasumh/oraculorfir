#!/usr/bin/env python3
"""OráculoRFIR · cosecha de exámenes antiguos (anteriores a los del portal) en webs y paquetes .zip de terceros.
Se ejecuta en GitHub Actions (allí hay red):  python3 scripts/rfir_cosecha.py
Lee «_cosecha» de data/fuentes_externas.json:
  · "sitios": webs dedicadas que se recorren (y sus subpáginas de exámenes) en busca de enlaces a .pdf y .zip;
  · "paginas": noticias sueltas de las que solo se toman sus enlaces a .pdf y .zip;
  · "ficheros": enlaces directos a .pdf o .zip;
  · "wayback": patrones de URL de webs desaparecidas cuyos .pdf/.zip se buscan en la Wayback Machine (archive.org).
Descarga cada fichero, abre los .zip y mira DENTRO de cada PDF qué es:
  · cuaderno: su portada es de Física y dice «PRUEBAS SELECTIVAS AAAA» (examen de enero de AAAA+1);
  · plantilla: tiene una tabla de respuestas legible; el año sale de su texto o, si no lo dice, del nombre del fichero.
El resultado (candidatos por año) va a /tmp/cosecha.json; rfir_externos.py lo usa después y hace las comprobaciones de siempre
(año del propio cuaderno, versión 0, preguntas anunciadas, plantilla que cubra el 90 %, no repetir plantilla)."""
import io, json, re, sys, html, hashlib, pathlib, zipfile, urllib.parse, urllib.request, unicodedata
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
    vistas, ficheros, cola = set(), {}, [(p, 0) for p in sitios] + [(p, 1) for p in paginas]
    while cola and len(vistas) < MAX_PAGINAS:
        u, prof = cola.pop(0)
        if u in vistas: continue
        vistas.add(u)
        try: t = X.baja(u).decode('utf-8', 'ignore')
        except Exception as e: print('  página ✕', u, e); continue
        ls = enlaces(u, t); nf = 0
        for l in sorted(ls):
            if es_fichero(l):
                if l not in ficheros: ficheros[l] = u; nf += 1
            elif prof == 0 and urllib.parse.urlparse(l).netloc == urllib.parse.urlparse(u).netloc and re.search(r'exam|cuaderno|respuesta|plantilla|descarg|convocatoria|rfir', l, re.I):
                cola.append((l, 1))
        print(f'  página {u}: {nf} ficheros nuevos')
    return ficheros


def baja_desde(u, pagina=None):
    m = re.search(r'drive\.google\.com/file/d/([\w-]+)', u)
    if m: u = f'https://drive.google.com/uc?export=download&id={m.group(1)}'   # enlace de vista de Drive → descarga
    if 'web.archive.org' in u:   # archive.org corta conexiones si se le pide mucho seguido: reintentos con pausa
        import time
        for k in range(5):
            try: return X.baja(u)
            except Exception as e:
                if k == 4: raise
                print(f'    archive.org: reintento {k + 1} ({e})'); time.sleep(8 * (k + 1))
    if not pagina: return X.baja(u)
    req = urllib.request.Request(urllib.parse.quote(u, safe=':/?&=%#'), headers={**X.UA, 'Referer': pagina})
    return X.OP.open(req, timeout=180).read()   # mismo «opener» que al visitar la página: lleva sus cookies


def wayback(patron, filtro=None):
    """PDF y ZIP archivados en la Wayback Machine (archive.org) para un patrón de URL, p. ej. «bir.hol.es/*»: webs ya desaparecidas."""
    q = 'https://web.archive.org/cdx/search/cdx?url=' + urllib.parse.quote(patron, safe='*/:') + '&output=json&filter=statuscode:200&collapse=urlkey&limit=3000'
    try: filas = json.loads(X.baja(q).decode('utf-8', 'ignore') or '[]')
    except Exception as e: print('  wayback ✕', patron, e); return []
    out = [f'https://web.archive.org/web/{f[1]}id_/{f[2]}' for f in filas[1:] if (f[2].lower().split('?')[0].endswith(('.pdf', '.zip')) or 'pdf' in f[3] or 'zip' in f[3])
           and (not filtro or re.search(filtro, f[2], re.I))]
    print(f'  wayback {patron}: {len(out)} ficheros archivados' + (f' que cumplen «{filtro}»' if filtro else ''))
    return out


def pdfs_de(u, pagina=None):
    """[(nombre, bytes)] de un enlace: el propio PDF o los PDF de dentro de un .zip (también .zip dentro de .zip)."""
    b = baja_desde(u, pagina)
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


def clasifica(nombre, b, pagina=''):
    p = TMP / (hashlib.sha1(b).hexdigest()[:16] + '.pdf'); p.write_bytes(b)
    try: tx = M.texto_pdf(str(p), columnas=False)
    except Exception as e: return None, None, f'no se lee ({e})', p
    cab = norm(tx[:1500]); todo = norm(tx)
    if len(tx.strip()) < 200: return None, None, 'escaneado sin texto', p
    ya = X.anio_examen(tx)
    if ya and re.search(r'cuaderno de examen', cab):
        if not PORTADA.search(cab): return None, None, f'cuaderno de otra titulación ({ya})', p
        # algunas copias llevan la hoja de respuestas al final del propio cuaderno: se separa como plantilla de ese año
        cola = tx[int(len(tx) * 0.6):]
        m = None
        for m in re.finditer(r'(respuestas\s+correctas|hoja\s+de\s+respuestas|plantilla|\bV\s+RC\b)', cola, re.I): pass
        if m:
            t2 = cola[m.start():]
            r2 = max(len(M.parse_plantilla(t2, 260, 5) or {}), len(M.parse_plantilla(t2, 260, 4) or {}))
            if r2 >= 150:
                q = p.with_name(p.stem + '-respuestas.txt'); q.write_text(t2, encoding='utf-8')
                return 'cuaderno+plantilla', [ya], f'cuaderno {ya} con sus respuestas al final ({r2})', (p, q)
        return 'cuaderno', [ya], f'cuaderno {ya}', p
    r = M.parse_plantilla(tx, 260, 5) or {}
    r4 = M.parse_plantilla(tx, 260, 4) or {}
    if max(len(r), len(r4)) >= 150:
        if OTRAS.search(cab) and not PORTADA.search(cab): return None, None, 'plantilla de otra titulación', p
        if 'provisional' in todo[:3000] and 'definitiv' not in todo[:3000]: return None, None, 'plantilla provisional', p
        c = re.search(r'convocatoria\s*:?\s*(20\d\d)', todo) or re.search(r'pruebas\s+selectivas[^\d]{0,40}?(20\d\d)', todo)
        if c: return 'plantilla', [int(c.group(1)) + 1], f'plantilla {int(c.group(1)) + 1} (año en el texto)', p
        # sin año en el texto: «dudosa». El año sale del nombre del fichero (examen o convocatoria) o de la noticia que la enlaza,
        # y el validador solo la acepta si la IA, resolviendo preguntas del cuaderno, coincide con ella (X.concordancia)
        nums = sorted({int(a) for a in re.findall(r'(?<!\d)(20[0-2]\d)(?!\d)', nombre)})
        ys = sorted({y for a in nums for y in (a, a + 1)}) or sorted({int(a) for a in re.findall(r'(?<!\d)(20[0-2]\d)(?!\d)', pagina)})
        return ('plantilla_dudosa', ys, f'plantilla dudosa {ys}', p) if ys else (None, None, 'plantilla sin año reconocible', p)
    return None, None, 'no parece cuaderno ni plantilla', p


def main():
    F = json.loads((R / 'data' / 'fuentes_externas.json').read_text(encoding='utf-8'))
    C = F.get('_cosecha', {})
    pag = recorre(C.get('sitios', []), C.get('paginas', []))
    wb = [u for p in C.get('wayback', []) for u in wayback(p, C.get('wayback_filtro'))]
    fich = list(dict.fromkeys(C.get('ficheros', []) + list(pag) + wb))[:MAX_FICHEROS]
    print(f'{len(fich)} ficheros candidatos')
    cand, vistos, orig = {}, set(), {}
    for u in fich:
        try: lista = pdfs_de(u, pag.get(u))
        except Exception as e: print('  ✕', u, e); continue
        for nombre, b in lista:
            h = hashlib.sha1(b).hexdigest()
            if h in vistos: continue
            vistos.add(h)
            tipo, ys, nota, p = clasifica(nombre, b, pag.get(u, ''))
            print(f'  {nombre[:70]:70s} → {nota}   ({u[:90]})')
            if not tipo: continue
            fuente = u if nombre == urllib.parse.unquote(u.split('?')[0].rsplit('/', 1)[-1]) else f'{u} :: {nombre}'
            pares = [('cuaderno', p[0]), ('plantilla', p[1])] if tipo == 'cuaderno+plantilla' else [(tipo, p)]
            for tp, f in pares:
                orig[f.as_uri()] = fuente + (' (respuestas al final del cuaderno)' if f.suffix == '.txt' else '')
                for y in ys:
                    e = cand.setdefault(str(y), {'cuaderno': [], 'plantilla': [], 'plantilla_dudosa': []})
                    # los que llevan el año en el texto, primero
                    (e[tp].insert(0, f.as_uri()) if len(ys) == 1 else e[tp].append(f.as_uri()))
    pathlib.Path('/tmp/cosecha.json').write_text(json.dumps({**cand, '_origen': orig}, indent=1), encoding='utf-8')
    print('\nResumen de la cosecha:')
    for y in sorted(cand, key=int): print(f"  {y}: {len(cand[y]['cuaderno'])} cuadernos, {len(cand[y]['plantilla'])} plantillas con año, {len(cand[y]['plantilla_dudosa'])} dudosas")


if __name__ == '__main__':
    main()
