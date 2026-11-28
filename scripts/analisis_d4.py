# -*- coding: utf-8 -*-
"""
Análisis de la prueba sellada del D4, fijado en PROTOCOLO_D4.md antes de correrla.

    python scripts/analisis_d4.py [carpeta del zip de prueba_d4_colab]   la prueba sellada
    python scripts/analisis_d4.py --piloto                                  validación del script

La carpeta es la de `prueba_d4.zip` descomprimido (tiene `agentes/` y `resultados/`). La regla
fija se lee de `resultados/` del repositorio. Con `--piloto` el mismo análisis corre sobre el
piloto del 13 nov, donde los números ya se conocen (D3 52/60, ajustado 48/60, gana 2 y pierde 6):
si no los reproduce, el script está mal.

Lo que calcula:
  - acierto conjunto (decisión y regla) de cada fila, en total y por bloque;
  - McNemar exacto bilateral D4 contra D3 (principal, α = 0,05) y D4 contra el control;
  - acierto estricto (ramo y período) y acierto del período del Intérprete en las filas de agentes;
  - lo que no debe romperse: casos con alguna respuesta ilegible, casos que el D3 acierta y el D4
    falla, uso de sin_ramo y de la revisión (rechazos del Verificador);
  - el caso de falla: el primer redactado, en orden de id_d4, que el D4 falla.
Escribe `resultados/analisis_d4.json` con todo.
"""

import argparse
import collections
import json
import sys
from math import comb
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FILAS_AGENTES = ("D3", "D4", "control")


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def mcnemar(b, c):
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def uno(carpeta, patron):
    hallados = sorted(Path(carpeta).glob(patron))
    assert len(hallados) == 1, f"se esperaba un archivo {patron} en {carpeta}, hay {len(hallados)}"
    return hallados[0]


def rutas_prueba(carpeta):
    """fila -> conjunto -> archivo raw.jsonl."""
    ag, res, local = Path(carpeta) / "agentes", Path(carpeta) / "resultados", RAIZ / "resultados"
    r = {}
    for conj in ("d4_plantilla", "d4_redactados"):
        r.setdefault("Baseline D1", {})[conj] = uno(res, f"Phi-3.5-mini-instruct__few_shot__prosa__{conj}.raw.jsonl")
        r.setdefault("D2", {})[conj] = uno(res, f"pipeline__Phi-3.5-mini-instruct__codigo__encadenado__{conj}.raw.jsonl")
        r.setdefault("D3", {})[conj] = uno(ag, f"agentes__Phi-3.5-mini-instruct__completo__{conj}.raw.jsonl")
        r.setdefault("D4", {})[conj] = uno(ag, f"agentes__Phi-3.5-mini-instruct+A-lora-*__completo__{conj}.raw.jsonl")
        r.setdefault("control", {})[conj] = uno(ag, f"agentes__Phi-3.5-mini-instruct__control_d4__{conj}.raw.jsonl")
        r.setdefault("Regla fija", {})[conj] = uno(local, f"agentes__regla_fija__completo__{conj}.raw.jsonl")
    casos = {"d4_plantilla": jl(RAIZ / "datos" / "prueba_d4" / "plantilla.jsonl"),
             "d4_redactados": jl(RAIZ / "datos" / "prueba_d4" / "redactados.jsonl")}
    return r, casos


def rutas_piloto():
    c = RAIZ / "resultados" / "piloto_d4" / "corridas"
    r = {"D3": {"piloto": c / "agentes__Phi-3.5-mini-instruct__completo__piloto.raw.jsonl"},
         "D4": {"piloto": c / "agentes__Phi-3.5-mini-instruct+A-lora-piloto__completo__piloto.raw.jsonl"},
         "control": {"piloto": c / "agentes__Phi-3.5-mini-instruct__control_muchos_ejemplos__piloto.raw.jsonl"}}
    return r, {"piloto": jl(RAIZ / "datos" / "piloto_d4" / "piloto.jsonl")}


def bloque(conj, caso):
    if conj == "d4_plantilla":
        return "plantilla"
    if caso["constructor"] in ("_c_inscrita_actual", "_c_inscrita_proximo"):
        return caso["constructor"][3:]
    return "otros redactados"


def interprete(traza):
    """caso -> lista de salidas del Intérprete, en orden."""
    t = collections.defaultdict(list)
    for m in traza:
        if m["de"] == "interprete":
            t[str(m["caso"])].append(m["contenido"])
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("carpeta", nargs="?", default=str(RAIZ / "resultados" / "prueba_d4"))
    ap.add_argument("--piloto", action="store_true")
    a = ap.parse_args()
    rutas, casos = rutas_piloto() if a.piloto else rutas_prueba(a.carpeta)

    # clave de cada caso: (conjunto, id); el id es la posición en su archivo, como en los runners
    claves = [(conj, str(i)) for conj in casos for i in range(len(casos[conj]))]
    caso = {(conj, str(i)): c for conj in casos for i, c in enumerate(casos[conj])}
    blq = {k: bloque(k[0], caso[k]) if not a.piloto else "piloto" for k in claves}
    filas, a_per, interp = {}, {}, {}
    for fila, por_conj in rutas.items():
        filas[fila] = {}
        for conj, ruta in por_conj.items():
            for x in jl(ruta):
                filas[fila][(conj, str(x["id"]))] = x
            if fila in FILAS_AGENTES:
                ti = interprete(jl(str(ruta).replace(".raw.jsonl", ".traza.jsonl")))
                for i, salidas in ti.items():
                    interp.setdefault(fila, {})[(conj, i)] = salidas
        faltan = [k for k in claves if k not in filas[fila]]
        assert not faltan, f"{fila}: faltan {len(faltan)} casos"
    for fila in FILAS_AGENTES:
        a_per[fila] = {k: ((interp[fila].get(k) or [{}])[0].get("periodo") or "actual")
                       == caso[k]["consulta"]["periodo"] for k in claves}

    n = len(claves)
    ac = {f: {k: bool(filas[f][k]["acierto_conjunto"]) for k in claves} for f in filas}
    salida = {"n": n, "filas": {}, "comparaciones": {}}
    bloques = sorted(set(blq.values()), key=lambda b: ["plantilla", "inscrita_actual",
                                                       "inscrita_proximo", "otros redactados",
                                                       "piloto"].index(b))
    print(f"{n} casos · acierto conjunto (decisión y regla)\n")
    print(f"{'':12}{'total':>7}" + "".join(f"{b[:16]:>18}" for b in bloques)
          + f"{'estricto':>10}{'A período':>11}")
    for f in filas:
        tot = sum(ac[f].values())
        porb = {b: (sum(ac[f][k] for k in claves if blq[k] == b), sum(1 for k in claves if blq[k] == b))
                for b in bloques}
        reg = {"conjunto": tot, "por_bloque": porb}
        linea = f"{f:12}{tot:>7}" + "".join(f"{f'{x}/{m}':>18}" for x, m in porb.values())
        if f in FILAS_AGENTES or f == "Regla fija":
            est = sum(1 for k in claves if filas[f][k]["acierto_ramo"] and filas[f][k]["acierto_periodo"])
            reg["estricto"] = est
            linea += f"{est:>10}"
        if f in FILAS_AGENTES:
            reg["periodo_interprete"] = sum(a_per[f].values())
            ram = filas[f]
            reg["casos_con_ilegibles"] = sum(1 for k in claves if ram[k]["ramas"]["ilegibles"])
            reg["sin_ramo"] = sum(1 for k in claves if ram[k]["ramas"]["sin_ramo"])
            reg["casos_con_rechazo"] = sum(1 for k in claves if ram[k]["ramas"]["rechazos_verificador"])
            reg["casos_con_revision_del_interprete"] = sum(1 for k in claves if len(interp[f].get(k, [])) > 1)
            linea += f"{reg['periodo_interprete']:>11}"
        salida["filas"][f] = reg
        print(linea)

    print()
    for x, y, principal in (("D4", "D3", True), ("D4", "control", False), ("control", "D3", False)):
        if x not in ac or y not in ac:
            continue
        b = sum(ac[x][k] and not ac[y][k] for k in claves)
        c = sum(ac[y][k] and not ac[x][k] for k in claves)
        p = mcnemar(b, c)
        salida["comparaciones"][f"{x} contra {y}"] = {"gana": b, "pierde": c, "p": p, "principal": principal}
        print(f"{x} contra {y}{' (PRINCIPAL)' if principal else ''}: gana {b}, pierde {c}, "
              f"McNemar exacto p = {p:.4g}{'  significativo' if p < 0.05 else ''}")
        for bl in bloques:
            kk = [k for k in claves if blq[k] == bl]
            bb = sum(ac[x][k] and not ac[y][k] for k in kk)
            cc = sum(ac[y][k] and not ac[x][k] for k in kk)
            print(f"    {bl:18} gana {bb:3}, pierde {cc:3}")

    print("\nlo que no debe romperse (casos):")
    for f in FILAS_AGENTES:
        r = salida["filas"][f]
        print(f"  {f:8} con ilegibles {r['casos_con_ilegibles']:3} · sin_ramo {r['sin_ramo']:3} · "
              f"con rechazo {r['casos_con_rechazo']:3} · Intérprete revisó {r['casos_con_revision_del_interprete']:3}")
    perdidos = [k for k in claves if ac["D3"][k] and not ac["D4"][k]]
    salida["d3_acierta_d4_falla"] = [list(k) for k in perdidos]
    print(f"\ncasos que el D3 acierta y el D4 falla ({len(perdidos)}):")
    for k in perdidos:
        detalle(k, caso[k], filas, interp)

    if not a.piloto:
        red = sorted((k for k in claves if k[0] == "d4_redactados" and not ac["D4"][k]),
                     key=lambda k: caso[k]["id_d4"])
        if red:
            k = red[0]
            salida["caso_de_falla"] = {"conjunto": k[0], "id": k[1], "id_d4": caso[k]["id_d4"]}
            print(f"\nCASO DE FALLA (primer redactado que el D4 falla, id_d4 {caso[k]['id_d4']}):")
            detalle(k, caso[k], filas, interp)
    destino = RAIZ / "resultados" / ("analisis_d4_piloto.json" if a.piloto else "analisis_d4.json")
    destino.write_text(json.dumps(salida, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nescrito {destino.relative_to(RAIZ)}")
    return salida


def detalle(k, c, filas, interp):
    print(f"  [{k[0]} {k[1]}] {c['consulta']['periodo']} · {c['ramo_objetivo']['nombre']} · "
          f"esperado {c['respuesta']['decision'] if 'respuesta' in c and isinstance(c['respuesta'], dict) and 'decision' in c['respuesta'] else ''}")
    print(f"      {c.get('pregunta_prosa')}")
    for f in FILAS_AGENTES:
        x = filas[f][k]
        s = (interp[f].get(k) or [{}])[0]
        print(f"      {f:8} {'OK' if x['acierto_conjunto'] else '--'} A: {s.get('consultado')!r} / "
              f"{s.get('frase_periodo')!r} / {s.get('periodo')}  -> {x['prediccion']['decision']} "
              f"{x['prediccion']['regla']}{'' if x['acierto_ramo'] else '  RAMO MAL'}"
              f"{'' if x['acierto_periodo'] else '  PERÍODO MAL'}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
