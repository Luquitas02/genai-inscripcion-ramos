# -*- coding: utf-8 -*-
"""
La ficha del caso — Deliverable 2.

El baseline le entrega al modelo 3.900 tokens: la malla completa de 61 asignaturas,
las reglas, el historial de 26 asignaturas y la pregunta. Con eso tiene que identificar
el ramo, recorrer el grafo, cruzar cada prerrequisito contra el historial, distinguir
aprobada de inscrita, sumar créditos y aplicar un orden de prioridad entre ocho reglas.
Todo en una pasada. No lo logra.

La ficha es el contexto enfocado que reemplaza esos 3.900 tokens en el paso 3 del
pipeline. Son ocho campos sobre un solo ramo. El historial trae 26 asignaturas en
promedio y el ramo objetivo tiene 1,2 prerrequisitos directos, así que la ficha descarta
unas 25 asignaturas irrelevantes por caso, incluidos los distractores que el generador
puso a propósito.

Este módulo sirve para dos cosas a la vez:

  - es el ground truth contra el que se mide el paso 2 en la variante `puro`, donde la
    ficha la arma el modelo;
  - es el paso 2 mismo en la variante `retrieval`, donde la arma el código.

`decidir_desde_ficha` no es parte del sistema que se entrega. Existe para probar que la
ficha contiene todo lo necesario para decidir, y para dar el techo de acierto que el
paso 3 podría alcanzar si recibiera una ficha perfecta.
"""

import json
from pathlib import Path

from verificador import (Verificador, RUTA_MALLA,
                         APROBADA, INSCRITA, REPROBADA, NO_CURSADA,
                         CUMPLE, CONDICIONAL, NO_CUMPLE)

RUTA_CASOS = Path(__file__).resolve().parent.parent / "datos" / "casos.jsonl"

# Los cinco campos de la ficha que son juicio del modelo en la variante `puro`.
# Los otros tres (`ramo`, `creditos_ramo`, `creditos_semestre`) son datos de entrada o
# aritmética sobre ellos, no juicios, y por eso se puntúan aparte.
CAMPOS_JUICIO = ("estado_actual", "prerrequisitos", "creditos_aprobados",
                 "umbral_creditos", "requisitos_especiales")
CAMPOS_ENTRADA = ("ramo", "creditos_ramo", "creditos_semestre")


# --------------------------------------------------------------- construcción

def construir_ficha(v, historial, ramo, periodo, creditos_ya_inscritos):
    """Los ocho campos que el paso 3 necesita para resolver las seis ramas del verificador.

    `creditos_aprobados` se cuenta distinto según el período. Para el semestre actual cuenta
    lo aprobado. Para el próximo cuenta lo aprobado más lo que está cursando ahora. Esa
    distinción es el mecanismo E1 en forma aritmética, y es la parte que más probablemente
    falle cuando esta ficha la arma el modelo en vez del código.
    """
    a = v.asig[ramo]
    cred = (v.creditos_aprobados(historial) if periodo == "actual"
            else v.creditos_si_aprueba_lo_inscrito(historial))
    prerreq = [{"codigo": p, "nombre": v.asig[p]["nombre"], "estado": v.estado(historial, p)}
               for p in a["prerrequisitos"]]
    especiales = []
    for req in a["requisitos_especiales"]:
        r, falta = v._conjunto_semestres_ok(historial, v.especiales[req]["semestres"], periodo)
        especiales.append({"nombre": req, "resultado": r, "falta": falta})
    es_practica = ramo in v.practicas
    return {
        "ramo": ramo,
        "nombre": a["nombre"],
        "estado_actual": v.estado(historial, ramo),
        "creditos_ramo": a["creditos"],
        "es_practica": es_practica,
        # El total del semestre si inscribiera este ramo. Dos ramas del verificador comparan
        # contra él: el tope máximo y el régimen de excepción por carga baja. Se calcula acá,
        # a partir de dos datos de entrada, porque no es un juicio sobre el expediente y
        # dejárselo al modelo lo obliga a una aritmética que no acierta.
        "creditos_semestre": (0 if es_practica else a["creditos"]) + creditos_ya_inscritos,
        "prerrequisitos": prerreq,
        "creditos_aprobados": cred,
        "umbral_creditos": a["creditos_minimos"] or None,
        "requisitos_especiales": especiales,
        "creditos_ya_inscritos": creditos_ya_inscritos,
        "periodo": periodo,
    }


def render_ficha(f):
    """El bloque de texto que ve el paso 3, y que el modelo debe producir en la variante `puro`."""
    lineas = [
        f"ramo objetivo:         {f['ramo']}  {f['nombre']}",
        f"estado actual:         {f['estado_actual']}",
        f"créditos del ramo:     {f['creditos_ramo']}",
    ]
    if f["prerrequisitos"]:
        for i, p in enumerate(f["prerrequisitos"]):
            etq = "prerrequisitos:       " if i == 0 else "                      "
            lineas.append(f"{etq} {p['codigo']}  {p['nombre']}  {p['estado']}")
    else:
        lineas.append("prerrequisitos:        ninguno")
    lineas.append(f"créditos aprobados:    {f['creditos_aprobados']}  "
                  f"(contados para el período {f['periodo']})")
    lineas.append(f"umbral del ramo:       {f['umbral_creditos'] or 'ninguno'}")
    if f["requisitos_especiales"]:
        for r in f["requisitos_especiales"]:
            lineas.append(f"requisito especial:    {r['nombre']}  {r['resultado']}"
                          + (f"  falta {r['falta']}" if r["falta"] else ""))
    else:
        lineas.append("requisitos especiales: ninguno")
    lineas.append(f"créditos ya inscritos: {f['creditos_ya_inscritos']}")
    lineas.append(f"créditos del semestre: {f['creditos_semestre']}  "
                  f"({f['creditos_ya_inscritos']} ya inscritos + "
                  f"{0 if f['es_practica'] else f['creditos_ramo']} de este ramo)")
    return "\n".join(lineas)


# --------------------------------------------------------------- decisión de referencia

def decidir_desde_ficha(v, f):
    """Replica las seis ramas del verificador leyendo solo la ficha, en el mismo orden.

    No es parte del sistema que se entrega. Prueba que la ficha es suficiente, y marca el
    techo de acierto que el paso 3 podría alcanzar con una ficha perfecta.
    """
    # 1. el ramo ya está aprobado o inscrito
    if f["estado_actual"] in (APROBADA, INSCRITA):
        return {"decision": "no", "regla": "R-YA-CURSADA"}

    # 2. tope máximo de créditos del semestre
    total = f["creditos_semestre"]
    if total > v.tope_max:
        return {"decision": "no", "regla": "R-TOPE-MAX"}
    bajo_minimo = total < v.tope_min

    # 3. prerrequisitos
    hay_condicional = False
    for p in f["prerrequisitos"]:
        if p["estado"] == APROBADA:
            continue
        if p["estado"] == INSCRITA and f["periodo"] == "proximo":
            hay_condicional = True
            continue
        if bajo_minimo:
            return {"decision": "condicional", "regla": "R-EXCEPCION-PRERREQ"}
        return {"decision": "no", "regla": p["codigo"]}

    # 4. umbral de créditos aprobados que exige el ramo
    if f["umbral_creditos"] and f["creditos_aprobados"] < f["umbral_creditos"]:
        return {"decision": "no", "regla": "R-CREDITOS-MINIMOS"}

    # 5. requisitos de año o semestre completo
    for r in f["requisitos_especiales"]:
        if r["resultado"] == NO_CUMPLE:
            return {"decision": "no", "regla": "R-ESPECIAL-" + r["nombre"]}
        if r["resultado"] == CONDICIONAL:
            hay_condicional = True

    # 6. tope mínimo: bajo el mínimo procede excepción por reglamento
    if total < v.tope_min:
        return {"decision": "condicional", "regla": "R-EXCEPCION-PRERREQ"}

    if hay_condicional:
        return {"decision": "condicional", "regla": "R-DEPENDE-APROBACION"}
    return {"decision": "sí", "regla": "R-SIN-IMPEDIMENTO"}


# --------------------------------------------------------------- comparación

def comparar_fichas(esperada, obtenida):
    """Compara campo por campo. Devuelve un booleano por campo.

    Se compara campo por campo y no la ficha entera porque interesa distinguir el caso en
    que falló toda la lectura del expediente del caso en que los prerrequisitos salieron
    bien y falló solo la suma de créditos.
    """
    campos = CAMPOS_ENTRADA + CAMPOS_JUICIO
    if obtenida is None:
        return {k: False for k in campos}

    def norm_pre(lista):
        return sorted((p.get("codigo"), p.get("estado")) for p in (lista or []))

    def norm_esp(lista):
        return sorted((r.get("nombre"), r.get("resultado")) for r in (lista or []))

    return {
        "ramo": esperada["ramo"] == obtenida.get("ramo"),
        "creditos_ramo": esperada["creditos_ramo"] == obtenida.get("creditos_ramo"),
        "creditos_semestre": esperada["creditos_semestre"] == obtenida.get("creditos_semestre"),
        "estado_actual": esperada["estado_actual"] == obtenida.get("estado_actual"),
        "prerrequisitos": norm_pre(esperada["prerrequisitos"]) == norm_pre(obtenida.get("prerrequisitos")),
        "creditos_aprobados": esperada["creditos_aprobados"] == obtenida.get("creditos_aprobados"),
        "umbral_creditos": esperada["umbral_creditos"] == obtenida.get("umbral_creditos"),
        "requisitos_especiales": norm_esp(esperada["requisitos_especiales"]) == norm_esp(obtenida.get("requisitos_especiales")),
    }


# --------------------------------------------------------------- prueba

def _prueba_suficiencia():
    """La ficha debe bastar para reproducir al verificador en los 60 casos.

    Si falla, la ficha está incompleta: le falta un campo que alguna rama necesita.
    Esta es la prueba que detecta un contrato mal diseñado antes de gastar GPU.
    """
    v = Verificador()
    casos = [json.loads(l) for l in open(RUTA_CASOS, encoding="utf-8") if l.strip()]
    fallas = []
    for i, caso in enumerate(casos):
        esperado = v.evaluar(caso["historial"], caso["consulta"])
        ficha = construir_ficha(v, caso["historial"],
                                caso["consulta"]["ramos"][0],
                                caso["consulta"]["periodo"],
                                caso["consulta"]["creditos_ya_inscritos"])
        obtenido = decidir_desde_ficha(v, ficha)
        if (obtenido["decision"] != esperado["decision"]
                or obtenido["regla"] != esperado["regla"]):
            fallas.append((i, caso, esperado, obtenido))
    return len(casos) - len(fallas), len(casos), fallas


def _prueba_render_y_comparacion():
    """`render_ficha` y `comparar_fichas` no las ejerce la prueba de suficiencia.

    Devuelve (aciertos, total, mensajes de falla).
    """
    v = Verificador()
    casos = [json.loads(l) for l in open(RUTA_CASOS, encoding="utf-8") if l.strip()]
    caso = casos[0]
    f = construir_ficha(v, caso["historial"], caso["consulta"]["ramos"][0],
                        caso["consulta"]["periodo"],
                        caso["consulta"]["creditos_ya_inscritos"])
    fallas = []
    checks = 0

    # render: todas las etiquetas que el paso 3 espera leer
    texto = render_ficha(f)
    for etiqueta in ("ramo objetivo:", "estado actual:", "créditos del ramo:",
                     "prerrequisitos:", "créditos aprobados:", "umbral del ramo:",
                     "requisitos especiales:", "créditos ya inscritos:"):
        checks += 1
        if etiqueta not in texto:
            fallas.append(f"render_ficha no emite la etiqueta {etiqueta!r}")

    # comparar: una ficha contra sí misma da todo verdadero
    checks += 1
    if not all(comparar_fichas(f, f).values()):
        fallas.append("comparar_fichas marca diferencias entre una ficha y sí misma")

    # comparar: una diferencia en un campo se detecta en ese campo y no en los otros
    checks += 1
    torcida = json.loads(json.dumps(f))
    torcida["creditos_aprobados"] = f["creditos_aprobados"] + 1
    r = comparar_fichas(f, torcida)
    if r["creditos_aprobados"] or not all(v_ for k, v_ in r.items() if k != "creditos_aprobados"):
        fallas.append("comparar_fichas no aísla la diferencia en creditos_aprobados")

    # comparar: una ficha ausente da todo falso, sin reventar
    checks += 1
    if any(comparar_fichas(f, None).values()):
        fallas.append("comparar_fichas con None debería dar todo falso")

    return checks - len(fallas), checks, fallas


def main():
    ok2, total2, fallas2 = _prueba_render_y_comparacion()
    for m in fallas2:
        print(f"[FALLA] {m}")
    print(f"{ok2}/{total2} chequeos de render y comparación correctos")
    print()

    ok, total, fallas = _prueba_suficiencia()
    for i, caso, esperado, obtenido in fallas:
        print(f"[FALLA] caso {i} · {caso['constructor']} · nivel {caso['nivel']}")
        print(f"        ramo {caso['consulta']['ramos'][0]} · período {caso['consulta']['periodo']}")
        print(f"        esperado: {esperado['decision']:12} regla {esperado['regla']}")
        print(f"        obtenido: {obtenido['decision']:12} regla {obtenido['regla']}")
        print(f"        {esperado['detalle']}")
        print()
    print(f"{ok}/{total} casos reproducen al verificador desde la ficha")
    return 0 if (ok == total and ok2 == total2) else 1


if __name__ == "__main__":
    raise SystemExit(main())
