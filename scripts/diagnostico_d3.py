# -*- coding: utf-8 -*-
"""
Diagnóstico del paso 1 del D2 — punto de partida del Deliverable 3.

Lee las salidas guardadas del sistema del D2 (no llama a ningún modelo) y separa los
errores de extracción por mecanismo:

  1. cómo nombra la pregunta al ramo: nombre exacto del catálogo, abreviado o coloquial,
     o una forma que corresponde a más de un ramo (ambigua por construcción del generador)
  2. si la pregunta menciona otro ramo antes del consultado
  3. si el período salió mal

Además mide cuánto resolvería T1, la búsqueda léxica del sistema de agentes
(`herramientas.buscar_ramo`), si recibiera la mención ya aislada. T1 no usa el diccionario
de abreviaciones del generador.

Para aislar la mención este script SÍ usa las plantillas del generador. Es una herramienta
de análisis y nunca forma parte del sistema: si el sistema leyera las plantillas, estaría
leyendo la respuesta.

    python diagnostico_d3.py
"""

import collections
import json
import sys
from pathlib import Path

import generador as G
from herramientas import buscar_ramo, normalizar

RAIZ = Path(__file__).resolve().parent.parent
DATOS, RESULTADOS = RAIZ / "datos", RAIZ / "resultados"

CORRIDAS = [
    ("Phi, 60 originales", "casos.jsonl",
     "pipeline__Phi-3.5-mini-instruct__codigo__encadenado.raw.jsonl"),
    ("Phi, 60 nuevos", "casos_nuevos.jsonl",
     "pipeline__Phi-3.5-mini-instruct__codigo__encadenado__casos_nuevos.raw.jsonl"),
    ("Qwen, 60 originales", "casos.jsonl",
     "pipeline__Qwen2.5-7B-Instruct__codigo__encadenado.raw.jsonl"),
]

MALLA = json.loads((DATOS / "malla.json").read_text(encoding="utf-8"))
ASIG = {a["codigo"]: a for a in MALLA["asignaturas"]}

# Todas las formas con que el generador puede nombrar cada ramo. Una forma que sirve para
# más de un ramo no se puede resolver leyendo solo la pregunta.
FORMAS = collections.defaultdict(set)
for _a in MALLA["asignaturas"]:
    for _f in G._abreviar(_a) + [_a["nombre"]]:
        FORMAS[_f.lower()].add(_a["codigo"])
SUELTAS = ("la i", "la ii", "la iii")

MARCAS_MENCION = [m.lower() for m in G.ESTADO_INSCRITA_TXT + G.ESTADO_REPROBADA_TXT]
FRASES_PERIODO = sorted({p for l in G.PERIODO_TXT.values() for p in l}, key=len, reverse=True)


def norm(s):
    return normalizar(s)


NOMBRES_NORM = {c: norm(a["nombre"]) for c, a in ASIG.items()}


def lexico(texto, k=5):
    """La misma búsqueda que T1 en el sistema de agentes."""
    return [r["codigo"] for r in buscar_ramo(texto, k)]


def mencion_consultada(prosa):
    """Lo que va entre el verbo y la frase de período en la plantilla."""
    baja = prosa.lower()
    for verbo in G.VERBOS:
        i = baja.find(verbo.lower())
        if i < 0:
            continue
        resto = prosa[i + len(verbo):].strip()
        for per in FRASES_PERIODO:
            if resto.endswith(per + "?"):
                return resto[: -len(per) - 1].strip()
    return None


def es_ambigua(ref):
    return len(FORMAS.get(ref.lower(), ())) > 1 or ref.lower() in SUELTAS


def candidatos_ambiguos(ref):
    if ref.lower() in SUELTAS:
        sufijo = " " + ref.split()[-1]
        return {c for c, a in ASIG.items() if a["nombre"].endswith(sufijo)}
    return FORMAS[ref.lower()]


def diagnosticar(etiqueta, archivo_casos, archivo_resultados):
    casos = [json.loads(l) for l in open(DATOS / archivo_casos, encoding="utf-8")]
    filas = {r["id"]: r for r in map(json.loads, open(RESULTADOS / archivo_resultados,
                                                       encoding="utf-8"))}
    t = collections.Counter()
    for i, c in enumerate(casos):
        r = filas[str(i)]
        ref = mencion_consultada(c["pregunta_prosa"]) or ""
        obj = c["ramo_objetivo"]["codigo"]
        ok = r["paso1"]["acierto_ramo"]
        if es_ambigua(ref):
            clase = "ambigua"
            libres = [k for k in candidatos_ambiguos(ref) if c["historial"].get(k) != "aprobada"]
            t["ambigua_resuelta_por_historial"] += len(libres) == 1
        elif norm(ref) == NOMBRES_NORM[obj]:
            clase = "nombre exacto"
        else:
            clase = "abreviado o coloquial"
        t[(clase, ok)] += 1
        otro = any(m in c["pregunta_prosa"].lower() for m in MARCAS_MENCION)
        t[("menciona otro ramo antes" if otro else "solo el consultado", ok)] += 1
        t[("período", r["paso1"]["acierto_periodo"])] += 1
        t[("acierto conjunto", r["acierto_conjunto"])] += 1
        if clase != "ambigua":
            top = lexico(ref)
            t[("léxico top-1", top[0] == obj)] += 1
            t[("léxico top-5", obj in top)] += 1

    print(f"\n=== {etiqueta} ===")
    for nombre in ("nombre exacto", "abreviado o coloquial", "ambigua",
                   "menciona otro ramo antes", "solo el consultado",
                   "período", "acierto conjunto", "léxico top-1", "léxico top-5"):
        bien, mal = t[(nombre, True)], t[(nombre, False)]
        print(f"  {nombre:28} {bien:3} de {bien + mal:3}")
    print(f"  {'ambiguas que el historial resuelve':28} {t['ambigua_resuelta_por_historial']:3}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("Formas que el generador usa para más de un ramo:")
    for f, cods in sorted(FORMAS.items()):
        if len(cods) > 1:
            print(f"  {f!r:18} {sorted(cods)}")
    for corrida in CORRIDAS:
        diagnosticar(*corrida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
