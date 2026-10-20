# -*- coding: utf-8 -*-
"""
Conjunto redactado fuera de las plantillas — Deliverable 3.

Las preguntas de `casos.jsonl` salen de plantillas del generador: siete aperturas, seis
verbos y una lista fija de frases de período. Una regla fija sin modelo (el texto que sigue
al verbo, buscado en el catálogo) acierta 42 de 60. Este conjunto controla eso: 30 casos
originales con la pregunta redactada de nuevo, sin plantillas.

Quién las redacta: un modelo de lenguaje sin acceso al sistema. Recibió solo el ramo, el
período y el ramo de contexto de cada fila, con la instrucción de escribir como un estudiante
por WhatsApp. No vio los prompts de los agentes, ni la herramienta de búsqueda, ni las
plantillas del generador, así que no pudo redactar a favor del sistema. Después un integrante
del equipo revisa cada pregunta. El CSV registra autor y revisión por fila, y el documento
técnico lo declara.

La etiqueta sigue siendo válida porque depende del historial y de la consulta (ramo,
período, créditos ya inscritos), no de la redacción. Lo único que cambia es `pregunta_prosa`.

    python preparar_redactados.py elegir                 -> datos/redactados.csv
    python preparar_redactados.py llenar <json> <autor>  -> completa las preguntas vacías
    python preparar_redactados.py unir                   -> datos/casos_redactados.jsonl

Lo mismo con `--desarrollo` arma 21 redactados del conjunto de DESARROLLO
(`desarrollo_redactados.csv` -> `casos_desarrollo_redactados.jsonl`), para comprobar antes
de congelar los prompts que el sistema no se rompe con preguntas fuera de las plantillas. Se
redactan igual, a ciegas, y no requieren revisión porque no son de prueba.

La selección es determinista (semilla 20261019): 10 casos por nivel, estratificados por
decisión y por si la pregunta original menciona otro ramo.
"""

import csv
import json
import random
import sys
from pathlib import Path

import generador as G
from verificador import INSCRITA, REPROBADA

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
CSV_RUTA = DATOS / "redactados.csv"
JSONL_SALIDA = DATOS / "casos_redactados.jsonl"
SEMILLA = 20261019
COLUMNAS = ["id_original", "ramo_por_el_que_pregunta", "periodo", "menciona_tambien",
            "estado_de_ese_ramo", "pregunta", "autor", "revisado_por"]

PERIODO_TXT = {"actual": "este semestre (2026-2)", "proximo": "el próximo semestre (2027-1)"}
ESTADO_TXT = {INSCRITA: "la está cursando ahora", REPROBADA: "la reprobó"}


# (origen, csv, salida, casos por nivel, semilla, exige revisión)
PRUEBA = ("casos.jsonl", CSV_RUTA, JSONL_SALIDA, 10, SEMILLA, True)
DESARROLLO = ("casos_desarrollo.jsonl", DATOS / "desarrollo_redactados.csv",
              DATOS / "casos_desarrollo_redactados.jsonl", 7, 20261021, False)
CONF = PRUEBA


def cargar_originales():
    return [json.loads(l) for l in open(DATOS / CONF[0], encoding="utf-8")]


def ramo_de_contexto(caso, asig):
    """El prerrequisito que la pregunta original menciona, si menciona alguno."""
    prosa = caso["pregunta_prosa"].lower()
    for p in asig[caso["ramo_objetivo"]["codigo"]]["prerrequisitos"]:
        estado = caso["historial"].get(p)
        if estado not in ESTADO_TXT:
            continue
        formas = [asig[p]["nombre"]] + G._abreviar(asig[p])
        if any(f.lower() in prosa for f in formas):
            return asig[p]["nombre"], ESTADO_TXT[estado]
    return "", ""


def leer_csv():
    return list(csv.DictReader(open(CONF[1], encoding="utf-8-sig")))


def escribir_csv(filas):
    with open(CONF[1], "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(filas)


def elegir():
    # Volver a elegir reescribe el CSV desde cero. Si ya tiene preguntas, las borraría.
    if CONF[1].exists() and any(f["pregunta"].strip() for f in leer_csv()):
        print(f"{CONF[1].name} ya tiene preguntas escritas; no se sobrescribe.")
        return 1
    casos = cargar_originales()
    asig = G.Generador().asig
    rnd = random.Random(CONF[4])
    elegidos = []
    for nivel in (1, 2, 3):
        # Se estratifica por decisión y por si la pregunta menciona otro ramo, que es uno
        # de los mecanismos que el D3 ataca. Sin esto salían 7 con mención de 30.
        grupos = {}
        for i, c in enumerate(casos):
            if c["nivel"] == nivel:
                clave = (c["respuesta"]["decision"], bool(ramo_de_contexto(c, asig)[0]))
                grupos.setdefault(clave, []).append(i)
        # una parte proporcional de cada grupo, redondeando hacia los grupos más grandes
        por_nivel = CONF[3]
        total = sum(len(ids) for ids in grupos.values())
        cupos = {k: len(ids) * por_nivel // total for k, ids in grupos.items()}
        for k in sorted(grupos, key=lambda k: (-(len(grupos[k]) * por_nivel % total),
                                               -len(grupos[k]), k)):
            if sum(cupos.values()) < por_nivel:
                cupos[k] += 1
        for k in sorted(grupos):
            ids = sorted(grupos[k])
            rnd.shuffle(ids)
            elegidos += sorted(ids[:cupos[k]])
    elegidos.sort()

    filas = []
    for i in elegidos:
        c = casos[i]
        otro, estado = ramo_de_contexto(c, asig)
        filas.append({"id_original": i, "ramo_por_el_que_pregunta": c["ramo_objetivo"]["nombre"],
                      "periodo": PERIODO_TXT[c["consulta"]["periodo"]],
                      "menciona_tambien": otro, "estado_de_ese_ramo": estado,
                      "pregunta": "", "autor": "", "revisado_por": ""})
    escribir_csv(filas)
    print(f"{len(filas)} casos -> {CONF[1].name}")
    return 0


def llenar(ruta_json, autor):
    """Completa las preguntas vacías con un JSON {id_original: pregunta}. No pisa ninguna."""
    nuevas = json.loads(Path(ruta_json).read_text(encoding="utf-8"))
    filas = leer_csv()
    puestas = 0
    for f in filas:
        q = nuevas.get(f["id_original"], "").strip()
        if q and not f["pregunta"].strip():
            f["pregunta"], f["autor"] = q, autor
            puestas += 1
    escribir_csv(filas)
    print(f"{puestas} preguntas completadas, autor: {autor}")
    return 0


def unir():
    casos = cargar_originales()
    filas = leer_csv()
    faltan = [f["id_original"] for f in filas if not f["pregunta"].strip()]
    sin_rev = [f["id_original"] for f in filas if not f["revisado_por"].strip()] if CONF[5] else []
    if faltan or sin_rev:
        if faltan:
            print(f"Faltan {len(faltan)} preguntas: ids {', '.join(faltan)}")
        if sin_rev:
            print(f"Faltan {len(sin_rev)} revisiones: ids {', '.join(sin_rev)}")
        return 1
    with open(CONF[2], "w", encoding="utf-8") as f:
        for fila in filas:
            c = dict(casos[int(fila["id_original"])])
            c["id_original"] = int(fila["id_original"])
            c["pregunta_plantilla"] = c["pregunta_prosa"]
            c["pregunta_prosa"] = fila["pregunta"].strip()
            c["autor_pregunta"] = fila["autor"]
            c["revisado_por"] = fila["revisado_por"]
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"{len(filas)} casos -> {CONF[2].name}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--desarrollo" in sys.argv:
        sys.argv.remove("--desarrollo")
        CONF = DESARROLLO
    accion = sys.argv[1] if len(sys.argv) > 1 else ""
    if accion == "elegir":
        raise SystemExit(elegir())
    if accion == "llenar" and len(sys.argv) == 4:
        raise SystemExit(llenar(sys.argv[2], sys.argv[3]))
    if accion == "unir":
        raise SystemExit(unir())
    print(__doc__)
    raise SystemExit(2)
