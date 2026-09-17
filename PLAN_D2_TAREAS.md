# Plan de implementación — Deliverable 2

> **Para quien ejecute esto:** las tareas van en orden y cada una termina con un entregable
> verificable por sí solo. Los pasos usan casillas (`- [ ]`) para seguimiento.

**Objetivo:** construir un pipeline de tres pasos que resuelva la tarea de inscripción con
Phi-3.5-mini, medirlo contra el baseline del D1 sobre los mismos 60 casos, y atribuir cada falla
al paso donde ocurre.

**Arquitectura:** el trabajo que hoy hace una sola llamada con 3.900 tokens se parte en tres
llamadas con contexto enfocado. El paso 1 extrae ramo y período de la pregunta en prosa. El paso 2
arma una ficha de siete campos con el estado del expediente. El paso 3 decide sobre esa ficha con
una lista cerrada de identificadores. El paso 2 tiene dos variantes, una donde lo resuelve el
modelo y otra donde lo resuelve código determinista.

**Herramientas:** Python 3, `transformers`, `bitsandbytes`, T4 de Google Colab. Sin dependencias
nuevas. Sin framework de tests: el proyecto ya usa el patrón de una lista `CASOS` y un `main()`
que imprime `N/M casos de control correctos` y devuelve 0 o 1.

**Diseño que implementa:** `PLAN_D2.md`

## Restricciones globales

- **Se congelan** `scripts/prompt.py`, `scripts/runner.py`, `scripts/verificador.py`,
  `scripts/generador.py`, `datos/malla.json` y `datos/casos.jsonl`. Ninguna tarea los modifica.
- **Modelo:** `microsoft/Phi-3.5-mini-instruct`, cuantizado a 4 bits.
- **Baseline de comparación:** `resultados/Phi-3.5-mini-instruct__few_shot__prosa.raw.jsonl`
  (35,0 % decisión · 23,3 % regla · 16,7 % conjunto).
- **Generación determinista:** `do_sample=False`, igual que el D1.
- **Idioma del código y los comentarios:** español, igual que el resto del repositorio.
- **Las tareas 1, 2, 3, 5 y 6 se desarrollan y prueban en el computador local, sin GPU.** Solo la
  tarea 4 necesita Colab.
- **Cada tarea termina con un commit.**

---

## Tarea 1: `scripts/ficha.py`

Construye la ficha determinista de un caso. Es el ground truth contra el que se mide el paso 2 en
la variante `puro`, y es el paso 2 mismo en la variante `retrieval`.

**Archivos:**
- Crear: `scripts/ficha.py`

**Interfaces:**
- Consume: de `verificador.py`, la clase `Verificador`, la constante `RUTA_MALLA` y las constantes
  de estado `APROBADA`, `INSCRITA`, `REPROBADA`, `NO_CURSADA`, `CUMPLE`, `CONDICIONAL`,
  `NO_CUMPLE`. También el helper de módulo `_historial(aprobadas=(), inscritas=(), reprobadas=())`.
- Define, en la cabecera del módulo, la ruta al conjunto de casos, en el mismo estilo que
  `RUTA_MALLA` en `verificador.py`:

  ```python
  RUTA_CASOS = Path(__file__).resolve().parent.parent / "datos" / "casos.jsonl"
  ```
- Produce, para las tareas 2, 3 y 5:
  - `construir_ficha(v, historial, ramo, periodo, creditos_ya_inscritos) -> dict`
  - `render_ficha(ficha) -> str`
  - `decidir_desde_ficha(v, ficha) -> {"decision": str, "regla": str}`
  - `comparar_fichas(esperada, obtenida) -> dict` con una clave booleana por campo

La ficha es este diccionario:

```python
{
    "ramo": "525223",
    "nombre": "Ecuaciones Diferenciales",
    "estado_actual": "no_cursada",
    "creditos_ramo": 5,
    "es_practica": False,
    "prerrequisitos": [
        {"codigo": "525150", "nombre": "Álgebra II", "estado": "aprobada"},
        {"codigo": "527150", "nombre": "Cálculo II", "estado": "inscrita"},
    ],
    "creditos_aprobados": 118,
    "umbral_creditos": None,
    "requisitos_especiales": [],
    "creditos_ya_inscritos": 12,
    "periodo": "actual",
}
```

Cada entrada de `requisitos_especiales` es
`{"nombre": "primer_anio_aprobado", "resultado": "cumple"|"cumple_condicional"|"no_cumple", "falta": "510140"|None}`.

`creditos_aprobados` usa `v.creditos_aprobados(historial)` cuando el período es `"actual"` y
`v.creditos_si_aprueba_lo_inscrito(historial)` cuando es `"proximo"`. Esa distinción es el
mecanismo E1 en forma aritmética y es la parte que más probablemente falle en la variante `puro`.

- [ ] **Paso 1: Escribir la prueba que falla**

Al final de `scripts/ficha.py`, la prueba de suficiencia. Es la prueba importante: verifica que la
ficha contiene todo lo necesario para decidir, comparando contra el verificador en los 60 casos.

```python
def _prueba_suficiencia():
    """La ficha debe bastar para reproducir al verificador en los 60 casos.

    Si falla, la ficha está incompleta: le falta un campo que alguna rama necesita.
    """
    v = Verificador()
    casos = [json.loads(l) for l in open(RUTA_CASOS, encoding="utf-8") if l.strip()]
    fallas = []
    for i, caso in enumerate(casos):
        esperado = v.evaluar(caso["historial"], caso["consulta"])
        ficha = construir_ficha(v, caso["historial"],
                                caso["consulta"]["ramos"][0],
                                caso["consulta"]["periodo"],
                                caso["consulta"]["creditos_ya_inscritos"])
        obtenido = decidir_desde_ficha(v, ficha)
        if (obtenido["decision"] != esperado["decision"]
                or obtenido["regla"] != esperado["regla"]):
            fallas.append((i, esperado, obtenido))
    return len(casos) - len(fallas), len(casos), fallas
```

- [ ] **Paso 2: Correrla para verificar que falla**

Ejecutar: `python scripts/ficha.py`
Esperado: falla con `NameError: name 'construir_ficha' is not defined`.

- [ ] **Paso 3: Escribir `construir_ficha` y `render_ficha`**

```python
def construir_ficha(v, historial, ramo, periodo, creditos_ya_inscritos):
    a = v.asig[ramo]
    cred = (v.creditos_aprobados(historial) if periodo == "actual"
            else v.creditos_si_aprueba_lo_inscrito(historial))
    prerreq = [{"codigo": p, "nombre": v.asig[p]["nombre"],
                "estado": v.estado(historial, p)}
               for p in a["prerrequisitos"]]
    especiales = []
    for req in a["requisitos_especiales"]:
        r, falta = v._conjunto_semestres_ok(historial, v.especiales[req]["semestres"], periodo)
        especiales.append({"nombre": req, "resultado": r, "falta": falta})
    return {
        "ramo": ramo,
        "nombre": a["nombre"],
        "estado_actual": v.estado(historial, ramo),
        "creditos_ramo": a["creditos"],
        "es_practica": ramo in v.practicas,
        "prerrequisitos": prerreq,
        "creditos_aprobados": cred,
        "umbral_creditos": a["creditos_minimos"] or None,
        "requisitos_especiales": especiales,
        "creditos_ya_inscritos": creditos_ya_inscritos,
        "periodo": periodo,
    }
```

`render_ficha` produce el bloque de texto que se le muestra al modelo en el paso 3, y que el modelo
debe producir en la variante `puro`. Usa exactamente estas etiquetas:

```python
def render_ficha(f):
    lineas = [
        f"ramo objetivo:         {f['ramo']}  {f['nombre']}",
        f"estado actual:         {f['estado_actual']}",
        f"créditos del ramo:     {f['creditos_ramo']}",
    ]
    if f["prerrequisitos"]:
        for i, p in enumerate(f["prerrequisitos"]):
            etq = "prerrequisitos:       " if i == 0 else "                      "
            lineas.append(f"{etq} {p['codigo']}  {p['nombre']}  {p['estado']}")
    else:
        lineas.append("prerrequisitos:        ninguno")
    lineas.append(f"créditos aprobados:    {f['creditos_aprobados']}  "
                  f"(contados para el período {f['periodo']})")
    lineas.append(f"umbral del ramo:       {f['umbral_creditos'] or 'ninguno'}")
    if f["requisitos_especiales"]:
        for r in f["requisitos_especiales"]:
            lineas.append(f"requisito especial:    {r['nombre']}  {r['resultado']}"
                          + (f"  falta {r['falta']}" if r["falta"] else ""))
    else:
        lineas.append("requisitos especiales: ninguno")
    lineas.append(f"créditos ya inscritos: {f['creditos_ya_inscritos']}")
    return "\n".join(lineas)
```

- [ ] **Paso 4: Escribir `decidir_desde_ficha`**

Replica las seis ramas del verificador en el mismo orden de prioridad, leyendo solo la ficha.
Sirve para dos cosas: probar que la ficha es suficiente, y dar el techo de acierto que el paso 3
podría alcanzar con una ficha perfecta.

```python
def decidir_desde_ficha(v, f):
    # 1. ya cursada
    if f["estado_actual"] in (APROBADA, INSCRITA):
        return {"decision": "no", "regla": "R-YA-CURSADA"}
    # 2. tope máximo
    pedidos = 0 if f["es_practica"] else f["creditos_ramo"]
    total = pedidos + f["creditos_ya_inscritos"]
    if total > v.tope_max:
        return {"decision": "no", "regla": "R-TOPE-MAX"}
    bajo_minimo = total < v.tope_min
    # 3. prerrequisitos
    hay_condicional = False
    for p in f["prerrequisitos"]:
        if p["estado"] == APROBADA:
            continue
        if p["estado"] == INSCRITA and f["periodo"] == "proximo":
            hay_condicional = True
            continue
        if bajo_minimo:
            return {"decision": "condicional", "regla": "R-EXCEPCION-PRERREQ"}
        return {"decision": "no", "regla": p["codigo"]}
    # 4. umbral de créditos aprobados
    if f["umbral_creditos"] and f["creditos_aprobados"] < f["umbral_creditos"]:
        return {"decision": "no", "regla": "R-CREDITOS-MINIMOS"}
    # 5. requisitos especiales
    for r in f["requisitos_especiales"]:
        if r["resultado"] == NO_CUMPLE:
            return {"decision": "no", "regla": "R-ESPECIAL-" + r["nombre"]}
        if r["resultado"] == CONDICIONAL:
            hay_condicional = True
    # 6. tope mínimo
    if total < v.tope_min:
        return {"decision": "condicional", "regla": "R-EXCEPCION-PRERREQ"}
    if hay_condicional:
        return {"decision": "condicional", "regla": "R-DEPENDE-APROBACION"}
    return {"decision": "sí", "regla": "R-SIN-IMPEDIMENTO"}
```

- [ ] **Paso 5: Escribir `comparar_fichas` y el `main()`**

```python
def comparar_fichas(esperada, obtenida):
    """Compara campo por campo. Devuelve un dict de booleanos, uno por campo."""
    if obtenida is None:
        return {k: False for k in ("ramo", "estado_actual", "creditos_ramo",
                                   "prerrequisitos", "creditos_aprobados",
                                   "umbral_creditos", "requisitos_especiales")}
    def norm_pre(lista):
        return sorted((p.get("codigo"), p.get("estado")) for p in (lista or []))
    def norm_esp(lista):
        return sorted((r.get("nombre"), r.get("resultado")) for r in (lista or []))
    return {
        "ramo": esperada["ramo"] == obtenida.get("ramo"),
        "estado_actual": esperada["estado_actual"] == obtenida.get("estado_actual"),
        "creditos_ramo": esperada["creditos_ramo"] == obtenida.get("creditos_ramo"),
        "prerrequisitos": norm_pre(esperada["prerrequisitos"]) == norm_pre(obtenida.get("prerrequisitos")),
        "creditos_aprobados": esperada["creditos_aprobados"] == obtenida.get("creditos_aprobados"),
        "umbral_creditos": esperada["umbral_creditos"] == obtenida.get("umbral_creditos"),
        "requisitos_especiales": norm_esp(esperada["requisitos_especiales"]) == norm_esp(obtenida.get("requisitos_especiales")),
    }
```

El `main()` corre `_prueba_suficiencia()`, imprime las fallas con su detalle si las hay, imprime
`N/60 casos reproducen al verificador desde la ficha`, y devuelve 0 solo si N es 60.

- [ ] **Paso 6: Correr y verificar que pasa**

Ejecutar: `python scripts/ficha.py`
Esperado: `60/60 casos reproducen al verificador desde la ficha`, código de salida 0.

Si sale menos de 60, **la ficha está incompleta y hay que arreglarla antes de seguir**. Las fallas
impresas dicen qué rama no se pudo resolver. No avanzar a la tarea 2 con este número abajo de 60.

- [ ] **Paso 7: Commit**

```bash
git add scripts/ficha.py
git commit -m "Agrega la ficha determinista del caso y su prueba de suficiencia"
```

---

## Tarea 2: `scripts/pipeline.py`

Los prompts y los parsers de los tres pasos. Sin llamadas al modelo, así que se prueba entero en
local contra salidas sintéticas.

**Archivos:**
- Crear: `scripts/pipeline.py`

**Interfaces:**
- Consume: de `ficha.py`, `construir_ficha`, `render_ficha`. De `verificador.py`, `Verificador`.
- Produce, para las tareas 3 y 6:
  - `prompt_paso1(caso, malla) -> list[dict]`
  - `parsear_paso1(texto, codigos) -> {"ramo": str|None, "periodo": str|None}`
  - `prompt_paso2(ramo, malla, historial, periodo) -> list[dict]`
  - `parsear_paso2(texto, v, ramo, periodo, creditos) -> dict|None`
  - `identificadores_validos(ficha) -> list[str]`
  - `prompt_paso3(ficha) -> list[dict]`
  - `parsear_paso3(texto, validos) -> {"decision": str|None, "regla": str|None, "parseo": str}`

Los prompts devuelven mensajes en formato chat, igual que `prompt.construir` del D1.

- [ ] **Paso 1: Escribir las pruebas de los parsers**

```python
CASOS_PARSEO = [
    # paso 1
    ("p1", '{"ramo": "525223", "periodo": "actual"}', {"ramo": "525223", "periodo": "actual"}),
    ("p1", 'Claro:\n{"ramo":"525223","periodo":"proximo"}\nEso.',
     {"ramo": "525223", "periodo": "proximo"}),
    ("p1", '{"ramo": "Ecuaciones", "periodo": "actual"}', {"ramo": None, "periodo": "actual"}),
    ("p1", 'no entiendo', {"ramo": None, "periodo": None}),
    # paso 3
    ("p3", '{"decision": "sí", "regla": "R-SIN-IMPEDIMENTO"}',
     {"decision": "sí", "regla": "R-SIN-IMPEDIMENTO", "parseo": "ok"}),
    ("p3", '{"decision": "SI", "regla": "525140"}',
     {"decision": "sí", "regla": "525140", "parseo": "ok"}),
    ("p3", '{"decision": "no", "regla": "R-CREDITOS-MINIMISMU"}',
     {"decision": "no", "regla": None, "parseo": "regla_fuera_de_lista"}),
    ("p3", 'sin json', {"decision": None, "regla": None, "parseo": "sin_json"}),
]
```

Tres decisiones de diseño que estas pruebas fijan:

1. `parsear_paso1` solo acepta un código que exista en la malla. Si el modelo devuelve el nombre
   del ramo en vez del código, es una falla del paso 1 y se registra como tal.
2. `parsear_paso3` rechaza cualquier regla fuera de la lista cerrada y lo marca como
   `regla_fuera_de_lista`. Ese es el mecanismo contra E3.
3. La normalización de la decisión (mayúsculas, tildes, `yes`) se copia tal cual de
   `prompt.parsear_respuesta` para que baseline y pipeline se corrijan igual.

- [ ] **Paso 2: Correr para verificar que falla**

Ejecutar: `python scripts/pipeline.py`
Esperado: falla con `NameError: name 'parsear_paso1' is not defined`.

- [ ] **Paso 3: Escribir `identificadores_validos`**

```python
def identificadores_validos(f):
    """Lista cerrada para el paso 3. Incluye los códigos de los prerrequisitos del caso.

    Sin esos códigos el sistema no puede responder los 12 casos cuya respuesta es un
    prerrequisito, que son el 20 % del conjunto. R-TOPE-MIN queda fuera a propósito:
    el verificador nunca lo emite.
    """
    base = ["R-SIN-IMPEDIMENTO", "R-DEPENDE-APROBACION", "R-EXCEPCION-PRERREQ",
            "R-TOPE-MAX", "R-CREDITOS-MINIMOS", "R-YA-CURSADA"]
    base += [p["codigo"] for p in f["prerrequisitos"]]
    base += ["R-ESPECIAL-" + r["nombre"] for r in f["requisitos_especiales"]]
    return base
```

- [ ] **Paso 4: Escribir los tres prompts y los tres parsers**

Lo que cada paso ve, y lo que deliberadamente no ve:

| Paso | Ve | No ve |
|---|---|---|
| 1 | la pregunta en prosa, los 61 pares de código y nombre | historial, reglas, malla con prerrequisitos |
| 2 | el código del ramo, la malla, el historial | la pregunta en prosa |
| 3 | la ficha renderizada, las reglas globales, el orden de prioridad, la lista cerrada | la malla, el historial, la pregunta |

El paso 1, completo, como referencia de estilo para los otros dos:

```python
INSTRUCCION_P1 = """Eres un asistente de inscripción académica. Se te entrega el catálogo de \
asignaturas y la consulta de un estudiante escrita de manera informal.

Tu única tarea es identificar DOS cosas:
1. El código de la asignatura por la que pregunta.
2. Si pregunta por el período actual o por el próximo.

El período actual es 2026-2. El próximo período es 2027-1.

El estudiante puede referirse a la asignatura por su nombre completo, por una abreviación o de \
manera coloquial. Devuelve siempre el CÓDIGO, nunca el nombre.

Responde ÚNICAMENTE con este JSON, sin texto adicional:

{"ramo": "<código>", "periodo": "actual" | "proximo"}"""


def prompt_paso1(caso, malla):
    catalogo = "\n".join(f"{a['codigo']}  {a['nombre']}" for a in malla["asignaturas"])
    usuario = (f"=== CATÁLOGO ===\n{catalogo}\n\n"
               f"=== CONSULTA ===\n{caso['pregunta_prosa']}\n\n"
               "Responde solo con el JSON.")
    return [{"role": "system", "content": INSTRUCCION_P1},
            {"role": "user", "content": usuario}]
```

Los parsers comparten un extractor de JSON, copiado de `prompt.parsear_respuesta` para que baseline
y pipeline se corrijan igual:

```python
def _extraer_json(texto):
    if not texto:
        return None, "vacio"
    ini, fin = texto.find("{"), texto.rfind("}")
    if ini == -1 or fin == -1 or fin < ini:
        return None, "sin_json"
    try:
        return json.loads(texto[ini:fin + 1]), "ok"
    except json.JSONDecodeError:
        return None, "json_invalido"


def parsear_paso1(texto, codigos):
    """codigos: el conjunto de códigos de la malla. Un ramo fuera de ese conjunto es None."""
    d, _ = _extraer_json(texto)
    if d is None:
        return {"ramo": None, "periodo": None}
    ramo = str(d.get("ramo", "")).strip()
    per = str(d.get("periodo", "")).strip().lower()
    return {"ramo": ramo if ramo in codigos else None,
            "periodo": per if per in ("actual", "proximo") else None}


def parsear_paso3(texto, validos):
    """Rechaza cualquier regla fuera de la lista cerrada. Ése es el mecanismo contra E3."""
    d, estado = _extraer_json(texto)
    if d is None:
        return {"decision": None, "regla": None, "parseo": estado}
    dec = str(d.get("decision", "")).strip().lower()
    dec = {"si": "sí", "sí": "sí", "yes": "sí", "no": "no",
           "condicional": "condicional", "conditional": "condicional"}.get(dec)
    regla = str(d.get("regla", "")).strip()
    if regla not in validos:
        return {"decision": dec, "regla": None, "parseo": "regla_fuera_de_lista"}
    return {"decision": dec, "regla": regla, "parseo": "ok"}
```

`parsear_paso2` recibe el texto, el `Verificador`, el ramo, el período y los créditos inscritos.
Extrae el JSON, y rellena con los valores del caso los campos que no dependen del modelo (`ramo`,
`periodo`, `creditos_ya_inscritos`, `nombre`, `creditos_ramo`, `es_practica`), porque esos son
datos de entrada y no juicios del modelo. Los cinco campos que sí evalúa el modelo son
`estado_actual`, `prerrequisitos`, `creditos_aprobados`, `umbral_creditos` y
`requisitos_especiales`, y son exactamente los cinco que `comparar_fichas` puntúa como juicio del
modelo. Si el JSON no se puede leer, devuelve `None`.

Cada prompt termina con la instrucción de responder solo con el JSON pedido, igual que el baseline.

- [ ] **Paso 5: Correr y verificar que pasa**

Ejecutar: `python scripts/pipeline.py`
Esperado: `8/8 casos de parseo correctos`, código de salida 0.

- [ ] **Paso 6: Commit**

```bash
git add scripts/pipeline.py
git commit -m "Agrega los prompts y parsers de los tres pasos del pipeline"
```

---

## Tarea 3: `scripts/runner_d2.py`

Corre el pipeline sobre los 60 casos y registra la salida de cada paso. Se prueba en local con un
modelo falso, sin GPU.

**Archivos:**
- Crear: `scripts/runner_d2.py`

**Interfaces:**
- Consume: de `runner.py`, la clase `ModeloHF`. De `pipeline.py`, los prompts y parsers. De
  `ficha.py`, `construir_ficha` y `comparar_fichas`.
- Produce: `resultados/pipeline__<modelo>__<variante>__<modo>.raw.jsonl`

Banderas de la línea de comandos:

```
--modelo      por defecto microsoft/Phi-3.5-mini-instruct
--variante    puro | retrieval
--modo        encadenado | oraculo
--limite N    correr solo los primeros N casos, para pruebas
--modelo-falso usar el modelo de prueba en vez de cargar pesos
```

Cada fila del `.jsonl` guarda: `id`, `variante`, `modo`, `nivel`, `esperado`, la salida cruda y
parseada de los tres pasos, `acierto_paso1` (dos booleanos), `acierto_paso2` (el dict de
`comparar_fichas`), `acierto_decision`, `acierto_regla`, `acierto_conjunto`, y `tokens` y
`segundos` por paso.

En modo `oraculo`, el paso 2 recibe el ramo y período verdaderos del caso, y el paso 3 recibe la
ficha determinista. En modo `encadenado`, cada paso recibe lo que produjo el anterior. Si el paso 1
falla y no devuelve un código válido, los pasos 2 y 3 se marcan como no ejecutados y el caso cuenta
como fallado.

En la variante `retrieval`, el paso 2 no llama al modelo: usa `construir_ficha` directamente y
registra cero tokens y cero segundos para ese paso.

- [ ] **Paso 1: Escribir el modelo falso y su prueba**

La interfaz tiene que ser idéntica a la de `ModeloHF` de `runner.py`, que es
`generar(mensajes) -> (texto, tokens_de_entrada)`. Devuelve dos valores, no tres: el tiempo lo mide
quien la llama, con `time.perf_counter()` alrededor de la llamada.

```python
class ModeloFalso:
    """Devuelve respuestas fijas. Permite probar el encadenado sin GPU.

    Misma firma que ModeloHF.generar, para que el runner no distinga entre ambos.
    """
    def __init__(self, respuestas):
        self.respuestas = respuestas
        self.llamadas = []
    def generar(self, mensajes):
        self.llamadas.append(mensajes)
        return self.respuestas[(len(self.llamadas) - 1) % len(self.respuestas)], 0
```

La prueba corre 3 casos en modo encadenado con un modelo falso que devuelve el paso 1 correcto y
una decisión fija, y verifica tres cosas: que se hicieron 3 llamadas por caso en la variante
`puro`, que se hicieron 2 por caso en la variante `retrieval`, y que el archivo de salida tiene una
fila por caso con las claves esperadas.

- [ ] **Paso 2: Correr para verificar que falla**

Ejecutar: `python scripts/runner_d2.py --modelo-falso --limite 3`
Esperado: falla, el archivo no existe todavía.

- [ ] **Paso 3: Escribir el bucle de corrida**

Copiar de `runner.py` el patrón de reanudación: si el archivo de salida ya existe, leer los `id` ya
hechos y saltarlos. Esto es lo que salvó la corrida del D1 cuando Colab se cayó.

- [ ] **Paso 4: Correr y verificar que pasa**

Ejecutar: `python scripts/runner_d2.py --modelo-falso --limite 3 --variante puro`
Esperado: `3/3 casos`, y el archivo con 3 filas.

Ejecutar: `python scripts/runner_d2.py --modelo-falso --limite 3 --variante retrieval`
Esperado: lo mismo, y 2 llamadas por caso en vez de 3.

- [ ] **Paso 5: Verificar el techo con el oráculo determinista**

Antes de gastar GPU, comprobar que un paso 3 perfecto da 60/60:

```bash
python -c "
import sys; sys.path.insert(0,'scripts')
import json
from verificador import Verificador
from ficha import construir_ficha, decidir_desde_ficha
v=Verificador()
casos=[json.loads(l) for l in open('datos/casos.jsonl',encoding='utf-8') if l.strip()]
ok=sum(decidir_desde_ficha(v, construir_ficha(v,c['historial'],c['consulta']['ramos'][0],
       c['consulta']['periodo'],c['consulta']['creditos_ya_inscritos']))==c['respuesta']
       for c in casos)
print(f'{ok}/60 techo con ficha y decision perfectas')"
```

Esperado: `60/60`. Ese es el techo que el pipeline puede alcanzar. Si sale menos, hay un desacuerdo
entre `casos.jsonl` y el verificador y hay que resolverlo antes de medir nada.

- [ ] **Paso 6: Commit**

```bash
git add scripts/runner_d2.py
git commit -m "Agrega el runner del pipeline con modelo falso para pruebas locales"
```

---

## Tarea 4: Correr la grilla en Colab

**Archivos:**
- Modificar: `paquete_colab.zip` (regenerar)
- Crear: `corrida_d2_colab.ipynb`
- Crear: 4 archivos en `resultados/`

- [ ] **Paso 1: Regenerar el paquete con los archivos nuevos**

```bash
python -c "
import zipfile
n=['scripts/verificador.py','scripts/prompt.py','scripts/runner.py','scripts/generador.py',
   'scripts/ficha.py','scripts/pipeline.py','scripts/runner_d2.py',
   'datos/malla.json','datos/casos.jsonl']
z=zipfile.ZipFile('paquete_colab.zip','w',zipfile.ZIP_DEFLATED)
[z.write(f) for f in n]; z.close(); print('paquete con', len(n), 'archivos')"
```

- [ ] **Paso 2: Crear el notebook**

Copiar `corrida_final_colab.ipynb` y cambiar la celda de medición por el bucle de la grilla. **Esta
vez sí montar Drive**, porque son cuatro corridas y no una:

```python
GRILLA = [('puro','encadenado'), ('puro','oraculo'),
          ('retrieval','encadenado'), ('retrieval','oraculo')]
for var, modo in GRILLA:
    cmd = [sys.executable, 'runner_d2.py', '--modelo', MODELO,
           '--variante', var, '--modo', modo]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print('\n'.join(r.stdout.strip().splitlines()[-20:]) if r.returncode == 0
          else 'FALLO:\n' + '\n'.join(r.stderr.strip().splitlines()[-8:]))
```

Antes del bucle, correr `python ficha.py` y `python pipeline.py` como chequeo de humo. Si alguno no
devuelve 0, parar.

- [ ] **Paso 3: Correr la grilla**

Cuatro corridas de 60 casos. La variante `puro` hace 3 llamadas por caso y la `retrieval` hace 2.
Con Phi a unos 2 segundos por llamada enfocada, calcular entre 40 y 55 minutos incluyendo la carga
del modelo.

- [ ] **Paso 4: Bajar y verificar**

Bajar el zip, extraerlo en `resultados/`, y confirmar que los cuatro archivos tienen 60 filas cada
uno:

```bash
for f in resultados/pipeline__*.raw.jsonl; do echo "$(wc -l < "$f") $f"; done
```

- [ ] **Paso 5: Commit**

```bash
git add resultados/pipeline__*.raw.jsonl corrida_d2_colab.ipynb
git commit -m "Corre la grilla del pipeline: dos variantes por dos modos sobre 60 casos"
```

---

## Tarea 5: `scripts/analisis_d2.py`

Produce las dos tablas que van al documento: la comparación contra el baseline y la atribución de
errores por paso.

**Archivos:**
- Crear: `scripts/analisis_d2.py`

**Interfaces:**
- Consume: los `.jsonl` de `resultados/`.
- Produce: salida por pantalla, que se copia al documento LaTeX.

- [ ] **Paso 1: Tabla de comparación**

Una fila por condición, con el baseline arriba. Columnas: decisión, regla, conjunto, tokens
promedio por caso, segundos promedio por caso.

La columna de tokens es la que responde la objeción de que el pipeline gana solo por hacer más
llamadas. Hay que reportarla aunque salga en contra.

- [ ] **Paso 2: Tabla de atribución por paso**

Para la variante `puro` en modo encadenado:

| | acierto |
|---|---|
| paso 1, ramo | |
| paso 1, período | |
| paso 2, cada uno de los 7 campos | |
| paso 3, decisión y regla | |

Y la diferencia entre el modo encadenado y el oráculo, que es el costo de la propagación de
errores.

- [ ] **Paso 3: Acierto por constructor**

Los ocho constructores (`_c_ok`, `_c_inscrita_proximo`, `_c_excepcion`, `_c_prerrequisito`,
`_c_inscrita_actual`, `_c_creditos`, `_c_tope_max`, `_c_especial`), baseline contra pipeline. Es
donde se ve si la intervención arregló lo que decía que iba a arreglar.

- [ ] **Paso 4: Correr y revisar**

Ejecutar: `python scripts/analisis_d2.py`

- [ ] **Paso 5: Elegir la variante que va al video**

Criterio: la que tenga mejor acierto conjunto en modo encadenado. Si la diferencia es menor a 3
casos, elegir `puro`, porque no adelanta el harness del D3.

- [ ] **Paso 6: Commit**

```bash
git add scripts/analisis_d2.py
git commit -m "Agrega el analisis del D2: comparacion, atribucion por paso y acierto por constructor"
```

---

## Tarea 6: `scripts/demo.py`

Un caso, baseline y pipeline lado a lado, con los tres pasos visibles. Es lo que se graba.

**Archivos:**
- Crear: `scripts/demo.py`

- [ ] **Paso 1: Elegir el caso con una regla declarada**

La rúbrica exige un input **no elegido para favorecer**. La regla, escrita antes de mirar: el
**primer caso de nivel 3 cuyo baseline falla**. Declararla en el README y en el documento.

```bash
python -c "
import sys, json; sys.path.insert(0,'scripts')
base=[json.loads(l) for l in open('resultados/Phi-3.5-mini-instruct__few_shot__prosa.raw.jsonl',encoding='utf-8')]
c=[r for r in base if r['nivel']==3 and not r['acierto_conjunto']]
print('caso del video:', c[0]['id'], c[0]['ramo'], '| esperado', c[0]['esperado'],
      '| baseline dijo', c[0]['prediccion'])"
```

- [ ] **Paso 2: Escribir el script**

`python scripts/demo.py --caso N` imprime, en este orden: la pregunta en prosa, la respuesta del
baseline con su veredicto, los tres pasos del pipeline uno por uno con su salida cruda, la
respuesta final con su veredicto, y la respuesta correcta.

Que imprima despacio y legible. Son tres minutos de video y el profesor tiene que poder leer.

- [ ] **Paso 3: Correr en Colab y grabar**

El demo necesita GPU. Correrlo en el mismo notebook de la tarea 4, en una celda al final.

- [ ] **Paso 4: Commit**

```bash
git add scripts/demo.py
git commit -m "Agrega la demo de un caso con baseline y pipeline lado a lado"
```

---

## Tarea 7: Documento, README y video

**Archivos:**
- Crear: `poster/deliverable2.tex` y `poster/Deliverable_2.pdf`
- Modificar: `README.md`

- [ ] **Paso 1: El documento en Overleaf**

Una página vertical. El D1 se compiló en Overleaf con pdfLaTeX y quedó apaisado; **este va
vertical**, que es lo que pide la rúbrica. Debe contener:

- el diagrama del pipeline, con los tres pasos y qué entra y sale de cada uno
- el modelo y su versión: `microsoft/Phi-3.5-mini-instruct`, 3,8 B, 4 bits
- las estrategias alternativas evaluadas: las dos variantes con sus cifras
- los resultados contra el baseline sobre los 60 casos, con el tamaño del conjunto dicho
- los límites: el caso de falla con su explicación mecánica, la filtración de los casos de
  excepción, y la comparación de tokens entre baseline y pipeline

Redactar con la regla del curso: prosa llana, una idea por oración, sin rayas de inciso ni
antítesis decorativa.

- [ ] **Paso 2: Verificar el PDF**

Una sola página. Vertical. Compilado en LaTeX. Sin texto cortado. Las cifras coinciden una a una
con las que imprime `analisis_d2.py`.

- [ ] **Paso 3: El README**

Agregar una sección del D2 con: qué hace el pipeline, los comandos exactos que reproducen lo que
muestra el video, el caso usado en el video y la regla con que se eligió, y la tabla de resultados.

El sexto criterio dice que un repositorio que solo guarda archivos, sin instrucciones que lleven al
resultado demostrado, no recibe crédito. La prueba a pasar: alguien que clone el repo y siga el
README llega al mismo número.

- [ ] **Paso 4: Grabar el video**

Máximo 3:00, solo se miran los primeros 3:00. Debe mostrarse la ejecución real, con el baseline
visible sobre el mismo input. Sin cortes que oculten la ejecución. Subir con acceso abierto y
probar el link desde una ventana privada.

- [ ] **Paso 5: Corregir la nota del D1 sobre los crudos perdidos**

El `README.md` dice que los crudos de Phi se perdieron. Ya no es cierto para Phi, sí para Qwen.
Corregir ese párrafo.

- [ ] **Paso 6: Commit y push**

```bash
git add README.md poster/deliverable2.tex poster/Deliverable_2.pdf
git commit -m "Cierra el Deliverable 2: documento de una pagina, README y video"
git push origin main
```

- [ ] **Paso 7: Verificar el repositorio desde afuera**

Abrir el link en una ventana privada, sin sesión. Confirmar que responde, que el README se ve bien
formateado, y que el link del video funciona. El criterio dice **al momento de la corrección**, no
al momento de subirlo.

---

## Orden y holgura

| Tarea | Dónde | Estimación | Fecha tope |
|---|---|---|---|
| 1. `ficha.py` | local | 2 h | 19 sep |
| 2. `pipeline.py` | local | 3 h | 20 sep |
| 3. `runner_d2.py` | local | 2 h | 21 sep |
| 4. Grilla en Colab | Colab | 1 h | 22 sep |
| 5. `analisis_d2.py` | local | 2 h | 23 sep |
| 6. `demo.py` | local y Colab | 2 h | 24 sep |
| 7. Documento, README, video | Overleaf | 4 h | 28 sep |

El 24 de septiembre es la fecha en que el trabajo con riesgo debe estar cerrado. Del 24 al 30
quedan seis días de holgura para el documento, el video y los imprevistos, con el Certamen 1 del 9
de octubre ya a la vista.

**Si algo se atrasa**, se corta la variante `retrieval` de la tarea 4 y se conserva la medición por
paso. La medición por paso sostiene el criterio de lectura de los límites, que vale 10 puntos.
