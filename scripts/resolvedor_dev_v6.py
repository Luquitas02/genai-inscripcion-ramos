"""Qué hizo el Resolvedor de la v6 en la corrida de desarrollo y qué habría hecho la regla en código.

    cd scripts && python resolvedor_dev_v6.py <carpeta con el contenido de resultados/v6_desarrollo.zip>
"""
import json
import sys
from collections import Counter, defaultdict

sys.path.insert(0, '.')
from herramientas import buscar_ramo, estado_en_historial, inscribible  # noqa: E402

D = sys.argv[1]
DATOS = {'casos': '../datos/casos.jsonl', 'casos_nuevos': '../datos/casos_nuevos.jsonl',
         'casos_redactados': '../datos/casos_redactados.jsonl',
         'casos_desarrollo': '../datos/casos_desarrollo.jsonl',
         'casos_desarrollo_redactados': '../datos/casos_desarrollo_redactados.jsonl',
         'plantilla_a': '../datos/prueba_v5/plantilla_a.jsonl',
         'plantilla_b': '../datos/prueba_v5/plantilla_b.jsonl',
         'redactados': '../datos/prueba_v5/redactados.jsonl'}
c = Counter()
for s, ruta in DATOS.items():
    casos = [json.loads(l) for l in open(ruta, encoding='utf-8')]
    tr = defaultdict(list)
    for l in open(f'{D}/agentes__Phi-3.5-mini-instruct__v6__{s}.traza.jsonl', encoding='utf-8'):
        m = json.loads(l)
        tr[str(m['caso'])].append(m)
    for l in open(f'{D}/agentes__Phi-3.5-mini-instruct__v6__{s}.raw.jsonl', encoding='utf-8'):
        r = json.loads(l)
        caso = casos[int(r['id'])]
        h, real = caso['historial'], caso['ramo_objetivo']['codigo']
        msgs = tr[str(r['id'])]
        b = [m for m in msgs if m['de'] == 'resolvedor' and m['contenido'].get('accion') == 'elegir']
        a = next((m for m in msgs if m['de'] == 'interprete' and 'consultado' in m['contenido']), None)
        if r['ramas']['atajo_exacto'] and not b:
            c['atajo'] += 1
            c['atajo_ok'] += r['acierto_ramo']
            continue
        if not b or not a:
            c['sin_eleccion'] += 1
            continue
        c['resolvedor'] += 1
        cod = b[0]['contenido']['codigo']
        est = estado_en_historial(h, cod)
        c['elige_no_inscribible'] += not inscribible(est)
        c['resolvedor_ok_1a'] += cod == real
        cand = buscar_ramo(a['contenido']['consultado'])
        regla = next((x['codigo'] for x in cand if inscribible(estado_en_historial(h, x['codigo']))),
                     cand[0]['codigo'])
        c['regla_ok'] += regla == real
        c['top1_ok'] += cand[0]['codigo'] == real
        c['final_ok'] += r['acierto_ramo']
for k, v in c.items():
    print(k, v)
