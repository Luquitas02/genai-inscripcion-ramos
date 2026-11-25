# -*- coding: utf-8 -*-
"""
Revisión de las etiquetas de entrenamiento del D4 (24 nov). Regla escrita antes de correr:

  1. Lector automático a ciegas (subagentes de Claude) sobre los 1.260 mensajes redactados
     (prosa y revisión): recibe solo id y mensaje, más la lista de 61 ramos, y dice qué ramo
     consulta, para qué semestre y qué otros ramos menciona. Un script compara con la etiqueta
     (ramo del caso, `periodo` del caso, otro ramo exigido por la fila).
  2. Los desacuerdos los lee Claude (los datos de entrenamiento no están sellados) y decide:
     el par se queda si la etiqueta es correcta, y sale si el mensaje no dice lo que dice la
     etiqueta. Se reportan cuántos salen.
  3. Revisión humana declarada (exigida por el enunciado): 60 pares al azar entre los que
     quedan (semilla 20261201), 30 por persona. Si hay 2 o más etiquetas mal en los 60, se
     revisan 60 más y se corrige la instrucción antes de entrenar.

    python lector_entrenamiento_d4.py preparar   -> datos/entrenamiento_d4/lector/entrada_{1..4}.json
    python lector_entrenamiento_d4.py comparar   -> desacuerdos.json y conteos
"""

import json
import sys
from pathlib import Path

from generador import Generador
from preparar_piloto_d4 import contexto

RAIZ = Path(__file__).resolve().parent.parent
E = RAIZ / "datos" / "entrenamiento_d4"
L = E / "lector"
PARTES = 4


def leer_jsonl(r):
    return [json.loads(l) for l in open(r, encoding="utf-8") if l.strip()]


def redactados():
    """id_ent -> (caso, mensaje) de los pares que quedaron en entrenamiento o validación."""
    casos = {c["id_ent"]: c for c in leer_jsonl(E / "casos.jsonl")}
    out = {}
    for f in ("entrenamiento.jsonl", "validacion.jsonl"):
        for p in leer_jsonl(E / f):
            if p["meta"]["bloque"] in ("prosa", "revision"):
                out[p["meta"]["id_ent"]] = (casos[p["meta"]["id_ent"]], p["meta"]["pregunta"], p)
    return out


def preparar():
    L.mkdir(exist_ok=True)
    r = redactados()
    ids = sorted(r)
    por = -(-len(ids) // PARTES)
    for k in range(PARTES):
        parte = [{"id": str(i), "mensaje": r[i][1]} for i in ids[k * por:(k + 1) * por]]
        (L / f"entrada_{k + 1}.json").write_text(json.dumps(parte, ensure_ascii=False, indent=1),
                                                 encoding="utf-8", newline="\n")
        print(f"entrada_{k + 1}.json: {len(parte)} mensajes")
    return 0


def norm(s):
    return " ".join(str(s or "").strip().lower().split())


def comparar():
    r = redactados()
    sal = {}
    for k in range(PARTES):
        sal.update({str(a): b for a, b in json.loads((L / f"salida_{k + 1}.json").read_text(encoding="utf-8")).items()})
    gen = Generador(seed=0)
    desac, motivos = [], {}
    for i, (c, m, p) in sorted(r.items()):
        s = sal.get(str(i))
        if s is None:
            mot = ["sin respuesta"]
        else:
            otro, _ = contexto(gen, c)
            mot = []
            if norm(s.get("ramo")) != norm(c["ramo_objetivo"]["nombre"]):
                mot.append("ramo")
            if s.get("semestre") != c["consulta"]["periodo"]:
                mot.append("semestre")
            if otro and norm(otro) not in {norm(o) for o in s.get("otros") or []}:
                mot.append("otro")
            if s.get("duda"):
                mot.append("duda")
        for x in mot:
            motivos[x] = motivos.get(x, 0) + 1
        if mot:
            desac.append({"id_ent": i, "motivos": mot, "mensaje": m,
                          "etiqueta": {"ramo": c["ramo_objetivo"]["nombre"], "periodo": c["consulta"]["periodo"],
                                       "salida": json.loads(p["completion"][0]["content"])},
                          "lector": s})
    (L / "desacuerdos.json").write_text(json.dumps(desac, ensure_ascii=False, indent=1),
                                        encoding="utf-8", newline="\n")
    print(f"{len(r)} mensajes; acuerdos {len(r) - len(desac)}, desacuerdos {len(desac)}; motivos {motivos}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    acciones = {"preparar": preparar, "comparar": comparar}
    a = sys.argv[1] if len(sys.argv) > 1 else ""
    if a in acciones:
        raise SystemExit(acciones[a]())
    print(__doc__)
    raise SystemExit(2)
