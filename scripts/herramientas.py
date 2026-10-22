# -*- coding: utf-8 -*-
"""
Las dos herramientas del sistema de agentes — Deliverable 3.

Las dos son código sin modelo. El enunciado exige que todos los agentes usen el mismo modelo,
y una herramienta con un modelo propio (por ejemplo de embeddings) sería un segundo modelo
dentro del sistema que corre.

  T1  buscar_ramo        texto -> los cinco ramos del catálogo más parecidos
                         la llama el traspaso del Intérprete al Resolvedor, y el Resolvedor
                         cuando decide volver a buscar

  T2  motor_de_reglas    código y período -> decisión y regla
                         es la ficha y el reglamento del D2 sin cambios (`ficha.py`)
                         la llama el Verificador al aceptar

Por qué T1 existe: en el D2 el modelo recibía los 61 pares de código y nombre y debía copiar
el código. Con el nombre exacto del catálogo en la pregunta acertaba 18 de 34. El problema no
es el tamaño del catálogo (unos 1.000 tokens) sino copiar un código de seis dígitos desde una
lista. T1 hace esa búsqueda y el modelo solo elige entre cinco.

T1 no usa el diccionario de abreviaciones del generador de casos. Si lo usara, estaría
leyendo la respuesta.

    python herramientas.py        # pruebas
"""

import difflib
import json
import re
import unicodedata

from verificador import Verificador, RUTA_MALLA
from ficha import construir_ficha, decidir_desde_ficha

K_CANDIDATOS = 5

_ROMANOS = {"i": "1", "ii": "2", "iii": "3"}


def normalizar(texto):
    """Minúsculas, sin tildes ni puntuación, y números romanos sueltos como arábigos.

    "Optimización I", "optimizacion 1" y "OPTIMIZACIÓN I" quedan iguales. Es forma de
    superficie, no significado: no expande siglas ni sinónimos.
    """
    t = unicodedata.normalize("NFD", str(texto).lower())
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\b(iii|ii|i)\b", lambda m: _ROMANOS[m.group(1)], t)
    return re.sub(r"\s+", " ", t).strip()


_MALLA = json.load(open(RUTA_MALLA, encoding="utf-8"))
CATALOGO = [(a["codigo"], a["nombre"], normalizar(a["nombre"])) for a in _MALLA["asignaturas"]]


def similitud(consulta_norm, nombre_norm):
    """Parecido de cadenas, más medio punto si la consulta está contenida en el nombre.

    El bono existe porque los estudiantes acortan: "transferencia" está dentro de
    "transferencia de calor" aunque la razón de difflib sea baja por el largo.
    """
    s = difflib.SequenceMatcher(None, consulta_norm, nombre_norm).ratio()
    if consulta_norm and consulta_norm in nombre_norm:
        s += 0.5
    return s


def buscar_ramo(texto, k=K_CANDIDATOS):
    """T1. Los k ramos más parecidos al texto, con su puntaje, de mayor a menor.

    `exacta` marca el candidato cuyo nombre normalizado es igual al texto normalizado (v5).
    En la v4 el Resolvedor recibió "Optimización 1" con Optimización I primero (1,50) y eligió
    Optimización II; la marca le dice lo que el puntaje solo sugería.
    """
    q = normalizar(texto)
    puntajes = sorted(((similitud(q, n), c, nombre, n) for c, nombre, n in CATALOGO),
                      key=lambda x: (-x[0], x[1]))
    return [{"codigo": c, "nombre": nombre, "similitud": round(s, 3), "exacta": bool(q) and q == n}
            for s, c, nombre, n in puntajes[:k]]


def motor_de_reglas(v, caso, codigo, periodo):
    """T2. La ficha y la decisión del D2, con el historial y los créditos del caso."""
    ficha = construir_ficha(v, caso["historial"], codigo, periodo,
                            caso["consulta"]["creditos_ya_inscritos"])
    return decidir_desde_ficha(v, ficha)


# --------------------------------------------------------------- pruebas

def _pruebas():
    v = Verificador()
    casos = [json.loads(l) for l in open(RUTA_MALLA.parent / "casos.jsonl", encoding="utf-8")]
    chequeos = [
        ("normaliza tildes y romanos", normalizar("Optimización I"), "optimizacion 1"),
        ("nombre exacto primero", buscar_ramo("Tecnologías de la Información")[0]["codigo"], "503700"),
        ("arábigo encuentra el romano", buscar_ramo("Optimización 1")[0]["codigo"], "580315"),
        ("el 2 no se confunde con el 1", buscar_ramo("optimización 2")[0]["codigo"], "580325"),
        ("palabra suelta dentro del nombre", buscar_ramo("transferencia")[0]["codigo"], "542355"),
        ("devuelve cinco", len(buscar_ramo("cálculo")), 5),
        ("orden estable ante empate", buscar_ramo("electiva") == buscar_ramo("electiva"), True),
        ("coincidencia exacta: 'Optimización 1' marca Optimización I",
         [(x["codigo"], x["exacta"]) for x in buscar_ramo("Optimización 1")[:2]],
         [("580315", True), ("580325", False)]),
        ("una palabra suelta no es coincidencia exacta",
         any(x["exacta"] for x in buscar_ramo("transferencia")), False),
    ]
    # T2 con el ramo y el período verdaderos reproduce la etiqueta en los 60 casos, igual que
    # el sistema del D2 con el paso 1 perfecto.
    iguales = sum(motor_de_reglas(v, c, c["consulta"]["ramos"][0], c["consulta"]["periodo"])
                  == c["respuesta"] for c in casos)
    chequeos.append(("T2 reproduce las 60 etiquetas", iguales, len(casos)))

    fallas = [(n, e, o) for n, o, e in chequeos if o != e]
    for n, e, o in fallas:
        print(f"[FALLA] {n}: esperado {e!r}, obtenido {o!r}")
    print(f"{len(chequeos) - len(fallas)}/{len(chequeos)} chequeos de herramientas correctos")
    return 0 if not fallas else 1


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(_pruebas())
