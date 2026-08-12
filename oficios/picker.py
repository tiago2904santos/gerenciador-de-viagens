"""Peças comuns dos seletores de ofício servidos sob demanda (`NOVO-07`).

Três telas montam o mesmo seletor pelo mesmo mecanismo — `justificativas`
(quick add), `termos` e `ordens_servico`. Cada uma tem o seu resumo, com campos
diferentes (`termos` e `ordens_servico` carregam `data_inicio`, `estado_id` e
companhia, que o preenchimento automático lê), então o resumo continua morando
em cada app. O que é igual nas três mora aqui.

O que muda com este ID: o `json_script` da página deixa de trazer todo ofício da
área — media ~680 bytes por ofício, e a página crescia com a tabela — e passa a
trazer só os **já selecionados**. O resto chega por um endpoint de busca.
"""

from __future__ import annotations

from django.forms.models import ModelChoiceIteratorValue


# Teto do que a busca devolve numa tacada. Não é paginação: o seletor é para
# encontrar um ofício, e quem digita algo que casa com mais de 30 refina a busca
# em vez de rolar. O teto mora no servidor porque o cliente não é confiável.
LIMITE_BUSCA = 30


def _como_pk(valor):
    """Aceita pk cru ou instância.

    `ModelMultipleChoiceField` num `ModelForm` recebe `initial` de
    `model_to_dict`, e para campo M2M isso são **instâncias**, não pks
    (`ManyToManyField.value_from_object`). Para FK são pks. Os dois caminhos
    passam por aqui.
    """
    return getattr(valor, "pk", valor)


def pks_ja_escolhidos(form, nome_do_campo):
    """Os pks que o formulário já tem selecionados, como lista de strings.

    Quando o formulário está *bound* — re-render depois de erro de validação — a
    escolha está em `form.data`, não em `initial`. Sem ler de lá, o que a pessoa
    acabou de escolher sumiria da tela junto com a mensagem de erro.
    """
    if form.is_bound:
        dados = form.data
        chave = form.add_prefix(nome_do_campo)
        brutos = dados.getlist(chave) if hasattr(dados, "getlist") else [dados.get(chave)]
    else:
        bruto = form.initial.get(nome_do_campo)
        brutos = list(bruto) if isinstance(bruto, (list, tuple, set)) else [bruto]
    return [str(_como_pk(valor)) for valor in brutos if str(_como_pk(valor) or "").isdigit()]


def oficios_ja_escolhidos(form, nome_do_campo):
    """Queryset com os ofícios já selecionados — o que precisa virar `<option>`.

    Sai do `queryset` do próprio campo, então herda o recorte por área e os
    filtros que o formulário aplicou (`ordens_servico` exclui cancelados).
    """
    campo = form.fields[nome_do_campo]
    pks = pks_ja_escolhidos(form, nome_do_campo)
    return campo.queryset.filter(pk__in=pks) if pks else campo.queryset.none()


def renderizar_so_os_escolhidos(form, nome_do_campo):
    """Deixa o campo **aceitando** a área inteira e **renderizando** só o escolhido.

    `ModelChoiceField.queryset` alimenta as duas coisas ao mesmo tempo. A
    separação é atribuir `widget.choices` — lista curta — **depois** de qualquer
    atribuição de `queryset`: `_set_queryset` reatribui `widget.choices`, então
    invertida a ordem o queryset largo voltaria a ser renderizado inteiro.

    O `queryset` fica largo de propósito. É ele que valida o pk que o seletor
    mandou sem que a página o tivesse renderizado — estreitá-lo junto com o
    `choices` faria o submit pelo seletor parar de funcionar, e nenhuma tela
    mostraria isso antes de alguém tentar salvar.

    A lista reproduz `ModelChoiceIterator`, item por item, em vez de inventar
    tuplas `(pk, texto)`. Dois motivos, os dois silenciosos se ignorados:

    - o valor tem de ser `ModelChoiceIteratorValue`, senão os `create_option` de
      `termos` e `ordens_servico` — que leem `value.instance` — desistem, e a
      opção sai sem `data-main`, `data-meta` nem `data-search`;
    - a opção vazia tem de continuar existindo em campo de escolha única. Um
      `<select>` sem `multiple` e sem opção vazia faz o navegador selecionar a
      primeira: desmarcar o ofício no seletor voltaria a marcá-lo, e o formulário
      gravaria um vínculo que ninguém pediu.
    """
    campo = form.fields[nome_do_campo]
    escolhas = []
    if getattr(campo, "empty_label", None) is not None:
        escolhas.append(("", campo.empty_label))
    escolhas += [
        (ModelChoiceIteratorValue(oficio.pk, oficio), campo.label_from_instance(oficio))
        for oficio in oficios_ja_escolhidos(form, nome_do_campo)
    ]
    campo.widget.choices = escolhas


def dados_do_option(oficio, *, resumo, rotulo, decorar=False):
    """O que o JS precisa para recriar um `<option>` igual ao que o Django renderiza.

    `decorar` acompanha o widget da tela. Os de `termos` e `ordens_servico`
    sobrescrevem `create_option` para pôr `data-main` e `data-meta`, que o
    seletor lê ao montar a linha do resultado — sem eles a opção vinda da busca
    apareceria sem protocolo nem assunto, mesma lista com linhas diferentes. O
    de `justificativas` é um `SelectMultiple` cru, e ali a opção continua crua.

    `search` vem do `search_text` do resumo, não do `data-search` do widget: o
    servidor casa por sede, destino e nome de servidor, e o filtro local do
    seletor descartaria justamente o que a busca achou se o texto de busca fosse
    mais estreito que a consulta.
    """
    dados = {
        "texto": rotulo(oficio),
        "search": " ".join(
            parte for parte in [resumo.get("search_text") or "", str(oficio.pk)] if parte
        ),
    }
    if decorar:
        protocolo = oficio.protocolo or ""
        assunto = oficio.assunto or ""
        dados["main"] = rotulo(oficio)
        dados["meta"] = " - ".join(parte for parte in [protocolo, assunto] if parte)
    return dados
