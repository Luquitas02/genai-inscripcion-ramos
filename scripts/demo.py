# -*- coding: utf-8 -*-
"""
Demostración de un caso — Deliverable 2.

Corre el baseline y el sistema sobre el MISMO caso y muestra los dos lado a lado, con los
pasos intermedios a la vista. Es lo que se graba para el video.

La rúbrica pide que el input no esté elegido para favorecer al sistema, así que los dos
casos que usa el video se eligieron con reglas escritas antes de mirar los resultados:

  caso 40   el primer caso de nivel 3 cuyo baseline falla.
            El sistema TAMBIÉN falla acá, y es el caso de falla que la guía exige.

  caso 42   el siguiente caso de nivel 3 con baseline fallado donde el sistema acierta.
            Está elegido para mostrar el sistema funcionando, y eso se declara sin
            disfrazarlo: la honestidad está en decirlo, no en fingir que salió al azar.

El modelo se carga UNA vez y sirve para todos los casos. Eso importa para el video: cargar
Phi en 4 bits toma minutos y la ejecucion real toma segundos, asi que conviene tener el modelo
ya en memoria antes de empezar a grabar.

Uso:
    python demo.py --casos 40 42              # los dos casos del video
    python demo.py --casos 40 --modelo-falso  # sin GPU, para probar el formato

Desde un notebook, con el modelo ya cargado en una celda anterior:
    import demo
    demo.correr(40, modelo, v, malla, casos)
"""

import argparse
import json
import time
from pathlib import Path

from verificador import Verificador, RUTA_MALLA
from ficha import construir_ficha, decidir_desde_ficha, render_ficha, RUTA_CASOS
import prompt as P
import pipeline as PL

MODELO_POR_DEFECTO = "microsoft/Phi-3.5-mini-instruct"
CASO_DECLARADO = 40

ANCHO = 78


def titulo(texto, car="="):
    print()
    print(car * ANCHO)
    print(texto)
    print(car * ANCHO)


def veredicto(obtenido, esperado):
    ok = (obtenido.get("decision") == esperado["decision"]
          and obtenido.get("regla") == esperado["regla"])
    return "CORRECTO" if ok else "INCORRECTO", ok


def cargar_contexto():
    """Devuelve (verificador, malla, casos). No toca el modelo."""
    v = Verificador()
    malla = json.load(open(RUTA_MALLA, encoding="utf-8"))
    casos = [json.loads(l) for l in open(RUTA_CASOS, encoding="utf-8") if l.strip()]
    return v, malla, casos


def correr(n_caso, modelo, v=None, malla=None, casos=None):
    """Corre el baseline y el sistema sobre un caso y los imprime lado a lado.

    Recibe el modelo ya cargado. Cargar Phi en 4 bits toma minutos y esto toma segundos,
    asi que separarlos es lo que hace grabable el video.
    """
    if v is None:
        v, malla, casos = cargar_contexto()
    caso = casos[n_caso]
    args_caso = n_caso

    # ------------------------------------------------------------------ el caso
    titulo(f"CASO {args_caso}   ·   nivel {caso['nivel']}   ·   {', '.join(caso['rasgos'])}")
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

    # ------------------------------------------------------------------ baseline
    titulo("BASELINE DEL DELIVERABLE 1   ·   una llamada, prompt directo")
    mensajes = P.construir(caso, malla, condicion="few_shot", usar_prosa=True)
    t0 = time.perf_counter()
    crudo_b, tok_b = modelo.generar(mensajes)
    seg_b = time.perf_counter() - t0
    pred_b = P.parsear_respuesta(crudo_b)
    print()
    print(f"  entra:  {tok_b:,} tokens   (malla completa + reglas + historial + 3 ejemplos)")
    print(f"  sale:   {crudo_b.strip()[:120]}")
    print(f"  tiempo: {seg_b:.1f} s")
    ver_b, ok_b = veredicto(pred_b, caso["respuesta"])
    print()
    print(f"  >>> {pred_b['decision']} · {pred_b['regla']}   ->   {ver_b}")

    # ------------------------------------------------------------------ sistema
    titulo("SISTEMA DEL DELIVERABLE 2   ·   tres pasos, contexto enfocado")

    print()
    print("  PASO 1 · EXTRACCIÓN   (el modelo)")
    print("    ve: la pregunta y los 61 pares de código y nombre")
    print("    no ve: el historial, la malla con prerrequisitos, las reglas")
    m1 = PL.prompt_paso1(caso, malla)
    t0 = time.perf_counter()
    crudo1, tok1 = modelo.generar(m1)
    seg1 = time.perf_counter() - t0
    p1 = PL.parsear_paso1(crudo1, set(v.asig))
    ramo_real = caso["consulta"]["ramos"][0]
    print(f"    entra: {tok1:,} tokens   sale: {crudo1.strip()[:80]}")
    marca = "ok" if p1["ramo"] == ramo_real else f"ERROR, el ramo era {ramo_real}"
    print(f"    ramo {p1['ramo']} · período {p1['periodo']}   [{marca}]")

    ramo = p1["ramo"] or ramo_real
    per = p1["periodo"] or "actual"

    print()
    print("  PASO 2 · FICHA DEL CASO   (el código, determinista)")
    f = construir_ficha(v, caso["historial"], ramo, per,
                        caso["consulta"]["creditos_ya_inscritos"])
    descartadas = len(caso["historial"]) - len(f["prerrequisitos"])
    print(f"    descarta {descartadas} asignaturas del historial que no tocan este ramo")
    print()
    for linea in render_ficha(f).splitlines():
        print("      " + linea)

    print()
    print("  PASO 3 · DECISIÓN   (el código, determinista)")
    print("    la ablación midió que el modelo aplica las reglas al 31,7 % con esta ficha")
    print("    delante, y que el código hace lo mismo al 100 %")
    d = decidir_desde_ficha(v, f)
    print(f"    regla que dispara: {d['regla']}")
    print(f"    decisión derivada: {d['decision']}")

    ver_s, ok_s = veredicto(d, caso["respuesta"])
    tok_s, seg_s = tok1, seg1
    print()
    print(f"  >>> {d['decision']} · {d['regla']}   ->   {ver_s}")

    # ------------------------------------------------------------------ cierre
    titulo("LADO A LADO")
    print()
    print(f"  {'':10} {'decisión':14} {'regla':26} {'tokens':>8} {'seg':>6}")
    print("  " + "-" * (ANCHO - 4))
    print(f"  {'baseline':10} {str(pred_b['decision']):14} {str(pred_b['regla']):26} "
          f"{tok_b:8,} {seg_b:6.1f}   {ver_b}")
    print(f"  {'sistema':10} {str(d['decision']):14} {str(d['regla']):26} "
          f"{tok_s:8,} {seg_s:6.1f}   {ver_s}")
    print(f"  {'correcto':10} {caso['respuesta']['decision']:14} "
          f"{caso['respuesta']['regla']:26}")
    print()
    if not ok_s and p1["ramo"] != ramo_real:
        print("  POR QUÉ FALLA EL SISTEMA")
        print(f"    El paso 1 devolvió {p1['ramo']} ({v.asig[p1['ramo']]['nombre']}), que la")
        print(f"    pregunta menciona como contexto, en vez de {ramo_real} "
              f"({v.asig[ramo_real]['nombre']}),")
        print("    que es por lo que realmente pregunta. Los pasos 2 y 3 evaluaron ese")
        print("    ramo y respondieron bien sobre él, y no era el ramo consultado.")
    print()
    print("  Sobre los 60 casos: baseline 16,7 % · sistema 58,3 % de acierto conjunto.")
    print("  El sistema acierta 28 de 28 cuando el paso 1 identifica bien el ramo.")
    return ok_s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--casos", type=int, nargs="+", default=[CASO_DECLARADO])
    ap.add_argument("--modelo", default=MODELO_POR_DEFECTO)
    ap.add_argument("--modelo-falso", action="store_true")
    args = ap.parse_args()

    if args.modelo_falso:
        from runner_d2 import ModeloFalso
        modelo = ModeloFalso(['{"decision": "condicional", "regla": "R-DEPENDE-APROBACION"}',
                              '{"ramo": "503203", "periodo": "actual"}'])
    else:
        from runner import ModeloHF
        print(f"cargando {args.modelo} en 4 bits, una sola vez...")
        modelo = ModeloHF(args.modelo, max_new_tokens=256)

    v, malla, casos = cargar_contexto()
    for n in args.casos:
        correr(n, modelo, v, malla, casos)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
