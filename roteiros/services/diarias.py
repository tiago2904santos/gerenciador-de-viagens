from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from roteiros.services.valor_extenso import valor_por_extenso_ptbr


# Valores que estavam fixados aqui até a Etapa 3. Mantidos só como referência
# histórica e como último recurso quando não há vigência cadastrada (banco novo,
# teste que não roda migração). A fonte de verdade é cadastros.TabelaDiaria.
TABELA_DIARIAS_HISTORICA = {
    'INTERIOR': {
        '24h': Decimal('290.55'),
        '15': Decimal('43.58'),
        '30': Decimal('87.17'),
    },
    'CAPITAL': {
        '24h': Decimal('371.26'),
        '15': Decimal('55.69'),
        '30': Decimal('111.38'),
    },
    'BRASILIA': {
        '24h': Decimal('468.12'),
        '15': Decimal('70.22'),
        '30': Decimal('140.43'),
    },
}

# Rede de seguranca do N-06: a fonte de verdade e' a base geografica
# (``Cidade.capital``). Este mapa so entra quando a base nao tem a UF — banco
# recem-criado ou ambiente sem a importacao rodada. Um teste afirma que os dois
# concordam nas 27 UFs, para a duplicacao nao voltar a divergir em silencio.
CAPITAIS_POR_UF = {
    'AC': 'RIO BRANCO',
    'AL': 'MACEIO',
    'AP': 'MACAPA',
    'AM': 'MANAUS',
    'BA': 'SALVADOR',
    'CE': 'FORTALEZA',
    'DF': 'BRASILIA',
    'ES': 'VITORIA',
    'GO': 'GOIANIA',
    'MA': 'SAO LUIS',
    'MT': 'CUIABA',
    'MS': 'CAMPO GRANDE',
    'MG': 'BELO HORIZONTE',
    'PA': 'BELEM',
    'PB': 'JOAO PESSOA',
    'PR': 'CURITIBA',
    'PE': 'RECIFE',
    'PI': 'TERESINA',
    'RJ': 'RIO DE JANEIRO',
    'RN': 'NATAL',
    'RS': 'PORTO ALEGRE',
    'RO': 'PORTO VELHO',
    'RR': 'BOA VISTA',
    'SC': 'FLORIANOPOLIS',
    'SP': 'SAO PAULO',
    'SE': 'ARACAJU',
    'TO': 'PALMAS',
}

_CAPITAIS_DA_BASE: dict[str, str] | None = None


@dataclass(frozen=True)
class PeriodMarker:
    """Um destino do roteiro: quando se sai para ele e quando se chega nele.

    ``chegada`` é opcional porque nem todo chamador conhece as duas pontas. O
    plano de trabalho monta marcadores a partir de eventos, que têm data de
    início e não têm hora de chegada; nesse caso o único instante conhecido é
    tratado como a chegada ao destino. A regra é uma só — muda a informação
    disponível, não o critério.
    """

    saida: datetime
    destino_cidade: str
    destino_uf: str
    chegada: datetime | None = None

    @property
    def instante_de_chegada(self) -> datetime:
        return self.chegada or self.saida


def tabela_vigente_em(data_referencia) -> dict:
    """Valores por faixa vigentes na data, no formato usado pelo cálculo.

    Lê de ``cadastros.TabelaDiaria`` (defeito ``N-01``). O formato de retorno é
    idêntico ao da constante antiga — ``{faixa: {'24h', '15', '30'}}`` — para
    que os pontos de cálculo não mudem: menos diff, menos risco num motor que
    produz valor monetário.

    Sem vigência cadastrada para a data, cai na tabela histórica em vez de
    falhar. Um roteiro anterior à primeira vigência é situação de dados, não de
    código, e derrubar a calculadora deixaria o operador sem saída.
    """
    from cadastros.models import TabelaDiaria

    resultado = {}
    for faixa, _rotulo in TabelaDiaria.FAIXA_CHOICES:
        vigente = TabelaDiaria.vigente_em(faixa, data_referencia)
        if vigente is None:
            resultado[faixa] = TABELA_DIARIAS_HISTORICA[faixa]
            continue
        resultado[faixa] = {
            "24h": vigente.valor_24h,
            "15": vigente.valor_15,
            "30": vigente.valor_30,
        }
    return resultado


def _data_de_referencia(markers) -> "date":
    """Data que decide qual vigência vale: a saída mais antiga do roteiro."""
    return min(marker.saida for marker in markers).date()


def _normalize_city_name(value: str | None) -> str:
    raw = unicodedata.normalize('NFKD', (value or '').strip().upper())
    return ''.join(ch for ch in raw if not unicodedata.combining(ch))


def locations_equivalent(
    cidade_a: str | None,
    uf_a: str | None,
    cidade_b: str | None,
    uf_b: str | None,
) -> bool:
    return (
        _normalize_city_name(cidade_a) == _normalize_city_name(cidade_b)
        and (uf_a or '').strip().upper() == (uf_b or '').strip().upper()
    )


def formatar_valor_diarias(valor: Decimal) -> str:
    quantizado = valor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    bruto = f'{quantizado:,.2f}'
    return bruto.replace(',', '_').replace('.', ',').replace('_', '.')


def calcular_diarias_com_valor(qtd, valor_unitario, pessoas):
    qtd_decimal = Decimal(str(qtd or 0))
    valor_unitario_decimal = Decimal(str(valor_unitario or 0))
    pessoas_decimal = Decimal(str(pessoas or 0))

    total = qtd_decimal * valor_unitario_decimal * pessoas_decimal

    return {
        'quantidade_diarias': qtd_decimal,
        'valor_total': total,
        'valor_extenso': valor_por_extenso_ptbr(total),
    }


def _capitais_da_base() -> dict[str, str]:
    """Capitais por UF vindas da base geografica, memorizadas no processo.

    ``classify`` roda uma vez por marcador de roteiro; consultar o banco a cada
    chamada viraria N+1 no editor. Quem importar a base deve chamar
    ``limpar_cache_capitais()``.
    """
    global _CAPITAIS_DA_BASE
    if _CAPITAIS_DA_BASE is None:
        from cadastros.models import Cidade

        _CAPITAIS_DA_BASE = {
            (uf or '').strip().upper(): _normalize_city_name(nome)
            for nome, uf in Cidade.objects.filter(capital=True).values_list('nome', 'uf')
            if uf
        }
    return _CAPITAIS_DA_BASE


def limpar_cache_capitais() -> None:
    """Esquece as capitais memorizadas (usar apos importar a base geografica)."""
    global _CAPITAIS_DA_BASE
    _CAPITAIS_DA_BASE = None


def _capital_da_uf(uf_norm: str) -> str | None:
    """Nome normalizado da capital daquela UF (N-06).

    A base geografica manda; ``CAPITAIS_POR_UF`` so entra quando ela nao tem a
    UF. Sem esse fallback, um banco sem a base importada faria todo destino
    virar INTERIOR — que e' exatamente a cobranca a menor que o N-06 existe para
    evitar. A correcao introduziria o defeito.
    """
    da_base = _capitais_da_base().get(uf_norm)
    if da_base:
        return da_base
    return CAPITAIS_POR_UF.get(uf_norm)


def classify(cidade: str | None, uf: str | None) -> str:
    uf_norm = (uf or '').strip().upper()
    cidade_norm = _normalize_city_name(cidade)
    if uf_norm == 'DF' and cidade_norm == 'BRASILIA':
        return 'BRASILIA'
    if uf_norm and cidade_norm and _capital_da_uf(uf_norm) == cidade_norm:
        return 'CAPITAL'
    return 'INTERIOR'


def infer_tipo_destino_from_paradas(paradas: list[tuple[str | None, str | None]]) -> str:
    tipo_destino = 'INTERIOR'
    for cidade, uf in paradas:
        tipo = classify(cidade, uf)
        if tipo == 'BRASILIA':
            return tipo
        if tipo == 'CAPITAL':
            tipo_destino = tipo
    return tipo_destino


def _segment_breakdown(start: datetime, end: datetime) -> tuple[int, int, Decimal, Decimal]:
    total_seconds = (end - start).total_seconds()
    if total_seconds <= 0:
        raise ValueError('Periodo invalido para calculo de diarias.')

    total_horas = Decimal(str(total_seconds / 3600)).quantize(
        Decimal('0.01'),
        rounding=ROUND_HALF_UP,
    )
    dias_inteiros = int(total_seconds // (24 * 3600))
    resto_seconds = total_seconds - (dias_inteiros * 24 * 3600)

    # A escada do resto (N-08 / N-10), por DURACAO — o calendario nao entra.
    #
    # Confirmada por cinco demonstrativos do sistema oficial, um deles um
    # experimento que isola a variavel: 12h01 dentro do MESMO dia, sem virada de
    # meia-noite, rende 100% da diaria.
    #
    # Antes havia teto de 30% acima de 8h mais uma excecao que dava diaria
    # inteira a qualquer periodo que cruzasse a meia-noite. Errava nos dois
    # sentidos: pagava a menos em toda viagem acima de 12 horas (ate R$ 259,88
    # por trecho) e cobrava diaria cheia por dois minutos entre 23:59 e 00:01.
    # As duas definicoes de "diaria integral" que o N-08 aponta eram justamente
    # essa excecao convivendo com a contagem por duracao.
    if resto_seconds <= 6 * 3600:
        parcial = 0
    elif resto_seconds <= 8 * 3600:
        parcial = 15
    elif resto_seconds <= 12 * 3600:
        parcial = 30
    else:
        parcial = 100

    horas_adicionais = Decimal(str(resto_seconds / 3600)).quantize(
        Decimal('0.01'),
        rounding=ROUND_HALF_UP,
    )
    return dias_inteiros, parcial, horas_adicionais, total_horas


def _format_dt(value: datetime) -> tuple[str, str]:
    return value.strftime('%d/%m/%Y'), value.strftime('%H:%M')


def _total_diarias_resumo(periodos: list[dict]) -> str:
    # Resto acima de 12 horas vale uma diaria cheia, entao entra na contagem de
    # 100% e nao como percentual — senao o resumo diria "0 x 100%" para uma
    # viagem que paga uma diaria inteira.
    full = sum(int(item.get('n_diarias', 0) or 0) for item in periodos)
    full += sum(
        1 for item in periodos if int(item.get('percentual_adicional', 0) or 0) == 100
    )
    p15 = sum(1 for item in periodos if int(item.get('percentual_adicional', 0) or 0) == 15)
    p30 = sum(1 for item in periodos if int(item.get('percentual_adicional', 0) or 0) == 30)
    partes = []
    if full:
        partes.append(f'{full} x 100%')
    if p15:
        partes.append(f'{p15} x 15%')
    if p30:
        partes.append(f'{p30} x 30%')
    return ' + '.join(partes)


def build_periods(
    markers: list[PeriodMarker],
    chegada_final_sede: datetime,
    *,
    quantidade_servidores: int = 1,
    sede_cidade: str | None = None,
    sede_uf: str | None = None,
) -> list[dict]:
    if not markers or not chegada_final_sede:
        raise ValueError('Preencha datas e horas para calcular.')

    # Uma resolução por cálculo: a vigência é a mesma para o roteiro inteiro,
    # decidida pela saída mais antiga. Resolver por trecho abriria a porta para
    # um roteiro que atravessa a virada de vigência cobrar dois valores.
    tabela_por_faixa = tabela_vigente_em(_data_de_referencia(markers))

    sorted_markers = sorted(markers, key=lambda item: item.saida)
    periodos = []
    servidores = max(0, int(quantidade_servidores or 0))

    total_markers = len(sorted_markers)
    # Onde cada período começa e termina (NOVO-11). O período de um destino vai
    # da CHEGADA nele até a CHEGADA no destino seguinte — não de uma saída à
    # outra. O primeiro é a exceção: começa na saída da sede, porque a ida já é
    # faturada no destino para onde se vai.
    #
    # Isso faz o tempo de estrada entre dois destinos ser cobrado na tarifa de
    # onde o servidor estava. Com limites por saída ele caía no trecho de volta
    # à sede, que não carrega complemento, e sumia da conta: num roteiro
    # Curitiba→São Paulo→Abatiá→Curitiba, R$ 111,38 a menos que o sistema
    # oficial. Os dois demonstrativos que serviram de régua estão em
    # roteiros/tests/test_diarias_limites_periodo.py.
    for idx, marker in enumerate(sorted_markers):
        start = marker.saida if idx == 0 else marker.instante_de_chegada
        end = (
            sorted_markers[idx + 1].instante_de_chegada
            if idx + 1 < len(sorted_markers)
            else chegada_final_sede
        )
        if end < start:
            raise ValueError('Preencha datas e horas para calcular.')
        if end == start:
            # Parada instantanea: o trecho seguinte sai no mesmo instante em que este comecou
            # (chegar num destino e seguir viagem no mesmo dia/horario). Nao ha permanencia,
            # entao o periodo nao gera diaria — mas tambem nao invalida o roteiro.
            continue

        is_last_marker = idx == (total_markers - 1)
        if (
            not is_last_marker
            and sede_cidade
            and sede_uf
            and locations_equivalent(
            marker.destino_cidade,
            marker.destino_uf,
            sede_cidade,
            sede_uf,
            )
        ):
            continue

        tipo = classify(marker.destino_cidade, marker.destino_uf)
        # Aqui so se monta o esqueleto do periodo (N-08). Dinheiro e' contado
        # uma vez so, mais abaixo, depois que os periodos consecutivos do mesmo
        # grupo viram um trecho. Antes o breakdown era calculado duas vezes: uma
        # por periodo, cujo resultado era jogado fora sempre que houvesse fusao,
        # e outra por trecho.
        data_saida, hora_saida = _format_dt(start)
        periodos.append(
            {
                'tipo': tipo,
                'data_saida': data_saida,
                'hora_saida': hora_saida,
                'valor_diaria': formatar_valor_diarias(
                    tabela_por_faixa.get(tipo, tabela_por_faixa['INTERIOR'])['24h']
                ),
                '_period_start': start,
                '_period_end': end,
                '_retorno_final': is_last_marker,
                # "Ultimo marcador" nao e' o mesmo que "volta para casa": no
                # plano de trabalho o ultimo marcador e' um destino de verdade.
                # So e' retorno quando o destino e' a propria sede.
                '_retorno_sede': bool(
                    is_last_marker
                    and sede_cidade
                    and sede_uf
                    and locations_equivalent(
                        marker.destino_cidade, marker.destino_uf, sede_cidade, sede_uf
                    )
                ),
            }
        )

    if not periodos:
        raise ValueError('Preencha datas e horas para calcular.')

    # Um TRECHO TARIFARIO e a sequencia de periodos consecutivos do mesmo grupo
    # (N-05). O sistema oficial fatura por trecho, nao por destino: tres
    # capitais seguidas viram um trecho so, com um unico complemento sobre a
    # sobra; um interior no meio quebra a sequencia e abre trecho novo.
    #
    # Aqui existiam dois ramos — um complemento por permanencia e um complemento
    # por viagem — e o comentario de um condenava o que o outro fazia. Os dois
    # eram casos extremos desta regra: grupos alternando a cada destino, e um
    # grupo so no roteiro inteiro. Erravam no meio, que e o caso comum: dois
    # destinos seguidos do mesmo grupo num roteiro que mistura grupos nunca eram
    # fundidos. Em 10.800 roteiros realistas, 21% davam valor diferente do
    # oficial, para mais e para menos.
    #
    # Os tres demonstrativos oficiais que servem de regua estao em
    # roteiros/tests/test_diarias_limites_periodo.py.
    trechos = []
    for periodo in periodos:
        anterior = trechos[-1] if trechos else None
        if anterior is not None and anterior['_period_end'] == periodo['_period_start']:
            # A volta para a sede nunca abre trecho: ela prolonga o ultimo
            # destino. Do contrario o dia da volta seria faturado na tarifa da
            # propria sede — numa sede capital, cobrando capital por estar indo
            # para casa. Quando o roteiro traz hora de chegada por trecho este
            # periodo tem duracao zero e nem chega aqui; sem ela (plano de
            # trabalho), e este ramo que preserva o comportamento correto.
            if periodo['_retorno_sede']:
                anterior['_period_end'] = periodo['_period_end']
                continue
            # Mesmo grupo tarifario e encostados: um trecho so.
            if anterior['tipo'] == periodo['tipo']:
                anterior['_period_end'] = periodo['_period_end']
                continue
        trechos.append(periodo)

    for trecho in trechos:
        start, end = trecho['_period_start'], trecho['_period_end']
        dias_inteiros, parcial, horas_adicionais, total_horas = _segment_breakdown(start, end)
        tabela = tabela_por_faixa.get(trecho['tipo'], tabela_por_faixa['INTERIOR'])
        valor_parcial = Decimal('0.00')
        if parcial == 15:
            valor_parcial = tabela['15']
        elif parcial == 30:
            valor_parcial = tabela['30']
        elif parcial == 100:
            # Resto acima de 12 horas vale uma diaria cheia. No demonstrativo
            # oficial ela aparece decomposta em hospedagem 70% + alimentacao
            # 30%; somar o valor de 24h direto da o mesmo numero e evita
            # arredondar duas vezes. (Se um dia o documento precisar das duas
            # colunas: alimentacao e' 30% arredondado e hospedagem e' o que
            # sobra da diaria, nao 70% arredondado.)
            valor_parcial = tabela['24h']
        subtotal = ((tabela['24h'] * dias_inteiros) + valor_parcial) * servidores
        data_chegada, hora_chegada = _format_dt(end)
        trecho['data_chegada'] = data_chegada
        trecho['hora_chegada'] = hora_chegada
        trecho['n_diarias'] = dias_inteiros
        trecho['horas_adicionais'] = float(horas_adicionais)
        trecho['percentual_adicional'] = parcial
        trecho['total_horas_periodo'] = float(total_horas)
        trecho['subtotal'] = formatar_valor_diarias(subtotal)
        trecho['subtotal_decimal'] = subtotal

    for trecho in trechos:
        trecho.pop('_period_start', None)
        trecho.pop('_period_end', None)
        trecho.pop('_pernoites_periodo', None)
        trecho.pop('_parcial_periodo', None)
        trecho.pop('_retorno_final', None)
        trecho.pop('_retorno_sede', None)

    return trechos


def calculate_periodized_diarias(
    markers: list[PeriodMarker],
    chegada_final_sede: datetime,
    *,
    quantidade_servidores: int = 1,
    sede_cidade: str | None = None,
    sede_uf: str | None = None,
) -> dict:
    periodos = build_periods(
        markers,
        chegada_final_sede,
        quantidade_servidores=quantidade_servidores,
        sede_cidade=sede_cidade,
        sede_uf=sede_uf,
    )
    total_valor_decimal = sum(
        (item['subtotal_decimal'] for item in periodos),
        Decimal('0.00'),
    )
    total_horas = sum(float(item.get('total_horas_periodo', 0) or 0) for item in periodos)
    resumo_diarias = _total_diarias_resumo(periodos)
    servidores = max(0, int(quantidade_servidores or 0))
    if servidores <= 0:
        valor_por_servidor = Decimal('0.00')
    else:
        valor_por_servidor = (
            total_valor_decimal / Decimal(servidores)
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    valores_unitarios = [str(item.get('valor_diaria', '') or '').strip() for item in periodos]
    valores_unitarios = [item for item in valores_unitarios if item]
    if len(set(valores_unitarios)) == 1:
        valor_unitario_referencia = valores_unitarios[0]
    elif valores_unitarios:
        valor_unitario_referencia = f'{valores_unitarios[0]} (variavel por periodo)'
    else:
        valor_unitario_referencia = ''

    periodos_out = []
    for item in periodos:
        row = dict(item)
        row.pop('subtotal_decimal', None)
        row.pop('total_horas_periodo', None)
        periodos_out.append(row)

    return {
        'periodos': periodos_out,
        'totais': {
            'total_diarias': resumo_diarias,
            'total_horas': round(total_horas, 2),
            'total_valor': formatar_valor_diarias(total_valor_decimal),
            'total_valor_decimal': total_valor_decimal,
            'valor_extenso': valor_por_extenso_ptbr(total_valor_decimal),
            'quantidade_servidores': servidores,
            'diarias_por_servidor': resumo_diarias,
            'valor_por_servidor': formatar_valor_diarias(valor_por_servidor),
            'valor_por_servidor_decimal': valor_por_servidor,
            'valor_unitario_referencia': valor_unitario_referencia,
        },
    }
