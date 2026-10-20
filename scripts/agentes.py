# -*- coding: utf-8 -*-
"""
Los tres agentes del sistema — Deliverable 3.

Cada agente es una llamada al mismo modelo con su rol, su prompt y una entrada y salida
definidas. Los prompts viven en `prompts/` y no en este archivo, como pide el enunciado. Cada
archivo tiene una sección `# sistema` y una `# usuario`, y las marcas {{...}} se reemplazan acá.
El hash del archivo queda en cada mensaje de la traza, así que una traza dice exactamente con
qué versión del prompt se produjo.

Cada agente devuelve su decisión en el campo `accion` de un JSON:

  Intérprete    entregar | sin_ramo
  Resolvedor    elegir | buscar | ninguno
  Verificador   aceptar | rechazar

Este módulo no ejecuta las acciones: arma el prompt, llama al modelo y lee la acción. Quien
la ejecuta es `orquestador.py`. Una salida ilegible recibe una acción por defecto declarada, y
queda marcada con `legible: False` para contarla aparte:

  Intérprete    sin_ramo    no se puede seguir sin una mención
  Resolvedor    ninguno     el trabajo vuelve al Intérprete como rechazo
  Verificador   aceptar     rechazar por ruido crearía bucles que no corrigen nada

Lo que se tolera es la forma, no el contenido: texto alrededor del JSON, mayúsculas, la tilde
de "próximo". Si el modelo escribe más de un JSON, vale el primero. Un código que no está entre
los candidatos no se corrige: cuenta como `ninguno`.
"""

import hashlib
import json
import re
import time
from pathlib import Path

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"

_MARCA_EJEMPLOS = re.compile(r"<!-- ejemplos -->.*?<!-- /ejemplos -->\n?", re.S)
_COMENTARIO = re.compile(r"<!--.*?-->\n?", re.S)

PERIODO_TXT = {"actual": "actual (2026-2, el semestre en curso)",
               "proximo": "proximo (2027-1, el semestre siguiente)"}


class Prompt:
    """Un archivo de `prompts/`, partido en sistema y usuario."""

    def __init__(self, relativo, con_ejemplos=True):
        ruta = PROMPTS / relativo
        # Saltos de línea normalizados: git deja CRLF en Windows y LF en Colab, y el hash
        # tiene que ser el mismo en las dos máquinas para que la traza identifique el prompt.
        crudo = ruta.read_text(encoding="utf-8").replace("\r\n", "\n")
        self.archivo = relativo
        self.hash = hashlib.sha256(crudo.encode("utf-8")).hexdigest()[:10]
        self.con_ejemplos = con_ejemplos
        texto = crudo if con_ejemplos else _MARCA_EJEMPLOS.sub("", crudo)
        texto = _COMENTARIO.sub("", texto)
        partes = re.split(r"^# (sistema|usuario)\s*$", texto, flags=re.M)
        secciones = dict(zip(partes[1::2], (p.strip() for p in partes[2::2])))
        if set(secciones) != {"sistema", "usuario"}:
            raise ValueError(f"{relativo}: necesita una sección '# sistema' y una '# usuario'")
        self.sistema, self.usuario = secciones["sistema"], secciones["usuario"]

    def mensajes(self, **valores):
        usuario = self.usuario
        for clave, valor in valores.items():
            usuario = usuario.replace("{{" + clave + "}}", valor)
        sobrantes = re.findall(r"\{\{(\w+)\}\}", usuario)
        if sobrantes:
            raise ValueError(f"{self.archivo}: faltan valores para {sobrantes}")
        # Las líneas vacías que deja una marca sin contenido no le dicen nada al modelo.
        usuario = re.sub(r"\n{3,}", "\n\n", usuario)
        return [{"role": "system", "content": self.sistema},
                {"role": "user", "content": usuario}]

    def ref(self):
        return {"archivo": self.archivo, "hash": self.hash, "ejemplos": self.con_ejemplos}


_DECODIFICADOR = json.JSONDecoder()


def _extraer_json(texto):
    """El PRIMER objeto JSON válido del texto. Devuelve (dict, estado).

    El lector del D2 tomaba desde la primera llave hasta la última. En el D3 Phi escribe el
    JSON, después una explicación y muchas veces repite el JSON al final, así que ese tramo
    no se puede leer: en la primera corrida de desarrollo dejó 15 de 52 respuestas ilegibles
    que traían el JSON correcto. Se toma el primero porque es la respuesta que el modelo dio
    antes de explicarse. Si el segundo dice otra cosa, cuenta el primero.
    """
    if not texto:
        return None, "vacio"
    for m in re.finditer(r"\{", texto):
        try:
            obj, _ = _DECODIFICADOR.raw_decode(texto, m.start())
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj, "ok"
    return None, "sin_json"


def llamar(modelo, mensajes):
    t0 = time.perf_counter()
    texto, tokens = modelo.generar(mensajes)
    return texto, tokens, time.perf_counter() - t0


def cita_en(cita, texto):
    """True si la cita aparece en el texto, sin distinguir tildes, mayúsculas ni romanos."""
    from herramientas import normalizar
    c = normalizar(cita)
    return bool(c) and c in normalizar(texto)


def _lista(nombres):
    return "\n".join(f"- {n}" for n in nombres) if nombres else "(ninguna)"


def _texto(x):
    return x.strip() if isinstance(x, str) else ""


# --------------------------------------------------------------- A. Intérprete

def norm_periodo(p):
    t = _texto(p).lower().replace("ó", "o")
    return t if t in ("actual", "proximo") else None


def interprete(modelo, prompt, pregunta, revision=None):
    """Devuelve (accion, llamada). `revision` es el rechazo anterior, si lo hubo."""
    bloque = ""
    if revision:
        bloque = ("\n=== REVISIÓN DE TU RESPUESTA ANTERIOR ===\n"
                  f"Tu respuesta: asignatura \"{revision['consultado']}\", "
                  f"período {revision['periodo']}.\n"
                  f"Problema: {revision['problema']}. {revision['motivo']}\n")
    mensajes = prompt.mensajes(pregunta=pregunta, revision=bloque)
    crudo, tokens, segundos = llamar(modelo, mensajes)
    d, _ = _extraer_json(crudo)

    accion = {"accion": "sin_ramo", "legible": d is not None}
    if d is not None:
        consultado = _texto(d.get("consultado"))
        if _texto(d.get("accion")).lower() != "sin_ramo" and consultado:
            otros = [_texto(o) for o in (d.get("otros") or []) if _texto(o)]
            accion = {"accion": "entregar", "consultado": consultado, "otros": otros,
                      "frase_periodo": _texto(d.get("frase_periodo")),
                      "periodo": norm_periodo(d.get("periodo")), "legible": True}
    return accion, {"mensajes": mensajes, "crudo": crudo, "tokens": tokens,
                    "segundos": segundos, "prompt": prompt.ref()}


# --------------------------------------------------------------- B. Resolvedor

def _render_candidatos(candidatos):
    return "\n".join(f"{c['codigo']}  {c['nombre']}  ({c['similitud']:.2f})" for c in candidatos)


def resolvedor(modelo, prompt, consultado, otros, candidatos, busquedas_hechas, busquedas_max,
               catalogo=None):
    """Devuelve (accion, llamada).

    Con `catalogo` es la ablación sin herramienta: recibe las 61 asignaturas en vez de los
    candidatos y no puede buscar. El código elegido se valida contra lo que vio.
    """
    if catalogo is not None:
        mensajes = prompt.mensajes(
            consultado=consultado, otros=_lista(otros),
            catalogo="\n".join(f"{c}  {n}" for c, n in catalogo))
        validos = {c for c, _ in catalogo}
    else:
        quedan = busquedas_max - len(busquedas_hechas)
        bloque = ""
        if busquedas_hechas:
            bloque = ("\nBúsquedas que ya hiciste: "
                      + ", ".join(f"\"{b}\"" for b in busquedas_hechas) + ".\n")
        bloque += (f"Te quedan {quedan} búsquedas." if quedan > 0
                   else "No te quedan búsquedas: elige o responde ninguno.")
        mensajes = prompt.mensajes(consultado=consultado, otros=_lista(otros),
                                   candidatos=_render_candidatos(candidatos),
                                   busquedas="\n" + bloque + "\n")
        validos = {c["codigo"] for c in candidatos}
    crudo, tokens, segundos = llamar(modelo, mensajes)
    d, _ = _extraer_json(crudo)

    accion = {"accion": "ninguno", "legible": d is not None}
    if d is not None:
        tipo = _texto(d.get("accion")).lower()
        codigo = _texto(str(d.get("codigo", "")))
        consulta = _texto(d.get("consulta"))
        if tipo == "elegir" or (not tipo and codigo):
            if codigo in validos:
                accion = {"accion": "elegir", "codigo": codigo, "legible": True}
            else:
                accion = {"accion": "ninguno", "legible": True, "codigo_fuera": codigo}
        elif tipo == "buscar" and consulta and catalogo is None:
            accion = {"accion": "buscar", "consulta": consulta, "legible": True}
    return accion, {"mensajes": mensajes, "crudo": crudo, "tokens": tokens,
                    "segundos": segundos, "prompt": prompt.ref()}


# --------------------------------------------------------------- C. Verificador

def verificador(modelo, prompt, pregunta, codigo, nombre, periodo, otros):
    """Devuelve (accion, llamada)."""
    mensajes = prompt.mensajes(pregunta=pregunta, codigo=codigo, nombre=nombre,
                               periodo=PERIODO_TXT[periodo], otros=", ".join(otros) or "ninguna")
    crudo, tokens, segundos = llamar(modelo, mensajes)
    d, _ = _extraer_json(crudo)

    accion = {"accion": "aceptar", "legible": d is not None}
    if d is not None and _texto(d.get("accion")).lower() == "rechazar":
        problema = _texto(d.get("problema")).lower().replace("í", "i").replace("é", "e")
        problema = "periodo" if problema.startswith("periodo") else "ramo"
        accion = {"accion": "rechazar", "problema": problema,
                  "motivo": _texto(d.get("motivo")) or "sin motivo", "legible": True}
    # La evidencia que copió antes de decidir queda en la traza, que es lo que muestra el video.
    # Si la cita no está en la consulta, el Verificador copió la interpretación que revisaba
    # (pasó en la v3). Se marca para medirlo; no cambia la acción.
    if d is not None:
        accion["cita_ramo"] = _texto(d.get("cita_ramo"))
        accion["cita_periodo"] = _texto(d.get("cita_periodo"))
        accion["cita_ramo_en_consulta"] = cita_en(accion["cita_ramo"], pregunta)
    return accion, {"mensajes": mensajes, "crudo": crudo, "tokens": tokens,
                    "segundos": segundos, "prompt": prompt.ref()}
