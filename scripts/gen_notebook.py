# -*- coding: utf-8 -*-
"""
Genera los dos notebooks de Google Colab del Deliverable 2: `corrida_d2_colab.ipynb`, que
mide todo, y `demo_colab.ipynb`, que clona el repositorio y corre solo la demostración.

El notebook es un artefacto derivado y se versiona igual, porque es lo que se abre en Colab.
Este script existe para poder regenerarlo sin editar JSON a mano.

No arma el paquete. De eso se encarga `empaquetar.py`, y tener el empaquetado en un solo
lugar evita que las dos versiones se desincronicen.

Uso:
    python scripts/gen_notebook.py
"""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SALIDA = BASE / "corrida_d2_colab.ipynb"
SALIDA_DEMO = BASE / "demo_colab.ipynb"
SALIDA_30SEP = BASE / "corridas_30sep_colab.ipynb"
REPO = "https://github.com/Luquitas02/genai-inscripcion-ramos"


def md(texto):
    return {"cell_type": "markdown", "metadata": {}, "source": texto.splitlines(True)}


def code(texto):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": texto.splitlines(True)}


CELDAS = [
    md("""# Pipeline del Deliverable 2 — Phi-3.5-mini

Ejecuta las celdas **en orden, de arriba abajo**. No hay que editar ninguna.

Dos mediciones distintas, y conviene correr la primera antes que la segunda:

| sección | qué mide | cuánto tarda |
|---|---|---|
| 6, ablaciones | el paso 1 con y sin ejemplos, y el paso 3 con cuatro prompts | ~15 min |
| 7, la grilla | el pipeline completo, 3 variantes × 2 modos | ~20 min |
"""),

    md("""## 1 · GPU y dependencias
Debe decir `cuda: True` y mostrar una **Tesla T4**.

Si no aparece la T4: menú *Entorno de ejecución* → *Cambiar tipo de entorno de ejecución* →
acelerador **T4 GPU**.
"""),
    code("""!nvidia-smi -L
!pip -q install transformers==5.17.0 accelerate bitsandbytes
import torch; print('cuda:', torch.cuda.is_available())
# transformers queda fijo en 5.17.0, la version con que se midio del 17 al 19 de septiembre.
# Las demas quedan impresas para poder registrarlas en requirements-colab.txt.
from importlib.metadata import version
for paquete in ('torch', 'transformers', 'accelerate', 'bitsandbytes'):
    print(f'{paquete}=={version(paquete)}')"""),

    md("""## 2 · Subir el paquete
Sube `paquete_colab.zip`. Se arma en la raíz del repositorio con
`python scripts/empaquetar.py`.

Para ver solo la demostración del video no hace falta este notebook: `demo_colab.ipynb`
clona el repositorio y corre la demo en unos cinco minutos.

**Ojo:** si ya subiste un archivo con ese nombre en esta sesión, Colab no lo reemplaza, lo
guarda como `paquete_colab (1).zip`. La celda siguiente toma el más reciente, así que no
importa cómo termine llamándose.
"""),
    code("""import os
os.chdir('/content')
from google.colab import files
subidos = files.upload()
for nombre, contenido in subidos.items():
    print(f'{nombre}: {len(contenido):,} bytes')"""),

    md("""## 3 · Descomprimir y verificar
**Ésta es la celda que decide si se puede seguir.** Corre las autopruebas del repositorio.
Todas tienen que pasar antes de gastar un segundo de GPU.

Debe terminar con `TODO EN ORDEN`.
"""),
    code("""import subprocess, sys, os, glob, zipfile

# Colab NO reemplaza un archivo subido que ya existe: lo guarda como "nombre (1).zip".
# Por eso no se busca por nombre, se toma el zip mas reciente de /content.
zips = sorted(glob.glob('/content/*.zip'), key=os.path.getmtime)
if not zips:
    raise SystemExit('no hay ningun .zip en /content: vuelve a la celda anterior')
paquete = zips[-1]
print(f'usando {paquete}  ({os.path.getsize(paquete):,} bytes)')
os.system('unzip -o -q "%s" -d /content/proyecto' % paquete)
os.chdir('/content/proyecto/scripts')
print()

PRUEBAS = [
    ('verificador.py', ['verificador.py']),
    ('ficha.py',       ['ficha.py']),
    ('pipeline.py',    ['pipeline.py']),
    ('runner_d2.py',   ['runner_d2.py', '--pruebas']),
    ('ablacion_p3.py', ['ablacion_p3.py', '--modelo-falso', '--limite', '2']),
    ('ablacion_p1.py', ['ablacion_p1.py', '--modelo-falso', '--limite', '2']),
]

todo_ok = True
for nombre, args in PRUEBAS:
    if not os.path.exists(args[0]):
        print(f'[FALTA] {nombre:16} no esta en el paquete')
        todo_ok = False
        continue
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    ultima = (r.stdout.strip().splitlines() or ['(sin salida)'])[-1]
    print(f'[{"OK  " if r.returncode == 0 else "FALLA"}] {nombre:16} {ultima[:60]}')
    if r.returncode != 0:
        todo_ok = False
        print(r.stdout[-1200:])
        print(r.stderr[-600:])

print()
print('TODO EN ORDEN' if todo_ok else '*** NO SIGAS: algo fallo ***')"""),

    md("""## 4 · Limpiar mediciones anteriores
Si esta sesión ya corrió algo, quedan archivos a medio escribir. El runner los daría por
buenos y los retomaría, mezclando dos mediciones. Esta celda los borra.

Las corridas completas anteriores están guardadas en el repositorio, así que no se pierde nada.
"""),
    code("""import glob, os

borrados = glob.glob('/content/proyecto/resultados/*.jsonl')
for f in borrados:
    os.remove(f)
print(f'{len(borrados)} archivos de mediciones anteriores borrados')"""),

    md("""## 5 · Modelo
Phi-3.5-mini, 3,8 mil millones de parámetros, cuantizado a 4 bits.
"""),
    code("""MODELO = 'microsoft/Phi-3.5-mini-instruct'
print('modelo elegido:', MODELO)"""),

    md("""## 6 · Ablaciones
Dos mediciones cortas que deciden qué prompt usar, antes de gastar los 25 minutos de la
grilla completa.

- **Paso 1**, con y sin ejemplos resueltos. Es el cuello de botella del sistema: si elige
  mal la asignatura, el caso está perdido pase lo que pase después.
- **Paso 3**, cuatro versiones del prompt, con la ficha verdadera de cada caso. El techo
  demostrado es 60/60.

Unos 15 minutos las dos.
"""),
    code("""import subprocess, sys, os, time

os.chdir('/content/proyecto/scripts')
t0 = time.time()
for script in ['ablacion_p1.py', 'ablacion_p3.py']:
    r = subprocess.run([sys.executable, script, '--modelo', MODELO],
                       capture_output=True, text=True)
    if r.returncode == 0:
        print(r.stdout[-4000:])
    else:
        print('FALLO en ' + script + ':')
        print('\\n'.join(r.stderr.strip().splitlines()[-10:]))
    print()
print('ablaciones completas en %.1f minutos' % ((time.time() - t0) / 60))"""),

    md("""## 7 · La grilla
El pipeline completo, seis corridas de 60 casos. Las variantes mueven el trabajo del modelo
al código una pieza por vez, así que la diferencia entre dos filas contiguas mide lo que esa
pieza aporta.

| variante | paso 2, la ficha | paso 3, la decisión |
|---|---|---|
| `puro` | el modelo | el modelo |
| `retrieval` | el código | el modelo |
| `codigo` | el código | el código |

Y cada variante en dos modos: `encadenado`, que es el sistema, y `oraculo`, que le da a cada
paso la entrada correcta para medir su competencia aislada.

Las dos corridas de `codigo` casi no usan GPU, así que el total ronda los 20 minutos. **Si
algo se corta, vuelve a correr esta misma celda**: retoma donde iba.
"""),
    code("""import subprocess, sys, os, time

os.chdir('/content/proyecto/scripts')
GRILLA = [('puro', 'encadenado'), ('puro', 'oraculo'),
          ('retrieval', 'encadenado'), ('retrieval', 'oraculo'),
          ('codigo', 'encadenado'), ('codigo', 'oraculo')]

t0 = time.time()
for var, modo in GRILLA:
    print('=' * 72)
    print('%s  ·  variante %s  ·  modo %s' % (MODELO, var, modo))
    print('=' * 72)
    cmd = [sys.executable, 'runner_d2.py', '--modelo', MODELO,
           '--variante', var, '--modo', modo]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0:
        print('\\n'.join(r.stdout.strip().splitlines()[-16:]))
    else:
        print('FALLO:')
        print('\\n'.join(r.stderr.strip().splitlines()[-10:]))
        break
    print()

print('grilla completa en %.1f minutos' % ((time.time() - t0) / 60))"""),

    md("""## 8 · Tabla comparativa
El baseline arriba, las corridas del pipeline abajo.
"""),
    code("""import json, glob, os

print('{:34} {:>9} {:>8} {:>8} {:>9} {:>8}'.format(
    'condicion', 'decision', 'regla', 'ambas', 'tok/caso', 's/caso'))
print('-' * 82)

f = '/content/proyecto/baseline/Phi-3.5-mini-instruct__few_shot__prosa.raw.jsonl'
if os.path.exists(f):
    r = [json.loads(l) for l in open(f, encoding='utf-8') if l.strip()]
    p = lambda k: 100 * sum(x[k] for x in r) / len(r)
    print('{:34} {:8.1f}% {:7.1f}% {:7.1f}% {:9,.0f} {:8.1f}'.format(
        'baseline few-shot (1 llamada)', p('acierto_decision'), p('acierto_regla'),
        p('acierto_conjunto'),
        sum(x['tokens_entrada'] for x in r) / len(r),
        sum(x['segundos'] for x in r) / len(r)))
else:
    print('  (falta el baseline en baseline/)')

for f in sorted(glob.glob('/content/proyecto/resultados/pipeline__*.raw.jsonl')):
    r = [json.loads(l) for l in open(f, encoding='utf-8') if l.strip()]
    if not r:
        continue
    p = lambda k: 100 * sum(x[k] for x in r) / len(r)
    print('{:34} {:8.1f}% {:7.1f}% {:7.1f}% {:9,.0f} {:8.1f}'.format(
        '%s / %s' % (r[0]['variante'], r[0]['modo']),
        p('acierto_decision'), p('acierto_regla'), p('acierto_conjunto'),
        sum(x['tokens_total'] for x in r) / len(r),
        sum(x['segundos_total'] for x in r) / len(r)))"""),

    md("""## 9 · Atribución por paso
Dónde se rompe el sistema.
"""),
    code("""import json, glob

for f in sorted(glob.glob('/content/proyecto/resultados/pipeline__*.raw.jsonl')):
    r = [json.loads(l) for l in open(f, encoding='utf-8') if l.strip()]
    if not r:
        continue
    n = len(r)
    print('=' * 72)
    print('variante %s  ·  modo %s   (n=%d)' % (r[0]['variante'], r[0]['modo'], n))
    print('=' * 72)
    print('  paso 1  ramo %5.1f%%   periodo %5.1f%%' % (
        100 * sum(x['paso1']['acierto_ramo'] for x in r) / n,
        100 * sum(x['paso1']['acierto_periodo'] for x in r) / n))
    for c in r[0]['paso2']['acierto']:
        print('  paso 2  %-24s %5.1f%%' % (
            c, 100 * sum(x['paso2']['acierto'][c] for x in r) / n))
    print('  paso 3  decision %5.1f%%   regla %5.1f%%' % (
        100 * sum(x['acierto_decision'] for x in r) / n,
        100 * sum(x['acierto_regla'] for x in r) / n))
    print('  CONJUNTO %5.1f%%' % (100 * sum(x['acierto_conjunto'] for x in r) / n))
    print()"""),

    md("""## 10 · Demostración
Lo que muestra el video: los diez primeros casos de nivel 3, del 40 al 49, sin saltarse
ninguno. El **caso 40** se muestra completo, con los tres pasos. Salió de una regla escrita
antes de correr el sistema, el primer caso de nivel 3, y el sistema falla ahí: es el caso de
falla que la guía exige. Los otros nueve van en una línea cada uno, con el conteo al final.

Son **dos celdas**. La primera carga el modelo y tarda minutos. La segunda corre la
demostración en segundos, y **ésa es la que se graba**.
"""),
    code("""# --- CELDA A: cargar el modelo. NO hace falta grabar esto. ---
# Cargar Phi en 4 bits toma minutos y la demostracion toma segundos. Separarlos es lo que
# hace que el video quepa en tres minutos mostrando ejecucion y no una barra de progreso.
import sys, os
sys.path.insert(0, '/content/proyecto/scripts')
os.chdir('/content/proyecto/scripts')

from runner import ModeloHF
import demo

modelo = ModeloHF(MODELO, max_new_tokens=256)
print('modelo cargado')"""),

    md("""### Celda B: la demostración
**Ésta es la que se graba.** Con el modelo ya en memoria, los diez casos corren en menos de un
minuto y la salida aparece en vivo.
"""),
    code("""# --- CELDA B: la demostracion. ESTO es lo que se graba. ---
import importlib
importlib.reload(demo)

casos_mostrados = demo.video(modelo)"""),

    md("""## 11 · Descargar
Baja todo lo medido para comitearlo al repositorio.
"""),
    code("""import shutil
shutil.make_archive('/content/resultados_d2', 'zip', '/content/proyecto/resultados')
from google.colab import files
files.download('/content/resultados_d2.zip')"""),
]


# El notebook corto: solo lo que muestra el video, desde un clon del repositorio. Trae las
# corridas guardadas en resultados/, así que la demo compara cada salida en vivo con ellas.
CELDAS_DEMO = [
    md("""# Demostración del Deliverable 2 — Phi-3.5-mini

Reproduce lo que muestra el video, en una T4 de Colab y en unos cinco minutos. Ejecuta las
celdas en orden. No hay que subir nada: la primera celda clona el repositorio.

Si no aparece la T4: menú *Entorno de ejecución* → *Cambiar tipo de entorno de ejecución* →
acelerador **T4 GPU**.
"""),
    code("""!nvidia-smi -L
!pip -q install transformers==5.17.0 accelerate bitsandbytes
!rm -rf /content/proyecto && git clone -q """ + REPO + """ /content/proyecto
!git -C /content/proyecto log -1 --format='commit %h  %ad  %s'
import torch; print('cuda:', torch.cuda.is_available())
# transformers queda fijo en 5.17.0, la version con que se midio del 17 al 19 de septiembre.
# Las demas quedan impresas para poder registrarlas en requirements-colab.txt.
from importlib.metadata import version
for paquete in ('torch', 'transformers', 'accelerate', 'bitsandbytes'):
    print(f'{paquete}=={version(paquete)}')"""),

    md("""## Autopruebas, sin GPU
Deben pasar las cuatro antes de cargar el modelo.
"""),
    code("""import subprocess, sys, os
os.chdir('/content/proyecto/scripts')
for args in (['verificador.py'], ['ficha.py'], ['pipeline.py'], ['runner_d2.py', '--pruebas']):
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    ultima = (r.stdout.strip().splitlines() or ['(sin salida)'])[-1]
    print(f'[{"OK  " if r.returncode == 0 else "FALLA"}] {args[0]:16} {ultima[:60]}')
    if r.returncode != 0:
        raise SystemExit('*** NO SIGAS: fallo ' + args[0] + ' ***')
print('TODO EN ORDEN')"""),

    md("""## Cargar el modelo
Tarda unos minutos. No hace falta grabar esta celda.
"""),
    code("""import sys
sys.path.insert(0, '/content/proyecto/scripts')
from runner import ModeloHF
import demo

modelo = ModeloHF('microsoft/Phi-3.5-mini-instruct', max_new_tokens=256)
print('modelo cargado')"""),

    md("""## La demostración
**Ésta es la que se graba.** Los diez primeros casos de nivel 3, del 40 al 49, sin saltarse
ninguno. El caso 40 se muestra completo y es el caso de falla. Cada salida del modelo se
compara con la corrida guardada en `resultados/`.
"""),
    code("""casos_mostrados = demo.video(modelo)"""),
]


# Las corridas del 30 de septiembre, descritas en PROTOCOLO_30SEP.md: los otros dos
# candidatos haciendo el trabajo del sistema, y los 60 casos nuevos. Clona el repositorio,
# así que corre exactamente el commit que imprime la primera celda.
CELDAS_30SEP = [
    md("""# Corridas del 30 de septiembre

Lo que describe `PROTOCOLO_30SEP.md`, escrito antes de correr esto:

| sección | qué corre | cuánto tarda |
|---|---|---|
| 4 | Phi en los 60 casos nuevos: baseline y sistema | ~15 min |
| 5 | el sistema con Mistral-7B en los 60 casos originales | ~25 min |
| 6 | el sistema con Qwen2.5-7B en los 60 casos originales | ~25 min |

Ejecuta las celdas en orden. Cada sección copia lo que mide a Google Drive apenas termina,
así que si la sesión se cae no se pierde nada. **Si una sección se corta, vuelve a correr
esa misma celda**: retoma donde iba.
"""),

    md("""## 1 · GPU, dependencias y repositorio
Debe decir `cuda: True`, mostrar una **Tesla T4** e imprimir el commit que se va a correr.
"""),
    code("""!nvidia-smi -L
!pip -q install transformers==5.17.0 accelerate bitsandbytes
!rm -rf /content/proyecto && git clone -q """ + REPO + """ /content/proyecto
!git -C /content/proyecto log -1 --format='commit %h  %ad  %s'
import torch; print('cuda:', torch.cuda.is_available())
from importlib.metadata import version
for paquete in ('torch', 'transformers', 'accelerate', 'bitsandbytes'):
    print(f'{paquete}=={version(paquete)}')"""),

    md("""## 2 · Google Drive
**No te saltes esta celda.** Sin Drive los resultados quedan en el disco temporal de Colab y se
pierden si la sesión se cae. Pide permiso para acceder a tu Drive: acéptalo.
"""),
    code("""from google.colab import drive
drive.mount('/content/drive')
import os, shutil, glob
RESPALDO = '/content/drive/MyDrive/genai_30sep'
os.makedirs(RESPALDO, exist_ok=True)

def respaldar():
    nuevos = (glob.glob('/content/proyecto/resultados/*casos_nuevos*.raw.jsonl')
              + glob.glob('/content/proyecto/resultados/pipeline__Mistral*.raw.jsonl')
              + glob.glob('/content/proyecto/resultados/pipeline__Qwen*.raw.jsonl'))
    for f in nuevos:
        shutil.copy(f, RESPALDO)
    print(f'{len(nuevos)} archivos copiados a {RESPALDO}')

print('Drive listo:', RESPALDO)"""),

    md("""## 3 · Autopruebas, sin GPU
Debe terminar con `TODO EN ORDEN`, y la última línea confirma el conjunto nuevo:
`60 casos · {'no': 21, 'condicional': 21, 'sí': 18}`.
"""),
    code("""import subprocess, sys, os, json
from collections import Counter
os.chdir('/content/proyecto/scripts')
for args in (['verificador.py'], ['ficha.py'], ['pipeline.py'], ['runner_d2.py', '--pruebas']):
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    ultima = (r.stdout.strip().splitlines() or ['(sin salida)'])[-1]
    print(f'[{"OK  " if r.returncode == 0 else "FALLA"}] {args[0]:16} {ultima[:60]}')
    if r.returncode != 0:
        raise SystemExit('*** NO SIGAS: fallo ' + args[0] + ' ***')
print('TODO EN ORDEN')
nuevos = [json.loads(l) for l in open('../datos/casos_nuevos.jsonl', encoding='utf-8')]
print(len(nuevos), 'casos ·', dict(Counter(c['respuesta']['decision'] for c in nuevos)))"""),

    md("""## 4 · Phi en los 60 casos nuevos
Dos celdas. Primero el baseline del Deliverable 1 (few-shot, 64 tokens) y después el sistema.
Cada una carga el modelo por su cuenta, unos 3 minutos.
"""),
    code("""%cd /content/proyecto/scripts
!python runner.py --modelo microsoft/Phi-3.5-mini-instruct --condicion few_shot --casos ../datos/casos_nuevos.jsonl
respaldar()"""),
    code("""%cd /content/proyecto/scripts
!python runner_d2.py --modelo microsoft/Phi-3.5-mini-instruct --variante codigo --modo encadenado --casos ../datos/casos_nuevos.jsonl
respaldar()"""),

    md("""## 5 · El sistema con Mistral-7B-Instruct-v0.3
Si falla con un error 401 o *gated repo*: entra a
huggingface.co/mistralai/Mistral-7B-Instruct-v0.3, acepta las condiciones, y agrega tu token
de Hugging Face en el panel de la llave (Secretos) de Colab con el nombre `HF_TOKEN`.
"""),
    code("""%cd /content/proyecto/scripts
!python runner_d2.py --modelo mistralai/Mistral-7B-Instruct-v0.3 --variante codigo --modo encadenado
respaldar()"""),

    md("""## 6 · El sistema con Qwen2.5-7B-Instruct
"""),
    code("""%cd /content/proyecto/scripts
!python runner_d2.py --modelo Qwen/Qwen2.5-7B-Instruct --variante codigo --modo encadenado
respaldar()"""),

    md("""## 7 · Resumen
Solo lee lo que ya se midió, y aplica la regla de elección del protocolo.
"""),
    code("""import json, os
from math import comb
R = '/content/proyecto/resultados/'

def leer(nombre):
    ruta = R + nombre
    if not os.path.exists(ruta):
        return None
    return {x['id']: x['acierto_conjunto'] for x in map(json.loads, open(ruta, encoding='utf-8'))}

def mcnemar(a, b):
    ga = sum(a[i] and not b[i] for i in a)
    gb = sum(b[i] and not a[i] for i in a)
    n, k = ga + gb, min(ga, gb)
    p = min(1.0, 2 * sum(comb(n, j) for j in range(k + 1)) / 2 ** n) if n else 1.0
    return ga, gb, p

print('CORRIDA B · Phi en los 60 casos nuevos')
b = leer('Phi-3.5-mini-instruct__few_shot__prosa__casos_nuevos.raw.jsonl')
s = leer('pipeline__Phi-3.5-mini-instruct__codigo__encadenado__casos_nuevos.raw.jsonl')
for et, r in (('baseline', b), ('sistema', s)):
    print(f'  {et:9}', f'{sum(r.values())}/{len(r)}' if r else 'falta')
if b and s and len(b) == len(s) == 60:
    gs, gb, p = mcnemar(s, b)
    print(f'  sistema gana {gs}, baseline gana {gb}, McNemar p = {p:.2g}')

print()
print('CORRIDA A · el sistema con cada candidato, 60 casos originales')
phi = leer('pipeline__Phi-3.5-mini-instruct__codigo__encadenado.raw.jsonl')
print(f'  Phi-3.5-mini             {sum(phi.values())}/60')
for nombre in ('Mistral-7B-Instruct-v0.3', 'Qwen2.5-7B-Instruct'):
    r = leer(f'pipeline__{nombre}__codigo__encadenado.raw.jsonl')
    if not r or len(r) < 60:
        print(f'  {nombre:24} falta')
        continue
    go, gp, p = mcnemar(r, phi)
    cambia = sum(r.values()) - sum(phi.values()) >= 6 and p < 0.05
    print(f'  {nombre:24} {sum(r.values())}/60  gana {go}, Phi gana {gp}, p = {p:.2g}'
          f'  -> {"SUPERA la regla" if cambia else "no supera la regla, se mantiene Phi"}')"""),

    md("""## 8 · Descargar
Baja los archivos nuevos en un zip. Están también en tu Drive, en `genai_30sep`.
"""),
    code("""respaldar()
import shutil
shutil.make_archive('/content/corridas_30sep', 'zip', RESPALDO)
from google.colab import files
files.download('/content/corridas_30sep.zip')"""),
]


def escribir(salida, celdas):
    nb = {"cells": celdas,
          "metadata": {"accelerator": "GPU",
                       "colab": {"provenance": [], "gpuType": "T4"},
                       "kernelspec": {"display_name": "Python 3", "name": "python3"},
                       "language_info": {"name": "python"}},
          "nbformat": 4, "nbformat_minor": 0}
    with open(salida, "w", encoding="utf-8") as fh:
        json.dump(nb, fh, ensure_ascii=False, indent=1)

    # toda celda de codigo tiene que compilar; las lineas de shell (! o %) no son Python
    errores = []
    for i, c in enumerate(celdas):
        if c["cell_type"] != "code":
            continue
        src = "\n".join(l for l in "".join(c["source"]).splitlines()
                        if not l.lstrip().startswith(("!", "%")))
        try:
            compile(src, f"celda{i}", "exec")
        except SyntaxError as e:
            errores.append((i, str(e)))

    n_code = sum(1 for c in celdas if c["cell_type"] == "code")
    print(f"{salida.name}: {len(celdas)} celdas, {n_code} de codigo")
    for i, e in errores:
        print(f"  [SINTAXIS] celda {i}: {e}")
    print("sintaxis OK" if not errores else "*** hay celdas que no compilan ***")
    return not errores


def main():
    ok = escribir(SALIDA, CELDAS)
    ok = escribir(SALIDA_DEMO, CELDAS_DEMO) and ok
    ok = escribir(SALIDA_30SEP, CELDAS_30SEP) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    # La consola de Windows no escribe en UTF-8 por defecto y rompe los acentos.
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
