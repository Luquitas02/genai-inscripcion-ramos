# -*- coding: utf-8 -*-
"""
Runner de evaluación — corre un modelo sobre los casos y mide.

Diseñado para una Colab gratuita, que se desconecta sin avisar:
  - Guarda CASO A CASO en un .jsonl, no al final.
  - Si el archivo de salida ya existe, retoma donde iba en vez de empezar de nuevo.
  - Mide el tiempo de cada caso, que es la evidencia del ítem de factibilidad.

Uso:
    python runner.py --modelo Qwen/Qwen2.5-7B-Instruct --condicion zero_shot
    python runner.py --modelo Qwen/Qwen2.5-7B-Instruct --condicion few_shot --limpia
"""

import argparse
import json
import time
from pathlib import Path

from verificador import RUTA_MALLA
import prompt as P

BASE = Path(__file__).resolve().parent.parent
CASOS = BASE / "datos" / "casos.jsonl"
RESULTADOS = BASE / "resultados"


def cargar_casos(ruta):
    with open(ruta, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def cargar_malla(ruta=RUTA_MALLA):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------- modelo

class ModeloHF:
    """Carga un modelo de Hugging Face en 4 bits. Cabe cómodo en una T4 de 15 GB."""

    def __init__(self, nombre, max_new_tokens=64, cuatro_bits=True):
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM

        self.nombre = nombre
        self.max_new_tokens = max_new_tokens
        self.tok = AutoTokenizer.from_pretrained(nombre)

        kwargs = {"device_map": "auto", "dtype": torch.float16}
        if cuatro_bits:
            try:
                from transformers import BitsAndBytesConfig
                kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_quant_type="nf4",
                )
            except ImportError:
                print("bitsandbytes no disponible; cargando en fp16")

        self.modelo = AutoModelForCausalLM.from_pretrained(nombre, **kwargs)
        self.modelo.eval()

    def generar(self, mensajes):
        import torch
        texto = self.tok.apply_chat_template(
            mensajes, tokenize=False, add_generation_prompt=True)
        ent = self.tok(texto, return_tensors="pt").to(self.modelo.device)
        n_in = ent["input_ids"].shape[1]
        with torch.no_grad():
            out = self.modelo.generate(
                **ent,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,                      # determinista: el baseline no se sortea
                pad_token_id=self.tok.eos_token_id,
            )
        return self.tok.decode(out[0][n_in:], skip_special_tokens=True), n_in


# --------------------------------------------------------------- corrida

def correr(modelo, casos, malla, condicion, usar_prosa, salida):
    hechos = set()
    if salida.exists():
        for l in open(salida, encoding="utf-8"):
            if l.strip():
                hechos.add(json.loads(l)["id"])
        print(f"retomando: {len(hechos)} casos ya corridos")

    f = open(salida, "a", encoding="utf-8")
    for i, caso in enumerate(casos):
        cid = f"{i}"
        if cid in hechos:
            continue
        msgs = P.construir(caso, malla, condicion, usar_prosa)
        t0 = time.time()
        try:
            crudo, n_in = modelo.generar(msgs)
            err = None
        except Exception as e:
            crudo, n_in, err = "", 0, str(e)
        dt = time.time() - t0

        pred = P.parsear_respuesta(crudo)
        esp = caso["respuesta"]
        fila = {
            "id": cid,
            "modelo": modelo.nombre,
            "condicion": condicion,
            "pregunta": "limpia" if not usar_prosa else "prosa",
            "nivel": caso["nivel"],
            "rasgos": caso["rasgos"],
            "ramo": caso["ramo_objetivo"],
            "esperado": esp,
            "prediccion": pred,
            "acierto_decision": pred["decision"] == esp["decision"],
            "acierto_regla": pred["regla"] == esp["regla"],
            "acierto_conjunto": (pred["decision"] == esp["decision"]
                                 and pred["regla"] == esp["regla"]),
            "tokens_entrada": n_in,
            "segundos": round(dt, 2),
            "crudo": crudo.strip()[:400],
            "error": err,
        }
        f.write(json.dumps(fila, ensure_ascii=False) + "\n")
        f.flush()
        marca = "OK" if fila["acierto_conjunto"] else ("~" if fila["acierto_decision"] else "X")
        print(f"[{marca}] {i+1:3}/{len(casos)} n{caso['nivel']} {dt:5.1f}s  "
              f"esp {esp['decision']}/{esp['regla']}  ->  "
              f"pred {pred['decision']}/{pred['regla']}")
    f.close()


# --------------------------------------------------------------- métricas

def resumir(ruta):
    filas = [json.loads(l) for l in open(ruta, encoding="utf-8") if l.strip()]
    if not filas:
        print("sin resultados")
        return

    def pct(sub, campo):
        return 100.0 * sum(r[campo] for r in sub) / len(sub) if sub else 0.0

    print()
    print("=" * 74)
    print(f"{filas[0]['modelo']} · {filas[0]['condicion']} · pregunta {filas[0]['pregunta']}")
    print("=" * 74)
    print(f"{'':10} {'n':>3} {'decisión':>10} {'regla':>10} {'conjunto':>10}")
    print(f"{'TOTAL':10} {len(filas):3} {pct(filas,'acierto_decision'):9.1f}% "
          f"{pct(filas,'acierto_regla'):9.1f}% {pct(filas,'acierto_conjunto'):9.1f}%")
    for n in sorted({r["nivel"] for r in filas}):
        sub = [r for r in filas if r["nivel"] == n]
        print(f"{'nivel '+str(n):10} {len(sub):3} {pct(sub,'acierto_decision'):9.1f}% "
              f"{pct(sub,'acierto_regla'):9.1f}% {pct(sub,'acierto_conjunto'):9.1f}%")

    seg = [r["segundos"] for r in filas]
    tok = [r["tokens_entrada"] for r in filas]
    print(f"\ntiempo por caso: {sum(seg)/len(seg):.1f}s promedio, "
          f"{min(seg):.1f}-{max(seg):.1f}s · tokens de entrada: {sum(tok)//len(tok)} promedio")

    par = {}
    for r in filas:
        par[r["prediccion"]["parseo"]] = par.get(r["prediccion"]["parseo"], 0) + 1
    print(f"parseo de la salida: {par}")

    print("\nmatriz de confusión de la decisión (esperado -> predicho):")
    dec = ["sí", "no", "condicional", None]
    print(f"{'esperado':14}" + "".join(f"{str(d):>13}" for d in dec))
    for e in ["sí", "no", "condicional"]:
        fila = [sum(1 for r in filas
                    if r["esperado"]["decision"] == e and r["prediccion"]["decision"] == d)
                for d in dec]
        print(f"{e:14}" + "".join(f"{v:13}" for v in fila))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--condicion", default="zero_shot", choices=["zero_shot", "few_shot"])
    ap.add_argument("--limpia", action="store_true",
                    help="usar la pregunta limpia en vez de la prosa ambigua")
    ap.add_argument("--casos", default=str(CASOS))
    ap.add_argument("--fp16", action="store_true", help="cargar en fp16 en vez de 4 bits")
    ap.add_argument("--solo-resumen", action="store_true")
    args = ap.parse_args()

    RESULTADOS.mkdir(exist_ok=True)
    etq = args.modelo.split("/")[-1]
    salida = RESULTADOS / (f"{etq}__{args.condicion}__"
                           f"{'limpia' if args.limpia else 'prosa'}.raw.jsonl")

    if not args.solo_resumen:
        casos = cargar_casos(args.casos)
        malla = cargar_malla()
        print(f"{len(casos)} casos · modelo {args.modelo} · {args.condicion} · "
              f"pregunta {'limpia' if args.limpia else 'prosa'}\n")
        modelo = ModeloHF(args.modelo, cuatro_bits=not args.fp16)
        correr(modelo, casos, malla, args.condicion, not args.limpia, salida)

    resumir(salida)


if __name__ == "__main__":
    raise SystemExit(main())
