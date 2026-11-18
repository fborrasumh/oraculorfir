#!/usr/bin/env python3
"""OráculoRFIR · clasificación de las preguntas por asignatura con IA (opcional; mejora mucho a las palabras clave).

Se ejecuta en GitHub Actions si existe el secreto OPENAI_API_KEY (modelo por defecto: gpt-6-luna) o, si no, ANTHROPIC_API_KEY.
    OPENAI_API_KEY=... python3 scripts/rfir_clasifica_ia.py        (MODELO_IA=… para otro modelo)
Guarda el resultado en data/clasificacion_ia.json ({id: asignatura}) y solo clasifica las preguntas que aún no estén ahí,
así que cada ejecución cuesta solo lo nuevo. El código comprueba que cada etiqueta sea una asignatura válida;
lo que no lo sea se ignora y esa pregunta se queda con la clasificación por palabras clave."""
import json, os, sys, time, pathlib, urllib.request, urllib.error

R = pathlib.Path(__file__).resolve().parent.parent
DATA, CACHE = R / 'data' / 'rfir.json', R / 'data' / 'clasificacion_ia.json'
OPENAI = bool(os.environ.get('OPENAI_API_KEY'))
MODELO = os.environ.get('MODELO_IA') or ('gpt-6-luna' if OPENAI else 'claude-haiku-4-5-20251001')
LOTE = 25


def _post(url, body, headers):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={'content-type': 'application/json', **headers})
    try:
        with urllib.request.urlopen(req, timeout=180) as r: return 200, json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code, e.read().decode('utf-8', 'ignore')[:400]


def llama(prompt, key):
    for k in range(5):
        if OPENAI:
            # los modelos nuevos de OpenAI piden max_completion_tokens y no aceptan temperature; si rechazan un parámetro, se quita
            body = {'model': MODELO, 'messages': [{'role': 'user', 'content': prompt}], 'max_completion_tokens': 6000, 'reasoning_effort': 'low', 'response_format': {'type': 'json_object'}}
            for _ in range(3):
                st, r = _post('https://api.openai.com/v1/chat/completions', body, {'Authorization': 'Bearer ' + key})
                if st == 400 and 'reasoning_effort' in str(r) and 'reasoning_effort' in body: body.pop('reasoning_effort'); continue
                if st == 400 and 'response_format' in str(r) and 'response_format' in body: body.pop('response_format'); continue
                break
            if st == 200: return r['choices'][0]['message']['content'] or ''
        else:
            st, r = _post('https://api.anthropic.com/v1/messages', {'model': MODELO, 'max_tokens': 2500, 'messages': [{'role': 'user', 'content': prompt}]}, {'x-api-key': key, 'anthropic-version': '2023-06-01'})
            if st == 200: return ''.join(b.get('text', '') for b in r['content'])
        if st in (401, 403, 404): raise SystemExit(f'Error {st} del proveedor (clave o modelo «{MODELO}»): {r}')
        print(f'  reintento tras error {st}: {str(r)[:200]}'); time.sleep(5 * (k + 1))
    raise RuntimeError('el proveedor no responde')


def main():
    key = os.environ.get('OPENAI_API_KEY') or os.environ.get('ANTHROPIC_API_KEY')
    if not key: print('Sin OPENAI_API_KEY ni ANTHROPIC_API_KEY: se mantiene la clasificación por palabras clave.'); return 0
    d = json.loads(DATA.read_text(encoding='utf-8'))
    asigs = [a for a in d['asignaturas'] if a['id'] != 'otras']; validas = {a['id'] for a in asigs}
    cache = json.loads(CACHE.read_text(encoding='utf-8')) if CACHE.exists() else {}
    pend = [q for q in d['preguntas'] if q['id'] not in cache]
    print(f"{len(pend)} preguntas por clasificar con {MODELO} ({'OpenAI' if OPENAI else 'Anthropic'})")
    lista = '\n'.join(f"{a['id']}: {a['nombre']}" for a in asigs)
    for i in range(0, len(pend), LOTE):
        lote = pend[i:i + LOTE]
        prompt = (f'Clasifica cada pregunta del examen RFIR en la asignatura de la que depende la respuesta (no la de los antecedentes del caso). '
                  f'Usa SOLO estos identificadores:\n{lista}\n\nDevuelve SOLO un objeto JSON {{"id_pregunta": "id_asignatura", ...}}.\n\n'
                  + '\n\n'.join(f"[{q['id']}] {q['enunciado'][:700]}\n" + '\n'.join(f'{k + 1}. {o[:200]}' for k, o in enumerate(q['opciones'])) for q in lote))
        try:
            tx = llama(prompt, key); j = json.loads(tx[tx.index('{'):tx.rindex('}') + 1])
            for q in lote:
                v = str(j.get(q['id'], '')).strip()
                if v in validas: cache[q['id']] = v
        except Exception as e: print('lote con error:', e)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True), encoding='utf-8')
        print(f'  {min(i + LOTE, len(pend))}/{len(pend)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
