# -*- coding: utf-8 -*-
"""
Demostración — Deliverable 2.

Corre el baseline y el sistema sobre los MISMOS casos, en vivo, y los muestra lado a lado.
Es lo que se graba para el video.

La rúbrica pide que el input no esté elegido para favorecer al sistema. El video corre los
diez primeros casos de nivel 3, del 40 al 49, sin saltarse ninguno:

  caso 40   el primer caso de nivel 3. Se muestra completo, con los tres pasos a la vista.
            La regla que lo elige quedó escrita en PLAN_D2_TAREAS.md (commit c8e0cca, 17 de
            septiembre) antes de correr el sistema. El sistema falla acá, y es el caso de
            falla que la guía exige.

  41 a 49   los nueve siguientes, una línea por caso, con el conteo de aciertos al final.
            Según la corrida guardada, el baseline acierta 1 de 10 y el sistema 4 de 10.

Cada salida del modelo se compara con la que quedó guardada en resultados/, así que lo que se
ve en el video se puede rastrear hasta el repositorio. La demo aplica la misma lógica que
runner_d2.py con la variante `codigo`: si el paso 1 no devuelve un código de la malla, el caso
se pierde, igual que en la corrida medida.

El modelo se carga UNA vez y sirve para todos los casos. Cargar Phi en 4 bits toma minutos y
la ejecución real toma segundos, así que conviene tenerlo en memoria antes de grabar.

Uso:
    python demo.py                            # caso 40 completo y 41-49 en una línea
    python demo.py --detalle 40 --casos 40 41 42
    python demo.py --modelo-falso             # sin GPU: prueba de formato, respuestas fijas

Desde un notebook, con el modelo ya cargado en una celda anterior:
    import demo
    demo.video(modelo)
"""

import argparse
import json
import time
from pathlib import Path

from verificador import Verificador, RUTA_MALLA
from ficha import construir_ficha, decidir_desde_ficha, render_ficha, RUTA_CASOS
import prompt as P
import pipeline as PL

BASE = Path(__file__).resolve().parent.parent
RESULTADOS = BASE / "resultados"

MODELO_POR_DEFECTO = "microsoft/Phi-3.5-mini-instruct"
CASOS_VIDEO = list(range(40, 50))
CASO_DETALLE = 40

# El baseline del Deliverable 1 corrió con 64 tokens de salida (runner.py). Se usa el mismo
# tope para que la salida en vivo sea comparable con la guardada.
TOKENS_BASELINE = 64

ARCHIVO_BASELINE = "Phi-3.5-mini-instruct__few_shot__prosa.raw.jsonl"
ARCHIVO_SISTEMA = "pipeline__Phi-3.5-mini-instruct__codigo__encadenado.raw.jsonl"

ANCHO = 78


def titulo(texto, car="="):
    print()
    print(car * ANCHO)
    print(texto)
    print(car * ANCHO)


def acierta(pred, esperado):
    return (pred.get("decision") == esperado["decision"]
            and pred.get("regla") == esperado["regla"])


def veredicto(ok):
    return "CORRECTO" if ok else "INCORRECTO"


def cargar_contexto():
    """Devuelve (verificador, malla, casos). No toca el modelo."""
    v = Verificador()
    malla = json.load(open(RUTA_MALLA, encoding="utf-8"))
    casos = [json.loads(l) for l in open(RUTA_CASOS, encoding="utf-8") if l.strip()]
    return v, malla, casos


def cargar_guardado(nombre):
    """Lee una corrida guardada en resultados/, indexada por id. Vacío si no está."""
    ruta = RESULTADOS / nombre
    if not ruta.exists():
        return {}
    filas = [json.loads(l) for l in open(ruta, encoding="utf-8") if l.strip()]
    return {str(f["id"]): f for f in filas}


def _generar(modelo, mensajes, max_tokens=None):
    """Llama al modelo con un tope de salida opcional y devuelve (texto, tokens, segundos)."""
    previo = getattr(modelo, "max_new_tokens", None)
    if max_tokens is not None and previo is not None:
        modelo.max_new_tokens = max_tokens
    try:
        t0 = time.perf_counter()
        crudo, tok = modelo.generar(mensajes)
        return crudo, tok, time.perf_counter() - t0
    finally:
        if previo is not None:
            modelo.max_new_tokens = previo


def _coincide(vivo, guardado):
    if guardado is None:
        return "sin corrida guardada para comparar"
    return ("igual a la corrida guardada" if vivo.strip() == guardado.strip()
            else "DISTINTA de la corrida guardada")


def ejecutar(n_caso, modelo, v, malla, casos):
    """Corre baseline y sistema sobre un caso. No imprime nada; devuelve lo que pasó.

    El sistema sigue a runner_d2.py con variante `codigo` y modo `encadenado`.
    """
    caso = casos[n_caso]
    ramo_real = caso["consulta"]["ramos"][0]

    # baseline: una llamada con el prompt del Deliverable 1
    mensajes = P.construir(caso, malla, condicion="few_shot", usar_prosa=True)
    crudo_b, tok_b, seg_b = _generar(modelo, mensajes, TOKENS_BASELINE)
    pred_b = P.parsear_respuesta(crudo_b)

    # paso 1: el modelo extrae ramo y período de la pregunta
    crudo1, tok1, seg1 = _generar(modelo, PL.prompt_paso1(caso, malla))
    p1 = PL.parsear_paso1(crudo1, set(v.asig))
    ramo, per = p1["ramo"], p1["periodo"]
    if ramo is not None and per is None:
        per = "actual"      # mismo valor por defecto que runner_d2.py

    f, d = None, {"decision": None, "regla": None}
    if ramo is not None:
        # paso 2 y paso 3: el código arma la ficha y aplica las reglas
        f = construir_ficha(v, caso["historial"], ramo, per,
                            caso["consulta"]["creditos_ya_inscritos"])
        d = decidir_desde_ficha(v, f)

    return {
        "caso": caso, "ramo_real": ramo_real,
        "crudo_b": crudo_b, "tok_b": tok_b, "seg_b": seg_b, "pred_b": pred_b,
        "ok_b": acierta(pred_b, caso["respuesta"]),
        "crudo1": crudo1, "tok1": tok1, "seg1": seg1, "p1": p1, "ramo": ramo, "per": per,
        "ficha": f, "pred_s": d, "ok_s": acierta(d, caso["respuesta"]),
    }


def mostrar_detalle(n_caso, r, v, malla, guard_b, guard_s):
    caso = r["caso"]
    ramo_real = r["ramo_real"]
    gb = guard_b.get(str(n_caso))
    gs = guard_s.get(str(n_caso))

    titulo(f"CASO {n_caso}   ·   nivel {caso['nivel']}   ·   {', '.join(caso['rasgos'])}")
    print()
    print("  PREGUNTA DEL ESTUDIANTE")
    print(f'    "{caso["pregunta_prosa"]}"')
    print()
    print(f"  HISTORIAL: {len(caso['historial'])} asignaturas")
    print(f"  MALLA:     {len(malla['asignaturas'])} asignaturas con sus prerrequisitos")
    print()
    print(f"  RESPUESTA CORRECTA:  {caso['respuesta']['decision']}  ·  "
          f"regla {caso['respuesta']['regla']}")
    print(f"    {caso['detalle']}")

    titulo("BASELINE DEL DELIVERABLE 1   ·   una llamada, prompt directo")
    print()
    print(f"  entra:  {r['tok_b']:,} tokens   (malla completa + reglas + historial + 3 ejemplos)")
    print(f"  sale:   {r['crudo_b'].strip()[:120]}")
    print(f"          [{_coincide(r['crudo_b'], gb and gb.get('crudo'))}]")
    print(f"  tiempo: {r['seg_b']:.1f} s")
    print()
    print(f"  >>> {r['pred_b']['decision']} · {r['pred_b']['regla']}   ->   "
          f"{veredicto(r['ok_b'])}")

    titulo("SISTEMA DEL DELIVERABLE 2   ·   tres pasos, contexto enfocado")
    print()
    print("  PASO 1 · EXTRACCIÓN   (el modelo)")
    print("    ve: la pregunta y los 61 pares de código y nombre")
    print("    no ve: el historial, la malla con prerrequisitos, las reglas")
    print(f"    entra: {r['tok1']:,} tokens   sale: {r['crudo1'].strip()[:80]}")
    print(f"           [{_coincide(r['crudo1'], gs and gs['paso1']['crudo'])}]")
    p1 = r["p1"]
    marca = "ok" if p1["ramo"] == ramo_real else f"ERROR, el ramo era {ramo_real}"
    print(f"    ramo {p1['ramo']} · período {p1['periodo']}   [{marca}]")

    if r["ramo"] is None:
        print()
        print("    el paso 1 no devolvió un código de la malla: el caso se pierde,")
        print("    igual que en la corrida medida")
    else:
        print()
        print("  PASO 2 · FICHA DEL CASO   (el código, determinista)")
        f = r["ficha"]
        descartadas = len(caso["historial"]) - len(f["prerrequisitos"])
        print(f"    descarta {descartadas} asignaturas del historial que no tocan este ramo")
        print()
        for linea in render_ficha(f).splitlines():
            print("      " + linea)
        print()
        print("  PASO 3 · DECISIÓN   (el código, determinista)")
        print("    aplica las reglas del reglamento sobre la ficha")
        print(f"    regla que dispara: {r['pred_s']['regla']}")
        print(f"    decisión derivada: {r['pred_s']['decision']}")

    print()
    print(f"  >>> {r['pred_s']['decision']} · {r['pred_s']['regla']}   ->   "
          f"{veredicto(r['ok_s'])}")

    titulo("LADO A LADO")
    print()
    print(f"  {'':10} {'decisión':14} {'regla':26} {'tokens':>8} {'seg':>6}")
    print("  " + "-" * (ANCHO - 4))
    print(f"  {'baseline':10} {str(r['pred_b']['decision']):14} {str(r['pred_b']['regla']):26} "
          f"{r['tok_b']:8,} {r['seg_b']:6.1f}   {veredicto(r['ok_b'])}")
    print(f"  {'sistema':10} {str(r['pred_s']['decision']):14} {str(r['pred_s']['regla']):26} "
          f"{r['tok1']:8,} {r['seg1']:6.1f}   {veredicto(r['ok_s'])}")
    print(f"  {'correcto':10} {caso['respuesta']['decision']:14} "
          f"{caso['respuesta']['regla']:26}")

    if not r["ok_s"] and r["ramo"] is not None and r["ramo"] != ramo_real:
        print()
        print("  POR QUÉ FALLA EL SISTEMA")
        print(f"    El paso 1 devolvió {r['ramo']} ({v.asig[r['ramo']]['nombre']}) en vez de "
              f"{ramo_real} ({v.asig[ramo_real]['nombre']}).")
        print(f"    Los pasos 2 y 3 evaluaron {r['ramo']}, así que la respuesta corresponde")
        print("    a ese ramo.")


def mostrar_linea(n_caso, r, guard_b, guard_s):
    gb = guard_b.get(str(n_caso))
    gs = guard_s.get(str(n_caso))
    iguales = (gb is not None and gs is not None
               and r["crudo_b"].strip() == gb["crudo"].strip()
               and r["crudo1"].strip() == gs["paso1"]["crudo"].strip())
    marca_ramo = "ok " if r["ramo"] == r["ramo_real"] else "mal"
    print(f"  {n_caso:>4}   {veredicto(r['ok_b']):10}   {veredicto(r['ok_s']):10}   "
          f"ramo {marca_ramo}   {'= guardada' if iguales else '≠ guardada'}")


def resumen_guardado(guard_b, guard_s):
    """Cifras sobre los 60 casos, leídas de la corrida guardada, no escritas a mano."""
    if not guard_b or not guard_s:
        return
    n = len(guard_s)
    ab = sum(bool(f["acierto_conjunto"]) for f in guard_b.values())
    as_ = sum(bool(f["acierto_conjunto"]) for f in guard_s.values())
    pct = lambda k: f"{100 * k / n:.1f}".replace(".", ",")
    print()
    print(f"  Sobre los {n} casos (leído de resultados/):  baseline {ab}/{n} ({pct(ab)} %)"
          f"  ·  sistema {as_}/{n} ({pct(as_)} %)")


def video(modelo, casos_video=CASOS_VIDEO, caso_detalle=CASO_DETALLE):
    """Lo que se graba: un caso completo y el resto en una línea cada uno."""
    v, malla, casos = cargar_contexto()
    guard_b = cargar_guardado(ARCHIVO_BASELINE)
    guard_s = cargar_guardado(ARCHIVO_SISTEMA)

    filas = []
    for n in casos_video:
        r = ejecutar(n, modelo, v, malla, casos)
        filas.append((n, r))
        if n == caso_detalle:
            mostrar_detalle(n, r, v, malla, guard_b, guard_s)
            titulo(f"CASOS {casos_video[0]} A {casos_video[-1]}, SIN SALTARSE NINGUNO")
            print()
            print(f"  {'caso':>4}   {'baseline':10}   {'sistema':10}   paso 1     en vivo vs repo")
            print("  " + "-" * (ANCHO - 4))
        mostrar_linea(n, r, guard_b, guard_s)

    k = len(filas)
    ab = sum(r["ok_b"] for _, r in filas)
    as_ = sum(r["ok_s"] for _, r in filas)
    print("  " + "-" * (ANCHO - 4))
    print(f"  total  baseline {ab}/{k}   sistema {as_}/{k}")
    resumen_guardado(guard_b, guard_s)
    return filas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--casos", type=int, nargs="+", default=CASOS_VIDEO)
    ap.add_argument("--detalle", type=int, default=CASO_DETALLE,
                    help="caso que se muestra completo, con los tres pasos")
    ap.add_argument("--modelo", default=MODELO_POR_DEFECTO)
    ap.add_argument("--modelo-falso", action="store_true",
                    help="sin GPU: respuestas fijas, solo para probar el formato")
    args = ap.parse_args()

    if args.modelo_falso:
        from runner_d2 import ModeloFalso
        print("*** MODELO FALSO: respuestas fijas, no es una ejecución del modelo ***")
        modelo = ModeloFalso(['{"decision": "condicional", "regla": "R-DEPENDE-APROBACION"}',
                              '{"ramo": "503203", "periodo": "actual"}'])
    else:
        from runner import ModeloHF
        print(f"cargando {args.modelo} en 4 bits, una sola vez...")
        modelo = ModeloHF(args.modelo, max_new_tokens=256)

    video(modelo, args.casos, args.detalle)
    return 0


if __name__ == "__main__":
    # La consola de Windows no escribe en UTF-8 por defecto y rompe los acentos.
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
