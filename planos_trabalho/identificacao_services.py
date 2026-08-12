"""Gravação da identificação do plano (etapa 1 do wizard).

`BE-14` fatia 5. As duas rotas gravavam o **mesmo plano** duas ou três vezes em sequência,
sem transação:

- o `POST` do wizard: o formulário, os textos padrão regenerados e o snapshot da diária;
- o autosave: o formulário e os textos padrão.

O caso caro é o do `POST`. `sincronizar_textos_padrao` regenera a contextualização a partir
do destino e do programa, e `atualizar_snapshot_diarias` recalcula o valor a partir do
período. Uma falha entre os dois deixa o plano com **o texto do destino novo e o valor da
diária do destino antigo** — e os dois saem no mesmo documento, sem nada apontando que se
contradizem.

Nenhuma função aqui recebe `request` (`docs/PADRAO_SERVICES.md:20`); o `QueryDict` entra
por `flags_automaticas`, no mesmo desenho de `solicitacao_services.valores_do_lote` da
fatia 2.
"""

from __future__ import annotations

from django.db import transaction

from .models import PlanoTrabalho
from .services import atualizar_snapshot_diarias
from .services import sincronizar_textos_padrao

#: Campo de texto → flag que diz se ele ainda está no modo automático.
FLAGS_AUTOMATICAS = {
    "contextualizacao": "contextualizacao_auto",
    "coordenacao": "coordenacao_auto",
    "consideracao_final": "consideracao_auto",
}


def flags_automaticas(post) -> dict[str, bool]:
    """Lê do `POST` os três interruptores de "texto automático".

    Ausente conta como ligado — é o padrão da tela para plano novo, e trocar isso mudaria
    o comportamento de quem nunca tocou nos interruptores.
    """
    return {
        flag: (post.get(flag, "1") or "0").strip() != "0"
        for flag in FLAGS_AUTOMATICAS.values()
    }


@transaction.atomic
def salvar_identificacao_do_wizard(form, *, flags) -> PlanoTrabalho:
    """O `POST` da etapa 1: formulário, textos padrão e diária numa operação só."""
    plano = form.save()
    for flag, ligado in flags.items():
        setattr(plano, flag, ligado)
    campos_texto = sincronizar_textos_padrao(plano)
    plano.save(update_fields=[*{*campos_texto, *flags}, "updated_at"])
    if plano.saida_sede_data and plano.chegada_sede_data:
        atualizar_snapshot_diarias(plano)
    return plano


@transaction.atomic
def salvar_identificacao_do_autosave(form, *, campos_editados) -> PlanoTrabalho:
    """O autosave da etapa 1: o formulário e os textos que dependem dele.

    Editar um texto à mão **desliga** o modo automático daquele campo; mudar destino ou
    programa mantém sincronizado o que ainda estiver automático. Essa regra é anterior ao
    `BE-14` e não mudou — o que mudou é que as duas gravações agora caem juntas.
    """
    plano = form.save()

    flag_updates: list[str] = []
    for campo, flag in FLAGS_AUTOMATICAS.items():
        if campo in campos_editados:
            setattr(plano, flag, False)
            flag_updates.append(flag)

    campos_texto = sincronizar_textos_padrao(plano)
    if campos_texto or flag_updates:
        plano.save(update_fields=[*{*campos_texto, *flag_updates}, "updated_at"])
    return plano
