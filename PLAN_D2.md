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

Entra el código del ramo, la malla y el historial. Sale una ficha de ocho campos.

```
ramo objetivo:         525223  Ecuaciones Diferenciales
estado actual:         no cursada
créditos del ramo:     5
prerrequisitos:        525150  Álgebra II       aprobada
                       527150  Cálculo II       inscrita
créditos aprobados:    118   (contados para el período consultado)
umbral del ramo:       ninguno
requisitos especiales: ninguno
créditos ya inscritos: 12
créditos del semestre: 17  (12 ya inscritos + 5 de este ramo)
```

Ataca el mecanismo E1, la falta de representación del estado "cursándola ahora". La ficha obliga a
nombrar ese estado como campo propio.

El historial trae 26 asignaturas en promedio y el ramo objetivo tiene 1,2 prerrequisitos directos.
El paso 2 descarta unas 25 asignaturas irrelevantes por caso. Entre ellas están los distractores
que el generador puso a propósito: 38 casos traen un ramo reprobado que no bloquea nada y 19 traen
uno inscrito que tampoco.

Los ocho campos cubren las seis ramas del verificador. El octavo, `creditos_semestre`, se agregó
al implementar: dos ramas comparan contra el total del semestre y la ficha solo daba los sumandos,
lo que obligaba al modelo a una suma que no acierta. Una versión anterior de este diseño
entregaba solo los prerrequisitos y su estado, lo que dejaba sin resolver los 3 casos de umbral de
créditos, los 3 de requisito especial y los 3 de tope máximo. Además habría respondido `sí` a esos
9 casos por no poder descartarlos, que es la misma patología de Mistral con más pasos.

Los créditos aprobados se cuentan distinto según el período. Para el semestre actual cuenta lo
aprobado. Para el próximo cuenta lo aprobado más lo que está cursando. Es el mecanismo E1 en forma
aritmética.

### Paso 3 — Decisión

Entra la ficha y la lista cerrada de identificadores válidos. Sale `{regla}`, y la decisión se
deriva de esa regla.

Ataca E3 y E4. La lista cerrada elimina los identificadores inventados. Derivar la decisión en vez
de pedirla elimina las contradicciones entre decisión y regla.

> **Nota del 20 de septiembre.** Dos cosas cambiaron acá al medir. El bloque de reglas globales
> salió del prompt, porque dictaba la respuesta por su posición. Y la decisión dejó de pedirse:
> queda determinada por la regla en los 60 casos, sin ambigüedad.

La lista cerrada incluye explícitamente los códigos de los prerrequisitos del caso. Sin eso el
sistema queda estructuralmente incapaz de responder los 12 casos cuya respuesta es un código de
ramo, que es el 20 % del conjunto.

---

## Las variantes

> **Nota del 20 de septiembre.** Esta sección describe el diseño como estaba el 17 de
> septiembre, con dos variantes. Después de la segunda corrida se agregó una tercera, `codigo`,
> y es la que se entrega. El detalle está en
> [La segunda revisión y el sistema que se entrega](#la-segunda-revisión-y-el-sistema-que-se-entrega).

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

## La primera corrida y la revisión del prompt

La primera corrida de la grilla, el 17 de septiembre, no mejoró al baseline. Las cuatro
condiciones dieron 15,0 % a 16,7 % de acierto conjunto contra 16,7 % del baseline, y las cuatro
dieron exactamente 35,0 % de acierto de decisión. Ese número idéntico era el síntoma: el paso 3
respondió `condicional` en los 60 casos de las cuatro corridas, y 21 de los 60 casos son
`condicional`.

La causa fue un error del prompt del paso 3. Ese prompt explicaba dos veces cuándo la respuesta
es `condicional` y no decía en ninguna parte cuándo es `sí` o `no`. El único desenlace que
nombraba era `condicional`. El prompt del baseline sí enumera las ocho reglas con su condición de
disparo, y esa enumeración se había omitido al escribir el paso 3, suponiendo que la ficha la
hacía evidente.

Se hicieron tres cambios. El criterio para cada uno fue la **paridad con el baseline**: la
intervención debe cambiar cómo se reparte el trabajo, no quitarle al pipeline información que el
baseline sí tenía.

1. **El paso 3 recupera la enumeración completa**, escrita como un procedimiento ordenado de ocho
   condiciones. El baseline entrega la misma información como ocho definiciones más una línea de
   prioridad. El contenido es el mismo y el formato cambia, y ese cambio de formato es parte de
   la intervención declarada, que la rúbrica admite como estructura de prompt.
2. **Los pasos 1 y 3 reciben ejemplos resueltos.** El baseline de comparación es la condición
   few-shot, con tres ejemplos. Los pasos del pipeline eran zero-shot, así que la comparación
   enfrentaba un baseline mejor asistido y parte de la diferencia venía de los ejemplos y no de
   la descomposición. Los ejemplos usan ramos que no son objetivo de ningún caso del conjunto de
   prueba, verificado por código.
3. **La ficha gana el campo `creditos_semestre`.** Dos ramas del verificador comparan contra el
   total de créditos del semestre, y la ficha solo entregaba los sumandos. El modelo tenía que
   sumar y después comparar contra 24 y contra 8. El total se calcula a partir de dos datos de
   entrada, igual que ya se hacía con los créditos del ramo, y no es un juicio sobre el
   expediente.

**El paso 2 no se tocó y sigue zero-shot.** Su problema no es de formato: produjo JSON legible en
el 100 % de los casos. Su problema es que no puede hacer las búsquedas ni la aritmética, y los
ejemplos no arreglan eso. La asimetría queda declarada.

Los cambios subieron el costo de contexto, que es el precio de la paridad:

| | antes de la revisión | después |
|---|---|---|
| pipeline `puro` | 1,46× el baseline | 1,79× |
| pipeline `retrieval` | 0,60× | 0,92× |

La primera corrida queda en el repositorio y sus cifras se reportan. Hubo una sola revisión del
prompt, y está descrita acá.

---

## La segunda revisión y el sistema que se entrega

La segunda corrida tampoco mejoró al baseline. El paso 3 citó `R-EXCEPCION-PRERREQ` en los 60
casos, incluso en el modo oráculo, donde recibe la ficha perfecta y tiene el procedimiento de
ocho condiciones delante. Ese identificador no aparece en ninguno de los tres ejemplos, así que
no vino de ahí.

Diagnosticar mal dos veces seguidas costó dos corridas de veinticinco minutos, así que la tercera
vez se midió. `ablacion_p3.py` corre solo el paso 3, con la ficha verdadera de cada caso, bajo
cuatro versiones del prompt. Son 60 llamadas cortas por versión.

| versión del prompt del paso 3 | acierto conjunto | regla dominante |
|---|---|---|
| completo | 26,7 % | `R-EXCEPCION-PRERREQ` 38 |
| **sin el bloque de reglas** | **31,7 %** | `R-DEPENDE-APROBACION` 49 |
| sin ejemplos | 15,0 % | `R-EXCEPCION-PRERREQ` 60 |
| mínimo | 30,0 % | `R-DEPENDE-APROBACION` 47 |

El bloque de reglas globales dictaba la respuesta por su posición. Era la última prosa que el
modelo leía antes de responder, y la única de todo el mensaje de usuario que nombraba un valor de
decisión. Además era redundante, porque el procedimiento ya traía los umbrales y
`creditos_semestre` ya incorporaba la regla de las prácticas.

Pero el colapso no se rompió. Con la ficha perfecta delante, la mejor versión aplica las reglas al
31,7 % y `decidir_desde_ficha` lo hace al 100 %.

### Los tres cambios

1. **El paso 3 deja de recibir el bloque de reglas.** Medido: vale 5 puntos.
2. **El paso 3 pide solo la regla y la decisión se deriva.** Se verificó sobre los 60 casos que
   ninguna de las ocho reglas admite más de una decisión, así que pedir los dos campos daba un
   grado de libertad que el dominio no tiene. Con él venía la posibilidad de citar una regla que
   bloquea junto a un `sí`, que es el mecanismo E4 del D1. Queda eliminado por construcción, igual
   que la lista cerrada eliminó E3.
3. **El paso 1 deja de recibir ejemplos.** `ablacion_p1.py` midió que bajan el acierto de ramo de
   51,7 % a 45,0 %. Aplanan el comportamiento: con ejemplos el acierto queda en 9/20 para las tres
   formas de nombrar el ramo, y sin ellos el nombre completo sube a 13/20.

### La tercera variante

La ablación mostró que el modelo no aplica las reglas y que el código sí. Se agregó la variante
`codigo`, donde el código arma la ficha y también decide. Es uso de herramientas, una de las
intervenciones que la guía enumera.

Las tres variantes forman una escalera que mueve una pieza por vez del modelo al código, así que
la diferencia entre dos filas mide lo que esa pieza aporta.

| | paso 2, la ficha | paso 3, la decisión | acierto conjunto | tokens |
|---|---|---|---|---|
| baseline few-shot | | | 16,7 % | 3.862 |
| `puro` | el modelo | el modelo | 25,0 % | 6.072 |
| `retrieval` | el código | el modelo | 28,3 % | 2.743 |
| **`codigo`** | el código | el código | **58,3 %** | **1.153** |

Mover la ficha al código vale 3,3 puntos. Mover la aplicación de reglas vale 30. El sistema que se
entrega es `codigo`, y es además el más barato de los cuatro.

En modo oráculo, `codigo` acierta 60 de 60. El sistema encadenado acierta 28 de 28 cuando el paso
1 identifica bien ramo y período, y 7 de 32 cuando no. Todo el error restante es extracción.

---

## Limitaciones declaradas

**Filtración en los casos de excepción.** Los 9 casos cuya respuesta es `R-EXCEPCION-PRERREQ`
tienen todos `creditos_ya_inscritos = 0`, y los otros 51 tienen entre 12 y 24. El umbral de la
regla es 8. Un sistema que detecte el cero acierta los 9 sin comparar contra el umbral. El conjunto
no prueba la frontera real de la regla, que está entre 1 y 7 créditos. Ambos modelos aciertan 0 de
9 hoy, así que la mejora sigue siendo real, pero mide si el modelo nota un cero y no si aplica un
umbral.

**La comparación no es de igual a igual, y el costo se mide distinto en cada variante.** El
pipeline hace más de una llamada al modelo y el baseline hace una. Medido en caracteres de prompt
sobre los 60 casos, antes de correr nada:

| | llamadas | caracteres por caso | contra el baseline |
|---|---|---|---|
| baseline few-shot | 1 | 8.130 | |
| pipeline `puro` | 3 | 11.873 | 1,46× |
| pipeline `retrieval` | 2 | 4.849 | 0,60× |

La variante `puro` cuesta 46 % más contexto que el baseline, porque su paso 2 necesita la malla
completa y el historial completo para que el modelo sume los créditos. Si esa variante mejora el
acierto, parte de la mejora se explica por más cómputo y hay que decirlo.

La variante `retrieval` cuesta 40 % menos contexto que el baseline, porque su paso 2 no llama al
modelo. Si esa variante mejora el acierto, lo hace siendo además más barata.

Una versión anterior de este documento afirmaba que el pipeline probablemente saldría más barato.
Esa afirmación resultó falsa para `puro` al medirla, y queda corregida acá. Los tokens y segundos
reales se miden en la corrida y se reportan en el documento.

**El rebalanceo por regla se posterga.** El D1 declaró que balancear sobre la regla y no sobre la
decisión era trabajo del D2. Rebalancear rompe la comparabilidad con el baseline, y la rúbrica
exige comparar sobre los mismos inputs. El rebalanceo se mueve al D3 y la desviación queda
declarada acá.

**Un solo dominio y 60 casos.** Sin cambios respecto al D1.

---

## Calendario

El trabajo con riesgo se cerró el 20 de septiembre, cuatro días antes de la fecha tope que este
plan se había puesto, y diez días antes de la entrega.

| Paso | Qué | Estado |
|---|---|---|
| 0 | Reponer el baseline de Phi y verificar el entorno | ✅ 17 sep |
| 1 | Contrato de los tres pasos | ✅ 17 sep, este documento |
| 2 | Implementar `ficha.py`, `pipeline.py`, `runner_d2.py` | ✅ 17 sep |
| 3 | Correr la grilla: 3 variantes × 2 modos × 60 casos | ✅ 20 sep |
| 4 | Atribución de errores por paso y elección de variante | ✅ 20 sep |
| 5 | `demo.py` para el video | ✅ 20 sep |
| 6 | Documento LaTeX de una página con el diagrama | ✅ 20 sep |
| 7 | Video y README | README ✅ · video ⏳ |

**Línea de corte si algo se atrasa.** Se sacrifica la variante `retrieval` y se conserva la
medición por paso. La medición por paso sostiene el criterio de lectura de los límites, que vale 10
puntos.

> **Nota del 20 de septiembre.** Esta línea de corte no se usó, y de haberse usado habría sido un
> error. Las variantes resultaron ser la escalera que mide cuánto aporta mover cada pieza al
> código, que es el argumento central del entregable. Ninguna sobraba.

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

**20 sep 2026 — El sistema que se entrega es `codigo`.** La ablación del paso 3 midió que el
modelo aplica las reglas al 31,7 % con la ficha perfecta delante y que el código lo hace al 100 %.
Se movieron las reglas al código. Es uso de herramientas, una de las intervenciones que la guía
enumera, y la desviación del plan del D1 queda declarada en el documento técnico.

**20 sep 2026 — El paso 3 pide solo la regla.** La decisión queda determinada por la regla en los
60 casos, sin ambigüedad, así que pedir los dos campos daba un grado de libertad inexistente. E4
queda eliminado por construcción.

**20 sep 2026 — El paso 1 va sin ejemplos.** Medido por ablación: 51,7 % de acierto de ramo sin
ellos contra 45,0 % con ellos.

**17 sep 2026 — El paso 2 entrega ficha completa.** La primera versión del contrato entregaba solo
prerrequisitos y dejaba 9 casos sin resolver y 18 respondidos por suerte. Corregido antes de
implementar.
