# -*- coding: utf-8 -*-
"""
Genera los prompts de las ablaciones de la versión 5 — Deliverable 3.

Cada ablación es una copia del prompt del sistema completo con UNA sola parte quitada. En la
v4 los archivos de ablación se escribieron a mano y `sin_descomposicion` terminó quitando dos
cosas (la lista de otros ramos y la regla del verbo). Acá se generan desde el prompt completo
con reemplazos exactos, y cada reemplazo tiene que encontrar su texto una vez: si el prompt
completo cambia y un reemplazo deja de calzar, el script falla en vez de generar una ablación
distinta de la declarada.

    python gen_ablaciones_v5.py           -> prompts/ablaciones/*.md
    python gen_ablaciones_v5.py --check   -> falla si algún archivo no coincide con lo generado

`sin_herramienta` (resolvedor_catalogo.md) no sale de acá: cambia la entrada del agente (el
catálogo en vez de los candidatos) y no solo una parte del texto. Se escribe a mano.
"""

import re
import sys
from pathlib import Path

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
CABECERA = re.compile(r"\A<!--.*?-->\n", re.S)


def _quitar(texto, reemplazos):
    for viejo, nuevo in reemplazos:
        n = texto.count(viejo)
        if n != 1:
            raise ValueError(f"el texto a quitar aparece {n} veces: {viejo[:60]!r}")
        texto = texto.replace(viejo, nuevo)
    return texto


def _bloque(nombre):
    """El bloque entre <!-- nombre --> y <!-- /nombre -->, con su salto de línea final."""
    return re.compile(rf"<!-- {nombre} -->\n.*?<!-- /{nombre} -->\n\n", re.S)


SIN_CITAS_EJEMPLOS = [
    ('"otros": ["química general 1"], "frase_periodo": "este semestre", ', '"otros": ["química general 1"], '),
    ('"otros": ["física 1"], "frase_periodo": "en marzo", ', '"otros": ["física 1"], '),
    ('"otros": ["cálculo 1"], "frase_periodo": "después del verano", ', '"otros": ["cálculo 1"], '),
    ('"otros": [], "frase_periodo": "ya", ', '"otros": [], '),
]

ABLACIONES = {
    "interprete_sin_lista_otros.md": ("interprete.md", "sin_lista_otros",
        "no pide la lista de las demás asignaturas (campo \"otros\"); la regla del verbo se queda", [
        ("devuelves cuatro cosas", "devuelves tres cosas"),
        ('2. "otros": las demás asignaturas que nombra la consulta, por ejemplo una que aprobó, '
         'reprobó o está cursando. Lista vacía si no nombra otras.\n3. "frase_periodo"',
         '2. "frase_periodo"'),
        ('4. "periodo"', '3. "periodo"'),
        ('"consultado": "<asignatura>", "otros": ["<asignatura>"], ', '"consultado": "<asignatura>", '),
        ('"otros": ["química general 1"], ', ''),
        ('"otros": ["física 1"], ', ''),
        ('"otros": ["cálculo 1"], ', ''),
        ('"otros": [], ', ''),
    ]),
    "interprete_sin_regla_verbo.md": ("interprete.md", "sin_regla_verbo",
        "no dice que la asignatura consultada es la que acompaña al verbo de inscribir", [
        ("Una consulta puede nombrar varias asignaturas. La que quiere inscribir es la que "
         "acompaña al verbo de inscribir, tomar o meter. Las demás son contexto, aunque "
         "aparezcan antes.\n\n", ""),
    ]),
    "interprete_sin_citas.md": ("interprete.md", "sin_citas_interprete",
        "no copia la frase que dice cuándo (frase_periodo) antes de decidir el período", [
        ("devuelves cuatro cosas", "devuelves tres cosas"),
        ('3. "frase_periodo": las palabras de la consulta que dicen cuándo quiere inscribir la '
         'asignatura consultada.\n4. "periodo"', '3. "periodo"'),
        ('El período sale de las palabras que dicen cuándo quiere inscribir la asignatura '
         'consultada. Cópialas en "frase_periodo" y decide el período a partir de ellas. Si la '
         'consulta dice que otra asignatura la está cursando ahora o este semestre, esas palabras '
         'hablan de la otra asignatura y no van en "frase_periodo". Si no dice cuándo, deja '
         '"frase_periodo" vacía y usa "actual".',
         'El período es el de la asignatura consultada. Si la consulta dice que otra asignatura '
         'la está cursando ahora o este semestre, eso habla de la otra asignatura. Si no dice '
         'cuándo, usa "actual".'),
        ('"otros": ["<asignatura>"], "frase_periodo": "<palabras>", ', '"otros": ["<asignatura>"], '),
    ] + SIN_CITAS_EJEMPLOS),
    "verificador_sin_citas.md": ("verificador.md", "sin_citas_verificador",
        "no copia citas de la consulta antes de comparar, y no hay revisión de citas", [
        (_bloque("citas"), ""),
        ("Después compara:", "Compara:"),
        ('{"cita_ramo": "<palabras de la consulta>", "cita_periodo": "<palabras de la consulta>", ', "{"),
        ('{"cita_ramo": "física 2", "cita_periodo": "en marzo", ', "{"),
        ('{"cita_ramo": "química 2", "cita_periodo": "este semestre", ', "{"),
        ('{"cita_ramo": "cálculo 2", "cita_periodo": "este semestre", ', "{"),
        ('{"cita_ramo": "dibujo industrial", "cita_periodo": "el que viene", ', "{"),
    ]),
    "verificador_sin_calendario.md": ("verificador.md", "sin_calendario",
        "no trae el calendario académico; todo lo demás igual, incluida la acción corregir_periodo", [
        (_bloque("calendario"), ""),
    ]),
}


def generar(nombre):
    origen, config, que, reemplazos = ABLACIONES[nombre]
    texto = (PROMPTS / origen).read_text(encoding="utf-8").replace("\r\n", "\n")
    cuerpo = CABECERA.sub("", texto)
    for viejo, nuevo in reemplazos:
        if isinstance(viejo, re.Pattern):
            cuerpo, n = viejo.subn(nuevo, cuerpo)
            if n != 1:
                raise ValueError(f"{nombre}: el bloque {viejo.pattern[:30]!r} aparece {n} veces")
        else:
            # Los reemplazos que siguen a uno anterior pueden repetirse en el texto (los
            # ejemplos): se aplican a todas las apariciones cuando el viejo texto se repite a
            # propósito, y si no, se exige una sola.
            n = cuerpo.count(viejo)
            if n == 0:
                raise ValueError(f"{nombre}: no se encontró {viejo[:60]!r}")
            if n > 1 and viejo.count('"<asignatura>"') + viejo.count("cita_ramo") == 0:
                raise ValueError(f"{nombre}: {viejo[:60]!r} aparece {n} veces")
            cuerpo = cuerpo.replace(viejo, nuevo)
    cabecera = (f"<!-- ABLACIÓN {config} · generada por scripts/gen_ablaciones_v5.py desde "
                f"prompts/{origen}\n     Igual al prompt completo salvo lo que se quita: {que}. "
                f"No editar a mano. -->\n")
    return cabecera + cuerpo


def main():
    check = "--check" in sys.argv
    malos = []
    for nombre in ABLACIONES:
        texto = generar(nombre)
        ruta = PROMPTS / "ablaciones" / nombre
        if check:
            actual = ruta.read_text(encoding="utf-8").replace("\r\n", "\n") if ruta.exists() else None
            if actual != texto:
                malos.append(nombre)
        else:
            ruta.write_text(texto, encoding="utf-8", newline="\n")
            print(f"-> prompts/ablaciones/{nombre}")
    if check:
        print("ablaciones al día" if not malos else f"desactualizadas: {', '.join(malos)}")
        return 1 if malos else 0
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
