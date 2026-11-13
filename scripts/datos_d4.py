# -*- coding: utf-8 -*-
"""
Pares de entrenamiento para el Intérprete (A) — Deliverable 4, versión del PILOTO.

Cada par es la entrada exacta que el Intérprete recibe en el sistema del D3 (su prompt v3, con
la pregunta en la sección de usuario) y la salida que debió dar. La salida correcta no la
escribe ningún modelo: la arma este script con lo que el generador sabe al escribir la
pregunta. El generador elige la forma en que nombra el ramo, los ramos de contexto que menciona
y la frase de período, así que la etiqueta es exactamente lo que el Intérprete debe copiar.

  {"accion": "entregar", "consultado": <cómo nombró el ramo>, "otros": [<ramos de contexto>],
   "frase_periodo": <la frase de período>, "periodo": "actual" | "proximo"}

En el piloto las preguntas son SOLO de plantilla. Sirve para probar que el entrenamiento corre
en una T4, no para el D4: el análisis previo mostró que con plantillas el ajuste aprendería
ocho frases de memoria. Los datos del D4 se deciden después del piloto.

Un par se descarta si su historial y consulta, o su pregunta, aparecen en cualquier conjunto de
evaluación o desarrollo (`preparar_piloto_d4.ANTERIORES` más el piloto).

    python datos_d4.py --n 500 --semilla 20261114 --salida ../datos/entrenamiento_piloto/
"""

import argparse
import json
import random
import sys
from pathlib import Path

import agentes as A
import generador as G
from preparar_prueba_v5 import clave, pregunta
from verificador import INSCRITA, REPROBADA, NO_CURSADA

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
EXCLUIR = ["casos.jsonl", "casos_nuevos.jsonl", "casos_redactados.jsonl",
           "casos_desarrollo.jsonl", "casos_desarrollo_redactados.jsonl",
           "prueba_v5/plantilla_a.jsonl", "prueba_v5/plantilla_b.jsonl",
           "prueba_v5/base_redactados.jsonl", "prueba_v5/redactados.jsonl",
           "piloto_d4/base.jsonl"]


class GeneradorEtiquetado(G.Generador):
    """El generador del D1 con una sola diferencia: al redactar guarda qué escribió.

    `_redactar` es copia de la del generador, línea por línea, más las tres anotaciones. Si
    el generador cambia, la prueba `_prueba_misma_prosa` lo detecta.
    """

    def _redactar(self, obj, h, periodo, nivel, ya_inscritos):
        ref, tipo_ref = self._referir(obj, nivel)
        per = self.rnd.choice(G.PERIODO_TXT[(periodo, nivel)])
        partes = []
        menciones, nombres = [], []
        for c in obj["prerrequisitos"]:
            e = h.get(c, NO_CURSADA)
            if e == INSCRITA:
                nom, _ = self._referir(self.asig[c], nivel)
                menciones.append(f"{'me falta ' if nivel > 1 else ''}{nom} pero "
                                 f"{self.rnd.choice(G.ESTADO_INSCRITA_TXT)}")
                nombres.append(nom)
            elif e == REPROBADA and nivel >= 2:
                nom, _ = self._referir(self.asig[c], nivel)
                menciones.append(f"{nom}, {self.rnd.choice(G.ESTADO_REPROBADA_TXT)}")
                nombres.append(nom)
        otros = []
        if menciones:
            k = self.rnd.randrange(len(menciones))     # = rnd.choice, con el índice a la vista
            partes.append(menciones[k])
            otros = [nombres[k]]
        apertura = self.rnd.choice(G.APERTURAS) if nivel >= 2 else ""
        verbo = self.rnd.choice(G.VERBOS) if nivel >= 2 else "¿puedo inscribir"
        nucleo = f"{verbo} {ref} {per}?"
        prosa = apertura + (", ".join(partes) + ", " if partes else "") + nucleo
        prosa = prosa[0].upper() + prosa[1:] if prosa else prosa
        limpia = (f"¿Puedo inscribir {obj['codigo']} ({obj['nombre']}) "
                  f"en {'2026-2' if periodo == 'actual' else '2027-1'}?")
        self.ultima_etiqueta = {"accion": "entregar", "consultado": ref, "otros": otros,
                                "frase_periodo": per, "periodo": periodo}
        return prosa, limpia, tipo_ref


def excluidos():
    claves, preguntas = set(), set()
    for f in EXCLUIR:
        ruta = DATOS / f
        if not ruta.exists():
            continue
        for l in open(ruta, encoding="utf-8"):
            if l.strip():
                c = json.loads(l)
                claves.add(clave(c))
                preguntas.add(pregunta(c))
                if "pregunta_plantilla" in c:
                    preguntas.add(c["pregunta_plantilla"].strip().lower())
    return claves, preguntas


def generar_pares(n, semilla):
    """n pares con decisión y nivel parejos, sin repetir problema ni pregunta."""
    claves, preguntas = excluidos()
    gen = GeneradorEtiquetado(seed=semilla)
    prompt = A.Prompt("interprete.md")
    constructores = [c for fam in G.Generador.POR_DECISION.values() for c in fam]
    rnd = random.Random(semilla)
    pares, vistos, intentos = [], set(), 0
    while len(pares) < n and intentos < 50 * n:
        intentos += 1
        c = gen.generar_caso(rnd.choice((1, 2, 3)), rnd.choice(constructores))
        if not c:
            continue
        k, q = clave(c), pregunta(c)
        if k in claves or q in preguntas or q in vistos:
            continue
        vistos.add(q)
        etiqueta = dict(gen.ultima_etiqueta)
        mensajes = prompt.mensajes(pregunta=c["pregunta_prosa"], revision="")
        pares.append({
            "prompt": mensajes,
            "completion": [{"role": "assistant",
                            "content": json.dumps(etiqueta, ensure_ascii=False)}],
            "meta": {"constructor": c["constructor"], "nivel": c["nivel"],
                     "pregunta": c["pregunta_prosa"], "clave": k, "prompt_hash": prompt.hash},
        })
    if len(pares) < n:
        raise RuntimeError(f"solo {len(pares)} pares de {n}")
    return pares


def _prueba_misma_prosa():
    """El generador etiquetado escribe exactamente las mismas preguntas que el original."""
    a, b = G.Generador(seed=7), GeneradorEtiquetado(seed=7)
    for i in range(300):
        cons = list(G.Generador.POR_DECISION.values())[i % 3][0]
        x, y = a.generar_caso(i % 3 + 1, cons), b.generar_caso(i % 3 + 1, cons)
        assert (x and x["pregunta_prosa"]) == (y and y["pregunta_prosa"]), (i, x, y)
        if y:
            e = b.ultima_etiqueta
            assert e["consultado"] in y["pregunta_prosa"] and e["frase_periodo"] in y["pregunta_prosa"]
            assert all(o in y["pregunta_prosa"] for o in e["otros"])
    print("generador etiquetado = generador original en 300 casos")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--semilla", type=int, default=20261114)
    ap.add_argument("--validacion", type=float, default=0.1)
    ap.add_argument("--salida", default=str(DATOS / "entrenamiento_piloto"))
    ap.add_argument("--pruebas", action="store_true")
    a = ap.parse_args()
    if a.pruebas:
        _prueba_misma_prosa()
        return 0
    pares = generar_pares(a.n, a.semilla)
    n_val = int(len(pares) * a.validacion)
    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)
    for nombre, filas in (("entrenamiento.jsonl", pares[n_val:]), ("validacion.jsonl", pares[:n_val])):
        with open(salida / nombre, "w", encoding="utf-8", newline="\n") as f:
            for p in filas:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"{len(pares) - n_val} de entrenamiento y {n_val} de validación -> {salida}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
