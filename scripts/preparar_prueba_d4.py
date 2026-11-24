# -*- coding: utf-8 -*-
"""
Prueba sellada del D4: 240 casos nuevos, armados ANTES de que exista cualquier dato de
entrenamiento. Los datos de entrenamiento se filtran después contra estos casos, no al revés.

Composición, fijada en `PLAN_D4.md` (13 nov) antes de generar:

  plantilla.jsonl         60  pregunta de plantilla del generador, balanceada como en el D3
                              (20 por nivel, decisión pareja dentro de cada nivel)
  redactados (decide el período)  120
                              60 `_c_inscrita_actual`  (prerrequisito en curso, este semestre -> "no")
                              60 `_c_inscrita_proximo` (prerrequisito en curso, el próximo -> "condicional")
  redactados (otros)       60  los demás constructores en la proporción del piloto

Las 180 redactadas siguen la misma receta que el piloto (`datos/piloto_d4/INSTRUCCION.md`):
estilo de período y de ramo asignados por código, prosa escrita por subagentes de Claude que
no ven el repositorio. Así el piloto es una muestra de la misma distribución que la prueba, y
elegir la época en el piloto no mira la prueba. La instrucción de los datos de entrenamiento
será otra, escrita después.

Un caso se descarta si repite historial y consulta, o la pregunta, de cualquier conjunto
anterior (D1 a D3, prueba de la v5, desarrollo, piloto) o de este mismo script.

Claude no lee las preguntas redactadas: los subagentes escriben directo a archivos y este
script imprime solo conteos. Las lee una persona del equipo antes de sellar.

    python preparar_prueba_d4.py elegir      -> plantilla.jsonl, base_redactados.jsonl,
                                                filas_redactor_{1,2,3}.json
    python preparar_prueba_d4.py rehacer_plantilla -> plantilla.jsonl solo con casos nuevos (24 nov)
    python preparar_prueba_d4.py llenar      -> lee redactor_{1,2,3}.json y arma lectura.csv
    python preparar_prueba_d4.py unir        -> redactados.jsonl (tras la lectura del equipo)
    python preparar_prueba_d4.py sellar      -> SELLO.txt
"""

import csv
import hashlib
import json
import random
import sys
from pathlib import Path

from generador import Generador
from preparar_piloto_d4 import ESTADO_TXT, PERIODO_ESTILOS, RAMO_ESTILOS, contexto
from preparar_prueba_v5 import clave, pregunta

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
SALIDA = DATOS / "prueba_d4"
PLANTILLA = SALIDA / "plantilla.jsonl"
BASE = SALIDA / "base_redactados.jsonl"
LECTURA = SALIDA / "lectura.csv"
REDACTADOS = SALIDA / "redactados.jsonl"
SEMILLA_PLANTILLA = 20261124
SEMILLA_REDACTADOS = 20261125
SEMILLA_ORDEN = 20261126
N_REDACTORES = 3
ANTERIORES = ["casos.jsonl", "casos_nuevos.jsonl", "casos_redactados.jsonl",
              "casos_desarrollo.jsonl", "casos_desarrollo_redactados.jsonl",
              "prueba_v5/plantilla_a.jsonl", "prueba_v5/plantilla_b.jsonl",
              "prueba_v5/base_redactados.jsonl", "prueba_v5/redactados.jsonl",
              "piloto_d4/base.jsonl", "piloto_d4/piloto.jsonl"]
CUPOS = [("_c_inscrita_actual", 60), ("_c_inscrita_proximo", 60),
         ("_c_prerrequisito", 12), ("_c_ok", 18), ("_c_excepcion", 12), ("_c_creditos", 6),
         ("_c_tope_max", 6), ("_c_especial", 6)]
# Lo que recibe el redactor (mismas palabras que el piloto).
CUANDO = {"actual": "ACTUAL", "proximo": "PROXIMO"}
COLUMNAS_LECTURA = ["id", "ramo", "cuando", "otro_ramo", "estado_otro", "pregunta",
                    "lectura", "pregunta_corregida", "lector", "nota"]


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


def escribir_jsonl(ruta, casos):
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        for c in casos:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")


def leer_jsonl(ruta):
    return [json.loads(l) for l in open(ruta, encoding="utf-8") if l.strip()]


def elegir():
    from preparar_prueba_v5 import generar_lote_sin_repetir
    if PLANTILLA.exists() or BASE.exists():
        print("La prueba ya existe; no se sobrescribe.")
        return 1
    SALIDA.mkdir(exist_ok=True)
    claves, preguntas = vistos()
    print(f"{len(claves)} casos distintos en los conjuntos anteriores")
    nuevas_claves, nuevas_preguntas = set(), set()

    plantilla = generar_lote_sin_repetir(Generador(seed=SEMILLA_PLANTILLA), claves, preguntas,
                                         nuevas_claves, nuevas_preguntas)
    escribir_jsonl(PLANTILLA, plantilla)

    gen = Generador(seed=SEMILLA_REDACTADOS)
    casos = []
    for cons, cupo in CUPOS:
        hechos, i = 0, 0
        while hechos < cupo and i < 20000:
            i += 1
            c = gen.generar_caso((i % 3) + 1, cons)
            if not c:
                continue
            k, q = clave(c), pregunta(c)
            if k in claves or k in nuevas_claves or q in preguntas or q in nuevas_preguntas:
                continue
            nuevas_claves.add(k)
            nuevas_preguntas.add(q)
            casos.append(c)
            hechos += 1
        if hechos < cupo:
            raise RuntimeError(f"{cons}: solo {hechos} de {cupo}")

    # Orden al azar: cada redactor recibe 60 filas seguidas con los seis estilos parejos
    # (60 es múltiplo de 6) y constructores mezclados.
    random.Random(SEMILLA_ORDEN).shuffle(casos)
    filas = []
    for i, c in enumerate(casos):
        otro, estado = contexto(gen, c)
        c["id_d4"] = i
        c["estilo"] = {"periodo": PERIODO_ESTILOS[i % 3], "ramo": RAMO_ESTILOS[(i // 3) % 2]}
        filas.append({"id": str(i), "ramo": c["ramo_objetivo"]["nombre"],
                      "cuando": CUANDO[c["consulta"]["periodo"]],
                      "otro_ramo": otro, "estado_otro": estado,
                      "periodo_estilo": c["estilo"]["periodo"],
                      "ramo_estilo": c["estilo"]["ramo"]})
    escribir_jsonl(BASE, casos)
    por = len(filas) // N_REDACTORES
    for r in range(N_REDACTORES):
        (SALIDA / f"filas_redactor_{r + 1}.json").write_text(
            json.dumps(filas[r * por:(r + 1) * por], ensure_ascii=False, indent=1),
            encoding="utf-8", newline="\n")

    def conteo(cs, campo):
        t = {}
        for c in cs:
            t[campo(c)] = t.get(campo(c), 0) + 1
        return dict(sorted(t.items()))
    print(f"plantilla.jsonl        {len(plantilla)}  decisión {conteo(plantilla, lambda c: c['respuesta']['decision'])}")
    print(f"base_redactados.jsonl  {len(casos)}  decisión {conteo(casos, lambda c: c['respuesta']['decision'])}")
    for r in range(N_REDACTORES):
        parte = casos[r * por:(r + 1) * por]
        print(f"  redactor {r + 1}: {len(parte)} filas, período {conteo(parte, lambda c: c['consulta']['periodo'])}, "
              f"estilos {conteo(parte, lambda c: c['estilo']['periodo'] + '/' + c['estilo']['ramo'])}")
    return 0


def rehacer_plantilla():
    """24 nov, decisión de Lucas. La primera versión de `plantilla.jsonl` usaba el filtro
    escalonado de la v5, que en el nivel 1 cae a repetir problemas: 13 de 60 repetían un
    problema o una pregunta de un conjunto anterior, y 7 se repetían dentro de la prueba. Aquí
    se exige que todo caso sea nuevo (historial, consulta y pregunta). El nivel 1 da los que
    tenga y lo que falta de cada decisión se completa con los niveles 2 y 3. Los 180 casos
    redactados no se tocan: se cargan como ya vistos."""
    vc, vp = vistos()
    for c in leer_jsonl(BASE):
        vc.add(clave(c))
        vp.add(pregunta(c))
    gen = Generador(seed=SEMILLA_PLANTILLA)
    casos, faltan = [], {"no": 0, "condicional": 0, "sí": 0}
    for nivel in (1, 2, 3):
        cupos = {"no": 7, "condicional": 7, "sí": 6}
        if nivel > 1:  # lo que no dio el nivel 1, repartido entre 2 y 3
            for d in cupos:
                extra = faltan[d] // 2 + (faltan[d] % 2 if nivel == 2 else 0)
                cupos[d] += extra
        for decision, cupo in cupos.items():
            familia = gen.POR_DECISION[decision]
            hechos, i = 0, 0
            while hechos < cupo and i < 20000:
                cons = familia[i % len(familia)]
                i += 1
                c = gen.generar_caso(nivel, cons)
                if not c or c["respuesta"]["decision"] != decision:
                    continue
                k, q = clave(c), pregunta(c)
                if k in vc or q in vp:
                    continue
                vc.add(k)
                vp.add(q)
                c["filtro_d4"] = "nuevo"
                casos.append(c)
                hechos += 1
            if nivel == 1:
                faltan[decision] = cupo - hechos
            elif hechos < cupo:
                raise RuntimeError(f"nivel {nivel}, {decision}: solo {hechos} de {cupo}")
    escribir_jsonl(PLANTILLA, casos)
    t = {}
    for c in casos:
        t[(c["nivel"], c["respuesta"]["decision"])] = t.get((c["nivel"], c["respuesta"]["decision"]), 0) + 1
    print(f"plantilla.jsonl {len(casos)} casos; nivel 1 no alcanzó: {faltan}")
    for n in (1, 2, 3):
        print(f"  nivel {n}: " + "  ".join(f"{d} {t.get((n, d), 0)}" for d in ("no", "condicional", "sí")))
    return 0


def llenar():
    """Junta lo que escribieron los redactores en `lectura.csv`, para la lectura del equipo.
    Imprime solo conteos."""
    casos = leer_jsonl(BASE)
    preguntas = {}
    for r in range(N_REDACTORES):
        ruta = SALIDA / f"redactor_{r + 1}.json"
        if not ruta.exists():
            print(f"Falta {ruta.name}")
            return 1
        preguntas.update({str(k): str(v).strip() for k, v in
                          json.loads(ruta.read_text(encoding="utf-8")).items()})
    faltan = [str(c["id_d4"]) for c in casos if not preguntas.get(str(c["id_d4"]))]
    if faltan:
        print(f"Faltan {len(faltan)} mensajes: ids {', '.join(faltan)}")
        return 1
    gen = Generador(seed=0)
    with open(LECTURA, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS_LECTURA)
        w.writeheader()
        for c in casos:
            otro, estado = contexto(gen, c)
            w.writerow({"id": c["id_d4"], "ramo": c["ramo_objetivo"]["nombre"],
                        "cuando": CUANDO[c["consulta"]["periodo"]], "otro_ramo": otro,
                        "estado_otro": estado, "pregunta": preguntas[str(c["id_d4"])],
                        "lectura": "", "pregunta_corregida": "", "lector": "", "nota": ""})
    largos = sorted(len(preguntas[str(c["id_d4"])]) for c in casos)
    print(f"{len(casos)} mensajes -> {LECTURA.name}; largo en caracteres: mín {largos[0]}, "
          f"mediana {largos[len(largos) // 2]}, máx {largos[-1]}")
    return 0


def unir():
    """Tras la lectura. `lectura` vale ok, corregida (se usa `pregunta_corregida`) o
    descartada (el caso sale de la prueba y se reporta)."""
    casos = {c["id_d4"]: c for c in leer_jsonl(BASE)}
    filas = list(csv.DictReader(open(LECTURA, encoding="utf-8-sig")))
    sin_leer = [f["id"] for f in filas if f["lectura"].strip() not in ("ok", "corregida", "descartada")]
    if sin_leer:
        print(f"{len(sin_leer)} filas sin lectura válida (ok/corregida/descartada): {', '.join(sin_leer[:20])}")
        return 1
    salida, cuenta = [], {"ok": 0, "corregida": 0, "descartada": 0}
    for f in filas:
        cuenta[f["lectura"].strip()] += 1
        if f["lectura"].strip() == "descartada":
            continue
        c = dict(casos[int(f["id"])])
        c["pregunta_plantilla"] = c["pregunta_prosa"]
        c["pregunta_prosa"] = (f["pregunta_corregida"] if f["lectura"].strip() == "corregida"
                               else f["pregunta"]).strip()
        c["autor_pregunta"] = "subagente Claude (Anthropic), 24 nov 2026"
        c["lectura"] = {"resultado": f["lectura"].strip(), "lector": f["lector"].strip()}
        salida.append(c)
    escribir_jsonl(REDACTADOS, salida)
    print(f"{len(salida)} casos -> {REDACTADOS.name}; lectura {cuenta}")
    return 0


def sellar():
    archivos = [(PLANTILLA, f"semilla {SEMILLA_PLANTILLA}"),
                (BASE, f"semilla {SEMILLA_REDACTADOS}, orden {SEMILLA_ORDEN}")]
    archivos += [(SALIDA / f"redactor_{r + 1}.json", "mensajes del redactor a ciegas, antes de la lectura")
                 for r in range(N_REDACTORES)]
    archivos += [(LECTURA, "lectura del equipo"), (REDACTADOS, "las redactadas tras la lectura")]
    lineas = []
    for ruta, nota in archivos:
        if not ruta.exists():
            print(f"Falta {ruta.name}")
            return 1
        datos = ruta.read_bytes().replace(b"\r\n", b"\n")
        lineas.append(f"{hashlib.sha256(datos).hexdigest()}  {ruta.name}  {nota}")
    (SALIDA / "SELLO.txt").write_text(
        "sha256 de cada archivo con saltos de línea LF, escrito antes de generar cualquier\n"
        "dato de entrenamiento del D4. Para comprobarlo:\n"
        "git show <commit>:datos/prueba_d4/<archivo> | sha256sum\n" + "\n".join(lineas) + "\n",
        encoding="utf-8", newline="\n")
    print("SELLO.txt escrito\n" + "\n".join(lineas))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    acciones = {"elegir": elegir, "rehacer_plantilla": rehacer_plantilla, "llenar": llenar, "unir": unir, "sellar": sellar}
    accion = sys.argv[1] if len(sys.argv) > 1 else ""
    if accion in acciones:
        raise SystemExit(acciones[accion]())
    print(__doc__)
    raise SystemExit(2)
