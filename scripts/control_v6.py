# -*- coding: utf-8 -*-
"""
Control de reproducibilidad antes de cada corrida de la v6 en Colab.

Corre la v4 (`completo`) sobre los casos 0 a 9 de los originales y compara cada salida del
modelo con la traza guardada de la corrida final. Con generación greedy, el mismo modelo, los
mismos prompts y las mismas versiones de librerías tiene que salir igual. Si no sale igual, la
máquina de Colab no es comparable con la que midió la v4, y no se sigue: una diferencia entre
v4 y v6 podría venir de la máquina y no del cambio.

    python control_v6.py --modelo-falso      # sin GPU: repite las salidas guardadas
"""

import argparse
import json
import sys
from pathlib import Path

import orquestador as O
import ver_traza as V
from demo_d3 import ModeloRepetidor, _marcas
from verificador import Verificador

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "datos" / "casos.jsonl"
TRAZA = RAIZ / "trazas" / "agentes__Phi-3.5-mini-instruct__completo__casos.jsonl"
N = 10


def controlar(modelo=None):
    """Cuántos de los casos 0 a N-1 dan todas sus salidas iguales a la traza guardada.

    Sin modelo usa un repetidor de las salidas guardadas, que es la autoprueba sin GPU."""
    v = Verificador()
    prompts = O.cargar_prompts("completo")
    casos = [json.loads(l) for l in open(CASOS, encoding="utf-8")][:N]
    iguales = 0
    for i, caso in enumerate(casos):
        guardados = V.leer(TRAZA, i)
        m = modelo or ModeloRepetidor([g["crudo"] for g in guardados if g.get("crudo")])
        _, mensajes = O.correr_caso(m, dict(caso, id=str(i)), v, "completo", prompts)
        marcas = [x for x in _marcas(mensajes, guardados) if x]
        llamadas_guardadas = sum(1 for g in guardados if g.get("crudo"))
        ok = len(marcas) == llamadas_guardadas and all(x == "= guardada" for x in marcas)
        iguales += ok
        if not ok:
            print(f"caso {i}: {marcas.count('= guardada')} de {llamadas_guardadas} salidas iguales")
    print(f"{iguales} de {N} casos iguales a la v4")
    return iguales


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo-falso", action="store_true")
    args = ap.parse_args()
    modelo = None
    if not args.modelo_falso:
        from runner_d3 import cargar_modelo
        modelo = cargar_modelo()
    return 0 if controlar(modelo) == N else 1


if __name__ == "__main__":
    raise SystemExit(main())
