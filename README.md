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

Se reportan **dos métricas separadas**. La decisión tiene tres valores, así que se acierta
un tercio por azar; la regla no se adivina entre unos quince identificadores posibles. La
brecha entre ambas mide cuánto del acierto es entendimiento y cuánto es suerte. La métrica
principal es el **acierto conjunto**: ambos campos correctos.

---

## Resultados del baseline

60 casos · 3 modelos · 3 condiciones · generación determinista

| Modelo | Params | Condición | Decisión | Regla | Ambas |
|---|---|---|---|---|---|
| Granite-3.1-8B | 8,0 B | zero-shot, prosa | **50,0 %** | 36,7 % | 35,0 % |
| | | zero-shot, reducida | 36,7 % | 21,7 % | 21,7 % |
| | | few-shot | 45,0 % | **38,3 %** | **38,3 %** |
| Qwen2.5-7B | 7,6 B | zero-shot, prosa | 40,0 % | 8,3 % | 8,3 % |
| | | zero-shot, reducida | 38,3 % | 6,7 % | 6,7 % |
| | | few-shot | 43,3 % | 31,7 % | 31,7 % |
| Phi-3.5-mini | 3,8 B | zero-shot, prosa | 43,3 % | 6,7 % | 5,0 % |
| | | zero-shot, reducida | 35,0 % | 5,0 % | 5,0 % |
| | | few-shot | 35,0 % | 23,3 % | 16,7 % |
| **Constante trivial** | — | (sin leer nada) | **35,0 %** | — | — |

### Cada modelo colapsa en una categoría distinta

Predicciones en zero-shot con prosa, sobre 60 casos:

| Modelo | `sí` | `no` | `condicional` |
|---|---|---|---|
| Qwen2.5-7B | 9 | **48** | 3 |
| Phi-3.5-mini | 20 | 8 | **31** |
| Granite-3.1-8B | **33** | 4 | 23 |
| *lo correcto* | *18* | *21* | *21* |

Tres arquitecturas, tres manías incompatibles entre sí. Ninguna extrae la respuesta del
expediente: cada una responde la categoría que trae de fábrica.

---

## Los cuatro mecanismos de falla

| | Mecanismo | Evidencia |
|---|---|---|
| **E1** | No representa *"cursándola ahora"* como estado propio | sobre 18 casos con prerrequisito en curso, el mejor modelo acierta 12; la categoría `condicional` se subproduce (Qwen 0–5 de 21) o se sobreproduce (Phi hasta 31) |
| **E2** | Depende de que la pregunta le apunte al dato | al reducir la consulta a código y período, con el historial completo aún en el prompt, el acierto cae en los tres: −1,7 / −8,3 / −13,3 puntos |
| **E3** | No copia un identificador que tiene delante | Phi degrada `R-CREDITOS-MINIMOS` en `R-CREDITOS-MINIMISMU`, `-MINIMISIMO`, `-MINIMISMUDA`. 35 instancias en Phi, 0 en Qwen, 4 en Granite |
| **E4** | Se contradice dentro de su propia respuesta | responde `sí` citando una regla que bloquea: hasta 28 de 60 en Qwen con la pregunta reducida, usando 4 identificadores distintos para los 60 casos |

### El few-shot arregla la forma, no el razonamiento

| | Contradicciones | Alucinaciones | Acierto de regla | Acierto de decisión |
|---|---|---|---|---|
| Phi | 18 → 11 | 35 → 4 | 6,7 % → 23,3 % | 43,3 % → 35,0 % |
| Qwen | 3 → 0 | 0 → 0 | 8,3 % → 31,7 % | 40,0 % → 43,3 % |
| Granite | 3 → 0 | 4 → 0 | 36,7 % → 38,3 % | 50,0 % → 45,0 % |

Tres modelos de tres familias, el mismo patrón. Eso delimita con evidencia qué puede lograr
el trabajo de prompt del Deliverable 2 y qué queda para el harness del Deliverable 3.

---

## Factibilidad de ejecución

| | |
|---|---|
| Hardware | GPU T4 gratuita de Google Colab, cuantización a 4 bits |
| VRAM ocupada | ≈ 5 GB de 15 disponibles |
| Tiempo por caso | 4,2 s (Phi) a 15,0 s (Granite) |
| Tokens de entrada | 3.253 a 3.963 |
| Corrida completa | 9 condiciones, ≈ 81 min de inferencia |
| Salidas con JSON válido | **539 / 540** |

El formato casi nunca falló: lo que falló, falló razonando.

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

**Generación hacia atrás.** No se sortean historiales a ver qué sale: se elige primero qué
regla debe decidir y se construye el historial que la produce. Así la distribución de
respuestas se controla en vez de sufrirse.

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

---

## Estructura

```
deliverable-1/
├── datos/
│   ├── malla.json           grafo de prerrequisitos y reglas, congelado
│   └── casos.jsonl          60 casos etiquetados por el verificador
├── scripts/
│   ├── verificador.py       ground truth determinista + 9 casos de control
│   ├── generador.py         generación hacia atrás y control de balance
│   ├── prompt.py            construcción del prompt y parseo de la salida
│   └── runner.py            corrida, métricas y reanudación
├── resultados/              (ver nota)
├── poster/poster.tex        el entregable, una página en LaTeX
└── corrida_final_colab.ipynb
```

### Reproducir

```bash
python scripts/verificador.py            # 9/9 casos de control
python scripts/generador.py              # regenera los 60 casos
python scripts/runner.py --modelo ibm-granite/granite-3.1-8b-instruct --condicion zero_shot
```

La generación es determinista (`do_sample=False`); la corrida se reprodujo idéntica al
repetirla tras perder la sesión de Colab.

> **Sobre `resultados/`.** Las nueve corridas se ejecutaron en una sesión de Google Colab que
> expiró antes de que descargáramos los archivos caso a caso. Todas las métricas reportadas en
> este README provienen de esas corridas y están completas. Los comandos de arriba las
> reproducen: la generación es determinista, así que los números salen idénticos.

---

## El proyecto completo

| Entregable | Fecha | Contenido | Estado |
|---|---|---|---|
| **D1** | 31 ago | Tarea, modelo y baseline | ✅ |
| D2 | 30 sep | Prompt y contexto — ataca E1 y E2 | ⏳ |
| D3 | 31 oct | Harness: consulta al grafo (E3), validador (E4) | ⏳ |
| D4 | 30 nov | Resultados contra este baseline | ⏳ |
