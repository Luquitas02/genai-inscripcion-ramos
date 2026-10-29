# Protocolo de las ablaciones de las reglas del Resolvedor

Este archivo se escribió y se subió al repositorio **antes** de correr lo que describe, como
`PROTOCOLO_ABLACIONES_V4.md`, del que es una extensión.

## Por qué se corre

El documento del D3 nombra como técnica del Resolvedor (B) sus reglas sobre siglas y números
("claro y directo", Lecture 5), y dice que no se quitaron. La rúbrica pide medir cada técnica
quitándola una a la vez. Son dos instrucciones distintas del prompt de B y se quitan por
separado.

La segunda es además la que toca el punto débil medido de B: el diagnóstico del 25 de octubre
encontró que B se aparta del primer candidato de T1 sobre todo cuando la mención trae un número
("cálculo 3" → Cálculo II).

## Lo que ya se sabía al escribir este protocolo

Con las corridas que ya están en el repositorio (`be528fb`), en los 33 de 180 casos cuyo ramo
consultado termina en un número, la v4 completa acierta el ramo en 25 y `top1` en 29. En los
otros 147 los dos aciertan 139. No se predice el signo del efecto de quitar la regla de números:
puede ser que la regla evite errores o que los cause.

## Lo que queda congelado

El sistema es la v4. Los prompts del sistema completo no cambian: `interprete.md` 485ade8387,
`resolvedor.md` d4dfb0dde1 y `verificador.md` d8751e096d. Cada configuración cambia solo el
prompt de B por una variante que genera `scripts/gen_ablaciones_v4.py` con un reemplazo exacto
(`--check` comprueba que los archivos guardados son los generados).

El modelo, la generación, la lectura de las salidas, los topes y los 180 casos sellados
(`datos/prueba_v5/`) son los de `PROTOCOLO_ABLACIONES_V4.md`. Se corre con
`ablaciones_b_colab.ipynb`, que clona el commit que sube este archivo y se detiene si Hugging
Face entrega otra revisión de Phi-3.5-mini que la `2fe1924`.

## Las configuraciones

M1 es copiar el código del ramo, que en el D3 es la tarea de T1 y B.

| configuración | qué se quita | agente | apunta a | prompt (hash) |
|---|---|---|---|---|
| `sin_regla_siglas` | "Si el estudiante usó una sigla o una abreviación... busca de nuevo escribiendo el nombre completo" | B | M1 | `resolvedor_sin_regla_siglas.md` 6bc8708b0c |
| `sin_regla_numeros` | "Fíjate en los números: "2", "II" y "dos" son lo mismo, y una asignatura 1 no es la misma que su 2." | B | M1 | `resolvedor_sin_regla_numeros.md` 7ae961e7be |

En `sin_regla_siglas` se mantiene la acción "buscar" con su ejemplo ("una sigla escrita
completa"). Se quita solo la instrucción de usarla ante una sigla.

## Análisis

`scripts/analisis_ablaciones_v4.py`, al que se le agregaron estas dos filas y la sección 5 antes
de correr. Para cada configuración, lo mismo que en el protocolo anterior: acierto conjunto en
los 180 contra la v4 completa (164), Δ, pares discordantes y McNemar exacto bilateral, también
con el criterio estricto (158); una diferencia de 3 casos o menos se reporta como dentro del
ruido. Por mecanismo, la tabla de la sección 2. Y la sección 5: acierto de ramo en los 33 casos
con número y en los otros 147, junto a la v4 completa y a `top1`.

Son comparaciones exploratorias, sin hipótesis principal ni corrección por comparaciones
múltiples.

## Cómo entra al documento

Se fija antes de ver resultados:

- Las dos filas entran a la tabla de técnicas del documento **cualquiera sea el resultado**, con
  su Δ y sus pares, y la frase "No se quitaron... las reglas de B" se corrige.
- El documento dice que estas dos filas se agregaron el 29 de octubre con este protocolo,
  después de las otras ablaciones.
- La sección 5 entra al texto en una oración si `sin_regla_numeros` difiere de la v4 completa en
  más de 3 casos de ramo entre los 33; si no, queda solo en el README.
- El sistema entregado sigue siendo la v4, cualquiera sea el resultado. Si quitar una regla
  mejora el acierto, se reporta como hallazgo para el D4 y no se cambia el prompt.

## Si aparece un error durante la corrida

Si un error de código invalida resultados, se corrige, se registra en `PLAN_D3.md` con su efecto
y se vuelve a correr lo afectado. No se corrige nada que no sea un error, y no se cambia ningún
prompt. Si Colab no tiene GPU disponible antes del 30 de octubre a las 18:00, no se corre y el
documento se entrega como está.
