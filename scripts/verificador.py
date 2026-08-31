# -*- coding: utf-8 -*-
"""
Verificador determinista de inscripción de ramos — Ingeniería Civil Industrial, UdeC.

Es el ground truth del proyecto. Dado un historial académico y una consulta, decide si el
estudiante puede inscribir los ramos pedidos y cuál regla sostiene la decisión.

NO usa modelos de lenguaje. Es aritmética y recorrido de grafo, y su respuesta es la verdad
contra la que se mide todo lo demás.

Estados del historial (vocabulario del portal UdeC):
    aprobada · inscrita · reprobada · no_cursada

Períodos de la consulta:
    actual   — el semestre en curso (2026-2). Una asignatura "inscrita" NO está aprobada.
    proximo  — el semestre siguiente (2027-1). Una "inscrita" estará aprobada si la pasa,
               así que el resultado es condicional.

Orden de prioridad de las reglas (declarado, no negociable una vez fijado):
    1. R-YA-CURSADA        el ramo ya está aprobado o inscrito
    2. R-TOPE-MAX          excede el máximo de créditos del semestre
    3. PRERREQUISITO       falta un prerrequisito (se cita el código del ramo faltante)
    4. R-CREDITOS-MINIMOS  no alcanza el umbral de créditos aprobados
    5. R-ESPECIAL          no cumple un requisito especial (año o semestre completo)
    6. R-TOPE-MIN          no alcanza el mínimo de créditos del semestre

Cuando varias reglas fallan, se cita la primera de esa lista.
"""

import json
from pathlib import Path

RUTA_MALLA = Path(__file__).resolve().parent.parent / "datos" / "malla.json"

APROBADA = "aprobada"
INSCRITA = "inscrita"
REPROBADA = "reprobada"
NO_CURSADA = "no_cursada"

CUMPLE = "cumple"
CONDICIONAL = "cumple_condicional"
NO_CUMPLE = "no_cumple"


class Verificador:
    def __init__(self, ruta_malla=RUTA_MALLA):
        with open(ruta_malla, encoding="utf-8") as f:
            self.malla = json.load(f)
        self.asig = {a["codigo"]: a for a in self.malla["asignaturas"]}
        self.reglas = self.malla["reglas_globales"]
        self.especiales = self.malla["requisitos_especiales_def"]
        self.tope_max = self.reglas["R-TOPE-MAX"]["valor"]
        self.tope_min = self.reglas["R-TOPE-MIN"]["valor"]
        self.practicas = set(self.reglas["R-PRACTICAS-NO-SUMAN"]["codigos"])
        self.umbral_excepcion = self.reglas["R-EXCEPCION-PRERREQ"]["umbral_creditos_inscritos"]

    # ---------- helpers de historial ----------

    def estado(self, historial, codigo):
        return historial.get(codigo, NO_CURSADA)

    def creditos_aprobados(self, historial):
        """Créditos efectivamente aprobados hoy. Los de práctica SÍ suman acá."""
        return sum(self.asig[c]["creditos"]
                   for c, e in historial.items()
                   if e == APROBADA and c in self.asig)

    def creditos_si_aprueba_lo_inscrito(self, historial):
        """Créditos que tendrá el próximo semestre si aprueba todo lo que cursa hoy."""
        return self.creditos_aprobados(historial) + sum(
            self.asig[c]["creditos"]
            for c, e in historial.items()
            if e == INSCRITA and c in self.asig)

    def _satisface(self, historial, codigo, periodo):
        """¿El ramo `codigo` cuenta como aprobado en el período consultado?"""
        e = self.estado(historial, codigo)
        if e == APROBADA:
            return CUMPLE
        if e == INSCRITA and periodo == "proximo":
            return CONDICIONAL
        return NO_CUMPLE

    def _conjunto_semestres_ok(self, historial, semestres, periodo):
        """¿Están aprobadas todas las asignaturas de esos semestres?"""
        peor = CUMPLE
        faltante = None
        for a in self.malla["asignaturas"]:
            if a["semestre"] not in semestres:
                continue
            r = self._satisface(historial, a["codigo"], periodo)
            if r == NO_CUMPLE:
                return NO_CUMPLE, a["codigo"]
            if r == CONDICIONAL and peor == CUMPLE:
                peor, faltante = CONDICIONAL, a["codigo"]
        return peor, faltante

    # ---------- evaluación ----------

    def evaluar(self, historial, consulta):
        """
        historial: {codigo: estado}
        consulta:  {"ramos": [codigos], "periodo": "actual"|"proximo",
                    "creditos_ya_inscritos": int}

        Devuelve {"decision": "sí"|"no"|"condicional", "regla": str, "detalle": str}
        """
        ramos = consulta["ramos"]
        periodo = consulta.get("periodo", "actual")
        ya_inscritos = consulta.get("creditos_ya_inscritos", 0)

        cred_aprob = (self.creditos_aprobados(historial) if periodo == "actual"
                      else self.creditos_si_aprueba_lo_inscrito(historial))
        hay_condicional = False

        # Régimen de excepción: un estudiante que inscribe menos del mínimo de créditos
        # puede pedir excepción de prerrequisitos por reglamento. En ese régimen un
        # prerrequisito faltante no es un "no", es un "condicional": requiere autorización.
        # La excepción cubre SOLO prerrequisitos, no los umbrales de créditos aprobados
        # ni los requisitos especiales de año completo.
        cred_pedidos_prev = sum(self.asig[c]["creditos"] for c in ramos
                                if c not in self.practicas and c in self.asig)
        bajo_minimo = (cred_pedidos_prev + ya_inscritos) < self.tope_min

        # --- 1. R-YA-CURSADA ---
        for c in ramos:
            e = self.estado(historial, c)
            if e in (APROBADA, INSCRITA):
                return self._r("no", "R-YA-CURSADA",
                               f"{c} ya está {e}; no corresponde inscribirla de nuevo")

        # --- 2. R-TOPE-MAX ---
        cred_pedidos = sum(self.asig[c]["creditos"] for c in ramos if c not in self.practicas)
        total = cred_pedidos + ya_inscritos
        if total > self.tope_max:
            return self._r("no", "R-TOPE-MAX",
                           f"{total} créditos superan el máximo de {self.tope_max}")

        # --- 3. PRERREQUISITOS ---
        for c in ramos:
            for p in self.asig[c]["prerrequisitos"]:
                r = self._satisface(historial, p, periodo)
                if r == NO_CUMPLE:
                    if bajo_minimo:
                        return self._r("condicional", "R-EXCEPCION-PRERREQ",
                                       f"falta {p} ({self.asig[p]['nombre']}), pero con menos de "
                                       f"{self.tope_min} créditos inscritos procede excepción por reglamento")
                    return self._r("no", p,
                                   f"{c} requiere {p} ({self.asig[p]['nombre']}), "
                                   f"que está {self.estado(historial, p)}")
                if r == CONDICIONAL:
                    hay_condicional = True

        # --- 4. R-CREDITOS-MINIMOS ---
        for c in ramos:
            umbral = self.asig[c]["creditos_minimos"]
            if umbral and cred_aprob < umbral:
                return self._r("no", "R-CREDITOS-MINIMOS",
                               f"{c} exige {umbral} créditos aprobados; tiene {cred_aprob}")

        # --- 5. REQUISITOS ESPECIALES ---
        for c in ramos:
            for req in self.asig[c]["requisitos_especiales"]:
                sems = self.especiales[req]["semestres"]
                r, falta = self._conjunto_semestres_ok(historial, sems, periodo)
                if r == NO_CUMPLE:
                    return self._r("no", f"R-ESPECIAL-{req}",
                                   f"{c} exige {req}; falta {falta} "
                                   f"({self.asig[falta]['nombre']})")
                if r == CONDICIONAL:
                    hay_condicional = True

        # --- 6. R-TOPE-MIN ---
        if total < self.tope_min:
            return self._r("condicional", "R-EXCEPCION-PRERREQ",
                           f"{total} créditos están bajo el mínimo de {self.tope_min}: "
                           f"requiere autorización por reglamento")

        if hay_condicional:
            return self._r("condicional", "R-DEPENDE-APROBACION",
                           "cumple solo si aprueba lo que cursa este semestre")
        return self._r("sí", "R-SIN-IMPEDIMENTO", "cumple todas las reglas")

    def _r(self, decision, regla, detalle):
        return {"decision": decision, "regla": regla, "detalle": detalle}


# ============================================================================
# Casos de control — criterio de salida de la Fase 2.
# Resueltos a mano contra la malla antes de generar un solo caso sintético.
# ============================================================================

def _historial(aprobadas=(), inscritas=(), reprobadas=()):
    h = {}
    for c in aprobadas:
        h[c] = APROBADA
    for c in inscritas:
        h[c] = INSCRITA
    for c in reprobadas:
        h[c] = REPROBADA
    return h


SEM1 = ["510140", "525140", "527140", "531140", "580120"]
SEM2 = ["510150", "525150", "527150", "531150", "500151"]
SEM3 = ["521227", "525223", "503203", "523219", "890050", "580201"]
SEM4 = ["523325", "521230", "541271", "541203", "580211", "890051"]

CASOS = [
    {
        "nombre": "Prerrequisito directo faltante",
        "historial": _historial(aprobadas=SEM1),
        "consulta": {"ramos": ["521227"], "periodo": "actual", "creditos_ya_inscritos": 10},
        "esperado": {"decision": "no", "regla": "527150"},
        "porque": "Cálculo III requiere Cálculo II, que no está cursado",
    },
    {
        "nombre": "Ramo en curso NO cuenta en el período actual",
        "historial": _historial(aprobadas=SEM1, inscritas=["527150"]),
        "consulta": {"ramos": ["521227"], "periodo": "actual", "creditos_ya_inscritos": 10},
        "esperado": {"decision": "no", "regla": "527150"},
        "porque": "Cálculo II está inscrita, no aprobada: hoy no habilita",
    },
    {
        "nombre": "Ramo en curso SÍ habilita el próximo semestre, condicionado",
        "historial": _historial(aprobadas=SEM1, inscritas=["527150", "525150"]),
        "consulta": {"ramos": ["521227"], "periodo": "proximo", "creditos_ya_inscritos": 10},
        "esperado": {"decision": "condicional", "regla": "R-DEPENDE-APROBACION"},
        "porque": "El próximo semestre Cálculo II y Álgebra II estarán aprobadas si las pasa",
    },
    {
        "nombre": "Prerrequisito OK pero umbral de créditos no alcanza",
        "historial": _historial(aprobadas=SEM1 + SEM2 + SEM3 + SEM4 + ["541340", "580315"]),
        "consulta": {"ramos": ["580512"], "periodo": "actual", "creditos_ya_inscritos": 10},
        "esperado": {"decision": "no", "regla": "R-CREDITOS-MINIMOS"},
        "porque": "Diseño de Sistemas de Producción tiene Optimización I aprobada, pero exige 150 créditos",
    },
    {
        "nombre": "Excede el tope de 24 créditos",
        "historial": _historial(aprobadas=SEM1 + SEM2),
        "consulta": {"ramos": ["521227", "525223"], "periodo": "actual", "creditos_ya_inscritos": 18},
        "esperado": {"decision": "no", "regla": "R-TOPE-MAX"},
        "porque": "5 + 4 + 18 = 27 créditos, sobre el máximo de 24",
    },
    {
        "nombre": "Requisito especial: año completo",
        "historial": _historial(aprobadas=SEM1 + [c for c in SEM2 if c != "500151"]),
        "consulta": {"ramos": ["890050"], "periodo": "actual", "creditos_ya_inscritos": 10},
        "esperado": {"decision": "no", "regla": "R-ESPECIAL-primer_anio_aprobado"},
        "porque": "Inglés I exige el primer año completo; falta Introducción a la Innovación",
    },
    {
        "nombre": "Régimen de excepción: bajo el mínimo, el prerrequisito faltante es condicional",
        "historial": _historial(aprobadas=SEM1),
        "consulta": {"ramos": ["521227"], "periodo": "actual", "creditos_ya_inscritos": 0},
        "esperado": {"decision": "condicional", "regla": "R-EXCEPCION-PRERREQ"},
        "porque": "5 créditos están bajo el mínimo de 8, así que procede excepción de prerrequisitos",
    },
    {
        "nombre": "Bajo el mínimo sin nada más que falle: también condicional",
        "historial": _historial(aprobadas=SEM1 + SEM2),
        "consulta": {"ramos": ["521227"], "periodo": "actual", "creditos_ya_inscritos": 0},
        "esperado": {"decision": "condicional", "regla": "R-EXCEPCION-PRERREQ"},
        "porque": "Prerrequisitos cumplidos pero 5 créditos no alcanzan el mínimo de 8",
    },
    {
        "nombre": "Todo en regla",
        "historial": _historial(aprobadas=SEM1 + SEM2),
        "consulta": {"ramos": ["521227", "525223"], "periodo": "actual", "creditos_ya_inscritos": 10},
        "esperado": {"decision": "sí", "regla": "R-SIN-IMPEDIMENTO"},
        "porque": "Prerrequisitos cumplidos y 5 + 4 + 10 = 19 créditos, dentro del tope",
    },
]


def main():
    v = Verificador()
    print(f"Malla: {len(v.asig)} asignaturas · tope {v.tope_min}-{v.tope_max} créditos\n")
    ok = 0
    for i, caso in enumerate(CASOS, 1):
        r = v.evaluar(caso["historial"], caso["consulta"])
        bien = (r["decision"] == caso["esperado"]["decision"]
                and r["regla"] == caso["esperado"]["regla"])
        ok += bien
        print(f"[{'OK ' if bien else 'FALLA'}] {i}. {caso['nombre']}")
        print(f"        esperado: {caso['esperado']['decision']:12} regla {caso['esperado']['regla']}")
        print(f"        obtenido: {r['decision']:12} regla {r['regla']}")
        print(f"        {r['detalle']}")
        if not bien:
            print(f"        razón del caso: {caso['porque']}")
        print()
    print(f"{ok}/{len(CASOS)} casos de control correctos")
    return 0 if ok == len(CASOS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
