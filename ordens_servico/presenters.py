from __future__ import annotations

from django.urls import reverse
from django.utils import timezone

from core import entity_cards
from oficios.presenters import _iniciais_nome_servidor


_ASSINANTE_NAO_RESOLVIDO = object()


def get_assinante_os(area=None) -> dict | None:
    try:
        from cadastros.models import AssinaturaConfiguracao
        from cadastros.selectors import get_configuracao_sistema

        config = get_configuracao_sistema(area=area)
        ass = (
            config.assinaturas
            .filter(tipo=AssinaturaConfiguracao.ORDEM_SERVICO, ativo=True)
            .select_related("servidor__cargo")
            .order_by("ordem")
            .first()
        )
        if ass and ass.servidor:
            srv = ass.servidor
            return {
                "nome": srv.nome,
                "cargo": srv.cargo.nome if srv.cargo_id and srv.cargo else "",
            }
    except Exception:
        pass
    return None


def _temporal_badge_os(ordem):
    inicio = ordem.data_evento_inicio
    if not inicio:
        return None, "muted"
    fim = ordem.data_evento_fim or inicio
    today = timezone.localdate()
    if today < inicio:
        dias = (inicio - today).days
        if dias == 1:
            return "falta 1 dia", "warning"
        return f"faltam {dias} dias", "warning"
    if inicio <= today <= fim:
        if today == inicio:
            return "começa hoje", "info"
        return "em andamento", "info"
    dias = (today - fim).days
    if dias == 0:
        return "foi hoje", "success"
    if dias == 1:
        return "foi ontem", "success"
    return f"há {dias} dias", "success"


def _servidores_display_os(ordem):
    motorista_pks = set()
    for oficio in ordem.oficios.all():
        if oficio.motorista_id:
            motorista_pks.add(oficio.motorista_id)

    cards = []
    for servidor in ordem.servidores.all():
        cargo_nome = servidor.cargo.nome if servidor.cargo_id and servidor.cargo else ""
        unidade_nome = str(servidor.unidade) if servidor.unidade_id else ""
        cards.append(
            {
                "initials": _iniciais_nome_servidor(servidor.nome),
                "name": servidor.nome,
                "cargo": cargo_nome,
                "unidade": unidade_nome,
                "is_motorista": servidor.pk in motorista_pks,
            },
        )
    return cards


def _destinos_display_os(ordem):
    # `.all()` aproveita o `Prefetch` do selector (ja ordenado por nome, com o
    # estado junto). Reordenar ou refazer `select_related` aqui descartaria o
    # cache e custaria uma query por card — era o `NOVO-07`.
    destinos = list(ordem.destinos.all())
    if not destinos:
        return ""
    parts = [f"{d.nome} ({d.estado.sigla})" for d in destinos[:3]]
    result = ", ".join(parts)
    if len(destinos) > 3:
        result += f" +{len(destinos) - 3}"
    return result


def _oficios_vinculados_os(ordem):
    items = []
    for oficio in ordem.oficios.all():
        try:
            url = reverse("oficios:dados_viajantes", args=[oficio.pk])
        except Exception:
            url = ""
        protocolo = ""
        try:
            from core.utils.masks import format_protocolo
            protocolo = format_protocolo(oficio.protocolo) or ""
        except Exception:
            pass
        items.append(
            {
                "numero": oficio.numero_formatado,
                "protocolo": protocolo,
                "url": url,
            },
        )
    return items


def _periodo_display_curto(ordem) -> str:
    inicio = ordem.data_evento_inicio
    fim = ordem.data_evento_fim
    if not inicio:
        return ""
    if not fim or fim == inicio:
        return inicio.strftime("%d/%m")
    if inicio.year == fim.year:
        return f"{inicio.strftime('%d/%m')} a {fim.strftime('%d/%m')}"
    return f"{inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}"


def apresentar_ordem_servico_card(ordem, *, assinante=_ASSINANTE_NAO_RESOLVIDO,
                                  menus_sob_demanda=True):
    """Card da Ordem de Serviço.

    `menus_sob_demanda` liga o `PF-04`: o menu sai com `src` e o corpo dele não vai
    no HTML da lista — quem serve é `ordens_servico:card_menus`, no primeiro
    clique. O endpoint chama este mesmo presenter com `False`.
    """
    menus_src = reverse("ordens_servico:card_menus", args=[ordem.pk]) if menus_sob_demanda else ""

    """Monta o card de uma OS.

    `assinante` e o mesmo para todas as OS da pagina — quem monta uma lista
    resolve uma vez com `get_assinante_os()` e passa aqui. O padrao resolve
    sozinho, para quem exibe um card so.
    """
    if assinante is _ASSINANTE_NAO_RESOLVIDO:
        assinante = get_assinante_os(area=getattr(ordem, "area", None))

    data_criacao_display = ""
    if ordem.created_at:
        try:
            tz = timezone.get_current_timezone()
            dt = ordem.created_at
            if timezone.is_aware(dt):
                dt = dt.astimezone(tz)
            data_criacao_display = dt.strftime("%d/%m/%Y")
        except Exception:
            pass

    temporal_label, temporal_tone = _temporal_badge_os(ordem)

    motivo = (ordem.motivo or "").strip()
    motivo_resumido = motivo
    if len(motivo) > 240:
        motivo_resumido = motivo[:240] + "…"

    numero_display = ordem.numero_formatado
    destinos_display = _destinos_display_os(ordem)
    periodo_display = _periodo_display_curto(ordem)
    servidores = _servidores_display_os(ordem)
    oficios_vinculados = _oficios_vinculados_os(ordem)

    header_value = " · ".join(
        parte for parte in [numero_display, destinos_display, periodo_display] if parte
    )
    header_chips = []
    if temporal_label:
        header_chips.append(entity_cards.chip(temporal_tone, temporal_label))
    if ordem.cancelado:
        header_chips.append(entity_cards.chip("danger", "Cancelada"))

    search_parts = [numero_display, destinos_display, motivo]
    search_parts.extend(s["name"] for s in servidores)
    search_parts.extend(o["numero"] for o in oficios_vinculados)

    editar_url = reverse("ordens_servico:editar", args=[ordem.pk])
    excluir_url = reverse("ordens_servico:excluir", args=[ordem.pk])

    return {
        "pk": ordem.pk,
        "search_text": " ".join(p for p in search_parts if p).strip(),
        "header": entity_cards.header(
            [entity_cards.header_item("Ordem de Serviço", header_value, wrap=True)],
            header_chips,
        ),
        "cancel_note": ordem.motivo_cancelamento if ordem.cancelado else "",
        "footer": entity_cards.footer(
            edit_url=editar_url,
            edit_aria="Editar Ordem de Serviço",
            menus=[
                entity_cards.documents_menu(
                    f"os-document-menu-{ordem.pk}",
                    numero_display,
                    title="Ordem de Serviço",
                    view_url=reverse("ordens_servico:pdf_inline", args=[ordem.pk]),
                    pdf_url=reverse("ordens_servico:baixar_pdf", args=[ordem.pk]),
                    docx_url=reverse("ordens_servico:baixar_docx", args=[ordem.pk]),
                    view_title="Visualizar documento",
                    view_description="Abrir a Ordem de Serviço",
                    docx_description="Arquivo editável da Ordem de Serviço",
                    trigger_aria=f"Abrir documentos da Ordem de Serviço {numero_display}",
                    src=menus_src,
                )
            ],
            delete_modal_url=excluir_url,
            delete_modal_label=numero_display,
            delete_aria="Excluir Ordem de Serviço",
        ),
        "numero_display": numero_display,
        "data_criacao_display": data_criacao_display,
        "periodo_display": periodo_display,
        "destinos_display": destinos_display,
        "temporal_label": temporal_label,
        "temporal_tone": temporal_tone,
        "servidores": servidores,
        # `len` da lista ja materializada. Ao contrario do que a auditoria
        # supoe, `.count()` aqui NAO custava query: `QuerySet.count()` devolve
        # `len(self._result_cache)` quando o prefetch ja preencheu o cache, e o
        # canario confirmou (trocar de volta nao muda a contagem). O `len` fica
        # porque nao depende do prefetch existir — um chamador que monte o card
        # sem ele pagaria a consulta.
        "servidores_count": len(servidores),
        "oficios_vinculados": oficios_vinculados,
        "cancelado": ordem.cancelado,
        "motivo_cancelamento": ordem.motivo_cancelamento,
        "motivo": motivo,
        "motivo_resumido": motivo_resumido,
        "assinante": assinante,
        "editar_url": editar_url,
        "docx_url": reverse("ordens_servico:baixar_docx", args=[ordem.pk]),
        "pdf_url": reverse("ordens_servico:baixar_pdf", args=[ordem.pk]),
        "visualizar_url": reverse("ordens_servico:pdf_inline", args=[ordem.pk]),
        "excluir_url": excluir_url,
    }
