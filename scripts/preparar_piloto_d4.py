# -*- coding: utf-8 -*-
"""
Conjunto piloto del D4: 60 casos de DESARROLLO con prosa difícil, redactada fuera de las plantillas.

Para qué. El análisis previo (`analisis_previo_d4.py`) mostró que el sistema del D3 lee bien el
período en 94-95 % de sus propios casos, y que casi todo lo que falla viene de una frase de la
plantilla ("el que viene"). Antes de entrenar hay que saber si el sistema base falla en prosa
más variada, la que representa la falla del D1 (E1, "cursándola ahora", y E2, leer la prosa).
Este conjunto es para medir eso en un piloto. No es de prueba: se puede mirar, y ninguna cifra
de aquí va al documento como resultado.

Composición (semilla 20261113, casos que no repiten historial y consulta ni pregunta de ningún
conjunto anterior):
  20 `_c_inscrita_actual`   un prerrequisito en curso, se pregunta por este semestre -> "no"
  20 `_c_inscrita_proximo`  un prerrequisito en curso, se pregunta por el próximo -> "condicional"
  20 de los demás constructores, para no medir solo el caso donde decide el período

Cada fila trae un estilo asignado por código (no por quien redacta), rotando:
  periodo_estilo  relativo · calendario · implicito
  ramo_estilo     nombre · apodo
Quién redacta: un subagente de Claude sin acceso al repositorio. Recibe solo las columnas del
CSV y la instrucción, que queda en `INSTRUCCION.md` de la misma carpeta.

    python preparar_piloto_d4.py elegir                -> datos/piloto_d4/piloto.csv
    python preparar_piloto_d4.py llenar <json> <autor> -> completa las preguntas vacías
    python preparar_piloto_d4.py unir                  -> datos/piloto_d4/piloto.jsonl
"""

import csv
import json
import sys
from pathlib import Path

from generador import Generador
from preparar_prueba_v5 import clave, pregunta
from verificador import INSCRITA, REPROBADA

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
SALIDA = DATOS / "piloto_d4"
CSV_RUTA = SALIDA / "piloto.csv"
BASE_RUTA = SALIDA / "base.jsonl"
JSONL_SALIDA = SALIDA / "piloto.jsonl"
SEMILLA = 20261113
ANTERIORES = ["casos.jsonl", "casos_nuevos.jsonl", "casos_redactados.jsonl",
              "casos_desarrollo.jsonl", "casos_desarrollo_redactados.jsonl",
              "prueba_v5/plantilla_a.jsonl", "prueba_v5/plantilla_b.jsonl",
              "prueba_v5/base_redactados.jsonl", "prueba_v5/redactados.jsonl"]
CUPOS = [("_c_inscrita_actual", 20), ("_c_inscrita_proximo", 20),
         ("_c_prerrequisito", 4), ("_c_ok", 6), ("_c_excepcion", 4), ("_c_creditos", 2),
         ("_c_tope_max", 2), ("_c_especial", 2)]
PERIODO_TXT = {"actual": "este semestre, el que está en curso (2026-2, el segundo semestre de 2026)",
               "proximo": "el semestre siguiente (2027-1, empieza en marzo de 2027)"}
ESTADO_TXT = {INSCRITA: "la está cursando ahora, este semestre", REPROBADA: "la reprobó"}
PERIODO_ESTILOS = ["relativo", "calendario", "implicito"]
RAMO_ESTILOS = ["nombre", "apodo"]
COLUMNAS = ["id", "ramo_por_el_que_pregunta", "periodo", "menciona_tambien", "estado_de_ese_ramo",
            "periodo_estilo", "ramo_estilo", "pregunta", "autor", "revisado_por"]


def vistos():
    claves, preguntas = set(), set()
    for f in ANTERIORES:
        for l in open(DATOS / f, encoding="utf-8"):
            if l.strip():
                c = json.loads(l)
                claves.add(clave(c))
                preguntas.add(pregunta(c))
                if "pregunta_plantilla" in c:
                    preguntas.add(c["pregunta_plantilla"].strip().lower())
    return claves, preguntas


def contexto(gen, caso):
    """El primer prerrequisito en curso o reprobado: es el que la pregunta debe nombrar."""
    for p in gen.asig[caso["ramo_objetivo"]["codigo"]]["prerrequisitos"]:
        e = caso["historial"].get(p)
        if e in ESTADO_TXT:
            return gen.asig[p]["nombre"], ESTADO_TXT[e]
    return "", ""


def elegir():
    if CSV_RUTA.exists():
        print(f"{CSV_RUTA.name} ya existe; no se sobrescribe.")
        return 1
    SALIDA.mkdir(exist_ok=True)
    claves, preguntas = vistos()
    gen = Generador(seed=SEMILLA)
    casos, nuevas = [], set()
    for cons, cupo in CUPOS:
        hechos, i = 0, 0
        while hechos < cupo and i < 5000:
            i += 1
            c = gen.generar_caso((i % 3) + 1, cons)
            if not c:
                continue
            k = clave(c)
            if k in claves or k in nuevas or pregunta(c) in preguntas:
                continue
            nuevas.add(k)
            casos.append(c)
            hechos += 1
        if hechos < cupo:
            raise RuntimeError(f"{cons}: solo {hechos} de {cupo}")
    with open(BASE_RUTA, "w", encoding="utf-8", newline="\n") as f:
        for c in casos:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    filas = []
    for i, c in enumerate(casos):
        otro, estado = contexto(gen, c)
        filas.append({"id": i, "ramo_por_el_que_pregunta": c["ramo_objetivo"]["nombre"],
                      "periodo": PERIODO_TXT[c["consulta"]["periodo"]],
                      "menciona_tambien": otro, "estado_de_ese_ramo": estado,
                      "periodo_estilo": PERIODO_ESTILOS[i % 3],
                      "ramo_estilo": RAMO_ESTILOS[(i // 3) % 2],
                      "pregunta": "", "autor": "", "revisado_por": ""})
    escribir_csv(filas)
    print(f"{len(filas)} casos -> {CSV_RUTA.name}; base -> {BASE_RUTA.name}")
    return 0


def leer_csv():
    return list(csv.DictReader(open(CSV_RUTA, encoding="utf-8-sig")))


def escribir_csv(filas):
    with open(CSV_RUTA, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(filas)


def llenar(ruta_json, autor):
    nuevas = json.loads(Path(ruta_json).read_text(encoding="utf-8"))
    filas = leer_csv()
    puestas = 0
    for f in filas:
        q = str(nuevas.get(f["id"], "")).strip()
        if q and not f["pregunta"].strip():
            f["pregunta"], f["autor"] = q, autor
            puestas += 1
    escribir_csv(filas)
    print(f"{puestas} preguntas completadas, autor: {autor}")
    return 0


def unir():
    casos = [json.loads(l) for l in open(BASE_RUTA, encoding="utf-8") if l.strip()]
    filas = leer_csv()
    faltan = [f["id"] for f in filas if not f["pregunta"].strip()]
    if faltan:
        print(f"Faltan {len(faltan)} preguntas: ids {', '.join(faltan)}")
        return 1
    with open(JSONL_SALIDA, "w", encoding="utf-8", newline="\n") as f:
        for fila in filas:
            c = dict(casos[int(fila["id"])])
            c["pregunta_plantilla"] = c["pregunta_prosa"]
            c["pregunta_prosa"] = fila["pregunta"].strip()
            c["autor_pregunta"] = fila["autor"]
            c["estilo"] = {"periodo": fila["periodo_estilo"], "ramo": fila["ramo_estilo"]}
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"{len(filas)} casos -> {JSONL_SALIDA.name}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    accion = sys.argv[1] if len(sys.argv) > 1 else ""
    if accion == "elegir":
        raise SystemExit(elegir())
    if accion == "llenar" and len(sys.argv) == 4:
        raise SystemExit(llenar(sys.argv[2], sys.argv[3]))
    if accion == "unir":
        raise SystemExit(unir())
    print(__doc__)
    raise SystemExit(2)
