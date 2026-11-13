# -*- coding: utf-8 -*-
"""
Análisis previo al plan del D4: qué tan medible es ajustar al Intérprete (A).

No corre modelos. Usa las trazas y .raw.jsonl de la v4 (configuración completa) y el motor de
reglas real.

  1. Dónde falla A: plantilla contra redactadas, por frase de período de la plantilla y por si
     la pregunta nombra otro ramo "en curso" (E1 del D1).
  2. Cuándo importa el período: con el ramo correcto, ¿cambiar el período cambia la respuesta?
  3. Potencia: cuántos casos necesita la prueba sellada para que una mejora real dé p < 0,05
     (McNemar exacto, simulación), y cuánto tiempo de T4 cuesta cada sistema.

    python scripts/analisis_previo_d4.py
"""

import collections
import json
import random
import statistics
import sys
from math import comb
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import generador as G                              # noqa: E402
from herramientas import motor_de_reglas, buscar_ramo   # noqa: E402
from verificador import Verificador                # noqa: E402

M = "Phi-3.5-mini-instruct"
PARTES = [  # (parte, archivo de datos, tipo, uso)
    ("casos", "datos/casos.jsonl", "plantilla", "150"),
    ("casos_nuevos", "datos/casos_nuevos.jsonl", "plantilla", "150"),
    ("casos_redactados", "datos/casos_redactados.jsonl", "redactada", "150"),
    ("plantilla_a", "datos/prueba_v5/plantilla_a.jsonl", "plantilla", "180"),
    ("plantilla_b", "datos/prueba_v5/plantilla_b.jsonl", "plantilla", "180"),
    ("redactados", "datos/prueba_v5/redactados.jsonl", "redactada", "180"),
    ("casos_desarrollo", "datos/casos_desarrollo.jsonl", "plantilla", "dev"),
    ("casos_desarrollo_redactados", "datos/casos_desarrollo_redactados.jsonl", "redactada", "dev"),
]
FRASES = sorted({f for v in G.PERIODO_TXT.values() for f in v}, key=len, reverse=True)
EN_CURSO = G.ESTADO_INSCRITA_TXT


def jl(r):
    with open(RAIZ / r, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def acierta(v, caso, codigo, periodo):
    p = motor_de_reglas(v, caso, codigo, periodo)
    e = caso["respuesta"]
    return p["decision"] == e["decision"] and p["regla"] == e["regla"]


def frase_plantilla(pregunta):
    q = pregunta.lower().rstrip("?")
    for f in FRASES:
        if q.endswith(" " + f):
            return f
    return "?"


def mcnemar_p(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def potencia(n, p_err, arregla, rompe, sims=4000, rnd=random.Random(1)):
    """Fracción de simulaciones con p < 0,05 cuando A base falla con prob. p_err, el ajustado
    arregla una fracción `arregla` de esos fallos y rompe una fracción `rompe` de los aciertos."""
    exito = 0
    for _ in range(sims):
        b = c = 0
        for _ in range(n):
            if rnd.random() < p_err:
                b += rnd.random() < arregla
            else:
                c += rnd.random() < rompe
        exito += mcnemar_p(b, c) < 0.05 and b > c
    return exito / sims


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    v = Verificador()
    filas = []
    for parte, ruta, tipo, uso in PARTES:
        casos = jl(ruta)
        raws = {str(r["id"]): r for r in jl(f"resultados/agentes__{M}__completo__{parte}.raw.jsonl")}
        tr = collections.defaultdict(list)
        for m in jl(f"trazas/agentes__{M}__completo__{parte}.jsonl"):
            tr[str(m["caso"])].append(m)
        for i, caso in enumerate(casos):
            raw = raws[str(i)]
            a = next(m["contenido"] for m in tr[str(i)] if m["de"] == "interprete")
            oro = caso["ramo_objetivo"]["codigo"]
            per = caso["consulta"]["periodo"]
            otro = "proximo" if per == "actual" else "actual"
            top1 = buscar_ramo(a.get("consultado") or "")[0]["codigo"]
            filas.append({
                "parte": parte, "tipo": tipo, "uso": uso, "id": i, "pregunta": caso["pregunta_prosa"],
                "per": per, "per_A": a.get("periodo") or "actual", "frase_A": a.get("frase_periodo"),
                "mencion_ok": top1 == oro,
                "en_curso": any(s in caso["pregunta_prosa"].lower() for s in EN_CURSO)
                            or "cursando" in caso["pregunta_prosa"].lower(),
                "frase": frase_plantilla(caso["pregunta_prosa"]) if tipo == "plantilla" else None,
                "importa_periodo": acierta(v, caso, oro, per) and not acierta(v, caso, oro, otro),
                "conjunto": raw["acierto_conjunto"], "seg": raw["segundos_total"],
                "constructor": caso["constructor"],
            })

    print("=== 1. Dónde falla el Intérprete (primera lectura) ===")
    for tipo in ("plantilla", "redactada"):
        f = [x for x in filas if x["tipo"] == tipo]
        print(f"{tipo}: {len(f)} casos · período bien {sum(x['per_A'] == x['per'] for x in f)} · "
              f"mención que lleva a T1 al ramo correcto {sum(x['mencion_ok'] for x in f)}")
        for ec in (True, False):
            g = [x for x in f if x["en_curso"] == ec]
            print(f"   {'nombra otro ramo en curso' if ec else 'sin otro ramo en curso'}: {len(g)} · "
                  f"período mal {sum(x['per_A'] != x['per'] for x in g)}")
    print("plantilla, por frase de período (casos · período mal):")
    f = [x for x in filas if x["tipo"] == "plantilla"]
    for fr in FRASES + ["?"]:
        g = [x for x in f if x["frase"] == fr]
        if g:
            print(f"   {fr!r:28} {len(g):3} · {sum(x['per_A'] != x['per'] for x in g)}")
    print("redactadas con período mal:")
    for x in filas:
        if x["tipo"] == "redactada" and x["per_A"] != x["per"]:
            print(f"   [{x['parte']} {x['id']}] caso={x['per']} A={x['per_A']} frase_A={x['frase_A']!r} · {x['pregunta']}")

    print("\n=== 2. Cuándo importa el período (con el ramo correcto) ===")
    imp = [x for x in filas if x["importa_periodo"]]
    print(f"importa en {len(imp)} de {len(filas)}; por constructor:",
          dict(collections.Counter(x["constructor"] for x in imp)))
    print("   de esos, nombran otro ramo en curso:", sum(x["en_curso"] for x in imp))
    for tipo in ("plantilla", "redactada"):
        g = [x for x in imp if x["tipo"] == tipo]
        print(f"   {tipo}: {len(g)} · A con período mal {sum(x['per_A'] != x['per'] for x in g)}")
    todos = collections.Counter(x["constructor"] for x in filas)
    print("   fracción en que importa, por constructor:",
          {k: f"{sum(1 for x in imp if x['constructor'] == k)}/{n}" for k, n in todos.items()})

    print("\n=== 3. Potencia de la prueba (McNemar exacto, p < 0,05, 4000 simulaciones) ===")
    for p_err in (0.10, 0.20, 0.30):
        for arregla in (0.5, 0.75):
            linea = " ".join(f"n={n}:{potencia(n, p_err, arregla, 0.02):.2f}" for n in (60, 100, 150, 200, 300))
            print(f"   A base falla {p_err:.0%} · ajustado arregla {arregla:.0%} · rompe 2%: {linea}")
    seg = [x["seg"] for x in filas]
    print(f"\ntiempo por caso del sistema completo: media {statistics.mean(seg):.1f} s, "
          f"mediana {statistics.median(seg):.1f} s, máx {max(seg):.1f} s")


if __name__ == "__main__":
    main()
