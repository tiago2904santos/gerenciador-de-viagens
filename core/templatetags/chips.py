"""Filtro de tom de selo — o vocabulário antigo traduzido para o do v2."""

from django import template

from core.presenters.badges import tom_de_chip_v2

register = template.Library()


@register.filter(name="tom_v2")
def tom_v2(tone):
    """`{{ chip.tone|tom_v2 }}` — success/info/warning/danger → done/progress/info/late.

    Existe como FILTRO porque os presenters de card montam o selo com o
    vocabulário antigo e são compartilhados com telas ainda não migradas:
    traduzir no template deixa o presenter servindo aos dois lados enquanto a
    migração corre. Quando a última tela migrar, o mapa sobe para o presenter e
    este filtro sai.
    """
    return tom_de_chip_v2(tone)
