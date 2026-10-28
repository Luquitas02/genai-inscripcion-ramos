"""Dónde podría aportar un Resolvedor y un Verificador rediseñados, en los 330 de prueba de la v4.

Lee las trazas del sistema completo (primer mensaje del Intérprete y primer T1) y la fila de
resultados. Corre desde la raíz de deliverable-1.
"""
import json
import sys
from collections import Counter, defaultdict

sys.path.insert(0, 'scripts')
from herramientas import buscar_ramo  # noqa: E402

SETS = ['casos', 'casos_nuevos', 'casos_redactados', 'plantilla_a', 'plantilla_b', 'redactados']
MODO = sys.argv[1] if len(sys.argv) > 1 else 'resumen'

tot = Counter()
detalle = []
for s in SETS:
    trazas = defaultdict(list)
    for l in open(f'trazas/agentes__Phi-3.5-mini-instruct__completo__{s}.jsonl', encoding='utf-8'):
        m = json.loads(l)
        trazas[str(m['caso'])].append(m)
    for l in open(f'resultados/agentes__Phi-3.5-mini-instruct__completo__{s}.raw.jsonl', encoding='utf-8'):
        r = json.loads(l)
        msgs = trazas[str(r['id'])]
        a = next((m for m in msgs if m['de'] == 'interprete' and m['tipo'] == 'agente'), None)
        real = r['ramo_objetivo']['codigo']
        if not a or 'consultado' not in a['contenido']:
            tot['sin_mencion'] += 1
            continue
        men = a['contenido']['consultado']
        c = buscar_ramo(men)
        exacta = c[0]['similitud'] >= 1.5
        top1ok = c[0]['codigo'] == real
        en5 = real in [x['codigo'] for x in c]
        clase = ('exacta' if exacta else 'no_exacta',
                 'top1_ok' if top1ok else ('en_top5' if en5 else 'fuera_top5'))
        tot[clase] += 1
        tot[clase + ('final_ok' if r['acierto_ramo'] else 'final_mal',)] += 1
        rech = r['ramas']['rechazos_verificador']
        if rech:
            tot['con_rechazo'] += 1
        per_ok_1 = a['contenido'].get('periodo') == r.get('esperado_periodo', None)
        detalle.append((s, r['id'], men, r['ramo_objetivo']['nombre'], c[0]['nombre'],
                        c[0]['similitud'], clase, r['acierto_ramo'], r['acierto_periodo'],
                        r['acierto_conjunto'], r['pregunta']))

if MODO == 'resumen':
    for k, v in sorted(tot.items(), key=str):
        print(k, v)
else:
    for d in detalle:
        if d[6][1] != 'top1_ok' or not d[7]:
            print(f'{d[0]} {d[1]} | men="{d[2]}" | real={d[3]} | top1={d[4]} ({d[5]}) | {d[6]} '
                  f'| ramo_final_ok={d[7]} periodo_ok={d[8]} conjunto={d[9]}\n    {d[10]}')
