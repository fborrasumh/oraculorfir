#!/usr/bin/env python3
"""Estructuras químicas y figuras DENTRO del cuaderno del RFIR (no hay cuadernillo de imágenes aparte).
Las estructuras vienen dibujadas con líneas y curvas (gráficos vectoriales) o como imágenes incrustadas, así que el
texto extraído pierde el dibujo y la pregunta no se puede contestar. Para cada pregunta cuya zona de la página
(desde su número hasta el de la siguiente, en la misma columna) contiene un dibujo, se guarda esa zona entera como
imagen: data/img/<año>/q<nº>.jpg. rfir_datos.py la enlaza a la pregunta (campo «img»).
    python3 scripts/rfir_figuras.py [años…] [--rehacer]"""
import re, sys, shutil, pathlib
import pdfplumber, pypdfium2 as pdfium
R = pathlib.Path(__file__).resolve().parent.parent; RAW = R / 'data' / 'raw'; IMG = R / 'data' / 'img'
NUM = re.compile(r'^(\d{1,3})\.$')


def marcas(pg):
    """Dibujos de la página: curvas, líneas cortas y rectángulos pequeños, e imágenes incrustadas (bbox en puntos)."""
    W = pg.width; m = []
    for c in pg.curves: m.append((c['x0'], c['top'], c['x1'], c['bottom']))
    for l in pg.lines:
        if abs(l['x1'] - l['x0']) < W * 0.4 and abs(l['bottom'] - l['top']) < pg.height * 0.3: m.append((l['x0'], l['top'], l['x1'], l['bottom']))
    for i in pg.images:
        if 20 < i['x1'] - i['x0'] < W * 0.9: m.append((i['x0'], i['top'], i['x1'], i['bottom']))
    return m


def zonas(pg, nmax):
    """[(nº, col, top, bottom)] de cada pregunta de la página, por columnas (izquierda/derecha)."""
    mid = pg.width / 2; ws = pg.extract_words(keep_blank_chars=False)
    ini = []
    for w in ws:
        m = NUM.match(w['text'])
        if not m or not 1 <= int(m.group(1)) <= nmax: continue
        col = 0 if w['x0'] < mid - 10 else 1
        izq = min((x['x0'] for x in ws if (x['x0'] < mid - 10) == (col == 0) and abs(x['top'] - w['top']) < 3), default=w['x0'])
        if w['x0'] - izq < 4: ini.append((int(m.group(1)), col, w['top']))   # el número abre la línea
    out = []
    for col in (0, 1):
        L = sorted([x for x in ini if x[1] == col], key=lambda x: x[2])
        for k, (n, _, top) in enumerate(L):
            bot = L[k + 1][2] - 2 if k + 1 < len(L) else pg.height * 0.94
            out.append((n, col, top - 3, bot))
    return out


def figuras(pdf, nmax):
    """{nº: (índice de página, bbox de la zona de la pregunta)} para las preguntas con dibujo."""
    res = {}
    with pdfplumber.open(pdf) as p:
        for ip, pg in enumerate(p.pages):
            if ip == 0: continue   # portada
            mk = marcas(pg)
            if len(mk) < 3: continue
            mid = pg.width / 2
            for n, col, top, bot in zonas(pg, nmax):
                x0, x1 = (0, mid) if col == 0 else (mid, pg.width)
                dentro = [b for b in mk if b[0] >= x0 - 5 and b[2] <= x1 + 5 and b[1] >= top and b[3] <= bot]
                area = sum((b[2] - b[0]) * (b[3] - b[1]) for b in dentro)
                if len(dentro) >= 6 or any((b[2] - b[0]) * (b[3] - b[1]) > 1500 for b in dentro) or area > 2500:
                    res[n] = (ip, (x0 + 4, top, x1 - 4, bot))
    return res


def guarda(pdf, figs, dst):
    doc = pdfium.PdfDocument(str(pdf)); dst.mkdir(parents=True, exist_ok=True)
    for n, (ip, (x0, top, x1, bot)) in figs.items():
        pg = doc[ip]; W, H = pg.get_size()
        im = pg.render(scale=2.4, crop=(max(0, x0), max(0, H - bot), max(0, W - x1), max(0, top))).to_pil().convert('RGB')
        if im.width > 1000: im = im.resize((1000, round(im.height * 1000 / im.width)))
        im.save(dst / f'q{n}.jpg', 'JPEG', quality=78, optimize=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]; rehacer = '--rehacer' in sys.argv
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent)); import rfir_datos as M
    for d in sorted(RAW.glob('20*')):
        if args and d.name not in args: continue
        pdf = d / 'cuaderno.pdf'
        if not pdf.exists() or not (d / 'cuaderno.txt').exists(): continue
        dst = IMG / d.name
        if any(dst.glob('q*.jpg')) and not rehacer: continue
        for f in dst.glob('q*.jpg'): f.unlink()
        qs, _ = M.mejor_cuaderno((d / 'cuaderno.txt').read_text(encoding='utf-8'))
        try: figs = figuras(pdf, max(q['n'] for q in qs))
        except Exception as e: print(f'{d.name}: ✕ no se pudo leer ({e})'); continue
        guarda(pdf, figs, dst)
        print(f'{d.name}: {len(figs)} preguntas con figura {sorted(figs)}')


if __name__ == '__main__':
    main()
