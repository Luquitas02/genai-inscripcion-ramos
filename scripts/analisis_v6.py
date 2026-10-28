# -*- coding: utf-8 -*-
"""
Compara la v6 con la v4 caso por caso (PLAN_V6.md).

Fase de desarrollo: los 403 casos ya usados. Sirve para ajustar el prompt del Resolvedor, así
que además del resumen lista los casos que cambian en cada dirección, con la mención que extrajo
el Intérprete y lo que eligió cada versión.

    python analisis_v6.py --fase desarrollo --dir <carpeta con los .raw.jsonl de la v6>
    python analisis_v6.py --prueba          # sin GPU: la v4 contra sí misma da 0 a 0
"""

import argparse
import json
import sys
from pathlib import Path

from analisis_d3 import mcnemar

RAIZ = Path(__file__).resolve().parent.parent
RES = RAIZ / "resultados"
ETQ = "Phi-3.5-mini-instruct"
DESARROLLO = ["casos", "casos_nuevos", "casos_redactados", "casos_desarrollo",
              "casos_desarrollo_redactados", "plantilla_a", "plantilla_b", "redactados"]


def leer(carpeta, config, conjuntos):
    """{(conjunto, id): fila} de una configuración."""
    filas = {}
    for conj in conjuntos:
        ruta = Path(carpeta) / f"agentes__{ETQ}__{config}__{conj}.raw.jsonl"
        for l in open(ruta, encoding="utf-8"):
            if l.strip():
                x = json.loads(l)
                filas[(conj, str(x["id"]))] = x
    return filas


def comparar(v4, v6):
    """Resumen de v6 contra v4 sobre los casos que están en las dos."""
    ids = sorted(set(v4) & set(v6))
    conj4 = {i: bool(v4[i]["acierto_conjunto"]) for i in ids}
    conj6 = {i: bool(v6[i]["acierto_conjunto"]) for i in ids}
    ramo4 = {i: bool(v4[i]["acierto_ramo"]) for i in ids}
    ramo6 = {i: bool(v6[i]["acierto_ramo"]) for i in ids}
    gana6, gana4, p = mcnemar(conj4, conj6)
    rgana6, rgana4, rp = mcnemar(ramo4, ramo6)
    ramas = [v6[i]["ramas"] for i in ids]
    return {
        "casos": len(ids),
        "v4": sum(conj4.values()), "v6": sum(conj6.values()),
        "solo_v6": gana6, "solo_v4": gana4, "p": p,
        "ramo_v4": sum(ramo4.values()), "ramo_v6": sum(ramo6.values()),
        "ramo_solo_v6": rgana6, "ramo_solo_v4": rgana4, "ramo_p": rp,
        "atajo_exacto": sum(r.get("atajo_exacto", False) for r in ramas),
        "rechazos": sum(r["rechazos_verificador"] for r in ramas),
        "llamadas_v4": sum(v4[i]["llamadas"] for i in ids) / max(len(ids), 1),
        "llamadas_v6": sum(v6[i]["llamadas"] for i in ids) / max(len(ids), 1),
        "cambian": [(i, conj4[i], conj6[i]) for i in ids if conj4[i] != conj6[i]],
    }


def imprimir(r, v4, v6):
    print(f"{r['casos']} casos · acierto conjunto v4 {r['v4']} · v6 {r['v6']}")
    print(f"  solo v6 {r['solo_v6']} a solo v4 {r['solo_v4']} · McNemar exacto p = {r['p']:.3g}")
    print(f"  ramo: v4 {r['ramo_v4']} · v6 {r['ramo_v6']} · {r['ramo_solo_v6']} a "
          f"{r['ramo_solo_v4']} (p = {r['ramo_p']:.3g})")
    print(f"  atajo exacto en {r['atajo_exacto']} casos · {r['rechazos']} rechazos · "
          f"llamadas por caso {r['llamadas_v4']:.2f} → {r['llamadas_v6']:.2f}")
    for titulo, quien in (("gana la v6", True), ("gana la v4", False)):
        casos = [i for i, a4, a6 in r["cambian"] if a6 == quien]
        if casos:
            print(f"\n{titulo} ({len(casos)}):")
        for i in casos:
            f4, f6 = v4[i], v6[i]
            print(f"  {i[0]} {i[1]}: objetivo {f6['ramo_objetivo']['nombre']} · "
                  f"v4 {f4['extraccion']} · v6 {f6['extraccion']}\n      {f6['pregunta']}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--fase", choices=["desarrollo"], default="desarrollo")
    ap.add_argument("--dir", default=None, help="carpeta con los resultados de la v6")
    ap.add_argument("--prueba", action="store_true")
    args = ap.parse_args()
    v4 = leer(RES, "completo", DESARROLLO)
    if args.prueba:
        r = comparar(v4, v4)
        print(f"{r['solo_v6']} a {r['solo_v4']} · {r['casos']} casos")
        return 0 if (r["solo_v6"], r["solo_v4"], r["casos"]) == (0, 0, 403) else 1
    if not args.dir:
        ap.error("falta --dir")
    v6 = leer(args.dir, "v6", DESARROLLO)
    r = comparar(v4, v6)
    imprimir(r, v4, v6)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
