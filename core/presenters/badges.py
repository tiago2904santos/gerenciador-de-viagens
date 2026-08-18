def build_badge(label, variant="neutral"):
    return {"text": label, "variant": variant}


#: Tons do sistema antigo -> tons do `c-v2.chip` (`static/css/v2/chip.css`, que
#: conhece `done`, `progress`, `late` e `info`). O par não é literal, é
#: SEMÂNTICO: "faltam 3 dias" é aviso no legado e informação no v2; "em
#: andamento" é informação no legado e progresso no v2. Traduzir pelo nome
#: deixaria uma viagem em curso com a cor de uma que já passou.
#:
#: Fica aqui, e não na tela que migrou primeiro, porque toda lista que vier
#: depois tem o mesmo selo — foi assim que o sistema antigo acumulou seis
#: vocabulários de cor.
TONS_DE_CHIP_V2 = {
    "success": "done",
    "info": "progress",
    "warning": "info",
    "danger": "late",
    "muted": "",
}


def tom_de_chip_v2(tone):
    """Devolve o tom do chip v2 para um tom do vocabulário antigo."""
    return TONS_DE_CHIP_V2.get(tone or "", "")
