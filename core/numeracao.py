"""Reserva de número de documento oficial, em um lugar só (`BE-15`).

Três documentos recebem número — Ofício, Ordem de Serviço e Plano de Trabalho — e cada um
tinha a sua cópia do mesmo mecanismo. O que estava reimplementado três vezes não era a
**política** (reuso de lacuna, piso, contador: essas são diferentes de propósito, porque os
documentos são diferentes), e sim a **mecânica**: serializar o escopo e repetir a escolha
quando outro processo venceu a corrida.

O que está aqui, e por quê:

**Serializar o escopo, não a linha.** Bloquear as linhas existentes não protege o próximo
número, porque ele ainda não existe. No PostgreSQL o advisory lock transacional cobre
exatamente esse intervalo lógico — "a numeração da área A no ano Y" — sem exigir uma tabela
de contadores. Fora do PostgreSQL cai no `select_for_update`, que é o que sustenta o
ambiente de desenvolvimento e a metade SQLite da suíte.

**Repetir quando perder a corrida.** Mesmo com o lock, um processo antigo (de antes do
deploy, ou de outro nó sem o lock) pode ter gravado o número escolhido. A `UniqueConstraint`
pega, e a tentativa seguinte já enxerga o número que venceu.

## A colisão é detectada perguntando ao banco, não lendo a mensagem dele

As três cópias faziam `if "<nome_da_constraint>" not in str(exc): raise`. **Isso só funciona
no PostgreSQL.** Medido nos dois bancos:

- PostgreSQL: `duplicate key value violates unique constraint "oficios_oficio_area_ano_numero_unique"`
- SQLite: `UNIQUE constraint failed: oficios_oficio.area_id, oficios_oficio.ano, oficios_oficio.numero`

A mensagem do SQLite **não contém o nome da constraint**, então o `not in` era sempre
verdadeiro e o retry re-levantava na primeira colisão. Em produção (PostgreSQL) o laço
funcionava; em metade da suíte ele era código morto, e o teste que existia passava porque
**fabricava** um `IntegrityError` já contendo o texto esperado — provava o laço, nunca o
casamento.

Aqui a identificação tem duas fontes, nesta ordem:

1. **O metadado estruturado da exceção**, quando o driver oferece. No PostgreSQL o psycopg
   expõe `exc.__cause__.diag.constraint_name` já com o nome exato (`sqlstate` `23505`) —
   é comparação de igualdade, não substring, e não depende de o texto da mensagem manter
   o formato entre versões.
2. **A ocupação atual do número**, quando não há metadado (SQLite). Se aquele número está
   tomado agora, foi colisão e vale repetir.

**Por que o metadado vem primeiro, e não a ocupação.** A ocupação é prova *indireta*: se a
linha que causou a colisão for apagada entre o `INSERT` que falhou e a consulta seguinte —
e as rotas de exclusão de ofício e de OS não tomam este lock, com `READ COMMITTED` a
consulta enxerga a exclusão —, a resposta vira "não está ocupado" e um `IntegrityError` que
merecia nova tentativa sobe cru. A janela é estreita, mas existe, e no PostgreSQL não é
preciso conviver com ela. No SQLite o resíduo permanece; lá não há metadado, e o ambiente
não é produção.
"""

from __future__ import annotations

from collections.abc import Callable

from django.db import IntegrityError
from django.db import connection
from django.db import transaction

#: Namespaces do advisory lock, um por documento. Precisam ser distintos: iguais, a
#: numeração de dois documentos passaria a se serializar mutuamente sem necessidade.
#: Os valores são os ASCII dos apelidos, mantidos como estavam para não mudar o
#: comportamento de nenhum nó que esteja no ar durante o deploy.
NAMESPACE_OFICIO = 0x4F464943  # "OFIC"
NAMESPACE_ORDEM_SERVICO = 0x4F534E55  # "OSNU"
NAMESPACE_PLANO_TRABALHO = 0x50544E55  # "PTNU"

#: Teto do `int4` que o `pg_advisory_xact_lock(int, int)` aceita.
_LIMITE_INT4 = 2_147_483_647

#: Quantos anos cabem num escopo antes de dois anos colidirem no mesmo lock. Colisão aqui
#: não corrompe nada — apenas serializa duas faixas que poderiam correr em paralelo.
_ANOS_POR_AREA = 4096

TENTATIVAS_PADRAO = 3


def escopo_do_lock(*, area_id: int | None, ano: int) -> int:
    """Um inteiro por (área, ano), estável entre processos."""
    return (((area_id or 0) * _ANOS_POR_AREA) + (ano % _ANOS_POR_AREA)) % _LIMITE_INT4


def bloquear_escopo_numeracao(*, namespace: int, area_id: int | None, ano: int, modelo) -> None:
    """Serializa a escolha do próximo número para uma área/ano.

    `modelo` é a classe do documento numerado; serve só ao caminho de fallback, para
    descobrir o modelo de área e para travar a faixa sem área.

    **O ramo `area_id is None` não é morto**, embora `area` seja `NOT NULL` nos três
    documentos desde o `DB-02`: a reserva acontece **antes** do `save()`, e é o `save()`
    que preenche a área a partir do evento ou da área ativa. No instante do lock o
    `area_id` ainda pode ser `None`, e sem este ramo a faixa global ficaria sem
    serialização nenhuma.
    """
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                [namespace, escopo_do_lock(area_id=area_id, ano=ano)],
            )
        return

    if area_id:
        area_model = modelo._meta.get_field("area").remote_field.model
        area_model.objects.select_for_update().filter(pk=area_id).exists()
        return

    list(
        # `BE-09`: `all_objects` — o lock cobre a faixa `area IS NULL`, e recortar pela
        # área ativa o deixaria vazio, matando a serialização em silêncio.
        modelo.all_objects.select_for_update()
        .filter(area__isnull=True, ano=ano)
        .exclude(numero__isnull=True)
    )


def colisao_de_numero(
    exc: IntegrityError, *, constraint: str, ja_ocupado: Callable[[int], bool], numero: int
) -> bool:
    """A violação foi a corrida por este número, ou é outra coisa?

    Duas fontes, nesta ordem — ver o cabeçalho do módulo para o porquê da ordem.
    """
    diagnostico = getattr(getattr(exc, "__cause__", None), "diag", None)
    nome = getattr(diagnostico, "constraint_name", None)
    if nome:
        return nome == constraint
    return ja_ocupado(numero)


def reservar_numero(
    *,
    namespace: int,
    area_id: int | None,
    ano: int,
    modelo,
    constraint: str,
    escolher: Callable[[], int],
    gravar: Callable[[int], None],
    ja_ocupado: Callable[[int], bool],
    apos_colisao: Callable[[], None] | None = None,
    tentativas: int = TENTATIVAS_PADRAO,
) -> int:
    """Escolhe e grava o próximo número, serializado e à prova de corrida perdida.

    - `escolher()` devolve o candidato — é onde mora a **política** de cada documento
      (menor lacuna, `max+1`, contador), e por isso ela não vem para cá.
    - `gravar(numero)` persiste. Roda dentro de um `atomic()` próprio: é **savepoint**, para
      que uma colisão não inutilize a transação de quem chamou.
    - `constraint` é o nome da `UniqueConstraint` que guarda o número. Comparado por
      igualdade contra o metadado da exceção quando o driver o oferece.
    - `ja_ocupado(numero)` responde se aquele número está tomado **agora**. É o segundo
      recurso, para bancos sem metadado — ver o cabeçalho do módulo.
    - `apos_colisao()` desfaz o que a tentativa perdida deixou no objeto em memória (o pk
      atribuído pelo `INSERT` que falhou, tipicamente).

    Devolve o número gravado.
    """
    bloquear_escopo_numeracao(namespace=namespace, area_id=area_id, ano=ano, modelo=modelo)

    ultimo_erro: IntegrityError | None = None
    for _tentativa in range(tentativas):
        try:
            with transaction.atomic():
                # A política pode persistir estado ao escolher (o contador do Plano
                # de Trabalho). Escolha e gravação precisam do mesmo savepoint para
                # uma colisão não deixar o contador avançado sem documento.
                numero = escolher()
                gravar(numero)
            return numero
        except IntegrityError as exc:
            if not colisao_de_numero(
                exc, constraint=constraint, ja_ocupado=ja_ocupado, numero=numero
            ):
                # Não foi corrida por este número: a violação é outra e não é nossa.
                raise
            ultimo_erro = exc
            if apos_colisao is not None:
                apos_colisao()

    assert ultimo_erro is not None
    raise ultimo_erro
