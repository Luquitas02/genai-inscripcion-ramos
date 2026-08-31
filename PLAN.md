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

**Lo único pendiente: subir `poster/Deliverable_1.pdf` a Canvas.**

---

## Checklist de revisión antes de entregar

### El PDF

- [ ] Es exactamente **una página** (verificado: sí, A4 apaisado 297×210 mm)
- [ ] El JSON del ejemplo se lee `{"decision":"condicional", "regla":"R-DEPENDE-APROBACION"}` sin ninguna `ç`
- [ ] Las cuatro barras de la figura están separadas, cada una con su etiqueta encima sin tocarse
- [ ] Los tres nombres del equipo están bien escritos
- [ ] El link del repositorio no tiene erratas
- [ ] Ninguna columna tiene texto cortado al final

### El repositorio

- [ ] Abre en ventana de incógnito sin pedir sesión
- [ ] El README se ve bien formateado en GitHub
- [ ] **No hay ninguna imagen del portal** (verificado: `malla/` está en `.gitignore`)

### Coherencia entre ambos

- [ ] Los números del póster coinciden con los del README
- [ ] El link impreso en el póster es el del repositorio que existe

---

## Los números, para contrastar

Constante trivial — responder siempre lo mismo, sin leer nada:

| Métrica | Constante | Piso |
|---|---|---|
| decisión | siempre `no` | **35,0 %** (21/60) |
| regla | siempre `R-SIN-IMPEDIMENTO` | **30,0 %** (18/60) |
| ambas | `sí` + `R-SIN-IMPEDIMENTO` | **30,0 %** (18/60) |

Seis de las nueve condiciones quedan bajo el piso conjunto de 30,0 %.

| Modelo | Condición | Decisión | Regla | Ambas |
|---|---|---|---|---|
| Granite-3.1-8B | zero, prosa | 50,0 % | 36,7 % | 35,0 % |
| | zero, reducida | 36,7 % | 21,7 % | 21,7 % |
| | few-shot | 45,0 % | 38,3 % | 38,3 % |
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
| Granite | 33 | 4 | 23 |

---

## Si sobra tiempo, en este orden

1. **Recuperar los resultados crudos.** Las nueve corridas se perdieron con la sesión de
   Colab. Relanzarlas toma ~50 min con `corrida_final_colab.ipynb` y **esta vez hay que
   descargar después de cada modelo**. Suma detalle al repositorio, no cambia ningún número
   porque la generación es determinista.
2. **Que los compañeros revisen el póster.** Sobre todo la redacción de la columna 3, que es
   la más densa.
3. **Nada más.** Todo lo demás está cerrado.

---

## Riesgos conocidos, ya mitigados

| Riesgo | Cómo quedó |
|---|---|
| Grafo de prerrequisitos mal transcrito | auditado: sin ciclos, créditos consistentes, un umbral corregido |
| Tarea demasiado fácil | el mejor modelo falla el 62 % de los casos |
| Test set con atajos superficiales | cruce rasgo × respuesta; se detectaron y cerraron dos |
| Datos personales en el repositorio | `malla/` y `Captura.PNG` excluidos, verificado contra el remoto |
| Póster que no cabe en una página | verificado: 1 página |

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
preferencias en prosa —*"sin clases antes de las 10, viernes libres"*— queda como material
del D3: el modelo traduce preferencias a restricciones y el solver arma el horario.
