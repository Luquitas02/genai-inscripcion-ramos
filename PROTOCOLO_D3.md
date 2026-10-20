# Protocolo de la corrida final del Deliverable 3

Este archivo se escribió y se subió al repositorio **antes** de correr lo que describe. Su fecha
en el historial de git es la evidencia de que nada de lo que sigue se ajustó a los resultados.
Es el mismo procedimiento del `PROTOCOLO_30SEP.md` del D2.

## Lo que queda congelado

Desde el commit que sube este archivo no cambian el código, los prompts ni los casos. La
corrida final se hace con `COMMIT` apuntando a ese commit en `corrida_d3_colab.ipynb`.

| | |
|---|---|
| Modelo | `microsoft/Phi-3.5-mini-instruct`, revisión `2fe1924`, 4 bits NF4, T4 de Colab |
| Generación | greedy, 256 tokens de salida, cortada al cerrar el primer JSON |
| Lectura de cada salida | el primer objeto JSON válido |
| Topes | 2 rechazos, 2 búsquedas extra por vuelta, 12 llamadas por caso |
| Prompts (hash) | `interprete.md` 485ade8387 · `resolvedor.md` d4dfb0dde1 · `verificador.md` d8751e096d · `ablaciones/interprete_sin_descomposicion.md` 21a207f753 · `ablaciones/resolvedor_catalogo.md` ac1b32212c |

Los prompts son la versión 4, elegida en el conjunto de desarrollo con la regla escrita en
`PLAN_D3.md` antes de correrla: 44 de 52 en los casos de plantilla y 20 de 21 en el chequeo
de robustez con preguntas de desarrollo redactadas fuera de las plantillas (la regla fija saca
33/52 y 11/21). Ningún caso de prueba se miró para ajustarlos.

## Conjuntos de prueba

| Conjunto | Archivo | Casos |
|---|---|---|
| Originales | `datos/casos.jsonl` | 60 |
| Nuevos | `datos/casos_nuevos.jsonl` | 60 |
| Redactados fuera de las plantillas | `datos/casos_redactados.jsonl` | 30 |

## Lo que se corre

Las seis configuraciones de `orquestador.py` sobre los tres conjuntos (sección 6 del notebook):
`completo`, `sin_descomposicion`, `sin_herramienta`, `sin_verificador`, `sin_ejemplos` y `top1`.

Además, sobre los redactados, el baseline few-shot del D1 (`runner.py --condicion few_shot`) y
el sistema del D2 (`runner_d2.py --variante codigo --modo encadenado`). Sobre originales y
nuevos esas dos filas ya están medidas y no se vuelven a correr:
`Phi-3.5-mini-instruct__few_shot__prosa[__casos_nuevos].raw.jsonl` y
`pipeline__Phi-3.5-mini-instruct__codigo__encadenado[__casos_nuevos].raw.jsonl`.

La regla fija sin modelo (`runner_d3.py --modelo-falso`) se corre en local sobre los tres
conjuntos. Es determinista.

## Métricas

**Principal:** acierto conjunto, decisión y regla correctas, el criterio del D1 y el D2.

**Secundarias:** acierto de ramo y de período, recall@5 de T1, activación de cada rama
(rechazos del Verificador, búsquedas extra, topes, `citas_fuera`), llamadas, tokens y segundos
por caso.

**Sin los ambiguos.** En originales y nuevos se reporta también el acierto excluyendo los
casos cuya mención del ramo consultado sirve para más de un ramo, según
`diagnostico_d3.es_ambigua`: 9 en originales y 6 en nuevos. En los redactados no se excluye
ninguno.

## Hipótesis y pruebas

**H1.** El sistema de agentes completo acierta más casos que el sistema del D2. Se prueba con
McNemar exacto bilateral, p < 0,05, sobre los 150 casos juntos. Se reporta además por conjunto.

**Ablaciones.** Cada configuración se compara con `completo` en los 150 casos, con McNemar
exacto. Una diferencia de 3 casos o menos se reporta como dentro del ruido, sin importar su
signo. Se reportan todas, incluidas las que muestren que una técnica no aporta o empeora.

**Regla fija.** Se reporta su acierto en los tres conjuntos, sin prueba.

## Caso de falla y casos del video

Se eligen con estas reglas, aplicadas en este orden a la corrida `completo`:

1. **Caso de falla:** el primer caso de los redactados, en orden de `id_original`, donde el
   sistema falla. Si no falla ninguno, el primero de los nuevos.
2. **Video, caso directo:** el primer redactado donde el sistema acierta con 3 llamadas.
3. **Video, caso con decisión:** el primer caso, mirando redactados, originales y nuevos en ese
   orden, donde el Verificador rechazó o el Resolvedor buscó de nuevo y el sistema acertó. Si no
   hay ninguno, el primero con cualquiera de esas ramas, acierte o no.
4. **Video, falla:** el caso de falla.

## Si aparece un error durante la corrida

Si un error de código invalida resultados, se corrige, se registra en `PLAN_D3.md` con su
efecto y se vuelven a correr todas las configuraciones afectadas. No se corrige nada que no
sea un error, y no se cambia ningún prompt.
