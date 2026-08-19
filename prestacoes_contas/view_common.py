from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from core.tenancy import filter_queryset_by_area, get_current_area
from core.presenters.text import join_non_empty
from core.utils.masks import format_protocolo

from .forms import CAMPOS_COM_MODELO, CAMPOS_CUSTEIO_COM_OUTRO
from .models import DiarioBordo, PrestacaoContas, PrestacaoServidor, RelatorioTecnico


def _area_related_queryset(queryset, area_field="prestacao__area"):
    area = get_current_area()
    if area is None:
        return queryset.filter(**{f"{area_field}__isnull": True})
    return queryset.filter(**{area_field: area})


def _prestacao_queryset():
    return filter_queryset_by_area(PrestacaoContas.objects)


def _prestacao_servidor_queryset():
    return _area_related_queryset(PrestacaoServidor.objects)


def _relatorio_queryset():
    return _area_related_queryset(RelatorioTecnico.objects)


def _diario_queryset():
    return _area_related_queryset(DiarioBordo.objects)


def _destino_display(oficio) -> str:
    try:
        destinos = list(oficio.roteiro.destinos.select_related("cidade", "estado").order_by("ordem"))
        if not destinos:
            return ""
        parts = [f"{d.cidade} ({d.estado.sigla})" for d in destinos[:3]]
        result = ", ".join(parts)
        if len(destinos) > 3:
            result += f" +{len(destinos) - 3}"
        return result
    except (AttributeError, TypeError, ValueError):
        return ""


def _periodo_display(oficio) -> str:
    try:
        from django.utils import timezone as tz_module
        roteiro = oficio.roteiro
        saida_dt = roteiro.saida_dt
        if not saida_dt:
            return ""
        current_tz = tz_module.get_current_timezone()
        saida = saida_dt.astimezone(current_tz).date() if tz_module.is_aware(saida_dt) else saida_dt.date()
        chegada_dt = getattr(roteiro, "retorno_chegada_dt", None) or getattr(roteiro, "chegada_dt", None)
        if chegada_dt:
            chegada = chegada_dt.astimezone(current_tz).date() if tz_module.is_aware(chegada_dt) else chegada_dt.date()
            if saida == chegada:
                return saida.strftime("%d/%m/%Y")
            return f"{saida.strftime('%d/%m/%Y')} a {chegada.strftime('%d/%m/%Y')}"
        return saida.strftime("%d/%m/%Y")
    except (AttributeError, TypeError, ValueError):
        return ""


def _build_campos_modelo(form) -> list:
    """Para cada campo de texto longo: select de modelos + textarea + URL de gerência."""
    base_url = reverse("prestacoes_contas:modelos_index")
    campos = []
    for campo, label in CAMPOS_COM_MODELO:
        select = form[f"modelo_{campo}"]
        campos.append(
            {
                "campo": campo,
                "label": label,
                "select": select,
                "textarea": form[campo],
                "manage_url": f"{base_url}#grupo-{campo}",
                "tem_modelos": select.field.queryset.exists(),
                "section_id": f"rt-topic-{campo}-title",
            }
        )
    return campos


def _build_campos_custeio(form) -> list:
    campos = [
        {
            "campo": "diaria",
            "label": "Diária",
            "field": form["diaria"],
            "other": None,
            "uses_other": False,
        }
    ]
    for campo, label in CAMPOS_CUSTEIO_COM_OUTRO:
        campos.append(
            {
                "campo": campo,
                "label": label,
                "field": form[campo],
                "other": form[f"{campo}_outro"],
                "uses_other": True,
            }
        )
    return campos


def _servidor_identificacao(ps) -> dict:
    from oficios.presenters import _iniciais_nome_servidor

    servidor = ps.servidor
    cargo = str(servidor.cargo) if servidor.cargo_id else "—"
    unidade = str(servidor.unidade) if servidor.unidade_id else ""
    cpf = servidor.cpf_formatado
    cpf_display = f"CPF {cpf}" if cpf and cpf != "—" else ""
    return {
        "ps_pk": ps.pk,
        "nome_servidor": servidor.nome,
        "cpf_servidor": cpf,
        "cargo": cargo,
        "unidade": unidade,
        "meta": join_non_empty([cargo, unidade, cpf_display]),
        "is_motorista": ps.is_motorista,
        "numero_solicitacao": ps.numero_solicitacao,
        "iniciais": _iniciais_nome_servidor(servidor.nome),
    }


def _servidor_removido_identificacao(ps) -> dict:
    """`DB-06`: quem saiu da equipe, com a data e o que ficou guardado dele."""
    identificacao = _servidor_identificacao(ps)
    guardados = []
    if ps.numero_solicitacao.strip():
        guardados.append("número da solicitação")
    if ps.documentos_anexos.exists():
        guardados.append("comprovante")
    if ps.assinaturas.exists():
        guardados.append("assinatura")
    identificacao["removida_em"] = ps.removida_em
    identificacao["guardados"] = ", ".join(guardados)
    return identificacao


def _build_identificacao(prestacao) -> dict:
    """Identificação de nível ofício + lista de servidores da prestação."""
    from .selectors import servidores_removidos_da_equipe

    oficio = prestacao.oficio
    servidores = [_servidor_identificacao(ps) for ps in prestacao.servidores_prestacao.all()]
    # `DB-06`: os que saíram da equipe levando dados junto. `objects` os esconde
    # em todo o resto do sistema — este é o único lugar onde reaparecem, para que
    # "preservado" não vire "sumido sem deixar endereço".
    removidos = [
        _servidor_removido_identificacao(ps)
        for ps in servidores_removidos_da_equipe(prestacao)
    ]
    return {
        "numero": oficio.numero_formatado,
        "protocolo": format_protocolo(oficio.protocolo) or "—",
        "data_oficio": oficio.data_criacao.strftime("%d/%m/%Y") if oficio.data_criacao else "—",
        "custeio": oficio.get_custeio_display() if oficio.custeio else "—",
        "destino": _destino_display(oficio) or "—",
        "periodo": _periodo_display(oficio) or "—",
        "servidores": servidores,
        "servidores_count": len(servidores),
        "servidores_removidos": removidos,
    }


def _primeiro_servidor(prestacao):
    return prestacao.servidores_prestacao.order_by("pk").first()


def _redirect_primeiro_servidor(request, prestacao, viewname):
    ps = _primeiro_servidor(prestacao)
    if ps is None:
        messages.error(request, "Esta prestação ainda não possui servidores.")
        return redirect("prestacoes_contas:index")
    return redirect(viewname, ps_pk=ps.pk)


def _build_prestacao_steps(ps, atual: str) -> list:
    """Etapas do wizard da prestação de contas (navegação por servidor)."""
    documentos_url = reverse("prestacoes_contas:documentos_servidor", args=[ps.pk])
    rt_url = reverse("prestacoes_contas:rt_servidor", args=[ps.pk])
    diario_url = reverse("prestacoes_contas:diario_servidor", args=[ps.pk])
    consolidado_url = reverse("prestacoes_contas:consolidado_servidor", args=[ps.pk])
    etapas = [
        ("rt", "Etapa 1", "Relatório Técnico", rt_url),
        ("diario", "Etapa 2", "Diário de Bordo", diario_url),
        ("documentos", "Etapa 3", "Documentos", documentos_url),
        ("consolidado", "Etapa 4", "PDF Final", consolidado_url),
    ]
    steps = []
    atingiu_atual = False
    for chave, _step_label, titulo, url in etapas:
        if chave == atual:
            state = "current"
            atingiu_atual = True
            status = "Em edição"
        elif atingiu_atual:
            state = ""
            status = "A seguir"
        else:
            state = "done"
            status = "Concluído"
        # Formato do `c-v2.stepper`: `label`, `status`, `state` e `url`. O
        # legado carregava também `marker`, `step_label`, `state_class` e
        # `aria_current` — quatro campos para dizer o que o componente novo
        # deduz do `state` e do índice do laço.
        #
        # A `url` FICA, ao contrário do stepper de ofício: aqui as quatro etapas
        # existem ao mesmo tempo e se visita a que interessa, como no painel do
        # evento. É a mesma razão pela qual o componente aceita etapa navegável.
        steps.append(
            {
                "label": titulo,
                "status": status,
                "state": state,
                "url": url,
            }
        )
    return steps


# `H-02`: as 5 telas do fluxo repetiam o mesmo `page_header` no template, com
# quatro constantes iguais e só o `status_label` variando. Como o rótulo da etapa
# já é dado por `_build_prestacao_steps`, ele sai daqui — o template deixa de
# carregar copy do módulo e a chave da etapa passa a ter um dono só.
_ROTULO_DA_ETAPA = {
    "rt": "Relatório Técnico",
    "diario": "Diário de Bordo",
    "documentos": "Documentos",
    "consolidado": "PDF Final",
}


def contexto_do_fluxo(ps, atual: str, *, back_label=None, back_url=None) -> dict:
    """Cabeçalho e stepper das telas de fluxo da prestação, num lugar só."""
    return {
        "wizard_page_steps": _build_prestacao_steps(ps, atual),
        "flow_eyebrow": "PRESTAÇÕES",
        "flow_icon_label": "PC",
        "flow_module_label": "Prestações de Contas",
        "flow_back_label": back_label or "Voltar à lista",
        "flow_back_url": back_url or reverse("prestacoes_contas:index"),
        "flow_status_label": _ROTULO_DA_ETAPA[atual],
        "flow_status_variant": "draft",
        # O selo da etapa no vocabulário do `c-v2.chip`: a prestação em curso é
        # trabalho em andamento, não conclusão.
        "flow_status_tone_v2": "progress",
    }


def _autosave_version(obj, field_name="atualizado_em") -> int:
    obj.refresh_from_db()
    value = getattr(obj, field_name, None)
    if value is None:
        return 0
    return int(timezone.localtime(value).timestamp())


def _autosave_form_errors(form):
    return {
        field: [str(item) for item in messages_list]
        for field, messages_list in form.errors.items()
    }


def _prestacao_full(pc_pk):
    return get_object_or_404(
        _prestacao_queryset().select_related("oficio__roteiro").prefetch_related(
            "servidores_prestacao__servidor__cargo",
            "servidores_prestacao__servidor__unidade",
            "servidores_prestacao__documentos_anexos",
            "documentos_anexos",
        ),
        pk=pc_pk,
    )


def _prestacao_servidor_full(ps_pk):
    return get_object_or_404(
        _prestacao_servidor_queryset()
        .select_related(
            "prestacao__oficio__roteiro",
            "servidor__cargo",
            "servidor__unidade",
        )
        .prefetch_related(
            "prestacao__servidores_prestacao__servidor__cargo",
            "prestacao__servidores_prestacao__servidor__unidade",
            "prestacao__servidores_prestacao__documentos_anexos",
            "prestacao__documentos_anexos",
            "documentos_anexos",
        ),
        pk=ps_pk,
    )


def _is_inline_request(request) -> bool:
    """Indica se o PDF deve ser servido embutido (iframe) em vez de baixado."""
    return (request.GET.get("inline") or "").strip() in {"1", "true", "sim"}


def _preview_error_response(exc) -> HttpResponse:
    """Mensagem amigável renderizada dentro do iframe quando a geração falha."""
    html = (
        '<!doctype html><html lang="pt-br"><head><meta charset="utf-8">'
        '<style>body{margin:0;display:flex;align-items:center;justify-content:center;'
        "min-height:100vh;font-family:system-ui,sans-serif;color:#52657a;background:#f8fafd;}"
        ".msg{max-width:32rem;padding:1.5rem;text-align:center;line-height:1.5;}</style>"
        "</head><body><div class=\"msg\">"
        "<strong>Não foi possível gerar a pré-visualização.</strong><br>"
        f"{escape(str(exc))}</div></body></html>"
    )
    return HttpResponse(html, content_type="text/html; charset=utf-8", status=422)
