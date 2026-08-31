# -*- coding: utf-8 -*-
"""
Generador de casos de prueba — validación de inscripción de ramos.

Genera casos SINTÉTICOS y ETIQUETADOS: historial + pregunta en prosa + respuesta correcta.
La etiqueta la pone el verificador determinista, no el generador.

Dos decisiones de diseño que sostienen la calidad del test set:

1. GENERACIÓN HACIA ATRÁS. No se sortea un historial y se ve qué sale. Se elige primero
   la respuesta objetivo (qué regla debe ser la que decide) y se construye el historial
   que la produce. Así la distribución de respuestas queda balanceada por construcción,
   en vez de quedar sesgada al azar.

2. AUTOVERIFICACIÓN. Cada caso se pasa por el verificador y se descarta si no salió la
   respuesta que el constructor pretendía. Un desacuerdo es un bug del generador, y se
   detecta al instante en vez de contaminar el test set.

Niveles de dificultad — las cinco perillas:

    perilla                nivel 1          nivel 2               nivel 3
    ---------------------- ---------------- --------------------- ----------------------
    referencia al ramo     nombre completo  nombre abreviado      coloquial / sigla
    período                explícito        "el próximo semestre" vago
    ramos en la pregunta   1                1                     2
    distractores           ninguno          uno reprobado         reprobado + en curso
    profundidad de cadena  1 salto          2 saltos              3+ saltos

Cada caso trae además su versión de PREGUNTA LIMPIA: la misma consulta con código y
estado explícitos. Correr las dos mitades y comparar es lo que prueba que la falla es de
interpretación y no de desconocimiento.
"""

import json
import random
import re
import unicodedata
from pathlib import Path

from verificador import (Verificador, APROBADA, INSCRITA, REPROBADA,
                         NO_CURSADA, RUTA_MALLA)

# ---------------------------------------------------------------- abreviaciones

ABREV_MANUAL = {
    "580421": ["PCP", "planificación de producción", "planificación y control"],
    "580311": ["multivariado", "análisis multivariado", "el multivariado"],
    "580423": ["calidad", "gestión de calidad"],
    "580512": ["diseño de sistemas", "diseño de producción"],
    "580513": ["evaluación de proyectos", "evapro"],
    "580525": ["dirección de proyectos", "control de proyectos"],
    "523325": ["inferencia", "inferencia estadística"],
    "580315": ["opti I", "optimización 1"],
    "580325": ["opti II", "optimización 2", "la II de optimización"],
    "525223": ["ecuaciones", "ecuaciones diferenciales", "EDO"],
    "521230": ["cálculo numérico", "numérico"],
    "503700": ["TI", "tecnologías de la información"],
    "580514": ["gestión de personas", "comportamiento organizacional"],
    "554150": ["sustentabilidad", "la de sustentabilidad"],
    "500151": ["intro a la innovación", "la intro de innovación"],
    "580120": ["habilidades de gestión", "desarrollo de habilidades"],
}

ROMANOS = {"I": "1", "II": "2", "III": "3"}


def _abreviar(asig):
    """Formas coloquiales de nombrar un ramo, como lo diría un estudiante."""
    cod, nombre = asig["codigo"], asig["nombre"]
    formas = list(ABREV_MANUAL.get(cod, []))
    m = re.match(r"^(.*?)\s+(I{1,3})$", nombre)
    if m:
        base, rom = m.group(1), m.group(2)
        formas += [f"{base} {ROMANOS[rom]}", f"la {rom}", f"la {rom} de {base.lower()}"]
    else:
        palabras = [p for p in nombre.split() if len(p) > 3 and p.lower() not in
                    ("para", "general", "nivel", "básico", "comunicativo")]
        if palabras:
            formas.append(palabras[0].lower())
    return formas or [nombre]


# ---------------------------------------------------------------- plantillas

APERTURAS = ["", "oye, ", "hola, una consulta: ", "disculpa, ", "una duda: ",
             "hola profe, ", "oye una consulta, "]

VERBOS = ["¿puedo inscribir", "¿alcanzo a meter", "¿me dejan tomar",
          "¿puedo tomar", "¿podría inscribir", "¿me sirve para tomar"]

PERIODO_TXT = {
    ("actual", 1):   ["este semestre", "ahora, este semestre"],
    ("actual", 2):   ["ahora", "este semestre"],
    ("actual", 3):   ["ahora ya", "de una vez"],
    ("proximo", 1):  ["el próximo semestre", "el semestre siguiente"],
    ("proximo", 2):  ["el próximo semestre", "el que viene"],
    ("proximo", 3):  ["cuando salga de esto", "el que viene", "para el otro semestre"],
}

ESTADO_INSCRITA_TXT = ["la estoy tomando ahora", "la estoy cursando", "la tengo inscrita",
                       "estoy en eso ahora", "la estoy dando este semestre"]

ESTADO_REPROBADA_TXT = ["la reprobé", "me la eché", "la tengo pendiente porque la reprobé",
                        "no la pasé"]


# ---------------------------------------------------------------- generador

class Generador:
    def __init__(self, ruta_malla=RUTA_MALLA, seed=20260830):
        self.v = Verificador(ruta_malla)
        self.malla = self.v.malla
        self.asig = self.v.asig
        self.rnd = random.Random(seed)
        self.por_sem = {}
        for a in self.malla["asignaturas"]:
            self.por_sem.setdefault(a["semestre"], []).append(a)

    # ---------- historiales ----------

    def _aprobar_hasta(self, semestre):
        """Historial de un estudiante al día que terminó el semestre indicado."""
        h = {}
        for s in range(1, semestre + 1):
            for a in self.por_sem[s]:
                h[a["codigo"]] = APROBADA
        return h

    def _agregar_distractores(self, h, nivel, evitar):
        """Ruido realista: ramos reprobados o en curso que no cambian la respuesta."""
        rasgos = []
        if nivel < 2:
            return rasgos
        candidatos = [c for c, e in h.items() if e == APROBADA and c not in evitar]
        self.rnd.shuffle(candidatos)
        if candidatos:
            h[candidatos[0]] = REPROBADA
            rasgos.append("distractor_reprobado")
        if nivel >= 3 and len(candidatos) > 1:
            h[candidatos[1]] = INSCRITA
            rasgos.append("distractor_inscrita")
        return rasgos

    def _cadena(self, codigo, prof=0):
        """Todos los prerrequisitos transitivos de un ramo, con su profundidad."""
        out = {}
        for p in self.asig[codigo]["prerrequisitos"]:
            out[p] = max(out.get(p, 0), prof + 1)
            for q, d in self._cadena(p, prof + 1).items():
                out[q] = max(out.get(q, 0), d)
        return out

    def _profundidad(self, codigo):
        c = self._cadena(codigo)
        return max(c.values()) if c else 0

    def _ramos_con_profundidad(self, minimo, maximo=99):
        return [a for a in self.malla["asignaturas"]
                if minimo <= self._profundidad(a["codigo"]) <= maximo
                and a["semestre"] >= 3]

    # ---------- constructores por regla ----------

    def _periodo_libre(self):
        """Período sorteado. Rompe la correlación período <-> respuesta: si el período
        siempre acompañara a la misma decisión, el modelo acertaría leyendo solo eso."""
        return self.rnd.choice(["actual", "proximo"])

    def _c_prerrequisito(self, nivel):
        """Falta un prerrequisito -> no, citando el código faltante.
        Vale para los dos períodos: un ramo reprobado o no cursado tampoco estará
        aprobado el próximo semestre."""
        prof = {1: (1, 1), 2: (2, 2), 3: (3, 9)}[nivel]
        cands = self._ramos_con_profundidad(*prof)
        obj = self.rnd.choice(cands)
        h = self._aprobar_hasta(obj["semestre"] - 1)
        falta = self.rnd.choice(obj["prerrequisitos"])
        h[falta] = self.rnd.choice([NO_CURSADA, REPROBADA])
        if h[falta] == NO_CURSADA:
            del h[falta]
        rasgos = self._agregar_distractores(h, nivel, evitar={falta, obj["codigo"]})
        return obj, h, self._periodo_libre(), 12, falta, rasgos

    def _c_excepcion(self, nivel):
        """Falta un prerrequisito PERO la carga está bajo el mínimo -> condicional
        en período actual. Es el contrapeso de _c_inscrita_proximo: sin este, todo
        condicional vendría acompañado de 'el próximo semestre'."""
        prof = {1: (1, 1), 2: (2, 2), 3: (3, 9)}[nivel]
        cands = [a for a in self._ramos_con_profundidad(*prof)
                 if a["creditos"] < self.v.tope_min]
        obj = self.rnd.choice(cands)
        h = self._aprobar_hasta(obj["semestre"] - 1)
        falta = self.rnd.choice(obj["prerrequisitos"])
        del h[falta]
        rasgos = self._agregar_distractores(h, nivel, evitar={falta, obj["codigo"]})
        rasgos.append("carga_baja")
        return obj, h, "actual", 0, "R-EXCEPCION-PRERREQ", rasgos

    def _c_inscrita_proximo(self, nivel):
        """Prerrequisito en curso + período próximo -> condicional. Mecanismo E1."""
        prof = {1: (1, 1), 2: (2, 2), 3: (2, 9)}[nivel]
        cands = self._ramos_con_profundidad(*prof)
        obj = self.rnd.choice(cands)
        h = self._aprobar_hasta(obj["semestre"] - 1)
        cursando = self.rnd.choice(obj["prerrequisitos"])
        h[cursando] = INSCRITA
        rasgos = self._agregar_distractores(h, nivel, evitar={cursando, obj["codigo"]})
        rasgos.append("prerreq_en_curso")
        return obj, h, "proximo", 12, "R-DEPENDE-APROBACION", rasgos

    def _c_inscrita_actual(self, nivel):
        """Prerrequisito EN CURSO pero período ACTUAL -> no. Mecanismo E1 puro.

        Este constructor es el par exacto de _c_inscrita_proximo y existe para romper
        el atajo más peligroso del test set: si cada vez que la pregunta dice "la estoy
        tomando ahora" la respuesta fuera condicional, el modelo acertaría reconociendo
        esa frase, sin resolver nunca la referencia temporal. Con los dos constructores,
        la MISMA frase lleva a respuestas distintas y solo el período las separa."""
        prof = {1: (1, 1), 2: (2, 2), 3: (2, 9)}[nivel]
        cands = self._ramos_con_profundidad(*prof)
        obj = self.rnd.choice(cands)
        h = self._aprobar_hasta(obj["semestre"] - 1)
        cursando = self.rnd.choice(obj["prerrequisitos"])
        h[cursando] = INSCRITA
        rasgos = self._agregar_distractores(h, nivel, evitar={cursando, obj["codigo"]})
        rasgos.append("prerreq_en_curso")
        return obj, h, "actual", 12, cursando, rasgos

    def _c_creditos(self, nivel):
        """Prerrequisitos OK pero no alcanza el umbral de créditos -> no."""
        cands = [a for a in self.malla["asignaturas"] if a["creditos_minimos"]]
        obj = self.rnd.choice(cands)
        # historial que satisface los prerrequisitos pero queda corto de créditos
        h = {}
        for c in self._cadena(obj["codigo"]):
            h[c] = APROBADA
        umbral = obj["creditos_minimos"]
        extras = [a for a in self.malla["asignaturas"]
                  if a["codigo"] not in h and a["codigo"] != obj["codigo"]
                  and a["semestre"] < obj["semestre"]]
        self.rnd.shuffle(extras)
        for a in extras:
            if self.v.creditos_aprobados(h) + a["creditos"] >= umbral:
                continue
            h[a["codigo"]] = APROBADA
        rasgos = self._agregar_distractores(h, nivel, evitar=set(self._cadena(obj["codigo"])))
        rasgos.append("umbral_creditos")
        return obj, h, self._periodo_libre(), 12, "R-CREDITOS-MINIMOS", rasgos

    def _c_tope_max(self, nivel):
        """La carga pedida supera el tope de 24 -> no."""
        cands = self._ramos_con_profundidad(1, 9)
        obj = self.rnd.choice(cands)
        h = self._aprobar_hasta(obj["semestre"] - 1)
        ya = self.v.tope_max - obj["creditos"] + self.rnd.randint(1, 4)
        rasgos = self._agregar_distractores(h, nivel, evitar={obj["codigo"]})
        rasgos.append("tope_creditos")
        return obj, h, self._periodo_libre(), ya, "R-TOPE-MAX", rasgos

    def _c_especial(self, nivel):
        """Falta un año o semestre completo -> no."""
        cands = [a for a in self.malla["asignaturas"] if a["requisitos_especiales"]
                 and a["codigo"] != "580695"]
        obj = self.rnd.choice(cands)
        req = obj["requisitos_especiales"][0]
        sems = self.malla["requisitos_especiales_def"][req]["semestres"]
        h = self._aprobar_hasta(obj["semestre"] - 1)
        for c in self._cadena(obj["codigo"]):
            h[c] = APROBADA
        # romper exactamente un ramo del conjunto exigido
        del_cands = [a["codigo"] for a in self.malla["asignaturas"]
                     if a["semestre"] in sems and a["codigo"] not in self._cadena(obj["codigo"])]
        roto = self.rnd.choice(del_cands)
        h[roto] = REPROBADA
        rasgos = ["requisito_especial"]
        return obj, h, "actual", 12, f"R-ESPECIAL-{req}", rasgos

    def _c_ok(self, nivel):
        """Todo en regla -> sí."""
        prof = {1: (1, 1), 2: (2, 2), 3: (3, 9)}[nivel]
        cands = self._ramos_con_profundidad(*prof)
        obj = self.rnd.choice(cands)
        h = self._aprobar_hasta(obj["semestre"] - 1)
        rasgos = self._agregar_distractores(
            h, nivel, evitar=set(self._cadena(obj["codigo"])) | {obj["codigo"]})
        return obj, h, self._periodo_libre(), 12, "R-SIN-IMPEDIMENTO", rasgos

    CONSTRUCTORES = ["_c_prerrequisito", "_c_inscrita_proximo", "_c_inscrita_actual",
                     "_c_creditos", "_c_tope_max", "_c_especial", "_c_ok",
                     "_c_excepcion", "_c_ok", "_c_inscrita_proximo",
                     "_c_inscrita_actual", "_c_prerrequisito"]

    # ---------- redacción ----------

    def _referir(self, asig, nivel):
        if nivel == 1:
            return asig["nombre"], "nombre_completo"
        formas = _abreviar(asig)
        if nivel == 2:
            return self.rnd.choice(formas), "nombre_abreviado"
        return self.rnd.choice(formas), "coloquial"

    def _redactar(self, obj, h, periodo, nivel, ya_inscritos):
        ref, tipo_ref = self._referir(obj, nivel)
        per = self.rnd.choice(PERIODO_TXT[(periodo, nivel)])
        partes = []

        # mencionar en prosa algún ramo en curso o reprobado que venga al caso
        menciones = []
        for c in obj["prerrequisitos"]:
            e = h.get(c, NO_CURSADA)
            if e == INSCRITA:
                nom, _ = self._referir(self.asig[c], nivel)
                menciones.append(f"{'me falta ' if nivel > 1 else ''}{nom} pero "
                                 f"{self.rnd.choice(ESTADO_INSCRITA_TXT)}")
            elif e == REPROBADA and nivel >= 2:
                nom, _ = self._referir(self.asig[c], nivel)
                menciones.append(f"{nom}, {self.rnd.choice(ESTADO_REPROBADA_TXT)}")
        if menciones:
            partes.append(self.rnd.choice(menciones))

        apertura = self.rnd.choice(APERTURAS) if nivel >= 2 else ""
        verbo = self.rnd.choice(VERBOS) if nivel >= 2 else "¿puedo inscribir"
        nucleo = f"{verbo} {ref} {per}?"
        prosa = apertura + (", ".join(partes) + ", " if partes else "") + nucleo
        prosa = prosa[0].upper() + prosa[1:] if prosa else prosa

        # La pregunta limpia debe diferenciarse de la prosa SOLO en la ambigüedad.
        # La versión anterior repetía los créditos ya inscritos, que el prompt ya entrega
        # en su propia línea: esa redundancia sesgó al modelo hacia R-TOPE-MAX en la
        # corrida del 30-08 (21/21 predicciones). Corregido: sin mención de créditos.
        limpia = (f"¿Puedo inscribir {obj['codigo']} ({obj['nombre']}) "
                  f"en {'2026-2' if periodo == 'actual' else '2027-1'}?")
        return prosa, limpia, tipo_ref

    # ---------- caso completo ----------

    def generar_caso(self, nivel, constructor):
        obj, h, periodo, ya, regla_esperada, rasgos = getattr(self, constructor)(nivel)
        consulta = {"ramos": [obj["codigo"]], "periodo": periodo,
                    "creditos_ya_inscritos": ya}
        r = self.v.evaluar(h, consulta)

        # autoverificación: el constructor declaró una regla; el verificador debe coincidir
        if r["regla"] != regla_esperada:
            return None

        prosa, limpia, tipo_ref = self._redactar(obj, h, periodo, nivel, ya)
        return {
            "nivel": nivel,
            "constructor": constructor,
            "historial": h,
            "consulta": consulta,
            "pregunta_prosa": prosa,
            "pregunta_limpia": limpia,
            "respuesta": {"decision": r["decision"], "regla": r["regla"]},
            "detalle": r["detalle"],
            "rasgos": sorted(set(rasgos + [tipo_ref, f"periodo_{periodo}"])),
            "profundidad_cadena": self._profundidad(obj["codigo"]),
            "ramo_objetivo": {"codigo": obj["codigo"], "nombre": obj["nombre"]},
        }

    # Qué decisión produce cada constructor. Se usa para balancear el lote.
    POR_DECISION = {
        "no":          ["_c_prerrequisito", "_c_inscrita_actual", "_c_creditos",
                        "_c_tope_max", "_c_especial"],
        "condicional": ["_c_inscrita_proximo", "_c_excepcion"],
        "sí":          ["_c_ok"],
    }

    def generar_lote(self, n_por_nivel=7, niveles=(1, 2, 3), intentos_max=3000):
        """Lote con la decisión BALANCEADA dentro de cada nivel.

        El desbalance importa: en la corrida del 30-08 el test set traía 15 "no" de 21,
        y por eso responder siempre "no" sacaba 71,4%. Con los tres valores parejos esa
        constante baja a ~33% y el colapso del modelo queda a la vista."""
        casos = []
        for nivel in niveles:
            base, resto = divmod(n_por_nivel, 3)
            cupos = {"no": base, "condicional": base, "sí": base}
            for k in list(cupos)[:resto]:
                cupos[k] += 1
            for decision, cupo in cupos.items():
                familia = self.POR_DECISION[decision]
                hechos, i = 0, 0
                while hechos < cupo and i < intentos_max:
                    cons = familia[i % len(familia)]
                    i += 1
                    c = self.generar_caso(nivel, cons)
                    if c and c["respuesta"]["decision"] == decision:
                        casos.append(c)
                        hechos += 1
        return casos


# ---------------------------------------------------------------- balance

def tabla_balance(casos):
    """Cruce rasgo x decisión. Una celda vacía o dominada es un atajo explotable."""
    rasgos = sorted({r for c in casos for r in c["rasgos"]})
    decisiones = ["sí", "no", "condicional"]
    filas = []
    for r in rasgos:
        sub = [c for c in casos if r in c["rasgos"]]
        conteo = {d: sum(1 for c in sub if c["respuesta"]["decision"] == d) for d in decisiones}
        filas.append((r, len(sub), conteo))
    return decisiones, filas


def main():
    g = Generador()
    casos = g.generar_lote(n_por_nivel=20)

    salida = Path(__file__).resolve().parent.parent / "datos" / "casos.jsonl"
    with open(salida, "w", encoding="utf-8") as f:
        for c in casos:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"{len(casos)} casos generados -> {salida.name}\n")

    print("=" * 78)
    print("DISTRIBUCIÓN")
    print("=" * 78)
    for nivel in (1, 2, 3):
        sub = [c for c in casos if c["nivel"] == nivel]
        dec = {}
        for c in sub:
            dec[c["respuesta"]["decision"]] = dec.get(c["respuesta"]["decision"], 0) + 1
        prof = [c["profundidad_cadena"] for c in sub]
        print(f"  nivel {nivel}: {len(sub):2} casos · {dec} · "
              f"profundidad {min(prof)}-{max(prof)}")

    reglas = {}
    for c in casos:
        reglas[c["respuesta"]["regla"]] = reglas.get(c["respuesta"]["regla"], 0) + 1
    print("\n  reglas citadas:")
    for r, n in sorted(reglas.items(), key=lambda x: -x[1]):
        print(f"    {n:3}  {r}")

    print()
    print("=" * 78)
    print("CHEQUEO DE BALANCE — rasgo x decisión")
    print("=" * 78)
    decisiones, filas = tabla_balance(casos)
    print(f"{'rasgo':26} {'n':>3} " + " ".join(f"{d:>12}" for d in decisiones) + "   alerta")
    for r, n, conteo in filas:
        dominado = n >= 4 and max(conteo.values()) == n
        alerta = "<-- ATAJO: una sola respuesta" if dominado else ""
        print(f"{r:26} {n:3} " + " ".join(f"{conteo[d]:12}" for d in decisiones) + f"   {alerta}")

    print()
    print("=" * 78)
    print("MUESTRA DE PREGUNTAS")
    print("=" * 78)
    for nivel in (1, 2, 3):
        sub = [c for c in casos if c["nivel"] == nivel]
        print(f"\n--- nivel {nivel} ---")
        for c in sub[:3]:
            print(f"  prosa   : {c['pregunta_prosa']}")
            print(f"  limpia  : {c['pregunta_limpia']}")
            print(f"  respuesta: {c['respuesta']['decision']} / {c['respuesta']['regla']}")
            print(f"  {c['detalle']}")
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
