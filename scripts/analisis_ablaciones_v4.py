# -*- coding: utf-8 -*-
"""
Análisis de las ablaciones de una sola técnica de la v4 sobre los 180 casos sellados, tal como
lo fija PROTOCOLO_ABLACIONES_V4.md.

Se escribió antes de correr las ablaciones. Lee los `.raw.jsonl` y no llama a ningún modelo.
La v4 completa es la de la réplica (`agentes__...__completo__{conjunto}`). Imprime:

  1. cada configuración contra la v4 completa en los 180: acierto conjunto, Δ, pares
     discordantes y McNemar exacto bilateral; lo mismo con el criterio estricto
  2. por mecanismo: ramo en plantilla con el nombre exacto (M1), abreviado, con otro ramo
     nombrado antes (M2), y período en los 180 (M3); y acierto en las redactadas
  3. ramas activadas, llamadas y segundos por caso
  4. el baseline zero-shot junto al few-shot de la réplica

    python analisis_ablaciones_v4.py
    python analisis_ablaciones_v4.py --raiz <resultados> --datos <casos>   # para probarlo
"""

import argparse
import json
import re
import sys
from pathlib import Path

import diagnostico_d3 as D
from analisis_replica_v4 import CONJUNTOS, MODELO, RAIZ, estricto, mcnemar, pct

RUIDO = 3
# Técnica, agente y mecanismo al que apunta, fijados en el protocolo antes de correr.
CONFIGS = [
    ("sin_herramienta", "búsqueda T1 (ReAct)", "B", "M1"),
    ("sin_ejemplos", "4 ejemplos (few-shot)", "A", "M2, M3"),
    ("sin_lista_otros", "lista de los otros ramos", "A", "M2"),
    ("sin_regla_verbo", "regla del verbo", "A", "M2"),
    ("sin_citas_interprete", "citar antes de decidir (quotes first)", "A", "M3"),
    ("sin_citas_verificador", "citar antes de decidir (quotes first)", "C", "M2, M3"),
    ("sin_ejemplos_verificador", "2 ejemplos (few-shot)", "C", "M2"),
    ("sin_verificador", "el Verificador entero", "C", "M2, M3"),
    ("top1", "el Resolvedor, reemplazado por el top-1", "B", "M1"),
    # Agregadas el 29 oct con PROTOCOLO_ABLACIONES_B.md, antes de correrlas.
    ("sin_regla_siglas", "regla de siglas (claro y directo)", "B", "M1"),
    ("sin_regla_numeros", "regla de números (claro y directo)", "B", "M1"),
]
# Un ramo "con número" termina en un número arábigo o romano (Cálculo III, Electiva 2).
CON_NUMERO = re.compile(r"\b(I|II|III|IV|V|VI|\d)\s*$")
DATOS = RAIZ / "datos" / "prueba_v5"


def archivo(res, config, conj):
    if config == "zero_shot":
        return res / f"{MODELO}__zero_shot__prosa__{conj}.raw.jsonl"
    if config == "few_shot":
        return res / f"{MODELO}__few_shot__prosa__{conj}.raw.jsonl"
    return res / f"agentes__{MODELO}__{config}__{conj}.raw.jsonl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", default=str(RAIZ / "resultados"))
    ap.add_argument("--datos", default=None)
    a = ap.parse_args()
    res = Path(a.raiz)
    datos_dir = Path(a.datos) if a.datos else DATOS

    nombres = ["completo"] + [c for c, *_ in CONFIGS] + ["zero_shot", "few_shot"]
    datos, faltan = {}, []
    for config in nombres:
        for _, conj in CONJUNTOS:
            ruta = archivo(res, config, conj)
            if ruta.exists():
                datos[(config, conj)] = {x["id"]: x for x in map(json.loads, open(ruta, encoding="utf-8"))}
            else:
                faltan.append(ruta.name)
    if faltan:
        print(f"faltan {len(faltan)} archivos; las filas incompletas no se muestran:")
        for f in faltan:
            print("  ", f)
    completas = [c for c in nombres if all((c, conj) in datos for _, conj in CONJUNTOS)]
    if "completo" not in completas:
        print("falta la v4 completa")
        return 1
    casos = {conj: [json.loads(l) for l in open(datos_dir / f"{conj}.jsonl", encoding="utf-8")]
             for _, conj in CONJUNTOS}
    # Cada configuración corre sobre los mismos prompts del sistema completo salvo uno.
    for config in completas:
        commits = {x.get("commit") for (c, _), d in datos.items() if c == config for x in d.values()}
        if len(commits) > 1:
            print(f"*** {config} mezcla filas de {len(commits)} commits: {sorted(map(str, commits))} ***")

    def global_(config, f=lambda x: x["acierto_conjunto"]):
        return {f"{conj}:{i}": bool(f(x)) for _, conj in CONJUNTOS
                for i, x in datos[(config, conj)].items()}

    base, base_e = global_("completo"), global_("completo", estricto)
    nb, nbe = sum(base.values()), sum(base_e.values())

    print("=" * 100)
    print(f"1 · CADA TÉCNICA QUITADA CONTRA LA V4 COMPLETA ({nb}/180, estricto {nbe})")
    print("=" * 100)
    for config, tecnica, agente, mec in CONFIGS:
        if config not in completas:
            continue
        otra, otra_e = global_(config), global_(config, estricto)
        no, noe = sum(otra.values()), sum(otra_e.values())
        completo_gana, abl_gana, p = mcnemar(otra, base)
        ce, ae, pe = mcnemar(otra_e, base_e)
        marca = "dentro del ruido" if abs(no - nb) <= RUIDO else ""
        print(f"  {config:26} {agente} {mec:7} {no:3}  Δ {no - nb:+3}  completo gana {completo_gana:2}, "
              f"sin ella gana {abl_gana:2}, p = {p:.3g}  {marca}")
        print(f"  {'':26} {tecnica}; estricto {noe:3}  Δ {noe - nbe:+3}  ({ce} a {ae}, p = {pe:.3g})")

    print()
    print("=" * 100)
    print("2 · POR MECANISMO")
    print("=" * 100)
    # Plantilla sin ambiguos: el nombre exacto (M1) y el abreviado reparten los casos; "otro
    # ramo antes" (M2) cruza a ambos. El período (M3) y las redactadas, en los 180.
    clase = {}
    for _, conj in CONJUNTOS[:2]:
        for i, c in enumerate(casos[conj]):
            ref = D.mencion_consultada(c["pregunta_prosa"]) or ""
            if D.es_ambigua(ref):
                continue
            obj = c["ramo_objetivo"]["codigo"]
            cl = ["exacto (M1)" if D.norm(ref) == D.NOMBRES_NORM[obj] else "abreviado"]
            if any(m in c["pregunta_prosa"].lower() for m in D.MARCAS_MENCION):
                cl.append("otro ramo antes (M2)")
            clase[f"{conj}:{i}"] = cl
    cols = ("exacto (M1)", "abreviado", "otro ramo antes (M2)")
    n_cl = {k: sum(k in v for v in clase.values()) for k in cols}
    print(f"  {'':26}" + "".join(f"{f'{k} ({n_cl[k]})':>26}" for k in cols)
          + f"{'período (180)':>15}{'redactadas':>12}")
    for config in ["completo"] + [c for c, *_ in CONFIGS if c in completas]:
        ramo = global_(config, lambda x: x["acierto_ramo"])
        per = global_(config, lambda x: x["acierto_periodo"])
        conjs = global_(config)
        fila = [sum(ramo[k] for k, v in clase.items() if col in v) for col in cols]
        red = sum(v for k, v in conjs.items() if k.startswith("redactados:"))
        print(f"  {config:26}" + "".join(f"{n:>26}" for n in fila)
              + f"{sum(per.values()):>15}{red:>12}")

    print()
    print("=" * 100)
    print("3 · RAMAS ACTIVADAS (casos), LLAMADAS Y SEGUNDOS POR CASO")
    print("=" * 100)
    for config in ["completo"] + [c for c, *_ in CONFIGS if c in completas]:
        xs = [x for _, c in CONJUNTOS for x in datos[(config, c)].values()]
        ramas = {k: sum(1 for x in xs if x["ramas"].get(k)) for k in xs[0]["ramas"]}
        activas = "  ".join(f"{k} {v}" for k, v in ramas.items() if v)
        print(f"  {config:26} {sum(x['llamadas'] for x in xs) / len(xs):4.1f} llamadas  "
              f"{sum(x['segundos_total'] for x in xs) / len(xs):4.1f} s   {activas}")

    print()
    print("=" * 100)
    print("4 · BASELINE DE PROMPTING DIRECTO")
    print("=" * 100)
    for config in ("zero_shot", "few_shot"):
        if config in completas:
            g = global_(config)
            red = sum(v for k, v in g.items() if k.startswith("redactados:"))
            print(f"  {config:26} {sum(g.values()):3}/180   redactadas {red}/60")

    print()
    print("=" * 100)
    print("5 · ACIERTO DE RAMO CUANDO EL RAMO CONSULTADO LLEVA NÚMERO (PROTOCOLO_ABLACIONES_B.md)")
    print("=" * 100)
    numerados = {f"{conj}:{i}" for _, conj in CONJUNTOS for i, c in enumerate(casos[conj])
                 if CON_NUMERO.search(c["ramo_objetivo"]["nombre"])}
    print(f"  {len(numerados)} de 180 casos")
    for config in ("completo", "sin_regla_numeros", "sin_regla_siglas", "top1"):
        if config in completas:
            ramo = global_(config, lambda x: x["acierto_ramo"])
            print(f"  {config:26} ramo {sum(ramo[k] for k in numerados):3}/{len(numerados)}   "
                  f"resto {sum(v for k, v in ramo.items() if k not in numerados):3}"
                  f"/{180 - len(numerados)}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
