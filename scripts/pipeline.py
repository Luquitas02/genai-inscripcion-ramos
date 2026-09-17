# -*- coding: utf-8 -*-
"""
El pipeline de tres pasos — Deliverable 2.

El baseline hace una sola llamada con 3.900 tokens y falla. Acá el trabajo se parte en
tres llamadas, y cada una recibe solo lo que necesita:

  paso 1  extracción   la pregunta en prosa y el catálogo de códigos
                       no ve el historial, ni las reglas, ni los prerrequisitos
                       ataca E2, la dependencia de que la pregunta apunte al dato

  paso 2  ficha        el código del ramo, la malla y el historial
                       no ve la pregunta en prosa
                       ataca E1, la falta de representación de "cursándola ahora"

  paso 3  decisión     la ficha renderizada, las reglas y la lista cerrada
                       no ve la malla, ni el historial, ni la pregunta
                       ataca E3 y E4, los identificadores inventados y las contradicciones

Este módulo no llama al modelo. Solo arma los prompts y lee las respuestas, así que se
prueba entero en local sin GPU. Quien llama al modelo es `runner_d2.py`.

La normalización de la decisión se copia de `prompt.parsear_respuesta` para que el
baseline y el pipeline se corrijan con el mismo criterio. Si se corrigieran distinto, la
comparación no mediría la intervención.
"""

import json

from verificador import Verificador, APROBADA, INSCRITA, REPROBADA, NO_CURSADA
from prompt import render_malla, render_historial, render_reglas
from ficha import render_ficha

# La malla y el historial se renderizan con las MISMAS funciones que usa el baseline.
# Si se representaran distinto, la comparación mediría el cambio de representación y no
# la descomposición en pasos, que es la intervención que este entregable evalúa.

_ESTADOS = (APROBADA, INSCRITA, REPROBADA, NO_CURSADA)

_DECISIONES = {"si": "sí", "sí": "sí", "yes": "sí",
               "no": "no",
               "condicional": "condicional", "conditional": "condicional"}


def _extraer_json(texto):
    """Devuelve (dict, estado). Tolerante con el texto alrededor, estricto con el JSON."""
    if not texto:
        return None, "vacio"
    ini, fin = texto.find("{"), texto.rfind("}")
    if ini == -1 or fin == -1 or fin < ini:
        return None, "sin_json"
    try:
        return json.loads(texto[ini:fin + 1]), "ok"
    except json.JSONDecodeError:
        return None, "json_invalido"


def _norm_estado(s):
    """Normaliza la forma de superficie, no el significado.

    "No Cursada" y "no cursada" son la misma palabra escrita distinto, así que se aceptan.
    Cualquier otra cosa se devuelve tal cual y cuenta como error del modelo. Normalizar
    más que esto inflaría el acierto del paso 2.
    """
    if s is None:
        return None
    t = str(s).strip().lower().replace(" ", "_").replace("-", "_")
    return t if t in _ESTADOS else str(s).strip()


def _norm_entero(x):
    """Acepta 37 y "37". El tipo es formato, no juicio."""
    if x is None:
        return None
    try:
        return int(str(x).strip())
    except (TypeError, ValueError):
        return x


# --------------------------------------------------------------- paso 1: extracción

INSTRUCCION_P1 = """Eres un asistente de inscripción académica de Ingeniería Civil Industrial \
de la Universidad de Concepción.

Se te entrega el catálogo de asignaturas y la consulta de un estudiante, escrita de manera \
informal. Tu única tarea es identificar DOS cosas:

1. El código de la asignatura por la que pregunta.
2. Si pregunta por el período actual o por el próximo.

El período actual es 2026-2. El próximo período es 2027-1.

El estudiante puede referirse a la asignatura por su nombre completo, por una abreviación o \
de manera coloquial. Devuelve siempre el CÓDIGO de seis dígitos, nunca el nombre.

No decidas si puede inscribir. Eso no es parte de esta tarea.

Responde ÚNICAMENTE con este JSON, sin texto adicional:

{"ramo": "<código>", "periodo": "actual" | "proximo"}"""


def prompt_paso1(caso, malla):
    catalogo = "\n".join(f"{a['codigo']}  {a['nombre']}" for a in malla["asignaturas"])
    usuario = (f"=== CATÁLOGO DE ASIGNATURAS ===\n{catalogo}\n\n"
               f"=== CONSULTA DEL ESTUDIANTE ===\n{caso['pregunta_prosa']}\n\n"
               "Responde solo con el JSON.")
    return [{"role": "system", "content": INSTRUCCION_P1},
            {"role": "user", "content": usuario}]


def parsear_paso1(texto, codigos):
    """Un ramo fuera de la malla es None. Que devuelva el nombre en vez del código es
    una falla del paso 1 y se registra como tal."""
    d, _ = _extraer_json(texto)
    if d is None:
        return {"ramo": None, "periodo": None}
    ramo = str(d.get("ramo", "")).strip()
    per = str(d.get("periodo", "")).strip().lower()
    return {"ramo": ramo if ramo in codigos else None,
            "periodo": per if per in ("actual", "proximo") else None}


# --------------------------------------------------------------- paso 2: ficha

INSTRUCCION_P2 = """Eres un asistente de inscripción académica de Ingeniería Civil Industrial \
de la Universidad de Concepción.

Se te entrega la malla curricular, el historial académico de un estudiante, un código de \
asignatura y el período consultado. Tu única tarea es levantar el estado del expediente para \
esa asignatura. No decidas si puede inscribirla.

Debes reportar cinco cosas:

1. "estado_actual": el estado de la asignatura consultada en el historial. Uno de:
   "aprobada", "inscrita", "reprobada", "no_cursada".
2. "prerrequisitos": la lista de prerrequisitos DIRECTOS de esa asignatura, cada uno con su
   estado en el historial. Si no tiene prerrequisitos, lista vacía.
3. "creditos_aprobados": el total de créditos del estudiante.
   - Si el período es "actual", suma solo los créditos de las asignaturas APROBADAS.
   - Si el período es "proximo", suma los créditos de las APROBADAS más los de las INSCRITAS,
     porque para el próximo semestre ya las habrá cursado.
4. "umbral_creditos": el mínimo de créditos aprobados que exige esa asignatura, o null si no
   exige ninguno.
5. "requisitos_especiales": los requisitos de semestre o año completo de esa asignatura. Para
   cada uno indica "cumple", "cumple_condicional" o "no_cumple", y qué asignatura falta.
   Si no tiene requisitos especiales, lista vacía.

Una asignatura INSCRITA no está aprobada. El estudiante la está cursando ahora y todavía \
puede reprobarla.

Responde ÚNICAMENTE con este JSON, sin texto adicional:

{"estado_actual": "...", "prerrequisitos": [{"codigo": "...", "estado": "..."}],
 "creditos_aprobados": 0, "umbral_creditos": null, "requisitos_especiales": []}"""


def prompt_paso2(ramo, malla, historial, periodo):
    usuario = (f"=== MALLA CURRICULAR ===\n{render_malla(malla)}\n\n"
               f"=== HISTORIAL DEL ESTUDIANTE ===\n{render_historial(historial, malla)}\n\n"
               f"=== CONSULTA ===\nAsignatura: {ramo}\nPeríodo consultado: {periodo}\n\n"
               "Responde solo con el JSON.")
    return [{"role": "system", "content": INSTRUCCION_P2},
            {"role": "user", "content": usuario}]


def parsear_paso2(texto, v, ramo, periodo, creditos_ya_inscritos):
    """Devuelve una ficha, o None si no se pudo leer el JSON.

    Los campos que son dato de entrada (`ramo`, `nombre`, `creditos_ramo`, `es_practica`,
    `periodo`, `creditos_ya_inscritos`) se rellenan de la malla y del caso. No son juicios
    del modelo y no tiene sentido puntuárselos.
    """
    d, _ = _extraer_json(texto)
    if d is None:
        return None
    a = v.asig[ramo]
    prerreq = []
    for p in (d.get("prerrequisitos") or []):
        if not isinstance(p, dict):
            continue
        cod = str(p.get("codigo", "")).strip()
        prerreq.append({"codigo": cod,
                        "nombre": v.asig[cod]["nombre"] if cod in v.asig else "?",
                        "estado": _norm_estado(p.get("estado"))})
    especiales = []
    for r in (d.get("requisitos_especiales") or []):
        if not isinstance(r, dict):
            continue
        especiales.append({"nombre": str(r.get("nombre", "")).strip(),
                           "resultado": str(r.get("resultado", "")).strip(),
                           "falta": r.get("falta") or None})
    return {
        "ramo": ramo,
        "nombre": a["nombre"],
        "estado_actual": _norm_estado(d.get("estado_actual")),
        "creditos_ramo": a["creditos"],
        "es_practica": ramo in v.practicas,
        "prerrequisitos": prerreq,
        "creditos_aprobados": _norm_entero(d.get("creditos_aprobados")),
        "umbral_creditos": _norm_entero(d.get("umbral_creditos")) or None,
        "requisitos_especiales": especiales,
        "creditos_ya_inscritos": creditos_ya_inscritos,
        "periodo": periodo,
    }


# --------------------------------------------------------------- paso 3: decisión

INSTRUCCION_P3 = """Eres un asistente de inscripción académica de Ingeniería Civil Industrial \
de la Universidad de Concepción.

Se te entrega la ficha ya levantada de un caso y las reglas de inscripción. Tu única tarea es \
decidir si el estudiante puede inscribir la asignatura, y citar la regla que sostiene la \
decisión. No tienes que buscar nada: todo lo que necesitas está en la ficha.

Una asignatura INSCRITA no está aprobada. Si un prerrequisito está inscrito y la consulta es \
por el PRÓXIMO período, la respuesta es condicional: puede inscribirla si aprueba lo que cursa \
ahora. Si la consulta es por el período ACTUAL, ese prerrequisito no está cumplido.

Si más de una regla impide la inscripción, cita la primera según este orden:
R-YA-CURSADA, R-TOPE-MAX, el código del prerrequisito faltante, R-CREDITOS-MINIMOS, R-ESPECIAL.

El campo "regla" debe ser EXACTAMENTE uno de los valores de la lista de identificadores \
válidos que se te entrega. No inventes identificadores ni los escribas de otra forma.

Responde ÚNICAMENTE con este JSON, sin texto adicional:

{"decision": "sí" | "no" | "condicional", "regla": "<identificador>"}"""


def identificadores_validos(f):
    """La lista cerrada del paso 3.

    Incluye los códigos de los prerrequisitos del caso. Sin ellos el sistema queda
    estructuralmente incapaz de responder los 12 casos cuya respuesta es un prerrequisito,
    que son el 20 % del conjunto. En el baseline, Mistral citó un código de ramo una sola vez
    en 180 respuestas.

    R-TOPE-MIN queda fuera a propósito: el prompt del baseline lo ofrecía, pero el verificador
    nunca lo emite y no es la respuesta correcta en ninguno de los 60 casos.
    """
    validos = ["R-SIN-IMPEDIMENTO", "R-DEPENDE-APROBACION", "R-EXCEPCION-PRERREQ",
               "R-TOPE-MAX", "R-CREDITOS-MINIMOS", "R-YA-CURSADA"]
    validos += [p["codigo"] for p in f["prerrequisitos"] if p.get("codigo")]
    validos += ["R-ESPECIAL-" + r["nombre"] for r in f["requisitos_especiales"] if r.get("nombre")]
    return validos


def prompt_paso3(f, malla):
    validos = identificadores_validos(f)
    usuario = (f"=== FICHA DEL CASO ===\n{render_ficha(f)}\n\n"
               f"=== REGLAS DE INSCRIPCIÓN ===\n{render_reglas(malla)}\n\n"
               "=== IDENTIFICADORES VÁLIDOS ===\n"
               + "\n".join(f"- {x}" for x in validos)
               + "\n\nResponde solo con el JSON.")
    return [{"role": "system", "content": INSTRUCCION_P3},
            {"role": "user", "content": usuario}]


def parsear_paso3(texto, validos):
    """Rechaza cualquier regla fuera de la lista cerrada. Ése es el mecanismo contra E3."""
    d, estado = _extraer_json(texto)
    if d is None:
        return {"decision": None, "regla": None, "parseo": estado}
    dec = _DECISIONES.get(str(d.get("decision", "")).strip().lower())
    regla = str(d.get("regla", "")).strip()
    if regla not in validos:
        return {"decision": dec, "regla": None, "parseo": "regla_fuera_de_lista"}
    return {"decision": dec, "regla": regla, "parseo": "ok"}


# --------------------------------------------------------------- pruebas

def _prueba_parseo():
    """Casos de control de los tres parsers. Devuelve (aciertos, total, fallas)."""
    v = Verificador()
    codigos = set(v.asig)

    # ramo 503203 (Programación): 3 créditos, prerrequisito 525140, umbral 37
    ficha_ref = {
        "ramo": "503203", "nombre": "Programación", "estado_actual": NO_CURSADA,
        "creditos_ramo": 3, "es_practica": False,
        "prerrequisitos": [{"codigo": "525140", "nombre": "Álgebra I", "estado": REPROBADA}],
        "creditos_aprobados": 37, "umbral_creditos": 37,
        "requisitos_especiales": [], "creditos_ya_inscritos": 12, "periodo": "actual",
    }

    casos = []

    # --- paso 1 ---
    casos += [
        ("p1 json limpio", lambda: parsear_paso1('{"ramo": "503203", "periodo": "actual"}', codigos),
         {"ramo": "503203", "periodo": "actual"}),
        ("p1 json con texto alrededor",
         lambda: parsear_paso1('Claro:\n{"ramo":"503203","periodo":"proximo"}\nEso.', codigos),
         {"ramo": "503203", "periodo": "proximo"}),
        ("p1 devuelve nombre en vez de código",
         lambda: parsear_paso1('{"ramo": "Programación", "periodo": "actual"}', codigos),
         {"ramo": None, "periodo": "actual"}),
        ("p1 código que no existe en la malla",
         lambda: parsear_paso1('{"ramo": "999999", "periodo": "actual"}', codigos),
         {"ramo": None, "periodo": "actual"}),
        ("p1 sin json", lambda: parsear_paso1('no entiendo la pregunta', codigos),
         {"ramo": None, "periodo": None}),
    ]

    # --- paso 2 ---
    salida_p2 = json.dumps({
        "estado_actual": "no_cursada",
        "prerrequisitos": [{"codigo": "525140", "estado": "reprobada"}],
        "creditos_aprobados": 37, "umbral_creditos": 37, "requisitos_especiales": [],
    }, ensure_ascii=False)
    casos += [
        ("p2 ficha correcta",
         lambda: parsear_paso2(salida_p2, v, "503203", "actual", 12), ficha_ref),
        ("p2 estado con espacio en vez de guion bajo",
         lambda: (parsear_paso2(
             '{"estado_actual": "no cursada", "prerrequisitos": [], '
             '"creditos_aprobados": 1, "umbral_creditos": null, "requisitos_especiales": []}',
             v, "503203", "actual", 12) or {}).get("estado_actual"),
         NO_CURSADA),
        ("p2 sin json", lambda: parsear_paso2('no sé', v, "503203", "actual", 12), None),
    ]

    # --- lista cerrada ---
    casos += [
        ("validos incluye el código del prerrequisito",
         lambda: "525140" in identificadores_validos(ficha_ref), True),
        ("validos excluye R-TOPE-MIN",
         lambda: "R-TOPE-MIN" in identificadores_validos(ficha_ref), False),
    ]

    # --- paso 3 ---
    validos = ["R-SIN-IMPEDIMENTO", "R-DEPENDE-APROBACION", "R-EXCEPCION-PRERREQ",
               "R-TOPE-MAX", "R-CREDITOS-MINIMOS", "R-YA-CURSADA", "525140"]
    casos += [
        ("p3 json limpio",
         lambda: parsear_paso3('{"decision": "sí", "regla": "R-SIN-IMPEDIMENTO"}', validos),
         {"decision": "sí", "regla": "R-SIN-IMPEDIMENTO", "parseo": "ok"}),
        ("p3 decisión sin tilde y en mayúsculas",
         lambda: parsear_paso3('{"decision": "SI", "regla": "525140"}', validos),
         {"decision": "sí", "regla": "525140", "parseo": "ok"}),
        ("p3 identificador inventado (E3)",
         lambda: parsear_paso3('{"decision": "no", "regla": "R-CREDITOS-MINIMISMU"}', validos),
         {"decision": "no", "regla": None, "parseo": "regla_fuera_de_lista"}),
        ("p3 código de ramo que no es prerrequisito del caso",
         lambda: parsear_paso3('{"decision": "no", "regla": "527150"}', validos),
         {"decision": "no", "regla": None, "parseo": "regla_fuera_de_lista"}),
        ("p3 sin json", lambda: parsear_paso3('no puedo responder', validos),
         {"decision": None, "regla": None, "parseo": "sin_json"}),
    ]

    fallas = []
    for nombre, fn, esperado in casos:
        try:
            obtenido = fn()
        except Exception as e:                      # noqa: BLE001
            fallas.append((nombre, esperado, f"excepción: {e!r}"))
            continue
        if obtenido != esperado:
            fallas.append((nombre, esperado, obtenido))
    return len(casos) - len(fallas), len(casos), fallas


def main():
    ok, total, fallas = _prueba_parseo()
    for nombre, esperado, obtenido in fallas:
        print(f"[FALLA] {nombre}")
        print(f"        esperado: {esperado}")
        print(f"        obtenido: {obtenido}")
        print()
    print(f"{ok}/{total} casos de parseo correctos")
    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
