"""Mide la fiabilidad del panel de agentes con preguntas oficiales y escribe data/calibracion.json.
Ejecuta el MISMO código de la app (index.html, los mismos prompts) en un Chromium, con la clave del entorno
(OPENAI_API_KEY), que se pasa al navegador en memoria y nunca se escribe en disco.
Uso:  OPENAI_API_KEY=... python3 scripts/rfir_calibracion.py [N]"""
import asyncio, functools, http.server, json, os, pathlib, sys, threading
from playwright.async_api import async_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 100

def sirve():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    h.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

async def main():
    clave = os.environ.get('OPENAI_API_KEY', '').strip()
    if not clave: sys.exit('Falta OPENAI_API_KEY')
    modelo = os.environ.get('MODELO_IA', 'gpt-6-luna')
    srv = sirve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); p = await (await b.new_context(bypass_csp=True)).new_page()   # para poder evaluar desde Playwright
        p.on('console', lambda m: print('[app]', m.text) if m.type == 'error' else None)
        await p.add_init_script(f"localStorage.setItem('ia_openai_key', {json.dumps(clave)}); localStorage.setItem('miapp_prov', 'openai'); localStorage.setItem('miapp_model_openai', {json.dumps(modelo)});")
        await p.goto(f'http://127.0.0.1:{srv.server_port}/index.html')
        await p.wait_for_function('typeof DATA !== "undefined" && DATA.preguntas && DATA.preguntas.length > 1000', timeout=60000)
        await p.expose_function('avance', lambda i, n: print(f'  {i}/{n}', flush=True))
        r = await p.evaluate(f'calibra({N}, "", (i, n) => window.avance(i, n))')
        await b.close()
    filas = r.pop('filas', [])
    (ROOT / 'data' / 'calibracion.json').write_text(json.dumps(r, ensure_ascii=False, indent=1))
    (ROOT / 'data' / 'calibracion_filas.json').write_text(json.dumps(filas, ensure_ascii=False))
    pc = lambda x: '–' if x is None else f'{round(x * 100)} %'
    resumen = (f"## Medición del panel ({r['n']} preguntas oficiales, {r['prov']} {r.get('modelo', '')})\n\n"
               "| Método | Acepta con la respuesta buena | Deja pasar una respuesta errónea |\n|---|---|---|\n"
               + ''.join(f"| {nom} | {pc(r[k]['ta'])} | {pc(r[k]['fa'])} |\n" for k, nom in (('A', 'Solo 2 resolutores'), ('B', '+ Contradictor'), ('C', 'Panel completo'), ('D', 'Panel completo + dudosas')) if k in r) +
               f"\nAcierto resolutor 1: {pc(r['acierto1'])} · resolutor 2: {pc(r['acierto2'])} · acuerdo: {pc(r['acuerdo'])} · acierto cuando coinciden: {pc(r['precisionAcuerdo'])}\n")
    print(resumen)
    if os.environ.get('GITHUB_STEP_SUMMARY'): open(os.environ['GITHUB_STEP_SUMMARY'], 'a').write(resumen)

asyncio.run(main())
