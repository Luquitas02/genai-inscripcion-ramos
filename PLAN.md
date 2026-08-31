# Plan de trabajo — Deliverable 1

**Vence:** lunes 31 de agosto de 2026, 23:59 · Canvas
**Vale:** 10% del proyecto semestral (70% de la nota) → **7% de la nota final**

---

## Bloqueadores — lo que se necesita antes de avanzar

| # | Qué falta | Bloquea | Quién |
|---|---|---|---|
| B1 | **Malla de Ingeniería Civil Industrial UdeC** (PDF o link) | Fase 2 completa — es el camino crítico | Lucas |
| B2 | **Nombres de los integrantes** | Póster y README | Lucas |
| B3 | **Usuario de GitHub** para crear el repo público | Fase 7 (10 pts) | Lucas |
| B4 | Confirmar acceso a **Google Colab** | Fases 4 y 5 | Lucas |

B1 es el único que detiene el trabajo. Los demás se pueden completar más tarde.

---

## Restricciones fijas

- **Formato:** una sola página, PDF **compilado desde LaTeX**. Multipágina o no-LaTeX → rechazado.
- **Modelos:** open-weight, **máximo 8B parámetros**, que corran en el hardware disponible o en Colab gratis.
- **Sin APIs externas** en ejecución (confirmado por el profesor el 27 de agosto).
- Los tres candidatos pueden ser de **familias y tamaños distintos**.
- **Hardware local:** Intel i3-1005G1, 2 núcleos, 15,7 GB RAM, sin GPU CUDA, 10 GB de disco libre.
- **No hay LaTeX instalado** → se usa Overleaf.

---

## Fase 0 · Estructura y repositorio — 20 min

- [x] Crear `deliverable-1/` con subcarpetas
- [x] `README.md` con la tarea, el equipo y el estado
- [x] `PLAN.md` con este checklist
- [ ] Corregir el `.gitignore` de la raíz (su comentario habla de boletas y cartolas, de otro proyecto)
- [ ] `git init` en la raíz del proyecto
- [ ] Crear el repositorio público en GitHub
- [ ] Primer commit y push

---

## Fase 1 · Especificación de la tarea — 30 min · **ítem 1, 10 pts**

- [ ] Fijar el esquema exacto de entrada (historial: campos y tipos)
- [x] Fijar el esquema exacto de salida (`decision`, `regla`)
- [ ] Escribir el criterio de corrección de cada campo, sin ambigüedad
- [x] Definir las tres reglas del reglamento que entran en juego, con su identificador
- [x] Congelar y declarar la versión de la malla y del reglamento

**Criterio de salida de la fase:** un lector externo puede decir, mirando un caso, si una respuesta
es correcta o no, sin preguntarnos nada.

---

## Fase 2 · Ground truth — 1,5 a 2 h · **camino crítico**

- [x] Extraer el grafo de prerrequisitos de la malla ICI a `datos/malla.json`
- [ ] **Verificar el grafo a ojo contra el PDF de la malla** ← si esto falla, todo el test set queda mal
- [x] Codificar las reglas numéricas del reglamento (tope de créditos, condiciones de inscripción)
- [x] Escribir el verificador determinista en `scripts/verificador.py`
- [x] Probar el verificador contra 5 casos resueltos a mano por el equipo

**Criterio de salida:** el verificador responde correctamente los 5 casos hechos a mano.

---

## Fase 3 · Generador de casos — 1,5 h

- [ ] Generador de historiales sintéticos (aprobados, reprobados, en curso, créditos)
- [ ] Catálogo de plantillas de pregunta con variantes de ambigüedad
- [ ] **Parámetro de nivel (1/2/3)** implementado desde la primera línea, con las cinco perillas
- [ ] Generar 20 casos piloto, repartidos en los tres niveles
- [ ] **Chequeo de balance:** tabla cruzada rasgo × respuesta. Ninguna celda vacía ni dominada
- [ ] Guardar en `datos/casos_piloto.jsonl`

**Criterio de salida:** la tabla cruzada está balanceada y el verificador etiqueta los 20 casos.

---

## Fase 4 · Punto de control — 45 min · **LA DECISIÓN**

- [ ] Montar un candidato de 8B en Colab
- [ ] Correr los 20 casos piloto, zero-shot
- [ ] Calcular acierto de decisión, de regla y conjunto, **por nivel**

| Resultado | Qué hacer |
|---|---|
| Acierto conjunto **20–50%** | Confirmado. Seguir a Fase 5 |
| Acierto **alto** | Endurecer con las perillas y volver a medir. Todavía hay tarde |
| **Alto incluso en nivel 3** | Cambiar a ruta crítica desde prosa, con la tarde por delante |
| Acierto **cercano a 0%** | Ablandar: el baseline necesita señal para poder mejorar en noviembre |

**No avanzar a la Fase 5 sin haber mirado este número.**

---

## Fase 5 · Baseline completo — 2 h · **ítems 2 y 4, 20 pts**

- [ ] Generar 60 casos (20 por nivel)
- [ ] Correr los **3 modelos candidatos**
- [ ] Correr **zero-shot y few-shot básico** — cierra la objeción de "le preguntaste mal"
- [ ] Clasificar cada error en E1 / E2 / E3 / E4
- [ ] **Medir tiempo por caso** ← esto es el ítem de factibilidad de ejecución
- [ ] Guardar corridas crudas en `resultados/`
- [ ] Producir la figura: acierto por nivel

**Criterio de salida:** una tabla de acierto por modelo × nivel × condición, y una tabla de
frecuencia por tipo de error.

---

## Fase 6 · Modelos candidatos — 1 h · **ítem 3, 10 pts + 3 bonus**

- [ ] Elegir **3 modelos open-weight bajo 8B, de familias distintas**
- [ ] Buscar benchmarks reales y **citar la fuente** de cada número
- [ ] Justificar cada uno **por la tarea**, no por el tamaño
- [ ] Argumentar el bonus: candidatos bastante menores a 8B, defendidos por la tarea
- [ ] Verificar que cada uno corre en Colab gratis o en el hardware local

---

## Fase 7 · Repositorio — 30 min · **ítem 5, 10 pts**

- [ ] Subir todo a GitHub, repositorio **público**
- [ ] README completo: la tarea, el equipo con nombres, el estado del trabajo
- [ ] **Abrir el link en ventana de incógnito** para confirmar que funciona sin sesión
- [ ] Pegar el link en el póster

---

## Fase 8 · Póster — 2 h · **ítem 6, 10 pts**

- [ ] Crear el proyecto en Overleaf
- [ ] Estructurar la página por los seis ítems de la rúbrica
- [ ] Figura protagonista: curva de acierto por nivel
- [ ] Tabla chica: taxonomía de errores con frecuencia
- [ ] Dos o tres casos reales mostrados en crudo, con la salida del modelo
- [ ] **Verificar que sea exactamente una página**
- [ ] Compilar a PDF desde LaTeX
- [ ] Subir a Canvas antes de las 23:59

---

## Cómo se reparten los 60 puntos

| Fase | Ítem de la rúbrica | Pts |
|---|---|---|
| 1 | Especificación de la tarea | 10 |
| 2, 3, 4, 5 | Diagnóstico de la falla | 10 |
| 6 | Modelos candidatos | 10 (+3) |
| 5 | Factibilidad de ejecución | 10 |
| 0, 7 | Repositorio | 10 |
| 8 | Formato y escritura | 10 |

---

## Riesgos abiertos

| Riesgo | Mitigación |
|---|---|
| **El grafo de prerrequisitos queda mal** | Verificación a ojo contra el PDF antes de generar casos (Fase 2) |
| **La tarea sale demasiado fácil** | Perillas de dificultad y punto de control de la Fase 4 |
| **El test set tiene atajos superficiales** | Chequeo de balance de la Fase 3 |
| **Colab se desconecta a mitad de corrida** | Guardar resultados incrementalmente, caso a caso |
| **El póster no cabe en una página** | Estructurar por los seis ítems desde el principio, no recortar al final |
