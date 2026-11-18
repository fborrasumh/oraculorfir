#!/usr/bin/env python3
"""Cuadernillos de imágenes → data/img/<año>/<nº>.jpg (una por imagen, ancho máx. 1000 px).
Los cuadernillos vienen en folleto (dos páginas por hoja, varias imágenes por página). Para cada imagen incrustada:
  · si hay rótulos «IMAGEN 23» en la hoja, se le asigna el rótulo que tiene justo encima (mismo lado de la hoja);
  · si no hay rótulos, se numeran en orden de lectura por número de página del folleto (abajo) y de arriba abajo.
Comprobación: el número de imágenes obtenidas debe coincidir con la imagen más alta que citan las preguntas de ese año
(data/raw/<año>/cuaderno.txt); si no, el año se descarta y se dice. Requiere pdfplumber, pypdfium2 y Pillow.
    python3 scripts/rfir_imagenes.py [--rehacer]"""
import re, sys, pathlib, shutil, subprocess, tempfile
import pdfplumber, pypdfium2 as pdfium
R = pathlib.Path(__file__).resolve().parent.parent; RAW = R / 'data' / 'raw'; IMG = R / 'data' / 'img'
REF = re.compile(r'imagen(?:es)?\s*(?:n\s*[ºo°.]*\s*)?(\d{1,3})', re.I)


def maximo_citado(anio):
    t = (RAW / anio / 'cuaderno.txt'); t = t.read_text(encoding='utf-8') if t.exists() else ''
    ns = [int(n) for n in REF.findall(t) if 0 < int(n) < 100]
    return max(ns) if ns else 0


def imagenes_de(pdf):
    """[(nº, nº_página_pdf, bbox), …] y el modo usado ('rotulos' u 'orden'). bbox = (x0, top, x1, bottom) en puntos."""
    todas = []
    with pdfplumber.open(pdf) as p:
        for ip, pg in enumerate(p.pages):
            ws = pg.extract_words(); mid = pg.width / 2
            rot = [(int(ws[i + 1]['text'].rstrip(':.')), ws[i]) for i in range(len(ws) - 1) if ws[i]['text'].lower() == 'imagen' and ws[i + 1]['text'].rstrip(':.').isdigit()]   # «IMAGEN 1» o «IMAGEN 1:»
            pags = [(int(w['text']), w) for w in ws if w['text'].isdigit() and w['top'] > pg.height * 0.9]
            ims = [i for i in pg.images if (i['x1'] - i['x0']) > 80 and (i['bottom'] - i['top']) > 40 and (i['x1'] - i['x0']) < pg.width * 0.95]
            for im in ims:
                bb = (im['x0'], im['top'], im['x1'], im['bottom']); lado = bb[0] >= mid - 20
                enc = [(im['top'] - w['bottom'], n) for n, w in rot if w['bottom'] <= im['top'] + 15 and ((w['x0'] >= mid - 20) == lado) and im['top'] - w['bottom'] < 120]
                pn = [n for n, w in pags if (w['x0'] >= mid - 20) == lado]
                todas.append({'rot': min(enc)[1] if enc else None, 'pag': pn[0] if pn else 999, 'top': bb[1], 'ip': ip, 'bb': bb})
    con = [x for x in todas if x['rot'] is not None]
    if todas and len(con) >= 0.8 * len(todas): return [(x['rot'], x['ip'], x['bb']) for x in con], 'rotulos'
    return [(k, x['ip'], x['bb']) for k, x in enumerate(sorted(todas, key=lambda x: (x['pag'], x['top'])), start=1)], 'orden'


def rotulo_interno(im):
    """Número que la propia imagen lleva escrito arriba («Imagen 22»), leído con OCR (tesseract). None si no se lee."""
    w, h = im.size; zona = im.crop((0, 0, w, max(40, int(h * 0.22)))).convert('L')
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f: zona.save(f.name)
    try: tx = subprocess.run(['tesseract', f.name, '-', '--psm', '6'], capture_output=True, text=True, timeout=60).stdout
    except Exception: return None
    m = re.search(r'imagen\s*(?:n\s*[ºo°.]*\s*)?(\d{1,2})\b', tx, re.I)
    return int(m.group(1)) if m else None


def render(doc, ip, bb):
    x0, top, x1, bot = bb; pg = doc[ip]; W, H = pg.get_size(); m = 4
    bm = pg.render(scale=2.2, crop=(max(0, x0 - m), max(0, H - bot - m), max(0, W - x1 - m), max(0, top - m)))
    im = bm.to_pil().convert('RGB')
    return im.resize((1000, round(im.height * 1000 / im.width))) if im.width > 1000 else im


def recorta(pdf, items, dst):
    doc = pdfium.PdfDocument(str(pdf)); dst.mkdir(parents=True, exist_ok=True)
    for n, ip, bb in items: render(doc, ip, bb).save(dst / f'{n}.jpg', 'JPEG', quality=72, optimize=True)


def main():
    rehacer = '--rehacer' in sys.argv
    for pdf in sorted(RAW.glob('20*/imagenes.pdf')):
        anio = pdf.parent.name; dst = IMG / anio
        if dst.exists() and any(dst.glob('*.jpg')) and not rehacer: continue
        if dst.exists(): shutil.rmtree(dst)
        try: items, modo = imagenes_de(pdf)
        except Exception as e: print(f'{anio}: ✕ no se pudo leer ({e})'); continue
        mx = maximo_citado(anio)
        if modo == 'rotulos':   # un rótulo imposible (fuera de 1..mx) se descarta solo él, no el año
            fuera = [n for n, _, _ in items if not 1 <= n <= mx]
            dentro = [x for x in items if 1 <= x[0] <= mx]; faltan = sorted(set(range(1, mx + 1)) - {x[0] for x in dentro})
            if len(fuera) == 1 and len(faltan) == 1:   # errata del cuadernillo (RFIR 2022: «IMAGEN 9999999» es la 9)
                print(f'{anio}: rótulo imposible {fuera[0]} → imagen {faltan[0]}, la única que falta')
                dentro += [(faltan[0], ip, bb) for n, ip, bb in items if n == fuera[0]]
            elif fuera: print(f'{anio}: rótulos fuera de rango ignorados: {fuera}')
            items = dentro
        nums = [n for n, _, _ in items]
        # con rótulos la asignación es fiable: se aceptan aunque falte alguna; por orden, solo si cuadra el total exacto
        if modo == 'orden':   # sin rótulos de texto: el número debe leerse DENTRO de cada imagen; el orden de lectura no basta (falló en 2014)
            doc = pdfium.PdfDocument(str(pdf)); leidos = [(rotulo_interno(render(doc, ip, bb)), ip, bb) for _, ip, bb in items]
            ok = [(n, ip, bb) for n, ip, bb in leidos if n]
            print(f'{anio}: rótulos leídos dentro de las imágenes: {len(ok)} de {len(items)}')
            items = ok; nums = [n for n, _, _ in items]
        valido = items and len(set(nums)) == len(nums) and all(1 <= n <= mx for n in nums) and len(nums) >= 0.8 * mx
        if not valido:
            print(f'{anio}: ✕ descartado ({modo}) · {len(items)} imágenes {sorted(nums)[:40]} · las preguntas citan hasta la {mx}'); continue
        faltan = sorted(set(range(1, mx + 1)) - set(nums))
        recorta(pdf, items, dst); print(f'{anio}: ✓ {len(items)} imágenes de {mx} ({"rótulo de texto" if modo == "rotulos" else "número leído dentro de la imagen"})' + (f' · sin imagen: {faltan}' if faltan else ''))


if __name__ == '__main__':
    main()
