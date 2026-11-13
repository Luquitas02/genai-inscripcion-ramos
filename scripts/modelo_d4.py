# -*- coding: utf-8 -*-
"""
El sistema del D3 con el Intérprete ajustado — Deliverable 4.

Un solo Phi en 4 bits en la GPU, con el adaptador LoRA encima. El adaptador se activa solo en
las llamadas del Intérprete. En las del Resolvedor y el Verificador se desactiva, así que esos
dos agentes corren con la base, igual que en el D3 (el enunciado lo permite: "the other agents
may keep the base model"). Cuál agente llama se reconoce por la primera línea de su prompt de
sistema, que cada archivo de `prompts/` fija ("Eres el intérprete...").

El mismo objeto sirve para el agente base: con `usar_adaptador=False` ninguna llamada lo usa.
Así el video puede mostrar el Intérprete base y el ajustado sobre la misma entrada sin cargar
dos modelos.

    from modelo_d4 import ConAdaptador
    m = ConAdaptador(runner_d3.cargar_modelo(), "ruta/o/repo-de-hugging-face")
"""

MARCA_INTERPRETE = "Eres el intérprete"


def es_interprete(mensajes):
    return mensajes[0]["role"] == "system" and mensajes[0]["content"].startswith(MARCA_INTERPRETE)


class ConAdaptador:
    def __init__(self, base, adaptador, etiqueta="A-lora", revision=None):
        from peft import PeftModel
        self.base = base
        self.base.modelo = PeftModel.from_pretrained(base.modelo, adaptador, revision=revision)
        self.base.modelo.eval()
        self.adaptador = adaptador
        self.usar_adaptador = True
        self.etiqueta = etiqueta
        self.llamadas_con_adaptador = 0

    @property
    def nombre(self):
        nombre = self.base.nombre.split("/")[-1]
        return f"{nombre}+{self.etiqueta}" if self.usar_adaptador else nombre

    def generar(self, mensajes):
        if self.usar_adaptador and es_interprete(mensajes):
            self.llamadas_con_adaptador += 1
            return self.base.generar(mensajes)
        with self.base.modelo.disable_adapter():
            return self.base.generar(mensajes)


def _pruebas():
    import orquestador as O
    p = O.cargar_prompts("completo")
    assert es_interprete(p["interprete"].mensajes(pregunta="x", revision=""))
    assert not es_interprete(p["resolvedor"].mensajes(consultado="x", otros="", candidatos="",
                                                       busquedas=""))
    for archivo in ("d4/interprete_muchos_ejemplos.md", "ablaciones/interprete_sin_citas.md"):
        import agentes as A
        assert es_interprete(A.Prompt(archivo).mensajes(pregunta="x", revision="")), archivo
    print("modelo_d4: el Intérprete se reconoce en todos sus prompts y el Resolvedor no")


if __name__ == "__main__":
    _pruebas()
