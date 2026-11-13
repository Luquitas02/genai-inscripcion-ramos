# -*- coding: utf-8 -*-
"""
Análisis del piloto del D4 (60 casos de desarrollo de `datos/piloto_d4/piloto.jsonl`).

Compara tres sistemas sobre los mismos casos: el del D3 (completo), el control (40 ejemplos
más en el prompt del Intérprete) y el del Intérprete ajustado con el adaptador del piloto.

    python scripts/analisis_piloto_d4.py [carpeta de corridas]
"""

import collections
import json
import sys
from math import comb
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CORRIDAS = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "resultados" / "piloto_d4" / "corridas"
SISTEMAS = {"D3": "Phi-3.5-mini-instruct__completo",
            "control": "Phi-3.5-mini-instruct__control_muchos_ejemplos",
            "ajustado": "Phi-3.5-mini-instruct+A-lora-piloto__completo"}


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def mcnemar(b, c):
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    casos = jl(RAIZ / "datos" / "piloto_d4" / "piloto.jsonl")
    res, trz = {}, {}
    for k, pref in SISTEMAS.items():
        res[k] = {str(r["id"]): r for r in jl(CORRIDAS / f"agentes__{pref}__piloto.raw.jsonl")}
        t = collections.defaultdict(list)
        for m in jl(CORRIDAS / f"agentes__{pref}__piloto.traza.jsonl"):
            t[str(m["caso"])].append(m)
        trz[k] = t
    n = len(casos)
    print(f"{n} casos · aciertos")
    print(f"{'':10}{'conjunto':>9}{'ramo':>6}{'período':>9}{'estricto':>9}{'A período':>11}{'s/ JSON':>8}")
    for k in SISTEMAS:
        r = res[k]
        a_per = 0
        for i, c in enumerate(casos):
            a = next((m["contenido"] for m in trz[k][str(i)] if m["de"] == "interprete"), {})
            a_per += (a.get("periodo") or "actual") == c["consulta"]["periodo"]
        ileg = sum(x["ramas"]["ilegibles"] for x in r.values())
        print(f"{k:10}{sum(x['acierto_conjunto'] for x in r.values()):>9}"
              f"{sum(x['acierto_ramo'] for x in r.values()):>6}{sum(x['acierto_periodo'] for x in r.values()):>9}"
              f"{sum(x['acierto_ramo'] and x['acierto_periodo'] for x in r.values()):>9}{a_per:>11}{ileg:>8}")
    for k in ("control", "ajustado"):
        for met in ("acierto_conjunto",):
            b = sum(res[k][str(i)][met] and not res["D3"][str(i)][met] for i in range(n))
            c = sum(res["D3"][str(i)][met] and not res[k][str(i)][met] for i in range(n))
            print(f"{k} contra D3 ({met}): gana {b}, pierde {c}, McNemar p = {mcnemar(b, c):.3f}")
    print("\npor estilo de período (conjunto D3 / control / ajustado):")
    for est in ("relativo", "calendario", "implicito"):
        ids = [str(i) for i, c in enumerate(casos) if c["estilo"]["periodo"] == est]
        print(f"   {est:11} {len(ids):3}: " + " / ".join(str(sum(res[k][i]['acierto_conjunto'] for i in ids)) for k in SISTEMAS))
    print("por estilo de ramo:")
    for est in ("nombre", "apodo"):
        ids = [str(i) for i, c in enumerate(casos) if c["estilo"]["ramo"] == est]
        print(f"   {est:11} {len(ids):3}: " + " / ".join(str(sum(res[k][i]['acierto_conjunto'] for i in ids)) for k in SISTEMAS))
    imp = [str(i) for i, c in enumerate(casos) if c["constructor"] in ("_c_inscrita_actual", "_c_inscrita_proximo")]
    print(f"donde decide el período ({len(imp)}): " + " / ".join(str(sum(res[k][i]['acierto_conjunto'] for i in imp)) for k in SISTEMAS))
    print("\ncasos que falla alguno (D3 · control · ajustado):")
    for i, c in enumerate(casos):
        s = str(i)
        if all(res[k][s]["acierto_conjunto"] for k in SISTEMAS):
            continue
        marcas = []
        for k in SISTEMAS:
            x = res[k][s]
            a = next((m["contenido"] for m in trz[k][s] if m["de"] == "interprete"), {})
            marcas.append(f"{'OK' if x['acierto_conjunto'] else '--'} {a.get('consultado')!r}/{a.get('periodo')}"
                          f"{'' if x['acierto_ramo'] else ' RAMO'}{'' if x['acierto_periodo'] else ' PER'}")
        print(f"[{i}] {c['consulta']['periodo']} {c['ramo_objetivo']['nombre']} · {c['pregunta_prosa']}")
        for k, mm in zip(SISTEMAS, marcas):
            print(f"      {k:9} {mm}")


if __name__ == "__main__":
    main()
