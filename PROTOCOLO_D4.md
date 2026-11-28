# Protocolo del D4: entrenamiento del Intérprete y medición sobre la prueba sellada

Este archivo se escribió y se subió al repositorio **antes** de entrenar el adaptador y antes de
correr cualquier sistema sobre la prueba sellada. Su fecha en el historial de git es la evidencia
de que nada se ajustó a los resultados. El diseño y sus razones están en `PLAN_D4.md`; aquí
quedan solo las reglas.

## Lo que queda congelado

| | |
|---|---|
| Modelo base | `microsoft/Phi-3.5-mini-instruct`, 4 bits NF4 con cómputo fp16, T4 de Colab |
| Agente ajustado | el Intérprete (A). El Resolvedor y el Verificador quedan con la base |
| Sistema | el de la v4 del D3, sin cambios de código ni de prompts |
| Prompts (hash corto) | `interprete.md` 485ade8387 · `resolvedor.md` d4dfb0dde1 · `verificador.md` d8751e096d |
| Prompt del control | `d4/interprete_control.md` a6c254ac24 |
| Generación | greedy, 256 tokens de salida, cortada al cerrar el primer JSON |

## Datos de entrenamiento

`datos/entrenamiento_d4/`, armados el 24 de noviembre después del sello de la prueba. sha256 con
saltos de línea LF:

```
490510a88f02d889e334703e91d856b18c0fccd582a8d01474af2d97d5b5532d  entrenamiento.jsonl  1.286 pares
60fcd7cacc32951c4fd172c22319bc932fe163e3c607848e376b3e0780e25e35  validacion.jsonl       143 pares
```

Revisión manual cerrada antes de este protocolo. Primera muestra de 60: Renato 30 de 30
correctas, Joaquín 23 de 30 (las 7 por apodos poco naturales, con la etiqueta bien copiada).
Segunda muestra de 60, con la opción "suena raro pero se entiende": **0 incorrectas** (Joaquín 27
correctas y 3 "suena raro", Renato 29 y 1). La regla escrita el 25 de noviembre decía que con 0 o
1 incorrectas se entrena sin regenerar, así que se entrena con estos datos.

## Entrenamiento

`scripts/entrenar_d4.py` con la receta del plan: QLoRA, LoRA de rango 16, alpha 32, dropout
0,05 en todas las capas lineales, learning rate 2e-4 lineal con 3 pasos de calentamiento, batch 2
con 4 de acumulación (8 efectivo), pérdida solo sobre la respuesta, `max_length` 2048, semilla
20261114, **2 épocas** (161 pasos cada una). La pérdida de validación se mide cada 23 pasos, que
cae justo al final de cada época. El adaptador de cada época se guarda en Drive y el entrenamiento
retoma desde ahí si la sesión se cae. No se cambia ningún hiperparámetro después de ver una curva.

## Elección de la época

Se corre el sistema completo con el adaptador de cada época sobre los 60 casos del piloto
(`datos/piloto_d4/piloto.jsonl`, de desarrollo, nunca de prueba). Se queda la época con **más
acierto conjunto**. Si empatan, la de menor pérdida de validación al final de la época. Solo esa
época se publica y se corre sobre la prueba.

## El control

La v4 con el Intérprete base y el prompt v3 con 27 ejemplos más, tomados de
`entrenamiento.jsonl` en orden al azar (semilla 20261202), los que caben sin pasar de 3.600 tokens
de entrada con la consulta más larga de los datos de entrenamiento (3.524 medidos). Así el control
ve en el prompt los mismos datos que el ajuste ve en los pesos. Antes de la prueba se corre sobre
los 60 del piloto. **Si más de 3 de los 60 casos tienen alguna respuesta ilegible**
(`ramas.ilegibles`, la falla que rompió al control del piloto), el control
se rehace con la mitad de los ejemplos y se vuelve a revisar en el piloto. Si no, queda como está.

## Hugging Face

El adaptador elegido se publica en un repositorio público de Hugging Face. La corrida sellada lo
carga **desde Hugging Face en la revisión fija** (el hash del commit en HF), no desde una copia
local, y verifica que el sha256 de `adapter_model.safetensors` sea el mismo que salió del
entrenamiento. Esa revisión queda en cada fila de resultados, el README y el PDF.

## La prueba sellada

`datos/prueba_d4/` (commit `6b54eac`, sellos en `SELLO.txt`): 239 casos, 60 de plantilla y 179
redactados (60 `_c_inscrita_actual`, 60 `_c_inscrita_proximo`, 59 de otros constructores). Se
corre **una sola vez**. Si la sesión se cae, se retoma en el mismo commit; no se repite un sistema
ya terminado.

| Fila | Qué es | Cómo se corre |
|---|---|---|
| Baseline few-shot (D1) | Phi con 3 ejemplos, sin sistema | `runner.py --condicion few_shot` |
| Sistema del D2 | lectura con un modelo y reglas en código | `runner_d2.py --variante codigo --modo encadenado` |
| Sistema del D3 (v4) | tres agentes, todos con la base | `runner_d3` configuración `completo` |
| **Sistema del D4** | la v4 con el Intérprete ajustado | `completo` con `ConAdaptador` |
| **Control** | la v4 con el Intérprete base y el prompt del control | configuración `control_d4` |
| Regla fija | sin modelo, el piso | `runner_d3.py --modelo-falso`, en local |

## Análisis fijado

En `scripts/analisis_d4.py`, que se escribe antes de ver resultados y se prueba sobre la
corrida del piloto.

- **Métrica principal:** acierto conjunto (decisión y regla correctas), el criterio del D1.
- **Comparación principal:** D4 contra D3 sobre los 239, McNemar exacto bilateral, α = 0,05.
- **Secundaria:** D4 contra el control, igual.
- **También se reporta**, sin prueba de significancia propia: acierto estricto (ramo y período),
  acierto del período del Intérprete, y todo lo anterior por bloque (plantilla,
  `_c_inscrita_actual`, `_c_inscrita_proximo`, otros redactados).
- **Lo que no debe romperse:** respuestas ilegibles del Intérprete, casos que el D3 acierta y el
  D4 falla (se listan todos), y uso de `sin_ramo` y de la revisión.
- **Caso de falla:** el primer caso redactado, en orden de `id_d4`, que el D4 falla en acierto
  conjunto. Se explica con su traza.
- Se reporta lo que salga, aunque no haya diferencia o el D4 pierda. Después de ver la prueba no
  se cambia el sistema, el adaptador ni el control.
