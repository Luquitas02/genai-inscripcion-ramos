# -*- coding: utf-8 -*-
"""
Genera `corrida_d3_colab.ipynb`, el notebook que mide el sistema de agentes en Colab.

Clona el repositorio en vez de subir un zip. En el D2 el zip trajo dos trampas: Colab renombra
el archivo resubido y se descomprimía el viejo, y había que regenerar el paquete a mano después
de cada cambio. Con el clon, lo que corre es lo que está en GitHub en el commit indicado.

Dos etapas, en este orden:

  desarrollo   el sistema completo sobre `casos_desarrollo.jsonl`. Se repite cada vez que se
               ajusta un prompt. Es el único conjunto que se mira para ajustar.
  final        todas las configuraciones sobre los tres conjuntos de prueba, más el baseline y
               el D2 sobre los redactados. Solo después de subir PROTOCOLO_D3.md, y con
               COMMIT apuntando a ese commit.

Uso:
    python scripts/gen_notebook_d3.py
"""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SALIDA = BASE / "corrida_d3_colab.ipynb"
REPO = "https://github.com/Luquitas02/genai-inscripcion-ramos"


def md(texto):
    return {"cell_type": "markdown", "metadata": {}, "source": texto.splitlines(True)}


def code(texto):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": texto.splitlines(True)}


CELDAS = [
    md("""# Sistema de agentes del Deliverable 3 — Phi-3.5-mini

Ejecuta las celdas **en orden, de arriba abajo**.

| sección | qué hace | cuándo |
|---|---|---|
| 1 a 4 | GPU, clon, autopruebas, Drive, carga del modelo | siempre |
| 5 | sistema completo sobre el conjunto de desarrollo | cada vez que se ajusta un prompt |
| 6 | todas las configuraciones sobre los conjuntos de prueba | **una vez**, tras subir el protocolo |
| 7 | bajar los resultados en un zip | al terminar |
"""),

    md("""## 1 · GPU, dependencias y repositorio
Debe decir `cuda: True` y mostrar una **Tesla T4**. Si no: *Entorno de ejecución* →
*Cambiar tipo de entorno de ejecución* → **T4 GPU**.

`COMMIT` vacío clona la última versión de `main`. Para la etapa final, pon el hash del commit
que sube `PROTOCOLO_D3.md`.
"""),
    code(f"""COMMIT = ''

%cd /content
!nvidia-smi -L
!pip -q install transformers==5.17.0 accelerate==1.14.0 bitsandbytes==0.50.2
!rm -rf /content/proyecto && git clone -q {REPO} /content/proyecto
import subprocess
if COMMIT:
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
    print(f'[{"OK  " if r.returncode == 0 else "FALLA"}] {args[0]:16} {ultima[:60]}')
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit('*** NO SIGAS: falló ' + args[0] + ' ***')
print('TODO EN ORDEN')"""),

    md("""## 3 · Google Drive
**No te saltes esta celda.** Cada corrida se copia a Drive apenas termina, en la carpeta
`genai_d3`. Sin Drive, una sesión caída pierde todo lo medido.
"""),
    code("""from google.colab import drive
import shutil
from pathlib import Path
drive.mount('/content/drive')
RESPALDO = Path('/content/drive/MyDrive/genai_d3')
(RESPALDO / 'resultados').mkdir(parents=True, exist_ok=True)
(RESPALDO / 'trazas').mkdir(parents=True, exist_ok=True)

def respaldar(*rutas):
    for r in rutas:
        r = Path(r)
        shutil.copy(r, RESPALDO / r.parent.name / r.name)
    print('copiado a Drive:', ', '.join(Path(r).name for r in rutas))

print('Drive listo:', RESPALDO)"""),

    md("""## 4 · Carga del modelo
Phi-3.5-mini en 4 bits, 256 tokens de salida, generación greedy: lo mismo que el D2. Tarda
entre tres y cinco minutos. Imprime la revisión descargada para registrarla.
"""),
    code("""sys.path.insert(0, '/content/proyecto/scripts')
from runner import ModeloHF
import runner_d3, ver_traza
modelo = ModeloHF('microsoft/Phi-3.5-mini-instruct', max_new_tokens=256)
print('modelo cargado · revisión', getattr(modelo.modelo.config, '_commit_hash', '?'))"""),

    md("""## 5 · Desarrollo
El sistema completo sobre los 52 casos de desarrollo. Después muestra la traza de los primeros
casos donde falla, que es lo que se mira para ajustar los prompts.

Si cambiaste un prompt, el runner se niega a retomar el archivo anterior y pide borrarlo: es a
propósito. Corre la celda de borrado y vuelve a correr esta.
"""),
    code("""DESARROLLO = '/content/proyecto/datos/casos_desarrollo.jsonl'
salida, traza = runner_d3.ejecutar(modelo, 'completo', DESARROLLO)
respaldar(salida, traza)

import json
filas = [json.loads(l) for l in open(salida, encoding='utf-8')]
fallas = [x for x in filas if not x['acierto_conjunto']]
print(f'\\n{len(fallas)} fallas. Las primeras cinco:\\n')
for x in fallas[:5]:
    print(f"caso {x['id']} · esperado {x['ramo_objetivo']['nombre']} · {x['esperado']}")
    ver_traza.mostrar(traza, int(x['id']), crudo=True)
    print()"""),
    code("""# Borra la corrida de desarrollo, para volver a medir tras cambiar un prompt.
for p in Path('/content/proyecto').glob('*/agentes__*__casos_desarrollo*'):
    p.unlink(); print('borrado', p.name)"""),

    md("""## 6 · Etapa final
**Solo después de subir `PROTOCOLO_D3.md`** y de poner su commit en `COMMIT` (sección 1). Corre
las seis configuraciones sobre los tres conjuntos de prueba, y el baseline y el D2 sobre los
redactados fuera de las plantillas (sobre originales y nuevos ya están medidos). Unas dos horas en la T4. Si la
sesión se cae, vuelve a correr las secciones 1 a 4 y esta: el runner retoma donde iba.
"""),
    code("""CONJUNTOS = ['casos.jsonl', 'casos_nuevos.jsonl', 'casos_redactados.jsonl']
CONFIGS = ['completo', 'sin_descomposicion', 'sin_herramienta', 'sin_verificador',
           'sin_ejemplos', 'top1']
datos = Path('/content/proyecto/datos')
assert (datos / 'casos_redactados.jsonl').exists(), 'falta casos_redactados.jsonl'
for conjunto in CONJUNTOS:
    for config in CONFIGS:
        salida, traza = runner_d3.ejecutar(modelo, config, str(datos / conjunto))
        respaldar(salida, traza)"""),
    code("""# Baseline few-shot y sistema del D2 sobre los redactados. Cargan su propio modelo.
redactados = str(datos / 'casos_redactados.jsonl')
for args in (['runner.py', '--modelo', 'microsoft/Phi-3.5-mini-instruct',
              '--condicion', 'few_shot', '--casos', redactados],
             ['runner_d2.py', '--variante', 'codigo', '--modo', 'encadenado',
              '--casos', redactados]):
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    print('\\n'.join(r.stdout.strip().splitlines()[-6:]), r.stderr[-1500:])
for p in Path('/content/proyecto/resultados').glob('*casos_redactados.raw.jsonl'):
    if not p.name.startswith('agentes__'):
        respaldar(p)"""),

    md("""## 7 · Bajar los resultados
Un zip con `resultados/` y `trazas/`. También están en Drive, en `genai_d3`.
"""),
    code("""from google.colab import files
shutil.make_archive('/content/resultados_d3', 'zip', str(RESPALDO))
files.download('/content/resultados_d3.zip')"""),
]


def main():
    nb = {"cells": CELDAS, "metadata": {"accelerator": "GPU", "colab": {"gpuType": "T4"},
                                        "kernelspec": {"name": "python3",
                                                       "display_name": "Python 3"}},
          "nbformat": 4, "nbformat_minor": 5}
    SALIDA.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(CELDAS)} celdas -> {SALIDA.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
