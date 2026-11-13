# -*- coding: utf-8 -*-
"""
Genera `prompts/d4/interprete_muchos_ejemplos.md`: el control del D4 en el PILOTO.

Es el prompt v3 del Intérprete sin otro cambio que el bloque de ejemplos: a los 4 ejemplos
escritos a mano se suman N pares del mismo tipo de los que se usan para entrenar
(`datos_d4.generar_pares`, otra semilla). Así el control y el ajuste ven el mismo tipo de
ejemplos, uno en el prompt y el otro en los pesos (Lecture 8, láminas 2 y 24).

    python gen_prompt_control_d4.py --n 40
"""

import argparse
import json
import sys
from pathlib import Path

from datos_d4 import generar_pares

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
ORIGEN = PROMPTS / "interprete.md"
DESTINO = PROMPTS / "d4" / "interprete_muchos_ejemplos.md"
FIN = "<!-- /ejemplos -->"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--semilla", type=int, default=20261115)
    a = ap.parse_args()
    texto = ORIGEN.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert texto.count(FIN) == 1
    extra = []
    for p in generar_pares(a.n, a.semilla):
        extra.append(f'Consulta: "{p["meta"]["pregunta"]}"\n{p["completion"][0]["content"]}\n')
    cabecera = (f"<!-- control del D4 (piloto): prompt v3 del Intérprete con {a.n} ejemplos más,\n"
                f"     generados por scripts/gen_prompt_control_d4.py (semilla {a.semilla}). -->\n")
    nuevo = cabecera + texto.replace(FIN, "\n".join(extra) + FIN)
    DESTINO.parent.mkdir(exist_ok=True)
    DESTINO.write_text(nuevo, encoding="utf-8", newline="\n")
    print(f"{DESTINO.relative_to(PROMPTS.parent)}: 4 + {a.n} ejemplos")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
