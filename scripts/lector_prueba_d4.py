# -*- coding: utf-8 -*-
"""
Lectura de las 180 redactadas de la prueba sellada del D4, con un lector automático a ciegas y
revisión humana dirigida. Reemplaza la lectura humana completa (decisión de Lucas, 24 nov).

Regla, escrita antes de lanzar al lector:
  1. Un subagente de Claude recibe solo id y mensaje (sin etiquetas) y la lista de los 61 ramos
     de la malla. Para cada mensaje dice qué ramo consulta, para qué semestre (actual o
     proximo), qué otros ramos menciona y si dudó.
  2. Este script compara con la etiqueta. Hay acuerdo si coinciden el ramo, el semestre, el
     lector no dudó y, cuando la fila exige mencionar otro ramo, el lector lo lista.
  3. Una persona del equipo lee TODOS los desacuerdos y 30 acuerdos al azar (semilla 20261127,
     elegidos aquí antes de que nadie los vea).
  4. Si en los 30 acuerdos la persona marca uno solo como no `ok`, lee 30 acuerdos más (misma
     semilla, siguientes en el orden). Si en esos aparece otro, lee todos los acuerdos.
  5. Los acuerdos que nadie lee quedan `ok` con lector "lector automático a ciegas".

Claude (la sesión que arma el sistema) no lee los mensajes: este script imprime solo conteos.

    python lector_prueba_d4.py preparar   -> datos/prueba_d4/lector_entrada.json, ramos_malla.json
    python lector_prueba_d4.py comparar   -> lee lector_salida.json y marca lectura.csv
    python lector_prueba_d4.py ampliar    -> marca 30 acuerdos más para la persona
"""

import csv
import json
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
P = RAIZ / "datos" / "prueba_d4"
LECTURA = P / "lectura.csv"
ENTRADA = P / "lector_entrada.json"
RAMOS = P / "ramos_malla.json"
SALIDA = P / "lector_salida.json"
SEMILLA_MUESTRA = 20261127
MUESTRA = 30
AUTO = "lector automático a ciegas"
CUANDO = {"ACTUAL": "actual", "PROXIMO": "proximo"}
COLUMNAS = ["id", "ramo", "cuando", "otro_ramo", "estado_otro", "pregunta", "revisar",
            "lector_ramo", "lector_cuando", "lector_otros", "lector_duda",
            "lectura", "pregunta_corregida", "lector", "nota"]


def leer():
    return list(csv.DictReader(open(LECTURA, encoding="utf-8-sig")))


def escribir(filas):
    with open(LECTURA, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS, extrasaction="ignore")
        w.writeheader()
        for r in filas:
            w.writerow({k: r.get(k, "") for k in COLUMNAS})


def preparar():
    malla = json.load(open(RAIZ / "datos" / "malla.json", encoding="utf-8"))["asignaturas"]
    a = malla.values() if isinstance(malla, dict) else malla
    nombres = sorted(x["nombre"] for x in a)
    RAMOS.write_text(json.dumps(nombres, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    entrada = [{"id": r["id"], "mensaje": r["pregunta"]} for r in leer()]
    ENTRADA.write_text(json.dumps(entrada, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"{len(entrada)} mensajes -> {ENTRADA.name}; {len(nombres)} ramos -> {RAMOS.name}")
    return 0


def norm(s):
    return " ".join(str(s or "").strip().lower().split())


def comparar():
    salida = json.loads(SALIDA.read_text(encoding="utf-8"))
    salida = {str(k): v for k, v in salida.items()}
    nombres = set(json.loads(RAMOS.read_text(encoding="utf-8")))
    filas = leer()
    faltan = [r["id"] for r in filas if r["id"] not in salida]
    if faltan:
        print(f"El lector no respondió {len(faltan)} ids: {', '.join(faltan[:20])}")
        return 1
    motivos, acuerdos = {"ramo": 0, "semestre": 0, "otro": 0, "duda": 0, "fuera_de_lista": 0}, []
    for r in filas:
        s = salida[r["id"]]
        r["lector_ramo"] = s.get("ramo", "")
        r["lector_cuando"] = s.get("semestre", "")
        r["lector_otros"] = "; ".join(s.get("otros", []) or [])
        r["lector_duda"] = "sí" if s.get("duda") else ""
        m = []
        if s.get("ramo") not in nombres:
            m.append("fuera_de_lista")
        if norm(s.get("ramo")) != norm(r["ramo"]):
            m.append("ramo")
        if s.get("semestre") != CUANDO[r["cuando"]]:
            m.append("semestre")
        if r["otro_ramo"] and norm(r["otro_ramo"]) not in {norm(o) for o in s.get("otros", []) or []}:
            m.append("otro")
        if s.get("duda"):
            m.append("duda")
        for x in m:
            motivos[x] += 1
        r["revisar"] = "desacuerdo: " + ", ".join(m) if m else ""
        if not m:
            acuerdos.append(r["id"])
    orden = sorted(acuerdos, key=int)
    random.Random(SEMILLA_MUESTRA).shuffle(orden)
    for r in filas:
        if r["id"] in orden[:MUESTRA]:
            r["revisar"] = "muestra de acuerdos (1-30)"
    escribir(filas)
    (P / "muestra_orden.json").write_text(json.dumps(orden), encoding="utf-8", newline="\n")
    d = sum(1 for r in filas if r["revisar"].startswith("desacuerdo"))
    print(f"acuerdos {len(acuerdos)}, desacuerdos {d}; motivos {motivos}")
    print(f"para la persona: {d} desacuerdos + {min(MUESTRA, len(acuerdos))} acuerdos al azar")
    return 0


def ampliar():
    orden = json.loads((P / "muestra_orden.json").read_text(encoding="utf-8"))
    filas = leer()
    ya = sum(1 for r in filas if r["revisar"].startswith("muestra"))
    nuevos = set(orden[ya:ya + MUESTRA])
    for r in filas:
        if r["id"] in nuevos:
            r["revisar"] = f"muestra de acuerdos ({ya + 1}-{ya + len(nuevos)})"
    escribir(filas)
    print(f"{len(nuevos)} acuerdos más marcados para la persona")
    return 0


def cerrar():
    """Tras la revisión humana: los acuerdos no leídos quedan ok por el lector automático."""
    filas = leer()
    sin = [r["id"] for r in filas if r["revisar"] and not r["lectura"].strip()]
    if sin:
        print(f"La persona no marcó {len(sin)} filas que le tocaban: {', '.join(sin[:20])}")
        return 1
    n = 0
    for r in filas:
        if not r["revisar"] and not r["lectura"].strip():
            r["lectura"], r["lector"] = "ok", AUTO
            n += 1
    escribir(filas)
    print(f"{n} acuerdos no leídos marcados ok ({AUTO})")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    acciones = {"preparar": preparar, "comparar": comparar, "ampliar": ampliar, "cerrar": cerrar}
    a = sys.argv[1] if len(sys.argv) > 1 else ""
    if a in acciones:
        raise SystemExit(acciones[a]())
    print(__doc__)
    raise SystemExit(2)
