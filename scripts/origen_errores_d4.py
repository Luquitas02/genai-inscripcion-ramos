# -*- coding: utf-8 -*-
"""
Dónde nacen los errores del sistema del D3 (v4) — insumo para elegir el agente del D4.

Lee las trazas y los .raw.jsonl de la configuración completa y, para cada caso, sigue el
camino: qué leyó el Intérprete (A), qué candidatos dio T1, qué eligió el Resolvedor (B), qué
hizo el Verificador (C) y qué recibió T2. No corre ningún modelo.

Un caso cuenta como error estricto si el ramo o el período final no son los del caso, aunque
la decisión y la regla salgan correctas (eso pasa cuando la regla no depende del dato errado).

Para cada error estricto se marca el primer punto donde se perdió el dato correcto:

  ramo
    A    el ramo correcto nunca apareció entre los candidatos de T1 (la mención no lo alcanza)
    B1   el ramo correcto era el primer candidato y B eligió otro
    B2   el ramo correcto estaba entre los candidatos, no primero, y B no lo eligió
    C    B eligió el correcto, pero tras un rechazo de C el caso terminó con otro
  período
    A    la primera lectura del Intérprete ya traía el período equivocado
    C    la primera lectura era correcta y cambió tras un rechazo de C

Techos ("oráculos"): se recalcula T2 con el motor de reglas real, cambiando un solo dato.
  B oráculo        si el ramo correcto estuvo entre los candidatos que vio B, B lo elige
  A período        el período es el del caso
  respeta exacto   si el primer candidato tiene puntaje 1,50 (coincidencia exacta), se toma ese

    python scripts/origen_errores_d4.py            # resumen
    python scripts/origen_errores_d4.py --detalle  # además, cada error, caso por caso
"""

import collections
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

from herramientas import motor_de_reglas          # noqa: E402
from verificador import Verificador               # noqa: E402

MODELO = "Phi-3.5-mini-instruct"
CONJUNTOS = {
    "150 (primera medición)": [("casos", "datos/casos.jsonl"),
                               ("casos_nuevos", "datos/casos_nuevos.jsonl"),
                               ("casos_redactados", "datos/casos_redactados.jsonl")],
    "180 (réplica sellada)": [("plantilla_a", "datos/prueba_v5/plantilla_a.jsonl"),
                              ("plantilla_b", "datos/prueba_v5/plantilla_b.jsonl"),
                              ("redactados", "datos/prueba_v5/redactados.jsonl")],
    "73 (desarrollo)": [("casos_desarrollo", "datos/casos_desarrollo.jsonl"),
                        ("casos_desarrollo_redactados", "datos/casos_desarrollo_redactados.jsonl")],
}
EXACTO = 1.5


def leer_jsonl(ruta):
    with open(ruta, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def acierta(v, caso, codigo, periodo):
    if codigo is None:
        return False
    pred = motor_de_reglas(v, caso, codigo, periodo)
    esp = caso["respuesta"]
    return pred["decision"] == esp["decision"] and pred["regla"] == esp["regla"]


def analizar_caso(v, caso, raw, msgs):
    oro = caso["ramo_objetivo"]["codigo"]
    per_oro = caso["consulta"]["periodo"]
    a_msgs = [m["contenido"] for m in msgs if m["de"] == "interprete"]
    t1_msgs = [m["contenido"] for m in msgs if m["de"] == "T1"]
    b_msgs = [m["contenido"] for m in msgs if m["de"] == "resolvedor"]
    c_msgs = [m["contenido"] for m in msgs if m["de"] == "verificador"]

    listas = [[c["codigo"] for c in t["candidatos"]] for t in t1_msgs]
    vistos = {c for l in listas for c in l}
    rango_1 = (listas[0].index(oro) + 1) if listas and oro in listas[0] else None
    exacto_1 = bool(t1_msgs) and t1_msgs[0]["candidatos"][0]["similitud"] >= EXACTO
    eleg = [b["codigo"] for b in b_msgs if b.get("accion") == "elegir"]

    ramo_f = raw["extraccion"]["ramo"]
    per_f = raw["extraccion"]["periodo"]
    ok_ramo = ramo_f == oro
    ok_per = per_f == per_oro

    # primer punto de pérdida del ramo
    cat_ramo = None
    if not ok_ramo:
        if oro not in vistos:
            cat_ramo = "A"
        elif eleg and eleg[0] == oro:
            cat_ramo = "C"
        else:
            # la lista desde la que B eligió por primera vez (o la última que vio)
            i = 0
            for k, b in enumerate(b_msgs):
                if b.get("accion") in ("elegir", "ninguno"):
                    i = k
                    break
            lista = listas[min(i, len(listas) - 1)] if listas else []
            cat_ramo = "B1" if lista and lista[0] == oro else "B2"

    cat_per = None
    if not ok_per:
        primera = (a_msgs[0].get("periodo") or "actual") if a_msgs else None
        cat_per = "A" if primera != per_oro else "C"

    exacto_cod = t1_msgs[0]["candidatos"][0]["codigo"] if exacto_1 else None
    return {
        "oro": oro, "per_oro": per_oro, "ramo_f": ramo_f, "per_f": per_f,
        "ok_ramo": ok_ramo, "ok_per": ok_per, "conjunto": raw["acierto_conjunto"],
        "cat_ramo": cat_ramo, "cat_per": cat_per,
        "rango_1": rango_1, "exacto_1": exacto_1, "exacto_correcto": exacto_cod == oro if exacto_1 else None,
        "oro_visto": oro in vistos, "primera_eleccion": eleg[0] if eleg else None,
        "busquedas": sum(1 for b in b_msgs if b.get("accion") == "buscar"),
        "ninguno": sum(1 for b in b_msgs if b.get("accion") == "ninguno"),
        "rechazos": sum(1 for c in c_msgs if c.get("accion") == "rechazar"),
        "or_B": acierta(v, caso, oro if oro in vistos else ramo_f, per_f),
        "or_per": acierta(v, caso, ramo_f, per_oro),
        "or_exacto": acierta(v, caso, exacto_cod if exacto_1 else ramo_f, per_f),
        "pregunta": caso["pregunta_prosa"],
        "mencion": a_msgs[0].get("consultado") if a_msgs else None,
        "otros": a_msgs[0].get("otros") if a_msgs else None,
        "per_A1": (a_msgs[0].get("periodo") or "actual") if a_msgs else None,
        "top": [(c["codigo"], c["nombre"], c["similitud"]) for c in t1_msgs[0]["candidatos"]] if t1_msgs else [],
        "nombre_oro": caso["ramo_objetivo"]["nombre"], "rasgos": caso.get("rasgos", []),
    }


def main(detalle=False):
    v = Verificador()
    for nombre, partes in CONJUNTOS.items():
        filas = []
        for parte, ruta_datos in partes:
            casos = leer_jsonl(RAIZ / ruta_datos)
            raws = {str(r["id"]): r for r in leer_jsonl(
                RAIZ / f"resultados/agentes__{MODELO}__completo__{parte}.raw.jsonl")}
            trazas = collections.defaultdict(list)
            for m in leer_jsonl(RAIZ / f"trazas/agentes__{MODELO}__completo__{parte}.jsonl"):
                trazas[str(m["caso"])].append(m)
            for i, caso in enumerate(casos):
                raw = raws[str(i)]
                assert raw["ramo_objetivo"]["codigo"] == caso["ramo_objetivo"]["codigo"], (parte, i)
                f = analizar_caso(v, caso, raw, trazas[str(i)])
                f["parte"], f["id"] = parte, i
                filas.append(f)
        n = len(filas)
        conj = sum(f["conjunto"] for f in filas)
        estr = sum(f["ok_ramo"] and f["ok_per"] for f in filas)
        print(f"\n=== {nombre}: {n} casos")
        print(f"acierto conjunto {conj}   estricto (ramo y período) {estr}   "
              f"conjunto sin estricto {sum(f['conjunto'] and not (f['ok_ramo'] and f['ok_per']) for f in filas)}")
        print("ramo mal:", dict(collections.Counter(f["cat_ramo"] for f in filas if f["cat_ramo"])))
        print("período mal:", dict(collections.Counter(f["cat_per"] for f in filas if f["cat_per"])))
        print("ambos mal:", sum(1 for f in filas if f["cat_ramo"] and f["cat_per"]))
        # errores del acierto conjunto, por origen
        err = [f for f in filas if not f["conjunto"]]
        print(f"errores de acierto conjunto {len(err)}:",
              dict(collections.Counter((f["cat_ramo"] or "-") + "/" + (f["cat_per"] or "-") for f in err)))
        print(f"techos (acierto conjunto): B oráculo {sum(f['or_B'] for f in filas)}   "
              f"período del caso {sum(f['or_per'] for f in filas)}   "
              f"respeta exacto {sum(f['or_exacto'] for f in filas)}")
        # comportamiento de B
        vio = [f for f in filas if f["oro_visto"]]
        r1 = [f for f in filas if f["rango_1"] == 1]
        rl = [f for f in filas if f["rango_1"] and f["rango_1"] > 1]
        ex = [f for f in filas if f["exacto_1"]]
        print(f"B: oro entre candidatos {len(vio)}; B lo eligió primero en "
              f"{sum(f['primera_eleccion'] == f['oro'] for f in vio)}")
        print(f"   oro primero en T1 {len(r1)} -> B eligió oro {sum(f['primera_eleccion'] == f['oro'] for f in r1)}")
        print(f"   oro 2.º-5.º en T1 {len(rl)} -> B eligió oro {sum(f['primera_eleccion'] == f['oro'] for f in rl)}")
        print(f"   top-1 exacto (1,50) {len(ex)}, de ellos correcto {sum(bool(f['exacto_correcto']) for f in ex)}; "
              f"B se apartó del exacto {sum(f['primera_eleccion'] != f['top'][0][0] for f in ex)} "
              f"(de esos, el exacto era el oro {sum(f['primera_eleccion'] != f['top'][0][0] and f['exacto_correcto'] for f in ex)})")
        print(f"   búsquedas extra {sum(f['busquedas'] for f in filas)} en "
              f"{sum(1 for f in filas if f['busquedas'])} casos; ninguno {sum(f['ninguno'] for f in filas)}; "
              f"rechazos de C {sum(f['rechazos'] for f in filas)}")
        if detalle:
            for f in filas:
                if f["cat_ramo"] or f["cat_per"]:
                    print(f"\n  [{f['parte']} {f['id']}] ramo:{f['cat_ramo'] or 'ok'} per:{f['cat_per'] or 'ok'} "
                          f"conjunto:{'ok' if f['conjunto'] else 'MAL'}  rasgos={f['rasgos']}")
                    print(f"    P: {f['pregunta']}")
                    print(f"    A: mención={f['mencion']!r} otros={f['otros']} período={f['per_A1']} (caso: {f['per_oro']})")
                    print(f"    oro: {f['oro']} {f['nombre_oro']}  rango T1={f['rango_1']}  final={f['ramo_f']}/{f['per_f']}")
                    print("    T1: " + " · ".join(f"{c} {nm} {s:.2f}" for c, nm, s in f["top"]))
                    print(f"    B: 1.ª elección={f['primera_eleccion']} búsquedas={f['busquedas']} ninguno={f['ninguno']} "
                          f"rechazos C={f['rechazos']}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main(detalle="--detalle" in sys.argv)
