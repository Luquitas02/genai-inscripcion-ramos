# -*- coding: utf-8 -*-
"""
Genera los prompts de las ablaciones de una sola técnica de la v4 (PROTOCOLO_ABLACIONES_V4.md).

La auditoría del 21 de octubre encontró que `sin_descomposicion` quitaba dos instrucciones a la
vez y que citar antes de decidir ("quotes first" en la Lecture 5) no se había ablacionado.
Cada archivo de abajo parte de `prompts/interprete.md` o `prompts/verificador.md` (v4, los
mismos hashes del protocolo) y quita una sola cosa, con reemplazos exactos. Los prompts del
sistema completo no se tocan.

    interprete_sin_lista_otros.md    sin el campo "otros" (la lista de las demás asignaturas)
    interprete_sin_regla_verbo.md    sin "la que acompaña al verbo de inscribir, tomar o meter"
    interprete_sin_citas.md          sin "frase_periodo": decide el período sin copiar la frase
    verificador_sin_citas.md         sin "cita_ramo" y "cita_periodo": compara sin copiar
    verificador_sin_ejemplos.md      sin sus 2 ejemplos
    resolvedor_sin_regla_siglas.md   sin la regla de siglas (PROTOCOLO_ABLACIONES_B.md, 29 oct)
    resolvedor_sin_regla_numeros.md  sin la regla de números (ídem)

    python gen_ablaciones_v4.py           escribe los archivos en prompts/ablaciones/
    python gen_ablaciones_v4.py --check   comprueba que los archivos guardados son los generados
"""

import re
import sys
from pathlib import Path

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"


def reemplazar(texto, viejo, nuevo):
    assert texto.count(viejo) == 1, f"no aparece exactamente una vez: {viejo[:60]!r}"
    return texto.replace(viejo, nuevo)


def cabecera(texto, nueva):
    """Cambia el comentario inicial <!-- ... --> por el de la ablación."""
    fin = texto.index("-->") + 3
    return nueva + texto[fin:]


def interprete_sin_lista_otros(t):
    t = cabecera(t, "<!-- agente: intérprete, ABLACIÓN sin la lista de otras asignaturas · v4\n"
                    "     Igual a prompts/interprete.md salvo el campo \"otros\". La regla del verbo\n"
                    "     y la frase \"las demás son contexto\" se mantienen. Lo genera\n"
                    "     scripts/gen_ablaciones_v4.py. -->")
    t = reemplazar(t, "devuelves cuatro cosas:", "devuelves tres cosas:")
    t = reemplazar(t, '2. "otros": las demás asignaturas que nombra la consulta, por ejemplo una '
                      'que aprobó, reprobó o está cursando. Lista vacía si no nombra otras.\n', "")
    t = reemplazar(t, '3. "frase_periodo"', '2. "frase_periodo"')
    t = reemplazar(t, '4. "periodo"', '3. "periodo"')
    t = reemplazar(t, '"otros": ["<asignatura>"], ', "")
    t, n = re.subn(r'"otros": \[[^\]]*\], ', "", t)
    assert n == 4, n
    return t


def interprete_sin_regla_verbo(t):
    t = cabecera(t, "<!-- agente: intérprete, ABLACIÓN sin la regla del verbo · v4\n"
                    "     Igual a prompts/interprete.md salvo la oración que dice que la asignatura\n"
                    "     consultada es la que acompaña al verbo de inscribir, tomar o meter. Lo\n"
                    "     genera scripts/gen_ablaciones_v4.py. -->")
    return reemplazar(t, "Una consulta puede nombrar varias asignaturas. La que quiere inscribir es "
                         "la que acompaña al verbo de inscribir, tomar o meter. Las demás son "
                         "contexto, aunque aparezcan antes.",
                      "Una consulta puede nombrar varias asignaturas. Una es la que quiere "
                      "inscribir y las demás son contexto, aunque aparezcan antes.")


def interprete_sin_citas(t):
    t = cabecera(t, "<!-- agente: intérprete, ABLACIÓN sin citar antes de decidir · v4\n"
                    "     Igual a prompts/interprete.md salvo \"frase_periodo\": decide el período\n"
                    "     sin copiar antes las palabras que lo dicen. Lo genera\n"
                    "     scripts/gen_ablaciones_v4.py. -->")
    t = reemplazar(t, "devuelves cuatro cosas:", "devuelves tres cosas:")
    t = reemplazar(t, '3. "frase_periodo": las palabras de la consulta que dicen cuándo quiere '
                      'inscribir la asignatura consultada.\n', "")
    t = reemplazar(t, '4. "periodo"', '3. "periodo"')
    t = reemplazar(t, 'Cópialas en "frase_periodo" y decide el período a partir de ellas. ', "")
    t = reemplazar(t, 'hablan de la otra asignatura y no van en "frase_periodo".',
                   "hablan de la otra asignatura.")
    t = reemplazar(t, 'Si no dice cuándo, deja "frase_periodo" vacía y usa "actual".',
                   'Si no dice cuándo, usa "actual".')
    t = reemplazar(t, '"frase_periodo": "<palabras>", ', "")
    t, n = re.subn(r'"frase_periodo": "[^"]*", ', "", t)
    assert n == 4, n
    return t


def verificador_sin_citas(t):
    t = cabecera(t, "<!-- agente: verificador, ABLACIÓN sin citar antes de decidir · v4\n"
                    "     Igual a prompts/verificador.md salvo \"cita_ramo\" y \"cita_periodo\":\n"
                    "     compara la consulta con la interpretación sin copiar antes la evidencia.\n"
                    "     Lo genera scripts/gen_ablaciones_v4.py. -->")
    t = reemplazar(t, "Primero copia dos cosas de la CONSULTA DEL ESTUDIANTE, con sus palabras "
                      "exactas. No copies de la interpretación: la interpretación es lo que estás "
                      "revisando.\n\n"
                      '- "cita_ramo": las palabras con que la consulta nombra la asignatura que '
                      "quiere inscribir.\n"
                      '- "cita_periodo": las palabras de la consulta que dicen cuándo quiere '
                      'inscribir esa asignatura. Si la consulta no lo dice, escribe "".\n\n'
                      "Después compara:", "Compara:")
    t = reemplazar(t, '1. ¿"cita_ramo" nombra la asignatura de la interpretación?',
                   "1. ¿La asignatura que la consulta quiere inscribir es la de la interpretación?")
    t = reemplazar(t, '2. ¿"cita_periodo" corresponde al período de la interpretación?',
                   "2. ¿Lo que dice la consulta sobre cuándo quiere inscribirla corresponde al "
                   "período de la interpretación?")
    t = reemplazar(t, 'Si "cita_periodo" está vacía, "actual" es correcto.',
                   'Si la consulta no dice cuándo, "actual" es correcto.')
    t, n = re.subn(r'"cita_ramo": "[^"]*", "cita_periodo": "[^"]*", ', "", t)
    assert n == 4, n
    return t


def verificador_sin_ejemplos(t):
    t = cabecera(t, "<!-- agente: verificador, ABLACIÓN sin ejemplos · v4\n"
                    "     Igual a prompts/verificador.md salvo sus dos ejemplos. Lo genera\n"
                    "     scripts/gen_ablaciones_v4.py. -->")
    inicio, fin = t.index("Ejemplos:\n"), t.index("Responde ÚNICAMENTE")
    assert t.count("Ejemplos:\n") == 1
    return t[:inicio] + t[fin:]


def resolvedor_sin_regla_siglas(t):
    t = cabecera(t, "<!-- agente: resolvedor, ABLACIÓN sin la regla de siglas · v2\n"
                    "     Igual a prompts/resolvedor.md salvo el párrafo que dice qué hacer con una\n"
                    "     sigla o abreviación. La acción \"buscar\" y su ejemplo se mantienen. Lo\n"
                    "     genera scripts/gen_ablaciones_v4.py (PROTOCOLO_ABLACIONES_B.md). -->")
    return reemplazar(t, "Si el estudiante usó una sigla o una abreviación y ningún candidato "
                         "contiene esas letras o palabras, no elijas el más parecido: busca de nuevo "
                         "escribiendo el nombre completo que crees que significa.\n\n", "")


def resolvedor_sin_regla_numeros(t):
    t = cabecera(t, "<!-- agente: resolvedor, ABLACIÓN sin la regla de números · v2\n"
                    "     Igual a prompts/resolvedor.md salvo el párrafo sobre los números. Lo\n"
                    "     genera scripts/gen_ablaciones_v4.py (PROTOCOLO_ABLACIONES_B.md). -->")
    return reemplazar(t, "Fíjate en los números: \"2\", \"II\" y \"dos\" son lo mismo, y una "
                         "asignatura 1 no es la misma que su 2.\n\n", "")


ABLACIONES = {
    "resolvedor_sin_regla_siglas.md": ("resolvedor.md", resolvedor_sin_regla_siglas),
    "resolvedor_sin_regla_numeros.md": ("resolvedor.md", resolvedor_sin_regla_numeros),
    "interprete_sin_lista_otros.md": ("interprete.md", interprete_sin_lista_otros),
    "interprete_sin_regla_verbo.md": ("interprete.md", interprete_sin_regla_verbo),
    "interprete_sin_citas.md": ("interprete.md", interprete_sin_citas),
    "verificador_sin_citas.md": ("verificador.md", verificador_sin_citas),
    "verificador_sin_ejemplos.md": ("verificador.md", verificador_sin_ejemplos),
}


def generar():
    return {nombre: f(open(PROMPTS / base, encoding="utf-8").read())
            for nombre, (base, f) in ABLACIONES.items()}


def main():
    textos = generar()
    if "--check" in sys.argv:
        malos = [n for n, t in textos.items()
                 if not (PROMPTS / "ablaciones" / n).exists()
                 or (PROMPTS / "ablaciones" / n).read_text(encoding="utf-8") != t]
        if malos:
            print("distintos de lo generado:", ", ".join(malos))
            return 1
        print(f"{len(textos)}/{len(textos)} prompts de ablación iguales a lo generado")
        return 0
    for n, t in textos.items():
        with open(PROMPTS / "ablaciones" / n, "w", encoding="utf-8", newline="\n") as f:
            f.write(t)
        print("escrito", n)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
