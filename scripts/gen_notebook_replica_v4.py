# -*- coding: utf-8 -*-
"""
Genera `replica_v4_colab.ipynb`, el notebook de la réplica de la v4 sobre los 180 casos
sellados (PROTOCOLO_REPLICA_V4.md).

Es la sección 6 del notebook de la v5 con el sistema de la v4: la v4 completa, el baseline
few-shot y el D2 sobre `plantilla_a`, `plantilla_b` y `redactados`. Sin ablaciones. La regla
fija se corre en local.

Uso:
    python scripts/gen_notebook_replica_v4.py
"""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SALIDA = BASE / "replica_v4_colab.ipynb"
REPO = "https://github.com/Luquitas02/genai-inscripcion-ramos"
# El commit que sube PROTOCOLO_REPLICA_V4.md. Se escribe acá en un commit aparte, después.
COMMIT = "5b5c5d5"


def md(texto):
    return {"cell_type": "markdown", "metadata": {}, "source": texto.splitlines(True)}


def code(texto):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": texto.splitlines(True)}


CELDAS = [
    md("""# Réplica de la v4 sobre los 180 casos sellados — Phi-3.5-mini

Ejecuta las celdas **en orden, de arriba abajo**, una sola vez. Lo que se corre y cómo se
analiza está en `PROTOCOLO_REPLICA_V4.md`, subido antes de esta corrida.

| sección | qué hace |
|---|---|
| 1 a 4 | GPU, clon en el commit del protocolo, autopruebas, Drive, carga del modelo |
| 5 | la v4 completa, el baseline y el D2 sobre los 180 casos (entre 1 y 2 horas) |
| 6 | bajar los resultados en un zip |
"""),

    md("""## 1 · GPU, dependencias y repositorio
Debe decir `cuda: True` y mostrar una **Tesla T4**. Si no: *Entorno de ejecución* →
*Cambiar tipo de entorno de ejecución* → **T4 GPU**.

`COMMIT` es el commit que sube el protocolo. No lo cambies.
"""),
    code(f"""COMMIT = '{COMMIT}'

%cd /content
!nvidia-smi -L
!pip -q install transformers==5.17.0 accelerate==1.14.0 bitsandbytes==0.50.2
!rm -rf /content/proyecto && git clone -q {REPO} /content/proyecto
import subprocess
assert COMMIT, 'falta el commit del protocolo'
subprocess.run(['git', '-C', '/content/proyecto', 'checkout', '-q', COMMIT], check=True)
!git -C /content/proyecto log -1 --format='commit %h  %ad  %s'
import torch; print('cuda:', torch.cuda.is_available())
from importlib.metadata import version
for paquete in ('torch', 'transformers', 'accelerate', 'bitsandbytes'):
    print(f'{{paquete}}=={{version(paquete)}}')"""),

    md("""## 2 · Autopruebas
No usan la GPU. Tienen que terminar en `TODO EN ORDEN`; si alguna falla, no sigas.
"""),
    code("""import subprocess, sys, os
os.chdir('/content/proyecto/scripts')
pruebas = (['verificador.py'], ['ficha.py'], ['pipeline.py'], ['runner_d2.py', '--pruebas'],
           ['herramientas.py'], ['runner_d3.py', '--pruebas'])
for args in pruebas:
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    ultima = (r.stdout.strip().splitlines() or ['(sin salida)'])[-1]
    print(f'[{"OK  " if r.returncode == 0 else "FALLA"}] {args[0]:22} {ultima[:60]}')
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit('*** NO SIGAS: falló ' + args[0] + ' ***')
print('TODO EN ORDEN')"""),

    md("""## 3 · Google Drive
**No te saltes esta celda.** Cada conjunto se copia a Drive apenas termina, en
`genai_replica_v4/<commit>`, y lo que ya estaba ahí se copia al clon para que el runner retome.
Si la sesión se cae a mitad de un conjunto, ese conjunto se repite.
"""),
    code("""from google.colab import drive
import shutil
from pathlib import Path
drive.mount('/content/drive')
HASH = subprocess.check_output(['git', '-C', '/content/proyecto', 'rev-parse', '--short=10',
                                'HEAD'], text=True).strip()
RESPALDO = Path('/content/drive/MyDrive/genai_replica_v4') / HASH
PROYECTO = Path('/content/proyecto')
for sub in ('resultados', 'trazas'):
    (RESPALDO / sub).mkdir(parents=True, exist_ok=True)
    for p in (RESPALDO / sub).glob('*.jsonl'):
        shutil.copy(p, PROYECTO / sub / p.name)
        print('recuperado de Drive:', sub, p.name)

def respaldar(*rutas):
    for r in rutas:
        r = Path(r)
        shutil.copy(r, RESPALDO / ('trazas' if 'trazas' in r.parts else 'resultados') / r.name)
    print('copiado a Drive:', ', '.join(Path(r).name for r in rutas))

print('Drive listo:', RESPALDO)"""),

    md("""## 4 · Carga del modelo
Phi-3.5-mini en 4 bits, 256 tokens de salida, generación greedy cortada al cerrar el primer
JSON, como en la corrida del 20 de octubre. Tarda entre tres y cinco minutos.
"""),
    code("""sys.path.insert(0, '/content/proyecto/scripts')
import runner_d3
modelo = runner_d3.cargar_modelo('microsoft/Phi-3.5-mini-instruct')
print('modelo cargado · revisión', getattr(modelo.modelo.config, '_commit_hash', '?'))"""),

    md("""## 5 · La v4, el baseline y el D2 sobre los 180 casos
Primero la v4 completa sobre los tres conjuntos (unos 20 minutos), después el baseline y el D2,
que cargan su propio modelo. Si la sesión se cae, vuelve a correr las secciones 1 a 4 y esta:
retoma donde iba.
"""),
    code("""PRUEBA = ['plantilla_a.jsonl', 'plantilla_b.jsonl', 'redactados.jsonl']
prueba = PROYECTO / 'datos' / 'prueba_v5'
assert all((prueba / c).exists() for c in PRUEBA), 'faltan los casos de prueba'
for conjunto in PRUEBA:
    salida, traza = runner_d3.ejecutar(modelo, 'completo', str(prueba / conjunto))
    respaldar(salida, traza)

for conjunto in PRUEBA:
    casos = str(prueba / conjunto)
    for args in (['runner.py', '--modelo', 'microsoft/Phi-3.5-mini-instruct',
                  '--condicion', 'few_shot', '--casos', casos],
                 ['runner_d2.py', '--variante', 'codigo', '--modo', 'encadenado',
                  '--casos', casos]):
        r = subprocess.run([sys.executable] + args, capture_output=True, text=True)
        print('\\n'.join(r.stdout.strip().splitlines()[-4:]), r.stderr[-1500:])
    for p in (PROYECTO / 'resultados').glob(f'*__{Path(conjunto).stem}.raw.jsonl'):
        respaldar(p)
print('réplica completa')"""),

    md("""## 6 · Bajar los resultados
Un zip con `resultados/` y `trazas/` de la réplica. También están en Drive, en
`genai_replica_v4/<commit>`.
"""),
    code("""from google.colab import files
shutil.make_archive('/content/replica_v4', 'zip', str(RESPALDO))
files.download('/content/replica_v4.zip')"""),
]


def main():
    nb = {"cells": CELDAS, "metadata": {"accelerator": "GPU", "colab": {"gpuType": "T4"},
                                        "kernelspec": {"display_name": "Python 3", "name": "python3"},
                                        "language_info": {"name": "python"}},
          "nbformat": 4, "nbformat_minor": 0}
    SALIDA.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"escrito {SALIDA.name} · commit {COMMIT or '(vacío)'}")


if __name__ == "__main__":
    main()
