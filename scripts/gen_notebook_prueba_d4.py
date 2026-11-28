# -*- coding: utf-8 -*-
"""
Genera `prueba_d4_colab.ipynb`: la corrida sellada del D4 (PROTOCOLO_D4.md).

Corre sobre los 239 casos de `datos/prueba_d4/` (60 de plantilla y 179 redactados) las cinco
filas con modelo: el sistema del D4 (Intérprete con el adaptador cargado desde Hugging Face en la
revisión fija), el del D3, el control, el D2 y el baseline few-shot. La regla fija se corre en
local. No usa Drive de quien entrenó: el adaptador viene de Hugging Face, así que puede correrlo
cualquiera del equipo con su propia cuenta de Colab.

El D4 y el D3 usan el mismo Phi cargado una vez: `ConAdaptador` con `usar_adaptador` en True
(D4) o en False (D3 y control, la base sin el adaptador), como en el video.

Los casos se copian con otro nombre (`d4_plantilla`, `d4_redactados`) porque `resultados/` ya
tiene archivos `__redactados` de la prueba de la v5, y el runner del D1 retomaría esos.

    python scripts/gen_notebook_prueba_d4.py
"""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SALIDA = BASE / "prueba_d4_colab.ipynb"
REPO = "https://github.com/Luquitas02/genai-inscripcion-ramos"
# Se llenan después de publicar el adaptador (publicado_hf.json del notebook de entrenamiento).
COMMIT = "3b5ec6e"
REPO_HF = "Lss02/phi35-mini-interprete-inscripcion-lora"
REVISION = "99262ad193b13a1736601dcb48716e05b033bf63"
SHA_ADAPTADOR = "2a88dfd091660d2e036e70fd1fb10aa20af21c285898cf8758b26b57be55c052"


def md(t):
    return {"cell_type": "markdown", "metadata": {}, "source": t.splitlines(True)}


def code(t):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": t.splitlines(True)}


CELDAS = [
    md("""# Prueba sellada del D4 — Phi-3.5-mini

Ejecuta las celdas **en orden, de arriba abajo**, una a la vez. Lo que se corre y cómo se analiza
está en `PROTOCOLO_D4.md`, subido antes de entrenar. La prueba se corre **una sola vez**.

| sección | qué hace | tiempo aprox. |
|---|---|---|
| 1 a 3 | GPU, dependencias, clon, autopruebas y sellos, Drive | 5 min |
| 4 | carga Phi y el adaptador desde Hugging Face, y verifica que sea el publicado | 5 min |
| 5 | D4, D3 y control sobre los 239 casos | 1 h 40 min |
| 6 | D2 y baseline few-shot sobre los 239 casos | 40 min |
| 7 | bajar todo en un zip | 1 min |

**Si la sesión se cae**, vuelve a correr desde la sección 1: lo que terminó está en Drive y cada
sistema retoma donde iba.
"""),
    md("""## 1 · GPU, dependencias y repositorio
Debe decir `cuda: True` y una **Tesla T4**. Si no: *Entorno de ejecución* → *Cambiar tipo de
entorno de ejecución* → **T4 GPU**. No cambies las constantes de arriba.
"""),
    code(f"""COMMIT = '{COMMIT}'
REPO_HF = '{REPO_HF}'
REVISION = '{REVISION}'
SHA_ADAPTADOR = '{SHA_ADAPTADOR}'

%cd /content
!nvidia-smi -L
!pip -q install transformers==5.17.0 accelerate==1.14.0 bitsandbytes==0.50.2 peft==0.21.2
!rm -rf /content/proyecto && git clone -q {REPO} /content/proyecto
import subprocess
assert COMMIT and REPO_HF and REVISION and SHA_ADAPTADOR, 'faltan constantes'
subprocess.run(['git', '-C', '/content/proyecto', 'checkout', '-q', COMMIT], check=True)
!git -C /content/proyecto log -1 --format='commit %h  %ad  %s'
import torch; print('cuda:', torch.cuda.is_available())
from importlib.metadata import version
for paquete in ('torch', 'transformers', 'accelerate', 'bitsandbytes', 'peft'):
    print(f'{{paquete}}=={{version(paquete)}}')"""),
    md("""## 2 · Autopruebas y sellos
No usan la GPU. Comprueban el código, que los casos sean los sellados el 24 de noviembre y que
los prompts sean los del protocolo. Tienen que terminar en `TODO EN ORDEN`.
"""),
    code("""import subprocess, sys, os, hashlib, json
os.chdir('/content/proyecto/scripts')
pruebas = (['verificador.py'], ['ficha.py'], ['pipeline.py'], ['runner_d2.py', '--pruebas'],
           ['herramientas.py'], ['runner_d3.py', '--pruebas'], ['modelo_d4.py'])
for args in pruebas:
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    ultima = (r.stdout.strip().splitlines() or ['(sin salida)'])[-1]
    print(f'[{"OK  " if r.returncode == 0 else "FALLA"}] {args[0]:22} {ultima[:60]}')
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit('*** NO SIGAS: falló ' + args[0] + ' ***')
SELLO = {'plantilla.jsonl': 'c10637092feb5c860beec4637a7137769e586f8729b7524a6fc4bee7854de979',
         'redactados.jsonl': 'ac3fde5c3e91c2697141e76e997103c9d7d03184dd676c51e8d40730608f3448'}
for nombre, esperado in SELLO.items():
    datos = open(f'/content/proyecto/datos/prueba_d4/{nombre}', 'rb').read().replace(b'\\r\\n', b'\\n')
    assert hashlib.sha256(datos).hexdigest() == esperado, f'*** NO SIGAS: {nombre} no es el sellado ***'
    print(f'[OK  ] {nombre:22} sello del 24 de noviembre')
sys.path.insert(0, '/content/proyecto/scripts')
import orquestador as O
PROMPTS = {'completo': {'interprete': '485ade8387', 'resolvedor': 'd4dfb0dde1', 'verificador': 'd8751e096d'},
           'control_d4': {'interprete': 'a6c254ac24', 'resolvedor': 'd4dfb0dde1', 'verificador': 'd8751e096d'}}
for config, esperados in PROMPTS.items():
    reales = {k: p.ref()['hash'] for k, p in O.cargar_prompts(config).items()}
    assert reales == esperados, f'*** NO SIGAS: prompts de {config} distintos del protocolo: {reales} ***'
    print(f'[OK  ] prompts {config:14} los del protocolo')
print('TODO EN ORDEN')"""),
    md("""## 3 · Google Drive
**No te saltes esta celda.** Cada resultado se copia a Drive en `genai_prueba_d4/<commit>`, y lo
que ya estaba ahí vuelve al clon para retomar.
"""),
    code("""from google.colab import drive
import shutil
from pathlib import Path
drive.mount('/content/drive')
HASH = subprocess.check_output(['git', '-C', '/content/proyecto', 'rev-parse', '--short=10',
                                'HEAD'], text=True).strip()
RESPALDO = Path('/content/drive/MyDrive/genai_prueba_d4') / HASH
PROYECTO = Path('/content/proyecto')
SAL = RESPALDO / 'agentes'                 # D4, D3 y control: resultados y trazas
SAL.mkdir(parents=True, exist_ok=True)
(RESPALDO / 'resultados').mkdir(exist_ok=True)

# Los casos con un nombre que no existe en resultados/ (ver el encabezado del generador).
PRUEBA = Path('/content/prueba_d4'); PRUEBA.mkdir(exist_ok=True)
CONJUNTOS = []
for origen, destino in (('plantilla.jsonl', 'd4_plantilla.jsonl'), ('redactados.jsonl', 'd4_redactados.jsonl')):
    shutil.copy(PROYECTO / 'datos' / 'prueba_d4' / origen, PRUEBA / destino)
    CONJUNTOS.append(str(PRUEBA / destino))
    assert not list((PROYECTO / 'resultados').glob(f'*__{Path(destino).stem}.raw.jsonl')), 'choque de nombres'
for p in (RESPALDO / 'resultados').glob('*.jsonl'):
    shutil.copy(p, PROYECTO / 'resultados' / p.name)
    print('recuperado de Drive:', p.name)
print('Drive listo:', RESPALDO)
print([Path(c).name for c in CONJUNTOS], [sum(1 for _ in open(c, encoding='utf-8')) for c in CONJUNTOS])"""),
    md("""## 4 · Phi y el adaptador desde Hugging Face
Carga Phi en 4 bits y pone encima el adaptador **en la revisión fija** de Hugging Face. Antes,
baja el archivo del adaptador y comprueba que su sha256 sea el que salió del entrenamiento.
"""),
    code("""from huggingface_hub import hf_hub_download
bajado = hf_hub_download(REPO_HF, 'adapter_model.safetensors', revision=REVISION)
assert hashlib.sha256(open(bajado, 'rb').read()).hexdigest() == SHA_ADAPTADOR, \\
    '*** NO SIGAS: el adaptador de Hugging Face no es el entrenado ***'
print('adaptador verificado:', REPO_HF, REVISION[:10])
import runner_d3
from modelo_d4 import ConAdaptador
base = runner_d3.cargar_modelo('microsoft/Phi-3.5-mini-instruct')
print('Phi cargado · revisión', getattr(base.modelo.config, '_commit_hash', '?'))
modelo = ConAdaptador(base, REPO_HF, etiqueta=f'A-lora-{REVISION[:7]}', revision=REVISION)
print('adaptador puesto:', modelo.nombre)"""),
    md("""## 5 · D4, D3 y control sobre los 239 casos (1 h 40 min)
Cada línea es un caso; `OK` es acierto conjunto. Primero el D4 (Intérprete ajustado), después el
D3 y el control con el mismo modelo y el adaptador apagado.
"""),
    code("""def correr(config, usar_adaptador):
    modelo.usar_adaptador = usar_adaptador
    for casos in CONJUNTOS:
        runner_d3.ejecutar(modelo, config, casos, dir_salida=str(SAL))

correr('completo', True)          # D4
print('llamadas con adaptador:', modelo.llamadas_con_adaptador)
correr('completo', False)         # D3
correr('control_d4', False)       # control
print('sección 5 completa')"""),
    md("""## 6 · D2 y baseline few-shot (40 min)
Cada uno carga su propio Phi. Primero libera la GPU.
"""),
    code("""import gc
del modelo, base
gc.collect(); torch.cuda.empty_cache()
for casos in CONJUNTOS:
    for args in (['runner_d2.py', '--variante', 'codigo', '--modo', 'encadenado', '--casos', casos],
                 ['runner.py', '--modelo', 'microsoft/Phi-3.5-mini-instruct',
                  '--condicion', 'few_shot', '--casos', casos]):
        r = subprocess.run([sys.executable] + args, capture_output=True, text=True)
        print('\\n'.join(r.stdout.strip().splitlines()[-4:]), r.stderr[-1500:])
    for p in (PROYECTO / 'resultados').glob(f'*__{Path(casos).stem}.raw.jsonl'):
        shutil.copy(p, RESPALDO / 'resultados' / p.name)
        print('copiado a Drive:', p.name)
print('sección 6 completa')"""),
    md("""## 7 · Bajar los resultados
Un zip con todo lo de Drive. Déjalo en `resultados/` del proyecto y avísame.
"""),
    code("""from google.colab import files
(RESPALDO / 'corrida.json').write_text(json.dumps({'commit': HASH, 'repo_hf': REPO_HF,
    'revision': REVISION, 'sha256_adapter': SHA_ADAPTADOR,
    'gpu': torch.cuda.get_device_name(0)}, indent=1), encoding='utf-8')
shutil.make_archive('/content/prueba_d4', 'zip', str(RESPALDO))
files.download('/content/prueba_d4.zip')"""),
]


def main():
    nb = {"cells": CELDAS, "metadata": {"accelerator": "GPU", "colab": {"gpuType": "T4"},
                                        "kernelspec": {"display_name": "Python 3", "name": "python3"},
                                        "language_info": {"name": "python"}},
          "nbformat": 4, "nbformat_minor": 0}
    SALIDA.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"escrito {SALIDA.name} · commit {COMMIT or '(vacío)'} · revisión {REVISION or '(vacía)'}")


if __name__ == "__main__":
    main()
