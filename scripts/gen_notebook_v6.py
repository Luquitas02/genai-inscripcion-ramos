# -*- coding: utf-8 -*-
"""
Genera los notebooks de Colab de la v6 (PLAN_V6.md).

Cada configuración escribe sus resultados directo en Drive. `runner_d3.correr` hace `flush`
después de cada caso, así que un corte de la sesión pierde a lo más el caso que estaba
corriendo, y al volver a correr las celdas retoma desde ahí. Antes de medir, la celda de
control corre 10 casos de la v4 que tienen que salir iguales a la traza guardada; si no, la
máquina no es comparable con la que midió la v4 y el notebook se detiene.

Uso:
    python scripts/gen_notebook_v6.py --fase desarrollo [--commit <hash>]
"""

import argparse
import json
import subprocess
from pathlib import Path

from gen_notebook_replica_v4 import REPO, code, md

BASE = Path(__file__).resolve().parent.parent

FASES = {
    "desarrollo": {
        "titulo": "Corrida de desarrollo de la v6 sobre los 403 casos ya usados",
        "configs": ["v6"],
        "conjuntos": ["datos/casos.jsonl", "datos/casos_nuevos.jsonl",
                      "datos/casos_redactados.jsonl", "datos/casos_desarrollo.jsonl",
                      "datos/casos_desarrollo_redactados.jsonl",
                      "datos/prueba_v5/plantilla_a.jsonl", "datos/prueba_v5/plantilla_b.jsonl",
                      "datos/prueba_v5/redactados.jsonl"],
        "duracion": "unos 50 minutos",
    },
}

TORCH = "2.11.0"    # la versión con que se midió la v4 (requirements-colab.txt)


def generar(fase, commit, configs, conjuntos):
    """El JSON del notebook de una fase."""
    f = FASES[fase]
    celdas = [
        md(f"""# {f['titulo']} — Phi-3.5-mini

Ejecuta las celdas **en orden, de arriba abajo**. Dura {f['duracion']} de GPU.

| sección | qué hace |
|---|---|
| 1 | GPU, dependencias y clon en el commit fijado |
| 2 | autopruebas sin GPU |
| 3 | Google Drive: los resultados se escriben ahí caso por caso |
| 4 | carga del modelo |
| 5 | control: 10 casos de la v4 iguales a la traza guardada, o no se sigue |
| 6 | las corridas |
| 7 | bajar los resultados en un zip |

**Si la sesión se cae:** vuelve a correr las secciones 1 a 5 y después la 6. Retoma desde el
último caso guardado en Drive.
"""),
        md("""## 1 · GPU, dependencias y repositorio
Debe decir `cuda: True` y mostrar una **Tesla T4**. Si no: *Entorno de ejecución* →
*Cambiar tipo de entorno de ejecución* → **T4 GPU**. `COMMIT` no se cambia.
"""),
        code(f"""COMMIT = '{commit}'

%cd /content
!nvidia-smi -L
from importlib.metadata import version
if not version('torch').startswith('{TORCH}'):
    print('instalando torch {TORCH} (Colab trae', version('torch'), ')')
    !pip -q install torch=={TORCH} --index-url https://download.pytorch.org/whl/cu128
    # torchvision y torchaudio de Colab quedan compilados para el otro torch; el modelo es
    # solo de texto, así que se quitan para que transformers no los cargue.
    !pip -q uninstall -y torchvision torchaudio
!pip -q install transformers==5.17.0 accelerate==1.14.0 bitsandbytes==0.50.2
!rm -rf /content/proyecto && git clone -q {REPO} /content/proyecto
import subprocess
subprocess.run(['git', '-C', '/content/proyecto', 'checkout', '-q', COMMIT], check=True)
!git -C /content/proyecto log -1 --format='commit %h  %ad  %s'
import torch; print('cuda:', torch.cuda.is_available())
for paquete in ('torch', 'transformers', 'accelerate', 'bitsandbytes'):
    print(f'{{paquete}}=={{version(paquete)}}')"""),
        md("""## 2 · Autopruebas
No usan la GPU. Tienen que terminar en `TODO EN ORDEN`; si alguna falla, no sigas.
"""),
        code("""import subprocess, sys, os
os.chdir('/content/proyecto/scripts')
pruebas = (['herramientas.py'], ['runner_d3.py', '--pruebas'], ['demo_d3.py', '--pruebas'],
           ['control_v6.py', '--modelo-falso'])
for args in pruebas:
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    ultima = (r.stdout.strip().splitlines() or ['(sin salida)'])[-1]
    print(f'[{"OK  " if r.returncode == 0 else "FALLA"}] {args[0]:18} {ultima[:60]}')
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit('*** NO SIGAS: falló ' + args[0] + ' ***')
print('TODO EN ORDEN')"""),
        md(f"""## 3 · Google Drive
**No te saltes esta celda.** Los resultados se escriben en
`genai_v6/{fase}/<commit>` de tu Drive, caso por caso.
"""),
        code(f"""from google.colab import drive
from pathlib import Path
drive.mount('/content/drive')
SALIDA = Path('/content/drive/MyDrive/genai_v6/{fase}') / COMMIT
SALIDA.mkdir(parents=True, exist_ok=True)
print('en Drive ya hay', len(list(SALIDA.glob('*.raw.jsonl'))), 'archivos de resultados')
print('Drive listo:', SALIDA)"""),
        md("""## 4 · Carga del modelo
Phi-3.5-mini en 4 bits, como en la v4. Tarda entre tres y cinco minutos. Se detiene si Hugging
Face entrega otra revisión del modelo que la `2fe1924`.
"""),
        code("""sys.path.insert(0, '/content/proyecto/scripts')
import runner_d3
modelo = runner_d3.cargar_modelo('microsoft/Phi-3.5-mini-instruct')
REVISION = str(getattr(modelo.modelo.config, '_commit_hash', '?'))
print('modelo cargado · revisión', REVISION)
assert REVISION.startswith('2fe1924'), '*** otra revisión del modelo: NO SIGAS, avisa ***'"""),
        md("""## 5 · Control
Corre la v4 en 10 casos y compara cada salida del modelo con la traza guardada. Tiene que decir
`10 de 10 casos iguales a la v4`. Si dice otra cosa, **no sigas** y avisa: esta máquina no da
lo mismo que la que midió la v4.
"""),
        code("""import control_v6
assert control_v6.controlar(modelo) == 10, '*** el control no da 10 de 10: NO SIGAS, avisa ***'"""),
        md("""## 6 · Corridas
Cada configuración sobre cada conjunto. Si aparece `PromptsCambiados`, en Drive hay resultados
de otro commit en la misma carpeta: avisa antes de borrar nada.
"""),
        code(f"""PROYECTO = Path('/content/proyecto')
CONFIGS = {configs!r}
CONJUNTOS = {conjuntos!r}
assert all((PROYECTO / c).exists() for c in CONJUNTOS), 'faltan conjuntos'
for config in CONFIGS:
    for conjunto in CONJUNTOS:
        runner_d3.ejecutar(modelo, config, str(PROYECTO / conjunto), dir_salida=str(SALIDA))
print('corridas completas')"""),
        md("""## 7 · Bajar los resultados
Un zip con todo lo que hay en la carpeta de Drive. Súbelo o avisa, y Claude hace el análisis.
"""),
        code(f"""import shutil
from google.colab import files
shutil.make_archive('/content/v6_{fase}', 'zip', str(SALIDA))
files.download('/content/v6_{fase}.zip')"""),
    ]
    return {"cells": celdas,
            "metadata": {"accelerator": "GPU", "colab": {"gpuType": "T4"},
                         "kernelspec": {"display_name": "Python 3", "name": "python3"},
                         "language_info": {"name": "python"}},
            "nbformat": 4, "nbformat_minor": 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fase", choices=list(FASES), required=True)
    ap.add_argument("--commit", default=None, help="por defecto, el HEAD actual")
    args = ap.parse_args()
    commit = args.commit or subprocess.check_output(
        ["git", "-C", str(BASE), "rev-parse", "--short=7", "HEAD"], text=True).strip()
    f = FASES[args.fase]
    nb = generar(args.fase, commit, f["configs"], f["conjuntos"])
    salida = BASE / f"{args.fase}_v6_colab.ipynb"
    salida.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"escrito {salida.name} · commit {commit}")


if __name__ == "__main__":
    main()
