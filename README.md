# Validación de inscripción de ramos desde una pregunta en prosa

**Proyecto semestral — Generative Artificial Intelligence (580694)**
Universidad de Concepción · Facultad de Ingeniería · Primavera 2026
Prof. Carlos Navarrete, PhD

---

## Equipo

- Joaquín Sepúlveda
- Renato Saavedra
- Lucas Saldivia

## Estado

**Deliverable 3** (31 de octubre de 2026). El sistema del D2 reconstruido como tres agentes
sobre el mismo Phi-3.5-mini sube el acierto conjunto de **64,0 % a 88,0 %** en 150 casos, y de
**65,6 % a 91,1 %** en una réplica sobre 180 casos sellados que nadie había usado. Detalle
en [la sección del D3](#deliverable-3--tres-agentes-sobre-el-mismo-modelo). Documento técnico:
[`poster/Deliverable_3.pdf`](poster/Deliverable_3.pdf). Video: [`demo_d3_colab.ipynb`](demo_d3_colab.ipynb).

**Deliverable 2 completo** (30 de septiembre de 2026). Sistema de tres pasos funcionando
sobre los mismos 60 casos, con el acierto conjunto subiendo de **16,7 % a 58,3 %** y usando
**un tercio de los tokens** del baseline. Detalle en [la sección del D2](#deliverable-2--el-sistema-de-tres-pasos).
Documento técnico: [`poster/Deliverable_2.pdf`](poster/Deliverable_2.pdf). Para reproducir el
video: [`demo_colab.ipynb`](demo_colab.ipynb) en una T4 de Colab
([abrir en Colab](https://colab.research.google.com/github/Luquitas02/genai-inscripcion-ramos/blob/main/demo_colab.ipynb)),
detalle en [Reproducir lo que muestra el video](#reproducir-lo-que-muestra-el-video).

**Deliverable 1 completo** (31 de agosto de 2026). Tarea definida, ground truth
construido y auditado, conjunto de prueba de 60 casos balanceados, y baseline medido sobre
tres modelos open-weight de familias distintas en nueve condiciones.

---

## La tarea

Un modelo de lenguaje abierto de **menos de 8 mil millones de parámetros** debe responder si
un estudiante puede inscribir un ramo, a partir de una pregunta escrita como la escribiría
una persona real, y citar la regla que sostiene la decisión.

**Entrada:** el historial del estudiante (ramos aprobados, reprobados, en curso, créditos
cursados) más la consulta en prosa:

> *"oye, me falta Cálculo 2 pero la estoy tomando ahora, ¿podría inscribir ecuaciones el
> que viene?"*

**Salida:** dos campos, alrededor de veinte tokens.

```json
{"decision": "condicional", "regla": "R-DEPENDE-APROBACION"}
```

| Campo | Valores | Cómo se corrige |
|---|---|---|
| `decision` | `sí` · `no` · `condicional` | coincidencia exacta |
| `regla` | código del prerrequisito o identificador del artículo | coincidencia exacta |

### Qué cuenta como respuesta correcta

Se reportan **dos métricas separadas**, cada una contra su propio piso trivial. El piso es
lo que consigue quien responde siempre lo mismo sin leer nada:

| Métrica | Constante trivial | Piso |
|---|---|---|
| decisión | siempre `no` | 21/60 = **35,0 %** |
| regla | siempre `R-SIN-IMPEDIMENTO` | 18/60 = **30,0 %** |
| ambas | siempre `sí` + `R-SIN-IMPEDIMENTO` | 18/60 = **30,0 %** |

El piso de la regla es alto porque el espacio de identificadores está torcido: los tres más
frecuentes cubren el 65 % de las respuestas, y todo caso cuya decisión es `sí` comparte
forzosamente la misma regla. Es una consecuencia de balancear la decisión, y por eso se
declara acá.

La métrica principal es el **acierto conjunto**: ambos campos correctos.

---

## Resultados del baseline

60 casos · 3 modelos · 3 condiciones · generación determinista

| Modelo | Params | Condición | Decisión | Regla | Ambas |
|---|---|---|---|---|---|
| Mistral-7B-v0.3 | 7,2 B | zero-shot, prosa | 40,0 % | 35,0 % | 33,3 % |
| | | zero-shot, reducida | 36,7 % | 31,7 % | 31,7 % |
| | | few-shot | 41,7 % | **45,0 %** | **38,3 %** |
| Qwen2.5-7B | 7,6 B | zero-shot, prosa | 40,0 % | 8,3 % | 8,3 % |
| | | zero-shot, reducida | 38,3 % | 6,7 % | 6,7 % |
| | | few-shot | 43,3 % | 31,7 % | 31,7 % |
| Phi-3.5-mini | 3,8 B | zero-shot, prosa | 43,3 % | 6,7 % | 5,0 % |
| | | zero-shot, reducida | 35,0 % | 5,0 % | 5,0 % |
| | | few-shot | 35,0 % | 23,3 % | 16,7 % |
| **Mejor constante, por columna** | — | "no" en decisión, "sí" en regla y ambas | **35,0 %** | **30,0 %** | **30,0 %** |

La fila de la constante toma la mejor respuesta fija de cada columna, así que no es una sola
constante: responder siempre "sí" da 30,0 % en las tres. Se detectó en la auditoría del 30 de
septiembre, y el D2 compara contra "siempre sí".

**Cinco de las nueve condiciones quedan por debajo de la mejor constante** en la métrica
conjunta. Solo la superan Mistral en sus tres condiciones y Qwen con few-shot, y el mejor
margen es de 8,3 puntos.

### Cada modelo colapsa en una categoría distinta

Predicciones en zero-shot con prosa, sobre 60 casos:

| Modelo | `sí` | `no` | `condicional` |
|---|---|---|---|
| Qwen2.5-7B | 9 | **48** | 3 |
| Phi-3.5-mini | 20 | 8 | **31** |
| Mistral-7B-v0.3 | **50** | 6 | 4 |
| *lo correcto* | *18* | *21* | *21* |

La fila de Phi suma 59: una de sus sesenta salidas no devolvió un JSON legible.

Los tres tienen sesgos distintos e incompatibles. Ninguno deduce la respuesta del
expediente. Cada uno se vuelca sobre una sola categoría.

---

## Los cuatro mecanismos de falla

| | Mecanismo | Evidencia |
|---|---|---|
| **E1** | No representa *"cursándola ahora"* como estado propio | de las 21 `condicional` esperadas, Qwen produce 3 y Mistral 4; Phi produce 31. Los 18 casos con prerrequisito en curso se parten 12 `condicional` / 6 `no` solo según el período preguntado. Mistral acierta **3 de esos 18**, y con la pregunta reducida acierta **0**: responde `sí` a los dieciocho |
| **E2** | Depende de que la pregunta le apunte al dato | al reducir la consulta a código y período, con el historial completo aún en el prompt, el acierto cae en los tres: −1,7 / −3,3 / −8,3 puntos |
| **E3** | No copia un identificador que tiene delante | Phi degrada `R-CREDITOS-MINIMOS` en `R-CREDITOS-MINIMISMU`, `-MINIMISIMO`, `-MINIMISMUDA`. 35 instancias en Phi, 0 en Qwen, 0 en Mistral |
| **E4** | Se contradice dentro de su propia respuesta | responde `sí` citando una regla que bloquea: hasta 28 de 60 en Qwen con la pregunta reducida, usando 4 identificadores distintos para los 60 casos. Mistral lo hace 10 veces, siempre citando `R-YA-CURSADA`, que no es la respuesta correcta en ninguno de los 60 |

### El few-shot ordena la salida pero no mejora la decisión

| | Contradicciones | Alucinaciones | Acierto de regla | Acierto de decisión |
|---|---|---|---|---|
| Phi | 18 → 11 | 35 → 4 | 6,7 % → 23,3 % | 43,3 % → 35,0 % |
| Qwen | 3 → 0 | 0 → 0 | 8,3 % → 31,7 % | 40,0 % → 43,3 % |
| Mistral | 10 → 3 | 0 → 0 | 35,0 % → 45,0 % | 40,0 % → 41,7 % |

Los conteos de contradicciones y alucinaciones de Phi son los que reportó el D1, sobre la
corrida original. La corrida de Phi relanzada el 17 de septiembre reproduce las nueve cifras
de acierto, pero da 33 → 3 alucinaciones y 15 → 11 contradicciones con `analisis.py`. El
documento del D2 cuenta 18 alucinaciones en zero-shot porque excluye `R-TOPE-MIN`, un
identificador que el prompt del baseline ofrece y que no es correcto en ningún caso.

Tres modelos de tres familias, el mismo patrón. Eso delimita con evidencia qué puede lograr
el trabajo de prompt del Deliverable 2 y qué queda para el harness del Deliverable 3.

---

## Factibilidad de ejecución

| | |
|---|---|
| Hardware | GPU T4 gratuita de Google Colab, cuantización a 4 bits |
| VRAM ocupada | ≈ 5 GB de 15 disponibles |
| Tiempo por caso | 4,2 s (Phi) a 11,0 s (Mistral) |
| Tokens de entrada | 3.515 a 3.914 (medidos en Mistral) |
| Corrida completa | 9 condiciones, ≈ 66 min de inferencia |
| Salidas con JSON válido | **539 / 540** |

El formato casi nunca falló. Los errores fueron de razonamiento.

---

## El ground truth

| Fuente | Uso |
|---|---|
| Malla de Ingeniería Civil Industrial, UdeC | grafo de prerrequisitos, créditos, semestres |
| Reglas de inscripción | topes de créditos, prácticas, régimen de excepción |

61 asignaturas · 227 créditos · 11 semestres · cadenas de hasta 6 niveles de profundidad ·
14 ramos con umbral de créditos aprobados.

**Auditado antes de usarse:** sin ciclos, sin prerrequisitos hacia semestres posteriores,
créditos acumulados consistentes en los once semestres. La auditoría detectó un umbral
inalcanzable (Planificación y Control de Producción exigía 150 créditos en un semestre
donde solo se acumulan 147) que se corrigió contra el portal.

El verificador determinista pasa **9 casos de control** resueltos a mano por el equipo.

> Las capturas del portal usadas para construir el grafo contienen datos personales
> (nombre, matrícula, promedio por semestre) y están excluidas de este repositorio.

---

## Diseño del conjunto de prueba

**Generación hacia atrás.** Se elige primero qué regla debe decidir y después se construye
el historial que la produce. Así la distribución de respuestas queda bajo control desde el
diseño.

**Autoverificación.** Cada constructor declara qué regla espera; el caso se descarta si el
verificador no coincide. Un desacuerdo es un error del generador y aparece al instante.

**Control de sesgo.** Cruce rasgo × respuesta antes de medir. El chequeo detectó y cerró dos
atajos reales: el período de la pregunta predecía la respuesta, y la frase *"la estoy
tomando ahora"* siempre acompañaba a `condicional`.

**Niveles de dificultad.** Cada caso lleva un nivel declarado sobre cinco perillas:
referencia al ramo, expresión del período, distractores en el historial, profundidad de la
cadena y reglas simultáneas.

---

## Limitaciones declaradas

- **La condición reducida no aísla la ambigüedad.** La versión en prosa menciona el ramo en
  curso; la reducida no. El historial completo está en el prompt en ambas, así que no es
  información nueva, pero la prosa **señala** el dato relevante. Esa comparación mide si el
  modelo depende de que le apunten, no si tolera la ambigüedad.
- **Un solo dominio.** Una malla, una carrera. No se afirma nada sobre generalización.
- **60 casos.** Suficiente para separar los efectos observados del baseline trivial, no para
  intervalos estrechos.
- **El espacio de reglas está torcido.** `R-SIN-IMPEDIMENTO` cubre 18 de los 60 casos y los
  tres identificadores más frecuentes cubren el 65 %; `R-CREDITOS-MINIMOS`, `R-TOPE-MAX` y
  `R-ESPECIAL` tienen 3 casos cada uno. Cualquier acierto por regla sobre esas colas tiene un
  intervalo muy ancho. Balancear sobre la regla, y no sobre la decisión, es trabajo del D2.
- **Los ejemplos del few-shot no son del todo ajenos al test set.** El tercer ejemplo usa
  525223 con `R-DEPENDE-APROBACION`, y 2 de los 60 casos comparten ese ramo y esa regla. Son
  3,3 % del set, equivalentes a 3,3 puntos como máximo. Ninguna de las tres mejoras de regla
  del few-shot (+23,4 en Qwen, +16,6 en Phi, +10,0 en Mistral) se explica por esa
  coincidencia, pero se declara igual.
- **El few-shot no ejemplifica 5 de las 8 reglas.** No hay ejemplo de `R-EXCEPCION-PRERREQ`,
  `R-CREDITOS-MINIMOS`, `R-TOPE-MAX` ni `R-ESPECIAL-*`, que juntas son 18 de los 60 casos.
  Que los ejemplos no arreglen el razonamiento admite una explicación alternativa que estos
  datos no descartan.
- **El prompt ofrece un identificador que nunca es correcto.** La línea de prioridad menciona
  `R-TOPE-MIN`, que no está entre los valores válidos enumerados y que el verificador nunca
  emite: en esa rama devuelve `R-EXCEPCION-PRERREQ`. Queda documentado y sin parchar, porque
  el código tiene que seguir siendo exactamente el que produjo los números reportados.

---

## Estructura

```
datos/
├── malla.json               grafo de prerrequisitos y reglas, congelado
├── casos.jsonl              60 casos etiquetados por el verificador
├── casos_nuevos.jsonl       60 casos más con la semilla 20260930, generados el 30 de
│                            septiembre con el sistema ya fijo
│   ── Deliverable 3 ──
├── casos_desarrollo.jsonl   52 casos para ajustar los prompts, semilla 20261020
├── casos_redactados.jsonl   30 casos originales con la pregunta redactada fuera de
│                            las plantillas (prueba)
├── casos_desarrollo_redactados.jsonl
│                            21 de desarrollo redactados, el chequeo de robustez
├── redactados.csv, desarrollo_redactados.csv
│                            autor y revisión de cada pregunta redactada
└── *_modelo.json            las respuestas del agente que las redactó

scripts/
│   ── Deliverable 1, congelado: produjo las cifras del baseline ──
├── verificador.py           ground truth determinista + 9 casos de control
├── generador.py             generación hacia atrás y control de balance
├── prompt.py                el prompt del baseline y el parseo de su salida
├── runner.py                corrida del baseline, métricas y reanudación
├── analisis.py              identificadores inventados y contradicciones
│   ── Deliverable 2 ──
├── ficha.py                 la ficha del caso y el paso 3 del sistema: aplica las
│                            reglas con la lógica del verificador (60/60 con la
│                            ficha verdadera)
├── pipeline.py              los prompts y parsers de los tres pasos
├── runner_d2.py             corrida del pipeline, 3 variantes × 2 modos
├── ablacion_p1.py           el paso 1 con y sin ejemplos
├── ablacion_p3.py           el paso 3, cuatro versiones del prompt
├── demo.py                  lo del video: baseline y sistema en vivo, casos 40 a 49
├── empaquetar.py            arma paquete_colab.zip y lo verifica byte a byte
├── gen_notebook.py          genera los tres notebooks de Colab
│   ── Deliverable 3 ──
├── herramientas.py          T1 (búsqueda léxica) y T2 (la ficha del D2)
├── agentes.py               los tres agentes: arman el prompt y leen la acción
├── orquestador.py           ejecuta cada acción, aplica los topes, escribe la traza
├── runner_d3.py             una configuración sobre un conjunto; --modelo-falso es
│                            la regla fija sin modelo
├── analisis_d3.py           todas las cifras del D3, según el protocolo
├── diagnostico_d3.py        el paso 1 del D2 separado por mecanismo
├── preparar_desarrollo.py   arma el conjunto de desarrollo
├── preparar_redactados.py   elige los casos a redactar y arma el conjunto
├── ver_traza.py             muestra una traza como conversación entre agentes
├── demo_d3.py               lo del video del D3
└── gen_notebook_d3.py       genera corrida_d3_colab.ipynb y demo_d3_colab.ipynb

prompts/                     un archivo por agente, con versión en la cabecera
└── ablaciones/              las versiones sin cada técnica

trazas/                      cada mensaje entre agentes de cada corrida del D3, con
                             el hash del prompt que lo produjo

resultados/
├── Mistral-*.raw.jsonl      baseline del D1
├── Phi-*.raw.jsonl          baseline del D1, relanzado el 17 de septiembre
├── pipeline__*.raw.jsonl    la corrida final del D2, de donde salen las cifras, y
│                            el sistema con Mistral y Qwen (30 de septiembre)
├── *__casos_nuevos.raw.jsonl baseline y sistema sobre los 60 casos nuevos
├── ablacion_p1__*.raw.jsonl el paso 1 con y sin ejemplos
├── ablacion_p3__*.raw.jsonl el paso 3, cuatro versiones del prompt
├── corrida_1_prompt_v1/     primera corrida, no mejoró (se conserva)
├── corrida_2_prompt_v2/     segunda corrida, no mejoró (se conserva)
├── corrida_3_final/         copia idéntica de pipeline__*, archivada junto a
│                            las otras dos para compararlas
└── agentes__*.raw.jsonl     el D3: una fila por caso y configuración

poster/
├── poster.tex               el entregable del D1, una página apaisada
├── Deliverable_1.pdf        el D1 compilado
├── deliverable2.tex         el entregable del D2, una página vertical
├── Deliverable_2.pdf        el D2 compilado
└── deliverable3.tex         el entregable del D3, una página vertical

PLAN.md                      el plan del D1
Hallazgos del baseline - Deliverable 1.docx
                             notas de trabajo del D1, previas al póster
PLAN_D2.md                   el diseño del D2 y su registro de decisiones
PLAN_D2_TAREAS.md            el plan de implementación por tareas
corrida_final_colab.ipynb    notebook del baseline del D1
corrida_d2_colab.ipynb       notebook del D2: ablaciones, grilla y demo
demo_colab.ipynb             solo la demo del video, clona el repositorio
corridas_30sep_colab.ipynb   los tres candidatos en el sistema y los 60 casos nuevos
PROTOCOLO_30SEP.md           las reglas de esas corridas, subidas antes de correrlas
requirements-colab.txt       las versiones con que se ensayó y grabó la demo
PLAN_D3.md                   el diseño del D3 y su registro de decisiones
PROTOCOLO_D3.md              las reglas de la corrida final, subidas antes de correrla
corrida_d3_colab.ipynb       notebook del D3: desarrollo y corrida final
demo_d3_colab.ipynb          solo la demo del video del D3
```

### Reproducir

```bash
python scripts/verificador.py            # 9/9 casos de control
python scripts/generador.py              # regenera los 60 casos
python scripts/runner.py --modelo mistralai/Mistral-7B-Instruct-v0.3 --condicion zero_shot
python scripts/analisis.py resultados/Mistral*.raw.jsonl resultados/Phi*.raw.jsonl
```

La generación es greedy (`do_sample=False`), así que el mismo entorno da la misma salida. Entre
entornos distintos (otra versión de `transformers` u otra GPU) el texto puede cambiar en algún
caso, como pasó con los conteos de E3 y E4 de Phi al relanzarlo. Por eso los notebooks fijan
`transformers==5.17.0`, la versión con que se midió el D2.

> **Sobre `resultados/`.** Están las tres corridas de Mistral y las tres de Phi caso a caso,
> así que sus cifras se recalculan con `analisis.py`. Las de Phi se relanzaron el 17 de
> septiembre y reprodujeron las nueve cifras reportadas sin desviación, lo que confirma que el
> entorno declarado sigue siendo válido. Las de Qwen siguen sin crudo: se midieron en una
> sesión de Colab que expiró antes de la descarga. Sus métricas del D1 están completas en este
> README.

---

# Deliverable 2 · El sistema de tres pasos

## Qué hace

El baseline recibe 3.862 tokens de una vez y debe identificar el ramo, recorrer el grafo de
prerrequisitos, distinguir aprobada de inscrita, sumar créditos y aplicar un orden de
prioridad entre ocho reglas. No lo logra. El sistema parte ese trabajo en tres pasos y cada
uno recibe solo lo que necesita.

| paso | quién lo hace | qué ve | ataca |
|---|---|---|---|
| 1 · extracción | **el modelo** | la pregunta y los 61 pares de código y nombre | la lectura de la prosa |
| 2 · ficha | el código | el ramo, la malla y el historial | E1, E2 |
| 3 · decisión | el código | la ficha y el reglamento | E3, E4 |

En el D1 el modelo leía la pregunta y el expediente y decidía. En este sistema solo identifica
el ramo y el período, y la ficha y la decisión las calcula el código con la lógica del
verificador que etiqueta los casos. Es una desviación del plan del D1, declarada en el
documento técnico: el 58,3 % mide la extracción que hace el modelo.

La ficha son ocho campos sobre un solo ramo. Como el historial trae 26 asignaturas en
promedio y el ramo objetivo tiene 1,2 prerrequisitos directos, el paso 2 descarta unas 25
asignaturas irrelevantes por caso.

## Resultados sobre los mismos 60 casos

| condición | decisión | regla | **ambas** | tok/caso | s/caso |
|---|---|---|---|---|---|
| baseline few-shot | 35,0 % | 23,3 % | 16,7 % | 3.862 | 4,2 |
| responder siempre "sí" | 30,0 % | 30,0 % | 30,0 % | — | — |
| ficha y reglas al modelo | 45,0 % | 25,0 % | 25,0 % | 6.072 | 10,4 |
| ficha al código | 45,0 % | 28,3 % | 28,3 % | 2.743 | 3,4 |
| **ficha y reglas al código** | **71,7 %** | **58,3 %** | **58,3 %** | **1.153** | **1,6** |
| *con el paso 1 resuelto* | 100,0 % | 100,0 % | 100,0 % | 1.153 | 1,6 |

El sistema triplica el baseline y es además la condición más barata, así que la mejora no
viene de gastar más cómputo.

**En 60 casos nuevos** (`datos/casos_nuevos.jsonl`, mismo generador con la semilla 20260930,
generados el 30 de septiembre con el sistema ya fijo) el baseline acierta 18/60 (30,0 %) y el
sistema 37/60 (61,7 %). Donde difieren, el sistema gana 29 y el baseline 10 (McNemar exacto,
p = 0,003). Ocho preguntas se repiten del conjunto original; sin ellas, 30/52 contra 16/52. El
protocolo se subió antes de correr: [`PROTOCOLO_30SEP.md`](PROTOCOLO_30SEP.md).

**E3 y E4 no ocurren en el sistema**, porque la regla y la decisión las entrega el código. En
el paso intermedio que se probó antes, donde el modelo elegía la regla de una lista cerrada y la
decisión se calculaba desde ella, las cuatro corridas de 60 casos no inventaron ningún
identificador. Dos de esas corridas (modo oráculo) reciben la misma ficha y repiten sus
salidas, así que son 180 respuestas distintas.

## Dónde se rompe

| | |
|---|---|
| acierto del sistema si el paso 1 acierta ramo y período | **28 de 28** |
| acierto del sistema si el paso 1 se equivoca | 7 de 32 |

Todo el error restante es extracción. El paso 1 identifica el ramo en 31 de 60 casos y se
degrada con la forma de nombrarlo: 13/20 con el nombre completo, 10/20 abreviado, 8/20
coloquial.

## Lo que muestra el video

Video: https://www.youtube.com/watch?v=GvLJfazDHvs (1:46). Corre el commit `4dde2d1`, marcado
con el tag [`d2-video`](https://github.com/Luquitas02/genai-inscripcion-ramos/tree/d2-video).

Los diez primeros casos de nivel 3, del 40 al 49, corridos en vivo en una T4 sin saltarse
ninguno. El baseline y el sistema corren sobre el mismo input, y cada salida del modelo se
compara en pantalla con la corrida guardada en `resultados/`.

**Caso 40, completo.** La regla que lo elige es *"primer caso de nivel 3 cuyo baseline
falla"*, y quedó escrita en `PLAN_D2_TAREAS.md` (commit `c8e0cca`, 17 de septiembre) antes de
correr el sistema. Nivel 3 es el más difícil: el ramo se nombra de forma coloquial, a veces junto a otro, y el historial trae distractores. El
sistema falla acá, y es el caso de falla que la guía exige. La pregunta es *"programación, la
reprobé, ¿puedo tomar Optimización 1 ahora ya?"*. El ramo consultado es 580315, pero el paso 1
devolvió 503203, que la pregunta nombra primero y que además es el prerrequisito que bloquea.
Los pasos 2 y 3 evaluaron 503203, así que la respuesta corresponde a Programación.

**Casos 41 a 49, una línea cada uno.** Según la corrida guardada, el baseline acierta 1 de 10
y el sistema 4 de 10. De esos cuatro, el caso 49 acierta con el ramo equivocado: el paso 1
devolvió 580325 en vez de 580327, y la respuesta para 580325 coincide por azar con la
correcta.

## Reproducir lo que muestra el video

Todo lo que no llama al modelo corre en cualquier máquina, sin GPU:

```bash
python scripts/verificador.py          # 9/9 casos de control
python scripts/ficha.py                # 60/60 reproducen al verificador desde la ficha
python scripts/pipeline.py             # 18/18 casos de parseo
python scripts/runner_d2.py --pruebas  # 6/6 chequeos del encadenado
```

Lo que llama al modelo necesita la T4 de Colab, el hardware declarado en el D1:

```bash
python scripts/empaquetar.py                              # arma paquete_colab.zip
# subir corrida_d2_colab.ipynb y paquete_colab.zip a Colab, y correr de arriba abajo

# o, dentro de Colab, los comandos sueltos:
python scripts/demo.py              # lo del video: caso 40 completo y 41 a 49 en una línea
python scripts/demo.py --modelo-falso   # sin GPU: solo prueba el formato, respuestas fijas
python scripts/runner_d2.py --variante codigo --modo encadenado    # el sistema, 60 casos
python scripts/ablacion_p1.py       # el paso 1 con y sin ejemplos
python scripts/ablacion_p3.py       # el paso 3, cuatro versiones del prompt
```

**Solo la demo.** `demo_colab.ipynb`
([abrir en Colab](https://colab.research.google.com/github/Luquitas02/genai-inscripcion-ramos/blob/main/demo_colab.ipynb))
clona este repositorio, imprime el commit que corre, pasa las autopruebas, carga Phi y ejecuta
`demo.video(modelo)`. Son unos cinco minutos en una T4, casi todos de carga del modelo. Las
pruebas sin GPU solo necesitan Python 3, sin dependencias externas.

`demo.py` imprime exactamente lo que se ve en el video: la pregunta, el baseline con su
veredicto, los tres pasos uno por uno, la comparación final y, para cada salida del modelo, si
es igual a la guardada en `resultados/`.

Los runners retoman una corrida a medias: si el archivo de salida ya existe en `resultados/`,
saltan los casos que ya tiene. En un clon del repositorio los 60 casos ya están, así que para
medir de nuevo hay que mover o borrar primero el `.raw.jsonl` correspondiente. El notebook
`corrida_d2_colab.ipynb` lo hace en su sección 4. Las salidas caso a caso quedan
en `resultados/pipeline__*.raw.jsonl`, así que cualquier cifra de este README se recalcula
desde ahí.

## Decisiones, y por qué

**El modelo es Phi-3.5-mini**, el más chico de los tres candidatos del D1. En el sistema el
modelo solo hace el paso 1, así que los tres se midieron haciendo ese trabajo sobre los 60
casos, con una regla de elección subida antes de correr ([`PROTOCOLO_30SEP.md`](PROTOCOLO_30SEP.md)):
cambiar a un modelo de 7B solo si acierta al menos 6 casos más que Phi con McNemar p < 0,05.

| modelo | params | ramo bien extraído | acierto conjunto | s/caso |
|---|---|---|---|---|
| **Phi-3.5-mini** | 3,8 B | 31/60 | 35/60 | 1,6 |
| Mistral-7B-v0.3 | 7,2 B | 32/60 | 36/60 | 3,1 |
| Qwen2.5-7B | 7,6 B | 41/60 | 42/60 | 2,8 |

Qwen acierta 7 casos más con p = 0,17, así que no cumple la regla y se mantiene Phi. Qwen sí
extrae mejor el ramo (p = 0,03), y esa brecha es el objetivo del D3. Qwen devolvió además dos
códigos que no existen en la malla; Phi ninguno. La primera versión del D2 argumentaba la elección con
el acierto de decisión fuera de la categoría donde cada modelo colapsa (Phi 40,5 %, Mistral
19,0 %). La auditoría del 30 de septiembre mostró que esa métrica no descuenta a una respuesta
constante, y se reemplazó por esta medición.

**Las reglas las aplica el código.** La ablación midió que el modelo las aplica al 31,7 % con
la ficha verdadera delante, y que el código lo hace al 100 %. Es uso de herramientas, una de
las intervenciones que la guía enumera.

**Hubo una revisión del prompt.** La primera corrida no mejoró al baseline porque el prompt
del paso 3 solo nombraba un desenlace. Las corridas fallidas están en
`resultados/corrida_1_prompt_v1/` y `corrida_2_prompt_v2/`, y no se borran. El detalle está en
[`PLAN_D2.md`](PLAN_D2.md).

**Límites declarados.** En los 12 casos con prerrequisito en curso preguntando por el próximo
período el sistema baja de 6/12 a 3/12. La respuesta correcta de los 12 es `condicional`, que el
baseline da con frecuencia. Los 9 casos de `R-EXCEPCION-PRERREQ` tienen todos cero créditos inscritos, así
que el conjunto no prueba la frontera de esa regla. Y las versiones del prompt se eligieron
por ablación sobre estos mismos 60 casos, así que diferencias de dos a cuatro casos no deben
leerse como efectos firmes. Por eso el sistema se midió además en 60 casos nuevos, donde acierta
37 contra 18 del baseline.

---

# Deliverable 3 · Tres agentes sobre el mismo modelo

## Qué hace

El sistema del D2 se reconstruye como tres agentes que usan el mismo Phi-3.5-mini y dos
herramientas sin modelo. Cada agente escribe su decisión en el campo `accion` de un JSON y un
orquestador en código la ejecuta ([`scripts/orquestador.py`](scripts/orquestador.py)).

| | recibe | devuelve | decide |
|---|---|---|---|
| **A · Intérprete** | la pregunta | ramo consultado con las palabras del estudiante, otros ramos, frase de período, período | entregar o `sin_ramo`; ante un rechazo, revisa |
| **T1 · buscar_ramo** | un texto | los 5 ramos más parecidos, con puntaje | (herramienta, sin modelo) |
| **B · Resolvedor** | la mención y los 5 candidatos | un código | elegir, buscar de nuevo (máx. 2 por vuelta) o `ninguno` |
| **C · Verificador** | la pregunta y la elección | citas de la pregunta y veredicto | aceptar y llamar a T2, o rechazar. Tras 2 vueltas al Intérprete, el tercer rechazo cierra el caso con la última elección |
| **T2 · motor de reglas** | código y período | decisión y regla | (herramienta: la ficha y el reglamento del D2) |

Los prompts están en [`prompts/`](prompts/), uno por agente, con su versión en la cabecera;
las versiones de las ablaciones están en `prompts/ablaciones/`. Cada mensaje de la traza guarda
el hash del prompt que lo produjo. Tope de 12 llamadas por caso.

## Resultados

Corrida final del 20 de octubre, con el protocolo [`PROTOCOLO_D3.md`](PROTOCOLO_D3.md) subido
antes de correr (commit `9158550`). Acierto conjunto, decisión y regla, el criterio del D1:

| | originales (60) | nuevos (60) | redactados (30) | **150** |
|---|---|---|---|---|
| baseline few-shot (D1) | 10 | 18 | 7 | 35 |
| sistema del D2 | 35 | 37 | 24 | 96 |
| regla fija, sin modelo | 42 | 41 | 7 | 90 |
| **tres agentes** | **52** | **51** | **29** | **132** |

Contra el D2, en los casos donde difieren, los agentes ganan 39 y pierden 3 (McNemar exacto,
p = 5,6·10⁻⁹). En los 30 redactados la diferencia es 6 a 1 (p = 0,125). La regla fija toma el
texto entre "inscribir", "tomar" o "meter" y el signo de interrogación, lo busca con T1 y supone
siempre el semestre actual. Supera al D2 en las preguntas de plantilla de esta corrida (83
contra 72) y cae a 7 de 30 en las redactadas.

### Réplica sobre 180 casos sellados

Después de la corrida del 20 de octubre, los 150 casos se usaron para diagnosticar y diseñar la
versión 5, así que ya no servían para medir. El 22 de octubre se corrió el mismo sistema, sin
cambiar código ni prompts, sobre los 180 casos de [`datos/prueba_v5/`](datos/prueba_v5/),
sellados el 21 de octubre (sha256 en `SELLO.txt`) y nunca usados para ajustar nada. El protocolo
[`PROTOCOLO_REPLICA_V4.md`](PROTOCOLO_REPLICA_V4.md) se subió antes de correr (commit `5b5c5d5`)
y fijaba que estos resultados irían al documento cualquiera fuera el resultado.

| | plantilla A (60) | plantilla B (60) | redactados a ciegas (60) | **180** | con ramo y período bien |
|---|---|---|---|---|---|
| baseline few-shot (D1) | 18 | 12 | 13 | 43 | — |
| sistema del D2 | 39 | 37 | 42 | 118 | 94 |
| regla fija, sin modelo | 37 | 40 | 25 | 102 | 57 |
| **tres agentes** | **54** | **55** | **55** | **164** | **158** |

Contra el D2 los agentes ganan 50 y pierden 4 (p = 3,8·10⁻¹¹). Cada conjunto por separado da
p < 0,001, incluidas las redactadas (14 a 1). Con el criterio estricto ganan 66 a 2. Sin los 8
casos de plantilla cuya pregunta repite una anterior, 50 a 4. Fuera del protocolo, sin los 38
casos que repiten el problema o la pregunta de un caso anterior, 34 a 4. Las cifras salen de
`python scripts/analisis_replica_v4.py`.

## Qué explica la mejora

| sin... | acierto (150) | Δ |
|---|---|---|
| la búsqueda T1 (el Resolvedor recibe el catálogo completo) | 75 | −57 |
| los 4 ejemplos del Intérprete | 123 | −9 |
| la lista de los otros ramos y la regla del verbo (descomposición) | 136 | +4 |
| el Verificador | 133 | +1 |
| el Resolvedor (se toma el primer candidato de T1) | 133 | +1 |

Las ablaciones son de la corrida de los 150 y no se repitieron en la réplica. La fila de
descomposición quita dos instrucciones a la vez. Copiar la frase de la pregunta antes de decidir
(`frase_periodo`, `cita_ramo`) y los 2 ejemplos del Verificador no se ablacionaron.

La mejora la explican T1, que saca al modelo de copiar códigos, y los ejemplos, que atacan M2
(sin ellos M2 baja de 34 a 26 y el período sube de 137 a 141). El Resolvedor y el Verificador
no aportan, y las trazas muestran por qué. El Resolvedor se apartó del primer candidato de T1 en
8 casos de los 150 y en 8 de los 180, y acertó en 1 de esos 16; en 8 el primero era el correcto.
Un rechazo del Verificador vuelve al Intérprete: si su mención estaba bien la repite, T1 devuelve
lo mismo y el Resolvedor elige lo mismo. Por eso 4 de los 5 casos con rechazo de cada corrida
terminan en un tope (en la réplica, 3 por rechazos y 1 por el límite de llamadas). Además el
Verificador no tiene veto: al llegar a un tope, T2 recibe la última elección aunque esté
rechazada. En 313 de los 330 casos la respuesta final es el primer candidato de T1 con el
período de la primera respuesta del Intérprete. El detalle por mecanismo y caso está en [`PLAN_D3.md`](PLAN_D3.md), en los registros del
20 y 21 de octubre.

**Caso de falla.** "...ando cursando administración y quería tomar marketing el otro
semestre, en marzo". El Intérprete leyó bien el período; el Verificador lo rechazó diciendo que
"el otro semestre" es el actual, el Intérprete cambió y el caso falló.

### La versión 5, que no se aceptó

Para corregir el bucle se probó una v5: el Verificador revisa el período contra el calendario y
un rechazo del ramo vuelve al Resolvedor. Se midió en 223 casos de desarrollo (los 52 + 21 de
desarrollo y los 150 de la corrida, que para la v5 eran desarrollo), con una regla de aceptación
escrita antes de correrla. Son cifras de desarrollo, no de prueba:

| | conjunto | estricto | período |
|---|---|---|---|
| v4 (la que se entrega) | 196 | 180 | 206 |
| v5 | 186 | 178 | 207 |
| v5b | 194 | 183 | 211 |

La v5b lee mejor el período, pero su Verificador convierte 4 aciertos estrictos en error (3 en
acierto conjunto) y el acierto
conjunto no llega al de la v4. Ninguna de las dos se aceptó. El código quedó en la rama
`v5-desarrollo` y el diagnóstico en `PLAN_D3.md` (22 de octubre).

## Lo que muestra el video

[`demo_d3_colab.ipynb`](demo_d3_colab.ipynb)
([abrir en Colab](https://colab.research.google.com/github/Luquitas02/genai-inscripcion-ramos/blob/main/demo_d3_colab.ipynb))
corre en vivo tres preguntas redactadas, elegidas por la regla del protocolo: "progra" (sin
bucles), "inglés básico 1" (el Verificador rechaza tres veces, con razón, un período mal leído;
el tope deja pasar ese período y la decisión sale correcta solo porque la regla no depende de
él) y el caso
de falla. Cada salida del modelo se marca `= guardada` si coincide con la traza de la corrida
final en [`trazas/`](trazas/). Las celdas 1 a 3 se corren antes de grabar; se graba la 4.

## Reproducir

Sin GPU, en cualquier máquina con Python 3:

```bash
python scripts/herramientas.py          # 8/8: T1 y T2 (T2 reproduce las 60 etiquetas)
python scripts/runner_d3.py --pruebas   # 29/29: cada rama del grafo con un modelo de guion
python scripts/demo_d3.py --pruebas     # la demo reproduce las trazas guardadas
python scripts/analisis_d3.py           # las cifras de los 150 casos
python scripts/analisis_replica_v4.py   # las cifras de la réplica sobre los 180
python scripts/diagnostico_d3.py        # el diagnóstico del paso 1 del D2 por mecanismo
python scripts/runner_d3.py --modelo-falso --casos datos/casos_redactados.jsonl --dir-salida /tmp/regla_fija
                                        # regla fija, idéntica a la guardada fila por fila
python scripts/ver_traza.py trazas/agentes__Phi-3.5-mini-instruct__completo__casos_redactados.jsonl 16
```

Con Phi, en una T4 de Colab: [`corrida_d3_colab.ipynb`](corrida_d3_colab.ipynb) clona el
repositorio en el commit de la corrida final (`COMMIT = '9158550'`, ya puesto) y corre el desarrollo (sección 5) o la etapa final
(sección 6, unas dos horas). El runner no retoma un archivo corrido con otros prompts u otro
commit. Las salidas quedan en `resultados/agentes__*.raw.jsonl` y `trazas/agentes__*.jsonl`.
El clon ya trae esos archivos, y con el mismo commit el runner los retoma sin volver a correr:
para repetir la medición desde cero hay que borrarlos antes en el clon de Colab, junto con
los `*__casos_redactados.raw.jsonl` del baseline y del D2.

La réplica se corre con [`replica_v4_colab.ipynb`](replica_v4_colab.ipynb)
([abrir en Colab](https://colab.research.google.com/github/Luquitas02/genai-inscripcion-ramos/blob/main/replica_v4_colab.ipynb)),
que clona el commit del protocolo de la réplica (`5b5c5d5`) y corre la v4, el baseline y el D2
sobre los 180 casos, entre una y dos horas.

## Cómo se midió

Los prompts se ajustaron solo en el conjunto de desarrollo
([`datos/casos_desarrollo.jsonl`](datos/casos_desarrollo.jsonl), 52 casos sin preguntas de
prueba), en cuatro versiones, y en 21 preguntas de desarrollo redactadas fuera de las
plantillas. La regla para aceptar cada versión se escribió en `PLAN_D3.md` antes de correrla.
Las 30 preguntas de [`datos/casos_redactados.jsonl`](datos/casos_redactados.jsonl) las redactó
un modelo de lenguaje sin acceso al sistema, a partir del ramo, el período y el ramo de contexto
de 30 casos originales ([`scripts/preparar_redactados.py`](scripts/preparar_redactados.py)); el
CSV registra autor y revisión de cada una. La etiqueta de esos casos es la del caso original,
porque depende del historial y no de la redacción. El equipo las leyó, y Claude, que conocía el
sistema, corrigió la redacción de 3 (filas 4, 18 y 20). Las 60 redactadas de la réplica se
hicieron igual, las leyó Lucas antes de sellarlas y Claude no las ha leído.

Límites que encontró la auditoría del 21 de octubre:

- El puntaje de T1 se ajustó mirando las menciones de originales y nuevos. Las redactadas y los
  180 de la réplica no los vio.
- 6 casos de desarrollo y 3 de desarrollo redactado comparten historial y consulta con 7 de los
  150. En los 180, 24 repiten el historial y la consulta de un caso anterior con otra pregunta,
  8 de plantilla repiten la pregunta de uno anterior, y 6 redactados salen de un caso base
  cuya pregunta de plantilla ya existía (la redactada es nueva). Son los 38 del cálculo
  exploratorio.
- 11 de los 132 aciertos de los 150 tienen el ramo o el período mal (6 de 164 en la réplica).
  Por eso se reporta también el criterio estricto.

---

## El proyecto completo

| Entregable | Fecha | Contenido | Estado |
|---|---|---|---|
| **D1** | 31 ago | Tarea, modelo y baseline | ✅ |
| **D2** | 30 sep | Sistema de tres pasos — 16,7 % → 58,3 % | ✅ |
| **D3** | 31 oct | Tres agentes sobre el mismo modelo — 64,0 % → 88,0 % (91,1 % en la réplica) | ✅ |
| D4 | 30 nov | Resultados y defensa | ⏳ |

El D1 reservaba la consulta al grafo para el D3. Se adelantó al D2 porque la ablación mostró
que el modelo no aplica las reglas, y la desviación queda declarada. El D3 atacó el cuello de
botella medido, el paso 1. La búsqueda se hizo léxica y no con embeddings, porque un modelo de
embeddings sería un segundo modelo en el sistema y la búsqueda léxica pone el ramo correcto
primero en 50 de 51 menciones no ambiguas.
