def build_meta(label, value):
    return {"label": label, "value": value}


#: O que o presenter escreve quando o campo não tem valor.
VAZIO = "—"


def linha_de_meta(itens):
    """Junta os valores de `meta` numa linha só, para a lista.

    Duas decisões, e as duas medidas em tela:

    - **Só os valores, sem os rótulos.** "Trechos: 16 trechos" e "Valor: R$
      2.789,44" dizem duas vezes a mesma coisa; numa lista o que se lê é a
      diferença entre uma linha e a outra.
    - **Só os preenchidos.** O traço de campo vazio, sem o rótulo ao lado, não
      informa nada — a linha saía "— · 2 trechos · —".

    Existe aqui, e não no template, porque o separador condicional é proibido
    em template (`test_conditional_separators`): montá-lo com `{% if %}` espalha
    pelas telas uma decisão de apresentação que é de um lugar só.
    """
    return " · ".join(
        str(item["value"]).strip()
        for item in itens or []
        if item and str(item.get("value") or "").strip() not in ("", VAZIO)
    )
