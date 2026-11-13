# -*- coding: utf-8 -*-
"""
Entrenamiento QLoRA del Intérprete (A) — Deliverable 4. Corre en una T4 de Colab.

La receta es la de la Lecture 8 (lámina 17): base en 4 bits NF4, adaptador LoRA de rango 16 en
todas las capas lineales, alpha 32, dropout 0,05, learning rate 2e-4, pérdida solo sobre la
respuesta (láminas 9 y 17). Tres diferencias, declaradas:
  - fp16 en vez de bfloat16: la T4 no tiene bfloat16 (la lámina asume una L4 o A100).
  - la cuantización es la misma con que el sistema del D3 corre Phi (NF4, cómputo en fp16, sin
    doble cuantización), para que el adaptador se use sobre exactamente la base con que se
    entrenó.
  - formato prompt-completion en vez de `assistant_only_loss`: la pérdida queda solo en la
    respuesta sin depender de que la plantilla de chat de Phi marque los turnos del asistente.

Guarda en --salida: el adaptador, `historial.json` (pérdida de entrenamiento y validación por
paso), `curvas.png`, y `config.json` con hiperparámetros, versiones, tiempo y memoria.

    python entrenar_d4.py --datos ../datos/entrenamiento_piloto --salida ../adaptadores/piloto
"""

import argparse
import json
import time
from importlib.metadata import version
from pathlib import Path

MODELO = "microsoft/Phi-3.5-mini-instruct"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datos", required=True)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--epocas", type=float, default=1.0)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--rango", type=int, default=16)
    ap.add_argument("--batch", type=int, default=2)
    ap.add_argument("--acumulacion", type=int, default=4)
    ap.add_argument("--max-length", type=int, default=2048)
    ap.add_argument("--semilla", type=int, default=20261114)
    ap.add_argument("--modelo", default=MODELO)
    ap.add_argument("--prueba-cpu", action="store_true",
                    help="sin GPU, sin 4 bits y en fp32: solo para probar el código con un modelo diminuto")
    a = ap.parse_args()
    cpu = a.prueba_cpu

    import torch
    from datasets import load_dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)
    datos = Path(a.datos)
    ds = load_dataset("json", data_files={"train": str(datos / "entrenamiento.jsonl"),
                                          "validation": str(datos / "validacion.jsonl")})
    ds = ds.remove_columns([c for c in ds["train"].column_names if c not in ("prompt", "completion")])

    tok = AutoTokenizer.from_pretrained(a.modelo)
    if cpu:
        modelo = AutoModelForCausalLM.from_pretrained(a.modelo, dtype=torch.float32)
    else:
        bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16,
                                 bnb_4bit_quant_type="nf4")
        modelo = AutoModelForCausalLM.from_pretrained(a.modelo, quantization_config=bnb,
                                                      dtype=torch.float16, device_map="auto")
    revision = getattr(modelo.config, "_commit_hash", None)

    lora = LoraConfig(r=a.rango, lora_alpha=2 * a.rango, lora_dropout=0.05,
                      target_modules="all-linear", task_type="CAUSAL_LM")
    args = SFTConfig(
        output_dir=str(salida / "checkpoints"), num_train_epochs=a.epocas, learning_rate=a.lr,
        per_device_train_batch_size=a.batch, per_device_eval_batch_size=a.batch,
        gradient_accumulation_steps=a.acumulacion, max_length=a.max_length,
        completion_only_loss=True, fp16=not cpu, bf16=False, gradient_checkpointing=not cpu,
        use_cpu=cpu,
        logging_steps=1, eval_strategy="steps", eval_steps=5, save_strategy="no",
        lr_scheduler_type="linear", warmup_steps=3, seed=a.semilla, report_to="none",
    )
    entrenador = SFTTrainer(model=modelo, args=args, train_dataset=ds["train"],
                            eval_dataset=ds["validation"], processing_class=tok, peft_config=lora)
    # Con fp16, los pesos que se entrenan tienen que estar en fp32 o el escalador de
    # gradientes falla ("Attempting to unscale FP16 gradients").
    for p in entrenador.model.parameters():
        if p.requires_grad:
            p.data = p.data.float()
    entrenables = sum(p.numel() for p in entrenador.model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in entrenador.model.parameters())

    if not cpu:
        torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    entrenador.train()
    segundos = time.perf_counter() - t0
    final = entrenador.evaluate()

    entrenador.model.save_pretrained(str(salida))
    tok.save_pretrained(str(salida))
    historial = entrenador.state.log_history
    (salida / "historial.json").write_text(json.dumps(historial, indent=1), encoding="utf-8")
    config = {
        "modelo_base": a.modelo, "revision_base": revision,
        "cuantizacion": "NF4, cómputo fp16, sin doble cuantización",
        "lora": {"r": a.rango, "alpha": 2 * a.rango, "dropout": 0.05, "modulos": "all-linear"},
        "epocas": a.epocas, "lr": a.lr, "batch": a.batch, "acumulacion": a.acumulacion,
        "batch_efectivo": a.batch * a.acumulacion, "max_length": a.max_length,
        "semilla": a.semilla, "precision": "fp16", "perdida": "solo la respuesta (prompt-completion)",
        "n_entrenamiento": len(ds["train"]), "n_validacion": len(ds["validation"]),
        "pasos": entrenador.state.global_step, "segundos": round(segundos, 1),
        "memoria_max_gb": None if cpu else round(torch.cuda.max_memory_allocated() / 2 ** 30, 2),
        "gpu": "cpu (prueba)" if cpu else torch.cuda.get_device_name(0),
        "parametros_entrenables": entrenables, "parametros_total": total,
        "perdida_validacion_final": final.get("eval_loss"),
        "versiones": versiones(),
    }
    (salida / "config.json").write_text(json.dumps(config, indent=1, ensure_ascii=False),
                                        encoding="utf-8")
    graficar(historial, salida / "curvas.png")
    print(json.dumps(config, indent=1, ensure_ascii=False))


def versiones():
    v = {}
    for p in ("torch", "transformers", "peft", "trl", "bitsandbytes", "accelerate", "datasets"):
        try:
            v[p] = version(p)
        except Exception:
            v[p] = None
    return v


def graficar(historial, ruta):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    tr = [(h["step"], h["loss"]) for h in historial if "loss" in h]
    ev = [(h["step"], h["eval_loss"]) for h in historial if "eval_loss" in h]
    fig, ax = plt.subplots(figsize=(4.2, 2.6), dpi=150)
    if tr:
        ax.plot(*zip(*tr), lw=1, color="#1f5aa6", label="entrenamiento")
    if ev:
        ax.plot(*zip(*ev), lw=1.6, marker="o", ms=2.5, color="#d0632a", label="validación")
    ax.set_xlabel("paso")
    ax.set_ylabel("pérdida")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(ruta)


if __name__ == "__main__":
    raise SystemExit(main())
