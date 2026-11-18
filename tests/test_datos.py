#!/usr/bin/env python3
"""Pruebas del paso PDF → preguntas con textos que imitan los cuadernos y plantillas oficiales (preguntas ficticias).
    python3 tests/test_datos.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'scripts'))
import rfir_datos as M

CUADERNO = """MINISTERIO DE SANIDAD
PRUEBAS SELECTIVAS 2026
CUADERNO DE EXAMEN
1. Compruebe que este cuaderno lleva todas sus páginas.
2. Las respuestas se marcan en la hoja de respuestas.
3. Dispone de 270 minutos.
FÍSICA
1. Pregunta asociada a la imagen 1.
Varón de 64 años con dolor torácico opresivo y elevación del ST
en derivaciones inferiores. ¿Cuál es la actitud más adecuada?
1. Angioplastia primaria.
2. Observación.
3. Alta con
antiagregación.
4. Ecocardiograma diferido.
- 1 -
2. Niño de 8 meses con bronquiolitis. ¿Qué tratamiento es de elección?
1. Medidas de soporte.
2. Corticoides.
3. Antibiótico.
4. Salbutamol sistemático.
3. En un ensayo clínico, la sensibilidad de una prueba es:
1. Verdaderos positivos entre enfermos.
2. Verdaderos negativos entre sanos.
3. 2 mg/kg.
4. Ninguna.
4. Mujer embarazada de 32 semanas con preeclampsia grave. Señale la correcta:
1. Sulfato de magnesio.
2. Esperar.
3. Diuréticos.
4. Ninguna.
"""
PLANTILLA_PAREJAS = """RESPUESTAS CORRECTAS DEFINITIVAS
1 1 3 1
2 1 4 1
"""
PLANTILLA_VERSIONES = """Pregunta V0 V1 V2 V3 V4
1 1 2 3 4 1
2 1 3 3 2 2
3 ANULADA ANULADA ANULADA ANULADA ANULADA
4 1 1 1 1 1
"""

ok = True
def check(nombre, cond, extra=''):
    global ok; ok &= bool(cond); print(('✓' if cond else '✕'), nombre, extra)

qs, nopt = M.mejor_cuaderno(CUADERNO)
check('se saltan las instrucciones numeradas de la portada y salen las 4 preguntas', [q['n'] for q in qs] == [1, 2, 3, 4], str([(q['n'], q['enunciado'][:30]) for q in qs]))
check('4 opciones detectadas', nopt == 4)
check('el enunciado de varias líneas se une', 'elevación del ST en derivaciones inferiores' in qs[0]['enunciado'])
check('la opción partida en dos líneas se une', qs[0]['opciones'][2] == 'Alta con antiagregación.', qs[0]['opciones'][2])
check('el número de página no se cuela', all('- 1 -' not in o for o in qs[0]['opciones']))
check('pregunta con imagen marcada', qs[0]['imagen'] and not qs[1]['imagen'])
check('«2 mg/kg» dentro de una opción no rompe nada', qs[2]['opciones'][2] == '2 mg/kg.')
A = M.parse_plantilla(PLANTILLA_PAREJAS, 4, 4); check('plantilla en parejas', A == {1: 1, 3: 1, 2: 1, 4: 1}, str(A))
B = M.parse_plantilla(PLANTILLA_VERSIONES, 4, 4); check('plantilla por versiones: se toma la versión 0 y la anulada es 0', B == {1: 1, 2: 1, 3: 0, 4: 1}, str(B))
asigs = M.carga_asignaturas()
FIRQ = [{'enunciado': 'Una fuente radiactiva con periodo de semidesintegración de 6 h: ¿qué actividad queda a las 18 h?', 'opciones': ['1/2.', '1/4.', '1/8.', '1/16.']},
        {'enunciado': 'La unidad de dosis absorbida es el gray. ¿Qué detector mide mejor la dosis absorbida en un haz de referencia?', 'opciones': ['Una cámara de ionización.', 'Un contador.', 'Una lente.', 'Un imán.']},
        {'enunciado': '¿Qué interacción de los fotones predomina en tejido blando a energías de megavoltaje: efecto Compton o fotoeléctrico?', 'opciones': ['Efecto Compton.', 'Efecto fotoeléctrico.', 'Producción de pares.', 'Rayleigh.']},
        {'enunciado': 'En tomografía computarizada, ¿cuántas unidades Hounsfield tiene el agua?', 'opciones': ['-1000.', '0.', '100.', '1000.']}]
lab = [M.clasifica(q, asigs)[0] for q in FIRQ]
check('clasificación por palabras clave', lab == ['nuclear', 'dosimetria', 'interaccion', 'radiodiagnostico'], str(lab))
check('sin palabras clave → «otras»', M.clasifica({'enunciado': 'zzz', 'opciones': ['a', 'b']}, asigs) == ('otras', 0.0))
J = [{'V_0': '1', 'RC_0': '3', 'V_1': '43', 'RC_1': '2'}, {'V_0': '2', 'RC_0': ' ', 'V_1': '44', 'RC_1': '1'}]
check('hoja de respuestas JSON del portal: tabla en columnas y anulada en blanco', M.parse_respuestas_json(J) == {1: 3, 43: 2, 2: 0, 44: 1})
H = 'Preguntas de reserva ( 176 - 185 )  176 2 : pregunta 176, respuesta 2\n 10 Anulada : pregunta 10, anulada\n' + ''.join(f' {i} 1 : pregunta {i}, respuesta 1\n' for i in range(1, 120) if i != 10)
r = M.parse_plantilla(H, 185, 4); check('plantilla web con «pregunta N, respuesta R»: el rango «176 - 185» no anula nada', r.get(176) == 2 and r.get(10) == 0 and r.get(11) == 1, str({k: r.get(k) for k in (10, 11, 176)}))
G = 'V RC V RC\n1 5 53 3\n2 3 54 1\n106 158 5\n131 183 3 235 1\n'
r = M.parse_plantilla(G, 260, 5); check('tabla del Ministerio con anulada como hueco («106 158 5»)', r.get(106) == 0 and r.get(158) == 5 and r.get(131) == 0 and r.get(183) == 3 and r.get(53) == 3, str({k: r.get(k) for k in (53, 106, 158, 131, 183, 235)}))
q_sp = M.parse_cuaderno('1. Primera pregunta:\n1. a\n2. b\n3. c\n4. d\n2 La segunda viene sin punto:\n1. a\n2. b\n3. c\n4. d\n3. Tercera:\n1. a\n2. b\n3. c\n4. d\n', 4)
check('errata: número de pregunta sin punto («165 La…»)', [q['n'] for q in q_sp] == [1, 2, 3] and q_sp[1]['enunciado'].startswith('La segunda'), str([q['n'] for q in q_sp]))
q_pie = M.parse_cuaderno('1. Pregunta:\n1. a\n2. b\n3. c\n4. Grave.\n)63/43--0-AÍREMREFNE--(\n32 de 34\nPagina: 33 de 34\n2. Otra:\n1. a\n2. b\n3. c\n4. d\n', 4)
check('pies de página del RFIR 2024 no se cuelan', q_pie[0]['opciones'][3] == 'Grave.', q_pie[0]['opciones'][3])
import rfir_externos as X
check('portada: «225 preguntas más 10 de reserva» → 235', X.anunciadas('integrado por 225 preguntas\nmás 10 de reserva, lleva') == 235 and X.anunciadas('se compone de 175 preguntas más 10 de reserva') == 185)
qi = M.parse_cuaderno('1. Pregunta vinculada a la imagen nº 3. ¿Qué muestra?:\n1. a\n2. b\n3. c\n4. d\n2. El diagnóstico «Trastorno de la imagen corporal» lo presentan:\n1. a\n2. b\n3. c\n4. d\n3. La figura de Florence Nightingale:\n1. a\n2. b\n3. c\n4. d\n', 4)
check('imagen: solo con número («imagen nº 3»), no «imagen corporal» ni «la figura de»', [q['imagen'] for q in qi] == [True, False, False], str([q['imagen'] for q in qi]))
import rfir_fetch as F
check('año del examen: convocatoria 2025-2026 → 2026', F.anio_de('Convocatoria 2025-2026 Física') == 2026 and F.anio_de('RFIR_2019_cuaderno.pdf') == 2019 and F.anio_de('conv 2014/15') == 2015)
check('tipo de documento', F.tipo_de('Cuaderno de examen') == 'cuaderno' and F.tipo_de('Plantilla de respuestas correctas') == 'plantilla' and F.tipo_de('Cuaderno de imágenes') == 'imagenes')
check('titulación: Física sí, Medicina y Enfermería no', F.es_titulacion('FÍSICA cuaderno 2020') and not F.es_titulacion('MEDICINA cuaderno 2020') and not F.es_titulacion('ENFERMERÍA cuaderno 2020'))
c = []; F.anota(c, 'https://x/a.pdf', 'Plantilla provisional de respuestas FÍSICA 2024'); check('plantilla provisional se distingue de la definitiva', c and c[0]['tipo'] == 'plantilla_provisional')
print('\nTODO OK' if ok else '\nHAY FALLOS'); sys.exit(0 if ok else 1)
