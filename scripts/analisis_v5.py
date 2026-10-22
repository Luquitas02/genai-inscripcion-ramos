# -*- coding: utf-8 -*-
"""
Análisis de la corrida final de la versión 5, tal como lo fija PROTOCOLO_V5.md.

Se escribió antes de la corrida final, junto con el protocolo. Lee los `.raw.jsonl` y no llama
a ningún modelo. Imprime:

  1. acierto conjunto y estricto por conjunto y fila (baseline, D2, regla fija, v5 y sus
     configuraciones)
  2. H1: v5 contra D2, McNemar exacto bilateral, en los 180 y por conjunto; secundarias con el
     criterio estricto y sin los casos que repiten una pregunta anterior
  3. cada configuración contra la v5 completa, con pares discordantes y la marca de ruido
  4. subconjuntos: sin los que repiten una pregunta, sin los ambiguos (solo plantilla)
  5. extracción: ramo, período y recall@5 de T1
  6. ramas activadas, llamadas, tokens de entrada y segundos
  7. caso de falla y casos del video, con las reglas del protocolo

    python analisis_v5.py
    python analisis_v5.py --raiz <resultados> --datos <casos>   # para probarlo con otros datos
"""

import argparse
import json
import sys
from math import comb
from pathlib import Path

import diagnostico_d3 as D

RAIZ = Path(__file__).resolve().parent.parent
MODELO = "Phi-3.5-mini-instruct"
CONJUNTOS = [("plantilla A", "plantilla_a"), ("plantilla B", "plantilla_b"),
             ("redactados", "redactados")]
CONFIGS = ["completo", "sin_herramienta", "sin_ejemplos", "sin_lista_otros", "sin_regla_verbo",
           "sin_citas_interprete", "sin_citas_verificador", "sin_calendario", "sin_verificador",
           "top1"]
RUIDO = 3
# Las ramas que son decisiones de un agente o un tope. Los demás contadores de `ramas`
# (citas fuera de la consulta, salidas ilegibles, códigos fuera de la lista) no cambian el camino.
BIFURCACIONES = ("rechazos_mencion", "rechazos_codigo", "correcciones_periodo", "mantener",
                 "revision_citas", "ninguno_resolvedor", "busquedas_extra", "sin_ramo",
                 "tope_rechazos", "tope_llamadas")
N_TOTAL = 180


def archivo(res, fila, conj):
    if fila == "baseline":
        return res / f"{MODELO}__few_shot__prosa__{conj}.raw.jsonl"
    if fila == "d2":
        return res / f"pipeline__{MODELO}__codigo__encadenado__{conj}.raw.jsonl"
    if fila == "regla_fija":
        return res / "v5" / f"agentes__regla_fija__completo__{conj}.raw.jsonl"
    return res / "v5" / f"agentes__{MODELO}__{fila}__{conj}.raw.jsonl"


DATOS = RAIZ / "datos" / "prueba_v5"


def casos_de(conj):
    return [json.loads(l) for l in open(DATOS / f"{conj}.jsonl", encoding="utf-8")]


def estricto(x):
    """Decisión, regla, ramo y período correctos. El D2 guarda ramo y período en `paso1`; el
    baseline no extrae nada y no tiene criterio estricto."""
    if "paso1" in x:
        return bool(x["acierto_conjunto"] and x["paso1"]["acierto_ramo"]
                    and x["paso1"]["acierto_periodo"])
    if "acierto_ramo" in x:
        return bool(x["acierto_conjunto"] and x["acierto_ramo"] and x["acierto_periodo"])
    return None


def mcnemar(a, b):
    """McNemar exacto bilateral sobre dos dicts {id: bool}. Devuelve (b_gana, a_gana, p)."""
    solo_a = sum(1 for i in a if a[i] and not b[i])
    solo_b = sum(1 for i in a if b[i] and not a[i])
    n = solo_a + solo_b
    if n == 0:
        return solo_b, solo_a, 1.0
    k = min(solo_a, solo_b)
    return solo_b, solo_a, min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def pct(n, d):
    return f"{n:3}/{d:<3} {100 * n / d:5.1f} %" if d else "    —      "


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", default=str(RAIZ / "resultados"))
    ap.add_argument("--datos", default=None,
                    help="carpeta con plantilla_a, plantilla_b y redactados (para probar el "
                         "script con otros casos sin abrir los de prueba)")
    a = ap.parse_args()
    res = Path(a.raiz)
    if a.datos:
        global DATOS
        DATOS = Path(a.datos)

    filas = ["baseline", "d2", "regla_fija"] + CONFIGS
    datos, faltan = {}, []
    for fila in filas:
        for _, conj in CONJUNTOS:
            ruta = archivo(res, fila, conj)
            if ruta.exists():
                datos[(fila, conj)] = {x["id"]: x for x in map(json.loads, open(ruta, encoding="utf-8"))}
            else:
                faltan.append(ruta.name)
    if faltan:
        print(f"faltan {len(faltan)} archivos; las filas incompletas no se muestran:")
        for f in faltan:
            print("  ", f)
    completas = [f for f in filas if all((f, c) in datos for _, c in CONJUNTOS)]
    casos = {conj: casos_de(conj) for _, conj in CONJUNTOS}

    def global_(fila, f=lambda x: x["acierto_conjunto"], filtro=lambda conj, i: True):
        return {f"{conj}:{i}": bool(f(x)) for _, conj in CONJUNTOS
                for i, x in datos[(fila, conj)].items() if filtro(conj, i)}

    print("=" * 100)
    print("1 · ACIERTO CONJUNTO (y estricto entre paréntesis)")
    print("=" * 100)
    print(f"{'fila':22}" + "".join(f"{n:>22}" for n, _ in CONJUNTOS) + f"{'los 180':>22}")
    for fila in completas:
        partes, tot, tot_e = [], 0, 0
        for _, conj in CONJUNTOS:
            d = datos[(fila, conj)]
            n = sum(x["acierto_conjunto"] for x in d.values())
            e = [estricto(x) for x in d.values()]
            ne = None if None in e else sum(e)
            tot += n
            tot_e = None if ne is None or tot_e is None else tot_e + ne
            partes.append(f"{n:3}/{len(d):<3}" + (f" ({ne:3})" if ne is not None else "      "))
        n_tot = sum(len(datos[(fila, c)]) for _, c in CONJUNTOS)
        print(f"{fila:22}" + "".join(f"{p:>22}" for p in partes)
              + f"{f'{tot:3}/{n_tot}' + (f' ({tot_e:3})' if tot_e is not None else ''):>22}")

    if "completo" in completas and "d2" in completas:
        print()
        print("=" * 100)
        print("2 · H1: V5 CONTRA D2 (McNemar exacto bilateral)")
        print("=" * 100)
        for nombre, conj in CONJUNTOS:
            d2 = {i: bool(x["acierto_conjunto"]) for i, x in datos[("d2", conj)].items()}
            v5 = {i: bool(x["acierto_conjunto"]) for i, x in datos[("completo", conj)].items()}
            g, p_, p = mcnemar(d2, v5)
            print(f"  {nombre:24} v5 gana {g:3}, D2 gana {p_:3}   p = {p:.4g}")
        g, p_, p = mcnemar(global_("d2"), global_("completo"))
        print(f"  {'H1, los 180':24} v5 gana {g:3}, D2 gana {p_:3}   p = {p:.4g}")
        g, p_, p = mcnemar(global_("d2", estricto), global_("completo", estricto))
        print(f"  {'estricto, los 180':24} v5 gana {g:3}, D2 gana {p_:3}   p = {p:.4g}")
        repite = {f"{conj}:{i}" for _, conj in CONJUNTOS for i, c in enumerate(casos[conj])
                  if c.get("filtro_v5") == "repite_pregunta"}
        sin_rep = lambda conj, i: f"{conj}:{i}" not in repite          # noqa: E731
        g, p_, p = mcnemar(global_("d2", filtro=sin_rep), global_("completo", filtro=sin_rep))
        print(f"  {f'sin los {len(repite)} que repiten':24} v5 gana {g:3}, D2 gana {p_:3}   p = {p:.4g}")
        if "baseline" in completas:
            g, p_, p = mcnemar(global_("baseline"), global_("completo"))
            print(f"  {'v5 contra baseline':24} v5 gana {g:3}, baseline gana {p_:3}   p = {p:.4g}")
        if "regla_fija" in completas:
            g, p_, p = mcnemar(global_("regla_fija"), global_("completo"))
            print(f"  {'v5 contra regla fija':24} v5 gana {g:3}, regla gana {p_:3}   p = {p:.4g}")

    if "completo" in completas:
        print()
        print("=" * 100)
        print("3 · CADA CONFIGURACIÓN CONTRA LA V5 COMPLETA (180 casos, exploratorio)")
        print("=" * 100)
        base = global_("completo")
        base_e = global_("completo", estricto)
        nb = sum(base.values())
        for fila in [f for f in CONFIGS[1:] if f in completas]:
            otra, otra_e = global_(fila), global_(fila, estricto)
            no = sum(otra.values())
            completo_gana, abl_gana, p = mcnemar(otra, base)
            ce, ae, pe = mcnemar(otra_e, base_e)
            marca = "dentro del ruido" if abs(no - nb) <= RUIDO else ""
            print(f"  {fila:22} {no:3}  Δ {no - nb:+3}  completo gana {completo_gana:2}, "
                  f"ablación gana {abl_gana:2}, p = {p:.3g}  {marca}")
            print(f"  {'':22} estricto {sum(otra_e.values()):3}  Δ {sum(otra_e.values()) - sum(base_e.values()):+3}"
                  f"  ({ce} a {ae}, p = {pe:.3g})")

    print()
    print("=" * 100)
    print("4 · SUBCONJUNTOS (acierto conjunto)")
    print("=" * 100)
    ambiguos = {f"{conj}:{i}" for _, conj in CONJUNTOS[:2] for i, c in enumerate(casos[conj])
                if D.es_ambigua(D.mencion_consultada(c["pregunta_prosa"]) or "")}
    repite = {f"{conj}:{i}" for _, conj in CONJUNTOS for i, c in enumerate(casos[conj])
              if c.get("filtro_v5") == "repite_pregunta"}
    plantilla = {f"{conj}:{i}" for _, conj in CONJUNTOS[:2] for i in range(len(casos[conj]))}
    print(f"  ambiguos en plantilla: {len(ambiguos)} de {len(plantilla)}; "
          f"repiten una pregunta anterior: {len(repite)}")
    for fila in [f for f in ("baseline", "d2", "regla_fija", "completo") if f in completas]:
        g = global_(fila)
        sin_amb = [v for k, v in g.items() if k in plantilla and k not in ambiguos]
        sin_rep = [v for k, v in g.items() if k not in repite]
        print(f"  {fila:22} plantilla sin ambiguos {pct(sum(sin_amb), len(sin_amb))}   "
              f"180 sin los que repiten {pct(sum(sin_rep), len(sin_rep))}")

    print()
    print("=" * 100)
    print("5 · EXTRACCIÓN (180 casos)")
    print("=" * 100)
    for fila in [f for f in ["regla_fija"] + CONFIGS if f in completas]:
        xs = [x for _, c in CONJUNTOS for x in datos[(fila, c)].values()]
        rec = [x["t1_recall5"] for x in xs if x.get("t1_recall5") is not None]
        print(f"  {fila:22} ramo {pct(sum(x['acierto_ramo'] for x in xs), len(xs))}   "
              f"período {pct(sum(x['acierto_periodo'] for x in xs), len(xs))}   "
              f"T1 recall@5 {sum(rec)}/{len(rec)}")
    if "d2" in completas:
        xs = [x for _, c in CONJUNTOS for x in datos[("d2", c)].values()]
        print(f"  {'d2':22} ramo {pct(sum(x['paso1']['acierto_ramo'] for x in xs), len(xs))}   "
              f"período {pct(sum(x['paso1']['acierto_periodo'] for x in xs), len(xs))}")

    print()
    print("=" * 100)
    print("6 · RAMAS ACTIVADAS (casos), LLAMADAS, TOKENS DE ENTRADA Y SEGUNDOS POR CASO")
    print("=" * 100)
    for fila in [f for f in CONFIGS if f in completas]:
        xs = [x for _, c in CONJUNTOS for x in datos[(fila, c)].values()]
        ramas = {k: sum(1 for x in xs if x["ramas"].get(k)) for k in xs[0]["ramas"]}
        activas = "  ".join(f"{k} {v}" for k, v in ramas.items() if v)
        print(f"  {fila:22} {sum(x['llamadas'] for x in xs) / len(xs):4.1f} llamadas  "
              f"{sum(x['tokens_total'] for x in xs) / len(xs):6,.0f} tokens  "
              f"{sum(x['segundos_total'] for x in xs) / len(xs):4.1f} s")
        print(f"  {'':22} {activas or '(ninguna rama)'}")
        camino_fijo = sum(1 for x in xs if not any(x["ramas"].get(k) for k in BIFURCACIONES))
        print(f"  {'':22} sin ninguna rama (camino fijo): {camino_fijo}/{len(xs)}")
    for fila, tk, sg in (("baseline", "tokens_entrada", "segundos"), ("d2", "tokens_total", "segundos_total")):
        if fila in completas:
            xs = [x for _, c in CONJUNTOS for x in datos[(fila, c)].values()]
            print(f"  {fila:22} {sum(x.get(tk) or 0 for x in xs) / len(xs):6,.0f} tokens  "
                  f"{sum(x.get(sg) or 0 for x in xs) / len(xs):4.1f} s")

    if "completo" in completas:
        print()
        print("=" * 100)
        print("7 · CASO DE FALLA Y CASOS DEL VIDEO (reglas del protocolo, v5 completa)")
        print("=" * 100)
        red = datos[("completo", "redactados")]
        orden = sorted(red, key=int)
        falla = next((("redactados", i) for i in orden if not red[i]["acierto_conjunto"]), None)
        if falla is None:
            pa = datos[("completo", "plantilla_a")]
            falla = next((("plantilla_a", i) for i in sorted(pa, key=int)
                          if not pa[i]["acierto_conjunto"]), None)
        directo = next((("redactados", i) for i in orden
                        if estricto(red[i]) and red[i]["llamadas"] == 3), None)

        def intervino(x):
            r = x["ramas"]
            return bool(r.get("correcciones_periodo") or r.get("rechazos_mencion")
                        or r.get("rechazos_codigo"))

        def con_decision(exigir):
            for _, conj in CONJUNTOS:
                d = datos[("completo", conj)]
                for i in sorted(d, key=int):
                    if intervino(d[i]) and (estricto(d[i]) or not exigir):
                        return conj, i
            return None

        decision = con_decision(True) or con_decision(False)
        for nombre, sel in (("caso de falla", falla), ("video, directo", directo),
                            ("video, con decisión", decision), ("video, falla", falla)):
            if sel is None:
                print(f"  {nombre:20} ninguno")
                continue
            conj, i = sel
            x = datos[("completo", conj)][i]
            print(f"  {nombre:20} {conj} caso {i}: \"{x['pregunta']}\"")
            print(f"  {'':20} esperado {x['ramo_objetivo']['nombre']} {x['esperado']} → "
                  f"{x['extraccion']} {x['prediccion']['decision']}/{x['prediccion']['regla']}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
