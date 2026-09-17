# -*- coding: utf-8 -*-
"""
Runner del pipeline — Deliverable 2.

Corre los tres pasos sobre los 60 casos y registra todo caso a caso, igual que el runner
del baseline: guarda cada fila apenas la termina y retoma donde iba si el archivo ya
existe, porque una Colab gratuita se desconecta sin avisar.

Dos variantes, que se diferencian solo en quién arma la ficha del paso 2:

    puro        la arma el modelo, leyendo la malla y el historial
    retrieval   la arma `ficha.construir_ficha`, determinista

Dos modos, que se diferencian en qué recibe cada paso:

    encadenado  cada paso recibe la salida real del anterior. Esto es el sistema, y es lo
                que se compara contra el baseline.
    oraculo     cada paso recibe el ground truth del anterior. Esto mide la competencia de
                cada paso por separado.

La diferencia entre los dos modos es el costo de la propagación de errores. Sin ella no se
puede distinguir un paso malo de un paso que recibió basura del anterior.

Uso:
    python runner_d2.py --variante puro --modo encadenado
    python runner_d2.py --variante retrieval --modo oraculo
    python runner_d2.py --modelo-falso --limite 3        # prueba local, sin GPU
"""

import argparse
import json
import time
from pathlib import Path

from verificador import Verificador, RUTA_MALLA
from ficha import construir_ficha, comparar_fichas, RUTA_CASOS
import pipeline as PL

BASE = Path(__file__).resolve().parent.parent
RESULTADOS = BASE / "resultados"

MODELO_POR_DEFECTO = "microsoft/Phi-3.5-mini-instruct"


class ModeloFalso:
    """Devuelve respuestas fijas, en ciclo. Permite probar el encadenado sin GPU.

    Misma firma que `ModeloHF.generar` de runner.py: devuelve (texto, tokens_de_entrada).
    El tiempo lo mide quien llama.
    """

    def __init__(self, respuestas):
        self.respuestas = respuestas
        self.llamadas = []

    def generar(self, mensajes):
        self.llamadas.append(mensajes)
        return self.respuestas[(len(self.llamadas) - 1) % len(self.respuestas)], 0


# --------------------------------------------------------------- un caso

def _llamar(modelo, mensajes):
    t0 = time.perf_counter()
    texto, tokens = modelo.generar(mensajes)
    return texto, tokens, time.perf_counter() - t0


def _paso_vacio(campos=None):
    d = {"crudo": None, "parseado": None, "tokens": 0, "segundos": 0.0}
    if campos is not None:
        d["acierto"] = {k: False for k in campos}
    return d


def correr_caso(modelo, caso, v, malla, variante, modo):
    """Corre los tres pasos sobre un caso y devuelve la fila que se guarda.

    La ficha del modelo siempre se compara contra la ficha VERDADERA del caso, no contra
    la del ramo que eligió el paso 1. Si el paso 1 se equivocó de ramo, la ficha está bien
    armada pero es de otra asignatura, y eso es un error del sistema aunque el paso 2 haya
    hecho su trabajo. Medirlo así es lo que deja ver la propagación de errores.
    """
    codigos = set(v.asig)
    ramo_real = caso["consulta"]["ramos"][0]
    per_real = caso["consulta"]["periodo"]
    cred = caso["consulta"]["creditos_ya_inscritos"]
    ficha_real = construir_ficha(v, caso["historial"], ramo_real, per_real, cred)
    campos = list(comparar_fichas(ficha_real, ficha_real))

    # --- paso 1: extracción ---
    crudo1, tok1, seg1 = _llamar(modelo, PL.prompt_paso1(caso, malla))
    p1 = PL.parsear_paso1(crudo1, codigos)
    paso1 = {"crudo": crudo1, "parseado": p1, "tokens": tok1, "segundos": seg1,
             "acierto_ramo": p1["ramo"] == ramo_real,
             "acierto_periodo": p1["periodo"] == per_real,
             "periodo_por_defecto": False}

    # qué ramo y período usan los pasos siguientes
    if modo == "oraculo":
        ramo, per = ramo_real, per_real
    else:
        ramo, per = p1["ramo"], p1["periodo"]
        if ramo is not None and per is None:
            # El paso 1 acertó el ramo pero no el período. Se sigue con "actual" para que
            # la cadena no se corte, y queda registrado que se usó el valor por defecto.
            per, paso1["periodo_por_defecto"] = "actual", True

    fila = {
        "id": caso.get("id", None),
        "modelo": getattr(modelo, "nombre", "falso"),
        "variante": variante, "modo": modo,
        "nivel": caso["nivel"], "constructor": caso["constructor"],
        "rasgos": caso["rasgos"],
        "ramo_objetivo": caso["ramo_objetivo"],
        "esperado": caso["respuesta"],
        "paso1": paso1, "paso2": _paso_vacio(campos), "paso3": _paso_vacio(),
        "prediccion": {"decision": None, "regla": None, "parseo": "paso1_fallado"},
        "acierto_decision": False, "acierto_regla": False, "acierto_conjunto": False,
    }

    if ramo is None:
        fila["tokens_total"] = tok1
        fila["segundos_total"] = seg1
        return fila

    # --- paso 2: ficha ---
    if variante == "puro":
        crudo2, tok2, seg2 = _llamar(modelo, PL.prompt_paso2(ramo, malla, caso["historial"], per))
        f2 = PL.parsear_paso2(crudo2, v, ramo, per, cred)
        fila["paso2"] = {"crudo": crudo2, "parseado": f2, "tokens": tok2, "segundos": seg2,
                         "acierto": comparar_fichas(ficha_real, f2)}
    else:
        f2 = construir_ficha(v, caso["historial"], ramo, per, cred)
        fila["paso2"] = {"crudo": None, "parseado": f2, "tokens": 0, "segundos": 0.0,
                         "acierto": comparar_fichas(ficha_real, f2)}

    # --- paso 3: decisión ---
    ficha3 = ficha_real if modo == "oraculo" else f2
    if ficha3 is None:
        fila["prediccion"]["parseo"] = "paso2_fallado"
        fila["tokens_total"] = tok1 + fila["paso2"]["tokens"]
        fila["segundos_total"] = seg1 + fila["paso2"]["segundos"]
        return fila

    crudo3, tok3, seg3 = _llamar(modelo, PL.prompt_paso3(ficha3, malla))
    p3 = PL.parsear_paso3(crudo3, PL.identificadores_validos(ficha3))
    fila["paso3"] = {"crudo": crudo3, "parseado": p3, "tokens": tok3, "segundos": seg3}
    fila["prediccion"] = p3
    fila["acierto_decision"] = p3["decision"] == caso["respuesta"]["decision"]
    fila["acierto_regla"] = p3["regla"] == caso["respuesta"]["regla"]
    fila["acierto_conjunto"] = fila["acierto_decision"] and fila["acierto_regla"]
    fila["tokens_total"] = tok1 + fila["paso2"]["tokens"] + tok3
    fila["segundos_total"] = seg1 + fila["paso2"]["segundos"] + seg3
    return fila


# --------------------------------------------------------------- la corrida

def correr(modelo, casos, v, malla, variante, modo, salida):
    """Guarda caso a caso y retoma donde iba. Una Colab gratuita se cae sin avisar."""
    hechos = set()
    if salida.exists():
        with open(salida, encoding="utf-8") as f:
            hechos = {json.loads(l)["id"] for l in f if l.strip()}
        if hechos:
            print(f"retomando: {len(hechos)} casos ya corridos")

    with open(salida, "a", encoding="utf-8") as f:
        for i, caso in enumerate(casos):
            if str(i) in hechos:
                continue
            caso = dict(caso, id=str(i))
            fila = correr_caso(modelo, caso, v, malla, variante, modo)
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
            f.flush()
            marca = "OK " if fila["acierto_conjunto"] else "   "
            print(f"[{marca}] {i + 1:3}/{len(casos)} n{caso['nivel']} "
                  f"{fila['segundos_total']:5.1f}s  "
                  f"p1 {'ok' if fila['paso1']['acierto_ramo'] else '--'}  "
                  f"esperado {fila['esperado']['decision']:12} "
                  f"obtenido {str(fila['prediccion']['decision']):12} "
                  f"regla {fila['prediccion']['regla']}")


def resumen(salida):
    filas = [json.loads(l) for l in open(salida, encoding="utf-8") if l.strip()]
    if not filas:
        print("sin resultados")
        return
    n = len(filas)
    pct = lambda k: 100 * sum(bool(x[k]) for x in filas) / n          # noqa: E731
    print()
    print("=" * 74)
    print(f"{filas[0]['modelo']} · variante {filas[0]['variante']} · modo {filas[0]['modo']}")
    print("=" * 74)
    print(f"paso 1   ramo {100 * sum(x['paso1']['acierto_ramo'] for x in filas) / n:5.1f}%   "
          f"período {100 * sum(x['paso1']['acierto_periodo'] for x in filas) / n:5.1f}%")
    campos = list(filas[0]["paso2"]["acierto"])
    print("paso 2   " + "   ".join(
        f"{c} {100 * sum(x['paso2']['acierto'][c] for x in filas) / n:5.1f}%" for c in campos))
    print(f"paso 3   decisión {pct('acierto_decision'):5.1f}%   regla {pct('acierto_regla'):5.1f}%")
    print()
    print(f"CONJUNTO {pct('acierto_conjunto'):5.1f}%   ({sum(x['acierto_conjunto'] for x in filas)}/{n})")
    print(f"tokens por caso {sum(x['tokens_total'] for x in filas) / n:,.0f}   "
          f"segundos por caso {sum(x['segundos_total'] for x in filas) / n:.1f}")


# --------------------------------------------------------------- pruebas

def _prueba_encadenado():
    """Verifica el número de llamadas por variante y la forma de la fila de salida."""
    v = Verificador()
    malla = json.load(open(RUTA_MALLA, encoding="utf-8"))
    casos = [json.loads(l) for l in open(RUTA_CASOS, encoding="utf-8") if l.strip()][:3]

    respuestas_puro = [
        '{"ramo": "503203", "periodo": "actual"}',
        '{"estado_actual": "no_cursada", "prerrequisitos": [{"codigo": "525140", '
        '"estado": "reprobada"}], "creditos_aprobados": 37, "umbral_creditos": 37, '
        '"requisitos_especiales": []}',
        '{"decision": "no", "regla": "525140"}',
    ]
    fallas = []
    checks = 0

    # puro: tres llamadas por caso
    checks += 1
    m = ModeloFalso(respuestas_puro)
    filas = [correr_caso(m, c, v, malla, "puro", "encadenado") for c in casos]
    if len(m.llamadas) != 3 * len(casos):
        fallas.append(f"puro debería hacer {3 * len(casos)} llamadas, hizo {len(m.llamadas)}")

    # retrieval: dos llamadas por caso, el paso 2 no llama al modelo
    checks += 1
    m2 = ModeloFalso([respuestas_puro[0], respuestas_puro[2]])
    [correr_caso(m2, c, v, malla, "retrieval", "encadenado") for c in casos]
    if len(m2.llamadas) != 2 * len(casos):
        fallas.append(f"retrieval debería hacer {2 * len(casos)} llamadas, hizo {len(m2.llamadas)}")

    # la fila trae todas las claves que analisis_d2 va a leer
    checks += 1
    claves = {"id", "variante", "modo", "nivel", "constructor", "esperado",
              "paso1", "paso2", "paso3", "acierto_decision", "acierto_regla",
              "acierto_conjunto", "tokens_total", "segundos_total"}
    faltan = claves - set(filas[0])
    if faltan:
        fallas.append(f"a la fila le faltan claves: {sorted(faltan)}")

    # en retrieval la ficha es correcta por construcción
    checks += 1
    fila_ret = correr_caso(ModeloFalso([respuestas_puro[0], respuestas_puro[2]]),
                           casos[0], v, malla, "retrieval", "encadenado")
    if not all(fila_ret["paso2"]["acierto"].values()):
        fallas.append("en retrieval la ficha debería ser correcta en todos los campos")

    # si el paso 1 no devuelve un código válido, el caso no puede seguir
    checks += 1
    fila_rota = correr_caso(ModeloFalso(['{"ramo": "Programación", "periodo": "actual"}']),
                            casos[0], v, malla, "retrieval", "encadenado")
    if fila_rota["acierto_conjunto"] or fila_rota["paso3"]["crudo"] is not None:
        fallas.append("con el paso 1 fallado, el paso 3 no debería ejecutarse")

    # en modo oraculo el paso 2 recibe el ramo verdadero aunque el paso 1 se equivoque
    checks += 1
    fila_or = correr_caso(ModeloFalso(['{"ramo": "999999", "periodo": "actual"}',
                                       respuestas_puro[2]]),
                          casos[0], v, malla, "retrieval", "oraculo")
    if fila_or["paso3"]["crudo"] is None:
        fallas.append("en modo oraculo el paso 3 debería ejecutarse igual")

    return checks - len(fallas), checks, fallas


def main_pruebas():
    ok, total, fallas = _prueba_encadenado()
    for m in fallas:
        print(f"[FALLA] {m}")
    print(f"{ok}/{total} chequeos del encadenado correctos")
    return 0 if ok == total else 1


# --------------------------------------------------------------- línea de comandos

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default=MODELO_POR_DEFECTO)
    ap.add_argument("--variante", default="puro", choices=["puro", "retrieval"])
    ap.add_argument("--modo", default="encadenado", choices=["encadenado", "oraculo"])
    ap.add_argument("--limite", type=int, default=None,
                    help="correr solo los primeros N casos")
    ap.add_argument("--modelo-falso", action="store_true",
                    help="usar respuestas fijas en vez de cargar pesos, para probar sin GPU")
    ap.add_argument("--pruebas", action="store_true",
                    help="correr los chequeos del encadenado y salir")
    args = ap.parse_args()

    if args.pruebas:
        return main_pruebas()

    v = Verificador()
    malla = json.load(open(RUTA_MALLA, encoding="utf-8"))
    casos = [json.loads(l) for l in open(RUTA_CASOS, encoding="utf-8") if l.strip()]
    if args.limite:
        casos = casos[:args.limite]

    if args.modelo_falso:
        modelo = ModeloFalso([
            '{"ramo": "503203", "periodo": "actual"}',
            '{"estado_actual": "no_cursada", "prerrequisitos": [], '
            '"creditos_aprobados": 0, "umbral_creditos": null, "requisitos_especiales": []}',
            '{"decision": "no", "regla": "R-SIN-IMPEDIMENTO"}',
        ])
        modelo.nombre = "falso"
    else:
        from runner import ModeloHF
        # El baseline usa 64 tokens de salida, que le bastan para sus dos campos. La ficha
        # del paso 2 es más larga: con dos prerrequisitos y un requisito especial pasa de
        # los 64 y se cortaría a media respuesta, dejando un JSON ilegible. Eso marcaría
        # como error de razonamiento lo que sería una falta de presupuesto de salida.
        modelo = ModeloHF(args.modelo, max_new_tokens=256)

    etq = args.modelo.split("/")[-1] if not args.modelo_falso else "falso"
    RESULTADOS.mkdir(exist_ok=True)
    salida = RESULTADOS / f"pipeline__{etq}__{args.variante}__{args.modo}.raw.jsonl"

    print(f"{len(casos)} casos · {etq} · variante {args.variante} · modo {args.modo}")
    print(f"salida: {salida.name}\n")
    correr(modelo, casos, v, malla, args.variante, args.modo, salida)
    resumen(salida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
