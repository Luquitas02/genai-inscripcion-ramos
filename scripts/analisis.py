# -*- coding: utf-8 -*-
"""
Análisis de una corrida — las cifras que van al póster.

Lee los .raw.jsonl que produce runner.py y calcula, sin intervención manual:

  - acierto de decisión, de regla y conjunto
  - reparto de las decisiones predichas (el colapso por categoría)
  - identificadores inventados: la regla citada no existe ni como código de
    asignatura de la malla ni como artículo del reglamento (mecanismo E3)
  - contradicciones internas: responde "sí" citando una regla que bloquea
    la inscripción (mecanismo E4)

Uso:
    python analisis.py ../resultados/*.raw.jsonl
    python analisis.py ../resultados/Mistral-7B-Instruct-v0.3__zero_shot__prosa.raw.jsonl
"""

import glob
import json
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RUTA_MALLA = BASE / "datos" / "malla.json"

# Artículos del reglamento que el prompt declara como valores válidos de "regla".
ARTICULOS = {
    "R-TOPE-MAX",
    "R-CREDITOS-MINIMOS",
    "R-EXCEPCION-PRERREQ",
    "R-DEPENDE-APROBACION",
    "R-SIN-IMPEDIMENTO",
    "R-YA-CURSADA",
}

# Reglas que significan "no puede inscribir". Citar una de éstas con decisión
# "sí" es una contradicción dentro de la propia respuesta.
BLOQUEAN = {"R-TOPE-MAX", "R-CREDITOS-MINIMOS", "R-YA-CURSADA"}


def cargar_validos():
    """Códigos de asignatura + artículos. Todo lo demás es invención."""
    with open(RUTA_MALLA, encoding="utf-8") as f:
        malla = json.load(f)
    codigos = {a["codigo"] for a in malla["asignaturas"]}
    especiales = {f"R-ESPECIAL-{r}" for r in malla["requisitos_especiales_def"]}
    return codigos, ARTICULOS | especiales


def bloquea(regla, codigos):
    """¿Esta regla dice que NO puede inscribir?"""
    if regla in BLOQUEAN or regla in codigos:
        return True
    return isinstance(regla, str) and regla.startswith("R-ESPECIAL-")


def analizar(ruta, codigos, validos):
    filas = [json.loads(l) for l in open(ruta, encoding="utf-8") if l.strip()]
    if not filas:
        return None
    n = len(filas)

    def pct(campo):
        return 100.0 * sum(f[campo] for f in filas) / n

    pred = [f["prediccion"] for f in filas]
    decisiones = Counter(p["decision"] for p in pred)

    inventadas = Counter()
    for p in pred:
        r = p["regla"]
        if r is not None and r not in validos and r not in codigos:
            inventadas[r] += 1

    contradicciones = [f for f in filas
                       if f["prediccion"]["decision"] == "sí"
                       and bloquea(f["prediccion"]["regla"], codigos)]

    reglas_usadas = {p["regla"] for p in pred if p["regla"] is not None}
    parseo = Counter(p["parseo"] for p in pred)

    return {
        "archivo": Path(ruta).name,
        "modelo": filas[0]["modelo"],
        "condicion": filas[0]["condicion"],
        "pregunta": filas[0]["pregunta"],
        "n": n,
        "decision": pct("acierto_decision"),
        "regla": pct("acierto_regla"),
        "conjunto": pct("acierto_conjunto"),
        "reparto": decisiones,
        "inventadas": inventadas,
        "n_inventadas": sum(inventadas.values()),
        "contradicciones": len(contradicciones),
        "identificadores_distintos": len(reglas_usadas),
        "parseo": parseo,
        "segundos": sum(f["segundos"] for f in filas) / n,
        "tokens": sum(f["tokens_entrada"] for f in filas) // n,
    }


def main():
    patrones = sys.argv[1:] or [str(BASE / "resultados" / "*.raw.jsonl")]
    rutas = sorted({r for p in patrones for r in glob.glob(p)})
    if not rutas:
        print("no se encontraron archivos")
        return 1

    codigos, validos = cargar_validos()
    print(f"identificadores válidos: {len(codigos)} códigos + {len(validos)} artículos\n")

    filas = [analizar(r, codigos, validos) for r in rutas]
    filas = [f for f in filas if f]

    print("=" * 96)
    print(f"{'modelo · condición':<44}{'n':>4}{'dec':>8}{'regla':>8}{'ambas':>8}"
          f"{'invent':>8}{'contra':>8}")
    print("=" * 96)
    for f in filas:
        etq = f"{f['modelo'].split('/')[-1]} · {f['condicion']}/{f['pregunta']}"
        print(f"{etq:<44}{f['n']:>4}{f['decision']:>7.1f}%{f['regla']:>7.1f}%"
              f"{f['conjunto']:>7.1f}%{f['n_inventadas']:>8}{f['contradicciones']:>8}")

    print()
    print("=" * 96)
    print("REPARTO DE LAS DECISIONES PREDICHAS  (esperado: sí 18 · no 21 · condicional 21)")
    print("=" * 96)
    print(f"{'modelo · condición':<44}{'sí':>7}{'no':>7}{'condic':>8}{'vacío':>7}")
    for f in filas:
        etq = f"{f['modelo'].split('/')[-1]} · {f['condicion']}/{f['pregunta']}"
        d = f["reparto"]
        print(f"{etq:<44}{d.get('sí', 0):>7}{d.get('no', 0):>7}"
              f"{d.get('condicional', 0):>8}{d.get(None, 0):>7}")

    print()
    for f in filas:
        if f["inventadas"]:
            print(f"--- identificadores inventados · {f['modelo'].split('/')[-1]} "
                  f"{f['condicion']}/{f['pregunta']} ---")
            for r, c in f["inventadas"].most_common(12):
                print(f"    {c:>3}x  {r}")
            print()

    print("=" * 96)
    print("FACTIBILIDAD")
    print("=" * 96)
    for f in filas:
        etq = f"{f['modelo'].split('/')[-1]} · {f['condicion']}/{f['pregunta']}"
        ok = f["parseo"].get("ok", 0)
        print(f"{etq:<44}{f['segundos']:>6.1f}s/caso  {f['tokens']:>6} tokens  "
              f"JSON válido {ok}/{f['n']}  ·  {f['identificadores_distintos']} identificadores distintos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
