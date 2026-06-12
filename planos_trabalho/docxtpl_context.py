"""Contexto docxtpl (placeholders planos) para o modelo plano_trabalho.docx."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from cadastros.selectors import build_configuracao_context
from documentos.services.formatters import format_city_uf
from documentos.services.formatters import format_document_display
from oficios.docxtpl_context import _assinatura_nome_cargo
from oficios.docxtpl_context import _build_sede

from .models import PlanoTrabalho


def build_plano_docxtpl_context(plano: PlanoTrabalho) -> dict[str, Any]:
    from .services import (
        format_data_extenso,
        format_periodo_evento_extenso,
        montar_efetivo_texto,
        montar_texto_coordenacao,
        montar_valor_do_plano_texto,
    )

    inst = build_configuracao_context()

    def _txt(value: object) -> str:
        return str(value or "").strip()

    nome_chefia, cargo_chefia = _assinatura_nome_cargo(inst, "PLANO_TRABALHO")

    return {
        "numero_plano_trabalho": plano.numero_formatado if plano.numero else "—",
        "unidade": _txt(inst.get("unidade")) or _txt(inst.get("nome_orgao")),
        "contextualizacao": _txt(plano.contextualizacao),
        "metas": _txt(plano.metas),
        "atividades": _txt(plano.atividades),
        "data_evento": format_periodo_evento_extenso(plano.data_evento_inicio, plano.data_evento_fim),
        "destinos": format_city_uf(plano.destino_display) if plano.destino_cidade_id else "",
        "horario_de_atendimento": _txt(plano.horario_atendimento),
        "efetivos": montar_efetivo_texto(plano),
        "unidade_movel": _txt(plano.unidade_movel_texto),
        "valor_do_plano": montar_valor_do_plano_texto(plano),
        "recursos_necessarios": _txt(plano.recursos_necessarios),
        "coordenacao": montar_texto_coordenacao(plano),
        "consideracao_final": _txt(plano.consideracao_final),
        "sede": _build_sede(inst),
        "data_extenso": format_data_extenso(timezone.localdate()),
        "nome_chefia": format_document_display(nome_chefia) if nome_chefia else "",
        "cargo_chefia": format_document_display(cargo_chefia) if cargo_chefia else "",
    }
