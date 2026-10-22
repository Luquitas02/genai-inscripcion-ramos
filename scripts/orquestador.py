# -*- coding: utf-8 -*-
"""
El orquestador del sistema de agentes — Deliverable 3, versión 5.

Es código y no decide nada: ejecuta la acción que escribió cada agente y aplica los topes.

    pregunta -> Intérprete --entregar--> T1 -> Resolvedor --elegir/mantener--> Verificador
                    |   ^                        |  ^   ^                       |
             sin_ramo:  |                buscar (máx. 2)                        |-- aceptar ---------> T2
                  fin   |                        |  |                           |-- corregir_periodo -> T2
                        |                ninguno |  |                           |       (con el período corregido)
                        +-------- rechazar: mencion | <---- rechazar: codigo ---+
                                  (vuelve al Intérprete)   (vuelve al Resolvedor)

    Si una cita del Verificador no aparece en la consulta, el Verificador recibe su propia
    salida y la revisa, una sola vez por caso. Si esa revisión no se puede hacer (tope de
    llamadas) o sale ilegible, vale su primera salida.

Topes, para que ningún bucle sea infinito:
  MAX_RECHAZOS    vueltas por rechazo del Verificador (al Intérprete o al Resolvedor) o por
                  `ninguno` del Resolvedor. Al pasarlo se usa la última elección.
  MAX_BUSQUEDAS   búsquedas extra del Resolvedor dentro de una vuelta.
  MAX_LLAMADAS    llamadas al modelo por caso, sumando todos los agentes.

Qué cambió respecto de la v4 (diseño en PLAN_D3.md, "Versión 5"): el rechazo por el código va
al Resolvedor y no al Intérprete, el Resolvedor puede mantener su elección, el Verificador
puede corregir el período y revisa sus citas, y las ablaciones quitan una sola cosa.

Cada mensaje entre agentes y herramientas queda en la traza, en orden. La traza de un caso es
lo que muestra el video.
"""

import agentes as A
from herramientas import buscar_ramo, motor_de_reglas, CATALOGO

VERSION = "v5"
MAX_RECHAZOS = 2
MAX_BUSQUEDAS = 2
MAX_LLAMADAS = 12

# Cada configuración es el sistema completo con una sola cosa quitada (ver PLAN_D3.md).
_COMPLETO = {"interprete": "interprete.md", "ejemplos": True, "resolvedor": "agente",
             "verificador": "verificador.md", "revisar_citas": True, "otros": True}
CONFIGURACIONES = {
    "completo":              dict(_COMPLETO),
    "sin_herramienta":       dict(_COMPLETO, resolvedor="catalogo"),
    "sin_ejemplos":          dict(_COMPLETO, ejemplos=False),
    # Sin la lista, el Resolvedor y el Verificador reciben "ninguna" aunque el modelo la escriba.
    "sin_lista_otros":       dict(_COMPLETO, interprete="ablaciones/interprete_sin_lista_otros.md",
                                  otros=False),
    "sin_regla_verbo":       dict(_COMPLETO, interprete="ablaciones/interprete_sin_regla_verbo.md"),
    "sin_citas_interprete":  dict(_COMPLETO, interprete="ablaciones/interprete_sin_citas.md"),
    "sin_citas_verificador": dict(_COMPLETO, verificador="ablaciones/verificador_sin_citas.md",
                                  revisar_citas=False),
    "sin_calendario":        dict(_COMPLETO, verificador="ablaciones/verificador_sin_calendario.md"),
    "sin_verificador":       dict(_COMPLETO, verificador=None, revisar_citas=False),
    "top1":                  dict(_COMPLETO, resolvedor="top1"),
}


def cargar_prompts(config):
    c = CONFIGURACIONES[config]
    prompts = {
        "interprete": A.Prompt(c["interprete"], con_ejemplos=c["ejemplos"]),
        "resolvedor": A.Prompt("ablaciones/resolvedor_catalogo.md"
                               if c["resolvedor"] == "catalogo" else "resolvedor.md"),
    }
    if c["verificador"]:
        prompts["verificador"] = A.Prompt(c["verificador"])
    return prompts


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
        self.ramas = {"rechazos_mencion": 0, "rechazos_codigo": 0, "correcciones_periodo": 0,
                      "mantener": 0, "revision_citas": 0, "ninguno_resolvedor": 0,
                      "busquedas_extra": 0, "sin_ramo": False, "tope_rechazos": False,
                      "tope_llamadas": False, "ilegibles": 0, "codigo_fuera": 0,
                      "citas_fuera": 0, "cita_periodo_fuera": 0, "citas_fuera_tras_revision": 0}
        self.ultima = None          # {"codigo", "nombre", "periodo", "otros"}
        self.primera_verificada = None   # lo que vio el Verificador la primera vez

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


def _citas_fuera(cv):
    """Los nombres de las citas del Verificador que no aparecen en la consulta."""
    fuera = []
    if "cita_ramo" in cv and not cv["cita_ramo_en_consulta"]:
        fuera.append("cita_ramo")
    if cv.get("cita_periodo_en_consulta") is False:
        fuera.append("cita_periodo")
    return fuera


def _resolver(r, c, prompts, a, otros, rechazo):
    """El paso B: el Resolvedor, o lo que lo reemplaza en las ablaciones. Devuelve el código
    elegido o None (`ninguno`). Anota T1 y cada llamada en la traza."""
    if c["resolvedor"] == "catalogo":
        b, ll = r.agente(A.resolvedor, prompts["resolvedor"], a["consultado"], otros,
                         None, [], 0, catalogo=[(cod, nom) for cod, nom, _ in CATALOGO],
                         rechazo=rechazo)
        r.ramas["codigo_fuera"] += "codigo_fuera" in b
        r.ramas["mantener"] += b["accion"] == "mantener"
        r.anotar("resolvedor", "verificador" if b.get("codigo") and b["accion"] != "ninguno"
                 else "interprete", "agente", _publica(b), ll)
        return b["codigo"] if b["accion"] in ("elegir", "mantener") else None

    candidatos = buscar_ramo(a["consultado"])
    r.anotar("T1", "resolvedor", "herramienta",
             {"consulta": a["consultado"], "candidatos": candidatos})
    if c["resolvedor"] == "top1":
        return candidatos[0]["codigo"]
    hechas = []
    while True:
        b, ll = r.agente(A.resolvedor, prompts["resolvedor"], a["consultado"], otros,
                         candidatos, hechas, MAX_BUSQUEDAS, rechazo=rechazo)
        r.ramas["codigo_fuera"] += "codigo_fuera" in b
        if b["accion"] == "buscar" and len(hechas) < MAX_BUSQUEDAS:
            r.anotar("resolvedor", "T1", "agente", _publica(b), ll)
            hechas.append(b["consulta"])
            r.ramas["busquedas_extra"] += 1
            candidatos = buscar_ramo(b["consulta"])
            r.anotar("T1", "resolvedor", "herramienta",
                     {"consulta": b["consulta"], "candidatos": candidatos})
            continue
        if b["accion"] in ("elegir", "mantener"):
            r.ramas["mantener"] += b["accion"] == "mantener"
            r.anotar("resolvedor", "verificador", "agente", _publica(b), ll)
            return b["codigo"]
        # `ninguno`, o pidió buscar sin búsquedas disponibles
        r.anotar("resolvedor", "interprete", "agente", dict(_publica(b), accion="ninguno"), ll)
        return None


def correr_caso(modelo, caso, v, config, prompts=None):
    """Corre un caso con una configuración. Devuelve la fila de resultados y la traza."""
    c = CONFIGURACIONES[config]
    prompts = prompts or cargar_prompts(config)
    r = Corrida(modelo)
    pregunta = caso["pregunta_prosa"]
    r.anotar("estudiante", "interprete", "entrada", {"pregunta": pregunta})

    revision, rechazo, rechazos, aceptada, citas_revisadas = None, None, 0, False, False
    t1_inicial, a, periodo, otros = None, None, None, []
    try:
        while True:
            # --- A. Intérprete (salvo que el rechazo fuera por el código) ---
            if rechazo is None:
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
                otros = a["otros"] if c["otros"] else []
                if t1_inicial is None and c["resolvedor"] != "catalogo":
                    t1_inicial = [x["codigo"] for x in buscar_ramo(a["consultado"])]

            # --- B. Resolvedor ---
            elegido = _resolver(r, c, prompts, a, otros, rechazo)
            rechazo = None
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
            if r.primera_verificada is None:
                r.primera_verificada = {"codigo": elegido, "periodo": periodo}
            cv, ll = r.agente(A.verificador, prompts["verificador"], pregunta, elegido, nombre,
                              periodo, otros)
            fuera = _citas_fuera(cv)
            r.ramas["citas_fuera"] += "cita_ramo" in fuera
            r.ramas["cita_periodo_fuera"] += "cita_periodo" in fuera
            if fuera and c["revisar_citas"] and not citas_revisadas and r.llamadas < MAX_LLAMADAS:
                # Revisa su propia salida una vez por caso: sus citas tienen que salir de la
                # consulta. Si la revisión sale ilegible, vale la primera salida.
                citas_revisadas = True
                r.anotar("verificador", "verificador", "agente", _publica(cv), ll)
                r.ramas["revision_citas"] += 1
                cv2, ll2 = r.agente(A.verificador, prompts["verificador"], pregunta, elegido,
                                    nombre, periodo, otros,
                                    revision=A.bloque_revision_citas(cv, fuera))
                if cv2["legible"]:
                    cv, ll = cv2, ll2
                    r.ramas["citas_fuera_tras_revision"] += bool(_citas_fuera(cv))
                else:
                    r.anotar("verificador", "verificador", "agente",
                             dict(_publica(cv2), nota="revisión ilegible: vale la primera salida"),
                             ll2)

            if cv["accion"] == "aceptar":
                r.anotar("verificador", "T2", "agente", _publica(cv), ll)
                aceptada = True
                break
            if cv["accion"] == "corregir_periodo":
                r.anotar("verificador", "T2", "agente", _publica(cv), ll)
                r.ramas["correcciones_periodo"] += 1
                periodo = cv["periodo_corregido"]
                r.ultima["periodo"] = periodo
                aceptada = True
                break

            # rechazar: al Resolvedor si es el código, al Intérprete si es la mención
            if cv["problema"] == "codigo":
                r.anotar("verificador", "resolvedor", "agente", _publica(cv), ll)
                r.ramas["rechazos_codigo"] += 1
                rechazo = {"codigo": elegido, "nombre": nombre, "motivo": cv["motivo"]}
            else:
                r.anotar("verificador", "interprete", "agente", _publica(cv), ll)
                r.ramas["rechazos_mencion"] += 1
                revision = {"consultado": a["consultado"], "periodo": periodo,
                            "problema": "ramo", "motivo": cv["motivo"]}
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
        "version": VERSION,
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
        "t1_top1_inicial": None if t1_inicial is None else t1_inicial[0],
        "primera_verificada": r.primera_verificada,
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
    if "filtro_v5" in caso:
        fila["filtro_v5"] = caso["filtro_v5"]
    fila["acierto_conjunto"] = fila["acierto_decision"] and fila["acierto_regla"]
    fila["acierto_estricto"] = (fila["acierto_conjunto"] and fila["acierto_ramo"]
                                and fila["acierto_periodo"])
    return fila, r.traza
