# -*- coding: utf-8 -*-
"""
Análisis de la corrida final del Deliverable 3, tal como lo fija PROTOCOLO_D3.md.

Lee los `.raw.jsonl` de `resultados/` y no llama a ningún modelo. Imprime:

  1. acierto conjunto por conjunto y fila (baseline, D2, regla fija, agentes, ablaciones)
  2. H1: agentes contra D2, McNemar exacto bilateral en los 150 casos y por conjunto
  3. ablaciones contra el sistema completo, con la marca de ruido (3 casos o menos)
  4. acierto sin los casos ambiguos (originales y nuevos)
  5. extracción: ramo, período y recall@5 de T1
  6. ramas activadas, llamadas, tokens y segundos
  7. caso de falla y casos del video, con las reglas del protocolo
  8. acierto de ramo y período por mecanismo, D2 contra agentes (originales y nuevos sin ambiguos)

    python analisis_d3.py
"""

import json
import sys
from math import comb
from pathlib import Path

import diagnostico_d3 as D

RAIZ = Path(__file__).resolve().parent.parent
RES = RAIZ / "resultados"
CONJUNTOS = [("originales", "casos"), ("nuevos", "casos_nuevos"), ("redactados", "casos_redactados")]
MODELO = "Phi-3.5-mini-instruct"
CONFIGS = ["completo", "sin_descomposicion", "sin_herramienta", "sin_verificador",
           "sin_ejemplos", "top1"]
RUIDO = 3


def _archivo_base(fila, conj):
    sufijo = "" if conj == "casos" else f"__{conj}"
    if fila == "baseline":
        return RES / f"{MODELO}__few_shot__prosa{sufijo}.raw.jsonl"
    if fila == "zero_shot":
        # originales: la corrida del D1; nuevos y redactados: zero_shot_150_colab.ipynb (31 oct)
        return RES / f"{MODELO}__zero_shot__prosa{sufijo}.raw.jsonl"
    if fila == "d2":
        return RES / f"pipeline__{MODELO}__codigo__encadenado{sufijo}.raw.jsonl"
    if fila == "regla_fija":
        return RES / f"agentes__regla_fija__completo__{conj}.raw.jsonl"
    return RES / f"agentes__{MODELO}__{fila}__{conj}.raw.jsonl"


def cargar(fila, conj):
    """{id: fila}. Los ids son la posición del caso en su archivo."""
    filas = [json.loads(l) for l in open(_archivo_base(fila, conj), encoding="utf-8") if l.strip()]
    return {str(x["id"]): x for x in filas}


def mcnemar(a, b):
    """McNemar exacto bilateral sobre dos dicts {id: bool}. Devuelve (b_gana, a_gana, p)."""
    solo_a = sum(1 for i in a if a[i] and not b[i])
    solo_b = sum(1 for i in a if b[i] and not a[i])
    n = solo_a + solo_b
    if n == 0:
        return solo_b, solo_a, 1.0
    k = min(solo_a, solo_b)
    p = min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)
    return solo_b, solo_a, p


def aciertos(fila):
    """{id_global: bool} en los 150 casos."""
    out = {}
    for _, conj in CONJUNTOS:
        for i, x in cargar(fila, conj).items():
            out[f"{conj}:{i}"] = bool(x["acierto_conjunto"])
    return out


def ambiguos(conj):
    """Ids cuya mención del ramo consultado sirve para más de un ramo (solo plantillas)."""
    if conj == "casos_redactados":
        return set()
    casos = [json.loads(l) for l in open(RAIZ / "datos" / f"{conj}.jsonl", encoding="utf-8")]
    return {str(i) for i, c in enumerate(casos)
            if D.es_ambigua(D.mencion_consultada(c["pregunta_prosa"]) or "")}


def pct(n, d):
    return f"{n:3}/{d:<3} {100 * n / d:5.1f} %"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    filas_tabla = ["zero_shot", "baseline", "d2", "regla_fija"] + CONFIGS

    print("=" * 96)
    print("1 · ACIERTO CONJUNTO")
    print("=" * 96)
    print(f"{'fila':20}" + "".join(f"{n:>19}" for n, _ in CONJUNTOS) + f"{'los 150':>19}")
    for fila in filas_tabla:
        partes, tot = [], 0
        for _, conj in CONJUNTOS:
            d = cargar(fila, conj)
            n = sum(x["acierto_conjunto"] for x in d.values())
            tot += n
            partes.append(pct(n, len(d)))
        print(f"{fila:20}" + "".join(f"{p:>19}" for p in partes) + f"{pct(tot, 150):>19}")

    print()
    print("=" * 96)
    print("2 · H1: AGENTES CONTRA D2 (McNemar exacto bilateral)")
    print("=" * 96)
    for nombre, conj in CONJUNTOS + [("los 150", None)]:
        if conj:
            a = {i: bool(x["acierto_conjunto"]) for i, x in cargar("d2", conj).items()}
            b = {i: bool(x["acierto_conjunto"]) for i, x in cargar("completo", conj).items()}
        else:
            a, b = aciertos("d2"), aciertos("completo")
        gana, pierde, p = mcnemar(a, b)
        print(f"  {nombre:12} agentes ganan {gana:3}, D2 gana {pierde:3}   p = {p:.4g}")
    a, b = aciertos("baseline"), aciertos("completo")
    gana, pierde, p = mcnemar(a, b)
    print(f"  {'vs baseline':12} agentes ganan {gana:3}, baseline gana {pierde:3}   p = {p:.4g}  (150)")
    a, b = aciertos("regla_fija"), aciertos("completo")
    gana, pierde, p = mcnemar(a, b)
    print(f"  {'vs regla':12} agentes ganan {gana:3}, regla gana {pierde:3}   p = {p:.4g}  (150)")

    print()
    print("=" * 96)
    print("3 · ABLACIONES CONTRA EL SISTEMA COMPLETO (150 casos)")
    print("=" * 96)
    base = aciertos("completo")
    nb = sum(base.values())
    for fila in CONFIGS[1:]:
        otra = aciertos(fila)
        no = sum(otra.values())
        completo_gana, ablacion_gana, p = mcnemar(otra, base)
        marca = "dentro del ruido" if abs(nb - no) <= RUIDO else ""
        por_conj = []
        for _, conj in CONJUNTOS:
            dc = sum(x["acierto_conjunto"] for x in cargar(fila, conj).values())
            bc = sum(x["acierto_conjunto"] for x in cargar("completo", conj).values())
            por_conj.append(f"{dc - bc:+3d}")
        print(f"  {fila:20} {no:3}  Δ {no - nb:+3d}  (orig {por_conj[0]}, nuevos {por_conj[1]}, "
              f"redact {por_conj[2]})  completo gana {completo_gana}, ablación gana {ablacion_gana}, "
              f"p = {p:.3g}  {marca}")

    print()
    print("=" * 96)
    print("4 · SIN LOS CASOS AMBIGUOS (originales y nuevos)")
    print("=" * 96)
    for nombre, conj in CONJUNTOS[:2]:
        amb = ambiguos(conj)
        linea = []
        for fila in ("baseline", "d2", "regla_fija", "completo"):
            d = cargar(fila, conj)
            ids = [i for i in d if i not in amb]
            linea.append(f"{fila} {pct(sum(d[i]['acierto_conjunto'] for i in ids), len(ids))}")
        print(f"  {nombre:11} ({len(amb)} ambiguos)  " + "   ".join(linea))

    print()
    print("=" * 96)
    print("5 · EXTRACCIÓN (150 casos)")
    print("=" * 96)
    for fila in ["regla_fija"] + CONFIGS:
        filas = [x for _, conj in CONJUNTOS for x in cargar(fila, conj).values()]
        r5 = [x["t1_recall5"] for x in filas if x["t1_recall5"] is not None]
        print(f"  {fila:20} ramo {pct(sum(x['acierto_ramo'] for x in filas), 150)}   "
              f"período {pct(sum(x['acierto_periodo'] for x in filas), 150)}   "
              f"T1 recall@5 {sum(r5)}/{len(r5)}")
    # El D2 por conjunto, para comparar la extracción con el sistema anterior
    for nombre, conj in CONJUNTOS:
        d2 = cargar("d2", conj)
        ag = cargar("completo", conj)
        print(f"  ramo en {nombre:11}  D2 {sum(x['paso1']['acierto_ramo'] for x in d2.values()):3}"
              f"   agentes {sum(x['acierto_ramo'] for x in ag.values()):3}   de {len(ag)}")

    print()
    print("=" * 96)
    print("6 · RAMAS ACTIVADAS (casos), LLAMADAS, TOKENS Y SEGUNDOS POR CASO")
    print("=" * 96)
    claves = ["rechazos_verificador", "busquedas_extra", "ninguno_resolvedor", "sin_ramo",
              "tope_rechazos", "tope_llamadas", "ilegibles", "codigo_fuera", "citas_fuera"]
    print(f"  {'fila':20}" + "".join(f"{k[:9]:>10}" for k in claves) + "   llam  tokens   s")
    for fila in CONFIGS:
        filas = [x for _, conj in CONJUNTOS for x in cargar(fila, conj).values()]
        cuentas = [sum(1 for x in filas if x["ramas"][k]) for k in claves]
        print(f"  {fila:20}" + "".join(f"{c:>10}" for c in cuentas)
              + f"  {sum(x['llamadas'] for x in filas) / 150:4.1f}"
              f"  {sum(x['tokens_total'] for x in filas) / 150:6,.0f}"
              f"  {sum(x['segundos_total'] for x in filas) / 150:4.1f}")
    for fila, tk, sg in (("baseline", "tokens_entrada", "segundos"), ("d2", "tokens_total", "segundos_total")):
        filas = [x for _, conj in CONJUNTOS for x in cargar(fila, conj).values()]
        print(f"  {fila:20}{'':90}  {1.0 if fila == 'baseline' else '':>4}"
              f"  {sum(x[tk] or 0 for x in filas) / 150:6,.0f}  {sum(x[sg] or 0 for x in filas) / 150:4.1f}")

    print()
    print("=" * 96)
    print("7 · CASO DE FALLA Y CASOS DEL VIDEO (reglas del protocolo, corrida completo)")
    print("=" * 96)
    red = cargar("completo", "casos_redactados")
    casos_red = [json.loads(l) for l in open(RAIZ / "datos" / "casos_redactados.jsonl", encoding="utf-8")]
    orden_red = sorted(red, key=lambda i: casos_red[int(i)]["id_original"])
    falla = next((("casos_redactados", i) for i in orden_red if not red[i]["acierto_conjunto"]), None)
    if falla is None:
        nue = cargar("completo", "casos_nuevos")
        falla = next((("casos_nuevos", i) for i in sorted(nue, key=int)
                      if not nue[i]["acierto_conjunto"]), None)
    directo = next((("casos_redactados", i) for i in orden_red
                    if red[i]["acierto_conjunto"] and red[i]["llamadas"] == 3), None)

    def con_decision(exigir_acierto):
        for conj in ("casos_redactados", "casos", "casos_nuevos"):
            d = cargar("completo", conj)
            orden = orden_red if conj == "casos_redactados" else sorted(d, key=int)
            for i in orden:
                r = d[i]["ramas"]
                if (r["rechazos_verificador"] or r["busquedas_extra"]) and \
                        (d[i]["acierto_conjunto"] or not exigir_acierto):
                    return conj, i
        return None

    decision = con_decision(True) or con_decision(False)
    for nombre, sel in (("caso de falla", falla), ("video, directo", directo),
                        ("video, con decisión", decision), ("video, falla", falla)):
        if sel is None:
            print(f"  {nombre:20} ninguno")
            continue
        conj, i = sel
        x = cargar("completo", conj)[i]
        extra = f" (id_original {casos_red[int(i)]['id_original']})" if conj == "casos_redactados" else ""
        print(f"  {nombre:20} {conj} caso {i}{extra}: \"{x['pregunta']}\"")
        print(f"  {'':20} esperado {x['ramo_objetivo']['nombre']} {x['esperado']} → "
              f"{x['extraccion']} {x['prediccion']['decision']}/{x['prediccion']['regla']}")

    print()
    print("=" * 96)
    print("8 · POR MECANISMO (originales y nuevos sin ambiguos, misma clasificación que diagnostico_d3)")
    print("=" * 96)
    # "nombre exacto" y "abreviado o coloquial" reparten los casos. "nombra otro ramo antes"
    # (M2) es un subconjunto que cruza a ambas.
    t = {}
    for _, conj in CONJUNTOS[:2]:
        casos = [json.loads(l) for l in open(RAIZ / "datos" / f"{conj}.jsonl", encoding="utf-8")]
        d2, ag = cargar("d2", conj), cargar("completo", conj)
        for i, c in enumerate(casos):
            ref = D.mencion_consultada(c["pregunta_prosa"]) or ""
            if D.es_ambigua(ref):
                continue
            obj = c["ramo_objetivo"]["codigo"]
            clases = ["exacto (M1)" if D.norm(ref) == D.NOMBRES_NORM[obj] else "abreviado o coloquial"]
            if any(m in c["pregunta_prosa"].lower() for m in D.MARCAS_MENCION):
                clases.append("de ellos, otro ramo antes (M2)")
            p1 = d2[str(i)]["paso1"]
            for clase in clases:
                n, a, b = t.get(clase, (0, 0, 0))
                t[clase] = (n + 1, a + p1["acierto_ramo"], b + ag[str(i)]["acierto_ramo"])
            n, a, b = t.get("período (M3)", (0, 0, 0))
            t["período (M3)"] = (n + 1, a + p1["acierto_periodo"], b + ag[str(i)]["acierto_periodo"])
    print(f"  {'':32}{'casos':>6}{'D2':>6}{'agentes':>9}")
    for clase in ("exacto (M1)", "abreviado o coloquial", "de ellos, otro ramo antes (M2)", "período (M3)"):
        n, a, b = t[clase]
        print(f"  {clase:32}{n:6}{a:6}{b:9}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
