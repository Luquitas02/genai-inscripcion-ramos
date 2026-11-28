# -*- coding: utf-8 -*-
"""
Genera los prompts del control del D4: el prompt v3 del Intérprete sin otro cambio que el
bloque de ejemplos. A los 4 ejemplos escritos a mano se suman pares del mismo tipo de los que
se usan para entrenar. Así el control y el ajuste ven los mismos ejemplos, uno en el prompt y el
otro en los pesos (Lecture 8, láminas 2 y 24).

Dos modos:

  --piloto   `prompts/d4/interprete_muchos_ejemplos.md`, el control del PILOTO (13 nov): 40
             pares de plantilla de `datos_d4.generar_pares`. Cruzó los 4.096 tokens de Phi-3.5 y
             se rompió. Se deja para reproducir el piloto.

  (defecto)  `prompts/d4/interprete_control.md`, el control de la PRUEBA SELLADA
             (PROTOCOLO_D4.md): pares de `datos/entrenamiento_d4/entrenamiento.jsonl` (los
             bloques prosa, plantilla y sin_ramo; la revisión tiene otro formato de entrada), en
             un orden al azar fijo, agregados mientras el prompt completo del Intérprete, con
             la consulta más larga de los datos de entrenamiento, no pase de 3.600 tokens del
             tokenizador de Phi-3.5. Así quedan 256 tokens de salida bajo el límite de 4.096.

    python gen_prompt_control_d4.py
    python gen_prompt_control_d4.py --piloto --n 40
"""

import argparse
import json
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PROMPTS = RAIZ / "prompts"
ORIGEN = PROMPTS / "interprete.md"
FIN = "<!-- /ejemplos -->"
ENTRENAMIENTO = RAIZ / "datos" / "entrenamiento_d4" / "entrenamiento.jsonl"
MODELO = "microsoft/Phi-3.5-mini-instruct"


def ejemplo(pregunta, completion):
    return f'Consulta: "{pregunta}"\n{completion}\n'


def piloto(texto, n, semilla):
    from datos_d4 import generar_pares
    extra = [ejemplo(p["meta"]["pregunta"], p["completion"][0]["content"])
             for p in generar_pares(n, semilla)]
    cabecera = (f"<!-- control del D4 (piloto): prompt v3 del Intérprete con {n} ejemplos más,\n"
                f"     generados por scripts/gen_prompt_control_d4.py (semilla {semilla}). -->\n")
    return PROMPTS / "d4" / "interprete_muchos_ejemplos.md", cabecera + texto.replace(
        FIN, "\n".join(extra) + FIN), n


def tokens_del_prompt(tok, archivo):
    """Tokens de entrada del Intérprete con la consulta más larga de los datos de entrenamiento,
    medidos como los ve Phi: con su plantilla de chat."""
    import agentes as A
    p = A.Prompt(archivo)
    pares = [json.loads(l) for l in open(ENTRENAMIENTO, encoding="utf-8") if l.strip()]
    larga = max((x["meta"]["pregunta"] for x in pares), key=len)
    msgs = p.mensajes(pregunta=larga, revision="")
    # En transformers 5, apply_chat_template(tokenize=True) devuelve un diccionario: se
    # arma el texto y se tokeniza aparte, como lo hace runner_d3.cargar_modelo.
    texto = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
    return len(tok(texto, add_special_tokens=False)["input_ids"])


def sellada(texto, semilla, maximo):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODELO)
    pares = [json.loads(l) for l in open(ENTRENAMIENTO, encoding="utf-8") if l.strip()]
    pares = [x for x in pares if x["meta"]["bloque"] in ("prosa", "plantilla", "sin_ramo")]
    random.Random(semilla).shuffle(pares)
    destino = PROMPTS / "d4" / "interprete_control.md"
    relativo = "d4/interprete_control.md"
    destino.parent.mkdir(exist_ok=True)

    def armar(k):
        extra = [ejemplo(x["meta"]["pregunta"], x["completion"][0]["content"]) for x in pares[:k]]
        cabecera = (f"<!-- control del D4 (prueba sellada, PROTOCOLO_D4.md): prompt v3 del Intérprete\n"
                    f"     con {k} ejemplos más de datos/entrenamiento_d4/entrenamiento.jsonl, en orden\n"
                    f"     al azar con semilla {semilla}, hasta {maximo} tokens de entrada.\n"
                    f"     Lo genera scripts/gen_prompt_control_d4.py. -->\n")
        return cabecera + texto.replace(FIN, "\n".join(extra) + FIN)

    k, medidos = 0, None
    while k < len(pares):
        destino.write_text(armar(k + 1), encoding="utf-8", newline="\n")
        t = tokens_del_prompt(tok, relativo)
        if t > maximo:
            break
        k, medidos = k + 1, t
    destino.write_text(armar(k), encoding="utf-8", newline="\n")
    assert tokens_del_prompt(tok, relativo) == medidos
    print(f"tokens de entrada con la consulta más larga: {medidos} (máximo {maximo})")
    return destino, None, k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--piloto", action="store_true")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--semilla", type=int, default=None)
    ap.add_argument("--max-tokens", type=int, default=3600)
    a = ap.parse_args()
    texto = ORIGEN.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert texto.count(FIN) == 1
    if a.piloto:
        destino, nuevo, k = piloto(texto, a.n, a.semilla or 20261115)
        destino.parent.mkdir(exist_ok=True)
        destino.write_text(nuevo, encoding="utf-8", newline="\n")
    else:
        destino, _, k = sellada(texto, a.semilla or 20261202, a.max_tokens)
    print(f"{destino.relative_to(RAIZ)}: 4 + {k} ejemplos")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
