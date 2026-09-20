# -*- coding: utf-8 -*-
"""
Genera `corrida_d2_colab.ipynb`, el notebook de Google Colab del Deliverable 2.

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
!pip -q install -U transformers accelerate bitsandbytes
import torch; print('cuda:', torch.cuda.is_available())"""),

    md("""## 2 · Subir el paquete
Sube `paquete_colab.zip` desde `C:\\\\Lucas\\\\Claude\\\\2026-2\\\\GenAI\\\\deliverable-1\\\\`.

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

    md("""## 10 · Demostración de un caso
Los dos casos del video, con el baseline y el sistema lado a lado.

El **caso 40** salió de una regla escrita antes de mirar resultados: el primero de nivel 3
cuyo baseline falla. El sistema también falla ahí, y ése es el caso de falla que la guía
exige. El **caso 42** está elegido para mostrar el sistema funcionando, y se declara así.
"""),
    code("""import subprocess, sys, os

os.chdir('/content/proyecto/scripts')
for caso in [40, 42]:
    r = subprocess.run([sys.executable, 'demo.py', '--caso', str(caso), '--modelo', MODELO],
                       capture_output=True, text=True)
    if r.returncode == 0:
        print(r.stdout)
    else:
        print('FALLO en el caso %d:' % caso)
        print('\\n'.join(r.stderr.strip().splitlines()[-10:]))"""),

    md("""## 11 · Descargar
Baja todo lo medido para comitearlo al repositorio.
"""),
    code("""import shutil
shutil.make_archive('/content/resultados_d2', 'zip', '/content/proyecto/resultados')
from google.colab import files
files.download('/content/resultados_d2.zip')"""),
]


def main():
    nb = {"cells": CELDAS,
          "metadata": {"accelerator": "GPU",
                       "colab": {"provenance": [], "gpuType": "T4"},
                       "kernelspec": {"display_name": "Python 3", "name": "python3"},
                       "language_info": {"name": "python"}},
          "nbformat": 4, "nbformat_minor": 0}
    with open(SALIDA, "w", encoding="utf-8") as fh:
        json.dump(nb, fh, ensure_ascii=False, indent=1)

    # toda celda de codigo tiene que compilar; las lineas de shell (! o %) no son Python
    errores = []
    for i, c in enumerate(CELDAS):
        if c["cell_type"] != "code":
            continue
        src = "\n".join(l for l in "".join(c["source"]).splitlines()
                        if not l.lstrip().startswith(("!", "%")))
        try:
            compile(src, f"celda{i}", "exec")
        except SyntaxError as e:
            errores.append((i, str(e)))

    n_code = sum(1 for c in CELDAS if c["cell_type"] == "code")
    print(f"{len(CELDAS)} celdas, {n_code} de codigo")
    for i, e in errores:
        print(f"  [SINTAXIS] celda {i}: {e}")
    print("sintaxis OK" if not errores else "*** hay celdas que no compilan ***")
    return 0 if not errores else 1


if __name__ == "__main__":
    raise SystemExit(main())
