# Diseño — Deliverable 3

**Vence:** viernes 31 de octubre de 2026, 23:59 · Canvas
**Vale:** 30% del proyecto semestral
**Equipo:** Joaquín Sepúlveda · Renato Saavedra · Lucas Saldivia
**Escrito:** 19 de octubre de 2026
**Enunciado:** `poster/Deliverable 3 (1).pdf`

---

## Qué pide la entrega

Reconstruir el sistema del D2 como un sistema de agentes y mostrar qué técnicas de prompting
dentro de cada agente explican la mejora. El enunciado define agente como una llamada al modelo
con rol, prompt propio, entrada y salida definidas, **que decide qué pasa después**: llamar una
herramienta, pasar el trabajo a otro agente, revisar su salida o detenerse. Una secuencia fija
de prompts sin decisiones es un pipeline y no califica.

| Requisito | Cómo se cumple |
|---|---|
| Al menos 3 agentes con roles distintos | Intérprete, Resolvedor y Verificador (sección "La arquitectura") |
| Por agente: rol, prompt, herramientas, formato de entrada y salida, condición de parada | Tabla de cada agente y `prompts/*.md` |
| Mismo modelo open-weight de 8B o menos en todos | Phi-3.5-mini (3,8B) en los tres; las herramientas son código sin modelo |
| Técnicas por agente, con ablación de a una | Cuatro ablaciones, cada una ligada a un mecanismo medido |
| Baseline, D2, agentes y ablaciones sobre los mismos casos | Tres conjuntos de prueba, todas las filas sobre los tres |
| Trazas de los mensajes entre agentes | Un JSONL por corrida, un registro por mensaje; las del video y la falla en el repo |
| Prompt de cada agente en archivo versionado, fuera del código | `prompts/`, y cada traza guarda el hash del prompt usado |
| Video de hasta 3 min, PDF de una página en LaTeX, repo reproducible | Secciones "Video" y "Documento" |

Rúbrica: seis criterios de 10 puntos (continuidad, grafo, diseño de agentes, técnicas,
evidencia, repositorio). La sección "Cobertura de la rúbrica" cruza cada uno con este plan.

---

## Punto de partida: qué falla en el sistema del D2

En el sistema del D2 el modelo solo hace el paso 1 (ramo y período), y con eso correcto el
código acierta 28 de 28. Todo el error está en la extracción. El D2 lo resumió en 31/60 de ramo
y en 3/20 cuando la pregunta nombra otro ramo antes. Separar los errores por mecanismo cambia
el diagnóstico. Cifras de `scripts/diagnostico_d3.py`, que lee las salidas guardadas del D2:

| Phi, 60 originales | acierta ramo |
|---|---|
| la pregunta trae el **nombre exacto** del catálogo | **18 de 34** |
| la pregunta lo abrevia o lo dice coloquial | 11 de 17 |
| la forma usada corresponde a más de un ramo | 2 de 9 |
| la pregunta menciona otro ramo antes | 3 de 20 |
| la pregunta solo nombra el consultado | 28 de 40 |
| período | 55 de 60 (50 de 60 en los nuevos) |

Tres mecanismos, en orden de peso:

- **M1. Copiar el código.** Con el nombre exacto delante, Phi falla 16 de 34. Tiene que copiar
  un código de seis dígitos desde una lista de 61 líneas y devuelve otro (Marketing → 580414,
  Tecnologías de la Información → Multivariado en los cuatro casos que la preguntan). T1, la
  búsqueda léxica de `herramientas.py`, recibiendo la mención ya aislada pone el ramo correcto
  primero en 50 de 51 casos no ambiguos (53 de 54 en los nuevos). El único que no encuentra es
  la sigla "PCP". No usa el diccionario de abreviaciones del generador. Consecuencia para el
  diseño: en los casos de plantilla el Resolvedor casi no tiene trabajo, y su aporte se juega
  en siglas y abreviaciones, que el conjunto redactado fuera de las plantillas va a traer más. La fila "B
  reemplazado por el top-1 de T1" lo mide.
- **M2. Aislar la mención.** Cuando la pregunta nombra un prerrequisito antes del ramo
  consultado, Phi acierta 3 de 20. A veces devuelve el prerrequisito y a veces un tercero.
- **M3. El período.** "el que viene", "de una vez" y "cuando salga de esto" fallan 5 veces en
  los originales y 10 en los nuevos.

**Casos sin solución desde la pregunta.** En 9 de los 60 originales y 6 de los 60 nuevos el
generador nombra el ramo con una forma que sirve para varios: "gestión" (3 ramos), "electiva"
(6), "la I" sola (6), "mecánica" (2), "complementaria" (2). Ningún sistema que lea solo la
pregunta los resuelve con seguridad. El techo real está bajo 100 % y se declara.

**Las preguntas salen de plantillas.** Siete aperturas, seis verbos, una lista fija de frases
de período, y preguntas repetidas (la de Tecnologías de la Información aparece cuatro veces; 7
preguntas idénticas entre originales y nuevos). Ajustar los prompts mirando estos casos puede
ajustarlos a las plantillas. Por eso se agrega un conjunto redactado fuera de las plantillas (sección "Conjuntos").

---

## Decisiones tomadas en esta revisión

**Modelo: Phi-3.5-mini.** El PDF del D2 dice que la brecha con Qwen en extracción (31 contra 41)
"es la que el Deliverable 3 tiene que cerrar con Phi". Cambiar de modelo contradiría lo
entregado y mezclaría el efecto del modelo con el de los agentes.

**Búsqueda léxica, sin embeddings.** El enunciado exige el mismo modelo en todo el sistema que
corre. Un modelo de embeddings en la herramienta sería un segundo modelo. El diagnóstico muestra
que no hace falta (top-1 en 50 de 51). La Lecture 6 da la regla de poner la base entera en el
prompt bajo 200.000 tokens, y el catálogo tiene unos 1.000, así que la herramienta no se
justifica por tamaño. Se justifica por M1: el modelo copia mal códigos de una lista.

**Sin T3 (desempate por historial).** Se evaluó una tercera herramienta que consultara el estado
de un ramo en el historial para descartar candidatos ya aprobados ("mecánica" con Mecánica
aprobada es Mecánica de Fluidos). Se descarta por cuatro razones. Resuelve 3 de 9 ambiguos en
los originales y 2 de 6 en los nuevos, como mucho 5 de 120. Obliga a que la lectura de la
pregunta toque el historial, que el D2 aisló a propósito. Funciona siempre en nuestros datos
porque el generador nunca pregunta por un ramo aprobado, y eso se puede leer como aprovechar la
construcción del conjunto. Y agrega un nodo cuyo aporte quedaría bajo el ruido de 60 casos. Los
ambiguos se declaran y se reporta el acierto con y sin ellos.

---

## La arquitectura

```
pregunta ─▶ A. INTÉRPRETE ─[mención consultada]─▶ T1 buscar_ramo ─[top-5]─▶ B. RESOLVEDOR
              ▲   │                                       ▲                    │
              │   └─ sin_ramo: FIN                        └──[nueva consulta]──┤ buscar (máx. 2)
              │                                                                │ elegir
              │                          [código, nombre, período, otras menciones]
              │                                                                ▼
              └───────[rechazo: ramo|período + motivo] (máx. 2)──── C. VERIFICADOR
                                                                               │ aceptar
                                                                               ▼
                                                     T2 motor de reglas (D2) ─▶ decisión + regla: FIN
```

Cada agente escribe su decisión en el campo `accion` de un JSON. El orquestador es código y solo
ejecuta esa acción. Una salida que no es JSON legible tiene una acción por defecto declarada, y
la traza la registra como tal.

### A. Intérprete

| | |
|---|---|
| Rol | Leer la pregunta en prosa. Es lo único que el código no puede hacer. |
| Ataca | M2 (aislar la mención) y M3 (período) |
| Recibe | La pregunta. Si viene de un rechazo, además la elección rechazada y el motivo. No ve catálogo, historial ni reglas. |
| Devuelve | `{"accion": "entregar", "consultado": "<texto tal como aparece>", "otros": ["..."], "periodo": "actual"|"proximo"}` o `{"accion": "sin_ramo"}` |
| Herramientas | Ninguna |
| Decide | Si encuentra un ramo consultado (entrega) o no (se detiene). Ante un rechazo, revisa su salida. |
| Parada | `sin_ramo` termina el caso sin ramo, que cuenta como error. JSON ilegible = `sin_ramo`. |

### B. Resolvedor

| | |
|---|---|
| Rol | Pasar del texto de la mención a un código del catálogo. |
| Ataca | M1 (copiar el código) y las abreviaciones que el léxico no encuentra ("PCP") |
| Recibe | La mención consultada, las otras menciones y los cinco candidatos de T1 (código, nombre, puntaje). |
| Devuelve | `{"accion": "elegir", "codigo": "..."}`, `{"accion": "buscar", "consulta": "..."}` o `{"accion": "ninguno"}` |
| Herramientas | T1 |
| Decide | Elegir un candidato, buscar de nuevo con otra consulta (por ejemplo expandiendo una sigla) o declarar que ninguno calza. |
| Parada | Elegir pasa al Verificador. `ninguno`, o agotar las 2 búsquedas extra, devuelve el trabajo al Intérprete como rechazo. JSON ilegible = `ninguno`. Un código fuera de los candidatos se trata como `ninguno`. |

### C. Verificador

| | |
|---|---|
| Rol | Revisar la elección contra la pregunta original. Es el único agente que ve las dos juntas. Cumple lo que el D1 dejó para el D3: un validador de la salida. |
| Ataca | Los errores de M2 y M3 que pasan a A y B |
| Recibe | La pregunta, el código con su nombre, el período y las otras menciones. |
| Devuelve | `{"accion": "aceptar"}` o `{"accion": "rechazar", "problema": "ramo"|"periodo", "motivo": "..."}` |
| Herramientas | T2, solo al aceptar |
| Decide | Aceptar y llamar a T2, o devolver el trabajo al Intérprete. |
| Parada | Aceptar termina con la salida de T2. Tras 2 rechazos se acepta la última elección. JSON ilegible = aceptar, para no crear bucles con ruido; se cuenta aparte. |

### Herramientas

- **T1 `buscar_ramo(texto)`**: normaliza tildes, mayúsculas y números romanos, compara contra
  los 61 nombres y devuelve los cinco más parecidos con su puntaje. Sin modelo y sin el
  diccionario del generador. Se reporta su recall@5 por separado, como pide la Lecture 6 para
  evaluar la recuperación aparte de la respuesta.
- **T2 `motor_de_reglas(codigo, periodo)`**: `ficha.py` y `decision_de_regla` del D2, sin
  cambios. Es lo que hace que el D3 construya sobre el D2.

**Límite global:** 12 llamadas al modelo por caso. Al llegar, se acepta la última elección.

### Por qué esta división

Cada agente tiene un mecanismo medido y un contexto que los otros no ven: A no ve el catálogo y
no puede caer en M1, B no ve la pregunta completa y solo elige entre cinco, C no elige códigos.
Es la técnica de aislar contexto de la Lecture 5 (escribir, seleccionar, comprimir, aislar) y
la misma idea del D2 (cada paso recibe solo lo que
necesita).

Alternativas descartadas: varios extractores que votan (mismo rol, falla el criterio de
diseño), un agente que redacta la respuesta en prosa (el criterio no mide prosa), y un solo
agente ReAct con herramientas (no llega a tres agentes).

---

## Técnicas y ablación

Nombres de la Lecture 5. Cada técnica va ligada al mecanismo que ataca.

| Técnica | Agente | Mecanismo | Configuración sin ella |
|---|---|---|---|
| Descomposición con salida estructurada (todas las menciones, cada una con su papel) | A | M2 | A devuelve solo "el ramo consultado" |
| Uso de herramienta, estilo ReAct (buscar, observar, elegir o volver a buscar) | B | M1 | B recibe el catálogo completo y devuelve el código, como el paso 1 del D2 |
| Self-Refine (crítica y revisión) | C → A | M2, M3 | Sin Verificador: se acepta la primera elección |
| Few-shot con ejemplos positivos | A | M3 | A en zero-shot |

Una fila de diagnóstico más, que no es técnica: **B reemplazado por el top-1 de T1**. Mide si el
Resolvedor aporta sobre tomar el primer candidato. Si no aporta, se dice.

Los ejemplos del few-shot usan ramos que no son objetivo de ningún caso de prueba y redacciones
que no copian las plantillas. En el D2 los ejemplos empeoraron el paso 1 (45,0 contra 51,7 %).
Si vuelve a pasar, se reporta.

---

## Conjuntos

| Conjunto | Casos | Uso |
|---|---|---|
| Desarrollo | 52 (60 generados, semilla 20261020, menos 8 que repetían una pregunta de prueba) | El único que se mira al ajustar prompts |
| Originales | 60, `casos.jsonl` | Prueba. Los del D1 y el D2 |
| Nuevos | 60, `casos_nuevos.jsonl` | Prueba. Los del 30 de septiembre |
| Redactados | 30, `casos_redactados.jsonl` | Prueba. Las plantillas fuera |

**Redactados fuera de las plantillas.** `scripts/preparar_redactados.py elegir` eligió 30 de
los originales (10 por nivel, balanceados por decisión y por si mencionan otro ramo; 10 de los
30 lo hacen) en `datos/redactados.csv`. Las preguntas las redactó un modelo de lenguaje sin
acceso al sistema: un subagente nuevo que recibió solo el ramo, el período y el ramo de
contexto de cada fila, con la instrucción de escribir como un estudiante chileno por WhatsApp,
variando la forma. No vio los prompts, la herramienta de búsqueda ni las plantillas del
generador, así que no pudo redactar a favor del sistema. El equipo no escribió las preguntas
porque no había tiempo de coordinar a los tres. La revisión de las 30 la hizo Claude (el
asistente que construyó el sistema) y se limitó a validez y naturalidad: las 30 piden el ramo y
el período de su fila, y se corrigió la redacción de 3 (filas 4, 18 y 20) sin cambiar el ramo
nombrado ni su forma. Lucas confirma la revisión con una lectura. El CSV registra autor y
revisión por fila. Las respuestas del agente están en `datos/redactados_modelo.json`.

El documento técnico lo declara en una frase: *"30 preguntas redactadas fuera de las
plantillas por un modelo de lenguaje sin acceso al sistema, revisadas con asistencia de IA y
confirmadas por el equipo"*. En el
video se llaman "preguntas redactadas fuera de las plantillas", no "preguntas reales".

La etiqueta no cambia, porque depende del historial y la consulta y no de la redacción.
`preparar_redactados.py unir` arma `casos_redactados.jsonl` solo si las 30 están revisadas.

---

## Medición

**Filas, todas sobre los tres conjuntos de prueba:** baseline few-shot del D1, sistema del D2,
sistema de agentes, las cuatro ablaciones y la fila de diagnóstico. El baseline y el D2 ya están
corridos en originales y nuevos; faltan en los redactados.

**Fila de referencia sin modelo: regla fija.** Toma el texto entre "inscribir/tomar/meter" y el
signo de interrogación, lo pasa por T1, se queda con el primer candidato y supone período
actual. Es `runner_d3.py --modelo-falso`. En los 60 originales acierta **42 de 60**, más que el
D2 (35) y lo mismo que Qwen, porque la plantilla siempre pone el ramo consultado justo después
del verbo. Cumple el papel que tuvo "responder siempre sí" en el D2: un piso que cualquier
sistema tiene que superar. En los redactados se espera que caiga, y esa caída es la
evidencia de que las plantillas eran fáciles para una regla y de que el sistema de agentes no
depende de ellas. Si los agentes no superan a la regla en las plantillas, se dice.

**Métricas.**
- Principal: acierto conjunto (decisión y regla), el criterio del D1 y el D2.
- De extracción: acierto de ramo, de período y recall@5 de T1.
- Con y sin los casos ambiguos.
- Activación de cada rama: casos con rechazo del Verificador, con búsqueda extra, con
  `sin_ramo`, con tope alcanzado. Si las ramas casi no se activan, el sistema funciona como
  pipeline en la práctica y hay que decirlo.
- Tokens y segundos por caso. El sistema de agentes va a costar más que el D2 (1.153 tokens).

**Rigor.**
- Protocolo `PROTOCOLO_D3.md` subido antes de las corridas de prueba, con la hipótesis, las
  filas, la regla del caso de falla y la del video.
- McNemar exacto de agentes contra el D2, por conjunto y en los 150 juntos.
- Una ablación que mueve 2 o 3 casos en 60 está dentro del ruido; se dice.
- Generación greedy, 4 bits NF4, la misma configuración del D2. Las trazas se reproducen.
- Los prompts se congelan antes de las corridas de prueba. El hash de cada uno queda en la traza.

**Caso de falla**, por regla escrita antes de correr: el primer caso del conjunto redactado,
en orden de `id_original`, donde el sistema de agentes falla.

---

## Trazas, prompts y archivos nuevos

Cada mensaje es una línea JSONL: `caso`, `conjunto`, `configuracion`, `paso`, `de`, `para`,
`contenido`, `accion`, `tokens`, `segundos`, `prompt` (archivo y hash). Se guardan todas las
corridas en `trazas/`.

| Archivo | Qué es |
|---|---|
| `prompts/interprete.md`, `resolvedor.md`, `verificador.md` | Prompts del sistema completo, con versión en la cabecera |
| `prompts/ablaciones/*.md` | Las versiones sin cada técnica |
| `scripts/herramientas.py` | T1 y el envoltorio de T2 |
| `scripts/agentes.py` | Los tres agentes: arman el prompt desde el archivo y leen la acción |
| `scripts/orquestador.py` | Ejecuta las acciones, aplica los topes y escribe la traza |
| `scripts/runner_d3.py` | Corre una configuración sobre un conjunto. Pruebas con un modelo falso, como `runner_d2.py` |
| `scripts/diagnostico_d3.py` | El diagnóstico de esta sección (ya está) |
| `scripts/preparar_redactados.py` | El conjunto redactado fuera de las plantillas (ya está) |
| `scripts/ver_traza.py` | Muestra una traza como conversación entre agentes, para la demo |
| `scripts/preparar_desarrollo.py` | El conjunto de desarrollo: 52 casos, semilla 20261020, sin preguntas de prueba |
| `scripts/gen_notebook_d3.py` → `corrida_d3_colab.ipynb` | Desarrollo y etapa final en la T4; clona el repo en el commit indicado |
| `demo_d3_colab.ipynb` | La demo del video (pendiente) |

---

## Video

Hasta 3 minutos, Phi cargado en una celda aparte. Tres casos, elegidos por regla escrita en el
protocolo: un redactado donde el sistema acierta sin bucle, el primer redactado donde
el Verificador rechaza y el resultado final es correcto, y el caso de falla. En cada uno se ven
los mensajes entre agentes y la salida final. Grabación a 1920x1080, como en el D2.

## Documento

Una página vertical, LaTeX, mismo formato del D2. Contenido: tarea y continuidad (corto), el
grafo en TikZ (cada agente y herramienta como nodo, aristas con lo que se pasa, los dos bucles
con su tope y las paradas), la tabla de agentes, la tabla de técnicas con el efecto de quitar
cada una, resultados sobre los tres conjuntos, activación de ramas, caso de falla y límites
declarados (ambiguos, plantillas, costo). El `.tex` se edita con reemplazos exactos y se
commitea antes de cada cambio grande.

---

## Cobertura de la rúbrica

| Criterio | Dónde se juega |
|---|---|
| Continuidad | Misma tarea, criterio y casos; T2 es el código del D2; Phi como prometió el D2. Desviaciones declaradas: diagnóstico más fino de la misma falla, conjunto redactado por un modelo a ciegas, ambiguos. |
| Grafo | TikZ con 3 agentes y 2 herramientas, aristas etiquetadas, bucles y paradas marcados |
| Diseño de agentes | Un mecanismo medido por agente y contexto aislado (tabla "Por qué esta división") |
| Técnicas | Cuatro ablaciones ligadas a M1, M2 y M3 |
| Evidencia | 150 casos en tres conjuntos, McNemar, activación de ramas |
| Repositorio | Prompts en archivos con hash en la traza, trazas versionadas, README que reproduce el video |

---

## Riesgos

- **El Verificador de 3,8B rechaza respuestas correctas.** La ablación lo mide. Si quita más de
  lo que agrega, se reporta y se discute.
- **Las ramas casi no se activan.** Se mide y se dice.
- **Las preguntas redactadas por un modelo suenan a modelo.** Pueden ser más ordenadas y
  explícitas que las de un estudiante real (más nombres completos, menos errores), y eso haría
  el conjunto más fácil. La revisión del equipo corrige las que suenen artificiales, y el
  límite se declara.
- **Filtrar las plantillas al sistema.** Ningún prompt ni herramienta usa el diccionario de
  abreviaciones ni las frases del generador.
- **Phi no respeta el JSON.** En el D2 todas sus salidas fueron legibles. Las acciones por
  defecto están declaradas.

---

## Calendario

| Fecha | Qué | Quién |
|---|---|---|
| 19-20 oct | Este plan. Correo al profesor. Repartir el CSV. | Lucas |
| 20-22 oct | Herramientas, agentes, orquestador, trazas, pruebas con modelo falso | Lucas + Claude |
| 20-22 oct | Escribir las 30 preguntas y revisarlas cruzado | los tres |
| 22-23 oct | Colab sobre desarrollo, ajuste de prompts | Lucas + Claude |
| 24 oct | Congelar prompts, subir el protocolo, correr todo | Lucas |
| 25-26 oct | Análisis, McNemar, caso de falla | Lucas + Claude |
| 26-28 oct | PDF y README | los tres revisan |
| 28-29 oct | Demo y video | Lucas |
| 30 oct | Auditoría contra la rúbrica | los tres |
| 31 oct | Margen. Entrega en Canvas. | Lucas |

---

## Preguntas al profesor

Borrador del correo:

> Profesor, somos el grupo de validación de inscripción de ramos (Sepúlveda, Saavedra,
> Saldivia). Dos dudas sobre el Deliverable 3:
>
> 1. El enunciado pide identificar las técnicas de prompting de cada agente "against a schema".
>    ¿Se refiere a la clasificación de técnicas de la Lecture 5, o a otro esquema que debamos
>    usar?
> 2. En nuestro sistema cada agente escribe su decisión (por ejemplo "buscar de nuevo" o
>    "rechazar") en su salida, y un orquestador en código la ejecuta. ¿Eso cumple la definición
>    de agente que decide qué pasa después? Las herramientas son código sin modelo.
>
> Gracias.

---

## Registro de decisiones

**19 oct 2026 — Diagnóstico por mecanismo.** El 3/20 del D2 es real pero no es la falla
principal: con el nombre exacto Phi acierta 18/34. Los agentes se diseñan contra M1, M2 y M3.

**19 oct 2026 — Phi-3.5-mini.** Lo comprometió el PDF del D2.

**19 oct 2026 — T1 léxica, sin embeddings.** Evita un segundo modelo en el sistema y el
diagnóstico muestra que basta.

**19 oct 2026 — Sin T3.** Gana como mucho 5 de 120, rompe el aislamiento del paso de lectura y
se apoya en una propiedad del generador. Ver "Decisiones tomadas en esta revisión".

**19 oct 2026 — El Intérprete puede detenerse.** Sin la acción `sin_ramo`, en la primera
pasada siempre entregaría y no tomaría ninguna decisión, que es lo que el enunciado excluye.

**20 oct 2026 — El chequeo de robustez sale 20/21 y se congela la v4 sin cambios.** Commit
`3ba2528`. Período 21/21, incluidos "pal primer semestre del 2027", "el que parte en marzo" y
"altiro" junto a 2027. El Resolvedor resolvió la sigla "DHG" buscando de nuevo dos veces. La
única falla es "la práctica", que sirve para Práctica Laboral y Práctica Profesional: un caso
aislado y ambiguo, así que por la regla no se toca nada. La regla fija saca 11/21.

**20 oct 2026 — Chequeo de robustez antes de congelar.** Todo el ajuste se hizo sobre preguntas
de plantilla, y uno de los tres conjuntos de prueba son preguntas redactadas fuera de ellas.
Para no descubrir en la corrida final que el sistema se rompe con ese estilo, se redactan 21
preguntas a partir de casos de DESARROLLO (`preparar_redactados.py --desarrollo`, semilla
20261021, mismo agente a ciegas y mismas instrucciones) y se corre la v4 una vez. **Regla
escrita antes de correr:** solo se cambia un prompt si aparece un tipo de falla general que se
repita en 3 casos o más; una falla aislada no se toca. Haya cambio o no, después de esta
corrida se congela. Si hay cambio, se vuelve a correr el desarrollo de plantillas para
comprobar que no baja de 44/52, y el protocolo se actualiza con los hashes nuevos antes de
subirlo.

**20 oct 2026 — Se congela la v4.** La v4 (commit `1db45fc`) sacó 44/52, con los mismos casos
que la v3, y no rechazó nada: cumple la regla y se queda. Sus citas ahora salen de la consulta
en 37 de 52 casos (`citas_fuera` 15). No rechaza porque en desarrollo no le queda nada que
pueda detectar: las 7 fallas restantes son preguntas ambiguas, donde la lectura elegida es
válida, y el resto ya lo resuelven el Intérprete y el Resolvedor (44 de 45 con solución). Su
aporte se mide en la corrida final, sobre todo en los redactados y en la ablación sin
descomposición. La fila de referencia sin modelo pasa a llamarse `regla_fija`. Siguiente:
`PROTOCOLO_D3.md`, subido antes de la corrida final.

**20 oct 2026 — v3 sacó 44/52; v4 es la última iteración, solo del Verificador.** La v3
(commit `781ba32`) ganó 4 casos y no perdió ninguno: período 48/52 contra 41/52. De las 8
fallas, 7 son las preguntas ambiguas y 1 es de período (caso 24): acierta 44 de los 45 casos
con solución. El Verificador no rechazó ningún caso, y la traza muestra por qué: sus citas
copiaban la interpretación que revisaba ("Gestión y Control de la Calidad", "proximo") en vez
de la consulta ("gestión", "el que viene"). v4: las citas salen de la consulta con sus
palabras exactas, y dos ejemplos (uno acepta, otro rechaza un ramo de contexto). El código
marca `citas_fuera` cuando la cita no aparece en la consulta, sin cambiar la acción.
**Regla escrita antes de correr la v4:** se queda la v4 solo si saca 44 o más en desarrollo y
ninguno de sus rechazos convierte un acierto en error. Si no, se congela la v3. En los dos
casos no hay más iteraciones de desarrollo.

**20 oct 2026 — Prompts v3: citar antes de decidir.** La v2 sacó 40/52 (commit `8cd44ab`):
ganó "PCP" (el Resolvedor buscó de nuevo por primera vez) e "ingeniería", y perdió dos casos
porque el Verificador rechazó períodos correctos con un motivo de reglamento ("ya está tomando
Modelación, no puede inscribirse"): juzgó si el estudiante podía inscribir en vez de comprobar
la interpretación. De sus 7 rechazos ninguno corrigió un error. Los 3 casos de período no
cambiaron. Cambios: el Verificador pierde la regla de la v2, se le dice que no decide si puede
inscribir, y copia `cita_ramo` y `cita_periodo` antes de comparar; el Intérprete copia
`frase_periodo` antes de decidir el período. Es la misma técnica en los dos agentes (extraer la
evidencia textual y decidir sobre ella) y no se ablaciona por separado. Las 6 a 10 s por caso
bajaron a 6,3 con el corte. Regla para cerrar: como mucho una iteración más después de esta,
y los 7 ambiguos no se persiguen.

**20 oct 2026 — Prompts v2, desde las fallas de desarrollo.** Con el lector corregido, la v1
sacó 40/52 en desarrollo (commit `2cbdfc8`). De las 12 fallas, 7 son preguntas ambiguas por
construcción ("gestión" cuatro veces, "la I", "práctica", "cálculo"), 3 son el período cuando
el ramo de contexto se está cursando "ahora" y la pregunta es por el próximo (el modelo toma el
"ahora" del otro ramo), 1 es la sigla "PCP" y 1 es "ingeniería". El Resolvedor no volvió a
buscar en ningún caso y el Verificador rechazó en uno. Cambios: regla del período del ramo
consultado en Intérprete y Verificador, un ejemplo con el ramo de contexto en curso, y en el
Resolvedor qué hacer con una sigla que ningún candidato contiene. Las versiones de ablación
llevan los mismos cambios. Además la generación se corta al cerrar el primer JSON (8,9 s por
caso en la v1, casi todo explicación descartada); con greedy y lectura del primer JSON la
respuesta usada es la misma.

**19 oct 2026 — Se lee el primer JSON de cada respuesta.** En la primera corrida de desarrollo
Phi escribió el JSON, una explicación y el JSON repetido, y el lector del D2 (de la primera
llave a la última) dejó 15 de 52 respuestas ilegibles que traían el JSON correcto: 12 casos
terminaron en `sin_ramo`. Se cambió el lector, no los prompts. Desde ahí cada fila guarda el
commit, y el runner no retoma un archivo corrido con otro código. Esa corrida (30/52) no cuenta.

**19 oct 2026 — Fila de referencia de regla fija.** La prueba del flujo con el modelo falso
acertó 42/60 en los originales. Se reporta como piso, en los tres conjuntos.

**19 oct 2026 — Conjunto redactado y conjunto de desarrollo.** Los prompts se ajustan solo en
desarrollo, y los redactados prueban que el sistema no aprendió las plantillas. Los redacta un
modelo sin acceso al sistema, no el equipo, por tiempo; se declara en el documento.
