# -*- coding: utf-8 -*-
"""
Genera `entrenamiento_d4_colab.ipynb`: el entrenamiento del Intérprete del D4 (PROTOCOLO_D4.md).

  1. entrena el adaptador QLoRA 2 épocas sobre `datos/entrenamiento_d4/`, con un checkpoint por
     época en Drive (retoma si la sesión se cae);
  2. revisa el control sobre los 60 casos del piloto (que no se rompa como el del 13 nov);
  3. corre el sistema con el adaptador de cada época sobre el piloto y elige la época con la
     regla del protocolo;
  4. publica esa época en Hugging Face y verifica que lo publicado sea lo entrenado.

No toca la prueba sellada.

    python scripts/gen_notebook_entrenamiento_d4.py
"""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SALIDA = BASE / "entrenamiento_d4_colab.ipynb"
REPO = "https://github.com/Luquitas02/genai-inscripcion-ramos"
# El commit que sube PROTOCOLO_D4.md. Se escribe acá en un commit aparte, después.
COMMIT = ""
NOMBRE_HF = "phi35-mini-interprete-inscripcion-lora"


def md(t):
    return {"cell_type": "markdown", "metadata": {}, "source": t.splitlines(True)}


def code(t):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": t.splitlines(True)}


FICHA = '''---
base_model: microsoft/Phi-3.5-mini-instruct
library_name: peft
language: es
tags: [lora, qlora, peft, phi-3.5]
---

# Intérprete ajustado: Phi-3.5-mini + LoRA (proyecto de inscripción de ramos)

Adaptador LoRA para el **Intérprete**, el primero de los tres agentes de un sistema que decide si
un estudiante de Ingeniería Civil Industrial (UdeC) puede inscribir un ramo a partir de una
pregunta en prosa. El Intérprete lee la consulta y devuelve un JSON con el ramo consultado, los
otros ramos que nombra, la frase que dice cuándo y el período (`actual` 2026-2 o `proximo`
2027-1). Proyecto del curso Generative Artificial Intelligence, Deliverable 4.

Repositorio, datos, protocolo y resultados: {repo}

| | |
|---|---|
| Base | `microsoft/Phi-3.5-mini-instruct`, cargada en 4 bits NF4 (cómputo fp16) |
| Método | QLoRA, rango 16, alpha 32, dropout 0,05, todas las capas lineales |
| Entrenamiento | lr 2e-4 lineal, 3 pasos de calentamiento, batch efectivo 8, pérdida solo sobre la respuesta |
| Datos | {n_ent} pares de entrenamiento y {n_val} de validación (`datos/entrenamiento_d4/`) |
| Época publicada | {epoca} de 2 (elegida en los 60 casos del piloto, regla de `PROTOCOLO_D4.md`) |
| Hardware | {gpu}, {minutos} min de entrenamiento |
| Commit del código | `{commit}` |

Uso: cargar la base en 4 bits y `PeftModel.from_pretrained(base, "{repo_hf}", revision=...)`,
con el adaptador activo solo en las llamadas del Intérprete (`scripts/modelo_d4.py`).
'''


CELDAS = [
    md("""# Entrenamiento del Intérprete del D4 — Phi-3.5-mini

Ejecuta las celdas **en orden, de arriba abajo**. Todo lo que se corre y cómo se decide está en
`PROTOCOLO_D4.md`, subido antes de esta corrida. Este notebook **no toca la prueba sellada**.

| sección | qué hace | tiempo aprox. |
|---|---|---|
| 1 a 3 | GPU, dependencias, clon del repositorio, autopruebas, Drive | 5 min |
| 4 | entrena el adaptador 2 épocas (un checkpoint por época en Drive) | 2,5 h |
| 5 | el control y el sistema con cada época sobre los 60 del piloto, y la elección de la época | 40 min |
| 6 | publica la época elegida en Hugging Face y lo verifica | 3 min |
| 7 | bajar todo en un zip | 1 min |

**Si la sesión se cae**, vuelve a correr desde la sección 1: el entrenamiento retoma desde el
último checkpoint en Drive y las corridas del piloto retoman donde iban.

**Antes de empezar**, en Hugging Face crea un token de escritura (*Settings* → *Access Tokens* →
*Write*) y guárdalo en Colab: icono de la llave a la izquierda → *Add new secret* → nombre
`HF_TOKEN`, pega el token y activa *Notebook access*. Nunca lo pegues en una celda ni en el chat.
"""),
    md("""## 1 · GPU, dependencias y repositorio
Debe decir `cuda: True` y una **Tesla T4**. Si no: *Entorno de ejecución* → *Cambiar tipo de
entorno de ejecución* → **T4 GPU**. `COMMIT` es el commit del protocolo: no lo cambies.
"""),
    code(f"""COMMIT = '{COMMIT}'

%cd /content
!nvidia-smi -L
!pip -q install transformers==5.17.0 accelerate==1.14.0 bitsandbytes==0.50.2 peft==0.21.2 trl==1.17.1 datasets
!rm -rf /content/proyecto && git clone -q {REPO} /content/proyecto
import subprocess
assert COMMIT, 'falta el commit del protocolo'
subprocess.run(['git', '-C', '/content/proyecto', 'checkout', '-q', COMMIT], check=True)
!git -C /content/proyecto log -1 --format='commit %h  %ad  %s'
import torch; print('cuda:', torch.cuda.is_available())
from importlib.metadata import version
for paquete in ('torch', 'transformers', 'accelerate', 'bitsandbytes', 'peft', 'trl', 'datasets'):
    print(f'{{paquete}}=={{version(paquete)}}')"""),
    md("""## 2 · Autopruebas
No usan la GPU. Tienen que terminar en `TODO EN ORDEN`; si alguna falla, no sigas y avísame.
También comprueba que los datos de entrenamiento sean los del protocolo (sha256).
"""),
    code("""import subprocess, sys, os, hashlib
os.chdir('/content/proyecto/scripts')
pruebas = (['verificador.py'], ['herramientas.py'], ['runner_d3.py', '--pruebas'],
           ['modelo_d4.py'])
for args in pruebas:
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    ultima = (r.stdout.strip().splitlines() or ['(sin salida)'])[-1]
    print(f'[{"OK  " if r.returncode == 0 else "FALLA"}] {args[0]:22} {ultima[:70]}')
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit('*** NO SIGAS: falló ' + args[0] + ' ***')
SHA = {'entrenamiento.jsonl': '490510a88f02d889e334703e91d856b18c0fccd582a8d01474af2d97d5b5532d',
       'validacion.jsonl': '60fcd7cacc32951c4fd172c22319bc932fe163e3c607848e376b3e0780e25e35'}
for nombre, esperado in SHA.items():
    datos = open(f'/content/proyecto/datos/entrenamiento_d4/{nombre}', 'rb').read().replace(b'\\r\\n', b'\\n')
    assert hashlib.sha256(datos).hexdigest() == esperado, f'*** NO SIGAS: {nombre} no es el del protocolo ***'
    print(f'[OK  ] {nombre:22} sha256 del protocolo')
print('TODO EN ORDEN')"""),
    md("""## 3 · Google Drive
**No te saltes esta celda.** Los checkpoints, las curvas y las corridas del piloto van a Drive,
en `genai_d4/<commit>`, a medida que se producen.
"""),
    code("""from google.colab import drive
import shutil, json
from pathlib import Path
drive.mount('/content/drive')
HASH = subprocess.check_output(['git', '-C', '/content/proyecto', 'rev-parse', '--short=10',
                                'HEAD'], text=True).strip()
RESPALDO = Path('/content/drive/MyDrive/genai_d4') / HASH
PROYECTO = Path('/content/proyecto')
CHECKPOINTS = RESPALDO / 'checkpoints'
ENTRENAMIENTO = RESPALDO / 'entrenamiento'     # config.json, historial.json, curvas.png
SAL = RESPALDO / 'piloto'
for d in (CHECKPOINTS, ENTRENAMIENTO, SAL):
    d.mkdir(parents=True, exist_ok=True)
PILOTO = str(PROYECTO / 'datos' / 'piloto_d4' / 'piloto.jsonl')
print('Drive listo:', RESPALDO)"""),
    md("""## 4 · Entrenamiento (unas 2,5 horas)
Imprime la pérdida en cada paso y la de validación cada 23. Al final de cada época guarda el
adaptador en Drive (`checkpoint-161` y `checkpoint-322`). Si la sesión se cae, vuelve a correr
las secciones 1 a 3 y esta: retoma desde el último checkpoint.
"""),
    code("""if (ENTRENAMIENTO / 'config.json').exists():
    print('el entrenamiento ya terminó: no se vuelve a entrenar')
else:
    !cd /content/proyecto/scripts && python entrenar_d4.py --datos /content/proyecto/datos/entrenamiento_d4 --salida /content/adaptador_d4 --epocas 2 --eval-steps 23 --checkpoints {CHECKPOINTS} 2>&1 | grep -v -i warn
    for nombre in ('config.json', 'historial.json', 'curvas.png'):
        shutil.copy(f'/content/adaptador_d4/{nombre}', ENTRENAMIENTO / nombre)
config = json.loads((ENTRENAMIENTO / 'config.json').read_text(encoding='utf-8'))
print({k: config[k] for k in ('pasos', 'segundos', 'retomado', 'memoria_max_gb', 'gpu',
                              'perdida_validacion_final')})
EPOCAS = sorted(CHECKPOINTS.glob('checkpoint-*'), key=lambda p: int(p.name.split('-')[1]))
print('checkpoints:', [p.name for p in EPOCAS])
assert len(EPOCAS) == 2, '*** faltan checkpoints: avísame ***'
from IPython.display import Image, display
display(Image(str(ENTRENAMIENTO / 'curvas.png')))"""),
    md("""## 5 · El control y las dos épocas sobre los 60 del piloto
Carga Phi en 4 bits. Primero el control (Intérprete base con 27 ejemplos más en el prompt),
después el sistema con el adaptador de la época 1 y de la época 2. Al final aplica la regla del
protocolo y dice qué época se publica. Unos 40 minutos.
"""),
    code("""import gc
sys.path.insert(0, '/content/proyecto/scripts')
import runner_d3
from modelo_d4 import ConAdaptador

def leer(p):
    return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]

def liberar():
    gc.collect(); torch.cuda.empty_cache()

base = runner_d3.cargar_modelo('microsoft/Phi-3.5-mini-instruct')
print('modelo cargado · revisión', getattr(base.modelo.config, '_commit_hash', '?'))
salida, _ = runner_d3.ejecutar(base, 'control_d4', PILOTO, dir_salida=str(SAL))
control = leer(salida)
con_ilegibles = sum(1 for x in control if x['ramas']['ilegibles'])
print(f'\\nCONTROL: {con_ilegibles} de {len(control)} casos con alguna respuesta ilegible '
      f'(el protocolo tolera 3)')

resultado = {}
for i, ckpt in enumerate(EPOCAS, start=1):
    if i > 1:
        del base, ajustado; liberar()
        base = runner_d3.cargar_modelo('microsoft/Phi-3.5-mini-instruct')
    ajustado = ConAdaptador(base, str(ckpt), etiqueta=f'A-lora-e{i}')
    salida, _ = runner_d3.ejecutar(ajustado, 'completo', PILOTO, dir_salida=str(SAL))
    filas = leer(salida)
    resultado[i] = {'checkpoint': ckpt.name, 'conjunto': sum(x['acierto_conjunto'] for x in filas),
                    'ilegibles': sum(1 for x in filas if x['ramas']['ilegibles']),
                    'llamadas_con_adaptador': ajustado.llamadas_con_adaptador}

historial = json.loads((ENTRENAMIENTO / 'historial.json').read_text(encoding='utf-8'))
for i, r in resultado.items():
    paso = int(r['checkpoint'].split('-')[1])
    r['eval_loss'] = next(h['eval_loss'] for h in historial if 'eval_loss' in h and h['step'] == paso)
mejor = max(r['conjunto'] for r in resultado.values())
empatadas = [i for i, r in resultado.items() if r['conjunto'] == mejor]
EPOCA = min(empatadas, key=lambda i: resultado[i]['eval_loss'])
ELEGIDA = EPOCAS[EPOCA - 1]
eleccion = {'epocas': resultado, 'elegida': EPOCA, 'checkpoint': ELEGIDA.name,
            'control_casos_con_ilegibles': con_ilegibles, 'commit': HASH,
            'regla': 'más acierto conjunto en el piloto; si empatan, menor pérdida de validación'}
(RESPALDO / 'eleccion_epoca.json').write_text(json.dumps(eleccion, indent=1), encoding='utf-8')
print(json.dumps(eleccion, indent=1))
print(f'\\n>>> SE PUBLICA LA ÉPOCA {EPOCA} ({ELEGIDA.name})')
if con_ilegibles > 3:
    print('>>> OJO: el control pasó el límite de ilegibles. Avísame antes de seguir con la prueba.')"""),
    md("""## 6 · Publicar en Hugging Face
Escribe tu usuario de Hugging Face entre las comillas de `USUARIO_HF` y corre la celda. Crea
el repositorio público, sube la época elegida con su ficha, las curvas y la configuración, y
después **baja** el adaptador desde Hugging Face y comprueba que sea idéntico al entrenado. Al
final imprime la `REVISION`: cópiala y mándamela.
"""),
    code(f"""USUARIO_HF = ''
assert USUARIO_HF, 'escribe tu usuario de Hugging Face'
from google.colab import userdata
from huggingface_hub import HfApi, hf_hub_download
REPO_HF = f'{{USUARIO_HF}}/{NOMBRE_HF}'
api = HfApi(token=userdata.get('HF_TOKEN'))
api.create_repo(REPO_HF, private=False, exist_ok=True)

PUBLICAR = Path('/content/publicar')
shutil.rmtree(PUBLICAR, ignore_errors=True); PUBLICAR.mkdir()
for p in ELEGIDA.iterdir():
    if p.name.startswith('adapter_') or p.name.startswith('tokenizer') or p.name == 'chat_template.jinja':
        shutil.copy(p, PUBLICAR / p.name)
for nombre in ('config.json', 'historial.json', 'curvas.png'):
    shutil.copy(ENTRENAMIENTO / nombre, PUBLICAR / ('entrenamiento_' + nombre))
shutil.copy(RESPALDO / 'eleccion_epoca.json', PUBLICAR / 'eleccion_epoca.json')
FICHA = {json.dumps(FICHA)}
(PUBLICAR / 'README.md').write_text(FICHA.format(
    repo='{REPO}', n_ent=config['n_entrenamiento'], n_val=config['n_validacion'], epoca=EPOCA,
    gpu=config['gpu'], commit=HASH,
    minutos=str(round(config['segundos'] / 60)) + (' (solo el tramo después de retomar)' if config['retomado'] else ''), repo_hf=REPO_HF),
    encoding='utf-8')
info = api.upload_folder(folder_path=str(PUBLICAR), repo_id=REPO_HF,
                         commit_message=f'Intérprete D4, época {{EPOCA}}, código {{HASH}}')
REVISION = info.oid

def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()
bajado = hf_hub_download(REPO_HF, 'adapter_model.safetensors', revision=REVISION,
                         local_dir='/content/verificacion_hf')
assert sha(bajado) == sha(ELEGIDA / 'adapter_model.safetensors'), '*** lo publicado no es lo entrenado ***'
publicado = {{'repo_hf': REPO_HF, 'revision': REVISION, 'epoca': EPOCA, 'commit_codigo': HASH,
             'sha256_adapter': sha(bajado)}}
(RESPALDO / 'publicado_hf.json').write_text(json.dumps(publicado, indent=1), encoding='utf-8')
print(json.dumps(publicado, indent=1))
print(f'\\nhttps://huggingface.co/{{REPO_HF}}/tree/{{REVISION}}')"""),
    md("""## 7 · Bajar los resultados
Un zip con la configuración, las curvas, la elección de la época, lo publicado y las corridas del
piloto (sin los checkpoints, que pesan; quedan en Drive). Déjalo en `resultados/` del proyecto y
avísame.
"""),
    code("""from google.colab import files
ZIP = Path('/content/entrenamiento_d4_zip')
shutil.rmtree(ZIP, ignore_errors=True)
shutil.copytree(RESPALDO, ZIP, ignore=shutil.ignore_patterns('checkpoints'))
shutil.copytree(ELEGIDA, ZIP / 'adaptador_elegido',
                ignore=shutil.ignore_patterns('optimizer.pt', 'scheduler.pt', 'rng_state.pth'))
shutil.make_archive('/content/entrenamiento_d4', 'zip', str(ZIP))
files.download('/content/entrenamiento_d4.zip')"""),
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
