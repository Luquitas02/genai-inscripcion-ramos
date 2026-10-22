# -*- coding: utf-8 -*-
"""
El orquestador del sistema de agentes — Deliverable 3.

Es código y no decide nada: ejecuta la acción que escribió cada agente y aplica los topes.

    pregunta -> Intérprete --entregar--> T1 -> Resolvedor --elegir--> Verificador --aceptar--> T2
                    |                            |  ^                      |
                    sin_ramo: fin                buscar (máx. 2)           rechazar (máx. 2)
                                                 ninguno -> Intérprete     -> Intérprete

Topes, para que ningún bucle sea infinito:
  MAX_RECHAZOS    vueltas al Intérprete, por rechazo del Verificador o por `ninguno` del
                  Resolvedor. Al pasarlo se acepta la última elección.
  MAX_BUSQUEDAS   búsquedas extra del Resolvedor dentro de una vuelta.
  MAX_LLAMADAS    llamadas al modelo por caso, sumando todos los agentes.

Cada mensaje entre agentes y herramientas queda en la traza, en orden. La traza de un caso es
lo que muestra el video.

Las configuraciones son el sistema completo, una por cada técnica quitada, y una de
diagnóstico (`top1`) que reemplaza al Resolvedor por el primer candidato de T1.
"""

import agentes as A
from herramientas import buscar_ramo, motor_de_reglas, CATALOGO

MAX_RECHAZOS = 2
MAX_BUSQUEDAS = 2
MAX_LLAMADAS = 12

CONFIGURACIONES = {
    "completo":           {"interprete": "interprete.md", "ejemplos": True,
                           "resolvedor": "agente", "verificador": True},
    "sin_descomposicion": {"interprete": "ablaciones/interprete_sin_descomposicion.md",
                           "ejemplos": True, "resolvedor": "agente", "verificador": True},
    "sin_herramienta":    {"interprete": "interprete.md", "ejemplos": True,
                           "resolvedor": "catalogo", "verificador": True},
    "sin_verificador":    {"interprete": "interprete.md", "ejemplos": True,
                           "resolvedor": "agente", "verificador": False},
    "sin_ejemplos":       {"interprete": "interprete.md", "ejemplos": False,
                           "resolvedor": "agente", "verificador": True},
    "top1":               {"interprete": "interprete.md", "ejemplos": True,
                           "resolvedor": "top1", "verificador": True},
}


def cargar_prompts(config):
    c = CONFIGURACIONES[config]
    return {
        "interprete": A.Prompt(c["interprete"], con_ejemplos=c["ejemplos"]),
        "resolvedor": A.Prompt("ablaciones/resolvedor_catalogo.md"
                               if c["resolvedor"] == "catalogo" else "resolvedor.md"),
        "verificador": A.Prompt("verificador.md"),
    }


class _Topado(Exception):
    """Se alcanzó MAX_LLAMADAS."""


class Corrida:
    """El estado de un caso: la traza, los contadores y la última elección."""

    def __init__(self, modelo):
        self.modelo = modelo
        self.traza = []
        self.llamadas = 0
        self.tokens = 0
        self.segundos = 0.0
        self.ramas = {"rechazos_verificador": 0, "ninguno_resolvedor": 0, "busquedas_extra": 0,
                      "sin_ramo": False, "tope_rechazos": False, "tope_llamadas": False,
                      "ilegibles": 0, "codigo_fuera": 0, "citas_fuera": 0}
        self.ultima = None          # {"codigo", "nombre", "periodo", "otros"}

    def anotar(self, de, para, tipo, contenido, llamada=None):
        m = {"n": len(self.traza) + 1, "de": de, "para": para, "tipo": tipo,
             "contenido": contenido}
        if llamada is not None:
            m.update({"entrada": llamada["mensajes"][-1]["content"], "crudo": llamada["crudo"],
                      "tokens": llamada["tokens"], "segundos": round(llamada["segundos"], 3),
                      "prompt": llamada["prompt"]})
        self.traza.append(m)

    def agente(self, fn, *args, **kwargs):
        if self.llamadas >= MAX_LLAMADAS:
            raise _Topado
        accion, llamada = fn(self.modelo, *args, **kwargs)
        self.llamadas += 1
        self.tokens += llamada["tokens"]
        self.segundos += llamada["segundos"]
        if not accion["legible"]:
            self.ramas["ilegibles"] += 1
        return accion, llamada


def _publica(accion):
    return {k: v for k, v in accion.items() if k != "legible"}


def correr_caso(modelo, caso, v, config, prompts=None):
    """Corre un caso con una configuración. Devuelve la fila de resultados y la traza."""
    c = CONFIGURACIONES[config]
    prompts = prompts or cargar_prompts(config)
    r = Corrida(modelo)
    pregunta = caso["pregunta_prosa"]
    r.anotar("estudiante", "interprete", "entrada", {"pregunta": pregunta})

    revision, rechazos, aceptada, t1_inicial = None, 0, False, None
    try:
        while True:
            # --- A. Intérprete ---
            a, ll = r.agente(A.interprete, prompts["interprete"], pregunta, revision)
            if a["accion"] == "sin_ramo":
                r.ramas["sin_ramo"] = True
                r.anotar("interprete", "fin", "agente", _publica(a), ll)
                break
            periodo = a["periodo"] or "actual"
            a_pub = dict(_publica(a), periodo=periodo,
                         periodo_por_defecto=a["periodo"] is None)
            r.anotar("interprete", "T1" if c["resolvedor"] != "catalogo" else "resolvedor",
                     "agente", a_pub, ll)
            otros = a["otros"]

            # --- B. Resolvedor (o lo que lo reemplaza en las ablaciones) ---
            elegido = None
            if c["resolvedor"] == "catalogo":
                b, ll = r.agente(A.resolvedor, prompts["resolvedor"], a["consultado"], otros,
                                 None, [], 0, catalogo=[(cod, nom) for cod, nom, _ in CATALOGO])
                r.anotar("resolvedor", "verificador" if b["accion"] == "elegir" else "interprete",
                         "agente", _publica(b), ll)
                r.ramas["codigo_fuera"] += "codigo_fuera" in b
                if b["accion"] == "elegir":
                    elegido = b["codigo"]
            else:
                candidatos = buscar_ramo(a["consultado"])
                if t1_inicial is None:
                    t1_inicial = [x["codigo"] for x in candidatos]
                r.anotar("T1", "resolvedor", "herramienta",
                         {"consulta": a["consultado"], "candidatos": candidatos})
                if c["resolvedor"] == "top1":
                    elegido = candidatos[0]["codigo"]
                else:
                    hechas = []
                    while True:
                        b, ll = r.agente(A.resolvedor, prompts["resolvedor"], a["consultado"],
                                         otros, candidatos, hechas, MAX_BUSQUEDAS)
                        r.ramas["codigo_fuera"] += "codigo_fuera" in b
                        if b["accion"] == "buscar" and len(hechas) < MAX_BUSQUEDAS:
                            r.anotar("resolvedor", "T1", "agente", _publica(b), ll)
                            hechas.append(b["consulta"])
                            r.ramas["busquedas_extra"] += 1
                            candidatos = buscar_ramo(b["consulta"])
                            r.anotar("T1", "resolvedor", "herramienta",
                                     {"consulta": b["consulta"], "candidatos": candidatos})
                            continue
                        if b["accion"] == "elegir":
                            r.anotar("resolvedor", "verificador", "agente", _publica(b), ll)
                            elegido = b["codigo"]
                        else:
                            # `ninguno`, o pidió buscar sin búsquedas disponibles
                            r.anotar("resolvedor", "interprete", "agente",
                                     dict(_publica(b), accion="ninguno"), ll)
                        break

            if elegido is None:
                r.ramas["ninguno_resolvedor"] += 1
                revision = {"consultado": a["consultado"], "periodo": periodo,
                            "problema": "ramo",
                            "motivo": f"Ninguna asignatura del catálogo corresponde a "
                                      f"\"{a['consultado']}\"."}
                rechazos += 1
                if rechazos > MAX_RECHAZOS:
                    r.ramas["tope_rechazos"] = True
                    break
                continue

            nombre = next(n for cod, n, _ in CATALOGO if cod == elegido)
            r.ultima = {"codigo": elegido, "nombre": nombre, "periodo": periodo, "otros": otros}

            # --- C. Verificador ---
            if not c["verificador"]:
                aceptada = True
                break
            cv, ll = r.agente(A.verificador, prompts["verificador"], pregunta, elegido, nombre,
                              periodo, otros)
            r.ramas["citas_fuera"] += cv["legible"] and not cv.get("cita_ramo_en_consulta")
            if cv["accion"] == "aceptar":
                r.anotar("verificador", "T2", "agente", _publica(cv), ll)
                aceptada = True
                break
            r.anotar("verificador", "interprete", "agente", _publica(cv), ll)
            r.ramas["rechazos_verificador"] += 1
            revision = {"consultado": a["consultado"], "periodo": periodo,
                        "problema": cv["problema"], "motivo": cv["motivo"]}
            rechazos += 1
            if rechazos > MAX_RECHAZOS:
                r.ramas["tope_rechazos"] = True
                break
    except _Topado:
        r.ramas["tope_llamadas"] = True

    # --- T2 o cierre sin decisión ---
    # Si se cortó por un tope o el Intérprete se rindió tras un rechazo, se usa la última
    # elección. Así un caso no queda sin respuesta por haber dudado de más.
    if r.ultima is not None:
        pred = motor_de_reglas(v, caso, r.ultima["codigo"], r.ultima["periodo"])
        r.anotar("T2", "fin", "herramienta",
                 {"codigo": r.ultima["codigo"], "periodo": r.ultima["periodo"],
                  "decision": pred["decision"], "regla": pred["regla"],
                  "por_tope": not aceptada})
    else:
        pred = {"decision": None, "regla": None}
        r.anotar("orquestador", "fin", "fin", {"motivo": "sin ramo elegido"})

    ramo_real = caso["consulta"]["ramos"][0]
    per_real = caso["consulta"]["periodo"]
    ext = r.ultima or {"codigo": None, "periodo": None}
    fila = {
        "id": caso.get("id"),
        "configuracion": config,
        "modelo": getattr(modelo, "nombre", "falso"),
        "nivel": caso["nivel"], "constructor": caso["constructor"], "rasgos": caso["rasgos"],
        "ramo_objetivo": caso["ramo_objetivo"],
        "pregunta": pregunta,
        "esperado": caso["respuesta"],
        "extraccion": {"ramo": ext["codigo"], "periodo": ext["periodo"]},
        "acierto_ramo": ext["codigo"] == ramo_real,
        "acierto_periodo": ext["periodo"] == per_real,
        "t1_recall5": None if t1_inicial is None else ramo_real in t1_inicial,
        "prediccion": pred,
        "acierto_decision": pred["decision"] == caso["respuesta"]["decision"],
        "acierto_regla": pred["regla"] == caso["respuesta"]["regla"],
        "aceptada": aceptada,
        "ramas": r.ramas,
        "llamadas": r.llamadas,
        "tokens_total": r.tokens,
        "segundos_total": round(r.segundos, 3),
        "prompts": {k: p.ref() for k, p in prompts.items()},
    }
    fila["acierto_conjunto"] = fila["acierto_decision"] and fila["acierto_regla"]
    return fila, r.traza
