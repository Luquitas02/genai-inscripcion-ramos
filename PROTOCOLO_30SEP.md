# Protocolo de las corridas del 30 de septiembre

Este archivo se escribió y se subió al repositorio **antes** de correr lo que describe. Su
fecha en el historial de git es la evidencia de que las reglas no se ajustaron a los
resultados.

La auditoría del 30 de septiembre encontró dos huecos en la evidencia del Deliverable 2.

1. **La elección del modelo no mide el trabajo que hace el modelo.** En el sistema final el
   modelo solo hace el paso 1, leer la pregunta y devolver ramo y período. Los tres
   candidatos se compararon en decidir, que ya no es su trabajo, y Qwen no se midió.
2. **Los prompts se eligieron sobre los mismos 60 casos en que se reporta la mejora.** El
   documento lo declara, pero no hay un conjunto que el sistema no haya visto.

Estas corridas cierran los dos. Nada del código del sistema, de los prompts ni del
verificador cambia entre este commit y las corridas.

## Corrida A · los tres candidatos haciendo el trabajo del sistema

Se corre el sistema entregado (`runner_d2.py --variante codigo --modo encadenado`) con
Mistral-7B-Instruct-v0.3 y con Qwen2.5-7B-Instruct sobre los 60 casos de `datos/casos.jsonl`.
Phi-3.5-mini ya está medido con el mismo comando: 35 de 60.

Misma configuración para los tres: 4 bits NF4, generación greedy, 256 tokens de salida,
T4 de Colab, `transformers==5.17.0`.

**Regla de elección.** Se mantiene Phi-3.5-mini salvo que otro candidato acierte al menos 6
casos más que Phi (41 o más de 60) **y** la diferencia sea significativa con McNemar exacto
bilateral, p < 0,05, sobre los casos donde difieren. Si los dos la cumplen, se elige el de
mayor acierto, y ante empate el más chico.

Por qué ese umbral: la rúbrica da el puntaje máximo de economía al modelo más chico, y Phi
tiene la mitad de parámetros que los otros dos. Cambiar a un modelo de 7B solo se justifica
con una mejora que no sea ruido. Con 60 casos, 5 de diferencia no lo es.

Se reporta el resultado de los tres, sea cual sea.

## Corrida B · 60 casos que el sistema no ha visto

Se generan 60 casos nuevos con el mismo generador y la misma distribución (20 por nivel,
decisión balanceada dentro de cada nivel), cambiando solo la semilla: **20260930** en vez de
20260830. Van a `datos/casos_nuevos.jsonl`, y el verificador pone las etiquetas como en el
conjunto original.

Se corre el baseline del Deliverable 1 en su mejor condición (few-shot, prosa, 64 tokens) y el
sistema entregado, los dos con Phi-3.5-mini, sobre esos 60 casos. El criterio de corrección es
el mismo: decisión y regla por coincidencia exacta.

Se reportan los dos números tal como salgan. Si el sistema acierta menos que en el conjunto
original, esa diferencia es la medida de cuánto se ajustaron los prompts al conjunto original,
y va al documento como límite.

Las preguntas repetidas entre los dos conjuntos se cuentan y se declaran.
