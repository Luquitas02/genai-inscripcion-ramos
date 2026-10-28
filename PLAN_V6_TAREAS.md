# v6 — plan de implementación

> **Para agentes:** sub-skill requerida: superpowers:executing-plans (o
> superpowers:subagent-driven-development). Los pasos usan casillas (`- [ ]`).

**Objetivo:** construir la v6 (Resolvedor con historial y pregunta completa, atajo de
coincidencia exacta en código, rechazo de ramo enviado al Resolvedor) sin tocar la v4, y dejar
lista la corrida de desarrollo en Colab.

**Arquitectura:** la v6 son configuraciones nuevas en `orquestador.CONFIGURACIONES` con banderas
explícitas. Las configuraciones de la v4 no cambian y deben reproducir sus trazas byte a byte.
El prompt nuevo del Resolvedor vive en su propio archivo. El notebook escribe los resultados
directo en Drive, y como `runner_d3.correr` hace `flush` después de cada caso, un corte pierde a
lo más un caso.

**Stack:** Python 3 solo con librería estándar en local; Colab T4 con transformers 5.17.0,
accelerate 1.14.0, bitsandbytes 0.50.2 y torch fijado.

**Spec:** `PLAN_V6.md`.

## Restricciones globales

- Las configuraciones de la v4 (`completo`, `top1`, `sin_*`) no cambian de comportamiento:
  `python scripts/runner_d3.py --pruebas` y `python scripts/demo_d3.py --pruebas` siguen
  pasando sin modificar sus expectativas.
- Los prompts van en archivos de `prompts/` con versión en la cabecera, fuera del código.
- Estados del historial: las constantes de `verificador.py` (`aprobada`, `inscrita`,
  `reprobada`, `no_cursada`).
- Coincidencia exacta: `similitud >= 1.5` en el primer candidato de T1.
- "No inscribible": estado `aprobada` o `inscrita`.
- Topes sin cambios: `MAX_RECHAZOS = 2`, `MAX_BUSQUEDAS = 2`, `MAX_LLAMADAS = 12`.
- Nada de esto toca `datos/prueba_v5/` ni los resultados de la v4.

## Foco de revisión

1. **Atajo exacto con el ramo aprobado** ("mecánica" con Mecánica aprobada): debe pasar al
   Resolvedor, no aceptarse. Prueba en la tarea 1.
2. **Rechazo de ramo sobre un atajo exacto:** el Resolvedor debe correr con los mismos 5
   candidatos, y el rechazo cuenta para `MAX_RECHAZOS`. Prueba en la tarea 1.
3. **`regla_codigo` sin ningún candidato inscribible:** devuelve el primero de T1, no falla.
   Prueba en la tarea 1.
4. **Una configuración v4 corrida después de una v6 en el mismo proceso:** no hereda estado
   (los prompts se cargan por configuración). Prueba en la tarea 1.
5. **Retomar en Drive con un prompt cambiado:** `correr` ya lanza `PromptsCambiados`. El
   notebook debe mostrar ese error, no tragárselo. Revisión manual en la tarea 3.

---

### Tarea 1: estados del historial, atajo exacto, `regla_codigo` y enrutamiento

**Archivos:**
- Modificar: `scripts/herramientas.py` (agregar `estado_en_historial`, `semestre_de`)
- Modificar: `scripts/agentes.py` (`resolvedor` acepta entradas nuevas)
- Modificar: `scripts/orquestador.py` (banderas y flujo v6)
- Crear: `prompts/resolvedor_v6.md` (versión 3)
- Pruebas: `scripts/runner_d3.py::_pruebas` (agregar chequeos; el patrón es `corre(respuestas, config)` con modelo falso)

**Interfaces:**
- Produce `herramientas.estado_en_historial(historial: dict, codigo: str) -> str`: el valor
  del historial o `"no_cursada"`.
- Produce `herramientas.semestre_de(codigo: str) -> int`, desde la malla.
- Produce `herramientas.INSCRIBIBLE(estado) -> bool`: `estado not in ("aprobada", "inscrita")`.
- `agentes.resolvedor(...)` agrega los kwargs `pregunta=None`, `historial=None`,
  `revision=None`. Con `historial`, cada candidato se muestra como
  `código  nombre  (similitud)  semestre N  estado`. Con `pregunta`, se llena `{{pregunta}}`,
  y si no, va `(no disponible)`. Con `revision`, se agrega el bloque
  `=== EL VERIFICADOR RECHAZÓ TU ELECCIÓN ===` con la cita y el motivo. Sin estos kwargs, los
  mensajes de la v4 quedan idénticos.
- Banderas nuevas por configuración, con default igual a la v4: `atajo_exacto` (False),
  `historial_resolvedor` (False), `pregunta_resolvedor` (False), `rechazo_ramo_a`
  (`"interprete"`), `prompt_resolvedor` (`"resolvedor.md"`). `resolvedor` admite además
  `"regla_codigo"`.
- Configuraciones nuevas: `v6`, `v6_top1`, `v6_regla_codigo`, `v6_sin_verificador`,
  `v6_resolvedor_sin_historial`, `v6_resolvedor_sin_pregunta`, `v6_enrutamiento_v4`,
  `v6_sin_herramienta`, `v6_sin_ejemplos`, `v6_sin_citas_interprete`, `v6_sin_lista_otros`,
  `v6_sin_regla_verbo`. Cada `v6_*` es `v6` con una sola diferencia. Las de técnicas usan los
  mismos prompts de ablación de la v4. En `v6_sin_herramienta` no hay atajo.
- Campo nuevo en la fila: `ramas["atajo_exacto"]` (bool), y la traza anota
  `{"de": "orquestador", "para": "verificador", "tipo": "atajo"}` cuando el código acepta.

- [ ] **Paso 1: pruebas que fallan**, agregadas a `_pruebas()`:
  - `estado_en_historial({"541271": "aprobada"}, "541271") == "aprobada"` y
    `estado_en_historial({}, "541340") == "no_cursada"`;
  - `v6` con mención "Optimización 1" (exacta, sin cursar): el Resolvedor no se llama (la
    respuesta falsa del Resolvedor no se consume) y `ramas["atajo_exacto"]` es True;
  - `v6` con mención "mecánica" y historial `{"541271": "aprobada"}`: el Resolvedor sí se llama;
  - `v6` con rechazo `problema: "ramo"`: el mensaje siguiente en la traza es
    `verificador → resolvedor`, no `verificador → interprete`, y `rechazos_verificador == 1`;
  - `v6` con rechazo `problema: "periodo"`: vuelve al Intérprete;
  - `v6_regla_codigo` con "gestión" y Gestión y Control de la Calidad aprobada: elige el primer
    candidato inscribible; con todos aprobados, elige el primero de T1;
  - `completo` corrido después de `v6` en el mismo proceso: los mensajes al modelo son
    idénticos a los de `completo` corrido solo.
- [ ] **Paso 2:** `python scripts/runner_d3.py --pruebas` → los chequeos nuevos fallan y los
  29 anteriores pasan.
- [ ] **Paso 3:** implementar. En el flujo de `correr_caso`, con `rechazo_ramo_a ==
  "resolvedor"` y `problema == "ramo"`, se vuelve al bucle del Resolvedor con los últimos
  candidatos de T1 y `revision`, sin llamar al Intérprete.
- [ ] **Paso 4:** escribir `prompts/resolvedor_v6.md` (versión 3, cabecera con lo que cambia
  respecto de la v2). Agrega a la v2: la sección `=== PREGUNTA COMPLETA ===`, que el estudiante
  pregunta por un ramo que todavía puede inscribir, que entre candidatos que responden a la
  mención se elige con el estado y los otros ramos nombrados, y que si la pregunta trae el
  nombre largo además de la sigla, se use ese. Dos ejemplos con ramos que no sean objetivo de
  ningún caso de prueba (mismo criterio que la v2).
- [ ] **Paso 5:** `python scripts/runner_d3.py --pruebas` → todo pasa;
  `python scripts/demo_d3.py --pruebas` → `TODO EN ORDEN`; `python scripts/herramientas.py`
  → 8/8 o más.
- [ ] **Paso 6:** commit `v6: atajo exacto, Resolvedor con historial y pregunta, rechazo de ramo al Resolvedor`.

### Tarea 2: control de reproducibilidad entre máquinas

**Archivos:**
- Crear: `scripts/control_v6.py`

**Interfaces:**
- Consume `runner_d3.cargar_modelo`, `orquestador.correr_caso`.
- Produce `controlar(modelo) -> int`: corre `completo` sobre los casos 0 a 9 de
  `datos/casos.jsonl`, compara cada `crudo` con el de
  `trazas/agentes__Phi-3.5-mini-instruct__completo__casos.jsonl` y devuelve cuántos de los
  10 casos coinciden en todos sus mensajes. Imprime `N de 10 casos iguales a la v4`.
- Con `--modelo-falso` usa las salidas guardadas como respuestas, y debe dar 10 de 10. Esa es
  su autoprueba sin GPU.

- [ ] **Paso 1:** `python scripts/control_v6.py --modelo-falso` → falla (no existe).
- [ ] **Paso 2:** implementar.
- [ ] **Paso 3:** `python scripts/control_v6.py --modelo-falso` → `10 de 10 casos iguales a la v4`.
- [ ] **Paso 4:** commit.

### Tarea 3: notebook de la corrida de desarrollo

**Archivos:**
- Crear: `scripts/gen_notebook_v6.py` (mismo estilo que `gen_notebook_ablaciones_v4.py`)
- Crear (generado): `desarrollo_v6_colab.ipynb`

**Interfaces:**
- Consume la tarea 2 (`control_v6.py`) y `runner_d3.ejecutar(modelo, config, ruta_casos, limite, dir_salida)`.
- Produce `generar(fase: str, commit: str, configs: list[str], conjuntos: list[str]) -> dict`
  (el JSON del notebook). La fase final reutiliza esta función más adelante.

Celdas: (1) `%cd /content`, GPU, clon en `COMMIT`, `pip install` con versiones fijas, torch
incluido; (2) autopruebas: `herramientas.py`, `runner_d3.py --pruebas`,
`demo_d3.py --pruebas`, que deben imprimir `TODO EN ORDEN`; (3) montar Drive,
`SALIDA = /content/drive/MyDrive/genai_v6/<fase>/<COMMIT>`; (4) cargar Phi; (5) control:
`controlar(modelo)` debe dar 10 de 10, y si no, la celda lanza un error y no se sigue; (6) una
celda por configuración y conjunto que llama a `ejecutar(..., dir_salida=SALIDA)`. Es
retomable: volver a correr las celdas 1 a 5 y después la que se cortó. (7) Zip de `SALIDA`
para descargar.

Fase de desarrollo: `configs = ["v6"]`, conjuntos: los 5 de `datos/` (originales, nuevos,
redactados, desarrollo y desarrollo redactados: 60 + 60 + 30 + 52 + 21) y los 3 de
`datos/prueba_v5/` (180), en total 403 casos.

- [ ] **Paso 1:** `python scripts/gen_notebook_v6.py --fase desarrollo` genera el `.ipynb`.
- [ ] **Paso 2:** verificar que el JSON abre (`json.load`) y que `COMMIT` es el commit de la
  tarea 1 o uno posterior que exista en `origin/main`.
- [ ] **Paso 3:** commit y push. Lucas abre el notebook con el link que lleva el hash, no
  `blob/main` (Colab cachea).

### Tarea 4: análisis de desarrollo

**Archivos:**
- Crear: `scripts/analisis_v6.py`

**Interfaces:**
- Produce `comparar(v4: dict, v6: dict) -> dict` sobre filas emparejadas por (conjunto, id):
  acierto conjunto, acierto de ramo, pares de McNemar, p exacto, y cuántas veces actuó el
  atajo, el Resolvedor y el rechazo enviado al Resolvedor.
- CLI: `python scripts/analisis_v6.py --fase desarrollo --dir <carpeta con los .raw.jsonl de la v6>`
  compara contra `resultados/` de la v4 en los mismos 403 casos. Además lista los casos que
  cambian en cada dirección, con la mención y los candidatos, que es lo que se usa para
  ajustar el prompt.
- Autoprueba sin GPU: `--prueba` compara la v4 contra sí misma y debe dar 0 a 0.

- [ ] **Paso 1:** `python scripts/analisis_v6.py --prueba` → falla.
- [ ] **Paso 2:** implementar (el McNemar exacto ya está en `analisis_d3.py`; importarlo).
- [ ] **Paso 3:** `--prueba` → `0 a 0`.
- [ ] **Paso 4:** commit.

### Después de la corrida de desarrollo (plan aparte, cuando haya resultados)

Congelar la v6, `PROTOCOLO_V6.md` con la regla de aceptación de `PLAN_V6.md`, conjunto
`datos/prueba_v6/` (300 de plantilla con exclusiones; instrucción del redactor commiteada;
60 redactadas; `SELLO.txt`), notebook de la fase final con los niveles 1 a 3, y análisis final.
