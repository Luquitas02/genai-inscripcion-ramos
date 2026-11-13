# Instrucción exacta al subagente que redactó `piloto.csv` (13 nov 2026)

Lo que sigue se entregó tal cual a un subagente de Claude (Anthropic) sin acceso al repositorio,
junto con las 60 filas (id, ramo, cuándo, otro ramo, estado del otro ramo, estilos). No vio los
prompts de los agentes, la herramienta de búsqueda, el generador ni sus plantillas.

---

Eres un estudiante de Ingeniería Civil Industrial de la Universidad de Concepción (Chile) que le
escribe por WhatsApp a la secretaria de la carrera o a un compañero para preguntar si puede
inscribir un ramo. Vas a escribir 60 mensajes, uno por fila.

Contexto del calendario: hoy es noviembre de 2026. El semestre en curso es el segundo semestre
de 2026 (2026-2, de agosto a diciembre). El semestre siguiente es el primero de 2027 (2027-1),
que empieza en marzo de 2027, después del verano.

Cada fila dice:
- `ramo`: el ramo por el que preguntas.
- `cuando`: ACTUAL si quieres inscribirlo en el semestre en curso (2026-2); PROXIMO si quieres
  inscribirlo en el semestre siguiente (2027-1).
- `otro_ramo` y `estado_otro`: si no están vacíos, el mensaje tiene que mencionar ese otro ramo
  y su estado (por ejemplo, que lo estás cursando ahora o que lo reprobaste), como lo haría un
  estudiante que sospecha que es un requisito.
- `periodo_estilo`: cómo dices cuándo quieres inscribir el ramo consultado.
  - `relativo`: con palabras relativas al hoy ("el próximo", "el otro semestre", "este mismo",
    "ya", "el que sigue"...), variadas, sin repetir siempre la misma.
  - `calendario`: con referencias de calendario ("en marzo", "después del verano", "este segundo
    semestre", "el primer semestre del otro año", "antes de que termine el año"...), variadas.
  - `implicito`: sin una frase de tiempo directa; que se entienda por el contexto ("¿alcanzo a
    meterlo todavía?", "¿lo puedo tomar de una?", "para cuando vuelva de vacaciones"...).
    Tiene que quedar claro para una persona cuál de los dos semestres es.
- `ramo_estilo`: `nombre` usa el nombre del ramo (puede ir en minúsculas, sin tildes o con un
  número escrito distinto, como "calculo 3" o "la III"); `apodo` usa como le dicen los
  estudiantes, una abreviación o sigla ("opti", "edo", "pcp", "evapro", "admin"...), siempre que
  un compañero de la carrera la entienda.

Reglas:
- Escribe como un estudiante real: informal, a veces sin tildes ni signos, con saludos o
  rodeos, de una a tres oraciones. Varía la forma de los mensajes entre filas.
- Un solo ramo consultado por mensaje. El otro ramo, si lo hay, se menciona como contexto.
- No inventes otros ramos ni datos que la fila no da.
- Que una persona que lea el mensaje sepa, sin dudar, qué ramo consultas y para qué semestre.

Responde con un único objeto JSON {"<id>": "<mensaje>", ...} con las 60 filas.
