from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.decorators.http import require_POST
from core.autosave import AutosavePayloadError
from core.autosave import autosave_json_response
from core.autosave import filter_allowed_fields
from core.autosave import parse_autosave_payload
from justificativas.services import oficio_exige_justificativa
from roteiros.forms import RoteiroForm
from roteiros.models import Roteiro
from roteiros.services.autosave import ROTEIRO_AUTOSAVE_FIELDS
from roteiros.services.autosave import has_minimum_roteiro_content
from roteiros.services.autosave import pk_de_autosave
from roteiros.presenters import montar_contexto_editor_roteiro
from roteiros.services import carregar_opcoes_rotas_avulsas_salvas, normalizar_destinos_e_trechos_apos_erro_post, preparar_estado_editor_roteiro_para_get, preparar_querysets_formulario_roteiro, validar_submissao_editor_roteiro
from .presenters import apresentar_oficio_wizard_summary
from .selectors import get_oficio_by_id
from .services import avaliar_oficio_dados_viajantes
from .services import criar_rascunho_de_roteiro_do_oficio
from .services import montar_roteiro_inicial_do_oficio
from .services import salvar_rascunho_parcial_do_oficio
from .services import salvar_roteiro_do_oficio
from .view_navigation import oficio_back_label as _oficio_back_label
from .view_navigation import oficio_back_url as _oficio_back_url
from core.wizard import normalizar_acao_do_wizard

from .view_helpers import _redirect_lista_oficio, _wizard_footer_ctx, _wizard_shell_ctx, _wizard_roteiro_step_status


def _resolver_roteiro_rascunho_autosave(post, *, oficio):
    """Resolve um rascunho de Roteiro ja criado por autosave nesta mesma edicao
    (o JS guarda o pk em `autosave_obj_id` assim que o primeiro autosave cria a linha)."""
    pk = pk_de_autosave(post)
    if pk is None:
        return None
    return (
        # `BE-09`: `all_objects` — o escopo é a área do **ofício**, na linha de baixo.
        Roteiro.all_objects.filter(
            pk=pk,
            area_id=oficio.area_id,
            tipo=Roteiro.TIPO_AVULSO,
            status=Roteiro.STATUS_RASCUNHO,
        )
        .filter(Q(oficios__isnull=True) | Q(oficios=oficio))
        .distinct()
        .first()
    )


@require_POST
def wizard_roteiro_autosave_criar(request, pk):
    """Cria (via autosave) o rascunho de roteiro proprio do oficio e ja vincula ao oficio.

    Sem isso, desmarcar o roteiro do evento (item "Roteiro novo") e comecar a preencher
    um roteiro proprio nao sobrevive a uma nova visita a etapa: como `oficio.roteiro_id`
    continua None ate o save final, a proxima GET volta a sugerir o roteiro do evento
    (ver `resolver_roteiro_padrao_evento`), fazendo parecer que "desmarcar" nao funciona.
    """
    oficio = get_oficio_by_id(pk)
    if oficio.roteiro_id:
        return autosave_json_response(ok=True, object_id=oficio.roteiro_id, created=False)

    try:
        payload = parse_autosave_payload(request, expected_model="roteiro")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    clean_fields = filter_allowed_fields(payload.fields, payload.dirty_fields, ROTEIRO_AUTOSAVE_FIELDS)
    if not has_minimum_roteiro_content(clean_fields, payload.snapshots):
        return autosave_json_response(ok=False, message="Conteúdo insuficiente para criar rascunho.")

    area = oficio.area or getattr(request, "area", None)
    if area is None:
        # Compatibilidade transitória para ofícios legados ainda sem área:
        # a configuração resolve uma área explícita (única ou técnica), nunca NULL.
        from cadastros.models import ConfiguracaoSistema

        area = ConfiguracaoSistema.get_singleton().area
    roteiro, version = criar_rascunho_de_roteiro_do_oficio(
        oficio, area=area, campos=clean_fields, snapshots=payload.snapshots
    )
    return autosave_json_response(ok=True, object_id=roteiro.pk, created=True, version=version)


def _redirect_after_roteiro_save(
    request,
    oficio,
    nav_action,
    *,
    nivel,
    msg_next,
    msg_back,
    msg_lista=None,
    msg_default=None,
):
    """Traduz a ação do rodapé em redirect, depois de a Etapa 2 ter gravado.

    `BE-12`: as duas cadeias `if nav_action == …` da view eram a mesma coisa com textos
    diferentes. `wizard_next` desvia para a justificativa quando a antecedência da saída a
    torna obrigatória — e por isso a checagem tem de vir **depois** da gravação, que é
    quem grava a data de saída. Segue o par já existente em `traveler_views.py`
    (`_redirect_after_dados_viajantes_save`, `_redirect_after_transporte_save`).

    `nav_action` chega já normalizado por `normalizar_acao_do_wizard`, nunca cru.
    """
    if nav_action == "wizard_next":
        nivel(request, msg_next)
        if oficio_exige_justificativa(oficio):
            return redirect("oficios:wizard_justificativa", pk=oficio.pk)
        return redirect("oficios:wizard_documentos", pk=oficio.pk)
    if nav_action == "wizard_back":
        nivel(request, msg_back)
        return redirect("oficios:dados_viajantes", pk=oficio.pk)
    if nav_action == "save_draft_list" and msg_lista is not None:
        return _redirect_lista_oficio(request, oficio, msg_lista)
    nivel(request, msg_default or msg_back)
    return redirect("oficios:wizard_roteiro", pk=oficio.pk)


def wizard_roteiro(request, pk):
    oficio = get_oficio_by_id(pk)
    # Nao cria mais um Roteiro vazio so por abrir a etapa: enquanto o oficio nao tiver
    # roteiro proprio, o form so ganha uma linha no banco quando o autosave (mesmo
    # mecanismo ja usado no fluxo avulso) detectar conteudo minimo, ou no save final.
    roteiro_vinculado = oficio.roteiro
    qtd_viajantes = oficio.servidores.count()

    route_options, route_state_map = carregar_opcoes_rotas_avulsas_salvas(
        evento=oficio.evento, excluir_pk=roteiro_vinculado.pk if roteiro_vinculado else None
    )

    if request.method == "POST":
        if roteiro_vinculado is None:
            roteiro_vinculado = _resolver_roteiro_rascunho_autosave(
                request.POST,
                oficio=oficio,
            )
        form = RoteiroForm(request.POST, instance=roteiro_vinculado)
        preparar_querysets_formulario_roteiro(
            form, method=request.method, post=request.POST, instance=roteiro_vinculado
        )
        roteiro_state, validated, diarias_resultado = validar_submissao_editor_roteiro(
            request.POST, route_state_map, roteiro=roteiro_vinculado
        )
        nav_action = normalizar_acao_do_wizard(request.POST)
        if form.is_valid() and validated["ok"]:
            resultado = salvar_roteiro_do_oficio(
                oficio,
                request.POST,
                form,
                roteiro_state=roteiro_state,
                validated=validated,
                diarias_resultado=diarias_resultado,
                roteiro_vinculado=roteiro_vinculado,
            )
            roteiro_vinculado = resultado.roteiro
            return _redirect_after_roteiro_save(
                request,
                oficio,
                nav_action,
                nivel=messages.success,
                msg_next="Roteiro e diárias salvos. Continue para a próxima etapa quando estiver pronto.",
                msg_back="Roteiro e diárias salvos.",
                msg_lista="Roteiro e diárias salvos.",
                msg_default="Rascunho do roteiro salvo.",
            )

        if nav_action in ("wizard_next", "wizard_back"):
            # Soft-advance: grava rascunho parcial e deixa navegar sem validação completa.
            resultado = salvar_rascunho_parcial_do_oficio(
                oficio,
                form,
                roteiro_state=roteiro_state,
                validated=validated,
                roteiro_vinculado=roteiro_vinculado,
            )
            roteiro_vinculado = resultado.roteiro
            return _redirect_after_roteiro_save(
                request,
                oficio,
                nav_action,
                nivel=messages.info,
                msg_next="Roteiro incompleto salvo como rascunho. Você pode completar depois.",
                msg_back="Roteiro incompleto salvo como rascunho.",
            )

        for error in validated.get("errors", []):
            form.add_error(None, error)
        destinos_atuais, trechos_list = normalizar_destinos_e_trechos_apos_erro_post(roteiro_state)
    elif roteiro_vinculado is not None:
        destinos_atuais, trechos_list, roteiro_state = preparar_estado_editor_roteiro_para_get(
            roteiro=roteiro_vinculado
        )
        form_initial = {}
        if not (roteiro_vinculado.origem_estado_id or roteiro_vinculado.origem_cidade_id):
            se_id = roteiro_state.get("sede_estado_id")
            sc_id = roteiro_state.get("sede_cidade_id")
            if se_id:
                form_initial["origem_estado"] = se_id
            if sc_id:
                form_initial["origem_cidade"] = sc_id
        form = RoteiroForm(
            instance=roteiro_vinculado,
            initial=form_initial if form_initial else None,
        )
        preparar_querysets_formulario_roteiro(
            form, method=request.method, post=request.POST, instance=roteiro_vinculado
        )
    else:
        # Oficio ainda sem roteiro proprio: pre-seleciona o roteiro do evento (se houver
        # um completo pronto pra reuso) ou parte de sede+destino do evento, sem datas e
        # sem persistir nada ainda.
        (
            form_instance,
            destinos_atuais,
            trechos_list,
            roteiro_state,
        ) = montar_roteiro_inicial_do_oficio(oficio)
        form = RoteiroForm(instance=form_instance)
        preparar_querysets_formulario_roteiro(
            form, method=request.method, post=request.POST, instance=form_instance
        )

    dados_av = avaliar_oficio_dados_viajantes(oficio=oficio)
    roteiro_status = _wizard_roteiro_step_status(oficio)
    context = montar_contexto_editor_roteiro(
        evento=None,
        form=form,
        obj=roteiro_vinculado,
        destinos_atuais=destinos_atuais,
        trechos_list=trechos_list,
        is_avulso=True,
        roteiro_state=roteiro_state,
        route_options=route_options,
        diarias_quantidade_servidores=qtd_viajantes,
    )
    context.update(
        {
            "page_title": "Cadastro de ofício",
            **_wizard_shell_ctx(
                oficio=oficio,
                etapa_atual="roteiro",
                dados_viajantes_status=dados_av["status"],
                roteiro_status=roteiro_status,
            ),
            "wizard_summary": apresentar_oficio_wizard_summary(oficio),
            "oficio": oficio,
            "wizard_back_url": _oficio_back_url(oficio),
            "wizard_back_label": _oficio_back_label(oficio),
            "roteiro_editor_oficio": True,
            "wizard_use_outer_form": False,
            **_wizard_footer_ctx(oficio),
        }
    )
    return render(request, "oficios/wizard_roteiro.html", context)
