"""Regras de negócio do Plano de Trabalho: textos padrão, diárias e geração documental."""

from __future__ import annotations

import logging
from datetime import date
from datetime import datetime
from decimal import Decimal

from django.utils import timezone

from cadastros.models import ConfiguracaoSistema
from documentos.services.facade import build_default_facade
from documentos.services.formatters import format_city_uf
from documentos.services.formatters import format_document_display
from documentos.services.responses import build_download_response
from documentos.services.timing import measure_step
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo
from roteiros.services.diarias import PeriodMarker
from roteiros.services.diarias import calculate_periodized_diarias
from roteiros.services.diarias import formatar_valor_diarias
from roteiros.services.valor_extenso import valor_por_extenso_ptbr

from .models import AtividadePlanoTrabalho
from .models import PlanoTrabalho

logger = logging.getLogger(__name__)

_MESES_PT = (
    "", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)

TEXTO_PADRAO_CONTEXTUALIZACAO = (
    "A Assessoria de Comunicação Social da Polícia Civil do Paraná (PCPR), no âmbito do "
    "programa “PCPR na Comunidade”, promoverá ação itinerante no município de {municipio}.\n"
    "A iniciativa visa atender à solicitação formulada pelo {programa} (Ofício em anexo), "
    "levando serviços essenciais de polícia judiciária às populações urbanas, rurais e "
    "ribeirinhas, especialmente em localidades de difícil acesso.\n"
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
    "Fica designado(a) como Coordenador(a) Administrativo(a) do Plano o(a) {cargo_nome}, "
    "o(a) qual ficará responsável pelo acompanhamento da execução administrativa do presente "
    "Plano de Trabalho, organização das escalas de servidores, controle de materiais e "
    "equipamentos, consolidação de dados estatísticos, elaboração de relatório final e demais "
    "providências necessárias ao regular cumprimento da ação."
)

TEXTO_COORDENADOR_OP = (
    "Fica designado(a) como Coordenador(a) Operacional do Evento o(a) {cargo_nome}, "
    "o(a) qual ficará responsável pela execução operacional da ação no local do evento, "
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


def textos_padrao_templates() -> dict[str, str]:
    """Modelos brutos (com tokens {municipio}/{programa}) para a pré-visualização no cliente."""
    return {
        "contextualizacao": TEXTO_PADRAO_CONTEXTUALIZACAO,
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
    if not (plano.consideracao_final or "").strip():
        plano.consideracao_final = texto_padrao_consideracao_final(plano)
        alterados.append("consideracao_final")
    return alterados


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
        paragrafos.append(TEXTO_COORDENADOR_ADM.format(cargo_nome=cargo_nome))
    nome_op, cargo_op = plano.coordenador_nome_cargo("op")
    if nome_op:
        cargo_nome = " ".join(
            parte
            for parte in (format_document_display(cargo_op), format_document_display(nome_op))
            if parte
        )
        paragrafos.append(TEXTO_COORDENADOR_OP.format(cargo_nome=cargo_nome))
    return "\n".join(paragrafos)


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


def montar_efetivo_texto(plano: PlanoTrabalho) -> str:
    """Texto do efetivo por cargo: '6 Policiais Civis' / '4 Investigadores, 2 Papiloscopistas'."""
    partes: list[str] = []
    for item in plano.efetivos.select_related("cargo").order_by("cargo__nome"):
        if not item.quantidade:
            continue
        cargo_nome = (item.cargo.nome or "").strip() if item.cargo_id else ""
        if not cargo_nome:
            continue
        rotulo = _cargo_rotulo(cargo_nome, plural=item.quantidade > 1)
        partes.append(f"{int(item.quantidade)} {rotulo}")
    return ", ".join(partes)


# ── Diárias ──────────────────────────────────────────────────────────────────


def _sede_cidade_uf() -> tuple[str, str]:
    config = ConfiguracaoSistema.get_singleton()
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

    sede_cidade, sede_uf = _sede_cidade_uf()
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
    """Bloco do placeholder {{valor_do_plano}} no formato dos exemplos reais."""
    if plano.diarias_valor_total is None or plano.diarias_valor_unitario is None:
        return ""
    total = Decimal(plano.diarias_valor_total)
    unitario = Decimal(plano.diarias_valor_unitario)
    return (
        f"Valor total: R${formatar_valor_diarias(total)} ({valor_por_extenso_ptbr(total)}). "
        f"Valor correspondente a {plano.diarias_composicao}, por servidor, no valor unitário "
        f"de R${formatar_valor_diarias(unitario)} ({valor_por_extenso_ptbr(unitario)})."
    )


# ── Atividades, metas e recursos (etapa 3) ───────────────────────────────────


CODIGO_UNIDADE_MOVEL = "UNIDADE_MOVEL"

TEXTO_UNIDADE_MOVEL = (
    "Estrutura: Unidade móvel da PCPR equipada para atendimento e confecção de documentos."
)


def atividades_catalogo_ativas() -> list[AtividadePlanoTrabalho]:
    """Catálogo de atividades ativas, na ordem oficial (ordem, nome)."""
    return list(AtividadePlanoTrabalho.objects.filter(ativo=True).order_by("ordem", "nome"))


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
    return "\n\n".join(metas)


def montar_recursos_texto(itens: list[AtividadePlanoTrabalho]) -> str:
    """Texto-base de recursos a partir das atividades (recurso é opcional)."""
    if not itens:
        return ""
    atividades = "; ".join(item.nome for item in itens)
    recursos_itens: list[str] = []
    vistos: set[str] = set()
    for item in itens:
        recurso = (item.recurso_necessario or "").strip()
        if recurso and recurso not in vistos:
            vistos.add(recurso)
            recursos_itens.append(f"• {recurso}")
    linhas = [
        (
            "Recursos operacionais, materiais de atendimento, equipamentos de apoio "
            "e suporte logístico compatíveis com as atividades selecionadas."
        ),
        f"Escopo previsto: {atividades}.",
    ]
    if recursos_itens:
        linhas.append("Recursos específicos por atividade:")
        linhas.extend(recursos_itens)
    if any(item.codigo == CODIGO_UNIDADE_MOVEL for item in itens):
        linhas.append("Prever unidade móvel institucional e o suporte operacional associado.")
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
    """
    itens = _atividades_selecionadas_ordenadas(plano)
    plano.atividades = montar_atividades_texto(itens)
    plano.metas = montar_metas_texto(itens)
    plano.recursos_necessarios = montar_recursos_texto(itens)
    plano.unidade_movel_texto = montar_unidade_movel_texto(itens)
    campos = ["atividades", "metas", "recursos_necessarios", "unidade_movel_texto"]
    if save:
        plano.save(update_fields=[*campos, "updated_at"])
    return campos


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
    if not plano.destino_cidade_id:
        pendencias.append("Informe o destino (cidade/UF) na etapa de identificação.")
    if not plano.data_evento_inicio:
        pendencias.append("Informe a data do evento na etapa de identificação.")
    nome_adm, _ = plano.coordenador_nome_cargo("adm")
    if not nome_adm:
        pendencias.append("Informe o coordenador administrativo na etapa de identificação.")
    if plano.total_efetivo <= 0:
        pendencias.append("Informe o efetivo (cargo e quantidade) na etapa de efetivo e diárias.")
    if plano.diarias_valor_total is None:
        pendencias.append("Calcule as diárias na etapa de efetivo e diárias.")
    return pendencias


# ── Geração documental ───────────────────────────────────────────────────────


def gerar_resposta_plano_documento(plano: PlanoTrabalho, formato: DocumentoFormato):
    """Gera DOCX/PDF do plano usando o template plano_trabalho.docx (placeholders planos)."""
    from .docxtpl_context import build_plano_docxtpl_context

    from cadastros.selectors import build_configuracao_context

    with measure_step(
        "plano_trabalho_gerar_documento",
        {"plano_id": plano.pk, "formato": formato.value},
    ):
        contexto = build_plano_docxtpl_context(plano)
        payload = {"institucional": build_configuracao_context(), "plano": contexto}
        reference = (
            f"{plano.numero:02d}-{plano.ano}" if plano.numero and plano.ano else f"plano-{plano.pk}"
        )
        facade = build_default_facade()
        doc = facade.gerar(
            tipo=DocumentoTipo.PLANO_TRABALHO,
            formato=formato,
            payload=payload,
            reference=reference,
            docxtpl_context=contexto,
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


def criar_plano_rascunho() -> PlanoTrabalho:
    plano = PlanoTrabalho(data_criacao=timezone.localdate())
    plano.atribuir_numero()
    config = ConfiguracaoSistema.get_singleton()
    if config.coordenador_adm_plano_trabalho_id:
        plano.coordenador_adm = config.coordenador_adm_plano_trabalho
    plano.save()
    return plano
