"""Fábricas de `CheckConstraint` para as regras que o banco passou a defender (`DB-07`).

O sistema tinha **2 `CheckConstraint` para 54 modelos**, contra 67 `UniqueConstraint`.
Na prática o banco não era última linha de defesa de nada: qualquer caminho que
escapasse do formulário — import, comando de gestão, migração de dados, correção
manual em produção — gravava período com fim antes do início ou dinheiro negativo,
e o valor seguia dali para o ofício e para a prestação assinada.

As três funções existem para que as 24 constraints novas digam a mesma coisa do
mesmo jeito. Escrever cada uma à mão convidava a divergência silenciosa: um `gt`
onde as outras usam `gte`, um sinal trocado. Elas rodam só na definição do modelo
— a migração recebe o `CheckConstraint` já expandido pelo `deconstruct()`, então
nada aqui vira dependência de migração.

**Nulo passa, e a condição não precisa dizer isso.** A primeira versão destas
funções trazia `Q(campo__isnull=True) | ...` na frente de cada condição, com a
justificativa de que `BaseConstraint.validate()` — o caminho Python do
`full_clean()` — não herdaria a semântica ternária do SQL. **Medido, é falso nos
dois caminhos:** removendo os ramos, nem o banco nem o `full_clean()` mudam de
comportamento, porque `CHECK` cujo resultado é `NULL` passa em SQL e o
`Q.check()` do Django chega ao mesmo resultado. Os ramos eram código inerte com
aparência de carga útil — pior do que um comentário, porque ninguém os removeria
sem medo. A garantia continua existindo e continua testada, agora onde ela é
verificável: `test_banco_aceita_com_um_dos_dois_nulo` e
`test_banco_aceita_valor_nulo`, em `core/tests/test_constraints_db07.py`.

**Por que `gte` e não `gt`.** Evento de um dia tem fim igual ao início, viagem de
ida e volta no mesmo horário é degenerada mas não impossível, e trecho sem
quilometragem rodada tem `km_final == km_inicial`. Recusar a igualdade quebraria
uso real; o defeito é a **inversão**. Provado por inversão: trocar `gte` por `gt`
reprova 22 casos de limite.
"""

from __future__ import annotations

from django.db import models
from django.db.models import F
from django.db.models import Q


def periodo_ordenado(
    inicio: str,
    fim: str,
    *,
    name: str,
    violation_error_message: str | None = None,
) -> models.CheckConstraint:
    """`fim` nunca antes de `inicio`. Nulo em qualquer um dos dois passa.

    `violation_error_message` é o texto que `validate_constraints()` levanta quando a
    regra é violada pelo caminho Python — formulário, autosave ou comando de gestão.
    Sem ele o Django monta `Restrição "<name>" foi violada.`, que serve para o log e
    não para a tela. Passe-o nas constraints que defendem campo que o operador digita;
    nas que só o código escreve, o padrão basta.
    """
    return models.CheckConstraint(
        condition=Q(**{f"{fim}__gte": F(inicio)}),
        name=name,
        **({"violation_error_message": violation_error_message} if violation_error_message else {}),
    )


def nao_negativo(campo: str, *, name: str) -> models.CheckConstraint:
    """Zero é válido, negativo não. Para valor calculado que pode dar zero."""
    return models.CheckConstraint(condition=Q(**{f"{campo}__gte": 0}), name=name)


def positivo(campo: str, *, name: str) -> models.CheckConstraint:
    """Nem zero nem negativo. Para valor que, existindo, tem de valer alguma coisa."""
    return models.CheckConstraint(condition=Q(**{f"{campo}__gt": 0}), name=name)
