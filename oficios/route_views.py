import logging
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
from roteiros.services.autosave import apply_roteiro_autosave
from roteiros.services.autosave import build_roteiro_draft
from roteiros.services.autosave import has_minimum_roteiro_content
from roteiros.services import atualizar_roteiro, carregar_opcoes_rotas_avulsas_salvas, montar_contexto_editor_roteiro, montar_estado_editor_roteiro_evento_selecionado, montar_initial_roteiro_evento_sem_datas, normalizar_destinos_e_trechos_apos_erro_post, preparar_estado_editor_roteiro_para_get, preparar_querysets_formulario_roteiro, roteiro_state_equivalente_ao_roteiro, validar_submissao_editor_roteiro
from .presenters import apresentar_oficio_wizard_summary
from .selectors import get_oficio_by_id
from .services import avaliar_oficio_dados_viajantes
from .services import resolver_roteiro_padrao_evento
from .services import obter_roteiro_escolhido_do_post
from .services import vincular_roteiro_ao_oficio_sem_copia
from .services import tocar_data_criacao_oficio
from .view_navigation import oficio_back_label as _oficio_back_label
from .view_navigation import oficio_back_url as _oficio_back_url
from .view_helpers import _redirect_lista_oficio, _wizard_normalizar_acao, _wizard_footer_ctx, _wizard_shell_ctx, _wizard_roteiro_step_status


def _resolver_roteiro_rascunho_autosave(post, *, oficio):
    """Resolve um rascunho de Roteiro ja criado por autosave nesta mesma edicao
    (o JS guarda o pk em `autosave_obj_id` assim que o primeiro autosave cria a linha)."""
    raw = (post.get("autosave_obj_id") or "").strip()
    if not raw:
        return None
    try:
        pk = int(raw)
    except (TypeError, ValueError):
        return None
    return (
        Roteiro.objects.filter(
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
    roteiro = build_roteiro_draft(area=area)
    version = apply_roteiro_autosave(roteiro, clean_fields, payload.snapshots)
    if not roteiro.origem_cidade_id and not roteiro.origem_estado_id:
        # A sede exibida na tela (herdada do evento/config) nao chega "suja" no payload de
        # autosave se o usuario nunca clicou nela — sem isso o rascunho nasceria sem sede.
        from cadastros.services import resolver_sede_ids_desde_configuracao

        estado_id, cidade_id, _aviso = resolver_sede_ids_desde_configuracao()
        if estado_id and cidade_id:
            roteiro.origem_estado_id = estado_id
            roteiro.origem_cidade_id = cidade_id
            roteiro.save(update_fields=["origem_estado", "origem_cidade", "updated_at"])
    oficio.roteiro = roteiro
    oficio.save(update_fields=["roteiro", "updated_at"])
    return autosave_json_response(ok=True, object_id=roteiro.pk, created=True, version=version)


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
        if form.is_valid() and validated["ok"]:
            roteiro_escolhido = obter_roteiro_escolhido_do_post(
                request.POST,
                evento=oficio.evento,
                area=oficio.area,
            )
            if roteiro_escolhido and roteiro_state_equivalente_ao_roteiro(roteiro_escolhido, roteiro_state, validated):
                # Sem alterações: vincular diretamente ao roteiro selecionado
                rascunho_antigo = roteiro_vinculado if (roteiro_vinculado and roteiro_vinculado.status == Roteiro.STATUS_RASCUNHO) else None
                vincular_roteiro_ao_oficio_sem_copia(oficio, roteiro_escolhido, rascunho_antigo=rascunho_antigo)
            else:
                # Com alterações (ou roteiro próprio): salvar sempre num rascunho
                # Nunca modificar um roteiro não-rascunho que pertence a outros ofícios
                if roteiro_vinculado is None or roteiro_vinculado.status != Roteiro.STATUS_RASCUNHO:
                    roteiro_vinculado = Roteiro(tipo=Roteiro.TIPO_AVULSO, status=Roteiro.STATUS_RASCUNHO)
                    form.instance = roteiro_vinculado
                roteiro_salvo = atualizar_roteiro(roteiro_vinculado, form, roteiro_state, validated, diarias_resultado)
                if oficio.roteiro_id != roteiro_salvo.pk:
                    oficio.roteiro = roteiro_salvo
                    oficio.save(update_fields=["roteiro", "updated_at"])
            oficio = tocar_data_criacao_oficio(oficio)
            nav_action = _wizard_normalizar_acao(request.POST)
            if nav_action == "wizard_next":
                messages.success(
                    request,
                    "Roteiro e diárias salvos. Continue para a próxima etapa quando estiver pronto.",
                )
                if oficio_exige_justificativa(oficio):
                    return redirect("oficios:wizard_justificativa", pk=oficio.pk)
                return redirect("oficios:wizard_documentos", pk=oficio.pk)
            if nav_action == "wizard_back":
                messages.success(request, "Roteiro e diárias salvos.")
                return redirect("oficios:dados_viajantes", pk=oficio.pk)
            if nav_action == "save_draft_list":
                return _redirect_lista_oficio(request, oficio, "Roteiro e diárias salvos.")
            messages.success(request, "Rascunho do roteiro salvo.")
            return redirect("oficios:wizard_roteiro", pk=oficio.pk)
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
        roteiro_padrao_evento = resolver_roteiro_padrao_evento(oficio.evento)
        if roteiro_padrao_evento is not None:
            destinos_atuais, trechos_list, roteiro_state = montar_estado_editor_roteiro_evento_selecionado(
                roteiro_padrao_evento
            )
            form_instance = Roteiro(
                tipo=Roteiro.TIPO_AVULSO,
                status=Roteiro.STATUS_RASCUNHO,
                origem_cidade=roteiro_padrao_evento.origem_cidade,
                origem_estado=roteiro_padrao_evento.origem_estado,
                observacoes=roteiro_padrao_evento.observacoes,
            )
        else:
            initial = montar_initial_roteiro_evento_sem_datas(oficio.evento)
            destinos_atuais, trechos_list, roteiro_state = preparar_estado_editor_roteiro_para_get(
                initial=initial
            )
            form_instance = Roteiro(tipo=Roteiro.TIPO_AVULSO, status=Roteiro.STATUS_RASCUNHO)
            if initial.get("origem_cidade"):
                form_instance.origem_cidade_id = initial["origem_cidade"]
            if initial.get("origem_estado"):
                form_instance.origem_estado_id = initial["origem_estado"]
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
