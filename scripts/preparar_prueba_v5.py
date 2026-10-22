# -*- coding: utf-8 -*-
"""
Conjuntos de prueba de la versión 5 del sistema de agentes — Deliverable 3.

Los 150 casos de prueba de la v4 ya se miraron: de sus trazas salió el diagnóstico que motiva
la v5. Medir la v5 sobre ellos sería medir sobre lo que se usó para diseñarla. Este script arma
casos que nadie ha visto, y se corre ANTES de diseñar la v5.

Tres lotes de 60 con el mismo generador y semillas nuevas, balanceados como los anteriores
(20 por nivel, decisión pareja dentro de cada nivel):

  plantilla_a.jsonl         60 casos con la pregunta de plantilla
  plantilla_b.jsonl         60 casos más con la pregunta de plantilla
  base_redactados.jsonl     60 casos cuya pregunta se redacta de nuevo fuera de las plantillas
                            (`preparar_redactados.py --v5`); la pregunta de plantilla no se usa

Un caso se descarta si repite el historial y la consulta, o la pregunta, de cualquier conjunto
anterior (prueba o desarrollo) o de un lote anterior de este mismo script. En la v4 el
conjunto de desarrollo solo filtraba preguntas idénticas y quedaron 6 casos con el mismo
historial y consulta que casos de prueba.

El script imprime solo conteos. Las preguntas no se leen hasta la corrida final.

    python preparar_prueba_v5.py      -> datos/prueba_v5/*.jsonl y SELLO.txt
"""

import hashlib
import json
import sys
from pathlib import Path

from generador import Generador

DATOS = Path(__file__).resolve().parent.parent / "datos"
SALIDA = DATOS / "prueba_v5"
ANTERIORES = ["casos.jsonl", "casos_nuevos.jsonl", "casos_redactados.jsonl",
              "casos_desarrollo.jsonl", "casos_desarrollo_redactados.jsonl"]
LOTES = [("plantilla_a.jsonl", 20261022), ("plantilla_b.jsonl", 20261023),
         ("base_redactados.jsonl", 20261024)]


def clave(caso):
    """Historial y consulta: lo que define la etiqueta. Dos casos con la misma clave son el
    mismo problema aunque la pregunta esté redactada distinto."""
    return json.dumps([caso["historial"], caso["consulta"]], sort_keys=True, ensure_ascii=False)


def pregunta(caso):
    return caso["pregunta_prosa"].strip().lower()


# Qué tan estricto es el filtro, de más a menos. Se baja de nivel solo cuando el generador
# agota los casos del anterior, y cada caso guarda con cuál entró.
#   nuevo           ni el historial y la consulta ni la pregunta aparecen antes
#   repite_problema el historial y la consulta ya aparecen antes, la pregunta no. Los agentes
#                   leen solo la pregunta.
#   repite_pregunta la pregunta ya aparece en un conjunto anterior
# Pasa en el nivel 1: con el nombre completo del ramo y sin distractores, el generador produce
# solo 10 problemas distintos con decisión "sí" y 10 con "condicional" (20 preguntas "sí", 16
# ya usadas). Los niveles 2 y 3 tienen miles.
FILTROS = ["nuevo", "repite_problema", "repite_pregunta"]


def generar_lote_sin_repetir(gen, vistas_claves, vistas_preguntas, nuevas_claves,
                             nuevas_preguntas, n_por_nivel=20, intentos=3000):
    """`Generador.generar_lote` con el mismo balance, saltando los casos ya vistos.

    `vistas_*` son los conjuntos anteriores; `nuevas_*`, lo ya elegido en este script. Nunca
    se repite una pregunta dentro de los lotes nuevos."""
    casos = []
    for nivel in (1, 2, 3):
        base, resto = divmod(n_por_nivel, 3)
        cupos = {"no": base, "condicional": base, "sí": base}
        for k in list(cupos)[:resto]:
            cupos[k] += 1
        for decision, cupo in cupos.items():
            familia = gen.POR_DECISION[decision]
            hechos = 0
            for filtro in FILTROS:
                i = 0
                while hechos < cupo and i < intentos:
                    cons = familia[i % len(familia)]
                    i += 1
                    c = gen.generar_caso(nivel, cons)
                    if not c or c["respuesta"]["decision"] != decision:
                        continue
                    k, q = clave(c), pregunta(c)
                    # Dentro de los lotes nuevos se prefiere no repetir el problema, pero el
                    # nivel 1 no alcanza (10 problemas "condicional" para 21 cupos): ahí basta
                    # con que la pregunta sea otra.
                    if q in nuevas_preguntas or (filtro == "nuevo" and k in nuevas_claves):
                        continue
                    if filtro == "nuevo" and (k in vistas_claves or q in vistas_preguntas):
                        continue
                    if filtro == "repite_problema" and q in vistas_preguntas:
                        continue
                    c["filtro_v5"] = filtro
                    nuevas_claves.add(k)
                    nuevas_preguntas.add(q)
                    casos.append(c)
                    hechos += 1
            if hechos < cupo:
                raise RuntimeError(f"nivel {nivel}, {decision}: solo {hechos} de {cupo} casos")
    return casos


def main():
    existentes = [p for p in (SALIDA / f for f, _ in LOTES) if p.exists()]
    if existentes:
        print(f"Ya existen {', '.join(p.name for p in existentes)}: no se sobrescriben.")
        return 1
    vistas_claves, vistas_preguntas = set(), set()
    for f in ANTERIORES:
        for l in open(DATOS / f, encoding="utf-8"):
            if l.strip():
                c = json.loads(l)
                vistas_claves.add(clave(c))
                vistas_preguntas.add(pregunta(c))
                if "pregunta_plantilla" in c:
                    vistas_preguntas.add(c["pregunta_plantilla"].strip().lower())
    print(f"{len(vistas_claves)} casos distintos en los conjuntos anteriores\n")

    SALIDA.mkdir(exist_ok=True)
    sello = []
    nuevas_claves, nuevas_preguntas = set(), set()
    for nombre, semilla in LOTES:
        casos = generar_lote_sin_repetir(Generador(seed=semilla), vistas_claves,
                                         vistas_preguntas, nuevas_claves, nuevas_preguntas)
        ruta = SALIDA / nombre
        with open(ruta, "w", encoding="utf-8", newline="\n") as f:
            for c in casos:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        sello.append(f"{hashlib.sha256(ruta.read_bytes()).hexdigest()}  {nombre}  semilla {semilla}")
        # Solo conteos: nivel x decisión, sin mirar las preguntas.
        tabla = {}
        for c in casos:
            k = (c["nivel"], c["respuesta"]["decision"])
            tabla[k] = tabla.get(k, 0) + 1
        resumen = "  ".join(f"n{n}: " + "/".join(str(tabla.get((n, d), 0))
                                                 for d in ("no", "condicional", "sí"))
                            for n in (1, 2, 3))
        filtros = {f: sum(c["filtro_v5"] == f for c in casos) for f in FILTROS}
        print(f"{nombre:24} {len(casos)} casos   (no/condicional/sí)  {resumen}")
        print(f"{'':24} {filtros}")

    (SALIDA / "SELLO.txt").write_text(
        "sha256 de cada lote al generarlo, antes de diseñar la v5\n" + "\n".join(sello) + "\n",
        encoding="utf-8", newline="\n")
    print("\nSELLO.txt escrito")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
