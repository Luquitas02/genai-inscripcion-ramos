# Plan de la v6 — que el Resolvedor y el Verificador tengan un rol que se pueda medir

Borrador del 28 de octubre de 2026, para que Lucas lo apruebe antes de tocar código. Nada de
lo que está aquí cambia el sistema entregado: la v4 sigue en `main` y su documento corregido
(commit `7c002ba`) es la entrega de respaldo.

## Por qué

El criterio *Agent design* de la rúbrica pide que cada agente tenga "un rol que la tarea
requiere y que los otros no cubren". En la v4 el Resolvedor y el Verificador no suben el
acierto: tomar el primer candidato de T1 da 168 de 180 y quitar el Verificador da 164, igual que
el sistema completo. Un corrector puede leer eso como que la búsqueda léxica ya cubre el rol del
Resolvedor. Ningún texto evita esa lectura. La v6 busca que cada uno haga algo que ni T1 ni otro
agente hacen, y medirlo en casos nuevos con suficiente tamaño para que se note.

**Éxito:** en un conjunto sellado nuevo, la v6 supera a la v4 con significancia, y quitar el
Resolvedor (top-1) o el Verificador baja el acierto de forma medible.

**No es objetivo:** subir el acierto total a cualquier costo, ni tocar el Intérprete, T1 o T2.

**Sería un fracaso aunque suba el número:** ajustar algo mirando el conjunto nuevo, cambiar la
regla de aceptación después de correr, o que la mejora venga de una regla en código y no de un
agente (eso vuelve a dejar al agente sin rol).

## Lo que dicen los datos

Analicé los 330 casos de prueba de la v4 (150 del 20 de octubre y 180 de la réplica) con la
primera mención que extrajo el Intérprete y la búsqueda T1 sobre ella. Script:
`scripts/oportunidades_v6.py`.

| T1 con la mención del Intérprete | casos | la v4 termina con el ramo mal |
|---|---|---|
| coincidencia exacta y primer candidato correcto | 215 | 6 |
| sin coincidencia exacta y primer candidato correcto | 88 | 2 |
| el correcto está entre los 5, no primero | 19 | 18 |
| el correcto no está entre los 5 | 8 | 8 |

1. **Los 8 que se pierden con el primer candidato correcto** son el error conocido del
   Resolvedor: con "cálculo 3" u "optimización 1" elige el ramo de número vecino. En 6 había
   coincidencia exacta.
2. **Los 19 con el correcto entre los 5 son casi todos menciones ambiguas por construcción**:
   "gestión" (10 casos, sirve para tres ramos), "mecánica" (3), "electiva" (2),
   "complementaria", "práctica", "optimización" y "la I". La pregunta sola no alcanza para
   saber cuál es.
3. **El historial resuelve la mitad de esas ambigüedades.** En los 240 casos de plantilla el
   ramo consultado nunca está cursado: el generador siempre pregunta por un ramo que el
   estudiante no ha tomado. En 9 de los 19, entre los candidatos con ese nombre hay uno solo sin
   cursar, y es el correcto (por ejemplo, "mecánica" con Mecánica aprobada es Mecánica de
   Fluidos). La v4 falla 8 de esos 9. En los otros 10 quedan dos o más sin cursar y la
   ambigüedad no se resuelve.
4. **De los 8 fuera de los 5, 4 son siglas** (PCP dos veces, TI y EDO), 2 son "la I" y en 2 el
   Intérprete extrajo mal la mención. Cuando el Resolvedor busca de nuevo, inventa: PCP lo buscó como "Ingeniería Civil Industrial" y eligió Ingeniería
   Económica. En un caso la pregunta decía "EDO... ecuaciones diferenciales", pero el
   Resolvedor solo recibe la mención, no la pregunta.
5. **El Verificador acepta errores de ramo evidentes.** Aceptó PCP como Ingeniería Económica,
   EDO como Mecánica de Fluidos y "opti 1" como Optimización II. De sus 10 rechazos, 5 fueron
   sobre propuestas correctas. Cuando rechaza un ramo con razón, el caso vuelve al Intérprete,
   que no ve el catálogo.

Techo realista sobre los 330: unos 14 ramos recuperables (6 de coincidencia exacta y 8 que
resuelve el historial). Las siglas dependen de que Phi las conozca, y probablemente no conoce
las locales como PCP.

## El diseño

Dos cambios, uno por agente. La v5 falló por mezclar varios cambios. Aquí cada uno tiene su
ablación.

### Cambio 1 — el Resolvedor decide con lo que T1 no ve

- **El código acepta la coincidencia exacta** (similitud 1,5) sin llamar al Resolvedor, salvo
  que ese ramo ya esté aprobado en el historial. Así el Resolvedor no puede deshacer una
  coincidencia exacta.
- **En el resto, el Resolvedor recibe más información:** la pregunta completa, la mención, los
  otros ramos, y para cada uno de los 5 candidatos su estado en el historial (aprobado,
  inscrito, reprobado, sin cursar) y su semestre en la malla.
- **Prompt nuevo (`resolvedor.md` v3):** el estudiante pregunta por un ramo que todavía puede
  inscribir. Si varios candidatos responden a la mención, se elige con el historial y con los
  otros ramos nombrados. Si la pregunta trae el nombre largo además de la sigla, se usa ese.

El rol queda como: **decidir entre candidatos cuando la búsqueda léxica no alcanza, usando el
historial y la pregunta completa**. T1 no ve ninguna de las dos cosas.

### Cambio 2 — el rechazo del Verificador va a quien puede corregirlo

- `problema: "ramo"` vuelve al **Resolvedor**, con la cita y el motivo del rechazo.
  `problema: "periodo"` vuelve al Intérprete, como hoy.
- El prompt del Verificador no cambia, para medir solo el efecto del enrutamiento. En la v5,
  esta pieza arregló 2 casos y no rompió ninguno.

Con los datos, este cambio aporta poco: 2 o 3 casos de 330. **El diseño no cuenta con que el
Verificador suba el acierto de forma significativa**, y eso se dirá así en el documento.
Si el equipo quiere un Verificador con más peso, ver la pregunta abierta 3.

### Detalles del flujo (decididos por Claude, para revisar)

- **Excepción a la coincidencia exacta:** el código no la acepta si el ramo está aprobado o
  inscrito, porque ninguno de los dos se puede inscribir. Un ramo reprobado sí se acepta: un
  estudiante puede preguntar por él para repetirlo.
- **Rechazo de ramo sobre una coincidencia exacta aceptada por el código:** va igual al
  Resolvedor, con los mismos 5 candidatos y la posibilidad de buscar de nuevo. Es la única
  forma en que se puede deshacer una coincidencia exacta, y requiere que el Verificador la
  objete. Cuenta para `MAX_RECHAZOS`, igual que hoy.
- **Ablaciones de técnicas:** se corren sobre la v6, que es el sistema que se entregaría. En
  `sin_herramienta` no hay T1, así que tampoco hay atajo de coincidencia exacta: el Resolvedor
  recibe el catálogo, como en la v4.
- **Redactadas:** el ramo, el historial y el período salen de `generador.py` con la semilla
  nueva, como en la réplica. Heredan el sesgo del generador, que se declara.
- **Métrica de la regla de aceptación:** acierto conjunto (decisión y regla), el criterio de
  los tres entregables, sobre plantilla y redactadas juntas. El acierto de ramo se reporta
  aparte, como diagnóstico.

### Lo que no cambia

El Intérprete, T1, T2, los topes, el modelo y la configuración de generación.

## Cómo se mide

### Conjunto sellado nuevo

- **Plantilla: 300 casos** generados con el mismo `generador.py` y una semilla nueva, sin
  repetir historial ni pregunta de ningún conjunto anterior. La exclusión va en el protocolo,
  no en el análisis. Se mantiene la mezcla de niveles del generador.
- **Redactadas: 60.** El ramo, el historial y el período salen del generador. Las escribe un
  subagente de Claude que no ve los prompts ni el código. Su instrucción se commitea antes de
  generarlas, y en ella el período va como "2026-2" o "2027-1", no como frase, para que no la
  copie. Se le pide nombrar el ramo como lo haría un estudiante: sigla, apodo o nombre
  incompleto. Lucas las lee antes de sellar y solo puede quitar las que estén mal escritas, sin
  reescribirlas.
- Todo se sella con sha256 en un `SELLO.txt` antes de cualquier corrida.

### Corridas, en orden de prioridad

Todo corre en una sola cuenta gratuita de Colab. El notebook guarda cada caso en Drive apenas
termina y retoma desde ahí si la sesión se cae. Fija la versión de torch y, antes de medir,
corre 10 casos de control de la v4 que deben coincidir con las trazas guardadas.

Unos 7 s por caso con agentes: cada configuración sobre los 360 casos toma unos 45 minutos.

**Nivel 1, imprescindible (unas 5 horas de GPU).** Sin esto no hay v6 que entregar.
- baseline zero-shot y few-shot, y sistema del D2 (los pide la rúbrica);
- v4 completa y v6 completa;
- `top1`: la v6 sin Resolvedor;
- `regla_codigo`: la v6 con el primer candidato sin cursar, elegido en código. Es la
  alternativa sin agente. Si iguala a la v6, el rol del Resolvedor lo cubre el código, y se
  reporta así;
- sin Verificador.

La regla fija corre en local, sin GPU.

**Nivel 2 (unas 2,5 horas).** Qué parte del Resolvedor y del Verificador explica el efecto.
- Resolvedor sin historial;
- Resolvedor sin la pregunta completa;
- Verificador con el enrutamiento de la v4.

**Nivel 3 (unas 4 horas).** Las técnicas de la v4 repetidas sobre la v6: sin T1, sin ejemplos,
sin citas del Intérprete, sin lista de otros, sin regla del verbo. Si no alcanza el cupo, el
documento usa las ablaciones de la v4 sobre los 180, que miden las mismas piezas del
Intérprete y de T1 (la v6 no las cambia), y declara que no se repitieron en el conjunto nuevo.

### Regla de aceptación, escrita antes de correr

La v6 se entrega si en el conjunto nuevo acierta más que la v4 con McNemar exacto p < 0,05. Si
no, se entrega la v4 con el documento de `7c002ba`, y la v6 va como límite medido. Si
`regla_codigo` iguala a la v6, la v6 se entrega igual (es la que mejor acierta) y el documento
lo dice. La regla no se cambia después de ver resultados.

### Datos de desarrollo

Los 330 de prueba anteriores y los 73 de desarrollo pasan a ser desarrollo de la v6. Ahí se
ajusta el prompt nuevo del Resolvedor. Cuando se congela la v6 (commit con los hashes de los
prompts), ya no se toca.

## Orden

1. Lucas aprueba este plan.
2. Código y pruebas sin GPU: orquestador, prompt v3 del Resolvedor, `regla_codigo`, las
   ablaciones nuevas, el notebook con guardado por caso y los casos de control. Lo hace Claude.
3. Corrida de desarrollo en Colab sobre los 403 casos (unos 50 minutos). Se ajusta el prompt
   solo con esos casos.
4. Se congela la v6. Protocolo con la regla de aceptación. Se genera el conjunto de plantilla,
   se commitea la instrucción del redactor, se generan las 60 redactadas, Lucas las lee y se
   sella todo.
5. Corridas finales: nivel 1, después nivel 2 y nivel 3 si hay cupo.
6. Análisis, documento según la regla de aceptación, video, auditoría y Canvas.

Para dejar el sábado 31 libre para el documento y el video, el nivel 1 tiene que terminar el
viernes 30. Si no termina, se entrega la v4, que ya está lista.

## Decisiones tomadas por Claude, para revisar

1. **El Verificador queda solo con el enrutamiento.** Un Verificador que también compare la
   cita con el nombre elegido (los casos de PCP y EDO) sería un tercer cambio, y la v5 falló
   por juntar cambios. El documento dirá que su aporte esperado es bajo.
2. **La regla "pregunta por un ramo que todavía puede inscribir" se declara como apoyada en el
   generador.** En la realidad un estudiante también pregunta por un ramo reprobado para
   repetirlo, y la v6 lo acepta, pero el generador nunca produce ese caso, así que queda sin
   medir.
3. **Con 300 casos de plantilla** se esperan unos 12 aciertos a favor de la v6 (4 % de los
   casos, según los 330 anteriores). Alcanza para p < 0,05 si pierde pocos casos. Más casos
   darían más margen, pero no caben en una cuenta gratuita.
