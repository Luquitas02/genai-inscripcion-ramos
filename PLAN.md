# Estado y revisión final — Deliverable 1

**Vence:** domingo 31 de agosto de 2026, 23:59 · Canvas
**Vale:** 10% del proyecto semestral (70% de la nota) → 7% de la nota final
**Equipo:** Joaquín Sepúlveda · Renato Saavedra · Lucas Saldivia

---

## Qué está hecho

| Ítem de la rúbrica | Pts | Estado | Dónde está |
|---|---|---|---|
| Especificación de la tarea | 10 | ✅ | póster, columna 1 |
| Diagnóstico de la falla | 10 | ✅ | póster, columna 3 · cuatro mecanismos medidos |
| Modelos candidatos | 10 (+3) | ✅ | póster, columna 3 · tres familias |
| Factibilidad de ejecución | 10 | ✅ | póster, columna 2 |
| Repositorio | 10 | ✅ | github.com/Luquitas02/genai-inscripcion-ramos |
| Formato y escritura | 10 | ✅ | `poster/Deliverable_1.pdf`, una página |

El entregable es `poster/Deliverable_1.pdf`: una página, compilada desde
`poster/poster.tex` con pdfLaTeX.

---

## Verificación de entrega

### El PDF

- [x] Una página, A4 apaisado 297×210 mm
- [x] El JSON del ejemplo se lee `{"decision":"condicional", "regla":"R-DEPENDE-APROBACION"}`, sin la `ç` que introducía babel
- [x] Las cuatro barras de la figura separadas, cada una con su etiqueta sin tocar la de arriba
- [x] Los tres nombres del equipo bien escritos
- [x] Los parámetros de los tres modelos verificados contra su ficha oficial, no contra su nombre
- [x] El link del repositorio sin erratas
- [x] Ninguna columna con texto cortado, ningún título separado de su primera línea

### El repositorio

- [x] Responde público, sin pedir sesión
- [x] El README se ve bien formateado en GitHub
- [x] Ninguna imagen del portal versionada: `malla/` y `Captura.PNG` están en `.gitignore`, verificado contra el remoto

### Coherencia entre ambos

- [x] Las cifras del póster coinciden una a una con las del README
- [x] El link impreso en el póster es el del repositorio que existe

---

## Los números, para contrastar

Constante trivial. Responder siempre lo mismo, sin leer nada, rinde:

| Métrica | Constante | Piso |
|---|---|---|
| decisión | siempre `no` | **35,0 %** (21/60) |
| regla | siempre `R-SIN-IMPEDIMENTO` | **30,0 %** (18/60) |
| ambas | `sí` + `R-SIN-IMPEDIMENTO` | **30,0 %** (18/60) |

Cinco de las nueve condiciones quedan bajo el piso conjunto de 30,0 %.

| Modelo | Condición | Decisión | Regla | Ambas |
|---|---|---|---|---|
| Mistral-7B-v0.3 | zero, prosa | 40,0 % | 35,0 % | 33,3 % |
| | zero, reducida | 36,7 % | 31,7 % | 31,7 % |
| | few-shot | 41,7 % | 45,0 % | 38,3 % |
| Qwen2.5-7B | zero, prosa | 40,0 % | 8,3 % | 8,3 % |
| | zero, reducida | 38,3 % | 6,7 % | 6,7 % |
| | few-shot | 43,3 % | 31,7 % | 31,7 % |
| Phi-3.5-mini | zero, prosa | 43,3 % | 6,7 % | 5,0 % |
| | zero, reducida | 35,0 % | 5,0 % | 5,0 % |
| | few-shot | 35,0 % | 23,3 % | 16,7 % |

Colapso por modelo, zero-shot prosa (correcto: 18 / 21 / 21):

| Modelo | sí | no | condicional |
|---|---|---|---|
| Qwen | 9 | 48 | 3 |
| Phi | 20 | 8 | 31 |
| Mistral | 50 | 6 | 4 |

---

## Trabajo de septiembre, en este orden

1. **Recuperar los resultados crudos.** Las nueve corridas se perdieron con la sesión de
   Colab. Relanzarlas toma ~50 min con `corrida_final_colab.ipynb`, descargando después de
   cada modelo. No cambia ningún número porque la generación es determinista, pero habilita
   el acierto por nivel de dificultad, que el ROADMAP declara y que todavía no se reporta.
2. **Rebalancear el conjunto de prueba sobre la regla.** Hoy `R-SIN-IMPEDIMENTO` cubre 18 de
   los 60 casos y tres identificadores cubren el 65 %, lo que deja el piso trivial de la
   regla en 30 %. Balancear por regla y subir a unos 120 casos baja ese piso y estrecha los
   intervalos.
3. **Ampliar los ejemplos del few-shot.** Los tres actuales no cubren `R-EXCEPCION-PRERREQ`,
   `R-CREDITOS-MINIMOS`, `R-TOPE-MAX` ni `R-ESPECIAL-*`, que juntas son 18 de los 60 casos.

---

## Riesgos conocidos, ya mitigados

| Riesgo | Cómo quedó |
|---|---|
| Grafo de prerrequisitos mal transcrito | auditado: sin ciclos, créditos consistentes, un umbral corregido |
| Tarea demasiado fácil | el mejor modelo falla el 62 % de los casos |
| Test set con atajos superficiales | cruce rasgo × respuesta; se detectaron y cerraron dos |
| Datos personales en el repositorio | `malla/` y `Captura.PNG` excluidos, verificado contra el remoto |
| Póster que no cabe en una página | verificado: 1 página |
| Candidato sobre el techo de 8 mil millones | Granite-3.1-8B declaraba 8,1 B; se reemplazó por Mistral-7B (7 248 023 552 verificados en la ficha) |
| Métricas sin piso de comparación | se reporta la constante trivial de las tres: 35,0 / 30,0 / 30,0 |
| Evidencia que empata con una estrategia trivial | el 12 de 18 del E1 se reporta junto con esa coincidencia; el peso recae en el colapso distribucional |

---

## Lo que viene después

| Entregable | Fecha | Ataca |
|---|---|---|
| D2 · Prompt y contexto | 30 sep | E1 (estado en curso) y E2 (dependencia de que le apunten) |
| D3 · El harness | 31 oct | E3 (consulta al grafo) y E4 (validador) |
| D4 · Resultados | 30 nov | puntaje final contra este baseline |

**Idea del equipo para endurecer la tarea** (Joaquín, 30 de agosto): agregar secciones con
horarios distintos, lo que introduce el choque de horario como regla nueva y activa dos
reglas a la vez. Requiere conseguir la oferta semestral con bloques horarios. La parte de
preferencias en prosa (*"sin clases antes de las 10, viernes libres"*) queda como material
del D3: el modelo traduce preferencias a restricciones y el solver arma el horario.
