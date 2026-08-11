"""Gravação do efetivo e das diárias do plano (etapa 2 do wizard).

`BE-14` fatia 5. `planos_trabalho/services.py` tem 1.314 linhas e **zero**
`transaction.atomic` — é um dos três módulos que o enunciado do defeito cita pelo nome. As
gravações moravam em `per_diem_views.py`, soltas.

A ordem importa e é o que torna a falta de transação cara: o efetivo é reconciliado
**primeiro** e a diária é recalculada **depois**, porque o valor da diária é função do
total do efetivo. Sem transação, uma falha entre as duas deixa o plano com o efetivo novo
e o valor do efetivo antigo — dado errado num documento de dinheiro, e nada na tela
apontando a contradição.

Nenhuma função aqui recebe `request` (`docs/PADRAO_SERVICES.md:20`).
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from .models import PlanoTrabalho
from .selectors import cargo_pertence_a_area
from .selectors import unidade_pertence_a_area
from .services import atualizar_snapshot_diarias
from .services import atualizar_snapshot_diarias_combinadas


@dataclass(frozen=True)
class ResultadoEfetivo:
    """O que a etapa 2 precisa devolver para a tela."""

    efetivo: list[dict]
    diarias: dict | None


def _to_int_or_none(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@transaction.atomic
def reconciliar_efetivo(plano: PlanoTrabalho, rows) -> list[dict]:
    """Reconcilia o efetivo do plano com o snapshot recebido da tela.

    Linhas com `cargo` e `quantidade` válidos são criadas/atualizadas; linhas incompletas
    são ignoradas (placeholders no formulário). IDs ausentes no snapshot são removidos do
    banco para refletir o estado atual da tela.

    **Reconcilia por id e não pelo management form** de propósito: o autosave pode ter
    criado efetivos depois do carregamento da página, o que deixaria `INITIAL_FORMS`
    defasado e faria o `formset.save()` inserir duplicatas. Essa decisão é anterior ao
    `BE-14` e não mudou.

    `atomic` própria, e não só herdada de quem chama: são `save` e `create` **em laço**
    mais um `delete` no fim, e uma falha no meio deixa metade do efetivo trocado. O
    decorador de fora viraria SAVEPOINT e a garantia continuaria de pé, mas um chamador
    futuro que entrasse direto aqui herdaria a meia gravação de volta — foi o que a fatia
    1 mediu em `salvar_diarias_recebidas`.
    """
    existentes = {efetivo.pk: efetivo for efetivo in plano.efetivos.all()}
    mantidos: set[int] = set()
    saida: list[dict] = []
    vistos: set[tuple] = set()

    for index, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        cargo_id = _to_int_or_none(row.get("cargo"))
        quantidade = _to_int_or_none(row.get("quantidade"))
        unidade_id = _to_int_or_none(row.get("unidade"))
        client_idx = _to_int_or_none(row.get("idx"))
        if client_idx is None:
            client_idx = index
        if not cargo_id or not quantidade or quantidade <= 0:
            continue
        if not cargo_pertence_a_area(cargo_id):
            continue
        if unidade_id and not unidade_pertence_a_area(unidade_id):
            unidade_id = None
        chave = (unidade_id, cargo_id)
        if chave in vistos:
            continue
        vistos.add(chave)
        row_id = _to_int_or_none(row.get("id"))
        if row_id and row_id in existentes:
            efetivo = existentes[row_id]
            efetivo.unidade_id = unidade_id
            efetivo.cargo_id = cargo_id
            efetivo.quantidade = quantidade
            efetivo.save(update_fields=["unidade", "cargo", "quantidade", "updated_at"])
            mantidos.add(row_id)
        else:
            efetivo = plano.efetivos.create(
                unidade_id=unidade_id, cargo_id=cargo_id, quantidade=quantidade
            )
            mantidos.add(efetivo.pk)
        saida.append({"idx": client_idx, "id": efetivo.pk})

    remover = [pk for pk in existentes if pk not in mantidos]
    if remover:
        plano.efetivos.filter(pk__in=remover).delete()
    return saida


def _recalcular_diarias(plano: PlanoTrabalho) -> dict:
    """Atualiza o snapshot da diária do rascunho e, em multi-evento, o combinado."""
    resultado = atualizar_snapshot_diarias(plano)
    if plano.is_multi_evento:
        atualizar_snapshot_diarias_combinadas(plano)
    return resultado


@transaction.atomic
def salvar_efetivo_e_diarias(plano: PlanoTrabalho, *, rows, diarias_form) -> ResultadoEfetivo:
    """O `POST` da etapa 2: efetivo, campos de saída/chegada e a diária, de uma vez.

    São três blocos de gravação em sequência — a reconciliação (N linhas), o formulário do
    plano e o snapshot da diária. O form já validou; aqui só se grava.
    """
    efetivo = reconciliar_efetivo(plano, rows)
    plano = diarias_form.save()
    return ResultadoEfetivo(efetivo=efetivo, diarias=_recalcular_diarias(plano))


@transaction.atomic
def salvar_efetivo_do_autosave(
    plano: PlanoTrabalho, *, rows=None, diarias_form=None
) -> ResultadoEfetivo:
    """O autosave da etapa 2, onde cada bloco é opcional conforme o que veio sujo.

    A diária só é recalculada quando as duas pontas do período existem — recalcular com
    metade do período gravaria um valor que a tela não mostra. Regra anterior ao `BE-14`.
    """
    if diarias_form is not None:
        plano = diarias_form.save()

    efetivo = reconciliar_efetivo(plano, rows) if rows is not None else None

    diarias = None
    if plano.saida_sede_data and plano.chegada_sede_data:
        diarias = _recalcular_diarias(plano)
    return ResultadoEfetivo(efetivo=efetivo, diarias=diarias)
