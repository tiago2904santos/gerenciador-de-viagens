"""Regras de negócio do Plano de Trabalho: textos padrão, diárias e geração documental."""

from __future__ import annotations

import logging
from datetime import date
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from cadastros.models import ConfiguracaoSistema
from core.numeracao import NAMESPACE_PLANO_TRABALHO
from core.numeracao import reservar_numero
from core.tenancy import filter_queryset_by_area
from core.tenancy import get_current_area
from documentos.services.facade import build_default_facade
from documentos.services.document_cache import build_document_cache_key
from documentos.services.document_cache import build_template_cache_signature
from documentos.services.document_cache import documento_gerado_from_artifact
from documentos.services.document_cache import get_cached_document_artifact
from documentos.services.formatters import format_city_uf
from documentos.services.formatters import format_document_display
from documentos.services.pdf_engine import resolve_pdf_engine
from documentos.services.responses import build_download_response
from documentos.services.timing import measure_step
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo
from roteiros.services.diarias import PeriodMarker
from roteiros.services.diarias import calculate_periodized_diarias
from roteiros.services.diarias import formatar_valor_diarias
from roteiros.services.valor_extenso import valor_por_extenso_ptbr

from .models import AtividadePlanoTrabalho
from .models import EventoPlano
from .models import PlanoTrabalho

logger = logging.getLogger(__name__)

CONSTRAINT_NUMERO_PLANO_TRABALHO = "planos_trabalho_area_ano_numero_unique"

_MESES_PT = (
    "", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)

TEXTO_PADRAO_CONTEXTUALIZACAO = (
    "A Assessoria de Comunicação Social da Polícia Civil do Paraná (PCPR), no âmbito do "
    'programa "PCPR na Comunidade", promoverá ação itinerante no município de {municipio}.\n\n'
    "A iniciativa visa atender à solicitação formulada pelo {programa} (Ofício em anexo), "
    "levando serviços essenciais de polícia judiciária às populações urbanas, rurais e "
    "ribeirinhas, especialmente em localidades de difícil acesso.\n\n"
    "A ação tem como foco principal garantir o acesso à documentação básica e prestar "
    "orientações de polícia judiciária, promovendo cidadania e fortalecendo a aproximação "
    "institucional com a comunidade."
)

TEXTO_PADRAO_CONSIDERACAO_FINAL = (
    "A realização da ação no município de {municipio} reforça o compromisso institucional "
    "da Polícia Civil do Paraná com a promoção da cidadania e com a ampliação do acesso a "
    "serviços públicos essenciais, especialmente em regiões com limitações de deslocamento "
    "e maior vulnerabilidade social."
)

TEXTO_COORDENADOR_ADM = (
    "Fica {designado} como {coordenador_administrativo} do Plano {artigo} {cargo_nome}, "
    "{artigo} qual ficará responsável pelo acompanhamento da execução administrativa do presente "
    "Plano de Trabalho, organização das escalas de servidores, controle de materiais e "
    "equipamentos, consolidação de dados estatísticos, elaboração de relatório final e demais "
    "providências necessárias ao regular cumprimento da ação."
)

TEXTO_COORDENADOR_OP = (
    "Fica {designado} como {coordenador_operacional} {artigo} {cargo_nome}, "
    "{artigo} qual ficará responsável pela execução operacional da ação no local do evento, "
    "acompanhamento das equipes e suporte às demandas surgidas durante o atendimento."
)


# ── Textos padrão ────────────────────────────────────────────────────────────


_MUNICIPIO_PLACEHOLDER = "________"


def _municipio_display(plano: PlanoTrabalho) -> str:
    labels: list[str] = []
    if plano.pk:
        for destino in plano.destinos.select_related("cidade").order_by("ordem", "pk"):
            if destino.cidade_id:
                labels.append(format_city_uf(f"{destino.cidade.nome}/{destino.cidade.uf}"))
    if not labels and plano.destino_cidade_id:
        labels.append(format_city_uf(f"{plano.destino_cidade.nome}/{plano.destino_cidade.uf}"))
    vistos: list[str] = []
    for label in labels:
        if label and label not in vistos:
            vistos.append(label)
    return ", ".join(vistos) if vistos else _MUNICIPIO_PLACEHOLDER


def _programa_display(plano: PlanoTrabalho) -> str:
    if plano.is_multi_evento and plano.pk:
        nomes: list[str] = []
        for evento in plano.eventos_ordenados:
            texto = evento.programa_display
            if texto:
                nomes.append(format_document_display(texto))
        nomes = list(dict.fromkeys(nomes))
        if nomes:
            return ", ".join(nomes)
        return "________"
    texto = plano.programa_display
    if not texto:
        return "________"
    return format_document_display(texto)


def texto_padrao_contextualizacao(plano: PlanoTrabalho) -> str:
    return TEXTO_PADRAO_CONTEXTUALIZACAO.format(
        municipio=_municipio_display(plano),
        programa=_programa_display(plano),
    )


def texto_padrao_consideracao_final(plano: PlanoTrabalho) -> str:
    return TEXTO_PADRAO_CONSIDERACAO_FINAL.format(municipio=_municipio_display(plano))


def texto_padrao_coordenacao(plano: PlanoTrabalho) -> str:
    return montar_texto_coordenacao(plano)


def textos_padrao_templates() -> dict[str, str]:
    """Modelos brutos (com tokens {municipio}/{programa}) para a pré-visualização no cliente."""
    return {
        "contextualizacao": TEXTO_PADRAO_CONTEXTUALIZACAO,
        "coordenacao_adm": TEXTO_COORDENADOR_ADM,
        "coordenacao_op": TEXTO_COORDENADOR_OP,
        "consideracao_final": TEXTO_PADRAO_CONSIDERACAO_FINAL,
    }


def sincronizar_textos_padrao(plano: PlanoTrabalho) -> list[str]:
    """Regenera os textos cujo flag `*_auto` está ativo (sem tocar nos editados à mão).

    Retorna a lista de campos alterados, para uso em ``save(update_fields=...)``.
    """
    alterados: list[str] = []
    if plano.contextualizacao_auto:
        plano.contextualizacao = texto_padrao_contextualizacao(plano)
        alterados.append("contextualizacao")
    if plano.coordenacao_auto:
        plano.coordenacao = texto_padrao_coordenacao(plano)
        alterados.append("coordenacao")
    if plano.consideracao_auto:
        plano.consideracao_final = texto_padrao_consideracao_final(plano)
        alterados.append("consideracao_final")
    return alterados


def aplicar_textos_padrao(plano: PlanoTrabalho) -> list[str]:
    """Preenche contextualização/considerações quando vazias. Retorna campos alterados.

    Mantida por compatibilidade; o fluxo do wizard usa ``sincronizar_textos_padrao``.
    """
    alterados: list[str] = []
    if not (plano.contextualizacao or "").strip():
        plano.contextualizacao = texto_padrao_contextualizacao(plano)
        alterados.append("contextualizacao")
    if not (plano.coordenacao or "").strip():
        texto = texto_padrao_coordenacao(plano)
        if texto:
            plano.coordenacao = texto
            alterados.append("coordenacao")
    if not (plano.consideracao_final or "").strip():
        plano.consideracao_final = texto_padrao_consideracao_final(plano)
        alterados.append("consideracao_final")
    return alterados


def _termos_genero_coordenador(genero: str) -> dict[str, str]:
    feminino = genero == PlanoTrabalho.COORDENADOR_GENERO_FEMININO
    return {
        "designado": "designada" if feminino else "designado",
        "artigo": "a" if feminino else "o",
        "coordenador_administrativo": (
            "Coordenadora Administrativa" if feminino else "Coordenador Administrativo"
        ),
        "coordenador_operacional": (
            "Coordenadora Operacional do Evento" if feminino else "Coordenador Operacional do Evento"
        ),
    }


def montar_texto_coordenacao(plano: PlanoTrabalho) -> str:
    """Parágrafos de designação dos coordenadores (adm sempre; operacional opcional)."""
    paragrafos: list[str] = []
    nome_adm, cargo_adm = plano.coordenador_nome_cargo("adm")
    if nome_adm:
        cargo_nome = " ".join(
            parte
            for parte in (format_document_display(cargo_adm), format_document_display(nome_adm))
            if parte
        )
        paragrafos.append(
            TEXTO_COORDENADOR_ADM.format(
                cargo_nome=cargo_nome,
                **_termos_genero_coordenador(plano.coordenador_genero("adm")),
            ),
        )
    # No multi-evento o coordenador operacional varia por evento; a designação única
    # de operacional não se aplica (o documento de exemplo traz apenas o administrativo).
    if plano.is_multi_evento:
        return "\n\n".join(paragrafos)
    nome_op, cargo_op = plano.coordenador_nome_cargo("op")
    if nome_op:
        cargo_nome = " ".join(
            parte
            for parte in (format_document_display(cargo_op), format_document_display(nome_op))
            if parte
        )
        paragrafos.append(
            TEXTO_COORDENADOR_OP.format(
                cargo_nome=cargo_nome,
                **_termos_genero_coordenador(plano.coordenador_genero("op")),
            ),
        )
    return "\n\n".join(paragrafos)


# ── Períodos e efetivo ───────────────────────────────────────────────────────


def format_data_extenso(valor: date) -> str:
    return f"{valor.day} de {_MESES_PT[valor.month]} de {valor.year}"


def format_periodo_evento_extenso(data_inicio: date | None, data_fim: date | None) -> str:
    """Portado do legado: '25 a 27 de junho de 2026', '30 de junho a 02 de julho de 2026'…"""
    if not data_inicio:
        return ""
    if not data_fim or data_fim == data_inicio:
        return format_data_extenso(data_inicio)

    d1 = f"{data_inicio.day:02d}"
    d2 = f"{data_fim.day:02d}"
    m1 = _MESES_PT[data_inicio.month]
    m2 = _MESES_PT[data_fim.month]

    if data_inicio.year == data_fim.year and data_inicio.month == data_fim.month:
        return f"{d1} a {d2} de {m1} de {data_inicio.year}"
    if data_inicio.year == data_fim.year:
        return f"{d1} de {m1} a {d2} de {m2} de {data_inicio.year}"
    return f"{d1} de {m1} de {data_inicio.year} a {d2} de {m2} de {data_fim.year}"


_CONECTORES_PT = {"de", "da", "do", "das", "dos", "e"}
_VOGAIS_PT = "aeiouáéíóúàâêîôûãõ"


def _is_sigla(word: str) -> bool:
    # Cargos são gravados todos em maiúsculas, então o case não distingue siglas;
    # só palavras curtas (NOC, DPC, PC) são tratadas como sigla.
    clean = "".join(c for c in word if c.isalpha())
    return bool(clean) and clean.isascii() and clean.isupper() and len(clean) <= 3


def _pluralizar_palavra_pt(word: str) -> str:
    if not word:
        return word
    if word.endswith("ão"):
        return word[:-2] + "ões"
    if word.endswith("il"):
        return word[:-2] + "is"
    last = word[-1]
    if last in _VOGAIS_PT:
        return word + "s"
    if last == "l" and len(word) >= 2:
        return word[:-1] + "is"
    if last in ("r", "z", "n"):
        return word + "es"
    if last == "m":
        return word[:-1] + "ns"
    if last == "s":
        return word
    return word + "s"


def _cargo_rotulo(nome: str, *, plural: bool) -> str:
    """'POLICIAL CIVIL' → 'Policiais Civis' (plural) ou 'Policial Civil' (singular)."""
    tokens = (nome or "").split()
    partes: list[str] = []
    for token in tokens:
        if _is_sigla(token):
            partes.append(token)
            continue
        low = token.lower()
        if plural and low not in _CONECTORES_PT:
            low = _pluralizar_palavra_pt(low)
        partes.append(low)
    return format_document_display(" ".join(partes))


def _efetivo_unidade_rotulo(unidade) -> str:
    """Sigla da unidade (ou o nome, se não houver sigla) para o sufixo entre parênteses."""
    if unidade is None:
        return ""
    sigla = (getattr(unidade, "sigla", "") or "").strip()
    return sigla or (getattr(unidade, "nome", "") or "").strip()


def _efetivo_linha(cargo_nome: str, unidade_nome: str, quantidade: int) -> str:
    """'2 Agentes de Polícia Judiciária (ASCOM)' — unidade só aparece quando informada."""
    rotulo = _cargo_rotulo(cargo_nome, plural=quantidade > 1)
    sufixo = f" ({unidade_nome})" if unidade_nome else ""
    return f"{quantidade} {rotulo}{sufixo}"


def _montar_efetivo_linhas(itens) -> str:
    """Uma linha por cargo/unidade, na ordem unidade → cargo."""
    linhas: list[str] = []
    for item in itens:
        if not item.quantidade or not item.cargo_id:
            continue
        cargo_nome = (item.cargo.nome or "").strip()
        if not cargo_nome:
            continue
        unidade = item.unidade if item.unidade_id else None
        linhas.append(_efetivo_linha(cargo_nome, _efetivo_unidade_rotulo(unidade), int(item.quantidade)))
    return "\n".join(linhas)


def montar_efetivo_texto(plano: PlanoTrabalho) -> str:
    """Texto do efetivo, uma linha por cargo/unidade:

        2 Agentes de Polícia Judiciária (ASCOM)
        8 Papiloscopistas (IIPR)

    No modo multi-evento, soma o efetivo de todos os eventos (por cargo + unidade).
    """
    if plano.is_multi_evento and plano.pk:
        agregados: dict[tuple[int, int | None], tuple[str, str, int]] = {}
        for evento in plano.eventos.all():
            for item in evento.efetivos.select_related("cargo", "unidade"):
                if not item.quantidade or not item.cargo_id:
                    continue
                cargo_nome = (item.cargo.nome or "").strip()
                if not cargo_nome:
                    continue
                unidade_nome = _efetivo_unidade_rotulo(item.unidade if item.unidade_id else None)
                chave = (item.cargo_id, item.unidade_id)
                _c, _u, anterior_qtd = agregados.get(chave, (cargo_nome, unidade_nome, 0))
                agregados[chave] = (cargo_nome, unidade_nome, anterior_qtd + int(item.quantidade))
        linhas = [
            _efetivo_linha(cargo_nome, unidade_nome, quantidade)
            for cargo_nome, unidade_nome, quantidade in sorted(
                agregados.values(), key=lambda v: (v[1], v[0])
            )
        ]
        return "\n".join(linhas)

    return _montar_efetivo_linhas(
        plano.efetivos.select_related("cargo", "unidade").order_by("unidade__nome", "cargo__nome")
    )


def montar_efetivo_evento_texto(evento: EventoPlano) -> str:
    """Texto do efetivo de um evento específico (uso multi-evento)."""
    return _montar_efetivo_linhas(
        evento.efetivos.select_related("cargo", "unidade").order_by("unidade__nome", "cargo__nome")
    )


# ── Diárias ──────────────────────────────────────────────────────────────────


def _sede_cidade_uf(area=None) -> tuple[str, str]:
    config = ConfiguracaoSistema.get_for_area(area)
    cidade = config.cidade_sede_padrao
    if cidade is not None:
        return cidade.nome or "", cidade.uf or ""
    return config.cidade_endereco or "", config.uf or ""


def calcular_diarias_plano(plano: PlanoTrabalho, total_efetivo: int | None = None) -> dict:
    """Calcula diárias com o motor de roteiros a partir da saída/chegada na sede.

    Um único período: sede → destino (saída) … chegada na sede.
    ``total_efetivo`` permite simular com efetivo ainda não persistido (cálculo ao vivo).
    Retorna {ok, erros[], composicao, valor_unitario, valor_total, displays e extensos}.
    """
    erros: list[str] = []
    if not (plano.saida_sede_data and plano.saida_sede_hora):
        erros.append("Informe data e hora de saída da sede.")
    if not (plano.chegada_sede_data and plano.chegada_sede_hora):
        erros.append("Informe data e hora de chegada na sede.")
    if not plano.destino_cidade_id:
        erros.append("Informe o destino na etapa de identificação.")
    if total_efetivo is None:
        total_efetivo = plano.total_efetivo
    if total_efetivo <= 0:
        erros.append("Informe o efetivo (cargo e quantidade).")
    if erros:
        return {"ok": False, "erros": erros}

    saida = datetime.combine(plano.saida_sede_data, plano.saida_sede_hora)
    chegada = datetime.combine(plano.chegada_sede_data, plano.chegada_sede_hora)
    if chegada <= saida:
        return {"ok": False, "erros": ["A chegada na sede deve ser depois da saída."]}

    sede_cidade, sede_uf = _sede_cidade_uf(plano.area if plano.area_id else None)
    marker = PeriodMarker(
        saida=saida,
        destino_cidade=plano.destino_cidade.nome,
        destino_uf=plano.destino_cidade.uf,
    )
    try:
        resultado = calculate_periodized_diarias(
            [marker],
            chegada,
            quantidade_servidores=total_efetivo,
            sede_cidade=sede_cidade or None,
            sede_uf=sede_uf or None,
        )
    except ValueError as exc:
        return {"ok": False, "erros": [str(exc)]}

    totais = resultado["totais"]
    valor_unitario = totais["valor_por_servidor_decimal"]
    valor_total = totais["total_valor_decimal"]
    return {
        "ok": True,
        "erros": [],
        "composicao": totais["diarias_por_servidor"],
        "valor_unitario": valor_unitario,
        "valor_total": valor_total,
        "valor_unitario_display": formatar_valor_diarias(valor_unitario),
        "valor_total_display": formatar_valor_diarias(valor_total),
        "valor_unitario_extenso": valor_por_extenso_ptbr(valor_unitario),
        "valor_total_extenso": valor_por_extenso_ptbr(valor_total),
        "quantidade_servidores": total_efetivo,
        "periodos": resultado["periodos"],
    }


def atualizar_snapshot_diarias(plano: PlanoTrabalho, *, save: bool = True) -> dict:
    """Recalcula e persiste a composição/valores das diárias no plano."""
    resultado = calcular_diarias_plano(plano)
    if resultado["ok"]:
        plano.diarias_composicao = resultado["composicao"]
        plano.diarias_valor_unitario = resultado["valor_unitario"]
        plano.diarias_valor_total = resultado["valor_total"]
    else:
        plano.diarias_composicao = ""
        plano.diarias_valor_unitario = None
        plano.diarias_valor_total = None
    if save:
        plano.save(
            update_fields=[
                "diarias_composicao",
                "diarias_valor_unitario",
                "diarias_valor_total",
                "updated_at",
            ]
        )
    return resultado


def montar_valor_do_plano_texto(plano: PlanoTrabalho) -> str:
    """Bloco do placeholder {{valor_do_plano}} no formato dos exemplos reais.

    No modo multi-evento, retorna o bloco do valor combinado (sede → todos eventos → sede).
    """
    if plano.is_multi_evento:
        composicao = plano.diarias_combinada_composicao
        unitario_val = plano.diarias_combinada_valor_unitario
        total_val = plano.diarias_combinada_valor_total
    else:
        composicao = plano.diarias_composicao
        unitario_val = plano.diarias_valor_unitario
        total_val = plano.diarias_valor_total
    if total_val is None or unitario_val is None:
        return ""
    total = Decimal(total_val)
    unitario = Decimal(unitario_val)
    return (
        f"Valor total: R${formatar_valor_diarias(total)} ({valor_por_extenso_ptbr(total)}). "
        f"Valor correspondente a {composicao}, por servidor, no valor unitário "
        f"de R${formatar_valor_diarias(unitario)} ({valor_por_extenso_ptbr(unitario)})."
    )


# ── Textos agrupados por evento (documento multi-evento) ─────────────────────
# No modo multi-evento cada seção do documento sai SEPARADA por evento, com um
# cabeçalho de data ("Dia 17 de junho de 2026:" / "Dias 18 a 21 de junho de 2026:"),
# em vez de concatenar tudo num bloco só.


def _evento_data_header(evento: EventoPlano) -> str:
    """'Dia 17 de junho de 2026' (dia único) ou 'Dias 18 a 21 de junho de 2026' (período)."""
    inicio = evento.data_evento_inicio
    fim = evento.data_evento_fim or inicio
    periodo = format_periodo_evento_extenso(inicio, fim)
    if not periodo:
        return ""
    dia_unico = (not fim) or (fim == inicio)
    return ("Dia " if dia_unico else "Dias ") + periodo


def _evento_data_curta(evento: EventoPlano) -> tuple[str, bool]:
    """('17/06/2026', True) para dia único; ('18 a 21/06/2026', False) p/ período (compacto)."""
    inicio = evento.data_evento_inicio
    fim = evento.data_evento_fim or inicio
    if not inicio:
        return "", True
    if not fim or fim == inicio:
        return inicio.strftime("%d/%m/%Y"), True
    if inicio.month == fim.month and inicio.year == fim.year:
        return f"{inicio.day:02d} a {fim.strftime('%d/%m/%Y')}", False
    return f"{inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}", False


def _valor_bloco_texto(label: str, composicao: str, unitario_val, total_val) -> str:
    if total_val is None or unitario_val is None:
        return ""
    total = Decimal(total_val)
    unitario = Decimal(unitario_val)
    return (
        f"{label}: R${formatar_valor_diarias(total)} ({valor_por_extenso_ptbr(total)}).\n"
        f"Valor correspondente a {composicao}, por servidor, no valor unitário "
        f"de R${formatar_valor_diarias(unitario)} ({valor_por_extenso_ptbr(unitario)})."
    )


def montar_valor_multi_texto(plano: PlanoTrabalho) -> str:
    """Seção 5 multi: valor de cada evento + 'Valor total' (trajeto combinado)."""
    blocos: list[str] = []
    for evento in plano.eventos_ordenados:
        curta, dia_unico = _evento_data_curta(evento)
        label = f"Valor do evento {'dia' if dia_unico else 'dias'}: {curta}"
        bloco = _valor_bloco_texto(
            label, evento.diarias_composicao, evento.diarias_valor_unitario, evento.diarias_valor_total
        )
        if bloco:
            blocos.append(bloco)
    total = _valor_bloco_texto(
        "Valor total",
        plano.diarias_combinada_composicao,
        plano.diarias_combinada_valor_unitario,
        plano.diarias_combinada_valor_total,
    )
    if total:
        blocos.append(total)
    return "\n\n".join(blocos)


# ── Diárias multi-evento ─────────────────────────────────────────────────────


def _destino_principal_evento(evento: EventoPlano) -> tuple[str, str] | None:
    """Retorna (cidade, uf) do destino principal do evento, ou None."""
    destino = evento.destino_principal
    if destino and destino.cidade_id:
        return destino.cidade.nome or "", destino.cidade.uf or ""
    # fallback: destino legado do plano (caso o evento ainda não tenha destino próprio)
    if evento.plano_id and evento.plano.destino_cidade_id:
        return evento.plano.destino_cidade.nome or "", evento.plano.destino_cidade.uf or ""
    return None


def _calcular_diaria(
    plano: PlanoTrabalho,
    markers: list[PeriodMarker],
    chegada: datetime,
    quantidade_servidores: int,
) -> dict:
    """Wrapper sobre ``calculate_periodized_diarias`` com formatação consistente."""
    sede_cidade, sede_uf = _sede_cidade_uf(plano.area if plano.area_id else None)
    resultado = calculate_periodized_diarias(
        markers,
        chegada,
        quantidade_servidores=quantidade_servidores,
        sede_cidade=sede_cidade or None,
        sede_uf=sede_uf or None,
    )
    totais = resultado["totais"]
    valor_unitario = totais["valor_por_servidor_decimal"]
    valor_total = totais["total_valor_decimal"]
    return {
        "ok": True,
        "erros": [],
        "composicao": totais["diarias_por_servidor"],
        "valor_unitario": valor_unitario,
        "valor_total": valor_total,
        "valor_unitario_display": formatar_valor_diarias(valor_unitario),
        "valor_total_display": formatar_valor_diarias(valor_total),
        "valor_unitario_extenso": valor_por_extenso_ptbr(valor_unitario),
        "valor_total_extenso": valor_por_extenso_ptbr(valor_total),
        "quantidade_servidores": quantidade_servidores,
        "periodos": resultado["periodos"],
    }


def calcular_diarias_evento(
    plano: PlanoTrabalho,
    evento: EventoPlano,
    total_efetivo: int | None = None,
) -> dict:
    """Cálculo individual: sede → evento → sede (só este evento)."""
    erros: list[str] = []
    if not (plano.saida_sede_data and plano.saida_sede_hora):
        erros.append("Informe data e hora de saída da sede.")
    if not (plano.chegada_sede_data and plano.chegada_sede_hora):
        erros.append("Informe data e hora de chegada na sede.")
    destino = _destino_principal_evento(evento)
    if destino is None:
        erros.append("Informe o destino do evento.")
    if total_efetivo is None:
        total_efetivo = evento.total_efetivo
    if total_efetivo <= 0:
        erros.append("Informe o efetivo do evento.")
    if erros:
        return {"ok": False, "erros": erros}

    saida = datetime.combine(plano.saida_sede_data, plano.saida_sede_hora)
    chegada = datetime.combine(plano.chegada_sede_data, plano.chegada_sede_hora)
    if chegada <= saida:
        return {"ok": False, "erros": ["A chegada na sede deve ser depois da saída."]}

    cidade, uf = destino  # type: ignore[misc]
    marker = PeriodMarker(saida=saida, destino_cidade=cidade, destino_uf=uf)
    try:
        return _calcular_diaria(plano, [marker], chegada, total_efetivo)
    except ValueError as exc:
        return {"ok": False, "erros": [str(exc)]}


def calcular_diarias_combinadas(plano: PlanoTrabalho) -> dict:
    """Cálculo combinado: sede → todos eventos (em ordem de data) → sede."""
    erros: list[str] = []
    if not (plano.saida_sede_data and plano.saida_sede_hora):
        erros.append("Informe data e hora de saída da sede.")
    if not (plano.chegada_sede_data and plano.chegada_sede_hora):
        erros.append("Informe data e hora de chegada na sede.")

    eventos = (
        list(plano.eventos.order_by("data_evento_inicio", "ordem", "pk"))
        if plano.pk
        else []
    )
    if not eventos:
        erros.append("Adicione ao menos um evento ao plano.")

    markers: list[PeriodMarker] = []
    for evento in eventos:
        destino = _destino_principal_evento(evento)
        if destino is None:
            erros.append(f"Informe o destino do evento {evento.ordem}.")
            continue
        if not evento.data_evento_inicio:
            erros.append(f"Informe a data de início do evento {evento.ordem}.")
            continue
        # Saída de cada trecho = início do evento (hora do horário de atendimento ou padrão)
        hora_inicio = _parse_hora_inicio(evento.horario_atendimento)
        saida_evento = datetime.combine(evento.data_evento_inicio, hora_inicio)
        cidade, uf = destino
        markers.append(PeriodMarker(saida=saida_evento, destino_cidade=cidade, destino_uf=uf))

    if erros:
        return {"ok": False, "erros": erros}

    chegada = datetime.combine(plano.chegada_sede_data, plano.chegada_sede_hora)
    # O primeiro marker deve coincidir com a saída da sede (substitui a saída padrão).
    saida_sede = datetime.combine(plano.saida_sede_data, plano.saida_sede_hora)
    if markers and saida_sede < markers[0].saida:
        markers[0] = PeriodMarker(
            saida=saida_sede,
            destino_cidade=markers[0].destino_cidade,
            destino_uf=markers[0].destino_uf,
        )
    if chegada <= markers[0].saida:
        return {"ok": False, "erros": ["A chegada na sede deve ser depois da saída."]}

    total = plano.total_efetivo_combinado
    if total <= 0:
        return {"ok": False, "erros": ["Informe o efetivo dos eventos."]}

    try:
        return _calcular_diaria(plano, markers, chegada, total)
    except ValueError as exc:
        return {"ok": False, "erros": [str(exc)]}


def _parse_hora_inicio(horario: str):
    """Extrai a hora de início de um texto livre tipo '09:00 até 17:00' ou '18h às 02h'."""
    from datetime import time
    import re

    if not horario:
        return time(9, 0)
    match = re.search(r"(\d{1,2})\s*[:hH]?\s*(\d{0,2})", horario)
    if not match:
        return time(9, 0)
    h = int(match.group(1))
    m = int(match.group(2)) if match.group(2) else 0
    if 0 <= h < 24 and 0 <= m < 60:
        return time(h, m)
    return time(9, 0)


def atualizar_snapshot_diarias_evento(evento: EventoPlano, *, save: bool = True) -> dict:
    """Recalcula e persiste a diária individual do evento."""
    resultado = calcular_diarias_evento(evento.plano, evento)
    if resultado["ok"]:
        evento.diarias_composicao = resultado["composicao"]
        evento.diarias_valor_unitario = resultado["valor_unitario"]
        evento.diarias_valor_total = resultado["valor_total"]
    else:
        evento.diarias_composicao = ""
        evento.diarias_valor_unitario = None
        evento.diarias_valor_total = None
    if save:
        evento.save(
            update_fields=[
                "diarias_composicao",
                "diarias_valor_unitario",
                "diarias_valor_total",
                "updated_at",
            ]
        )
    return resultado


def atualizar_snapshot_diarias_combinadas(plano: PlanoTrabalho, *, save: bool = True) -> dict:
    """Recalcula e persiste a diária combinada do plano (modo multi-evento)."""
    resultado = calcular_diarias_combinadas(plano)
    if resultado["ok"]:
        plano.diarias_combinada_composicao = resultado["composicao"]
        plano.diarias_combinada_valor_unitario = resultado["valor_unitario"]
        plano.diarias_combinada_valor_total = resultado["valor_total"]
    else:
        plano.diarias_combinada_composicao = ""
        plano.diarias_combinada_valor_unitario = None
        plano.diarias_combinada_valor_total = None
    if save:
        plano.save(
            update_fields=[
                "diarias_combinada_composicao",
                "diarias_combinada_valor_unitario",
                "diarias_combinada_valor_total",
                "updated_at",
            ]
        )
    return resultado


# ── Atividades, metas e recursos (etapa 3) ───────────────────────────────────


CODIGO_UNIDADE_MOVEL = "UNIDADE_MOVEL"

TEXTO_UNIDADE_MOVEL = (
    "Estrutura: Unidade móvel da PCPR equipada para atendimento e confecção de documentos."
)


def atividades_catalogo_ativas() -> list[AtividadePlanoTrabalho]:
    """Catálogo de atividades ativas, na ordem oficial (ordem, nome)."""
    return list(filter_queryset_by_area(AtividadePlanoTrabalho.objects).filter(ativo=True).order_by("ordem", "nome"))


def presets_atividades_ativos() -> list:
    """Presets ativos da área corrente, com atividades pré-carregadas."""
    from .models import PresetAtividadesPlanoTrabalho

    return list(
        filter_queryset_by_area(PresetAtividadesPlanoTrabalho.objects)
        .filter(ativo=True)
        .prefetch_related("atividades")
        .order_by("ordem", "nome")
    )


def _atividades_selecionadas_ordenadas(plano: PlanoTrabalho) -> list[AtividadePlanoTrabalho]:
    """Atividades marcadas no plano, sempre na ordem oficial do catálogo."""
    if not plano.pk:
        return []
    return list(plano.atividades_selecionadas.order_by("ordem", "nome"))


def montar_atividades_texto(itens: list[AtividadePlanoTrabalho]) -> str:
    """Lista das atividades selecionadas (uma por linha)."""
    return "\n".join(f"• {item.nome}" for item in itens)


def montar_metas_texto(itens: list[AtividadePlanoTrabalho]) -> str:
    """Metas correspondentes às atividades, na ordem oficial, sem duplicar."""
    metas: list[str] = []
    vistos: set[str] = set()
    for item in itens:
        meta = (item.meta or "").strip()
        if meta and meta not in vistos:
            vistos.add(meta)
            metas.append(meta)
    return "\n".join(f"• {m}" for m in metas)


def montar_recursos_texto(itens: list[AtividadePlanoTrabalho]) -> str:
    """Texto-base de recursos a partir das atividades (recurso é opcional)."""
    if not itens:
        return ""
    recursos_itens: list[str] = []
    vistos: set[str] = set()
    for item in itens:
        recurso = (item.recurso_necessario or "").strip()
        if recurso and recurso not in vistos:
            vistos.add(recurso)
            recursos_itens.append(f"• {recurso}")
    linhas: list[str] = []
    if recursos_itens:
        linhas.extend(recursos_itens)
    if any(item.codigo == CODIGO_UNIDADE_MOVEL for item in itens):
        linhas.append("• Prever unidade móvel institucional e o suporte operacional associado.")
    return "\n".join(linhas)


def montar_unidade_movel_texto(itens: list[AtividadePlanoTrabalho]) -> str:
    """Texto do placeholder {{unidade_movel}} — só quando a atividade está marcada."""
    if any(item.codigo == CODIGO_UNIDADE_MOVEL for item in itens):
        return TEXTO_UNIDADE_MOVEL
    return ""


def sincronizar_atividades(plano: PlanoTrabalho, *, save: bool = True) -> list[str]:
    """Regenera os textos de etapa 3 a partir das atividades selecionadas.

    Retorna a lista de campos alterados (para ``save(update_fields=...)``).
    Deve ser chamada após persistir o M2M ``atividades_selecionadas``.
    No modo multi-evento, agrega das atividades de cada evento.
    """
    if plano.is_multi_evento and plano.pk:
        itens = _atividades_combinadas_multi(plano)
    else:
        itens = _atividades_selecionadas_ordenadas(plano)
    plano.atividades = montar_atividades_texto(itens)
    plano.metas = montar_metas_texto(itens)
    plano.recursos_necessarios = montar_recursos_texto(itens)
    plano.unidade_movel_texto = montar_unidade_movel_texto(itens)
    campos = ["atividades", "metas", "recursos_necessarios", "unidade_movel_texto"]
    if save:
        plano.save(update_fields=[*campos, "updated_at"])
    return campos


def _atividades_evento_ordenadas(evento: EventoPlano) -> list[AtividadePlanoTrabalho]:
    if not evento.pk:
        return []
    return list(evento.atividades_selecionadas.order_by("ordem", "nome"))


def _atividades_combinadas_multi(plano: PlanoTrabalho) -> list[AtividadePlanoTrabalho]:
    """União ordenada (catálogo) das atividades de todos os eventos do plano."""
    if not plano.pk:
        return []
    codigos: set[str] = set()
    for evento in plano.eventos.all():
        for ativ in evento.atividades_selecionadas.all():
            codigos.add(ativ.codigo)
    if not codigos:
        return []
    return list(
        filter_queryset_by_area(AtividadePlanoTrabalho.objects).filter(codigo__in=codigos).order_by("ordem", "nome")
    )


def sincronizar_atividades_evento(evento: EventoPlano, *, save: bool = True) -> list[str]:
    """Regenera os textos cacheados do evento a partir de suas atividades."""
    itens = _atividades_evento_ordenadas(evento)
    evento.atividades_texto = montar_atividades_texto(itens)
    evento.metas = montar_metas_texto(itens)
    evento.recursos_necessarios = montar_recursos_texto(itens)
    evento.unidade_movel_texto = montar_unidade_movel_texto(itens)
    campos = ["atividades_texto", "metas", "recursos_necessarios", "unidade_movel_texto"]
    if save:
        evento.save(update_fields=[*campos, "updated_at"])
    return campos


# ── Multi-evento: scratchpad ↔ EventoPlano ───────────────────────────────────
#
# As etapas 1–3 sempre editam os campos plano-level ("rascunho do evento atual").
# Ao "Adicionar evento ao plano" (etapa 4) o rascunho é commitado para um
# ``EventoPlano`` (cópia de programa/destino/datas/horário/coord op/efetivo/
# atividades/diárias) e o rascunho é limpo para o próximo evento. Editar o card de
# um evento recarrega aquele evento no rascunho. Usamos semântica de CÓPIA para
# destinos e efetivo (o evento recebe cópias; o rascunho permanece intacto), o que
# permite sincronizar sem corromper o formulário em edição.

# Campos escalares espelhados entre o rascunho (plano) e o evento.
# (origem_no_plano, destino_no_evento)
_SCRATCHPAD_CAMPOS = [
    ("programa_id", "programa_id"),
    ("programa_outros", "programa_outros"),
    ("data_evento_inicio", "data_evento_inicio"),
    ("data_evento_fim", "data_evento_fim"),
    ("horario_atendimento", "horario_atendimento"),
    ("coordenador_op_modo", "coordenador_op_modo"),
    ("coordenador_op_id", "coordenador_op_id"),
    ("coordenador_op_nome_manual", "coordenador_op_nome_manual"),
    ("coordenador_op_cargo_manual", "coordenador_op_cargo_manual"),
    ("coordenador_op_genero", "coordenador_op_genero"),
    ("metas", "metas"),
    ("atividades", "atividades_texto"),
    ("recursos_necessarios", "recursos_necessarios"),
    ("unidade_movel_texto", "unidade_movel_texto"),
    ("diarias_composicao", "diarias_composicao"),
    ("diarias_valor_unitario", "diarias_valor_unitario"),
    ("diarias_valor_total", "diarias_valor_total"),
]


def scratchpad_tem_conteudo(plano: PlanoTrabalho) -> bool:
    """True se o rascunho atual tem dados de evento dignos de virar um EventoPlano."""
    if not plano.pk:
        return False
    return bool(
        plano.programa_id
        or (plano.programa_outros or "").strip()
        or plano.destino_cidade_id
        or plano.data_evento_inicio
        or plano.atividades_selecionadas.exists()
        or plano.efetivos.exists()
        or plano.destinos.filter(evento__isnull=True).exists()
    )


def commit_scratchpad_para_evento(plano: PlanoTrabalho) -> EventoPlano | None:
    """Cria/atualiza o EventoPlano que o rascunho representa. Retorna o evento (ou None)."""
    from .models import EfetivoEvento, EventoPlano as _EventoPlano, PlanoDestino

    evento = plano.evento_em_edicao
    if evento is None:
        if not scratchpad_tem_conteudo(plano):
            return None
        ordem = (plano.eventos.aggregate(maxo=Max("ordem"))["maxo"] or 0) + 1
        evento = _EventoPlano(plano=plano, ordem=ordem)

    for origem, destino in _SCRATCHPAD_CAMPOS:
        setattr(evento, destino, getattr(plano, origem))
    evento.save()

    # Atividades (M2M) — cópia.
    evento.atividades_selecionadas.set(plano.atividades_selecionadas.all())

    # Efetivo — recria as linhas do evento a partir do rascunho.
    evento.efetivos.all().delete()
    for ef in plano.efetivos.all():
        EfetivoEvento.objects.create(
            evento=evento,
            unidade_id=ef.unidade_id,
            cargo_id=ef.cargo_id,
            quantidade=ef.quantidade,
        )

    # Destinos — recria cópias para o evento (mantém as linhas do rascunho intactas).
    PlanoDestino.objects.filter(evento=evento).delete()
    scratch = list(plano.destinos.filter(evento__isnull=True).order_by("ordem", "pk"))
    for d in scratch:
        PlanoDestino.objects.create(
            plano=plano, evento=evento, estado_id=d.estado_id, cidade_id=d.cidade_id, ordem=d.ordem
        )
    if not scratch and plano.destino_cidade_id:
        estado_id = plano.destino_estado_id or plano.destino_cidade.estado_id
        PlanoDestino.objects.create(
            plano=plano, evento=evento, estado_id=estado_id, cidade_id=plano.destino_cidade_id, ordem=1
        )
    return evento


def limpar_scratchpad(plano: PlanoTrabalho) -> None:
    """Zera os campos de evento do rascunho (preserva coord adm/contextualização/sede)."""
    plano.programa = None
    plano.programa_outros = ""
    plano.destino_estado = None
    plano.destino_cidade = None
    plano.data_evento_inicio = None
    plano.data_evento_fim = None
    plano.horario_atendimento = "09:00 até 17:00"
    plano.coordenador_op_modo = PlanoTrabalho.COORDENADOR_MODO_SERVIDOR
    plano.coordenador_op = None
    plano.coordenador_op_nome_manual = ""
    plano.coordenador_op_cargo_manual = ""
    plano.coordenador_op_genero = PlanoTrabalho.COORDENADOR_GENERO_MASCULINO
    plano.metas = ""
    plano.atividades = ""
    plano.recursos_necessarios = ""
    plano.unidade_movel_texto = ""
    plano.diarias_composicao = ""
    plano.diarias_valor_unitario = None
    plano.diarias_valor_total = None
    plano.save()
    plano.atividades_selecionadas.clear()
    plano.efetivos.all().delete()
    plano.destinos.filter(evento__isnull=True).delete()


def carregar_evento_no_scratchpad(plano: PlanoTrabalho, evento: EventoPlano) -> None:
    """Copia um evento commitado de volta para o rascunho e marca-o em edição."""
    from .models import EfetivoPlano, PlanoDestino

    for origem, destino in _SCRATCHPAD_CAMPOS:
        setattr(plano, origem, getattr(evento, destino))

    primeiro = evento.destinos.order_by("ordem", "pk").first() if evento.pk else None
    if primeiro:
        plano.destino_estado_id = primeiro.estado_id
        plano.destino_cidade_id = primeiro.cidade_id
    else:
        plano.destino_estado = None
        plano.destino_cidade = None
    plano.evento_em_edicao = evento
    plano.save()

    plano.atividades_selecionadas.set(evento.atividades_selecionadas.all())

    plano.efetivos.all().delete()
    for ef in evento.efetivos.all():
        EfetivoPlano.objects.create(
            plano=plano, unidade_id=ef.unidade_id, cargo_id=ef.cargo_id, quantidade=ef.quantidade
        )

    plano.destinos.filter(evento__isnull=True).delete()
    for d in evento.destinos.order_by("ordem", "pk"):
        PlanoDestino.objects.create(
            plano=plano, evento=None, estado_id=d.estado_id, cidade_id=d.cidade_id, ordem=d.ordem
        )


def adicionar_evento_ao_plano(plano: PlanoTrabalho) -> EventoPlano | None:
    """Commita o rascunho como evento, limpa o rascunho e devolve à etapa 1 em branco."""
    evento = commit_scratchpad_para_evento(plano)
    if evento is None:
        return None
    plano.is_multi_evento = True
    plano.evento_em_edicao = None
    limpar_scratchpad(plano)  # full save persiste flags + zera o rascunho
    atualizar_snapshot_diarias_combinadas(plano)
    return evento


def editar_evento_no_scratchpad(plano: PlanoTrabalho, evento: EventoPlano) -> None:
    """Salva o rascunho em andamento e carrega o evento escolhido para edição."""
    commit_scratchpad_para_evento(plano)  # preserva o evento que estava sendo digitado
    plano.evento_em_edicao = None
    limpar_scratchpad(plano)
    carregar_evento_no_scratchpad(plano, evento)
    atualizar_snapshot_diarias_combinadas(plano)


def remover_evento(plano: PlanoTrabalho, evento: EventoPlano) -> None:
    """Exclui um evento; se era o que estava em edição, limpa o rascunho."""
    era_em_edicao = plano.evento_em_edicao_id == evento.pk
    evento.delete()  # cascade remove efetivos e destinos do evento
    if era_em_edicao:
        plano.evento_em_edicao = None
        limpar_scratchpad(plano)
    if plano.eventos.count() == 0:
        plano.is_multi_evento = False
        plano.evento_em_edicao = None
        plano.save(update_fields=["is_multi_evento", "evento_em_edicao", "updated_at"])
    else:
        atualizar_snapshot_diarias_combinadas(plano)


def sincronizar_scratchpad(plano: PlanoTrabalho) -> EventoPlano | None:
    """Reflete o rascunho atual como EventoPlano sem limpá-lo (etapa 4/finalização)."""
    if not plano.is_multi_evento:
        return None
    evento = commit_scratchpad_para_evento(plano)
    if evento is not None and plano.evento_em_edicao_id != evento.pk:
        plano.evento_em_edicao = evento
        plano.save(update_fields=["evento_em_edicao", "updated_at"])
    atualizar_snapshot_diarias_combinadas(plano)
    return evento


def eventos_para_cards(plano: PlanoTrabalho) -> list[EventoPlano]:
    """Eventos commitados a exibir como cards (exclui o que está no rascunho)."""
    if not plano.pk or not plano.is_multi_evento:
        return []
    qs = plano.eventos.order_by("ordem", "data_evento_inicio", "pk")
    if plano.evento_em_edicao_id:
        qs = qs.exclude(pk=plano.evento_em_edicao_id)
    return list(qs)


# ── Avaliação de etapas (stepper) ────────────────────────────────────────────


def avaliar_etapa_identificacao(plano: PlanoTrabalho) -> str:
    campos = [
        plano.destino_cidade_id,
        plano.data_evento_inicio,
        (plano.contextualizacao or "").strip(),
    ]
    nome_adm, _ = plano.coordenador_nome_cargo("adm")
    if all(campos) and nome_adm:
        return "complete"
    if any(campos) or nome_adm:
        return "incomplete"
    return "not_started"


def avaliar_etapa_efetivo_diarias(plano: PlanoTrabalho) -> str:
    tem_efetivo = plano.total_efetivo > 0
    tem_diarias = plano.diarias_valor_total is not None
    if tem_efetivo and tem_diarias:
        return "complete"
    if tem_efetivo or plano.saida_sede_data or plano.chegada_sede_data:
        return "incomplete"
    return "not_started"


def avaliar_etapa_atividades(plano: PlanoTrabalho) -> str:
    if plano.pk and plano.atividades_selecionadas.exists():
        return "complete"
    return "not_started"


def avaliar_pendencias_documento(plano: PlanoTrabalho) -> list[str]:
    pendencias: list[str] = []
    nome_adm, _ = plano.coordenador_nome_cargo("adm")
    if not nome_adm:
        pendencias.append("Informe o coordenador administrativo na etapa de identificação.")
    if plano.is_multi_evento:
        eventos = list(plano.eventos.all()) if plano.pk else []
        if not eventos:
            pendencias.append("Adicione ao menos um evento ao plano.")
        for evento in eventos:
            destino = _destino_principal_evento(evento)
            if destino is None:
                pendencias.append(f"Informe o destino do evento {evento.ordem}.")
            if not evento.data_evento_inicio:
                pendencias.append(f"Informe a data do evento {evento.ordem}.")
            if evento.total_efetivo <= 0:
                pendencias.append(f"Informe o efetivo do evento {evento.ordem}.")
        if plano.diarias_combinada_valor_total is None:
            pendencias.append("Calcule as diárias combinadas na etapa de efetivo e diárias.")
    else:
        if not plano.destino_cidade_id:
            pendencias.append("Informe o destino (cidade/UF) na etapa de identificação.")
        if not plano.data_evento_inicio:
            pendencias.append("Informe a data do evento na etapa de identificação.")
        if plano.total_efetivo <= 0:
            pendencias.append("Informe o efetivo (cargo e quantidade) na etapa de efetivo e diárias.")
        if plano.diarias_valor_total is None:
            pendencias.append("Calcule as diárias na etapa de efetivo e diárias.")
    return pendencias


# ── Geração documental ───────────────────────────────────────────────────────


def gerar_plano_documento(plano: PlanoTrabalho, formato: DocumentoFormato):
    """Gera o documento do plano (DOCX/PDF) e o persiste como ``DocumentoArtefato``.

    Retorna o ``DocumentoGerado``. A persistência é idempotente por conteúdo e
    no-op quando desligada (testes); falhas não quebram a geração.
    """
    from .docxtpl_context import build_plano_docxtpl_context

    from cadastros.selectors import build_configuracao_context

    with measure_step(
        "plano_trabalho_gerar_documento",
        {"plano_id": plano.pk, "formato": formato.value},
        track_sla=True,
    ):
        contexto = build_plano_docxtpl_context(plano)
        payload = {
            "institucional": build_configuracao_context(area=getattr(plano, "area", None)),
            "plano": contexto,
        }
        reference = (
            f"{plano.numero:02d}-{plano.ano}" if plano.numero and plano.ano else f"plano-{plano.pk}"
        )
        # Multi-evento usa um template dedicado (loops por evento); single mantém o padrão.
        docx_template = "plano_trabalho_multievento.docx" if plano.is_multi_evento else None
        attempt_chain = ()
        if formato == DocumentoFormato.PDF:
            attempt_chain = resolve_pdf_engine(
                explicit_setting=getattr(settings, "DOCUMENTOS_DEFAULT_PDF_ENGINE", "auto"),
                prefer_docx_pipeline=True,
            ).attempt_chain
        cache_key = build_document_cache_key(
            tipo=DocumentoTipo.PLANO_TRABALHO,
            formato=formato,
            reference=reference,
            payload=payload,
            docxtpl_context=contexto,
            attempt_chain=attempt_chain,
            template_signature=build_template_cache_signature(
                tipo=DocumentoTipo.PLANO_TRABALHO,
                formato=formato,
                docx_template_path=docx_template,
            ),
        )
        if plano.evento_id:
            cached = get_cached_document_artifact(
                evento_id=plano.evento_id,
                tipo=DocumentoTipo.PLANO_TRABALHO,
                formato=formato,
                cache_key=cache_key,
            )
            if cached is not None:
                return documento_gerado_from_artifact(
                    cached,
                    tipo=DocumentoTipo.PLANO_TRABALHO,
                    formato=formato,
                    reference=reference,
                )

        facade = build_default_facade()
        doc = facade.gerar(
            tipo=DocumentoTipo.PLANO_TRABALHO,
            formato=formato,
            payload=payload,
            reference=reference,
            docxtpl_context=contexto,
            docx_template_path=docx_template,
        )
        _persistir_plano_artefato(
            plano,
            doc,
            cache_key=cache_key,
            payload_snapshot=payload,
        )
        return doc


def _persistir_plano_artefato(
    plano: PlanoTrabalho,
    doc,
    *,
    cache_key: str = "",
    payload_snapshot: dict | None = None,
) -> None:
    try:
        from documentos.models import DocumentoArtefato
        from documentos.services.persistence import persist_geracao
        from integracoes.google_drive import naming

        if DocumentoArtefato.objects.filter(
            tipo=DocumentoTipo.PLANO_TRABALHO.value, hash_sha256=doc.hash_sha256
        ).exists():
            return
        oficio = plano.evento.oficios.first() if plano.evento_id else None
        persist_geracao(
            doc,
            evento_id=plano.evento_id,
            oficio_id=(oficio.pk if oficio else None),
            nome_drive=naming.nome_plano(plano),
            payload_snapshot=payload_snapshot,
            cache_key=cache_key,
            engine=doc.pdf_engine_used or "",
        )
    except Exception:
        logger.warning("Não foi possível persistir artefato do plano de trabalho.", exc_info=True)


def gerar_resposta_plano_documento(plano: PlanoTrabalho, formato: DocumentoFormato):
    """Gera DOCX/PDF do plano e devolve a resposta de download."""
    doc = gerar_plano_documento(plano, formato)
    reference = (
        f"{plano.numero:02d}-{plano.ano}" if plano.numero and plano.ano else f"plano-{plano.pk}"
    )
    response = build_download_response(
        content=doc.conteudo,
        tipo=DocumentoTipo.PLANO_TRABALHO,
        formato=formato,
        reference=reference,
    )
    response["X-Document-SHA256"] = doc.hash_sha256
    return response


def marcar_plano_gerado(plano: PlanoTrabalho) -> None:
    if plano.status != PlanoTrabalho.STATUS_GERADO:
        plano.status = PlanoTrabalho.STATUS_GERADO
        plano.save(update_fields=["status", "updated_at"])


@transaction.atomic
def salvar_plano_numerado(plano: PlanoTrabalho) -> PlanoTrabalho:
    """Reserva e grava o Plano com a mecânica comum e a política de contador."""
    if plano.numero and plano.ano:
        plano.save()
        return plano

    ano = timezone.localdate().year
    original_pk = plano.pk
    original_adding = plano._state.adding
    escolha = {}

    def escolher():
        numero, ano_escolhido, sufixo = type(plano).proximo_numero(plano.area)
        escolha["ano"] = ano_escolhido
        escolha["sufixo"] = sufixo
        return numero

    def gravar(numero):
        plano.numero = numero
        plano.ano = escolha["ano"]
        plano.sufixo_numero = escolha["sufixo"]
        plano.save()

    def limpar():
        plano.numero = None
        plano.ano = None
        plano.sufixo_numero = ""
        if original_adding:
            plano.pk = original_pk
            plano._state.adding = True

    def numero_ocupado(numero):
        # `BE-09`: `all_objects` é deliberado; o filtro já usa a área do Plano,
        # não a área ativa do request, e precisa funcionar em worker/comando.
        return (
            # O recorte explícito por `plano.area_id` está logo abaixo.
            PlanoTrabalho.all_objects.filter(
                area_id=plano.area_id,
                ano=ano,
                numero=numero,
            )
            .exclude(pk=plano.pk)
            .exists()
        )

    reservar_numero(
        namespace=NAMESPACE_PLANO_TRABALHO,
        area_id=plano.area_id,
        ano=ano,
        modelo=PlanoTrabalho,
        constraint=CONSTRAINT_NUMERO_PLANO_TRABALHO,
        escolher=escolher,
        gravar=gravar,
        ja_ocupado=numero_ocupado,
        apos_colisao=limpar,
    )
    return plano


def criar_plano_rascunho(evento=None) -> PlanoTrabalho:
    seed = {}
    if evento is not None:
        from eventos.services import build_evento_document_seed

        seed = build_evento_document_seed(evento)

    area = getattr(evento, "area", None) or get_current_area()
    plano = PlanoTrabalho(data_criacao=timezone.localdate(), area=area)
    plano.evento = evento
    config = ConfiguracaoSistema.get_for_area(area)
    if config.coordenador_adm_plano_trabalho_id:
        plano.coordenador_adm = config.coordenador_adm_plano_trabalho
    elif getattr(evento, "responsavel_id", None):
        plano.coordenador_adm = evento.responsavel
    if getattr(evento, "responsavel_id", None):
        plano.coordenador_op = evento.responsavel
    cidade = seed.get("cidade")
    estado = seed.get("estado")
    if cidade is not None:
        plano.destino_cidade = cidade
        plano.destino_estado = getattr(cidade, "estado", None) or estado
    elif estado is not None:
        plano.destino_estado = estado
    plano.data_evento_inicio = seed.get("data_inicio")
    plano.data_evento_fim = seed.get("data_fim") or seed.get("data_inicio")
    if evento is not None:
        plano.programa_outros = getattr(evento, "titulo", "") or ""
        if getattr(evento, "horario_inicio", None) and getattr(evento, "horario_fim", None):
            plano.horario_atendimento = (
                f"{evento.horario_inicio:%H:%M} ate {evento.horario_fim:%H:%M}"
            )
    # A contextualização NÃO herda o motivo do evento: o motivo é texto curto de
    # agenda, não o parágrafo de abertura do plano. Fica no modo automático
    # (destino + programa) até o usuário editar à mão.
    return salvar_plano_numerado(plano)
