# -*- coding: utf-8 -*-
"""
Muestra la traza de un caso como una conversación entre agentes — Deliverable 3.

Es lo que se ve en el video: cada mensaje con quién lo manda, a quién, y qué pasa. Lee los
archivos de `trazas/` que escribe `runner_d3.py`.

    python ver_traza.py ../trazas/agentes__Phi-3.5-mini-instruct__completo__casos.jsonl 40
    python ver_traza.py <traza> 40 --crudo      # además la salida textual del modelo
"""

import argparse
import json
import sys

NOMBRES = {"estudiante": "ESTUDIANTE", "interprete": "A · INTÉRPRETE",
           "resolvedor": "B · RESOLVEDOR", "verificador": "C · VERIFICADOR",
           "T1": "T1 · buscar_ramo", "T2": "T2 · motor de reglas",
           "orquestador": "ORQUESTADOR", "fin": "FIN"}


def resumen_contenido(m):
    c = m["contenido"]
    if m["tipo"] == "entrada":
        return f"\"{c['pregunta']}\""
    if m["de"] == "T1":
        cands = ", ".join(f"{x['codigo']} {x['nombre']} ({x['similitud']:.2f})"
                          for x in c["candidatos"])
        return f"busca \"{c['consulta']}\" → {cands}"
    if m["de"] == "T2":
        tope = "  (por tope, sin aceptación)" if c.get("por_tope") else ""
        return f"{c['codigo']} · {c['periodo']} → decisión {c['decision']}, regla {c['regla']}{tope}"
    accion = c.get("accion", "")
    resto = {k: v for k, v in c.items() if k not in ("accion", "periodo_por_defecto")}
    return f"{accion.upper()}  " + json.dumps(resto, ensure_ascii=False)


def leer(ruta, caso):
    return [json.loads(l) for l in open(ruta, encoding="utf-8")
            if l.strip() and json.loads(l)["caso"] == str(caso)]


def imprimir(mensajes, crudo=False, marcas=None):
    """Una línea por mensaje. `marcas` agrega al final una marca por mensaje (la demo la usa
    para decir si la salida del modelo coincide con la traza guardada)."""
    for k, m in enumerate(mensajes):
        de, para = NOMBRES.get(m["de"], m["de"]), NOMBRES.get(m["para"], m["para"])
        extra = f"  {marcas[k]}" if marcas and marcas[k] else ""
        print(f"{m['n']:2}  {de:18} → {para:18} {resumen_contenido(m)}{extra}")
        if crudo and m.get("crudo"):
            print(f"{'':42}modelo: {m['crudo'].strip()}")


def mostrar(ruta, caso, crudo=False):
    mensajes = leer(ruta, caso)
    if not mensajes:
        print(f"no hay mensajes del caso {caso} en {ruta}")
        return 1
    imprimir(mensajes, crudo)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("traza")
    ap.add_argument("caso", type=int)
    ap.add_argument("--crudo", action="store_true")
    a = ap.parse_args()
    return mostrar(a.traza, a.caso, a.crudo)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
