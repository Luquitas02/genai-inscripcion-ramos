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
