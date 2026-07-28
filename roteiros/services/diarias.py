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


@dataclass(frozen=True)
class PeriodMarker:
    saida: datetime
    destino_cidade: str
    destino_uf: str


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


def classify(cidade: str | None, uf: str | None) -> str:
    uf_norm = (uf or '').strip().upper()
    cidade_norm = _normalize_city_name(cidade)
    if uf_norm == 'DF' and cidade_norm == 'BRASILIA':
        return 'BRASILIA'
    if uf_norm and cidade_norm and CAPITAIS_POR_UF.get(uf_norm) == cidade_norm:
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


def count_pernoites(saida: datetime, chegada: datetime) -> int:
    """
    Número de pernoites (noites dormidas) fora da sede entre saida e chegada.
    Regra: cada noite entre saida.date() e chegada.date() conta como 1 pernoite.
    Ex.: saida 15/03 14:00, chegada 18/03 11:30 → 3 pernoites (noites 15→16, 16→17, 17→18).
    """
    if chegada.date() <= saida.date():
        return 0
    return (chegada.date() - saida.date()).days


def _count_period_pernoites(periodos: list[dict]) -> int:
    return sum(int(item.get('_pernoites_periodo', 0) or 0) for item in periodos)


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

    parcial = 0
    if start.date() != end.date() and total_seconds < 24 * 3600:
        dias_inteiros = 1
        resto_seconds = 0
    else:
        if resto_seconds <= 6 * 3600:
            parcial = 0
        elif resto_seconds <= 8 * 3600:
            parcial = 15
        else:
            parcial = 30

    horas_adicionais = Decimal(str(resto_seconds / 3600)).quantize(
        Decimal('0.01'),
        rounding=ROUND_HALF_UP,
    )
    return dias_inteiros, parcial, horas_adicionais, total_horas


def _format_dt(value: datetime) -> tuple[str, str]:
    return value.strftime('%d/%m/%Y'), value.strftime('%H:%M')


def _total_diarias_resumo(periodos: list[dict]) -> str:
    full = sum(int(item.get('n_diarias', 0) or 0) for item in periodos)
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
    for idx, marker in enumerate(sorted_markers):
        start = marker.saida
        end = sorted_markers[idx + 1].saida if idx + 1 < len(sorted_markers) else chegada_final_sede
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
        dias_inteiros, parcial, horas_adicionais, total_horas = _segment_breakdown(start, end)
        tabela = tabela_por_faixa.get(tipo, tabela_por_faixa['INTERIOR'])
        valor_24h = tabela['24h']
        valor_parcial = Decimal('0.00')
        if parcial == 15:
            valor_parcial = tabela['15']
        elif parcial == 30:
            valor_parcial = tabela['30']

        valor_1_servidor = (valor_24h * dias_inteiros) + valor_parcial
        subtotal = valor_1_servidor * servidores
        data_saida, hora_saida = _format_dt(start)
        data_chegada, hora_chegada = _format_dt(end)
        periodos.append(
            {
                'tipo': tipo,
                'data_saida': data_saida,
                'hora_saida': hora_saida,
                'data_chegada': data_chegada,
                'hora_chegada': hora_chegada,
                'n_diarias': dias_inteiros,
                'horas_adicionais': float(horas_adicionais),
                'valor_diaria': formatar_valor_diarias(valor_24h),
                'subtotal': formatar_valor_diarias(subtotal),
                'subtotal_decimal': subtotal,
                'percentual_adicional': parcial,
                'total_horas_periodo': float(total_horas),
                '_period_start': start,
                '_period_end': end,
                '_pernoites_periodo': count_pernoites(start, end),
                '_parcial_periodo': parcial,
                '_retorno_final': is_last_marker,
            }
        )

    if not periodos:
        raise ValueError('Preencha datas e horas para calcular.')

    # O último período é o deslocamento de volta para a sede. Ele nunca carrega o
    # complemento: o servidor está indo para casa e não pode herdar a tarifa da sede
    # (numa sede capital isso cobraria o dia da volta como capital).
    periodos_permanencia = [item for item in periodos if not item['_retorno_final']]
    tipos_permanencia = {item['tipo'] for item in periodos_permanencia}

    if len(tipos_permanencia) > 1:
        # Roteiro que mistura categorias (interior/capital/Brasília): cada permanência é
        # faturada na tarifa da sua cidade e com o próprio complemento. Um complemento
        # único da viagem teria de escolher arbitrariamente uma das tarifas.
        for item in periodos:
            n_in_period = int(item.get('_pernoites_periodo', 0) or 0)
            parcial_periodo = (
                0 if item['_retorno_final'] else int(item.get('_parcial_periodo', 0) or 0)
            )
            tabela = tabela_por_faixa.get(item['tipo'], tabela_por_faixa['INTERIOR'])
            valor_parcial = Decimal('0.00')
            if parcial_periodo == 15:
                valor_parcial = tabela['15']
            elif parcial_periodo == 30:
                valor_parcial = tabela['30']
            item['n_diarias'] = n_in_period
            item['percentual_adicional'] = parcial_periodo
            subtotal_novo = ((tabela['24h'] * n_in_period) + valor_parcial) * servidores
            item['subtotal'] = formatar_valor_diarias(subtotal_novo)
            item['subtotal_decimal'] = subtotal_novo

        for item in periodos:
            item.pop('_period_start', None)
            item.pop('_period_end', None)
            item.pop('_pernoites_periodo', None)
            item.pop('_parcial_periodo', None)
            item.pop('_retorno_final', None)

        return periodos

    # Regra da viagem única (saída da sede → retorno à sede):
    # a diária NÃO é a soma de trechos independentes. As diárias integrais são
    # as noites fora da sede (pernoites) e há, no máximo, UM percentual
    # complementar (15%/30%) sobre o tempo que sobra além das noites inteiras.
    # Nunca um complemento por trecho — do contrário a mesma viagem acumularia
    # 15% de um trecho + 30% de outro, inflando o total. (Vale para o roteiro que
    # permanece numa única categoria; misturando categorias, o bloco acima já
    # faturou cada permanência na sua própria tarifa.)
    total_pernoites = _count_period_pernoites(periodos)
    trip_start = periodos[0]['_period_start']
    trip_end = periodos[-1]['_period_end']

    if total_pernoites > 0:
        # Percentual complementar único, medido sobre a viagem inteira: o tempo
        # que excede as noites inteiras (pode ser negativo quando o retorno se dá
        # antes de completar o último bloco de 24h → sem complemento).
        leftover_seconds = (trip_end - trip_start).total_seconds() - (total_pernoites * 24 * 3600)
        leftover_percentual = 0
        if leftover_seconds > 6 * 3600:
            leftover_percentual = 15 if leftover_seconds <= 8 * 3600 else 30

        for p in periodos:
            # Cada noite é faturada na categoria da cidade onde foi dormida.
            n_in_period = int(p.get('_pernoites_periodo', 0) or 0)
            p['n_diarias'] = n_in_period
            p['percentual_adicional'] = 0
            tabela = tabela_por_faixa.get(p['tipo'], tabela_por_faixa['INTERIOR'])
            valor_1_servidor = tabela['24h'] * n_in_period
            subtotal_novo = valor_1_servidor * servidores
            p['subtotal'] = formatar_valor_diarias(subtotal_novo)
            p['subtotal_decimal'] = subtotal_novo

        if leftover_percentual:
            # Atribui a fração ao último período com pernoite real (o trecho
            # puramente de retorno à sede, sem pernoite, não deve "herdar" a
            # tarifa da sede para o dia da volta).
            alvo = next(
                (p for p in reversed(periodos) if p['n_diarias'] > 0 and not p['_retorno_final']),
                (periodos_permanencia or periodos)[-1],
            )
            tabela = tabela_por_faixa.get(alvo['tipo'], tabela_por_faixa['INTERIOR'])
            valor_parcial = tabela['15'] if leftover_percentual == 15 else tabela['30']
            alvo['percentual_adicional'] = leftover_percentual
            valor_1_servidor = (tabela['24h'] * alvo['n_diarias']) + valor_parcial
            subtotal_novo = valor_1_servidor * servidores
            alvo['subtotal'] = formatar_valor_diarias(subtotal_novo)
            alvo['subtotal_decimal'] = subtotal_novo
    else:
        # Viagem sem pernoite: também é uma única viagem. Aplica no máximo um
        # complemento, sobre a duração total, no destino mais oneroso — em vez
        # de somar uma fração por trecho. O período de volta à sede fica de fora
        # da escolha para não cobrar o dia da volta na tarifa da própria sede.
        leftover_seconds = (trip_end - trip_start).total_seconds()
        leftover_percentual = 0
        if leftover_seconds > 6 * 3600:
            leftover_percentual = 15 if leftover_seconds <= 8 * 3600 else 30

        for p in periodos:
            p['n_diarias'] = 0
            p['percentual_adicional'] = 0
            p['subtotal'] = formatar_valor_diarias(Decimal('0.00'))
            p['subtotal_decimal'] = Decimal('0.00')

        if leftover_percentual:
            ordem_tipo = {'INTERIOR': 0, 'CAPITAL': 1, 'BRASILIA': 2}
            alvo = max(periodos_permanencia or periodos, key=lambda p: ordem_tipo.get(p['tipo'], 0))
            tabela = tabela_por_faixa.get(alvo['tipo'], tabela_por_faixa['INTERIOR'])
            valor_parcial = tabela['15'] if leftover_percentual == 15 else tabela['30']
            alvo['percentual_adicional'] = leftover_percentual
            subtotal_novo = valor_parcial * servidores
            alvo['subtotal'] = formatar_valor_diarias(subtotal_novo)
            alvo['subtotal_decimal'] = subtotal_novo

    for p in periodos:
        p.pop('_period_start', None)
        p.pop('_period_end', None)
        p.pop('_pernoites_periodo', None)
        p.pop('_parcial_periodo', None)
        p.pop('_retorno_final', None)

    return periodos


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
