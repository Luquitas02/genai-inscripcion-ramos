# Instrucción exacta a los subagentes que redactaron los datos de entrenamiento del D4 (24 nov 2026)

Se entregó tal cual (lo que va bajo la línea) a subagentes de Claude (Anthropic), uno por lote de
60 filas (`lotes/lote_NN.json`), cada uno con acceso solo a su archivo de filas y a su archivo de
salida (`lotes/lote_NN_redactado.json`). No vieron la prueba sellada, su instrucción, el piloto,
los prompts de los agentes ni el generador.

El lote 01 se redactó sin la línea "Los ejemplos de frases de arriba son solo ideas"; se agregó
porque ese lote repetía "modificación de carga". Los lotes 02 a 21 la tienen.

Es distinta de la instrucción de la prueba (`datos/prueba_d4/INSTRUCCION.md`): otros ejemplos de
frases, otros canales y registros, y pide declarar las palabras usadas. Las mismas dos dimensiones
de estilo (cómo se dice el semestre y cómo se nombra el ramo) porque son la falla que se entrena.

---

Vas a escribir mensajes de estudiantes de Ingeniería Civil Industrial de la Universidad de
Concepción (Chile) que preguntan si pueden inscribir un ramo. Varía quién escribe y por dónde:
un correo a la jefatura de carrera, un mensaje en el grupo del curso, una pregunta a un ayudante,
una nota de voz transcrita, un comentario en un foro. Unos van apurados, otros dan contexto,
algunos escriben con faltas o sin puntuación, otros más formales.

Calendario: es noviembre de 2026. El semestre en curso es 2026-2 (agosto a diciembre). El
siguiente es 2027-1, que parte en marzo de 2027.

Cada fila trae:
- `ramo`: el ramo que el estudiante quiere inscribir.
- `cuando`: ACTUAL = lo quiere inscribir en el semestre en curso (2026-2). PROXIMO = en el
  siguiente (2027-1).
- `otro_ramo` y `estado_otro`: si vienen, el mensaje menciona ese otro ramo y su estado (lo está
  cursando ahora, o lo reprobó), como contexto. Ojo: si el otro ramo se está cursando "ahora",
  esa palabra habla del otro ramo, no de cuándo quiere inscribir el consultado.
- `periodo_estilo`, cómo dice cuándo:
  - `relativo`: palabras relativas a hoy, por ejemplo "el semestre que viene", "al tiro",
    "pal otro", "ahora mismo", "el siguiente", "en este", "más adelante"; inventa otras.
  - `calendario`: fechas o hitos, por ejemplo "en 2027", "el primer semestre", "cuando vuelvan
    las clases en marzo", "para el 2027-1", "este segundo semestre", "en lo que queda del año";
    inventa otras.
  - `implicito`: sin frase de tiempo directa, que se deduzca del contexto, por ejemplo "¿todavía
    estoy a tiempo de agregarlo?", "¿lo dejo planificado para la próxima toma de ramos?",
    "¿alcanzo a sumarlo con la modificación de carga?"; inventa otras. Tiene que quedar claro
    cuál de los dos semestres es.
- `ramo_estilo`: `nombre` = el nombre del ramo, como lo escribiría alguien (minúsculas, sin
  tildes, número romano o arábigo, nombre incompleto pero claro); `apodo` = como le dicen los
  estudiantes (sigla, abreviación, sobrenombre) que un compañero de la carrera reconocería.

Reglas:
- Los ejemplos de frases de arriba son solo ideas: no los copies tal cual, y usa cada uno a lo
  más una vez en todo el lote.
- Una a tres oraciones. Un solo ramo consultado. No inventes ramos ni datos que la fila no da.
- Varía la estructura: no empieces todos igual ni pongas el ramo siempre en el mismo lugar.
- Una persona de la carrera tiene que entender sin dudar qué ramo y qué semestre.

Para cada fila devuelve, además del mensaje, las palabras EXACTAS que usaste (copiadas tal cual
del mensaje, mismas letras):
- `palabras_ramo`: cómo nombraste el ramo consultado.
- `palabras_otro_ramo`: lista con cómo nombraste el otro ramo (vacía si la fila no trae otro).
- `palabras_semestre`: las palabras que dicen o dan a entender cuándo quiere inscribir el ramo
  consultado. Vacío solo si es ACTUAL y no hay ninguna.

Formato: un único objeto JSON
{"<id>": {"mensaje": "...", "palabras_ramo": "...", "palabras_otro_ramo": ["..."], "palabras_semestre": "..."}, ...}
