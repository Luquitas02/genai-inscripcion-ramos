# -*- coding: utf-8 -*-
"""
Ablación del paso 1 — Deliverable 2.

Por qué existe. Los ejemplos resueltos se agregaron al paso 1 por paridad con el baseline,
que es la condición few-shot. Al comparar las dos corridas de la grilla apareció que el
acierto del ramo BAJÓ: 31 de 60 sin ejemplos, 27 de 60 con ellos. Son cuatro casos sobre
sesenta, poco para concluir, y además las dos corridas cambiaron más de una cosa a la vez.

Esto lo aísla. Corre SOLO el paso 1, con y sin ejemplos, sobre los mismos 60 casos. Es la
llamada más barata del pipeline, así que las dos versiones toman unos tres minutos.

El paso 1 es el cuello de botella del sistema: todo lo que venga después trabaja sobre el
ramo que este paso eligió, y si eligió mal, el caso está perdido.

Uso:
    python ablacion_p1.py
    python ablacion_p1.py --modelo-falso --limite 2    # prueba local, sin GPU
"""

import argparse
import collections
import json
import time
from pathlib import Path

from verificador import Verificador, RUTA_MALLA
from ficha import RUTA_CASOS
import pipeline as PL

BASE = Path(__file__).resolve().parent.parent
RESULTADOS = BASE / "resultados"
MODELO_POR_DEFECTO = "microsoft/Phi-3.5-mini-instruct"

VERSIONES = {"con_ejemplos": True, "sin_ejemplos": False}

# Las tres formas en que el conjunto de prueba nombra el ramo, veinte casos cada una.
RASGOS_NOMBRE = ("nombre_completo", "nombre_abreviado", "coloquial")


def correr_version(modelo, casos, malla, codigos, nombre, salida):
    con_ejemplos = VERSIONES[nombre]
    hechos = set()
    if salida.exists():
        with open(salida, encoding="utf-8") as fh:
            hechos = {json.loads(l)["id"] for l in fh if l.strip()}
    with open(salida, "a", encoding="utf-8") as fh:
        for i, caso in enumerate(casos):
            if str(i) in hechos:
                continue
            mensajes = PL.prompt_paso1(caso, malla, con_ejemplos=con_ejemplos)
            t0 = time.perf_counter()
            crudo, tokens = modelo.generar(mensajes)
            seg = time.perf_counter() - t0
            p1 = PL.parsear_paso1(crudo, codigos)
            esperado = caso["consulta"]["ramos"][0]
            fila = {
                "id": str(i), "version": nombre, "nivel": caso["nivel"],
                "rasgos": caso["rasgos"], "pregunta": caso["pregunta_prosa"],
                "esperado_ramo": esperado, "esperado_periodo": caso["consulta"]["periodo"],
                "parseado": p1, "crudo": crudo, "tokens": tokens, "segundos": seg,
                "acierto_ramo": p1["ramo"] == esperado,
                "acierto_periodo": p1["periodo"] == caso["consulta"]["periodo"],
                "devolvio_codigo_valido": p1["ramo"] is not None,
            }
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
            fh.flush()


def resumen():
    print()
    print("=" * 92)
    print("ABLACION DEL PASO 1   ·   extraccion de ramo y periodo   ·   60 casos")
    print("=" * 92)
    print(f"{'version':16} {'ramo':>8} {'periodo':>9} {'ambos':>8}   "
          + "  ".join(f"{r:>17}" for r in RASGOS_NOMBRE))
    print("-" * 92)
    for nombre in VERSIONES:
        f = RESULTADOS / f"ablacion_p1__{nombre}.raw.jsonl"
        if not f.exists():
            continue
        r = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
        if not r:
            continue
        n = len(r)
        ramo = 100 * sum(x["acierto_ramo"] for x in r) / n
        per = 100 * sum(x["acierto_periodo"] for x in r) / n
        amb = 100 * sum(x["acierto_ramo"] and x["acierto_periodo"] for x in r) / n
        por_rasgo = []
        for rasgo in RASGOS_NOMBRE:
            sub = [x for x in r if rasgo in x["rasgos"]]
            por_rasgo.append(f"{sum(x['acierto_ramo'] for x in sub)}/{len(sub)}"
                             if sub else "-")
        print(f"{nombre:16} {ramo:7.1f}% {per:8.1f}% {amb:7.1f}%   "
              + "  ".join(f"{p:>17}" for p in por_rasgo))
    print()
    print("cuando falla el ramo, ¿devuelve algo invalido o el codigo de otra asignatura?")
    for nombre in VERSIONES:
        f = RESULTADOS / f"ablacion_p1__{nombre}.raw.jsonl"
        if not f.exists():
            continue
        r = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
        malos = [x for x in r if not x["acierto_ramo"]]
        invalido = sum(1 for x in malos if not x["devolvio_codigo_valido"])
        print(f"  {nombre:16} {len(malos)} fallas: {invalido} invalidas, "
              f"{len(malos) - invalido} codigos de otra asignatura")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default=MODELO_POR_DEFECTO)
    ap.add_argument("--modelo-falso", action="store_true")
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--solo-resumen", action="store_true")
    args = ap.parse_args()

    if args.solo_resumen:
        resumen()
        return 0

    v = Verificador()
    malla = json.load(open(RUTA_MALLA, encoding="utf-8"))
    casos = [json.loads(l) for l in open(RUTA_CASOS, encoding="utf-8") if l.strip()]
    if args.limite:
        casos = casos[:args.limite]
    codigos = set(v.asig)

    if args.modelo_falso:
        from runner_d2 import ModeloFalso
        modelo = ModeloFalso(['{"ramo": "503203", "periodo": "actual"}'])
    else:
        from runner import ModeloHF
        modelo = ModeloHF(args.modelo, max_new_tokens=64)

    RESULTADOS.mkdir(exist_ok=True)
    for nombre in VERSIONES:
        salida = RESULTADOS / f"ablacion_p1__{nombre}.raw.jsonl"
        print(f"version {nombre}  ({len(casos)} casos)")
        correr_version(modelo, casos, malla, codigos, nombre, salida)
    resumen()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
