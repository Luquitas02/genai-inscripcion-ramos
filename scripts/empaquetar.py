# -*- coding: utf-8 -*-
"""
Arma `paquete_colab.zip`, lo que se sube a Google Colab para correr con GPU.

El paquete no se versiona, porque es un artefacto derivado. Este script es lo que lo hace
reproducible: cualquiera que clone el repositorio puede regenerarlo idéntico.

Los baselines del Deliverable 1 viajan bajo `baseline/` y no bajo `resultados/`, porque la
celda que monta Google Drive reemplaza `resultados/` por un enlace simbólico y borraría lo
que hubiera adentro. Sin ellos, la tabla comparativa del notebook queda sin fila de baseline.

Uso:
    python scripts/empaquetar.py
"""

import hashlib
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SALIDA = BASE / "paquete_colab.zip"

CODIGO = [
    "scripts/verificador.py", "scripts/prompt.py", "scripts/runner.py",
    "scripts/generador.py", "scripts/ficha.py", "scripts/pipeline.py",
    "scripts/runner_d2.py", "scripts/ablacion_p3.py",
    "datos/malla.json", "datos/casos.jsonl",
]

BASELINES = [
    "resultados/Phi-3.5-mini-instruct__few_shot__prosa.raw.jsonl",
    "resultados/Phi-3.5-mini-instruct__zero_shot__prosa.raw.jsonl",
    "resultados/Phi-3.5-mini-instruct__zero_shot__limpia.raw.jsonl",
]


def main():
    faltan = [f for f in CODIGO + BASELINES if not (BASE / f).exists()]
    if faltan:
        for f in faltan:
            print(f"[FALTA] {f}")
        return 1

    with zipfile.ZipFile(SALIDA, "w", zipfile.ZIP_DEFLATED) as z:
        for f in CODIGO:
            z.write(BASE / f, f)
        for f in BASELINES:
            z.write(BASE / f, "baseline/" + Path(f).name)

    # el paquete tiene que ser idéntico a lo que hay en el repositorio, byte a byte:
    # una corrida hecha con código distinto del versionado no es reproducible
    z = zipfile.ZipFile(SALIDA)
    distintos = [f for f in CODIGO
                 if hashlib.md5(z.read(f)).hexdigest()
                 != hashlib.md5((BASE / f).read_bytes()).hexdigest()]
    for f in distintos:
        print(f"[DISTINTO] {f}")

    print(f"{len(CODIGO) + len(BASELINES)} archivos · {SALIDA.stat().st_size:,} bytes")
    print("idéntico al repositorio" if not distintos else "*** hay archivos distintos ***")
    return 0 if not distintos else 1


if __name__ == "__main__":
    raise SystemExit(main())
