"""Persistência do número de solicitação, da data de liberação e do prazo limite.

`BE-14` fatia 2. As duas rotas que gravam esses três campos moravam em
`prestacoes_contas/views.py` e gravavam **fora de transação**:

- o lote sem JS percorria N servidores e fazia um `UPDATE` por servidor — uma falha no
  terceiro deixava os dois primeiros gravados;
- o autosave gravava campo a campo, com até três `save()` no mesmo objeto e três
  marcações de status, ou seja **até seis escritas numa requisição só**.

**Esta fatia não unifica as duas rotas.** Elas divergem em três pontos há muito tempo, e
os três estão fotografados em `test_solicitacao.py` e em
`test_solicitacao_transacao_be14.py`:

| | lote (sem JS) | autosave (com JS) |
|---|---|---|
| data inválida | engole em silêncio, mantém a anterior | devolve `ok=False` com mensagem |
| status | **não marca** | marca em preenchimento |
| erro no meio | continua nos outros servidores | para, com o que já gravou no banco |

Escolher qual comportamento vence muda o que o operador vê, e é decisão de produto — não
de camada. O que muda aqui é só onde a gravação mora e o fato de ela ser atômica.

Uma consequência do que **não** muda, e que merece ser dita: a transação não desfaz a
gravação parcial do autosave, porque o erro de data sai por `return`, não por exceção. O
`atomic` commita, e o número continua salvo. Isso é o comportamento de hoje, travado por
teste.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass

from django.db import transaction

from core.normalizers import normalize_spaces

from .services import marcar_servidor_em_preenchimento

_CAMPOS_DO_LOTE = {
    "numero_solicitacao": re.compile(r"^ps-(\d+)-numero_solicitacao$"),
    "data_liberacao_diarias": re.compile(r"^ps-(\d+)-data_liberacao_diarias$"),
    "prazo_limite_saque": re.compile(r"^ps-(\d+)-prazo_limite_saque$"),
}

#: Mensagem por campo de data, como o autosave sempre respondeu.
MENSAGEM_DATA_INVALIDA = {
    "data_liberacao_diarias": "Data de liberação inválida.",
    "prazo_limite_saque": "Data de prazo limite inválida.",
}


@dataclass(frozen=True)
class ResultadoSolicitacao:
    """O que a gravação fez. A view traduz isto em JSON ou em `messages`.

    `erro` é **retorno, não exceção**: é assim que o autosave responde `ok=False` sem
    desfazer o que já entrou — comportamento de hoje, preservado nesta fatia.
    """

    erro: str = ""
    campos_gravados: tuple[str, ...] = ()
    servidores_gravados: int = 0

    @property
    def ok(self) -> bool:
        return not self.erro


def _parse_iso_date(texto):
    """Converte ``'AAAA-MM-DD'`` em ``date``; ``''`` vira ``None``."""
    if not texto:
        return None
    return datetime.date.fromisoformat(texto)


def valores_do_lote(post) -> dict[int, dict[str, str]]:
    """Lê `ps-<pk>-<campo>` do POST e agrupa por servidor.

    Recebe o `QueryDict`, não o `request` (`docs/PADRAO_SERVICES.md:20`). Só leitura:
    nada aqui grava, e é isso que permite a view decidir se há o que fazer antes de
    abrir transação.
    """
    por_servidor: dict[int, dict[str, str]] = {}
    for nome, valor in post.items():
        for campo, padrao in _CAMPOS_DO_LOTE.items():
            match = padrao.match(str(nome or ""))
            if not match:
                continue
            texto = normalize_spaces(valor or "") if campo == "numero_solicitacao" else (valor or "").strip()
            por_servidor.setdefault(int(match.group(1)), {})[campo] = texto
            break
    return por_servidor


@transaction.atomic
def salvar_solicitacoes_em_lote(servidores, valores) -> ResultadoSolicitacao:
    """Grava os três campos de N servidores, um `UPDATE` por servidor.

    Atômica porque grava **em laço**: sem ela, uma falha no meio deixa parte da lista com
    o valor novo e parte com o antigo, e o operador volta para uma tela que não diz qual
    é qual.

    **Data inválida é engolida de propósito**, mantendo o valor anterior — é o
    comportamento do caminho sem JS desde sempre, fotografado em
    `test_solicitacao.py:178`. Diverge do autosave, e unificar é decisão de produto.
    """
    gravados = 0
    for servidor_prestacao in servidores:
        campos = valores.get(servidor_prestacao.pk)
        if not campos:
            continue
        update_fields = []
        if "numero_solicitacao" in campos:
            novo = campos["numero_solicitacao"]
            if servidor_prestacao.numero_solicitacao != novo:
                servidor_prestacao.numero_solicitacao = novo
                update_fields.append("numero_solicitacao")
        for campo in ("data_liberacao_diarias", "prazo_limite_saque"):
            if campo not in campos:
                continue
            try:
                novo_valor = _parse_iso_date(campos[campo])
            except ValueError:
                novo_valor = getattr(servidor_prestacao, campo)
            if getattr(servidor_prestacao, campo) != novo_valor:
                setattr(servidor_prestacao, campo, novo_valor)
                update_fields.append(campo)
        if update_fields:
            servidor_prestacao.save(update_fields=[*update_fields, "atualizado_em"])
            gravados += 1
    return ResultadoSolicitacao(servidores_gravados=gravados)


@transaction.atomic
def salvar_solicitacao_do_autosave(
    servidor_prestacao, *, numero=None, datas=None
) -> ResultadoSolicitacao:
    """Grava o que veio sujo do autosave, campo a campo, e marca o status.

    `numero` e cada entrada de `datas` valem `None` quando **não vieram no payload** — o
    autosave manda só o que mudou, e ausência não é ordem de apagar.

    A ordem das gravações é a de hoje (número, liberação, prazo) e o erro de data
    interrompe o restante, **deixando gravado o que já entrou**. Isso é decisão de
    produto anterior a esta fatia, travada por
    `test_solicitacao_transacao_be14.py::test_numero_fica_gravado_mesmo_quando_a_data_seguinte_e_recusada`.
    A transação não a desfaz porque o erro sai por `return`, não por exceção.
    """
    gravados: list[str] = []

    def _gravar(campo, valor):
        setattr(servidor_prestacao, campo, valor)
        servidor_prestacao.save(update_fields=[campo, "atualizado_em"])
        marcar_servidor_em_preenchimento(servidor_prestacao)
        gravados.append(campo)

    if numero is not None and servidor_prestacao.numero_solicitacao != numero:
        _gravar("numero_solicitacao", numero)

    for campo in ("data_liberacao_diarias", "prazo_limite_saque"):
        bruto = (datas or {}).get(campo)
        if bruto is None:
            continue
        try:
            novo_valor = _parse_iso_date(bruto)
        except ValueError:
            return ResultadoSolicitacao(
                erro=MENSAGEM_DATA_INVALIDA[campo], campos_gravados=tuple(gravados)
            )
        if getattr(servidor_prestacao, campo) != novo_valor:
            _gravar(campo, novo_valor)

    return ResultadoSolicitacao(campos_gravados=tuple(gravados))
