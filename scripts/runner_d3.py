# -*- coding: utf-8 -*-
"""
Runner del sistema de agentes — Deliverable 3.

Corre una configuración sobre un conjunto de casos y guarda dos archivos:

  resultados/agentes__<modelo>__<config>__<conjunto>.raw.jsonl   una fila por caso
  trazas/agentes__<modelo>__<config>__<conjunto>.jsonl            un mensaje por línea

Igual que los runners del D1 y el D2, guarda caso a caso y retoma donde iba, porque una Colab
gratuita se desconecta sin avisar. La traza de un caso se escribe junto con su fila, al
terminarlo, así que una caída a mitad de caso no deja mensajes sueltos.

Uso:
    python runner_d3.py --config completo
    python runner_d3.py --config sin_verificador --casos ../datos/casos_nuevos.jsonl
    python runner_d3.py --pruebas                        # sin GPU
    python runner_d3.py --modelo-falso --limite 3        # recorre el flujo sin GPU
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from verificador import Verificador
import agentes as A
import orquestador as O

BASE = Path(__file__).resolve().parent.parent
RESULTADOS = BASE / "resultados"
TRAZAS = BASE / "trazas"
CASOS_ORIGINALES = BASE / "datos" / "casos.jsonl"

MODELO_POR_DEFECTO = "microsoft/Phi-3.5-mini-instruct"


def json_completo(texto):
    """True si el texto ya trae un objeto JSON cerrado que empieza en su primera llave."""
    i = texto.find("{")
    if i < 0:
        return False
    try:
        obj, _ = A._DECODIFICADOR.raw_decode(texto, i)
    except ValueError:
        return False
    return isinstance(obj, dict)


def cargar_modelo(nombre=MODELO_POR_DEFECTO, max_new_tokens=256):
    """`ModeloHF` del D1 y el D2, con la generación cortada al cerrar el primer JSON.

    En la corrida de desarrollo Phi escribía el JSON y después hasta 200 tokens de
    explicación: 8,9 s por caso contra 1,6 del D2. Como la generación es greedy y el agente
    lee el primer JSON (`agentes._extraer_json`), cortar ahí no cambia la respuesta que se
    usa, solo deja de generar lo que se descartaba. El baseline y el D2 siguen con `ModeloHF`
    sin corte, como se midieron.
    """
    import torch
    from transformers import StoppingCriteria, StoppingCriteriaList
    from runner import ModeloHF

    class _HastaPrimerJSON(StoppingCriteria):
        def __init__(self, tok, n_in):
            self.tok, self.n_in = tok, n_in

        def __call__(self, input_ids, scores, **kwargs):
            texto = self.tok.decode(input_ids[0][self.n_in:], skip_special_tokens=True)
            listo = "}" in texto and json_completo(texto)
            return torch.full((input_ids.shape[0],), listo, dtype=torch.bool,
                              device=input_ids.device)

    class ModeloAgentes(ModeloHF):
        def generar(self, mensajes):
            texto = self.tok.apply_chat_template(
                mensajes, tokenize=False, add_generation_prompt=True)
            ent = self.tok(texto, return_tensors="pt").to(self.modelo.device)
            n_in = ent["input_ids"].shape[1]
            with torch.no_grad():
                out = self.modelo.generate(
                    **ent,
                    max_new_tokens=self.max_new_tokens,
                    do_sample=False,
                    pad_token_id=self.tok.eos_token_id,
                    stopping_criteria=StoppingCriteriaList([_HastaPrimerJSON(self.tok, n_in)]),
                )
            return self.tok.decode(out[0][n_in:], skip_special_tokens=True), n_in

    return ModeloAgentes(nombre, max_new_tokens=max_new_tokens)


class ModeloGuion:
    """Devuelve respuestas fijas en orden. Para probar cada rama del grafo sin GPU."""

    nombre = "guion"

    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def generar(self, mensajes):
        self.llamadas.append(mensajes)
        return self.respuestas[(len(self.llamadas) - 1) % len(self.respuestas)], 0


class ModeloFalso:
    """La regla fija sin modelo, que también sirve para recorrer el flujo sin GPU.

    El Intérprete devuelve el texto entre el verbo (inscribir, tomar, meter) y el signo de
    interrogación, con período actual; el Resolvedor elige el primer candidato de T1 y el
    Verificador acepta. Es la fila de referencia del protocolo: el piso que saca una regla
    escrita mirando las plantillas, sin ningún modelo de lenguaje.
    """

    nombre = "regla_fija"

    def generar(self, mensajes):
        sistema, usuario = mensajes[0]["content"], mensajes[1]["content"]
        if "intérprete" in sistema:
            consulta = usuario.split("===\n", 1)[1].split("\n")[0]
            m = re.search(r"(?:inscribir|tomar|meter)\s+(.*?)\s*\?", consulta)
            return json.dumps({"accion": "entregar", "consultado": m.group(1) if m else consulta,
                               "otros": [], "periodo": "actual"}, ensure_ascii=False), 0
        if "resolvedor" in sistema:
            m = re.search(r"^(\d+)\s", usuario.split("CANDIDATOS", 1)[-1].split("CATÁLOGO", 1)[-1],
                          flags=re.M)
            return json.dumps({"accion": "elegir", "codigo": m.group(1)}), 0
        return '{"accion": "aceptar"}', 0


# --------------------------------------------------------------- la corrida

def nombre_salida(etq, config, ruta_casos):
    conjunto = Path(ruta_casos).stem
    return f"agentes__{etq}__{config}__{conjunto}"


class PromptsCambiados(Exception):
    pass


def commit_actual():
    """El commit del repositorio con que se corre. Queda en cada fila."""
    try:
        r = subprocess.run(["git", "-C", str(BASE), "rev-parse", "--short=10", "HEAD"],
                           capture_output=True, text=True, check=True)
        return r.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "desconocido"


def correr(modelo, casos, v, config, salida, traza):
    """Retoma solo si los prompts y el código son los mismos de lo que ya está guardado.

    En el D2 una corrida retomó resultados viejos y no midió nada. Acá los prompts cambian
    mientras se ajustan en el conjunto de desarrollo, y el código también: en la primera
    corrida de desarrollo el lector de JSON tuvo que corregirse sin tocar ningún prompt.
    Retomar mezclaría dos versiones en un mismo archivo sin que nadie lo note.
    """
    prompts = O.cargar_prompts(config)
    actuales = {k: p.ref() for k, p in prompts.items()}
    commit = commit_actual()
    hechos = set()
    if salida.exists():
        with open(salida, encoding="utf-8") as f:
            filas = [json.loads(l) for l in f if l.strip()]
        distintas = [x["id"] for x in filas
                     if x["prompts"] != actuales or x.get("commit") != commit]
        if distintas:
            raise PromptsCambiados(
                f"{salida.name} tiene {len(distintas)} casos corridos con otros prompts u "
                f"otro commit. Bórralo (y su traza) antes de volver a correr.")
        hechos = {x["id"] for x in filas}
        if hechos:
            print(f"retomando: {len(hechos)} casos ya corridos con los mismos prompts")
    with open(salida, "a", encoding="utf-8") as fs, open(traza, "a", encoding="utf-8") as ft:
        for i, caso in enumerate(casos):
            if str(i) in hechos:
                continue
            caso = dict(caso, id=str(i))
            fila, mensajes = O.correr_caso(modelo, caso, v, config, prompts)
            fila["commit"] = commit
            for m in mensajes:
                ft.write(json.dumps({"caso": str(i), **m}, ensure_ascii=False) + "\n")
            fs.write(json.dumps(fila, ensure_ascii=False) + "\n")
            ft.flush()
            fs.flush()
            ramas = fila["ramas"]
            marca = "OK " if fila["acierto_conjunto"] else "   "
            print(f"[{marca}] {i + 1:3}/{len(casos)} n{caso['nivel']} "
                  f"{fila['segundos_total']:5.1f}s {fila['llamadas']:2} llamadas  "
                  f"ramo {'ok' if fila['acierto_ramo'] else '--'} "
                  f"per {'ok' if fila['acierto_periodo'] else '--'}  "
                  f"rech {ramas['rechazos_verificador']} busq {ramas['busquedas_extra']}  "
                  f"{fila['prediccion']['decision']} / {fila['prediccion']['regla']}")


def resumen(salida):
    filas = [json.loads(l) for l in open(salida, encoding="utf-8") if l.strip()]
    if not filas:
        print("sin resultados")
        return
    n = len(filas)
    cuenta = lambda f: sum(1 for x in filas if f(x))                   # noqa: E731
    print()
    print("=" * 74)
    print(f"{filas[0]['modelo']} · configuración {filas[0]['configuracion']} · {n} casos")
    print("=" * 74)
    print(f"ramo {cuenta(lambda x: x['acierto_ramo'])}/{n}   "
          f"período {cuenta(lambda x: x['acierto_periodo'])}/{n}   "
          f"T1 recall@5 {cuenta(lambda x: x['t1_recall5'])}/{cuenta(lambda x: x['t1_recall5'] is not None)}")
    print(f"CONJUNTO {cuenta(lambda x: x['acierto_conjunto'])}/{n}")
    print("ramas activadas (casos):")
    for clave in ("rechazos_verificador", "busquedas_extra", "ninguno_resolvedor",
                  "sin_ramo", "tope_rechazos", "tope_llamadas", "ilegibles", "codigo_fuera",
                  "citas_fuera"):
        print(f"  {clave:22} {cuenta(lambda x: x['ramas'][clave]):3}")
    print(f"llamadas por caso {sum(x['llamadas'] for x in filas) / n:.1f}   "
          f"tokens por caso {sum(x['tokens_total'] for x in filas) / n:,.0f}   "
          f"segundos por caso {sum(x['segundos_total'] for x in filas) / n:.1f}")


# --------------------------------------------------------------- pruebas

def _pruebas():
    v = Verificador()
    caso = dict(json.loads(open(CASOS_ORIGINALES, encoding="utf-8").readline()), id="0")
    # caso 0: "¿puedo inscribir Programación este semestre?" -> no / 525140

    A_OK = '{"accion": "entregar", "consultado": "Programación", "otros": [], "periodo": "actual"}'
    A_MAL = ('{"accion": "entregar", "consultado": "Álgebra I", "otros": [], '
             '"periodo": "actual"}')
    B_OK = '{"accion": "elegir", "codigo": "503203"}'
    B_MAL = '{"accion": "elegir", "codigo": "525140"}'
    B_BUSCA = '{"accion": "buscar", "consulta": "programacion"}'
    C_OK = '{"accion": "aceptar"}'
    C_NO = '{"accion": "rechazar", "problema": "ramo", "motivo": "Álgebra I es contexto."}'

    def corre(respuestas, config="completo"):
        m = ModeloGuion(respuestas)
        fila, traza = O.correr_caso(m, caso, v, config)
        return m, fila, traza

    chequeos = []

    def chequea(nombre, obtenido, esperado):
        chequeos.append((nombre, obtenido, esperado))

    m, f, t = corre([A_OK, B_OK, C_OK])
    chequea("camino directo: 3 llamadas", len(m.llamadas), 3)
    chequea("camino directo: acierta", f["acierto_conjunto"], True)
    chequea("camino directo: recorrido de la traza",
            [(x["de"], x["para"]) for x in t],
            [("estudiante", "interprete"), ("interprete", "T1"), ("T1", "resolvedor"),
             ("resolvedor", "verificador"), ("verificador", "T2"), ("T2", "fin")])
    chequea("cada llamada al modelo deja prompt y salida cruda en la traza",
            all(x.get("prompt", {}).get("hash") and x.get("crudo") for x in t
                if x["tipo"] == "agente"), True)
    chequea("T1 recall@5 registrado", f["t1_recall5"], True)

    m, f, t = corre([A_OK, B_BUSCA, B_OK, C_OK])
    chequea("búsqueda extra: 4 llamadas y T1 dos veces",
            (len(m.llamadas), sum(x["de"] == "T1" for x in t)), (4, 2))
    chequea("búsqueda extra: la segunda vez el Resolvedor sabe lo que buscó",
            "Búsquedas que ya hiciste" in m.llamadas[2][1]["content"], True)

    m, f, t = corre([A_MAL, B_MAL, C_NO, A_OK, B_OK, C_OK])
    chequea("rechazo y corrección: 6 llamadas, acierta",
            (len(m.llamadas), f["acierto_conjunto"], f["ramas"]["rechazos_verificador"]),
            (6, True, 1))
    chequea("rechazo: el Intérprete recibe la revisión",
            "REVISIÓN" in m.llamadas[3][1]["content"], True)

    m, f, t = corre([A_MAL, B_MAL, C_NO])
    chequea("tope de rechazos: 9 llamadas, usa la última elección",
            (len(m.llamadas), f["ramas"]["tope_rechazos"], f["extraccion"]["ramo"], f["aceptada"]),
            (9, True, "525140", False))

    m, f, t = corre(['{"accion": "sin_ramo"}'])
    chequea("sin_ramo: 1 llamada y sin decisión",
            (len(m.llamadas), f["prediccion"]["decision"], f["ramas"]["sin_ramo"]),
            (1, None, True))

    m, f, t = corre([A_OK, B_OK, "no sé qué responder"])
    chequea("Verificador ilegible: acepta y se cuenta",
            (f["aceptada"], f["ramas"]["ilegibles"], f["acierto_conjunto"]), (True, 1, True))

    m, f, t = corre([A_OK, '{"accion": "elegir", "codigo": "999999"}', A_OK, B_OK, C_OK])
    chequea("código fuera de los candidatos: cuenta como ninguno y vuelve al Intérprete",
            (len(m.llamadas), f["ramas"]["codigo_fuera"], f["ramas"]["ninguno_resolvedor"],
             f["acierto_conjunto"]), (5, 1, 1, True))

    m, f, t = corre([A_OK, B_BUSCA, B_BUSCA, B_OK, C_NO])
    chequea("tope de llamadas: se corta en 12",
            (len(m.llamadas), f["ramas"]["tope_llamadas"]), (12, True))

    m, f, t = corre(['{"accion": "entregar", "consultado": "Programación", "periodo": "?"}',
                     B_OK, C_OK])
    chequea("período ilegible: se usa actual y se marca",
            (f["extraccion"]["periodo"], t[1]["contenido"]["periodo_por_defecto"]),
            ("actual", True))

    m, f, t = corre([A_OK, B_OK], "sin_verificador")
    chequea("sin verificador: 2 llamadas", (len(m.llamadas), f["acierto_conjunto"]), (2, True))

    m, f, t = corre([A_OK, C_OK], "top1")
    chequea("top1: el Resolvedor no llama al modelo",
            (len(m.llamadas), f["extraccion"]["ramo"]), (2, "503203"))

    m, f, t = corre([A_OK, B_OK, C_OK], "sin_herramienta")
    chequea("sin herramienta: el Resolvedor ve las 61 asignaturas y no hay T1",
            ("CATÁLOGO" in m.llamadas[1][1]["content"],
             len(re.findall(r"^\d+  ", m.llamadas[1][1]["content"], re.M)),
             any(x["de"] == "T1" for x in t)), (True, 61, False))

    m, _, _ = corre([A_OK, B_OK, C_OK], "sin_ejemplos")
    m2, _, _ = corre([A_OK, B_OK, C_OK])
    chequea("sin ejemplos: el Intérprete pierde solo el bloque de ejemplos",
            ("Ejemplos:" in m.llamadas[0][0]["content"], "Ejemplos:" in m2.llamadas[0][0]["content"]),
            (False, True))

    m, _, _ = corre([A_OK, B_OK, C_OK], "sin_descomposicion")
    chequea("sin descomposición: el Intérprete no pide las otras asignaturas",
            '"otros"' in m.llamadas[0][0]["content"], False)

    # Salidas reales de Phi en la primera corrida de desarrollo (casos 0 y 13): el JSON,
    # una explicación y el JSON repetido o cambiado. Vale el primero.
    A_REAL = ('{"accion": "entregar", "consultado": "Programación", "otros": [], '
              '"periodo": "actual"}\n\nExplicación: el estudiante pregunta por "Programación".'
              '\n\nJSON:\n\n{"accion": "entregar", "consultado": "Programación", "otros": [], '
              '"periodo": "actual"}')
    C_REAL = ('{"accion": "aceptar", "problema": "error de contexto", "motivo": "..."}\n\n'
              '```json\n{\n  "accion": "rechazar",\n  "problema": "contexto",\n'
              '  "motivo": "otra cosa"\n}\n```')
    m, f, t = corre([A_REAL, B_OK, C_REAL])
    chequea("JSON repetido con explicación: se lee el primero",
            (f["ramas"]["ilegibles"], f["ramas"]["sin_ramo"], f["acierto_conjunto"],
             f["ramas"]["rechazos_verificador"]), (0, False, True, 0))
    chequea("JSON dentro de un bloque de código: se lee",
            A._extraer_json('Claro:\n```json\n{"accion": "aceptar"}\n```')[0],
            {"accion": "aceptar"})
    chequea("llaves sueltas antes del JSON: se saltan",
            A._extraer_json('uso {llaves} sueltas {"accion": "ninguno"}')[0],
            {"accion": "ninguno"})

    # Citas del Verificador: se mide si salen de la consulta o de la interpretación (v3).
    m, f, t = corre([A_OK, B_OK,
                     '{"cita_ramo": "Programación", "cita_periodo": "este semestre", '
                     '"accion": "aceptar"}'])
    chequea("cita tomada de la consulta: no se marca", f["ramas"]["citas_fuera"], 0)
    m, f, t = corre([A_OK, B_OK,
                     '{"cita_ramo": "503203 Programación", "cita_periodo": "actual (2026-2)", '
                     '"accion": "aceptar"}'])
    chequea("cita copiada de la interpretación: se marca y no cambia la acción",
            (f["ramas"]["citas_fuera"], f["aceptada"]), (1, True))

    # El corte de generación: se detiene solo cuando el primer JSON está cerrado.
    chequea("corte: JSON a medias no corta", json_completo('{"accion": "entre'), False)
    chequea("corte: JSON cerrado corta", json_completo('{"accion": "aceptar"} y más'), True)
    chequea("corte: lo que lee el agente es lo mismo con y sin corte",
            A._extraer_json(A_REAL)[0] == A._extraer_json(A_REAL[:A_REAL.index("}") + 1])[0],
            True)

    chequea("los prompts no dejan marcas sin reemplazar",
            any("{{" in msg["content"] for msg in sum(m2.llamadas, [])), False)

    # --- v6 (PLAN_V6.md) ---
    from herramientas import estado_en_historial
    chequea("estado: aprobada", estado_en_historial({"541271": "aprobada"}, "541271"), "aprobada")
    chequea("estado: sin entrada es no_cursada", estado_en_historial({}, "541340"), "no_cursada")

    def corre_con(respuestas, config, historial_extra=None, **cambios):
        c = dict(caso, historial=dict(caso["historial"], **(historial_extra or {})), **cambios)
        m = ModeloGuion(respuestas)
        fila, traza = O.correr_caso(m, c, v, config)
        return m, fila, traza

    m, f, t = corre([A_OK, C_OK], "v6")
    chequea("v6: coincidencia exacta sin cursar no llama al Resolvedor",
            (len(m.llamadas), f["ramas"]["atajo_exacto"], f["extraccion"]["ramo"],
             f["acierto_conjunto"]), (2, True, "503203", True))
    chequea("v6: el atajo queda en la traza",
            ("orquestador", "verificador") in [(x["de"], x["para"]) for x in t], True)

    m, f, t = corre_con([A_OK, B_OK, C_OK], "v6", {"503203": "aprobada"})
    chequea("v6: coincidencia exacta con el ramo aprobado pasa al Resolvedor",
            (len(m.llamadas), f["ramas"]["atajo_exacto"]), (3, False))
    chequea("v6: el Resolvedor ve la pregunta completa y el estado de cada candidato",
            ("PREGUNTA COMPLETA" in m.llamadas[1][1]["content"],
             caso["pregunta_prosa"] in m.llamadas[1][1]["content"],
             "aprobada" in m.llamadas[1][1]["content"]), (True, True, True))

    m, f, t = corre_con([A_OK, B_OK, C_OK], "v6_resolvedor_sin_historial", {"503203": "aprobada"})
    chequea("v6 sin historial: el Resolvedor no ve estados",
            "aprobada" in m.llamadas[1][1]["content"], False)
    m, f, t = corre_con([A_OK, B_OK, C_OK], "v6_resolvedor_sin_pregunta", {"503203": "aprobada"})
    chequea("v6 sin pregunta: el Resolvedor no ve la consulta",
            (caso["pregunta_prosa"] in m.llamadas[1][1]["content"],
             "(no disponible)" in m.llamadas[1][1]["content"]), (False, True))

    m, f, t = corre([A_OK, C_NO, B_OK, C_OK], "v6")
    pares = [(x["de"], x["para"]) for x in t]
    chequea("v6: un rechazo de ramo vuelve al Resolvedor, no al Intérprete",
            (("verificador", "resolvedor") in pares, ("verificador", "interprete") in pares,
             f["ramas"]["rechazos_verificador"], len(m.llamadas)), (True, False, 1, 4))
    chequea("v6: el Resolvedor recibe el rechazo",
            "RECHAZÓ" in m.llamadas[2][1]["content"], True)

    m, f, t = corre([A_OK, C_NO, B_OK, C_NO, B_OK, C_NO], "v6")
    chequea("v6: los rechazos al Resolvedor cuentan para el tope",
            (len(m.llamadas), f["ramas"]["tope_rechazos"]), (6, True))

    C_PER = '{"accion": "rechazar", "problema": "periodo", "motivo": "Dice el próximo."}'
    m, f, t = corre([A_OK, C_PER, A_OK, C_OK], "v6")
    chequea("v6: un rechazo de período vuelve al Intérprete",
            ("verificador", "interprete") in [(x["de"], x["para"]) for x in t], True)

    m, f, t = corre([A_OK, C_NO, A_OK, C_OK], "v6_enrutamiento_v4")
    chequea("v6 con enrutamiento v4: el rechazo de ramo vuelve al Intérprete",
            ("verificador", "interprete") in [(x["de"], x["para"]) for x in t], True)

    A_GEST = ('{"accion": "entregar", "consultado": "gestión", "otros": [], '
              '"periodo": "actual"}')
    m, f, t = corre_con([A_GEST, C_OK], "v6_regla_codigo",
                        {"580423": "aprobada", "580120": "aprobada"})
    chequea("regla en código: el primer candidato inscribible, sin llamar al modelo",
            (len(m.llamadas), f["extraccion"]["ramo"]), (2, "580415"))
    todos = {c: "aprobada" for c in ("580423", "580120", "580415", "580514", "580413")}
    m, f, t = corre_con([A_GEST, C_OK], "v6_regla_codigo", todos)
    chequea("regla en código: sin candidatos inscribibles, el primero de T1",
            f["extraccion"]["ramo"], "580423")

    m, f, t = corre([A_OK, B_OK], "v6_sin_herramienta")
    chequea("v6 sin herramienta: no hay atajo ni T1",
            (f["ramas"]["atajo_exacto"], any(x["de"] == "T1" for x in t)), (False, False))

    m_v6, _, _ = corre([A_OK, B_OK, C_OK], "v6")
    m_c, _, _ = corre([A_OK, B_OK, C_OK])
    chequea("completo después de v6: mismos mensajes que completo solo",
            m_c.llamadas, m2.llamadas)

    fallas = [(n, o, e) for n, o, e in chequeos if o != e]
    for n, o, e in fallas:
        print(f"[FALLA] {n}\n        esperado: {e!r}\n        obtenido: {o!r}")
    print(f"{len(chequeos) - len(fallas)}/{len(chequeos)} chequeos del orquestador correctos")
    return 0 if not fallas else 1


# --------------------------------------------------------------- línea de comandos

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="completo", choices=list(O.CONFIGURACIONES))
    ap.add_argument("--modelo", default=MODELO_POR_DEFECTO)
    ap.add_argument("--casos", default=str(CASOS_ORIGINALES))
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--modelo-falso", action="store_true")
    ap.add_argument("--pruebas", action="store_true")
    ap.add_argument("--dir-salida", default=None,
                    help="carpeta para resultados y trazas, en vez de resultados/ y trazas/. "
                         "Sirve para reproducir una corrida sin tocar la guardada")
    args = ap.parse_args()

    if args.pruebas:
        return _pruebas()

    if args.modelo_falso:
        modelo = ModeloFalso()
    else:
        # 256 tokens de salida, como el D2. Los JSON de los agentes miden menos de 80.
        modelo = cargar_modelo(args.modelo)
    ejecutar(modelo, args.config, args.casos, args.limite, args.dir_salida)
    return 0


def ejecutar(modelo, config, ruta_casos, limite=None, dir_salida=None):
    """Una configuración sobre un conjunto. El notebook la llama con el modelo ya cargado,
    para no recargar Phi en cada configuración. Devuelve las rutas de salida y traza."""
    v = Verificador()
    casos = [json.loads(l) for l in open(ruta_casos, encoding="utf-8") if l.strip()]
    if limite:
        casos = casos[:limite]
    etq = getattr(modelo, "nombre", "falso").split("/")[-1]
    # Con --dir-salida, resultados y traza van a la misma carpeta y no tocan los guardados.
    res = Path(dir_salida) if dir_salida else RESULTADOS
    tra = res if dir_salida else TRAZAS
    res.mkdir(parents=True, exist_ok=True)
    tra.mkdir(parents=True, exist_ok=True)
    nombre = nombre_salida(etq, config, ruta_casos)
    salida = res / f"{nombre}.raw.jsonl"
    traza = tra / (f"{nombre}.traza.jsonl" if dir_salida else f"{nombre}.jsonl")
    print(f"{len(casos)} casos · {etq} · configuración {config}")
    print(f"salida: {salida.name}\ntraza:  {traza.name}\n")
    correr(modelo, casos, v, config, salida, traza)
    resumen(salida)
    return salida, traza


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
