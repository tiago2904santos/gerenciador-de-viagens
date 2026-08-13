"""`BE-13` fatia 3 — a persistência do editor de roteiro.

Estas funções vieram de `roteiros/services/editor_state_builder.py`, onde eram privadas e conviviam com
parsing de request e montagem de contexto. Gravar é trabalho de service
(`docs/PADRAO_APP.md:8`), e é só isso que elas fazem.

Nomes públicos, como nos módulos irmãos (`editor_parser`, `editor_context`,
`map_defaults`): o enunciado do `BE-13` reclama de "57 definições de topo **todas
privadas**", e um service cujas funções de entrada começam com `_` não fecha essa parte.

`salvar_roteiro_avulso_from_roteiro_state` é `@transaction.atomic` porque grava três
tabelas — `Roteiro`, `RoteiroDestino` e `RoteiroTrecho` — e o caminho do autosave não abre
transação nenhuma. A prova está em
`core/tests/test_colecoes_ordenadas_db08.py::test_falha_entre_os_dois_passos_nao_deixa_posicao_no_bloco`.

**Contrato de entrada (`NOVO-98`).** O service recebe estado já normalizado pelo parser:
adicional não negativo, duração do retorno derivada e volta duplicada removida. Essas
regras moram exclusivamente em `_build_roteiro_state_from_post` e
`dedupe_roteiro_loop_retorno_final`; o gravador não mantém uma segunda implementação.
"""

from datetime import datetime

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from roteiros.models import RoteiroDestino
from roteiros.models import RoteiroDiariaComponente
from roteiros.models import RoteiroTrecho
from roteiros.services.editor_parser import parse_int
from roteiros.services.editor_parser import parse_roteiro_decimal


#: `DB-08` fatia 2: bloco livre para onde as posições vão no primeiro passo.
#: Precisa ficar acima de qualquer posição final — e as finais são
#: `0..len(trechos_validated)`, uma por trecho do payload do editor. Um milhão dá
#: folga de sobra e cabe com margem no `PositiveIntegerField` (máx. 2.147.483.647).
DESLOCAMENTO_ORDEM_TRECHO = 1_000_000


def atualizar_datas_roteiro_apos_salvar_trechos(roteiro):
    """Deriva o cabeçalho de datas do roteiro a partir dos trechos (`NOVO-36`).

    A regra era POSICIONAL: `trechos[0].saida_dt` para a saída e
    `trechos[-2].chegada_dt` para a chegada da ida. Isso vale enquanto a posição
    coincide com a cronologia — e ela deixa de coincidir na REORDENAÇÃO de
    destinos, que preserva o horário de cada trecho e troca a ordem deles. Com
    dois trechos de ida (01/05 e 02/05) invertidos, gravava saída=02/05 e
    chegada=01/05: chegada 23 h ANTES da saída. Achado pela constraint
    `roteiro_ida_ordenada` do `DB-07`, que por causa disto ficou adiada.

    Agora é CRONOLÓGICA, que é a regra que o resto do sistema já usa: o motor de
    diárias ordena marcadores por `saida` (`services/diarias.py:299`) e escolhe a
    vigência por `min(saida)` (`:116-118`); `prestacoes_contas/services.py:89`
    resolve o fim por `order_by('-chegada_dt')` sobre os trechos. A derivação
    posicional era a anomalia. Em roteiro cronologicamente bem formado as duas
    dão o MESMO valor — elas só divergem onde a antiga produzia chegada < saída.

    Três decisões que parecem detalhe e não são:

    1. `chegada_dt` sai EXCLUSIVAMENTE das idas. Cair para o máximo sobre todos
       os trechos pegaria `retorno.chegada_dt`, que por construção vem depois de
       `retorno_saida_dt` — e gravaria violação determinística de
       `roteiro_permanencia_ordenada`, constraint JÁ em produção. Trocaria dado
       errado por HTTP 500 num caminho que hoje devolve 200.
    2. O ramo sem retorno também muda. A versão antiga usava `trechos[-1]` ali, e
       uma correção que mexesse só no ramo com retorno deixaria o roteiro
       reordenado SEM volta ainda invertido.
    3. Continua só ATRIBUINDO quando a fonte existe, sem limpar. Escrever `None`
       cegamente apagaria `retorno_*` de rascunho cujo trecho de retorno existe
       mas ainda está sem datas — regressão de outra natureza, fora deste ID.
    """
    trechos_salvos = list(roteiro.trechos.order_by('ordem'))
    if not trechos_salvos:
        return

    idas = [t for t in trechos_salvos if t.tipo != RoteiroTrecho.TIPO_RETORNO]
    retornos = [t for t in trechos_salvos if t.tipo == RoteiroTrecho.TIPO_RETORNO]
    retorno = retornos[-1] if retornos else None

    update_fields = []

    saidas_da_ida = [t.saida_dt for t in idas if t.saida_dt is not None]
    # Sem nenhuma ida com saída, a viagem começa no próprio retorno. É o estado
    # que o autosave fabrica quando o usuário remove a última linha de destino:
    # `salvar_roteiro_avulso_from_roteiro_state` cria o trecho de retorno
    # incondicionalmente e apaga os demais.
    primeira_saida = min(saidas_da_ida) if saidas_da_ida else (
        retorno.saida_dt if retorno else None
    )
    if primeira_saida is not None:
        roteiro.saida_dt = primeira_saida
        update_fields.append('saida_dt')

    chegadas_da_ida = [t.chegada_dt for t in idas if t.chegada_dt is not None]
    if chegadas_da_ida:
        roteiro.chegada_dt = max(chegadas_da_ida)
        update_fields.append('chegada_dt')

    if retorno is not None:
        if retorno.saida_dt is not None:
            roteiro.retorno_saida_dt = retorno.saida_dt
            update_fields.append('retorno_saida_dt')
        if retorno.chegada_dt is not None:
            roteiro.retorno_chegada_dt = retorno.chegada_dt
            update_fields.append('retorno_chegada_dt')

    if update_fields:
        update_fields.append('status')
        roteiro.save(update_fields=update_fields)

def roteiro_combine_date_time(data_value, hora_value):
    if not data_value or not hora_value:
        return None
    return datetime.combine(data_value, hora_value)


def _datetime_para_banco(value):
    if value is not None and timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


@transaction.atomic
def persistir_diarias_roteiro(roteiro, diarias_resultado):
    if not diarias_resultado:
        return
    roteiro.aplicar_diarias_calculadas(diarias_resultado)
    roteiro.save(update_fields=['quantidade_diarias', 'valor_diarias', 'valor_diarias_extenso'])
    roteiro.componentes_diarias.all().delete()
    RoteiroDiariaComponente.objects.bulk_create([
        RoteiroDiariaComponente(
            roteiro=roteiro,
            ordem=ordem,
            origem=RoteiroDiariaComponente.ORIGEM_CALCULO,
            **{
                **componente,
                'periodo_inicio': _datetime_para_banco(componente.get('periodo_inicio')),
                'periodo_fim': _datetime_para_banco(componente.get('periodo_fim')),
            },
        )
        for ordem, componente in enumerate(getattr(diarias_resultado, 'componentes', []))
    ])

@transaction.atomic
def salvar_roteiro_avulso_from_roteiro_state(roteiro, roteiro_state, validated, diarias_resultado=None):
    """Persiste o editor preservando trechos existentes por id e retorno em bloco proprio.

    `roteiro_state` e `validated` são saídas normalizadas do parser; chamadores não devem
    construir esses dicionários como entrada bruta (`NOVO-98`).

    `DB-08` fatia 2: atômica de ponta a ponta. Dois dos quatro caminhos que chegam
    aqui já vinham dentro de transação (`criar_roteiro` e `atualizar_roteiro` em
    `roteiros/services/roteiro_editor.py`) — nesses o `atomic` é só um savepoint
    aninhado. O caminho do autosave (`roteiros/services/autosave.py`, que não tem
    `atomic` nenhum) é que precisava: sem transação, uma falha no meio deixa as
    posições estacionadas no bloco de deslocamento, e antes disso já deixava o
    roteiro **sem destino nenhum**, porque o `delete()` da linha abaixo é
    irreversível fora de transação.
    """
    destinos_post = []
    for item in (roteiro_state.get('destinos_atuais') or []):
        estado_id = parse_int(item.get('estado_id'))
        cidade_id = parse_int(item.get('cidade_id'))
        if estado_id and cidade_id:
            destinos_post.append((estado_id, cidade_id))

    roteiro.destinos.all().delete()
    for ordem, (estado_id, cidade_id) in enumerate(destinos_post):
        RoteiroDestino.objects.create(
            roteiro=roteiro,
            estado_id=estado_id,
            cidade_id=cidade_id,
            ordem=ordem,
        )

    retorno_state = roteiro_state.get('retorno') or {}
    trechos_validated = list(validated.get('trechos') or [])
    # `DB-08` fatia 2, **primeiro passo**. As posições finais são gravadas uma a
    # uma no laço abaixo, e o escritor reaproveita as linhas por `id`: trocar dois
    # trechos de lugar, ou encolher o roteiro e reposicionar o retorno, colide com
    # uma linha que ainda não foi reposicionada nem apagada. Este `UPDATE` único
    # empurra todas para um bloco que nenhuma posição final alcança; o laço as traz
    # de volta já no lugar certo, e o `delete()` do fim leva as que sobraram.
    #
    # `deferrable=DEFERRED` resolveria isso no banco e **não serve**:
    # `supports_deferrable_unique_constraints` é `False` no SQLite, e a suíte roda
    # nos dois bancos — a proteção existiria só no PostgreSQL.
    roteiro.trechos.update(ordem=F('ordem') + DESLOCAMENTO_ORDEM_TRECHO)
    trechos_existentes = {
        trecho.pk: trecho
        for trecho in roteiro.trechos.all()
    }
    trechos_mantidos = set()
    for ordem, trecho in enumerate(trechos_validated):
        # Reordenacao muda a ordem e as pontas do trecho, mas nao deve limpar campos manuais
        # quando o payload omite valores que ja existem no banco.
        tempo_adicional = trecho.get('tempo_adicional_min') or 0
        tempo_cru = trecho.get('tempo_cru_estimado_min')
        duracao_estimada = trecho.get('duracao_estimada_min')
        if duracao_estimada is None and ((tempo_cru or 0) + tempo_adicional) > 0:
            duracao_estimada = (tempo_cru or 0) + tempo_adicional
        distancia = parse_roteiro_decimal(trecho.get('distancia_km'))
        trecho_id = parse_int(trecho.get('id'))
        trecho_obj = trechos_existentes.get(trecho_id) if trecho_id else None
        if trecho_obj is None:
            trecho_obj = RoteiroTrecho(roteiro=roteiro)
        trecho_obj.ordem = ordem
        trecho_obj.tipo = RoteiroTrecho.TIPO_IDA
        trecho_obj.origem_estado_id = trecho.get('origem_estado_id') or trecho_obj.origem_estado_id
        trecho_obj.origem_cidade_id = trecho.get('origem_cidade_id') or trecho_obj.origem_cidade_id
        trecho_obj.destino_estado_id = trecho.get('destino_estado_id') or trecho_obj.destino_estado_id
        trecho_obj.destino_cidade_id = trecho.get('destino_cidade_id') or trecho_obj.destino_cidade_id
        trecho_obj.saida_dt = roteiro_combine_date_time(trecho.get('saida_data'), trecho.get('saida_hora')) or trecho_obj.saida_dt
        trecho_obj.chegada_dt = roteiro_combine_date_time(trecho.get('chegada_data'), trecho.get('chegada_hora')) or trecho_obj.chegada_dt
        if distancia is not None:
            trecho_obj.distancia_km = distancia
        if duracao_estimada is not None:
            trecho_obj.duracao_estimada_min = duracao_estimada
        if tempo_cru is not None:
            trecho_obj.tempo_cru_estimado_min = tempo_cru
        if trecho.get('tempo_adicional_min') is not None:
            trecho_obj.tempo_adicional_min = tempo_adicional
        if 'rota_fonte' in trecho:
            trecho_obj.rota_fonte = (trecho.get('rota_fonte') or '').strip()
        if distancia is not None or tempo_cru is not None:
            trecho_obj.rota_calculada_em = timezone.now()
        trecho_obj.save()
        trechos_mantidos.add(trecho_obj.pk)

    retorno_tempo_cru = parse_int(retorno_state.get('tempo_cru_estimado_min'))
    retorno_tempo_adicional = parse_int(retorno_state.get('tempo_adicional_min')) or 0
    retorno_duracao = parse_int(retorno_state.get('duracao_estimada_min'))

    ultimo_trecho = trechos_validated[-1] if trechos_validated else None
    origem_retorno_estado_id = (ultimo_trecho or {}).get('destino_estado_id') or roteiro.origem_estado_id
    origem_retorno_cidade_id = (ultimo_trecho or {}).get('destino_cidade_id') or roteiro.origem_cidade_id
    distancia_retorno = parse_roteiro_decimal(retorno_state.get('distancia_km'))

    retorno_obj = (
        roteiro.trechos.filter(tipo=RoteiroTrecho.TIPO_RETORNO).order_by('ordem', 'id').first()
    )
    if retorno_obj is None:
        retorno_obj = RoteiroTrecho(roteiro=roteiro, tipo=RoteiroTrecho.TIPO_RETORNO)
    retorno_obj.ordem = len(trechos_validated)
    retorno_obj.tipo = RoteiroTrecho.TIPO_RETORNO
    retorno_obj.origem_estado_id = origem_retorno_estado_id
    retorno_obj.origem_cidade_id = origem_retorno_cidade_id
    retorno_obj.destino_estado_id = roteiro.origem_estado_id
    retorno_obj.destino_cidade_id = roteiro.origem_cidade_id
    retorno_obj.saida_dt = roteiro_combine_date_time(validated.get('retorno_saida_data'), validated.get('retorno_saida_hora')) or retorno_obj.saida_dt
    retorno_obj.chegada_dt = roteiro_combine_date_time(validated.get('retorno_chegada_data'), validated.get('retorno_chegada_hora')) or retorno_obj.chegada_dt
    if distancia_retorno is not None:
        retorno_obj.distancia_km = distancia_retorno
    if retorno_duracao is not None:
        retorno_obj.duracao_estimada_min = retorno_duracao
    if retorno_tempo_cru is not None:
        retorno_obj.tempo_cru_estimado_min = retorno_tempo_cru
    if retorno_state.get('tempo_adicional_min') is not None:
        retorno_obj.tempo_adicional_min = retorno_tempo_adicional
    if 'rota_fonte' in retorno_state:
        retorno_obj.rota_fonte = (retorno_state.get('rota_fonte') or '').strip()
    if distancia_retorno is not None or retorno_tempo_cru is not None:
        retorno_obj.rota_calculada_em = timezone.now()
    retorno_obj.save()
    trechos_mantidos.add(retorno_obj.pk)
    roteiro.trechos.exclude(pk__in=trechos_mantidos).delete()

    atualizar_datas_roteiro_apos_salvar_trechos(roteiro)
    persistir_diarias_roteiro(roteiro, diarias_resultado)

    from roteiros.services.routing.route_stale import mark_stale_when_signature_changed

    mark_stale_when_signature_changed(roteiro)
