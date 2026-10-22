# -*- coding: utf-8 -*-
"""
La demostración del video del Deliverable 3.

Corre en vivo, con Phi, los tres casos que eligió la regla de PROTOCOLO_D3.md sobre la
corrida final, y muestra cada mensaje entre agentes y herramientas. Cada salida del modelo se
compara con la traza guardada en `trazas/`: con generación greedy y los mismos prompts tiene que
salir igual, y la marca `= guardada` lo muestra mensaje por mensaje.

  1. directo    redactado 0   "¿todavía se puede meter progra este semestre...?"
  2. decisión   redactado 3   "¿me dejan inscribir inglés básico 1 ahora en el segundo semestre...?"
  3. falla      redactado 16  "...quería tomar marketing el otro semestre, en marzo..."

    import demo_d3; demo_d3.video(modelo)       # en Colab, con el modelo cargado
    python demo_d3.py --pruebas                  # sin GPU: reproduce las trazas guardadas
"""

import json
import sys
from pathlib import Path

import orquestador as O
import ver_traza as V
from verificador import Verificador

RAIZ = Path(__file__).resolve().parent.parent
CONJUNTO = "casos_redactados"
TRAZA = RAIZ / "trazas" / f"agentes__Phi-3.5-mini-instruct__completo__{CONJUNTO}.jsonl"
CASOS = [
    (0, "caso directo: pasa por los tres agentes sin volver atrás"),
    (3, "caso con decisión: el Verificador rechaza el período y el tope cierra el caso"),
    (16, "caso de falla: un rechazo del Verificador deshace un acierto del Intérprete"),
]


def _casos():
    return [json.loads(l) for l in open(RAIZ / "datos" / f"{CONJUNTO}.jsonl", encoding="utf-8")]


def _marcas(vivos, guardados):
    """`= guardada` si la salida del modelo es la misma de la corrida final."""
    marcas = []
    for k, m in enumerate(vivos):
        if not m.get("crudo"):
            marcas.append("")
            continue
        g = guardados[k] if k < len(guardados) else {}
        marcas.append("= guardada" if g.get("crudo") == m["crudo"] else "≠ guardada")
    return marcas


def correr(modelo, i, titulo, v, casos, prompts):
    caso = dict(casos[i], id=str(i))
    print("=" * 110)
    print(f"{titulo}  ·  redactado {i}")
    print("=" * 110)
    fila, mensajes = O.correr_caso(modelo, caso, v, "completo", prompts)
    guardados = V.leer(TRAZA, i)
    marcas = _marcas(mensajes, guardados)
    V.imprimir(mensajes, marcas=marcas)
    esp = caso["respuesta"]
    pred = fila["prediccion"]
    print(f"\n    esperado: {esp['decision']} / {esp['regla']}   ·   sistema: "
          f"{pred['decision']} / {pred['regla']}   ·   "
          f"{'ACIERTA' if fila['acierto_conjunto'] else 'FALLA'}   ·   "
          f"{fila['llamadas']} llamadas, {fila['segundos_total']:.1f} s\n")
    return marcas


def video(modelo):
    v = Verificador()
    casos = _casos()
    prompts = O.cargar_prompts("completo")
    todas = []
    for i, titulo in CASOS:
        todas += [m for m in correr(modelo, i, titulo, v, casos, prompts) if m]
    iguales = sum(m == "= guardada" for m in todas)
    print(f"{iguales} de {len(todas)} salidas del modelo iguales a la corrida final")
    return iguales == len(todas)


class ModeloRepetidor:
    """Devuelve, en orden, las salidas guardadas en la traza. Prueba la demo sin GPU."""

    nombre = "repetidor"

    def __init__(self, crudos):
        self.crudos = list(crudos)

    def generar(self, mensajes):
        return self.crudos.pop(0), 0


def _pruebas():
    # Esta demo reproduce las trazas de la v4 con el código y los prompts de la v4. Desde la
    # v5 el orquestador y los prompts cambiaron, así que solo corre en el commit de la v4,
    # que es el que fija demo_d3_colab.ipynb.
    if getattr(O, "VERSION", "v4") != "v4":
        print(f"Esta es la demo de la v4 y el código es {O.VERSION}. Córrela en el commit "
              "b145da9 (git checkout b145da9), que es el que clona demo_d3_colab.ipynb.")
        return 1
    v = Verificador()
    casos = _casos()
    prompts = O.cargar_prompts("completo")
    ok = True
    for i, titulo in CASOS:
        crudos = [m["crudo"] for m in V.leer(TRAZA, i) if m.get("crudo")]
        marcas = correr(ModeloRepetidor(crudos), i, titulo, v, casos, prompts)
        ok &= all(m in ("", "= guardada") for m in marcas)
    print("TODO EN ORDEN" if ok else "[FALLA] la demo no reproduce las trazas guardadas")
    return 0 if ok else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--pruebas" in sys.argv:
        raise SystemExit(_pruebas())
    print(__doc__)
