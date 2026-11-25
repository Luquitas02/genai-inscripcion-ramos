# -*- coding: utf-8 -*-
"""
Separación entre los datos de entrenamiento del D4 y la prueba sellada, demostrada (criterio
"Training data" de la rúbrica). Fijado en `PLAN_D4.md` antes de generar los datos:

  1. Ningún par de entrenamiento comparte historial y consulta con un caso de prueba.
  2. Ninguna pregunta de entrenamiento es igual ni casi igual (difflib > 0,85) a una de prueba.
  3. Solapamiento de 6-gramas de palabras: qué fracción de los 6-gramas de cada pregunta de
     prueba aparece en el entrenamiento, comparada con la fracción que aparece en el RESTO de
     la propia prueba (dejando fuera la pregunta). Si el entrenamiento no se parece a la
     prueba más de lo que la prueba se parece a sí misma, no hay fuga de redacción.

Imprime solo cifras: no muestra texto de la prueba.

    python separacion_d4.py            -> imprime y escribe datos/entrenamiento_d4/separacion.json
"""

import difflib
import json
import re
import sys
from pathlib import Path

from preparar_prueba_v5 import clave

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
UMBRAL = 0.85
N = 6


def leer_jsonl(ruta):
    return [json.loads(l) for l in open(ruta, encoding="utf-8") if l.strip()]


def palabras(t):
    return re.findall(r"\w+", t.lower())


def ngramas(t):
    p = palabras(t)
    return {tuple(p[i:i + N]) for i in range(len(p) - N + 1)}


def main():
    prueba = leer_jsonl(DATOS / "prueba_d4" / "plantilla.jsonl") + \
        leer_jsonl(DATOS / "prueba_d4" / "redactados.jsonl")
    pares = leer_jsonl(DATOS / "entrenamiento_d4" / "entrenamiento.jsonl") + \
        leer_jsonl(DATOS / "entrenamiento_d4" / "validacion.jsonl")
    ent_q = [p["meta"]["pregunta"] for p in pares]
    ent_k = {p["meta"]["clave"] for p in pares if "clave" in p["meta"]}
    pru_q = [c["pregunta_prosa"] for c in prueba]
    pru_k = [clave(c) for c in prueba]

    r = {"casos_prueba": len(prueba), "pares_entrenamiento": len(pares)}
    r["1_mismo_historial_y_consulta"] = sum(k in ent_k for k in pru_k)

    iguales, casi, maximo = 0, 0, 0.0
    ent_l = [q.lower() for q in ent_q]
    ent_set = set(ent_l)
    for q in pru_q:
        ql = q.lower()
        iguales += ql in ent_set
        sm = difflib.SequenceMatcher(None, ql, autojunk=False)
        mejor = 0.0
        for e in ent_l:
            sm.set_seq2(e)
            if sm.real_quick_ratio() <= mejor or sm.quick_ratio() <= mejor:
                continue
            mejor = max(mejor, sm.ratio())
        maximo = max(maximo, mejor)
        casi += mejor > UMBRAL
    r["2_preguntas_iguales"] = iguales
    r[f"2_preguntas_casi_iguales_difflib_mayor_{UMBRAL}"] = casi
    r["2_similitud_maxima"] = round(maximo, 3)

    ent_ng = set().union(*(ngramas(q) for q in ent_q))
    pru_ng = [ngramas(q) for q in pru_q]
    cuenta = {}
    for g in (g for s in pru_ng for g in s):
        cuenta[g] = cuenta.get(g, 0) + 1
    con = [s for s in pru_ng if s]
    frac_ent = sum(len(s & ent_ng) / len(s) for s in con) / len(con)
    # resto de la prueba: un 6-grama cuenta si aparece en otra pregunta de prueba
    frac_resto = sum(sum(1 for g in s if cuenta[g] > 1) / len(s) for s in con) / len(con)
    r["3_preguntas_de_prueba_con_6gramas"] = len(con)
    r["3_fraccion_6gramas_en_entrenamiento"] = round(frac_ent, 4)
    r["3_fraccion_6gramas_en_resto_de_la_prueba"] = round(frac_resto, 4)

    (DATOS / "entrenamiento_d4" / "separacion.json").write_text(
        json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    for k, v in r.items():
        print(f"{k:50} {v}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
