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

**Deliverable 2 completo** (30 de septiembre de 2026). Sistema de tres pasos funcionando
sobre los mismos 60 casos, con el acierto conjunto subiendo de **16,7 % a 58,3 %** y usando
**un tercio de los tokens** del baseline. Detalle en [la sección del D2](#deliverable-2--el-sistema-de-tres-pasos).

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
| **Constante trivial** | — | (sin leer nada) | **35,0 %** | **30,0 %** | **30,0 %** |

**Cinco de las nueve condiciones quedan por debajo de la constante trivial** en la métrica
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
└── casos.jsonl              60 casos etiquetados por el verificador

scripts/
│   ── Deliverable 1, congelado: produjo las cifras del baseline ──
├── verificador.py           ground truth determinista + 9 casos de control
├── generador.py             generación hacia atrás y control de balance
├── prompt.py                el prompt del baseline y el parseo de su salida
├── runner.py                corrida del baseline, métricas y reanudación
├── analisis.py              identificadores inventados y contradicciones
│   ── Deliverable 2 ──
├── ficha.py                 la ficha del caso, su prueba de suficiencia y la
│                            decisión determinista que marca el techo de 60/60
├── pipeline.py              los prompts y parsers de los tres pasos
├── runner_d2.py             corrida del pipeline, 3 variantes × 2 modos
├── ablacion_p1.py           el paso 1 con y sin ejemplos
├── ablacion_p3.py           el paso 3, cuatro versiones del prompt
├── demo.py                  un caso, baseline y sistema lado a lado
├── empaquetar.py            arma paquete_colab.zip y lo verifica byte a byte
└── gen_notebook.py          genera el notebook de Colab

resultados/
├── Mistral-*.raw.jsonl      baseline del D1
├── Phi-*.raw.jsonl          baseline del D1, relanzado el 17 de septiembre
├── pipeline__*.raw.jsonl    la corrida final del D2
├── corrida_1_prompt_v1/     primera corrida, no mejoró (se conserva)
└── corrida_2_prompt_v2/     segunda corrida, no mejoró (se conserva)

poster/
├── poster.tex               el entregable del D1, una página apaisada
└── deliverable2.tex         el entregable del D2, una página vertical

PLAN_D2.md                   el diseño del D2 y su registro de decisiones
PLAN_D2_TAREAS.md            el plan de implementación por tareas
corrida_final_colab.ipynb    notebook del baseline del D1
corrida_d2_colab.ipynb       notebook del D2: ablaciones, grilla y demo
```

### Reproducir

```bash
python scripts/verificador.py            # 9/9 casos de control
python scripts/generador.py              # regenera los 60 casos
python scripts/runner.py --modelo mistralai/Mistral-7B-Instruct-v0.3 --condicion zero_shot
python scripts/analisis.py resultados/*.raw.jsonl
```

La generación es determinista (`do_sample=False`); la corrida se reprodujo idéntica al
repetirla tras perder la sesión de Colab.

> **Sobre `resultados/`.** Están las tres corridas de Mistral y las tres de Phi caso a caso,
> así que sus cifras se recalculan con `analisis.py`. Las de Phi se relanzaron el 17 de
> septiembre y reprodujeron las nueve cifras reportadas sin desviación, lo que confirma que el
> entorno declarado sigue siendo válido. Las de Qwen siguen sin crudo: se midieron en una
> sesión de Colab que expiró antes de la descarga. Sus métricas están completas en este README
> y los comandos de arriba las reproducen, porque la generación es determinista.

---

# Deliverable 2 · El sistema de tres pasos

## Qué hace

El baseline recibe 3.862 tokens de una vez y debe identificar el ramo, recorrer el grafo de
prerrequisitos, distinguir aprobada de inscrita, sumar créditos y aplicar un orden de
prioridad entre ocho reglas. No lo logra. El sistema parte ese trabajo en tres pasos y cada
uno recibe solo lo que necesita.

| paso | quién lo hace | qué ve | ataca |
|---|---|---|---|
| 1 · extracción | **el modelo** | la pregunta y los 61 pares de código y nombre | E2 |
| 2 · ficha | el código | el ramo, la malla y el historial | E1 |
| 3 · decisión | el código | la ficha y la lista cerrada de reglas | E3, E4 |

La ficha son ocho campos sobre un solo ramo. Como el historial trae 26 asignaturas en
promedio y el ramo objetivo tiene 1,2 prerrequisitos directos, el paso 2 descarta unas 25
asignaturas irrelevantes por caso.

## Resultados sobre los mismos 60 casos

| condición | decisión | regla | **ambas** | tok/caso | s/caso |
|---|---|---|---|---|---|
| baseline few-shot | 35,0 % | 23,3 % | 16,7 % | 3.862 | 4,2 |
| constante trivial | 35,0 % | 30,0 % | 30,0 % | — | — |
| ficha y reglas al modelo | 45,0 % | 25,0 % | 25,0 % | 6.072 | 10,4 |
| ficha al código | 45,0 % | 28,3 % | 28,3 % | 2.743 | 3,4 |
| **ficha y reglas al código** | **71,7 %** | **58,3 %** | **58,3 %** | **1.153** | **1,6** |
| *con el paso 1 resuelto* | 100,0 % | 100,0 % | 100,0 % | 1.153 | 1,6 |

El sistema triplica el baseline y es además la condición más barata, así que la mejora no
viene de gastar más cómputo.

**E3 y E4 quedan en cero** sobre las 240 respuestas donde el modelo decide. La lista cerrada
elimina los identificadores inventados, y derivar la decisión desde la regla elimina las
contradicciones. Se verificó sobre los 60 casos que la decisión queda determinada por la
regla, sin una sola ambigüedad, así que pedir los dos campos daba un grado de libertad que el
dominio no tiene.

## Dónde se rompe

| | |
|---|---|
| casos donde el paso 1 acierta ramo y período | **28 de 28** |
| casos donde el paso 1 falla | 7 de 32 |

Todo el error restante es extracción. El paso 1 identifica el ramo en 31 de 60 casos y se
degrada con la forma de nombrarlo: 13/20 con el nombre completo, 10/20 abreviado, 8/20
coloquial.

## Lo que muestra el video

Dos casos, los dos con el baseline visible sobre el mismo input.

**Caso 40.** Elegido por una regla escrita antes de medir: el primero de nivel 3 cuyo baseline
falla. El sistema también falla acá, y es el caso de falla que la guía exige. La pregunta es
*"programación, la reprobé, ¿puedo tomar Optimización 1 ahora ya?"*. El ramo consultado es
580315, pero el paso 1 devolvió 503203, que la frase menciona de contexto y que además es el
prerrequisito que bloquea. Los pasos 2 y 3 resolvieron con toda corrección la pregunta
equivocada.

**Caso 42.** Elegido para mostrar el sistema funcionando, y se declara así. La pregunta es
*"¿puedo tomar termodinámica cuando salga de esto?"*, el baseline cita el código del ramo y el
sistema acierta con `R-CREDITOS-MINIMOS`.

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
python scripts/demo.py --caso 40    # el caso del video, el que falla
python scripts/demo.py --caso 42    # el caso del video, el que funciona
python scripts/runner_d2.py --variante codigo --modo encadenado    # el sistema, 60 casos
python scripts/ablacion_p1.py       # el paso 1 con y sin ejemplos
python scripts/ablacion_p3.py       # el paso 3, cuatro versiones del prompt
```

`demo.py` imprime exactamente lo que se ve en el video: la pregunta, el baseline con su
veredicto, los tres pasos uno por uno y la comparación final. Las salidas caso a caso quedan
en `resultados/pipeline__*.raw.jsonl`, así que cualquier cifra de este README se recalcula
desde ahí.

## Decisiones, y por qué

**El modelo es Phi-3.5-mini**, el más chico de los tres candidatos del D1. Se eligió con un
criterio declarado antes de mirar los datos: acierto de decisión fuera de la categoría donde
cada modelo colapsa. Phi da 40,5 % y Mistral 19,0 %, con la mitad de los parámetros.

**Las reglas las aplica el código.** La ablación midió que el modelo las aplica al 31,7 % con
la ficha perfecta delante, y que el código lo hace al 100 %. Es uso de herramientas, una de
las intervenciones que la guía enumera.

**Hubo una revisión del prompt.** La primera corrida no mejoró al baseline porque el prompt
del paso 3 solo nombraba un desenlace. Las corridas fallidas están en
`resultados/corrida_1_prompt_v1/` y `corrida_2_prompt_v2/`, y no se borran. El detalle está en
[`PLAN_D2.md`](PLAN_D2.md).

**Límites declarados.** En los 12 casos con prerrequisito en curso preguntando por el próximo
período el sistema baja de 6/12 a 3/12: el baseline acertaba ahí apostando a `condicional`,
no razonando. Los 9 casos de `R-EXCEPCION-PRERREQ` tienen todos cero créditos inscritos, así
que el conjunto no prueba la frontera de esa regla. Y las versiones del prompt se eligieron
por ablación sobre estos mismos 60 casos, así que diferencias de dos a cuatro casos no deben
leerse como efectos firmes.

---

## El proyecto completo

| Entregable | Fecha | Contenido | Estado |
|---|---|---|---|
| **D1** | 31 ago | Tarea, modelo y baseline | ✅ |
| **D2** | 30 sep | Sistema de tres pasos — 16,7 % → 58,3 % | ✅ |
| D3 | 31 oct | La extracción: emparejar prosa con códigos, y el validador | ⏳ |
| D4 | 30 nov | Resultados contra este baseline | ⏳ |

El D1 reservaba la consulta al grafo para el D3. Se adelantó al D2 porque la ablación mostró
que el modelo no aplica las reglas, y la desviación queda declarada. El D3 pasa a atacar el
cuello de botella medido, que es el paso 1: emparejar *"me falta cálculo 2"* con el código
`527150`. Es el problema de los embeddings del Workshop 1.
