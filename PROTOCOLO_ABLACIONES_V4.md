# Protocolo de las ablaciones de la v4 sobre los 180 casos sellados

Este archivo se escribió y se subió al repositorio **antes** de correr lo que describe, como
`PROTOCOLO_D3.md` y `PROTOCOLO_REPLICA_V4.md`.

## Por qué se corre

La auditoría del 22 de octubre, con cuatro revisores independientes, encontró dos problemas en
las ablaciones de la corrida del 20 de octubre:

1. No quitan siempre una sola técnica. `sin_descomposicion` quita a la vez la lista de los otros
   ramos y la regla del verbo.
2. Hay técnicas en uso que nunca se midieron: citar antes de decidir ("quotes first" en la
   Lecture 5), en el Intérprete y en el Verificador, y los 2 ejemplos del Verificador.

Además, esas ablaciones están sobre los 150 casos, que después se usaron para diseñar la v5.
La evidencia principal del documento ya está en los 180 casos sellados (réplica, commit
`7006c9e`). Las ablaciones se repiten ahí, una técnica a la vez.

## Lo que queda congelado

El sistema es la v4 de la réplica. Los prompts del sistema completo no cambian: `interprete.md`
485ade8387, `resolvedor.md` d4dfb0dde1 y `verificador.md` d8751e096d. Cada ablación cambia un
solo prompt por una variante. Las variantes nuevas las genera `scripts/gen_ablaciones_v4.py`
con reemplazos exactos sobre los prompts de la v4, y `--check` comprueba que los archivos
guardados son los generados.

El modelo, la generación, la lectura de las salidas y los topes son los de `PROTOCOLO_D3.md`.
El notebook se detiene si Hugging Face entrega otra revisión de Phi-3.5-mini que la `2fe1924`.
Se corre con `ablaciones_v4_colab.ipynb`, que clona el commit que sube este archivo.

## Las configuraciones

Cada fila se compara con la v4 completa de la réplica sobre los mismos 180 casos. El mecanismo
al que apunta cada técnica se fija aquí, antes de ver resultados. M1 es copiar el código, M2
aislar la mención del ramo consultado, M3 el período.

| configuración | qué se quita | agente | apunta a | prompt (hash) |
|---|---|---|---|---|
| `sin_herramienta` | la búsqueda T1: el Resolvedor recibe el catálogo de 61 | B | M1 | `resolvedor_catalogo.md` ac1b32212c |
| `sin_ejemplos` | los 4 ejemplos del Intérprete | A | M2, M3 | `interprete.md` sin el bloque de ejemplos |
| `sin_lista_otros` | el campo "otros", la lista de los demás ramos | A | M2 | `interprete_sin_lista_otros.md` 04271921b2 |
| `sin_regla_verbo` | "la que acompaña al verbo de inscribir, tomar o meter" | A | M2 | `interprete_sin_regla_verbo.md` 97d8a265cc |
| `sin_citas_interprete` | copiar la frase del período antes de decidirlo | A | M3 | `interprete_sin_citas.md` 610b0faa13 |
| `sin_citas_verificador` | copiar la mención y el período antes de comparar | C | M2, M3 | `verificador_sin_citas.md` ee737480f8 |
| `sin_ejemplos_verificador` | los 2 ejemplos del Verificador | C | M2 | `verificador_sin_ejemplos.md` 98bb48347b |
| `sin_verificador` | el agente entero: la elección va directo a T2 | C | M2, M3 | — |
| `top1` | el Resolvedor: se toma el primer candidato de T1 | B | M1 | — (diagnóstico, no es una técnica de prompting) |

Sin la lista de otros ramos, el Verificador recibe "otras asignaturas nombradas: ninguna". Es
parte de lo que se quita. `sin_descomposicion` no se repite: lo reemplazan `sin_lista_otros` y
`sin_regla_verbo`.

Además se corre el baseline zero-shot del D1 (`runner.py --condicion zero_shot`) sobre los 180,
para que la fila de prompting directo no dependa solo del few-shot.

## Análisis

`scripts/analisis_ablaciones_v4.py`, escrito antes de correr y probado con las ablaciones de los
150 casos, cuyas cifras reproduce (75, 123, 133 y 133; por mecanismo 67, 33 y 34).

Para cada configuración: acierto conjunto en los 180, diferencia con la v4 completa (164), pares
discordantes y McNemar exacto bilateral; lo mismo con el criterio estricto (158). Una diferencia
de 3 casos o menos se reporta como dentro del ruido, sin importar su signo. Por mecanismo:
acierto de ramo en plantilla sin ambiguos (nombre exacto, abreviado, otro ramo nombrado antes),
acierto de período en los 180 y acierto conjunto en las redactadas. También ramas, llamadas y
segundos por caso.

Son comparaciones exploratorias. No hay hipótesis principal y no se corrige por comparaciones
múltiples. Con 180 casos, McNemar necesita al menos 6 a 0 discordantes para p < 0,05.

## Cómo entra al documento

Se fija antes de ver resultados:

- La tabla de técnicas del documento pasa a ser la de los 180 casos, con las nueve filas, cada
  una con su Δ y sus pares discordantes, **cualquiera sea el resultado**. Las que no aporten o
  empeoren se reportan igual.
- La columna "apunta a" es la de este protocolo. Si el efecto aparece en otro mecanismo, se dice
  en el texto, sin cambiar la columna.
- Las ablaciones de los 150 casos quedan en el README como la primera medición.
- El caso de falla y los casos del video no cambian.

## Si aparece un error durante la corrida

Si un error de código invalida resultados, se corrige, se registra en `PLAN_D3.md` con su efecto
y se vuelve a correr lo afectado. No se corrige nada que no sea un error, y no se cambia ningún
prompt.
