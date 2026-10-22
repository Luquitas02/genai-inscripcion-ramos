# Protocolo de la réplica de la v4 sobre los 180 casos sellados

Este archivo se escribió y se subió al repositorio **antes** de correr lo que describe, como el
`PROTOCOLO_D3.md`. Su fecha en el historial de git es la evidencia de que nada se ajustó a los
resultados.

## Por qué se corre

La v4 se midió el 20 de octubre sobre 150 casos con `PROTOCOLO_D3.md`: 132 de 150 contra 96 del
D2 (39 a 3, p = 5,6e-9). Ese resultado sigue valiendo. Pero después esos 150 casos se usaron
para diagnosticar y diseñar la v5, así que ya no sirven para medir nada nuevo. Además, la parte
redactada fuera de las plantillas tenía solo 30 casos.

La v5 no superó a la v4 en desarrollo (`PLAN_D3.md`, 22 de octubre) y se entrega la v4. Los 180
casos sellados el 21 de octubre para la v5 quedaron sin usar. Nadie los usó para ajustar nada.
Correr la v4 sobre ellos dice si su resultado se repite en casos nuevos, con el doble de
preguntas redactadas. Esto reemplaza la decisión del 22 de octubre de no correr la v4 sobre
estos casos, que se tomó cuando la v4 iba a ser solo una fila al lado de la v5.

## Lo que queda congelado

El sistema es el de la corrida del 20 de octubre. El código de los agentes y los prompts del
commit que sube este archivo son los del commit `9158550`. Entre ese commit y este solo cambian
scripts de análisis, demo y preparación de datos, el visor de trazas y una opción
`--dir-salida` del runner que aquí no se usa.

| | |
|---|---|
| Modelo | `microsoft/Phi-3.5-mini-instruct`, revisión `2fe1924`, 4 bits NF4, T4 de Colab |
| Generación | greedy, 256 tokens de salida, cortada al cerrar el primer JSON |
| Lectura de cada salida | el primer objeto JSON válido |
| Topes | 2 rechazos, 2 búsquedas extra por vuelta, 12 llamadas por caso |
| Prompts (hash) | `interprete.md` 485ade8387 · `resolvedor.md` d4dfb0dde1 · `verificador.md` d8751e096d |

La réplica se corre con `replica_v4_colab.ipynb`, que clona el repositorio en el commit que sube
este archivo. Cada fila guarda el commit con que se corrió.

## Conjuntos

Los tres sellados el 21 de octubre (`datos/prueba_v5/SELLO.txt` tiene el sha256 de cada uno):

| Conjunto | Archivo | Casos |
|---|---|---|
| Plantilla A | `datos/prueba_v5/plantilla_a.jsonl` | 60 |
| Plantilla B | `datos/prueba_v5/plantilla_b.jsonl` | 60 |
| Redactados a ciegas | `datos/prueba_v5/redactados.jsonl` | 60 |

Lucas leyó las 60 redactadas para validarlas antes de sellarlas. Claude no ha leído ninguna
pregunta. Al revisar el formato de los archivos para escribir este protocolo vio el primer caso
de `plantilla_a`, y contó la marca `filtro_v5` de cada caso sin mirar las preguntas. Como no se
ajusta nada, eso no cambia lo que se mide.

## Lo que se corre

Sobre los tres conjuntos: la v4 completa (`runner_d3.ejecutar(modelo, 'completo', ...)`), el
baseline few-shot del D1 (`runner.py --condicion few_shot`) y el sistema del D2
(`runner_d2.py --variante codigo --modo encadenado`). La regla fija sin modelo
(`runner_d3.py --modelo-falso`) se corre en local. Es determinista.

**No se corren las ablaciones.** Se quedan con su medición sobre los 150 casos del 20 de
octubre, y el documento lo dice.

## Métricas e hipótesis

El análisis completo es `scripts/analisis_replica_v4.py`, escrito antes de correr y probado con
los resultados de los 150 casos, cuyas cifras reproduce.

**Principal:** acierto conjunto, decisión y regla correctas, el mismo criterio del D1, el D2 y
la corrida del 20 de octubre.

**H1 (réplica).** La v4 acierta más casos que el D2 en los 180. Se prueba con McNemar exacto
bilateral, p < 0,05.

**Secundarias:** lo mismo por conjunto, con el criterio estricto (también ramo y período
correctos) y sin los 8 casos de plantilla cuya pregunta repite una de un conjunto anterior. La
v4 contra el baseline y contra la regla fija. Acierto sin los ambiguos (solo plantilla, según
`diagnostico_d3.es_ambigua`). Extracción de ramo y período, recall@5 de T1, ramas activadas,
llamadas, tokens y segundos por caso.

## Cómo entra al documento

Esto se fija antes de ver los resultados, para no elegir después qué cifra mostrar:

- La tabla de resultados lleva los 180 al lado de los 150 para baseline, D2, regla fija y v4, y
  el texto reporta H1 de la réplica con sus pares discordantes **cualquiera sea el resultado**.
- Si la réplica no cumple H1, o si la v4 cae en las redactadas, el documento lo dice así, en
  la misma frase que la cifra de los 150.
- El caso de falla y los casos del video siguen siendo los de la corrida del 20 de octubre,
  elegidos con las reglas de `PROTOCOLO_D3.md`. No se vuelven a elegir.
- Las ablaciones siguen siendo las de los 150 casos.

## Si aparece un error durante la corrida

Si un error de código invalida resultados, se corrige, se registra en `PLAN_D3.md` con su
efecto y se vuelve a correr lo afectado. No se corrige nada que no sea un error, y no se cambia
ningún prompt.
