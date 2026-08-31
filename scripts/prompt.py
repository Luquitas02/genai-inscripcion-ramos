# -*- coding: utf-8 -*-
"""
Construcción del prompt — condición de DIRECT PROMPTING.

Esto es el baseline del proyecto, así que el prompt tiene que ser JUSTO: ni saboteado
para que el modelo falle, ni asistido para que acierte. Le entrega al modelo todo lo
que necesita y le pide la respuesta. Nada más.

Qué recibe el modelo:
  - La malla completa: 61 asignaturas con créditos, semestre, prerrequisitos y umbrales.
  - Las reglas globales: topes de créditos, régimen de excepción, prácticas.
  - El historial del estudiante, con el estado de cada ramo.
  - La pregunta.
  - El formato de salida exigido.

Lo que NO recibe, y es deliberado:
  - Ninguna pista de cuál regla mirar.
  - Ningún recordatorio de que "inscrita" no es "aprobada".
  - Ninguna herramienta. Sumar créditos y recorrer el grafo le toca a él.

Esas tres ausencias son justamente lo que los Deliverables 2 y 3 van a ir agregando.

Dos condiciones:
  zero_shot  — solo la instrucción.
  few_shot   — la instrucción más tres ejemplos resueltos, escritos a mano y ajenos
               al test set. Existe para cerrar la objeción de "le preguntaste mal":
               si el modelo falla también con ejemplos delante, el problema no es
               el fraseo de la instrucción.
"""

import json

from verificador import APROBADA, INSCRITA, REPROBADA, NO_CURSADA

ETIQUETA_ESTADO = {
    APROBADA: "aprobada",
    INSCRITA: "inscrita (cursándola ahora)",
    REPROBADA: "reprobada",
    NO_CURSADA: "no cursada",
}


def render_malla(malla):
    """La malla en texto compacto. Un ramo por línea."""
    lineas = []
    for a in malla["asignaturas"]:
        partes = [f"{a['codigo']}  {a['nombre']} ({a['creditos']} cr, sem {a['semestre']})"]
        if a["prerrequisitos"]:
            partes.append("prerreq: " + ", ".join(a["prerrequisitos"]))
        if a["creditos_minimos"]:
            partes.append(f"mínimo {a['creditos_minimos']} créditos aprobados")
        for r in a["requisitos_especiales"]:
            d = malla["requisitos_especiales_def"].get(r)
            if d:
                partes.append(d["descripcion"].lower())
        lineas.append(" | ".join(partes))
    return "\n".join(lineas)


def render_reglas(malla):
    r = malla["reglas_globales"]
    return "\n".join([
        f"- Máximo de créditos inscribibles en un semestre: {r['R-TOPE-MAX']['valor']}.",
        f"- Mínimo de créditos inscribibles en un semestre: {r['R-TOPE-MIN']['valor']}.",
        f"- Los créditos de las prácticas ({', '.join(r['R-PRACTICAS-NO-SUMAN']['codigos'])}) "
        f"no cuentan para el tope del semestre, pero sí cuentan como créditos aprobados.",
        f"- Un estudiante que inscribe menos de {r['R-EXCEPCION-PRERREQ']['umbral_creditos_inscritos']} "
        f"créditos puede pedir excepción de prerrequisitos por reglamento: en ese caso la "
        f"respuesta es condicional. La excepción cubre solo prerrequisitos, no los umbrales "
        f"de créditos aprobados ni los requisitos de año completo.",
    ])


def render_historial(historial, malla):
    idx = {a["codigo"]: a for a in malla["asignaturas"]}
    lineas = []
    for a in malla["asignaturas"]:
        e = historial.get(a["codigo"])
        if e:
            lineas.append(f"{a['codigo']}  {a['nombre']}: {ETIQUETA_ESTADO[e]}")
    return "\n".join(lineas) if lineas else "(sin asignaturas cursadas)"


INSTRUCCION = """Eres un asistente de inscripción académica de Ingeniería Civil Industrial \
de la Universidad de Concepción.

Se te entrega la malla curricular con sus prerrequisitos, las reglas de inscripción, el \
historial académico de un estudiante y su consulta. Debes decidir si puede inscribir lo que \
pregunta.

El período actual es 2026-2. El próximo período es 2027-1.

Responde ÚNICAMENTE con un objeto JSON de dos campos, sin texto adicional:

{"decision": "sí" | "no" | "condicional", "regla": "<identificador>"}

El campo "regla" debe contener:
- el CÓDIGO de la asignatura faltante, si lo que impide es un prerrequisito (ej: "527150")
- "R-TOPE-MAX" si excede el máximo de créditos del semestre
- "R-CREDITOS-MINIMOS" si no alcanza el umbral de créditos aprobados que exige el ramo
- "R-ESPECIAL-<requisito>" si no cumple un requisito de semestre o año completo
- "R-EXCEPCION-PRERREQ" si aplica el régimen de excepción por carga bajo el mínimo
- "R-DEPENDE-APROBACION" si cumple solo condicionado a aprobar lo que cursa ahora
- "R-SIN-IMPEDIMENTO" si puede inscribir sin restricción
- "R-YA-CURSADA" si el ramo ya está aprobado o inscrito

Si más de una regla impide la inscripción, cita la primera según este orden:
R-YA-CURSADA, R-TOPE-MAX, prerrequisito, R-CREDITOS-MINIMOS, R-ESPECIAL, R-TOPE-MIN."""


EJEMPLOS_FEW_SHOT = [
    {
        "historial": "510140  Física I: aprobada\n525140  Álgebra I: aprobada",
        "consulta": "Quiere inscribir 510150 (Física II) este semestre. Tiene 10 créditos ya inscritos.",
        "respuesta": '{"decision": "sí", "regla": "R-SIN-IMPEDIMENTO"}',
    },
    {
        "historial": "525140  Álgebra I: aprobada\n525150  Álgebra II: inscrita (cursándola ahora)",
        "consulta": "Quiere inscribir 525223 (Ecuaciones Diferenciales) este semestre. Tiene 12 créditos ya inscritos.",
        "respuesta": '{"decision": "no", "regla": "525150"}',
    },
    {
        "historial": "525140  Álgebra I: aprobada\n525150  Álgebra II: inscrita (cursándola ahora)\n527150  Cálculo II: inscrita (cursándola ahora)",
        "consulta": "Quiere inscribir 525223 (Ecuaciones Diferenciales) el próximo semestre. Tiene 12 créditos ya inscritos.",
        "respuesta": '{"decision": "condicional", "regla": "R-DEPENDE-APROBACION"}',
    },
]


def _bloque_consulta(caso, usar_prosa=True):
    q = caso["pregunta_prosa"] if usar_prosa else caso["pregunta_limpia"]
    ya = caso["consulta"]["creditos_ya_inscritos"]
    return f'El estudiante pregunta: "{q}"\n\nCréditos que ya tiene inscritos este semestre: {ya}.'


def construir(caso, malla, condicion="zero_shot", usar_prosa=True):
    """Devuelve la lista de mensajes en formato chat."""
    sistema = INSTRUCCION

    partes = [
        "=== MALLA CURRICULAR ===",
        render_malla(malla),
        "",
        "=== REGLAS DE INSCRIPCIÓN ===",
        render_reglas(malla),
        "",
    ]

    if condicion == "few_shot":
        partes.append("=== EJEMPLOS RESUELTOS ===")
        for i, ej in enumerate(EJEMPLOS_FEW_SHOT, 1):
            partes += [f"Ejemplo {i}.",
                       "Historial:", ej["historial"],
                       ej["consulta"],
                       "Respuesta: " + ej["respuesta"], ""]

    partes += [
        "=== HISTORIAL DEL ESTUDIANTE ===",
        render_historial(caso["historial"], malla),
        "",
        "=== CONSULTA ===",
        _bloque_consulta(caso, usar_prosa),
        "",
        "Responde solo con el JSON.",
    ]

    return [{"role": "system", "content": sistema},
            {"role": "user", "content": "\n".join(partes)}]


def parsear_respuesta(texto):
    """Extrae {decision, regla} de la salida del modelo. Tolerante pero no permisivo:
    normaliza mayúsculas y acentos de la decisión, pero no adivina la regla."""
    if not texto:
        return {"decision": None, "regla": None, "parseo": "vacio"}
    ini, fin = texto.find("{"), texto.rfind("}")
    if ini == -1 or fin == -1 or fin < ini:
        return {"decision": None, "regla": None, "parseo": "sin_json"}
    try:
        d = json.loads(texto[ini:fin + 1])
    except json.JSONDecodeError:
        return {"decision": None, "regla": None, "parseo": "json_invalido"}

    dec = str(d.get("decision", "")).strip().lower()
    dec = {"si": "sí", "sí": "sí", "yes": "sí",
           "no": "no",
           "condicional": "condicional", "conditional": "condicional"}.get(dec)
    regla = d.get("regla")
    regla = str(regla).strip() if regla is not None else None
    return {"decision": dec, "regla": regla, "parseo": "ok"}
