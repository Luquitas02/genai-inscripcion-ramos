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

`COMMIT` trae el commit que sube `PROTOCOLO_D3.md`, con el que se hizo la corrida final. Así
el notebook corre el mismo código y los mismos prompts que se midieron. `COMMIT = ''` clona la
última versión de `main`, que sirve solo para desarrollo: el runner se niega a mezclar filas
de otro commit en un archivo de resultados ya guardado.
"""),
    code(f"""COMMIT = '9158550'

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
Phi-3.5-mini en 4 bits, 256 tokens de salida, generación greedy: lo mismo que el D2, con la
generación cortada al cerrar el primer JSON (no cambia la respuesta que lee el agente, solo
evita generar la explicación que se descartaba). Tarda entre tres y cinco minutos. Imprime la
revisión descargada para registrarla.
"""),
    code("""sys.path.insert(0, '/content/proyecto/scripts')
import runner_d3, ver_traza
modelo = runner_d3.cargar_modelo('microsoft/Phi-3.5-mini-instruct')
print('modelo cargado · revisión', getattr(modelo.modelo.config, '_commit_hash', '?'))"""),

    md("""## 5 · Desarrollo
El sistema completo sobre un conjunto de desarrollo: los 52 casos de plantilla
(`casos_desarrollo.jsonl`) o los 21 redactados fuera de las plantillas
(`casos_desarrollo_redactados.jsonl`). Se elige en `CONJUNTO`. Después muestra todas las
fallas y la traza de las cinco primeras, que es lo que se mira para ajustar los prompts.

Si cambiaste un prompt, el runner se niega a retomar el archivo anterior y pide borrarlo: es a
propósito. Corre la celda de borrado y vuelve a correr esta.
"""),
    code("""CONJUNTO = 'casos_desarrollo_redactados.jsonl'   # o 'casos_desarrollo.jsonl'
DESARROLLO = f'/content/proyecto/datos/{CONJUNTO}'
# La corrida anterior que está en Drive, para compararla con esta antes de pisarla.
import json
anterior = RESPALDO / 'resultados' / f'agentes__Phi-3.5-mini-instruct__completo__{Path(CONJUNTO).stem}.raw.jsonl'
previas = {}
if anterior.exists():
    previas = {x['id']: x for x in map(json.loads, open(anterior, encoding='utf-8'))}
salida, traza = runner_d3.ejecutar(modelo, 'completo', DESARROLLO)
if previas:
    ahora = {x['id']: x for x in map(json.loads, open(salida, encoding='utf-8'))}
    p = previas[next(iter(previas))]
    print(f"\\nContra la corrida anterior (commit {p.get('commit', '?')}, "
          f"{sum(x['acierto_conjunto'] for x in previas.values())}/{len(previas)}):")
    for i in sorted(ahora, key=int):
        if i in previas and ahora[i]['acierto_conjunto'] != previas[i]['acierto_conjunto']:
            print(f"  caso {i:>3}: {'ganó' if ahora[i]['acierto_conjunto'] else 'perdió'}")
respaldar(salida, traza)

import json
filas = [json.loads(l) for l in open(salida, encoding='utf-8')]
fallas = [x for x in filas if not x['acierto_conjunto']]
print(f'\\n{len(fallas)} fallas, una por línea (esperado → extraído):\\n')
for x in fallas:
    ext = x['extraccion']
    marcas = ' '.join(k for k, v in x['ramas'].items() if v)
    print(f"{x['id']:>3} | {x['pregunta'][:90]}\\n"
          f"    {x['ramo_objetivo']['codigo']} {x['esperado']['decision']:11} → "
          f"{ext['ramo']} {ext['periodo']} · {x['prediccion']['decision']} · {marcas}")
print('\\nLas primeras cinco con su traza completa:\\n')
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


SALIDA_DEMO = BASE / "demo_d3_colab.ipynb"

# El notebook del video. Las celdas 1 a 3 se corren antes de grabar: cargar Phi toma minutos
# y el video sería una barra de progreso. Se graban las celdas 4 y 5; la 6 baja la traza en vivo.
CELDAS_DEMO = [
    md("""# Demostración del Deliverable 3 · sistema de agentes con Phi-3.5-mini

Corre en vivo los tres casos que eligió la regla de `PROTOCOLO_D3.md` y muestra cada mensaje
entre agentes y herramientas. Cada salida del modelo se compara con la corrida final guardada
en `trazas/`: con generación greedy tiene que decir `= guardada`.

**Antes de grabar:** T4 GPU, y correr las celdas 1, 2 y 3. **Se graban las celdas 4 y 5.**
Después de grabar, la celda 6 baja la traza de la pregunta en vivo para subirla al repositorio.
Grabar a 1920x1080 para que el texto monoespaciado se lea.
"""),
    code(f"""# 1 · repositorio y dependencias
# El commit de la demo: los prompts, los agentes y las herramientas son los de la corrida final
# (9158550), y trae scripts/demo_d3.py con la pregunta en vivo, que guarda su traza.
# Con '' clona main.
COMMIT = '75ed9b2'

%cd /content
!pip -q install transformers==5.17.0 accelerate==1.14.0 bitsandbytes==0.50.2
!rm -rf /content/proyecto && git clone -q {REPO} /content/proyecto
import subprocess
if COMMIT:
    subprocess.run(['git', '-C', '/content/proyecto', 'checkout', '-q', COMMIT], check=True)
!git -C /content/proyecto log -1 --format='commit %h  %ad  %s'
import torch; print('cuda:', torch.cuda.is_available())"""),
    code("""# 2 · autopruebas: la demo reproduce las trazas guardadas sin usar la GPU
import sys, os
os.chdir('/content/proyecto/scripts')
sys.path.insert(0, '/content/proyecto/scripts')
r = subprocess.run([sys.executable, 'demo_d3.py', '--pruebas'], capture_output=True, text=True)
print(r.stdout.strip().splitlines()[-1])
r = subprocess.run([sys.executable, 'runner_d3.py', '--pruebas'], capture_output=True, text=True)
print(r.stdout.strip().splitlines()[-1])"""),
    code("""# 3 · carga de Phi-3.5-mini (tres a cinco minutos)
import runner_d3, demo_d3
modelo = runner_d3.cargar_modelo('microsoft/Phi-3.5-mini-instruct')
print('modelo cargado · revisión', getattr(modelo.modelo.config, '_commit_hash', '?'))"""),
    code("""# 4 · DEMOSTRACIÓN: grabar esta celda
demo_d3.video(modelo)"""),
    code("""# 5 · una pregunta escrita en el momento, sobre el historial del redactado 0
# (grabar también). No tiene etiqueta: se ve la decisión del sistema, sin acierto ni falla.
PREGUNTA = '¿puedo tomar estadística este semestre si ya pasé cálculo 2?'
demo_d3.en_vivo(modelo, PREGUNTA)"""),
    code("""# 6 · después de grabar: baja la traza y la fila de la pregunta en vivo (no se graba).
# Se dejan en trazas/ y resultados/ del repositorio y se suben con el PDF.
from google.colab import files
files.download('/content/proyecto/trazas/en_vivo.jsonl')
files.download('/content/proyecto/resultados/en_vivo.raw.jsonl')"""),
]


def _escribir(celdas, salida):
    nb = {"cells": celdas, "metadata": {"accelerator": "GPU", "colab": {"gpuType": "T4"},
                                        "kernelspec": {"name": "python3",
                                                       "display_name": "Python 3"}},
          "nbformat": 4, "nbformat_minor": 5}
    salida.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(celdas)} celdas -> {salida.name}")


def main():
    _escribir(CELDAS, SALIDA)
    _escribir(CELDAS_DEMO, SALIDA_DEMO)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
