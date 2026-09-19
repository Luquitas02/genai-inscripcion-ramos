# -*- coding: utf-8 -*-
"""
Ablación del paso 3 — Deliverable 2.

Por qué existe. La primera corrida de la grilla dio `condicional` en los 240 casos. Se
diagnosticó que el prompt del paso 3 solo nombraba ese desenlace, se reescribió como un
procedimiento ordenado de ocho condiciones y se le agregaron ejemplos. La segunda corrida
volvió a colapsar, ahora citando `R-EXCEPCION-PRERREQ` en los 60 casos aun con la ficha
perfecta delante.

O sea que la primera explicación era incompleta. En vez de adivinar por tercera vez, esto
mide. Corre SOLO el paso 3, con la ficha verdadera de cada caso, bajo cuatro versiones del
prompt. Son 60 llamadas cortas por versión, unos dos minutos cada una.

La hipótesis a falsar: el bloque de reglas globales domina por posición. Es la última prosa
que el modelo lee, su frase más larga dice "en ese caso la respuesta es condicional", y es la
única del mensaje de usuario que nombra un valor de decisión. Además es redundante, porque el
procedimiento del mensaje de sistema ya trae los umbrales y `creditos_semestre` ya incorpora
la regla de las prácticas.

Esta ablación es también la sección de "estrategias alternativas evaluadas" que el documento
técnico exige.

Uso:
    python ablacion_p3.py                  # las cuatro versiones
    python ablacion_p3.py --modelo-falso   # prueba local sin GPU
"""

import argparse
import collections
import json
import time
from pathlib import Path

from verificador import Verificador, RUTA_MALLA
from ficha import construir_ficha, RUTA_CASOS
import pipeline as PL

BASE = Path(__file__).resolve().parent.parent
RESULTADOS = BASE / "resultados"
MODELO_POR_DEFECTO = "microsoft/Phi-3.5-mini-instruct"

# nombre -> (con_reglas, con_ejemplos)
VERSIONES = {
    "completo":      (True,  True),    # lo que corrió en la grilla 2
    "sin_reglas":    (False, True),    # la hipótesis principal
    "sin_ejemplos":  (True,  False),   # aísla el efecto de los ejemplos
    "minimo":        (False, False),   # solo ficha, procedimiento e identificadores
}


def correr_version(modelo, casos, v, malla, nombre, salida):
    con_reglas, con_ejemplos = VERSIONES[nombre]
    hechos = set()
    if salida.exists():
        with open(salida, encoding="utf-8") as fh:
            hechos = {json.loads(l)["id"] for l in fh if l.strip()}
    with open(salida, "a", encoding="utf-8") as fh:
        for i, caso in enumerate(casos):
            if str(i) in hechos:
                continue
            f = construir_ficha(v, caso["historial"], caso["consulta"]["ramos"][0],
                                caso["consulta"]["periodo"],
                                caso["consulta"]["creditos_ya_inscritos"])
            mensajes = PL.prompt_paso3(f, malla, con_reglas=con_reglas,
                                       con_ejemplos=con_ejemplos)
            t0 = time.perf_counter()
            crudo, tokens = modelo.generar(mensajes)
            seg = time.perf_counter() - t0
            p3 = PL.parsear_paso3(crudo, PL.identificadores_validos(f))
            fila = {
                "id": str(i), "version": nombre, "nivel": caso["nivel"],
                "constructor": caso["constructor"], "esperado": caso["respuesta"],
                "prediccion": p3, "crudo": crudo, "tokens": tokens, "segundos": seg,
                "acierto_decision": p3["decision"] == caso["respuesta"]["decision"],
                "acierto_regla": p3["regla"] == caso["respuesta"]["regla"],
            }
            fila["acierto_conjunto"] = fila["acierto_decision"] and fila["acierto_regla"]
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
            fh.flush()


def resumen():
    print()
    print("=" * 96)
    print("ABLACION DEL PASO 3   ·   ficha perfecta   ·   60 casos   ·   techo demostrado 60/60")
    print("=" * 96)
    print(f"{'version':16} {'decision':>9} {'regla':>8} {'ambas':>8}   "
          f"{'reparto de decisiones':38} {'tok':>6}")
    print("-" * 96)
    for nombre in VERSIONES:
        f = RESULTADOS / f"ablacion_p3__{nombre}.raw.jsonl"
        if not f.exists():
            continue
        r = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
        if not r:
            continue
        n = len(r)
        pct = lambda k: 100 * sum(x[k] for x in r) / n            # noqa: E731
        d = collections.Counter(str(x["prediccion"]["decision"]) for x in r)
        reparto = "  ".join(f"{k} {v}" for k, v in sorted(d.items(), key=lambda z: -z[1]))
        print(f"{nombre:16} {pct('acierto_decision'):8.1f}% {pct('acierto_regla'):7.1f}% "
              f"{pct('acierto_conjunto'):7.1f}%   {reparto:38} "
              f"{sum(x['tokens'] for x in r) / n:6,.0f}")
    print()
    print("correcto: sí 18 · no 21 · condicional 21   |   piso trivial del conjunto: 30,0 %")
    print()
    print("reglas más citadas por versión:")
    for nombre in VERSIONES:
        f = RESULTADOS / f"ablacion_p3__{nombre}.raw.jsonl"
        if not f.exists():
            continue
        r = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
        c = collections.Counter(str(x["prediccion"]["regla"]) for x in r).most_common(4)
        print(f"  {nombre:16} " + "   ".join(f"{k} {v}" for k, v in c))


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

    if args.modelo_falso:
        from runner_d2 import ModeloFalso
        modelo = ModeloFalso(['{"decision": "no", "regla": "R-TOPE-MAX"}'])
    else:
        from runner import ModeloHF
        modelo = ModeloHF(args.modelo, max_new_tokens=256)

    RESULTADOS.mkdir(exist_ok=True)
    for nombre in VERSIONES:
        salida = RESULTADOS / f"ablacion_p3__{nombre}.raw.jsonl"
        print(f"version {nombre}  ({len(casos)} casos)")
        correr_version(modelo, casos, v, malla, nombre, salida)
    resumen()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
