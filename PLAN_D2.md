# Diseño — Deliverable 2

**Vence:** martes 30 de septiembre de 2026, 23:59 · Canvas
**Vale:** 20% del proyecto semestral (70% de la nota final) → 14% de la nota final
**Equipo:** Joaquín Sepúlveda · Renato Saavedra · Lucas Saldivia
**Escrito:** 17 de septiembre de 2026

---

## Qué pide la entrega

El D1 definió la tarea y diagnosticó por qué un modelo abierto pequeño falla cuando se le
pregunta directo. El D2 convierte ese diagnóstico en un sistema que corre.

| Requisito | Cómo se cumple |
|---|---|
| Compromiso de modelo | Phi-3.5-mini, elegido con la evidencia de la sección siguiente |
| Una intervención | Descomposición en tres pasos con contexto enfocado y salida restringida |
| Comparación con baseline | Los mismos 60 casos, contra la condición few-shot del D1 |
| Sistema funcionando | Corre de punta a punta en la T4 gratuita de Colab, el hardware del D1 |
| Caso de falla | Se identifica con la atribución de errores por paso |

Entregables: video de hasta 3 minutos, PDF de una página compilado en LaTeX con diagrama del
pipeline, y el repositorio con instrucciones que reproduzcan lo que muestra el video.

---

## La elección de modelo

Se mide el acierto de decisión **fuera de la categoría donde cada modelo colapsa**. Esa métrica
descuenta el premio de apostar siempre a la misma respuesta.

| Modelo | Params | Condición | Acierto de decisión fuera de su colapso |
|---|---|---|---|
| **Phi-3.5-mini** | **3,8 B** | few-shot | **40,5 %** (17/42) |
| Phi-3.5-mini | 3,8 B | zero-shot | 30,8 % (12/39) |
| Mistral-7B-v0.3 | 7,2 B | few-shot | 19,0 % (8/42) |
| Mistral-7B-v0.3 | 7,2 B | zero-shot | 16,7 % (7/42) |

Phi razona más del doble que Mistral con la mitad de los parámetros. Cuatro hechos lo respaldan.

1. Phi reparte sus respuestas. Con few-shot predice 23 `sí`, 22 `no` y 14 `condicional`, contra
   los 18/21/21 correctos. La fila suma 59 porque una salida no devolvió JSON legible. Mistral
   predice 50/6/4 en zero-shot y 50/8/2 en few-shot.
2. Phi cita códigos de ramo. Doce casos exigen nombrar el prerrequisito que bloquea. Phi lo
   intenta 18 veces con few-shot. Mistral lo hizo una vez en 180 respuestas.
3. Phi ya es mejor donde apunta esta entrega. En los 12 casos donde el prerrequisito está en
   curso y se pregunta por el próximo período, que son el mecanismo E1 del D1, Phi acierta 6 y
   Mistral 2.
4. La falla dominante de Phi es la barata. Sus identificadores inventados caen de 18 a 3 solo con
   los ejemplos, y la salida restringida elimina los 3 restantes sin que el modelo mejore.

Qwen2.5-7B queda descartado por ser el más grande de los tres y peor que Mistral en la métrica
conjunta del D1.

**El riesgo asumido.** El acierto conjunto absoluto de Phi es 16,7 %, bajo el piso trivial de
30 %. Está bajo el piso porque no toma la apuesta gratis de responder siempre `sí`, que es lo que
pone a Mistral por encima. Para construir un sistema que razone, ese es mejor punto de partida.

El criterio de selección se declaró por escrito antes de mirar los datos recuperados.

---

## Reproducibilidad del entorno

Las tres condiciones de Phi se relanzaron el 17 de septiembre con el mismo paquete que produjo
los números del D1, verificado idéntico byte a byte contra los scripts del repositorio. Las nueve
cifras reproducen sin desviación. El entorno declarado en el D1 sigue siendo válido.

---

## El diseño

El baseline recibe 3.900 tokens por caso: la malla completa de 61 asignaturas, las reglas, el
historial de 26 asignaturas y la pregunta. Con eso debe identificar el ramo, recorrer el grafo,
cruzar cada prerrequisito contra el historial, distinguir aprobada de inscrita, sumar créditos y
aplicar un orden de prioridad entre ocho reglas. Todo en una sola pasada.

La intervención parte el trabajo en tres pasos. Cada paso recibe solo lo que necesita.

### Paso 1 — Extracción

Entra la pregunta en prosa y los 61 pares de código y nombre. Sale el par `{ramo, periodo}`.

Ataca el mecanismo E2 del D1, la dependencia de que la pregunta apunte al dato. El ramo se nombra
de tres formas distintas en el conjunto de prueba, veinte casos cada una: nombre completo, nombre
abreviado y forma coloquial.

### Paso 2 — Ficha del caso

Entra el código del ramo, la malla y el historial. Sale una ficha de siete campos.

```
ramo objetivo:         525223  Ecuaciones Diferenciales
estado actual:         no cursada
créditos del ramo:     5
prerrequisitos:        525150  Álgebra II       aprobada
                       527150  Cálculo II       inscrita
créditos aprobados:    118   (contados para el período consultado)
umbral del ramo:       ninguno
requisitos especiales: ninguno
```

Ataca el mecanismo E1, la falta de representación del estado "cursándola ahora". La ficha obliga a
nombrar ese estado como campo propio.

El historial trae 26 asignaturas en promedio y el ramo objetivo tiene 1,2 prerrequisitos directos.
El paso 2 descarta unas 25 asignaturas irrelevantes por caso. Entre ellas están los distractores
que el generador puso a propósito: 38 casos traen un ramo reprobado que no bloquea nada y 19 traen
uno inscrito que tampoco.

Los siete campos cubren las seis ramas del verificador. Una versión anterior de este diseño
entregaba solo los prerrequisitos y su estado, lo que dejaba sin resolver los 3 casos de umbral de
créditos, los 3 de requisito especial y los 3 de tope máximo. Además habría respondido `sí` a esos
9 casos por no poder descartarlos, que es la misma patología de Mistral con más pasos.

Los créditos aprobados se cuentan distinto según el período. Para el semestre actual cuenta lo
aprobado. Para el próximo cuenta lo aprobado más lo que está cursando. Es el mecanismo E1 en forma
aritmética.

### Paso 3 — Decisión

Entra la ficha, los créditos ya inscritos, las reglas globales y la lista cerrada de
identificadores válidos. Sale `{decision, regla}`.

Ataca E3 y E4. La lista cerrada elimina los identificadores inventados y las contradicciones entre
decisión y regla.

La lista cerrada incluye explícitamente los códigos de los prerrequisitos del caso. Sin eso el
sistema queda estructuralmente incapaz de responder los 12 casos cuya respuesta es un código de
ramo, que es el 20 % del conjunto.

---

## Las dos variantes

Las variantes se diferencian solo en quién resuelve el paso 2.

| Variante | Quién arma la ficha | Qué mide |
|---|---|---|
| `puro` | el modelo, leyendo la malla y el historial | hasta dónde llega el prompt solo |
| `retrieval` | una función determinista sobre `malla.json` | cuánto agrega quitarle el trabajo mecánico |

La diferencia entre las dos columnas cuantifica lo que el harness del D3 puede aportar. El plan del
D1 reservaba la consulta al grafo para el D3, y esta variante la adelanta como medición y no como
sistema final. La decisión queda declarada acá.

La variante `retrieval` usa la misma función que genera el ground truth del paso 2, así que su
paso 2 es correcto por construcción. Es una ablación, y se declara como tal en el documento.

---

## Medición

Cada paso tiene ground truth propio.

| Paso | Se compara contra | Qué mide |
|---|---|---|
| 1 | `consulta.ramos[0]` y `consulta.periodo` | si entendió la pregunta |
| 2 | la ficha determinista, campo por campo | si leyó bien el expediente |
| 3 | `respuesta` | si aplicó bien las reglas |

El paso 2 se mide campo por campo. Eso separa el caso en que la ficha entera salió mal del caso en
que los prerrequisitos salieron bien y falló solo la suma de créditos.

Cada variante se corre en dos modos.

- **Encadenado.** Cada paso recibe la salida real del anterior. Esto es el sistema, y es lo que se
  compara contra el baseline.
- **Oráculo.** Cada paso recibe el ground truth del anterior. Esto es la competencia de cada paso
  por separado.

La diferencia entre ambos modos es el costo de la propagación de errores, con un número. Es lo que
permite escribir dónde se rompe el sistema, que es lo que pide el criterio de lectura de los
límites.

**El baseline de comparación es la condición few-shot con pregunta en prosa** (35,0 / 23,3 / 16,7).
Es la más fuerte de las tres del D1. Comparar contra la más débil inflaría la mejora.

---

## Lo que se congela

`prompt.py`, `runner.py`, `verificador.py`, `generador.py`, `malla.json` y `casos.jsonl` no se
tocan. Si cambian, los números del D1 dejan de ser comparables y se cae el criterio de continuidad.
Todo lo nuevo vive en archivos nuevos.

Eso incluye el identificador `R-TOPE-MIN` que el prompt del baseline ofrece sin que sea nunca la
respuesta correcta. Se verificó que es inerte: Mistral no lo emitió ninguna vez en 180 respuestas y
no es la respuesta correcta en ninguno de los 60 casos. El baseline lo conserva y el pipeline no lo
incluye.

---

## Archivos nuevos

| Archivo | Qué hace |
|---|---|
| `scripts/ficha.py` | construye la ficha determinista de un caso |
| `scripts/pipeline.py` | los tres pasos: prompts, parsers y el encadenado |
| `scripts/runner_d2.py` | corre los 60 casos, con flags de variante y modo |
| `scripts/analisis_d2.py` | atribución de errores por paso |
| `scripts/demo.py` | un caso, baseline y pipeline lado a lado, para el video |

Los resultados salen a `resultados/pipeline__<modelo>__<variante>__<modo>.raw.jsonl`, con la salida
de los tres pasos guardada caso a caso. El segundo criterio de la rúbrica da cero a las salidas que
no se puedan rastrear al repositorio, así que lo que se vea en el video tiene que estar en un
archivo versionado.

---

## Limitaciones declaradas

**Filtración en los casos de excepción.** Los 9 casos cuya respuesta es `R-EXCEPCION-PRERREQ`
tienen todos `creditos_ya_inscritos = 0`, y los otros 51 tienen entre 12 y 24. El umbral de la
regla es 8. Un sistema que detecte el cero acierta los 9 sin comparar contra el umbral. El conjunto
no prueba la frontera real de la regla, que está entre 1 y 7 créditos. Ambos modelos aciertan 0 de
9 hoy, así que la mejora sigue siendo real, pero mide si el modelo nota un cero y no si aplica un
umbral.

**La comparación no es de igual a igual.** El pipeline hace tres llamadas al modelo y el baseline
hace una. Hay que medir tokens y segundos en ambos y reportarlo. Si el pipeline resulta más barato
en tokens totales, lo que es probable porque el baseline mete 3.900 de contexto por caso, el
argumento queda cerrado con datos.

**El rebalanceo por regla se posterga.** El D1 declaró que balancear sobre la regla y no sobre la
decisión era trabajo del D2. Rebalancear rompe la comparabilidad con el baseline, y la rúbrica
exige comparar sobre los mismos inputs. El rebalanceo se mueve al D3 y la desviación queda
declarada acá.

**Un solo dominio y 60 casos.** Sin cambios respecto al D1.

---

## Calendario

Quedan 13 días y el Certamen 1 es el 9 de octubre, así que el trabajo con riesgo debe cerrarse
antes del 24 de septiembre.

| Paso | Qué | Estado |
|---|---|---|
| 0 | Reponer el baseline de Phi y verificar el entorno | ✅ 17 sep |
| 1 | Contrato de los tres pasos | ✅ 17 sep, este documento |
| 2 | Implementar `ficha.py`, `pipeline.py`, `runner_d2.py` | |
| 3 | Correr la grilla: 2 variantes × 2 modos × 60 casos | |
| 4 | Atribución de errores por paso y elección de variante | |
| 5 | `demo.py` para el video | |
| 6 | Documento LaTeX de una página con el diagrama | |
| 7 | Video y README | |

**Línea de corte si algo se atrasa.** Se sacrifica la variante `retrieval` y se conserva la
medición por paso. La medición por paso sostiene el criterio de lectura de los límites, que vale 10
puntos. La segunda variante es una columna más en la tabla.

---

## Registro de decisiones

**17 sep 2026 — Modelo.** Phi-3.5-mini sobre Mistral-7B y Qwen2.5-7B. Criterio declarado antes de
mirar los datos recuperados: acierto de decisión fuera de la categoría de colapso. Phi 40,5 %
contra 19,0 % de Mistral, con la mitad de los parámetros. Gana además el criterio de economía de
modelo, que vale 10 puntos.

**17 sep 2026 — Intervención.** Descomposición en tres pasos con contexto enfocado y salida
restringida, por sobre prompt plano mejorado o fine-tuning. La razón decisiva es que la
descomposición da ground truth por paso, y eso convierte la afirmación de que el sistema falla en
la afirmación de que el sistema falla en el paso 2 por la suma de créditos, que es lo que pide el
criterio de lectura de los límites.

**17 sep 2026 — Baseline de comparación.** La condición few-shot con pregunta en prosa, que es la
más fuerte del D1.

**17 sep 2026 — El paso 2 entrega ficha completa.** La primera versión del contrato entregaba solo
prerrequisitos y dejaba 9 casos sin resolver y 18 respondidos por suerte. Corregido antes de
implementar.
