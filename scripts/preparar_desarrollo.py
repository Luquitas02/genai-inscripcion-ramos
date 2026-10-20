# -*- coding: utf-8 -*-
"""
Conjunto de desarrollo — Deliverable 3.

Es el único conjunto que se mira mientras se ajustan los prompts de los agentes. Los tres de
prueba (originales, nuevos y escritos a mano) no se tocan hasta las corridas finales.

Usa el mismo generador con otra semilla y descarta los casos cuya pregunta ya aparece en un
conjunto de prueba. Sin ese filtro, ajustar sobre desarrollo sería ajustar sobre prueba: entre
originales y nuevos ya se repiten 7 preguntas.

    python preparar_desarrollo.py   -> datos/casos_desarrollo.jsonl
"""

import json
import sys
from pathlib import Path

from generador import Generador

DATOS = Path(__file__).resolve().parent.parent / "datos"
SEMILLA = 20261020
PRUEBA = ["casos.jsonl", "casos_nuevos.jsonl"]


def main():
    vistas = {json.loads(l)["pregunta_prosa"].strip().lower()
              for f in PRUEBA for l in open(DATOS / f, encoding="utf-8") if l.strip()}
    casos = Generador(seed=SEMILLA).generar_lote(n_por_nivel=20)
    nuevos = [c for c in casos if c["pregunta_prosa"].strip().lower() not in vistas]
    with open(DATOS / "casos_desarrollo.jsonl", "w", encoding="utf-8") as f:
        for c in nuevos:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"{len(casos)} generados, {len(casos) - len(nuevos)} descartados por repetir una "
          f"pregunta de prueba, {len(nuevos)} -> casos_desarrollo.jsonl")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
