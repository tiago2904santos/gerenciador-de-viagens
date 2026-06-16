"""Contexto docxtpl (placeholders planos) para o modelo plano_trabalho.docx."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from cadastros.selectors import build_configuracao_context
from documentos.services.formatters import format_city_uf
from documentos.services.formatters import format_document_display
from oficios.docxtpl_context import _assinatura_nome_cargo
from oficios.docxtpl_context import _build_endereco
from oficios.docxtpl_context import _build_sede

from .models import EventoPlano
from .models import PlanoTrabalho


def _txt(value: object) -> str:
    return str(value or "").strip()


def _destinos_unicos(plano: PlanoTrabalho) -> str:
    """Lista única (dedup) de destinos do plano e de todos os eventos."""
    labels: list[str] = []
    seen: set[str] = set()
    # Destinos plano-level
    if plano.pk:
        for d in plano.destinos.select_related("cidade").order_by("ordem", "pk"):
            if d.cidade_id:
                label = format_city_uf(f"{d.cidade.nome}/{d.cidade.uf}")
                if label and label not in seen:
                    seen.add(label)
                    labels.append(label)
    if not labels and plano.destino_cidade_id:
        label = format_city_uf(f"{plano.destino_cidade.nome}/{plano.destino_cidade.uf}")
        seen.add(label)
        labels.append(label)
    return ", ".join(labels)


def _data_evento_agregada(plano: PlanoTrabalho) -> str:
    from .services import format_periodo_evento_extenso

    if plano.is_multi_evento and plano.pk:
        eventos = list(plano.eventos.exclude(data_evento_inicio__isnull=True))
        if eventos:
            inicio = min(e.data_evento_inicio for e in eventos)
            fim = max((e.data_evento_fim or e.data_evento_inicio) for e in eventos)
            return format_periodo_evento_extenso(inicio, fim)
        return ""
    return format_periodo_evento_extenso(plano.data_evento_inicio, plano.data_evento_fim)


def build_plano_docxtpl_context(plano: PlanoTrabalho) -> dict[str, Any]:
    from .services import (
        _atividades_combinadas_multi,
        _atividades_selecionadas_ordenadas,
        format_data_extenso,
        montar_atividades_multi_texto,
        montar_atividades_texto,
        montar_atuacao_texto,
        montar_efetivo_texto,
        montar_metas_multi_texto,
        montar_metas_texto,
        montar_recursos_multi_texto,
        montar_recursos_texto,
        montar_texto_coordenacao,
        montar_unidade_movel_texto,
        montar_valor_multi_texto,
        montar_valor_do_plano_texto,
    )

    multi = bool(plano.is_multi_evento and plano.pk)
    if multi:
        _itens = _atividades_combinadas_multi(plano)
        metas_txt = montar_metas_multi_texto(plano)
        atividades_txt = montar_atividades_multi_texto(plano)
        recursos_txt = montar_recursos_multi_texto(plano)
        valor_txt = montar_valor_multi_texto(plano)
    else:
        _itens = _atividades_selecionadas_ordenadas(plano)
        metas_txt = montar_metas_texto(_itens)
        atividades_txt = _txt(plano.atividades) or montar_atividades_texto(_itens)
        recursos_txt = montar_recursos_texto(_itens)
        valor_txt = montar_valor_do_plano_texto(plano)

    inst = build_configuracao_context()
    nome_chefia, cargo_chefia = _assinatura_nome_cargo(inst, "PLANO_TRABALHO")

    destinos_display = _destinos_unicos(plano) if plano.is_multi_evento else (
        format_city_uf(plano.destino_display) if plano.destino_cidade_id else ""
    )

    contexto: dict[str, Any] = {
        "numero_plano_trabalho": plano.numero_formatado if plano.numero else "—",
        "unidade": _txt(inst.get("unidade")) or _txt(inst.get("nome_orgao")),
        "contextualizacao": _txt(plano.contextualizacao),
        "metas": metas_txt,
        "atividades": atividades_txt,
        # Seção 4 (ATUAÇÃO) num placeholder único: single = estrutura fixa, multi = por evento.
        "atuacao": montar_atuacao_texto(plano),
        # Mantidos para retrocompatibilidade do template (single-event usa estes).
        "data_evento": _data_evento_agregada(plano),
        "destinos": destinos_display,
        "horario_de_atendimento": _txt(plano.horario_atendimento),
        "efetivos": montar_efetivo_texto(plano),
        "unidade_movel": montar_unidade_movel_texto(_itens),
        "valor_do_plano": valor_txt,
        "recursos_necessarios": recursos_txt,
        # Em modo automático regenera (garante admin-only no multi e evita texto obsoleto);
        # se o usuário editou à mão (coordenacao_auto=False), respeita o texto salvo.
        "coordenacao": montar_texto_coordenacao(plano)
        if plano.coordenacao_auto
        else _txt(plano.coordenacao),
        "consideracao_final": _txt(plano.consideracao_final),
        "divisao": _txt(inst.get("divisao")).upper(),
        "unidade_rodape": format_document_display(
            _txt(inst.get("divisao") or inst.get("unidade") or inst.get("nome_orgao"))
        ),
        "endereco": _build_endereco(inst),
        "telefone": _txt(inst.get("telefone_formatado") or inst.get("telefone")),
        "email": (_txt(inst.get("email")) or "").lower(),
        "sede": _build_sede(inst),
        "data_extenso": format_data_extenso(timezone.localdate()),
        "nome_chefia": format_document_display(nome_chefia) if nome_chefia else "",
        "cargo_chefia": format_document_display(cargo_chefia) if cargo_chefia else "",
        # Flag usada pelo template para alternar a seção ATUAÇÃO ({%p if is_multi_evento %}).
        # As demais seções multi-evento (metas/atividades/valor/recursos) já vêm prontas,
        # agrupadas por evento, nas variáveis de texto acima.
        "is_multi_evento": multi,
    }

    return contexto
