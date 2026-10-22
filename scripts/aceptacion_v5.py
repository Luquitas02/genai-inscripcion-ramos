# -*- coding: utf-8 -*-
"""
Aplica la regla para aceptar la versión 5 — Deliverable 3.

La regla se escribió en PLAN_D3.md ("Versión 5", "Regla para aceptar la v5") antes de correr
la v5. Compara la v5 con la v4 sobre los 223 casos de desarrollo: el desarrollo de la v4 (52 +
21) y los 150 de prueba de la v4, que para la v5 son desarrollo porque de sus trazas salió el
diagnóstico. No llama a ningún modelo: lee los resultados guardados.

  v4   resultados/agentes__Phi-3.5-mini-instruct__completo__<conjunto>.raw.jsonl
  v5   resultados/v5/agentes__Phi-3.5-mini-instruct__<config>__<conjunto>.raw.jsonl

La v5 se acepta si cumple todo:
  1. acierto conjunto mayor que el de la v4 (196) y estricto mayor que el de la v4 (180)
  2. período igual o mayor que el de la v4 (206)
  3. ningún conjunto baja más de 2 casos en acierto conjunto
  4. ninguna corrección ni rechazo del Verificador convierte en error un caso que la v4
     acertaba estricto
  5. el Resolvedor se aparta del primer candidato de T1 sin acertar en menos casos que la v4 (11)

    python aceptacion_v5.py
    python aceptacion_v5.py --config completo --dir resultados/v5
"""

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MODELO = "Phi-3.5-mini-instruct"
DESARROLLO = ["casos", "casos_nuevos", "casos_redactados", "casos_desarrollo",
              "casos_desarrollo_redactados"]
MAX_BAJA_POR_CONJUNTO = 2


def cargar(ruta):
    return {x["id"]: x for x in map(json.loads, open(ruta, encoding="utf-8")) if x}


def estricto(x):
    return bool(x["acierto_conjunto"] and x["acierto_ramo"] and x["acierto_periodo"])


def top1_inicial_v4(conjunto):
    """El primer candidato de la primera búsqueda de T1 en la v4, desde su traza."""
    top = {}
    ruta = RAIZ / "trazas" / f"agentes__{MODELO}__completo__{conjunto}.jsonl"
    for l in open(ruta, encoding="utf-8"):
        m = json.loads(l)
        if m["de"] == "T1" and m["caso"] not in top:
            top[m["caso"]] = m["contenido"]["candidatos"][0]["codigo"]
    return top


def desvio_sin_acierto(x, top):
    return top is not None and x["extraccion"]["ramo"] != top and not x["acierto_ramo"]


def intervino_verificador(x):
    r = x["ramas"]
    return bool(r.get("correcciones_periodo") or r.get("rechazos_mencion")
                or r.get("rechazos_codigo"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="completo")
    ap.add_argument("--dir", default=str(RAIZ / "resultados" / "v5"))
    a = ap.parse_args()

    tot = {"v4": {"conjunto": 0, "estricto": 0, "periodo": 0, "desvio": 0},
           "v5": {"conjunto": 0, "estricto": 0, "periodo": 0, "desvio": 0}}
    bajas, convertidos, cambios, n = [], [], [], 0
    print(f"{'conjunto':30} {'n':>4} {'v4':>5} {'v5':>5}   (acierto conjunto)")
    for conj in DESARROLLO:
        v4 = cargar(RAIZ / "resultados" / f"agentes__{MODELO}__completo__{conj}.raw.jsonl")
        ruta5 = Path(a.dir) / f"agentes__{MODELO}__{a.config}__{conj}.raw.jsonl"
        if not ruta5.exists():
            print(f"falta {ruta5}")
            return 2
        v5 = cargar(ruta5)
        if set(v5) != set(v4):
            print(f"{conj}: la v5 tiene {len(v5)} casos y la v4 {len(v4)}; corre el conjunto completo")
            return 2
        if any("t1_top1_inicial" not in x for x in v5.values()):
            # Sin ese campo los desvíos de T1 darían 0 sin haberse medido.
            print(f"{ruta5.name} no trae t1_top1_inicial: no son filas de la v5")
            return 2
        top4 = top1_inicial_v4(conj)
        c4 = sum(x["acierto_conjunto"] for x in v4.values())
        c5 = sum(x["acierto_conjunto"] for x in v5.values())
        print(f"{conj:30} {len(v4):4} {c4:5} {c5:5}")
        if c4 - c5 > MAX_BAJA_POR_CONJUNTO:
            bajas.append(f"{conj} baja {c4 - c5}")
        n += len(v4)
        for i in v4:
            x4, x5 = v4[i], v5[i]
            for etq, x, top in (("v4", x4, top4.get(i)), ("v5", x5, x5.get("t1_top1_inicial"))):
                tot[etq]["conjunto"] += x["acierto_conjunto"]
                tot[etq]["estricto"] += estricto(x)
                tot[etq]["periodo"] += x["acierto_periodo"]
                tot[etq]["desvio"] += desvio_sin_acierto(x, top)
            if estricto(x4) and not estricto(x5) and intervino_verificador(x5):
                convertidos.append(f"{conj} {i}")
            if x4["acierto_conjunto"] != x5["acierto_conjunto"] or estricto(x4) != estricto(x5):
                cambios.append((conj, i, x4, x5))

    t4, t5 = tot["v4"], tot["v5"]
    print(f"\n{'':30} {n:4}   v4    v5")
    for k, nombre in (("conjunto", "acierto conjunto"), ("estricto", "estricto (ramo y período)"),
                      ("periodo", "período"), ("desvio", "desvíos de T1 sin acertar")):
        print(f"{nombre:30} {'':4} {t4[k]:5} {t5[k]:5}")

    reglas = [
        ("1. conjunto mayor que la v4", t5["conjunto"] > t4["conjunto"]),
        ("1. estricto mayor que la v4", t5["estricto"] > t4["estricto"]),
        ("2. período igual o mayor que la v4", t5["periodo"] >= t4["periodo"]),
        (f"3. ningún conjunto baja más de {MAX_BAJA_POR_CONJUNTO}", not bajas),
        ("4. el Verificador no convierte aciertos estrictos en error", not convertidos),
        ("5. menos desvíos de T1 sin acertar que la v4", t5["desvio"] < t4["desvio"]),
    ]
    print()
    for nombre, ok in reglas:
        print(f"  [{'cumple' if ok else 'NO CUMPLE'}] {nombre}")
    for b in bajas:
        print(f"      {b}")
    for c in convertidos:
        print(f"      convertido por el Verificador: {c}")

    print("\nCasos que cambian respecto de la v4 (conjunto / estricto):")
    for conj, i, x4, x5 in cambios:
        marcas = " ".join(k for k, v in x5["ramas"].items() if v)
        print(f"  {conj:28} {i:>3}  v4 {int(x4['acierto_conjunto'])}/{int(estricto(x4))}  "
              f"v5 {int(x5['acierto_conjunto'])}/{int(estricto(x5))}  "
              f"{x5['extraccion']['ramo']} {x5['extraccion']['periodo']}  {marcas}")

    acepta = all(ok for _, ok in reglas)
    print(f"\n{'SE ACEPTA LA V5' if acepta else 'NO SE ACEPTA: queda una iteración (v5b), con la misma regla'}")
    return 0 if acepta else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
