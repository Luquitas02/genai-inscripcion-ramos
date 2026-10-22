# -*- coding: utf-8 -*-
"""
Genera `corrida_v5_colab.ipynb`, el notebook que mide la versión 5 del sistema de agentes.

Igual que el de la v4 (`gen_notebook_d3.py`), clona el repositorio en el commit indicado y
guarda cada corrida en Drive apenas termina. Dos diferencias:

  - Las salidas van a `resultados/v5/` y `trazas/v5/`, y a la carpeta `genai_d3_v5` de Drive.
  - Al empezar, copia desde Drive lo que ya se corrió. Una sesión caída en la v4 obligaba a
    rehacer el conjunto; ahora el runner retoma donde iba (solo si el commit y los prompts son
    los mismos: si no, se niega).

Etapas:

  desarrollo   la v5 completa sobre los 223 casos de desarrollo y la regla de aceptación
               (`aceptacion_v5.py`). Unos 30 minutos.
  final        se agrega con PROTOCOLO_V5.md, antes de correrla.

Uso:
    python scripts/gen_notebook_v5.py
"""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SALIDA = BASE / "corrida_v5_colab.ipynb"
REPO = "https://github.com/Luquitas02/genai-inscripcion-ramos"


def md(texto):
    return {"cell_type": "markdown", "metadata": {}, "source": texto.splitlines(True)}


def code(texto):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": texto.splitlines(True)}


CELDAS = [
    md("""# Sistema de agentes, versión 5 — Phi-3.5-mini

Ejecuta las celdas **en orden, de arriba abajo**. El diseño y la regla para aceptar la v5 están
en `PLAN_D3.md`, sección "Versión 5".

| sección | qué hace | cuándo |
|---|---|---|
| 1 a 4 | GPU, clon, autopruebas, Drive, carga del modelo | siempre |
| 5 | la v5 sobre los 223 casos de desarrollo y la regla de aceptación | ahora |
| 6 | bajar los resultados en un zip | al terminar |
"""),

    md("""## 1 · GPU, dependencias y repositorio
Debe decir `cuda: True` y mostrar una **Tesla T4**. Si no: *Entorno de ejecución* →
*Cambiar tipo de entorno de ejecución* → **T4 GPU**.

`COMMIT` es el commit que se mide. Cada fila de resultados lo guarda, y el runner no mezcla
filas de commits distintos en un mismo archivo.
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
pruebas = (['verificador.py'], ['ficha.py'], ['herramientas.py'], ['runner_d3.py', '--pruebas'],
           ['gen_ablaciones_v5.py', '--check'])
for args in pruebas:
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    ultima = (r.stdout.strip().splitlines() or ['(sin salida)'])[-1]
    print(f'[{"OK  " if r.returncode == 0 else "FALLA"}] {args[0]:22} {ultima[:60]}')
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit('*** NO SIGAS: falló ' + args[0] + ' ***')
print('TODO EN ORDEN')"""),

    md("""## 3 · Google Drive
**No te saltes esta celda.** Cada corrida se copia a Drive apenas termina, en la carpeta
`genai_d3_v5`, y lo que ya estaba en Drive se copia al clon para que el runner retome.
"""),
    code("""from google.colab import drive
import shutil
from pathlib import Path
drive.mount('/content/drive')
RESPALDO = Path('/content/drive/MyDrive/genai_d3_v5')
PROYECTO = Path('/content/proyecto')
for sub in ('resultados', 'trazas'):
    (RESPALDO / sub).mkdir(parents=True, exist_ok=True)
    (PROYECTO / sub / 'v5').mkdir(parents=True, exist_ok=True)
    for p in (RESPALDO / sub).glob('*.jsonl'):
        shutil.copy(p, PROYECTO / sub / 'v5' / p.name)
        print('recuperado de Drive:', sub, p.name)

def respaldar(*rutas):
    for r in rutas:
        r = Path(r)
        sub = 'resultados' if 'resultados' in r.parts else 'trazas'
        shutil.copy(r, RESPALDO / sub / r.name)
    print('copiado a Drive:', ', '.join(Path(r).name for r in rutas))

print('Drive listo:', RESPALDO)"""),

    md("""## 4 · Carga del modelo
Phi-3.5-mini en 4 bits, 256 tokens de salida, generación greedy cortada al cerrar el primer
JSON: lo mismo que la v4. Tarda entre tres y cinco minutos.
"""),
    code("""sys.path.insert(0, '/content/proyecto/scripts')
import runner_d3, ver_traza
modelo = runner_d3.cargar_modelo('microsoft/Phi-3.5-mini-instruct')
print('modelo cargado · revisión', getattr(modelo.modelo.config, '_commit_hash', '?'))"""),

    md("""## 5 · Desarrollo: la v5 sobre los 223 casos y la regla de aceptación
Los cinco conjuntos de desarrollo: el desarrollo de la v4 (52 + 21) y los 150 de prueba de la
v4, que para la v5 son desarrollo. Unos 30 minutos. Si la sesión se cae, vuelve a correr las
secciones 1 a 4 y esta: retoma donde iba.

Al final, `aceptacion_v5.py` aplica la regla escrita en `PLAN_D3.md` antes de correr y lista
los casos que cambian respecto de la v4. Copia toda la salida de esta celda y pégala en el
chat.
"""),
    code("""DESARROLLO = ['casos_desarrollo.jsonl', 'casos_desarrollo_redactados.jsonl',
              'casos.jsonl', 'casos_nuevos.jsonl', 'casos_redactados.jsonl']
datos = PROYECTO / 'datos'
for conjunto in DESARROLLO:
    salida, traza = runner_d3.ejecutar(modelo, 'completo', str(datos / conjunto))
    respaldar(salida, traza)

r = subprocess.run([sys.executable, 'aceptacion_v5.py'], capture_output=True, text=True)
print(r.stdout, r.stderr[-2000:])"""),

    md("""## 6 · Bajar los resultados
Un zip con `resultados/` y `trazas/` de la v5. También están en Drive, en `genai_d3_v5`.
"""),
    code("""from google.colab import files
shutil.make_archive('/content/resultados_v5', 'zip', str(RESPALDO))
files.download('/content/resultados_v5.zip')"""),
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
