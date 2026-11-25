# -*- coding: utf-8 -*-
"""
Datos de entrenamiento del Intérprete (A) para el D4. Se arman DESPUÉS de sellar la prueba
(`datos/prueba_d4/SELLO.txt`, commit 6b54eac) y se filtran contra ella y contra todo conjunto
anterior.

Composición, fijada en `PLAN_D4.md` antes de generar:

  prosa       1.200  mensajes de subagentes de Claude (Anthropic) con instrucción propia
                     (`datos/entrenamiento_d4/INSTRUCCION.md`), distinta de la de la prueba.
                     50 % de constructores donde decide el período (`_c_inscrita_actual` y
                     `_c_inscrita_proximo`), el resto en la proporción del piloto.
  revision       60  turnos con un rechazo previo en la entrada: 30 con rechazo fundado (la
                     respuesta anterior estaba mal y se corrige) y 30 con rechazo infundado (la
                     anterior estaba bien y se mantiene). Mensajes de los mismos redactores.
  plantilla     150  preguntas del generador, con la etiqueta del generador etiquetado
                     (`datos_d4.GeneradorEtiquetado`).
  sin_ramo       20  mensajes que no piden ningún ramo, de un subagente aparte.

De dónde sale cada parte de la etiqueta:
  periodo                        el caso del generador. Nadie lo escribe.
  consultado, otros, frase_periodo  las palabras que el redactor declara haber usado. Este
                                 script exige que estén literalmente en el mensaje; si no, el
                                 par se descarta y se cuenta.

    python preparar_entrenamiento_d4.py elegir     -> casos y lotes para los redactores
    python preparar_entrenamiento_d4.py verificar  -> lee los lotes redactados, controla y cuenta
    python preparar_entrenamiento_d4.py unir       -> entrenamiento.jsonl y validacion.jsonl
"""

import json
import random
import sys
from pathlib import Path

import agentes as A
from datos_d4 import generar_pares
from generador import Generador
from preparar_piloto_d4 import PERIODO_ESTILOS, RAMO_ESTILOS, contexto
from preparar_prueba_v5 import clave, pregunta

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
SALIDA = DATOS / "entrenamiento_d4"
LOTES = SALIDA / "lotes"
BASE = SALIDA / "casos.jsonl"
SEMILLA = 20261128
SEMILLA_PLANTILLA = 20261129
SEMILLA_VALIDACION = 20261130
POR_LOTE = 60
N_PROSA, N_REVISION, N_PLANTILLA, N_SIN_RAMO = 1200, 60, 150, 20
VALIDACION = 0.10
EXCLUIR = ["casos.jsonl", "casos_nuevos.jsonl", "casos_redactados.jsonl",
           "casos_desarrollo.jsonl", "casos_desarrollo_redactados.jsonl",
           "prueba_v5/plantilla_a.jsonl", "prueba_v5/plantilla_b.jsonl",
           "prueba_v5/base_redactados.jsonl", "prueba_v5/redactados.jsonl",
           "piloto_d4/base.jsonl", "piloto_d4/piloto.jsonl",
           "prueba_d4/plantilla.jsonl", "prueba_d4/base_redactados.jsonl",
           "prueba_d4/redactados.jsonl"]
N_REDACTADOS = N_PROSA + N_REVISION
# 50 % donde decide el período; el resto en la proporción del piloto (4:6:4:2:2:2 sobre 20).
CUPOS = [("_c_inscrita_actual", 315), ("_c_inscrita_proximo", 315),
         ("_c_prerrequisito", 153), ("_c_ok", 189), ("_c_excepcion", 126),
         ("_c_creditos", 63), ("_c_tope_max", 63), ("_c_especial", 36)]
# `_c_especial` da solo 36 casos nuevos (24 nov): los 27 que faltan van a `_c_prerrequisito`.
CUANDO = {"actual": "ACTUAL", "proximo": "PROXIMO"}
# Pares que salen tras leer los desacuerdos del lector a ciegas (24 nov, regla en
# `lector_entrenamiento_d4.py`). Motivo de cada uno:
QUITADOS = {1135: "\"el semestre de agosto\" en noviembre puede ser 2026-2 o 2027-2: ambiguo"}


def leer_jsonl(ruta):
    return [json.loads(l) for l in open(ruta, encoding="utf-8") if l.strip()]


def escribir_jsonl(ruta, filas):
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        for x in filas:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")


def excluidos():
    claves, preguntas = set(), set()
    for f in EXCLUIR:
        for c in leer_jsonl(DATOS / f):
            claves.add(clave(c))
            preguntas.add(pregunta(c))
            if "pregunta_plantilla" in c:
                preguntas.add(c["pregunta_plantilla"].strip().lower())
    return claves, preguntas


def elegir():
    if BASE.exists():
        print("Los casos ya existen; no se sobrescriben.")
        return 1
    assert sum(n for _, n in CUPOS) == N_REDACTADOS
    LOTES.mkdir(parents=True, exist_ok=True)
    claves, preguntas = excluidos()
    gen = Generador(seed=SEMILLA)
    casos, nuevas = [], set()
    for cons, cupo in CUPOS:
        hechos, i = 0, 0
        while hechos < cupo and i < 200000:
            i += 1
            c = gen.generar_caso((i % 3) + 1, cons)
            if not c:
                continue
            k = clave(c)
            if k in claves or k in nuevas or pregunta(c) in preguntas:
                continue
            nuevas.add(k)
            casos.append(c)
            hechos += 1
        if hechos < cupo:
            raise RuntimeError(f"{cons}: solo {hechos} de {cupo}")
    rnd = random.Random(SEMILLA)
    rnd.shuffle(casos)
    for i, c in enumerate(casos):
        c["id_ent"] = i
        c["estilo"] = {"periodo": PERIODO_ESTILOS[i % 3], "ramo": RAMO_ESTILOS[(i // 3) % 2]}
        # Los últimos 60 (al azar por el barajado) van a turnos de revisión, mitad y mitad.
        c["bloque"] = "prosa" if i < N_PROSA else "revision"
        if c["bloque"] == "revision":
            c["rechazo"] = "fundado" if (i - N_PROSA) % 2 == 0 else "infundado"
    escribir_jsonl(BASE, casos)
    for n in range(0, len(casos), POR_LOTE):
        filas = []
        for c in casos[n:n + POR_LOTE]:
            otro, estado = contexto(gen, c)
            filas.append({"id": str(c["id_ent"]), "ramo": c["ramo_objetivo"]["nombre"],
                          "cuando": CUANDO[c["consulta"]["periodo"]], "otro_ramo": otro,
                          "estado_otro": estado, "periodo_estilo": c["estilo"]["periodo"],
                          "ramo_estilo": c["estilo"]["ramo"]})
        (LOTES / f"lote_{n // POR_LOTE + 1:02d}.json").write_text(
            json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    dec = {}
    for c in casos:
        dec[c["constructor"]] = dec.get(c["constructor"], 0) + 1
    print(f"{len(casos)} casos -> {BASE.name}; {len(casos) // POR_LOTE} lotes de {POR_LOTE}")
    print(f"constructores {dec}")
    return 0


def _en(texto, frag):
    return bool(frag) and frag.lower() in texto.lower()


def verificar(imprimir=True):
    """Controla cada mensaje redactado contra lo que declaró su redactor. Devuelve los pares
    válidos (caso, mensaje, etiqueta) y los motivos de descarte."""
    casos = {c["id_ent"]: c for c in leer_jsonl(BASE)}
    gen = Generador(seed=0)
    validos, descartes, faltan = [], {}, []
    for ruta in sorted(LOTES.glob("lote_??.json")):
        salida = ruta.with_name(ruta.stem + "_redactado.json")
        if not salida.exists():
            faltan.append(salida.name)
            continue
        red = {str(k): v for k, v in json.loads(salida.read_text(encoding="utf-8")).items()}
        for fila in json.loads(ruta.read_text(encoding="utf-8")):
            c = casos[int(fila["id"])]
            r = red.get(fila["id"])
            motivo = None
            if not isinstance(r, dict) or not str(r.get("mensaje", "")).strip():
                motivo = "sin mensaje"
            else:
                m = r["mensaje"].strip()
                cons = str(r.get("palabras_ramo", "")).strip()
                otros = [str(o).strip() for o in (r.get("palabras_otro_ramo") or []) if str(o).strip()]
                frase = str(r.get("palabras_semestre", "")).strip()
                otro, _ = contexto(gen, c)
                if not _en(m, cons):
                    motivo = "palabras del ramo no están en el mensaje"
                elif any(not _en(m, o) for o in otros):
                    motivo = "palabras del otro ramo no están en el mensaje"
                elif otro and not otros:
                    motivo = "no declaró el otro ramo que la fila exige"
                elif frase and not _en(m, frase):
                    motivo = "palabras del semestre no están en el mensaje"
                elif not frase and c["consulta"]["periodo"] == "proximo":
                    motivo = "sin palabras de semestre en un caso del próximo"
                elif cons.lower() in [o.lower() for o in otros]:
                    motivo = "el ramo consultado aparece como otro"
            if not motivo and c["id_ent"] in QUITADOS:
                motivo = "quitado tras leer el desacuerdo del lector"
            if motivo:
                descartes[motivo] = descartes.get(motivo, 0) + 1
                continue
            # Se copian las palabras tal como aparecen en el mensaje (mayúsculas incluidas).
            def literal(frag):
                i = m.lower().find(frag.lower())
                return m[i:i + len(frag)]
            etiqueta = {"accion": "entregar", "consultado": literal(cons),
                        "otros": [literal(o) for o in otros], "frase_periodo": literal(frase) if frase else "",
                        "periodo": c["consulta"]["periodo"]}
            validos.append((c, m, etiqueta))
    if imprimir:
        print(f"lotes sin redactar: {len(faltan)}" + (f" ({', '.join(faltan[:5])}...)" if faltan else ""))
        print(f"pares válidos {len(validos)}; descartados {sum(descartes.values())} {descartes}")
    return validos, descartes, faltan


MOTIVOS_FUNDADO = {
    "periodo": "La consulta dice \"{frase}\", que habla {bien}, no {mal}.",
    "ramo": "La consulta pregunta por {cons}; {otro} es otra asignatura que menciona como contexto.",
}
MOTIVOS_INFUNDADO = {
    "periodo": "Revisa el período: la consulta podría hablar {mal}.",
    "ramo": "La asignatura consultada podría ser otra de las que nombra la consulta.",
}
SEM = {"actual": "del semestre en curso", "proximo": "del semestre siguiente"}
OTRO_PER = {"actual": "proximo", "proximo": "actual"}


def bloque_revision(c, et):
    """El bloque de revisión que el orquestador habría escrito (mismo formato que
    `agentes.interprete`), con un rechazo fundado o infundado."""
    per = et["periodo"]
    if c["rechazo"] == "fundado":
        if et["otros"]:
            anterior = {"consultado": et["otros"][0], "periodo": per}
            problema, motivo = "ramo", MOTIVOS_FUNDADO["ramo"].format(cons=et["consultado"], otro=et["otros"][0])
        else:
            anterior = {"consultado": et["consultado"], "periodo": OTRO_PER[per]}
            frase = et["frase_periodo"] or "nada sobre cuándo"
            problema, motivo = "periodo", MOTIVOS_FUNDADO["periodo"].format(
                frase=frase, bien=SEM[per], mal=SEM[OTRO_PER[per]])
    else:
        anterior = {"consultado": et["consultado"], "periodo": per}
        problema = "ramo" if et["otros"] else "periodo"
        motivo = MOTIVOS_INFUNDADO[problema].format(mal=SEM[OTRO_PER[per]])
    return ("\n=== REVISIÓN DE TU RESPUESTA ANTERIOR ===\n"
            f"Tu respuesta: asignatura \"{anterior['consultado']}\", "
            f"período {anterior['periodo']}.\n"
            f"Problema: {problema}. {motivo}\n")


def unir():
    validos, descartes, faltan = verificar(imprimir=True)
    if faltan:
        print("Faltan lotes; no se une.")
        return 1
    sin_ramo_ruta = SALIDA / "sin_ramo_redactado.json"
    if not sin_ramo_ruta.exists():
        print(f"Falta {sin_ramo_ruta.name}")
        return 1
    prompt = A.Prompt("interprete.md")
    pares = []

    def par(mensaje, revision, etiqueta, meta):
        pares.append({"prompt": prompt.mensajes(pregunta=mensaje, revision=revision),
                      "completion": [{"role": "assistant",
                                      "content": json.dumps(etiqueta, ensure_ascii=False)}],
                      "meta": dict(meta, pregunta=mensaje, prompt_hash=prompt.hash)})

    for c, m, et in validos:
        meta = {"bloque": c["bloque"], "constructor": c["constructor"], "estilo": c["estilo"],
                "id_ent": c["id_ent"], "clave": clave(c)}
        if c["bloque"] == "revision":
            meta["rechazo"] = c["rechazo"]
            par(m, bloque_revision(c, et), et, meta)
        else:
            par(m, "", et, meta)

    # Plantillas: excluye también los casos redactados de entrenamiento.
    import datos_d4
    datos_d4.EXCLUIR = EXCLUIR + [str(BASE.relative_to(DATOS)).replace("\\", "/")]
    # 24 nov: la primera unión dejó 9 plantillas de entrenamiento casi iguales (difflib > 0,85)
    # a 9 preguntas de prueba. El generador tiene pocas frases, así que dos plantillas de ramos
    # distintos se parecen. Se generan candidatas de más y se descarta toda plantilla casi igual
    # a una pregunta de prueba (la comparación no imprime texto de la prueba).
    import difflib
    prueba_q = [c["pregunta_prosa"].lower() for f in ("prueba_d4/plantilla.jsonl", "prueba_d4/redactados.jsonl")
                for c in leer_jsonl(DATOS / f)]

    def casi_igual(q):
        sm = difflib.SequenceMatcher(None, q.lower(), autojunk=False)
        for t in prueba_q:
            sm.set_seq2(t)
            if sm.real_quick_ratio() > 0.85 and sm.quick_ratio() > 0.85 and sm.ratio() > 0.85:
                return True
        return False
    puestas, quitadas = 0, 0
    for p in generar_pares(N_PLANTILLA * 2, SEMILLA_PLANTILLA):
        if puestas == N_PLANTILLA:
            break
        if casi_igual(p["meta"]["pregunta"]):
            quitadas += 1
            continue
        p["meta"]["bloque"] = "plantilla"
        pares.append(p)
        puestas += 1
    print(f"plantillas: {puestas} puestas, {quitadas} descartadas por parecerse a la prueba")

    sin_ramo = json.loads(sin_ramo_ruta.read_text(encoding="utf-8"))
    for i, m in enumerate(sin_ramo[:N_SIN_RAMO]):
        par(m.strip(), "", {"accion": "sin_ramo"}, {"bloque": "sin_ramo", "id_ent": f"s{i}"})

    # Validación: 10 % al azar dentro de cada bloque, con semilla fija.
    rnd = random.Random(SEMILLA_VALIDACION)
    ent, val = [], []
    for b in ("prosa", "revision", "plantilla", "sin_ramo"):
        grupo = [p for p in pares if p["meta"]["bloque"] == b]
        rnd.shuffle(grupo)
        k = round(len(grupo) * VALIDACION)
        val += grupo[:k]
        ent += grupo[k:]
    rnd.shuffle(ent)
    escribir_jsonl(SALIDA / "entrenamiento.jsonl", ent)
    escribir_jsonl(SALIDA / "validacion.jsonl", val)
    cuenta = {}
    for p in pares:
        cuenta[p["meta"]["bloque"]] = cuenta.get(p["meta"]["bloque"], 0) + 1
    print(f"{len(pares)} pares {cuenta} -> entrenamiento {len(ent)}, validación {len(val)}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    acciones = {"elegir": elegir, "verificar": lambda: (verificar(), 0)[1], "unir": unir}
    a = sys.argv[1] if len(sys.argv) > 1 else ""
    if a in acciones:
        raise SystemExit(acciones[a]())
    print(__doc__)
    raise SystemExit(2)
