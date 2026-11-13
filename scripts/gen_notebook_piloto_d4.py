# -*- coding: utf-8 -*-
"""
Genera `piloto_d4_colab.ipynb`: el piloto del D4, antes de decidir el plan.

Responde tres preguntas sobre los 60 casos de DESARROLLO de `datos/piloto_d4/piloto.jsonl`:
  1. ¿Falla el sistema del D3 en prosa más variada? (configuración completa)
  2. ¿Lo arregla el prompt con 40 ejemplos más? (control_muchos_ejemplos)
  3. ¿Corre QLoRA de Phi-3.5 en una T4, y el Intérprete ajustado entra al sistema?
     (500 pares de plantilla, 1 época; es una prueba técnica, no el ajuste del D4)

    python scripts/gen_notebook_piloto_d4.py
"""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SALIDA = BASE / "piloto_d4_colab.ipynb"
REPO = "https://github.com/Luquitas02/genai-inscripcion-ramos"
COMMIT = ""   # se llena en un commit aparte, después de subir el piloto


def md(t):
    return {"cell_type": "markdown", "metadata": {}, "source": t.splitlines(True)}


def code(t):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": t.splitlines(True)}


CELDAS = [
    md("""# Piloto del D4 — Phi-3.5-mini

Ejecuta las celdas **en orden, de arriba abajo**, una sola vez. Toma alrededor de una hora de T4.

| sección | qué hace | tiempo aprox. |
|---|---|---|
| 1 a 3 | GPU, dependencias, clon del repositorio, autopruebas, Drive | 5 min |
| 4 | el sistema del D3 y el control (40 ejemplos más) sobre los 60 casos del piloto | 20 min |
| 5 | arma 500 pares de entrenamiento y entrena el adaptador del Intérprete | 20-30 min |
| 6 | el sistema con el Intérprete ajustado sobre los mismos 60 casos | 10 min |
| 7 | bajar todo en un zip | 1 min |

Si la sesión se cae, vuelve a correr desde la sección 1: lo que ya terminó está en Drive y se
retoma.
"""),
    md("""## 1 · GPU, dependencias y repositorio
Debe decir `cuda: True` y una **Tesla T4**. Si no: *Entorno de ejecución* → *Cambiar tipo de
entorno de ejecución* → **T4 GPU**. Al final imprime las versiones: no te preocupes si cambian,
quedan registradas.
"""),
    code(f"""COMMIT = '{COMMIT}'

%cd /content
!nvidia-smi -L
!pip -q install transformers==5.17.0 accelerate==1.14.0 bitsandbytes==0.50.2 peft trl datasets
!rm -rf /content/proyecto && git clone -q {REPO} /content/proyecto
import subprocess
assert COMMIT, 'falta el commit del piloto'
subprocess.run(['git', '-C', '/content/proyecto', 'checkout', '-q', COMMIT], check=True)
!git -C /content/proyecto log -1 --format='commit %h  %ad  %s'
import torch; print('cuda:', torch.cuda.is_available())
from importlib.metadata import version
for paquete in ('torch', 'transformers', 'accelerate', 'bitsandbytes', 'peft', 'trl', 'datasets'):
    print(f'{{paquete}}=={{version(paquete)}}')"""),
    md("""## 2 · Autopruebas
No usan la GPU. Tienen que terminar en `TODO EN ORDEN`; si alguna falla, no sigas y avísame.
"""),
    code("""import subprocess, sys, os
os.chdir('/content/proyecto/scripts')
pruebas = (['verificador.py'], ['herramientas.py'], ['runner_d3.py', '--pruebas'],
           ['modelo_d4.py'], ['datos_d4.py', '--pruebas'])
for args in pruebas:
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    ultima = (r.stdout.strip().splitlines() or ['(sin salida)'])[-1]
    print(f'[{"OK  " if r.returncode == 0 else "FALLA"}] {args[0]:22} {ultima[:70]}')
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit('*** NO SIGAS: falló ' + args[0] + ' ***')
print('TODO EN ORDEN')"""),
    md("""## 3 · Google Drive
**No te saltes esta celda.** Todo se copia a Drive en `genai_piloto_d4/<commit>` apenas termina.
"""),
    code("""from google.colab import drive
import shutil
from pathlib import Path
drive.mount('/content/drive')
HASH = subprocess.check_output(['git', '-C', '/content/proyecto', 'rev-parse', '--short=10',
                                'HEAD'], text=True).strip()
RESPALDO = Path('/content/drive/MyDrive/genai_piloto_d4') / HASH
PROYECTO = Path('/content/proyecto')
SAL = RESPALDO / 'corridas'
SAL.mkdir(parents=True, exist_ok=True)
PILOTO = str(PROYECTO / 'datos' / 'piloto_d4' / 'piloto.jsonl')
ADAPTADOR = RESPALDO / 'adaptador_piloto'
print('Drive listo:', RESPALDO)"""),
    md("""## 4 · El sistema del D3 y el control sobre los 60 casos
Carga Phi en 4 bits (3 a 5 minutos) y corre dos configuraciones. Cada línea es un caso;
`OK` es acierto conjunto. Los resultados se escriben directo en Drive.
"""),
    code("""sys.path.insert(0, '/content/proyecto/scripts')
import runner_d3
modelo = runner_d3.cargar_modelo('microsoft/Phi-3.5-mini-instruct')
print('modelo cargado · revisión', getattr(modelo.modelo.config, '_commit_hash', '?'))
for config in ('completo', 'control_muchos_ejemplos'):
    runner_d3.ejecutar(modelo, config, PILOTO, dir_salida=str(SAL))"""),
    md("""## 5 · Datos y entrenamiento del adaptador
Primero libera la GPU, después arma 450 pares de entrenamiento y 50 de validación, y entrena
una época. Imprime la pérdida cada paso. Al final muestra un resumen con el tiempo y la memoria.
**Si aparece un error, copia las últimas líneas y avísame: es justo lo que el piloto busca.**
"""),
    code("""import gc
if 'modelo' in globals():
    del modelo
gc.collect(); torch.cuda.empty_cache()
DATOS = PROYECTO / 'datos' / 'entrenamiento_piloto'
r = subprocess.run([sys.executable, 'datos_d4.py', '--n', '500', '--salida', str(DATOS)],
                   capture_output=True, text=True)
print(r.stdout, r.stderr[-1500:])
shutil.copytree(DATOS, RESPALDO / 'entrenamiento_piloto', dirs_exist_ok=True)
if (ADAPTADOR / 'adapter_config.json').exists():
    print('el adaptador ya está en Drive: no se vuelve a entrenar')
else:
    !cd /content/proyecto/scripts && python entrenar_d4.py --datos {DATOS} --salida /content/adaptador_piloto 2>&1 | grep -v -i warn
    shutil.copytree('/content/adaptador_piloto', ADAPTADOR, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('checkpoints'))
from IPython.display import Image, display
display(Image(str(ADAPTADOR / 'curvas.png')))"""),
    md("""## 6 · El sistema con el Intérprete ajustado
Vuelve a cargar Phi, le pone el adaptador encima y lo usa **solo** en el Intérprete. El
Resolvedor y el Verificador siguen con la base.
"""),
    code("""from modelo_d4 import ConAdaptador
base = runner_d3.cargar_modelo('microsoft/Phi-3.5-mini-instruct')
ajustado = ConAdaptador(base, str(ADAPTADOR), etiqueta='A-lora-piloto')
runner_d3.ejecutar(ajustado, 'completo', PILOTO, dir_salida=str(SAL))
print('llamadas con adaptador:', ajustado.llamadas_con_adaptador)"""),
    md("""## 7 · Bajar los resultados
Un zip con las corridas, la configuración del entrenamiento, las curvas y el adaptador. Déjalo en
la carpeta `resultados/` del proyecto y avísame.
"""),
    code("""from google.colab import files
shutil.make_archive('/content/piloto_d4', 'zip', str(RESPALDO))
files.download('/content/piloto_d4.zip')"""),
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
