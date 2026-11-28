# Diseño — Deliverable 4

**Vence:** domingo 30 de noviembre de 2026, 23:59 · Canvas
**Vale:** 40% del proyecto semestral
**Equipo:** Joaquín Sepúlveda · Renato Saavedra · Lucas Saldivia
**Escrito:** 13 de noviembre de 2026
**Enunciado:** `Material del curso/Deliverable_4.pdf` · clase de referencia: Lecture 8 (Fine-tuning)

---

## Qué pide la entrega

Ajustar con fine-tuning el modelo de al menos un agente del sistema del D3, con datos construidos
contra la falla diagnosticada en el D1, y mostrar qué logran los pesos nuevos que el prompting
solo no logró.

| Requisito (enunciado) | Cómo se cumple |
|---|---|
| Elegir el agente con evidencia de las trazas del D3 | El Intérprete. Sección "El agente" |
| Parte del mismo modelo base; los demás pueden quedar con la base | Adaptador QLoRA sobre Phi-3.5-mini (revisión `2fe1924`), activo solo en las llamadas del Intérprete (`scripts/modelo_d4.py`) |
| Pares de entrada y salida para el rol, con origen, tamaño y cómo se obtuvo cada salida | Sección "Datos de entrenamiento" |
| Datos de un modelo más grande: nombrarlo y revisar a mano una muestra declarada | La prosa la escribe Claude (Anthropic); el equipo revisa 100 pares |
| Pesos o adaptador publicados en Hugging Face | Sección "Hugging Face" |
| Caso de falla con explicación y traza en el repo | Regla fijada en el protocolo, sección "Medición" |
| Video ≤ 3 min: agente base y ajustado sobre la misma entrada, mensajes visibles | Sección "Video" |
| PDF de una página en LaTeX: grafo con el agente marcado, datos, configuración con curvas de pérdida, tabla de los cuatro sistemas y el control | Sección "Documento" |
| Repo: script de entrenamiento, datos o script que los rehace, link a los pesos, prompts versionados, trazas | Sección "Archivos" |

Rúbrica, seis criterios de 10: continuidad con D1 a D3, elección del agente (con evidencia y
explicando por qué fine-tuning y no más prompting), datos (origen, tamaño, etiquetado, muestra
revisada a mano, separación de la evaluación **demostrada**), procedimiento (método,
hiperparámetros, curvas, tiempo, hardware, y que el adaptador publicado cargue y reproduzca),
evidencia de mejora sobre un conjunto declarado, y repositorio reproducible.

---

## Punto de partida: dónde fallan el D3 y qué se puede arreglar

Cifras de `scripts/origen_errores_d4.py` y `scripts/analisis_previo_d4.py` sobre las trazas de
la v4 (150 + 180 casos de prueba y 73 de desarrollo, 403 en total).

**Los 34 errores de acierto conjunto en los 330 casos de prueba**, por el primer punto donde se
perdió el dato correcto:

| Origen | Errores | ¿Lo arregla ajustar ese agente? |
|---|---|---|
| Referencia ambigua por construcción ("gestión", "electiva", "mecánica", "la I") | 14 | No. El Resolvedor recibe la misma entrada con ramos correctos distintos (caso 26 de originales y 21 de plantilla_b) |
| Resolvedor elige Cálculo II por "cálculo 3" teniendo la coincidencia exacta primero | 8 | Sí, pero una regla de una línea en código hace lo mismo |
| Intérprete: período o mención | 11 | Sí. Es comportamiento, no un dato que falte |
| Verificador rechaza una lectura correcta | 1 | — |

**El Intérprete** lee bien el período en 94 % de las plantillas y 95 % de las redactadas. Lo que
falla en sus datos está concentrado: "el que viene" en plantilla (14 de 40 mal; copia la frase y
pone `actual`) y "este segundo semestre" en redactadas (4 de 5 errores). El período solo decide
la respuesta en 130 de 403 casos (los constructores `_c_inscrita_actual` y `_c_inscrita_proximo`,
un prerrequisito en curso: es E1 del D1).

**Piloto del 13 de noviembre** (`scripts/analisis_piloto_d4.py`, 60 casos de desarrollo con
prosa variada escrita por un subagente, resultados en `8e823af`):

| | Acierto conjunto | Período del Intérprete | Donde decide el período (40) |
|---|---|---|---|
| D3 (v4) | 52/60 | 53/60 | 32/40 |
| Intérprete ajustado con 450 pares de plantilla | 48/60 | 48/60 | 28/40 |
| Control, 40 ejemplos más en el prompt | 37/60 (20 salidas ilegibles) | 50/60 | 19/40 |

Tres lecciones:
1. Con prosa variada el D3 falla 13 % (20 % donde decide el período): hay espacio. Falla en
   "segundo semestre", "en el semestre de agosto a diciembre", y en apodos (evapro, edo, cálculo 3).
2. Entrenar con plantillas empeora (gana 2, pierde 6): la pérdida llega a 0,001 en 20 pasos, el
   adaptador aprende las ocho frases del generador y lee `proximo` en "este semestre que va" o
   "de una". **Los datos de entrenamiento tienen que ser prosa variada.**
3. Con 40 ejemplos el prompt mide unos 4.050 tokens y Phi-3.5 cruza su límite de 4.096 (cambia la
   escala de posiciones) al generar: escribe un mismo carácter repetido. El control se rehace con
   los ejemplos que quepan con margen bajo ese límite.

Además el piloto probó la parte técnica: QLoRA en una T4 con 450 pares tomó 24,8 min, 57 pasos y
3,5 GB, y el adaptador se activó solo en las llamadas del Intérprete.

---

## El agente: el Intérprete

**Por qué él** (criterio "Choice of agent"):
- De los errores que algún agente puede arreglar, la mayoría nace en él, y en prosa variada su
  error de período sube a 12-20 %.
- Es la falla del D1. E1 ("no representa *cursándola ahora*") y E2 ("depende de que la pregunta
  le apunte") son errores de lectura de la pregunta, y el Intérprete es el agente que lee.
- El Resolvedor queda descartado: casi todo su error es ambiguo por construcción o lo arregla
  una regla en código.

**Por qué fine-tuning y no más prompting:**
- El prompt v3 ya define el período con fechas ("actual... 2026-2"), trae 4 ejemplos y pide citar
  la frase antes de decidir. En el D3 esa técnica subió el período de 154 a 173 de 180. Aun así,
  copia "el que viene" o "este segundo semestre" y decide al revés con la frase delante.
- Las versiones v5 y v6 corrigieron con prompts y con el Verificador, y no superaron a la v4.
- Hay un techo físico: los ejemplos en el prompt de Phi-3.5 caben hasta unos 4.000 tokens. El
  ajuste pone miles de ejemplos en los pesos y deja el prompt como está.
- Es un comportamiento, no un dato nuevo: la Lecture 8 (lámina 5, Gekhman et al. 2024) dice que
  el fine-tuning sirve para enseñar conductas y no hechos.

**Qué no cambia:** el prompt del Intérprete (v3, mismo archivo), el Resolvedor, el Verificador,
T1, T2 y el orquestador. Sistema del D4 = v4 + adaptador en el Intérprete. Así la diferencia con
el D3 son solo los pesos.

---

## Datos de entrenamiento

**Formato.** Cada par es la entrada exacta del Intérprete en el sistema (prompt v3 de sistema +
la consulta en la sección de usuario) y la salida que debió dar, en JSON (lámina 8, formato de
mensajes; prompt-completion, pérdida solo en la respuesta):

    {"accion": "entregar", "consultado": "...", "otros": [...], "frase_periodo": "...", "periodo": "actual" | "proximo"}

**De dónde sale cada parte de la etiqueta.**

| Campo | Origen |
|---|---|
| `periodo` | El caso del generador (la consulta). No lo escribe ningún modelo |
| ramo y ramos de contexto (qué son) | El caso del generador |
| `consultado`, `otros`, `frase_periodo` (cómo se escribieron) | Las palabras exactas del mensaje que el redactor declara; un script exige que estén literalmente en el mensaje y descarta el par si no |
| la prosa del mensaje | Claude (Anthropic), subagentes con la instrucción versionada en `datos/entrenamiento_d4/INSTRUCCION.md` |

**Composición (fijada antes de generar):**

| Bloque | Pares | Para qué |
|---|---|---|
| Prosa variada, 6 estilos (período relativo, de calendario o implícito × ramo por nombre o apodo) | 1.200 | El comportamiento que falla. 50 % de constructores donde decide el período, con el otro ramo en curso |
| Plantillas del generador (`datos_d4.py`) | 150 | Que no pierda lo que ya hace bien |
| Turnos de revisión (la entrada trae un rechazo del Verificador) | 60 | El Intérprete también corrige tras un rechazo (19 veces en 403 casos). La mitad con rechazo fundado y la mitad con rechazo a una lectura correcta, que debe mantener |
| Sin asignatura ("hola, ¿a qué hora abre la secretaría?") | 20 | La acción `sin_ramo` |
| **Total** | **1.430** | 1.290 de entrenamiento y 140 de validación, al azar con semilla fija |

**Revisión a mano.** El equipo revisa 100 pares al azar (estratificados por estilo) contra una
pauta: ¿el mensaje dice el ramo y el semestre de la etiqueta?, ¿`consultado` y `frase_periodo`
son las palabras correctas? Queda en `datos/entrenamiento_d4/revision_manual.csv` con quién
revisó. Se reporta la tasa de error. Si pasa del 5 %, se revisan 100 más y se corrige la
instrucción antes de entrenar.

**Separación de la prueba, demostrada con un script** (`scripts/separacion_d4.py`):
- ningún caso de entrenamiento comparte historial y consulta con un caso de prueba;
- ninguna pregunta de entrenamiento es igual ni casi igual (difflib > 0,85) a una de prueba;
- tabla de solapamiento de 6-gramas entre entrenamiento y prueba, comparada con el solapamiento
  dentro de la propia prueba.

Límite que se declara: el mismo modelo (Claude) escribe la prosa de entrenamiento y la de prueba.
Lo mitigan los casos distintos, la instrucción distinta y que el redactor de la prueba no vea los
datos de entrenamiento, pero no lo elimina.

---

## La prueba sellada

**240 casos nuevos**, con semillas que no se usaron nunca, filtrados contra todos los conjuntos
anteriores, el piloto y el entrenamiento:

| Bloque | Casos | Prosa |
|---|---|---|
| Plantilla | 60 | La del generador, para continuidad con el D3 |
| Redactada, donde decide el período | 120 | Subagente a ciegas, instrucción propia versionada |
| Redactada, otros constructores | 60 | Ídem |

- Se arma y se sella (sha256 en `datos/prueba_d4/SELLO.txt`) **antes de entrenar**.
- Uno de nosotros lee las 180 redactadas antes de sellar, para descartar mensajes que una persona
  no entendería. Claude no las lee hasta la corrida final.
- Por qué 240 y no 180 (simulación de `analisis_previo_d4.potencia`, McNemar exacto, el ajuste
  rompe 2 % de los aciertos): con el 13 % de error que el D3 tuvo en el piloto, 180 casos detectan
  la mejora con probabilidad 0,53 si el ajuste arregla la mitad de los errores y 0,89 si arregla
  tres cuartos. Con 240, 0,69 y 0,96. Si el error del D3 en la prueba es 20 %, 240 casos dan 0,98
  con la mitad. Cada fila cuesta unos 30 min de T4 sobre 240 casos.

Los 60 casos del piloto quedan como conjunto de desarrollo, el único que se mira para decidir.

---

## Entrenamiento

Receta de la Lecture 8 (lámina 17), con lo que el piloto midió:

| | Valor | Origen |
|---|---|---|
| Método | QLoRA: base en NF4 congelada, adaptador LoRA | láminas 12 a 17 |
| LoRA | rango 16, alpha 32, dropout 0,05, todas las capas lineales | lámina 17 |
| Learning rate | 2e-4, lineal, 3 pasos de calentamiento | lámina 17 |
| Batch | 2 × 4 de acumulación = 8 | piloto (memoria 3,5 GB) |
| Épocas | hasta 2, se guarda el adaptador de cada una en Drive | 3 épocas serían 3,5 h, más que una sesión gratuita segura |
| Precisión | fp16 (la T4 no tiene bfloat16) | piloto |
| Pérdida | solo la respuesta | lámina 9 |
| Hardware | Tesla T4 de Colab | — |
| Tiempo esperado | unos 70 min por época con 1.290 pares | piloto: 24,8 min con 450 |

**Elección de la época, escrita antes:** se queda la época con más acierto conjunto del sistema
completo en los 60 del piloto. Si empatan, la de menor pérdida de validación. La prueba sellada
se corre una sola vez, con esa época.

---

## Medición

**Las filas de la tabla** (todas sobre los 240 sellados, mismo criterio que el D1: decisión y
regla correctas):

| Fila | Qué es |
|---|---|
| Baseline few-shot (D1) | Phi con 3 ejemplos, sin sistema |
| Sistema del D2 | Lectura con un modelo y reglas en código |
| Sistema del D3 (v4) | Tres agentes, todos con la base |
| **Sistema del D4** | La v4 con el Intérprete ajustado |
| **Control** | La v4 con el Intérprete base y el mejor prompt posible: el v3 más los ejemplos de entrenamiento que quepan sin pasar de 3.600 tokens (se verifica en el piloto que no degenere) |
| Regla fija, sin modelo | Piso, como en el D3 |

Los "cuatro sistemas" serían el D1, el D2, el D3 y el D4, y el control el de arriba. Se confirma
con el profesor (ver "Preguntas al profesor").

**Análisis fijado antes de correr** (`PROTOCOLO_D4.md`, subido al repo antes de la corrida):
- Comparación principal: D4 contra D3 en acierto conjunto sobre los 240, McNemar exacto bilateral,
  α = 0,05. Secundaria: D4 contra control.
- También: acierto estricto (ramo y período), período del Intérprete, y los tres bloques por
  separado.
- "Lo que no debe romperse" (lámina 24): JSON legible en todas las llamadas del Intérprete, casos
  que el D3 acertaba y el D4 falla, uso de `sin_ramo` y de la revisión.
- Caso de falla: el primer caso redactado, en orden de id, que el D4 falla. Se explica con su
  traza. Candidato natural: el Resolvedor que elige Cálculo II aunque el Intérprete lea bien.
- Se reporta lo que salga, aunque no haya significancia.

---

## Hugging Face

- Repositorio público del adaptador, por ejemplo `<usuario>/phi35-mini-interprete-inscripcion-lora`,
  con una ficha que dice base, revisión, datos, hiperparámetros, curvas y resultados.
- **La corrida sellada carga el adaptador desde Hugging Face en una revisión fija** (el hash del
  commit en HF), no desde una copia local. Esa revisión queda en el PDF, el README y cada fila de
  resultados. Así "los pesos del link son los que produjeron los resultados" se verifica.
- El token de escritura va en los *Secrets* de Colab, nunca en el chat ni en el repo.

---

## Video, documento y archivos

**Video (≤ 3 min).** El mismo mensaje redactado de la prueba con el Intérprete base y con el
ajustado, los mensajes entre agentes en pantalla (`ConAdaptador`, `usar_adaptador` True y False
sobre un solo modelo cargado), más el caso de falla. Trazas guardadas en el repo.

**Documento (una página).** Grafo del D3 con el Intérprete marcado como ajustado. Datos (origen,
tamaño, composición, revisión manual, separación). Configuración con las curvas de pérdida de
entrenamiento y validación. La tabla de la sección "Medición". Por qué fine-tuning y no prompting.
Caso de falla. Límites.

**Archivos nuevos o ya hechos:**
- hechos: `scripts/origen_errores_d4.py`, `analisis_previo_d4.py`, `preparar_piloto_d4.py`,
  `datos_d4.py`, `gen_prompt_control_d4.py`, `entrenar_d4.py`, `modelo_d4.py`,
  `gen_notebook_piloto_d4.py`, `analisis_piloto_d4.py`;
- por hacer: `preparar_entrenamiento_d4.py` (casos, filas para los redactores, verificación de las
  palabras declaradas, unión), `preparar_prueba_d4.py` (casos sellados y redactadas),
  `separacion_d4.py`, `PROTOCOLO_D4.md`, notebook de entrenamiento y de la corrida sellada,
  `analisis_d4.py`, `poster/deliverable4.tex`, README.

---

## Riesgos

| Riesgo | Qué se hace |
|---|---|
| La mejora no es significativa | La prueba concentra los casos donde decide el período. Se reporta igual, con el estricto y el período del Intérprete |
| El control queda tan bien como el ajuste | Es un resultado válido y se reporta. El argumento de los tokens (4.000 contra 1.000) sigue en pie |
| El ajuste aprende el estilo del redactor | Separación medida, límite declarado, 60 casos de plantilla en la prueba |
| El adaptador rompe la revisión o `sin_ramo` | Pares de revisión y sin asignatura en el entrenamiento; se mide en el piloto y en la prueba |
| Cupo de GPU de Colab | El entrenamiento retoma desde Drive; el calendario deja dos días de margen |
| Costo de redactar 1.200 mensajes | Unos 20 subagentes de 60 mensajes; se puede bajar a 800 si hace falta (decisión de Lucas) |

---

## Calendario

| Fecha | Paso | Quién |
|---|---|---|
| 14 nov | Casos y redacción de los datos de entrenamiento; verificación automática | Claude |
| 14-15 nov | Revisión manual de 100 pares | Equipo |
| 15 nov | Prueba sellada: casos, redacción, lectura del equipo, sello | Claude y equipo |
| 15 nov | Correo al profesor | Lucas |
| 16 nov | `PROTOCOLO_D4.md` y separación, en el repo antes de entrenar | Claude |
| 16-17 nov | Entrenamiento (2 épocas, unas 2,5 h) y elección de época en el piloto | Lucas corre, Claude analiza |
| 17 nov | Publicación en Hugging Face | Lucas |
| 18-19 nov | Corrida sellada: seis filas sobre los 240 (unas 2 a 3 h de T4, en dos sesiones) | Lucas corre |
| 20-22 nov | Análisis, caso de falla | Claude |
| 22-25 nov | Documento | Claude escribe, Lucas compila en Overleaf |
| 25-27 nov | Video, README | Lucas graba |
| 27-29 nov | Auditoría y entrega | Ambos |
| 30 nov | Margen | — |

---

## Preguntas al profesor

1. "Los cuatro sistemas y el control": ¿son el baseline del D1, el D2, el D3 y el D4, y el control
   es el agente base con el mejor prompt posible (incluidos ejemplos de los datos de
   entrenamiento)?
2. ¿Un adaptador QLoRA sobre el modelo cuantizado en 4 bits cuenta como "starts from the same
   open-weight base model"?

---

## Registro de decisiones

- **13 nov.** D3 calificado con 7. Se lee el enunciado y la Lecture 8 completa.
- **13 nov.** Primer conteo rápido sugería ajustar el Resolvedor. La revisión caso a caso lo
  descartó: sus errores son ambiguos por construcción o se arreglan con una regla en código. Se
  elige el **Intérprete**.
- **13 nov.** Las preguntas redactadas las escribe un subagente (decisión de Lucas), solo con la
  instrucción y las filas, sin ver el sistema.
- **13 nov.** Piloto en Colab (commit `c68a777`): el D3 falla 13 % en prosa variada; ajustar con
  plantillas empeora; el control con 40 ejemplos cruza el límite de 4.096 tokens. Se decide
  entrenar con prosa variada etiquetada, control bajo 3.600 tokens, y elegir época en el piloto.
- **13 nov.** La prueba sellada sube de 180 a 240 casos: con 180 la potencia era 0,53 en el
  escenario conservador (cifra corregida; el primer borrador decía 0,9 sin haberla calculado).
- **24 nov.** Se retoma tras 11 días sin avance. Lucas confirma que el tiempo no es restricción:
  se mantiene el plan completo (1.200 pares de prosa, 240 sellados, hasta 2 épocas). El
  calendario de arriba queda corrido; las fechas nuevas van en `ROADMAP.md`.
- **24 nov.** Prueba sellada armada con `scripts/preparar_prueba_d4.py` antes de cualquier dato
  de entrenamiento: 60 de plantilla (semilla 20261124) y 180 para redactar (semilla 20261125;
  60 `_c_inscrita_actual`, 60 `_c_inscrita_proximo`, 60 de otros constructores en la proporción
  del piloto), filtrados contra D1 a D3, la prueba de la v5, el desarrollo y el piloto. La prosa
  la escriben tres subagentes con la instrucción del piloto (misma distribución, así elegir la
  época en el piloto no mira la prueba), y escriben directo a archivo: Claude no lee los
  mensajes. Antes de sellar los lee una persona del equipo.
- **24 nov.** La verificación independiente de la prueba encontró que 13 de los 60 casos de
  plantilla (todos de nivel 1) repetían un problema o una pregunta de un conjunto anterior, y 7
  se repetían dentro de la prueba. Venía heredado del filtro escalonado de la v5: en el nivel 1
  el generador solo produce unos 10 problemas distintos con "sí" o "condicional". Decisión de
  Lucas: rehacer la plantilla solo con casos nuevos (`preparar_prueba_d4.py rehacer_plantilla`).
  El nivel 1 ya no tiene ningún caso nuevo con "sí" ni "condicional": queda con 7 "no", y los 13
  que faltan van a los niveles 2 y 3. Resultado: 0 repetidos con conjuntos anteriores y 0 dentro
  de la prueba. Decisión 21/21/18 igual que antes; el balance por nivel cambia (n1 7, n2 27,
  n3 26) y se declara. Los 180 redactados no cambiaron (sha256 idéntico antes y después).
- **24 nov.** Lectura de las 180 redactadas: en vez de una persona leyéndolas todas con la
  etiqueta a la vista (decisión de Lucas), un lector automático a ciegas (subagente de Claude,
  solo id y mensaje más la lista de 61 ramos) dice qué ramo y semestre entiende, y un script lo
  compara con la etiqueta (`scripts/lector_prueba_d4.py`). Una persona lee todos los desacuerdos
  y 30 acuerdos al azar (semilla 20261127). Si marca uno de esos 30 como no `ok`, lee 30 más; si
  aparece otro, lee todos. Regla escrita aquí antes de lanzar al lector. Límite declarado: lector
  y redactores son el mismo modelo, por eso la muestra humana de acuerdos.
- **24 nov.** Lectura cerrada: 177 acuerdos y 3 desacuerdos (los 3 por duda del lector, 1 además
  por semestre). Lucas leyó los 3 desacuerdos (2 `ok`, 1 `descartada`) y los 30 acuerdos al azar
  (30 `ok`), así que por la regla no se amplió la muestra. La prueba queda en 239 casos: 60 de
  plantilla y 179 redactados.
- **24 nov. Límite que se declara: oferta semestral.** El sistema (desde el D1) no modela en qué
  semestre se dicta cada ramo. Lucas registró la oferta real de los 61 ramos en
  `datos/OFERTA_RAMOS.xlsx`: 25 se dictan ambos semestres, 19 solo en el segundo y 17 solo en el
  primero. En la prueba sellada, 104 de 239 casos piden un ramo en un semestre en que no se dicta,
  y 52 de las 129 etiquetas afirmativas ("sí" o "condicional") serían en realidad "no se dicta".
  Decisión: no se agrega la regla, para no cambiar la tarea respecto de D1 a D3 (continuidad) y
  porque sería una regla de código, no algo que el fine-tuning del Intérprete deba aprender. Se
  declara en los límites del documento con esta cifra.
- **24 nov. Datos de entrenamiento armados después del sello** (`scripts/preparar_entrenamiento_d4.py`):
  1.260 casos nuevos (semilla 20261128) filtrados contra la prueba sellada, el piloto y todo lo
  anterior; `_c_especial` solo dio 36 casos nuevos y los 27 restantes pasaron a
  `_c_prerrequisito`. 21 subagentes con instrucción propia (`datos/entrenamiento_d4/INSTRUCCION.md`;
  el lote 01 se redactó sin la regla de no copiar los ejemplos, agregada después). 1.260 de
  1.260 pasaron el control de palabras literales. 471 frases de período distintas en los
  primeros 660. Total 1.430 pares (1.200 prosa, 60 revisión, 150 plantilla, 20 sin ramo):
  1.287 de entrenamiento y 143 de validación (10 % por bloque, semilla 20261130).
- **24 nov. Separación** (`scripts/separacion_d4.py`): la primera unión dejó 9 plantillas de
  entrenamiento casi iguales (difflib > 0,85) a preguntas de la prueba, porque el generador
  tiene pocas frases. Se descartaron del lado del entrenamiento (10 candidatas) sin tocar la
  prueba. Resultado final: 0 problemas repetidos, 0 preguntas iguales, 0 casi iguales (máximo
  0,848), y 7,3 % de los 6-gramas de la prueba aparecen en el entrenamiento, contra 8,5 % en el
  resto de la propia prueba.
- **24 nov. Revisión de etiquetas de entrenamiento** (`scripts/lector_entrenamiento_d4.py`, regla
  en su encabezado antes de correr): lector automático a ciegas sobre los 1.260 redactados;
  Claude lee los desacuerdos; el equipo revisa a mano 60 pares al azar (exigido por el
  enunciado), 30 por persona; con 2 o más etiquetas mal se revisan 60 más.
- **25 nov. Primera revisión manual** (60 pares al azar, semilla 20261201): Renato 30/30
  correctas, Joaquín 23/30 (7 incorrectas). La regla (2 o más) se activó. 6 de las 7 son del
  estilo apodo: 4 apodos que un estudiante no usaría ("estratégica", "calidad"; "calidad" ya
  venía del generador del D1) y 3 frases difíciles de entender. En las 7 la etiqueta copia
  literalmente las palabras del mensaje, que es lo que el Intérprete debe hacer; lo que falla
  es la naturalidad del mensaje. Decisión de Lucas: no cambiar la instrucción ni regenerar, y
  cumplir la otra parte de la regla con una segunda muestra de 60 (los siguientes 60 del mismo
  orden al azar) con tres opciones: correcta, "suena raro pero se entiende" (no cuenta como
  error de etiqueta) e incorrecta. Si hay 2 o más incorrectas en la segunda, se corrige la
  instrucción y se regenera. Límite que se declara: parte de los apodos los inventó el modelo
  redactor. Los dos revisores aplicaron criterios distintos en la primera vuelta.
- **28 nov. Segunda revisión manual devuelta: 0 incorrectas** (Joaquín 27 correctas y 3 "suena
  raro pero se entiende", Renato 29 y 1; los 4 "suena raro" son apodos: GPCO, evapro, compo
  organizacional, compo orga). Por la regla del 25 nov se entrena sin regenerar.
- **28 nov. `PROTOCOLO_D4.md`** subido antes de entrenar. Cambios respecto del plan, todos
  antes de ver resultados: (1) `entrenar_d4.py` guarda un checkpoint por época en Drive y retoma
  desde el último, y la validación se mide cada 23 pasos, que divide los 161 de cada época
  (medido en CPU con un modelo diminuto: 18 pares dan 3 pasos por época, o sea se redondea hacia
  arriba). (2) El control de la prueba toma sus ejemplos de los datos de entrenamiento reales, no
  de pares de plantilla como en el piloto: 27 ejemplos, 3.524 tokens con la consulta más larga
  (el del piloto medía 4.031 con el mismo tokenizador). Configuración `control_d4`. (3) La prueba
  tiene 239 casos y no 240 (uno descartado en la lectura del 24 nov).
- **28 nov. Regla fija sobre la prueba sellada** (en local, como fija el protocolo): 38/60 en
  plantilla y 57/179 en redactados, 95/239. `scripts/analisis_d4.py` escrito y validado sobre el
  piloto (reproduce D3 52/60, ajustado 48/60, gana 2 y pierde 6, estricto 49 y 42). Al probar
  su lectura de la prueba con filas falsas (copias de la regla fija), la salida mostró a Claude el
  texto de un redactado sellado (`id_d4` 3). Se declara. No cambia nada: sistema, datos de
  entrenamiento, control y protocolo ya estaban fijados en `ceadb14`.
- **28 nov. Entrenamiento y publicación.** 2 épocas, 322 pasos, 114 min en T4, 3,6 GB, sin
  cortes. Pérdida de validación de 0,033 (paso 23) a 0,0113 (paso 322). En el piloto las dos
  épocas dan 55/60 y el control `control_d4` 52/60 con 0 ilegibles (bajo el límite de 3, no se
  reconstruye). Por empate se eligió la época 2, de menor pérdida de validación. Publicada en
  `Lss02/phi35-mini-interprete-inscripcion-lora`, revisión `99262ad`, sha256 del adaptador
  `2a88dfd0…` (comprobado también bajándolo en local). Registro en `resultados/entrenamiento_d4/`.
- **28 nov. Prueba sellada, arreglo en la celda de Drive.** El chequeo de choque de nombres de
  `prueba_d4_colab.ipynb` (`bef0724`) buscaba `*__d4_plantilla.raw.jsonl` en `resultados/` y dio
  con los dos archivos de la regla fija subidos en `a1922f7`. No chocan con ninguna salida de la
  prueba (D1 y D2 escriben con prefijo `Phi-3.5…` y `pipeline__…`; los agentes, en Drive). Se
  borraron de la copia de Colab con una celda agregada a mano antes de la sección 3. No toca
  casos, prompts, adaptador ni análisis, que lee la regla fija del repositorio local. La prueba
  se corrió desde otra cuenta de Colab de Lucas por el cupo de GPU.
