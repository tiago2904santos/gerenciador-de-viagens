import re

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.autosave import (
    AutosavePayloadError,
    autosave_json_response,
    filter_allowed_fields,
    parse_autosave_payload,
)
from core.normalizers import normalize_spaces
from documentos.services.exceptions import DocumentValidationError

from .diario_services import diaria_info
from .forms import (
    CAMPOS_CUSTEIO_COM_OUTRO,
    OUTRO_VALUE,
    PrestacaoServidorDiariaForm,
    RelatorioTecnicoForm,
    get_custeio_valores_fixos,
)
from .models import PrestacaoServidor, RelatorioTecnico
from .services import (
    aplicar_diaria_recebida,
    diaria_inicial_da_prestacao,
    diaria_recebida_display,
    garantir_campos_padrao_relatorio_tecnico,
    gerar_relatorio_tecnico_docx,
    nome_arquivo_rt,
)
from .view_common import (
    _autosave_version,
    _build_campos_custeio,
    _build_campos_modelo,
    _build_identificacao,
    _build_prestacao_steps,
    _is_inline_request,
    _marcar_servidor_em_preenchimento,
    _marcar_servidores_pendentes,
    _prestacao_queryset,
    _prestacao_servidor_full,
    _prestacao_servidor_queryset,
    _preview_error_response,
    _redirect_primeiro_servidor,
    _relatorio_queryset,
)


def _salvar_diaria_overrides(prestacao, fields):
    """Salva os campos ``ps-<pk>-diaria_valor_override`` presentes em ``fields``.

    Usado tanto pelo autosave do RT (um campo por servidor no mesmo formulário)
    quanto pelo fallback sem JS do POST de ``rt_criar``.

    Devolve ``{nome_do_campo: [mensagens]}`` para o que foi recusado — vazio
    quando tudo entrou.
    """
    atualizacoes = {}
    for name, value in fields.items():
        match = re.match(r"^ps-(\d+)-diaria_valor_override$", str(name or ""))
        if match:
            atualizacoes[int(match.group(1))] = normalize_spaces(value or "")
    if not atualizacoes:
        return {}

    erros = {}
    servidores = PrestacaoServidor.objects.filter(pk__in=atualizacoes.keys(), prestacao=prestacao)
    for ps in servidores:
        texto = atualizacoes.get(ps.pk, "")
        anterior = (ps.diaria_valor_override, ps.diaria_valor_override_observacao)
        problemas = aplicar_diaria_recebida(ps, texto)
        if problemas:
            # Não grava nada deste servidor: um valor recusado não pode virar
            # meia gravação. O autosave devolve o erro no nome do campo, e a
            # tela mostra ao lado do input que o operador acabou de digitar.
            erros[f"ps-{ps.pk}-diaria_valor_override"] = problemas
            continue
        if (ps.diaria_valor_override, ps.diaria_valor_override_observacao) != anterior:
            ps.save(
                update_fields=[
                    "diaria_valor_override",
                    "diaria_valor_override_observacao",
                    "atualizado_em",
                ]
            )
    return erros


def _salvar_rt_autosave(relatorio, clean_fields):
    if not clean_fields:
        return
    update_fields = set()
    for campo, value in clean_fields.items():
        if campo.endswith("_outro"):
            base = campo.removesuffix("_outro")
            if base in {item[0] for item in CAMPOS_CUSTEIO_COM_OUTRO}:
                text = normalize_spaces(value or "")
                if text:
                    setattr(relatorio, base, text)
                    update_fields.add(base)
            continue
        if campo in {item[0] for item in CAMPOS_CUSTEIO_COM_OUTRO}:
            text = normalize_spaces(value or "")
            if text == OUTRO_VALUE:
                continue
            if text in get_custeio_valores_fixos(campo):
                setattr(relatorio, campo, text)
                update_fields.add(campo)
            continue
        setattr(relatorio, campo, normalize_spaces(value or ""))
        update_fields.add(campo)
    if update_fields:
        relatorio.save(update_fields=[*update_fields, "atualizado_em"])


def _servidor_rt_ctx(ps):
    return {
        "ps_pk": ps.pk,
        "nome": ps.servidor.nome,
        "is_motorista": ps.is_motorista,
        # O selo também acende quando só sobrou a observação: é o caso dos
        # valores legados que a migração não conseguiu virar número, e são
        # justamente os que alguém precisa olhar.
        "diaria_ajustada": bool(
            ps.diaria_valor_override is not None
            or ps.diaria_valor_override_observacao
        ),
        "diaria_form": PrestacaoServidorDiariaForm(instance=ps, prefix=f"ps-{ps.pk}"),
        "download_pdf_url": reverse(
            "prestacoes_contas:rt_download_servidor_formato", args=[ps.pk, "pdf"]
        ),
        "download_docx_url": reverse(
            "prestacoes_contas:rt_download_servidor_formato", args=[ps.pk, "docx"]
        ),
        "preview_inline_url": reverse(
            "prestacoes_contas:rt_download_servidor_formato", args=[ps.pk, "pdf"]
        ) + "?inline=1",
    }


def rt_criar(request, pc_pk):
    """Compatibilidade: redireciona para o primeiro servidor."""
    prestacao = get_object_or_404(_prestacao_queryset(), pk=pc_pk)
    return _redirect_primeiro_servidor(request, prestacao, "prestacoes_contas:rt_servidor")


def rt_servidor(request, ps_pk):
    """Edição do texto compartilhado do RT; preview/download só do servidor atual."""
    ps = _prestacao_servidor_full(ps_pk)
    prestacao = ps.prestacao

    relatorio, _ = RelatorioTecnico.objects.get_or_create(prestacao=prestacao)
    garantir_campos_padrao_relatorio_tecnico(relatorio)
    identificacao = _build_identificacao(prestacao)

    if request.method == "POST":
        form = RelatorioTecnicoForm(request.POST, instance=relatorio, relatorio=relatorio)
        if form.is_valid():
            form.save()
            erros = _salvar_diaria_overrides(prestacao, request.POST)
            _marcar_servidor_em_preenchimento(ps)
            if erros:
                for mensagens in erros.values():
                    for mensagem in mensagens:
                        messages.error(request, mensagem)
            else:
                messages.success(request, "Texto do relatório técnico salvo.")
            return redirect("prestacoes_contas:rt_servidor", ps_pk=ps.pk)
    else:
        initial = {}
        if not relatorio.diaria:
            initial["diaria"] = diaria_inicial_da_prestacao(prestacao)
        if not relatorio.motivo:
            initial["motivo"] = prestacao.oficio.motivo or ""
        form = RelatorioTecnicoForm(instance=relatorio, relatorio=relatorio, initial=initial)

    servidores_ctx = [_servidor_rt_ctx(ps)]

    return render(
        request,
        "prestacoes_contas/relatorio_tecnico_form.html",
        {
            "page_title": f"Relatório Técnico — {ps.servidor.nome}",
            "form": form,
            "campos_modelo": _build_campos_modelo(form),
            "campos_custeio": _build_campos_custeio(form),
            "relatorio": relatorio,
            "prestacao": prestacao,
            "ps": ps,
            "identificacao": identificacao,
            "servidores": servidores_ctx,
            "wizard_page_steps": _build_prestacao_steps(ps, "rt"),
            "diaria_info": diaria_info(prestacao),
            "back_url": reverse("prestacoes_contas:index"),
            "documentos_url": reverse("prestacoes_contas:documentos_servidor", args=[ps.pk]),
            "diario_url": reverse("prestacoes_contas:diario_servidor", args=[ps.pk]),
            "autosave_url": reverse("prestacoes_contas:rt_servidor_autosave", args=[ps.pk]),
            "preview_inline_url": servidores_ctx[0]["preview_inline_url"],
        },
    )


def rt_servidor_autosave(request, ps_pk):
    ps = get_object_or_404(_prestacao_servidor_queryset().select_related("prestacao"), pk=ps_pk)
    relatorio = get_object_or_404(_relatorio_queryset(), prestacao=ps.prestacao)
    try:
        payload = parse_autosave_payload(request, expected_model="relatorio_tecnico")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    allowed_fields = {
        "diaria",
        "translado",
        "combustivel",
        "passagem",
        "translado_outro",
        "combustivel_outro",
        "passagem_outro",
        "motivo",
        "atividade",
        "conclusao",
        "medidas",
        "info_complementares",
    }
    clean_fields = filter_allowed_fields(payload.fields, payload.dirty_fields, allowed_fields)
    _salvar_rt_autosave(relatorio, clean_fields)
    erros = _salvar_diaria_overrides(
        ps.prestacao,
        {name: payload.fields.get(name) for name in payload.dirty_fields},
    )
    if erros:
        return autosave_json_response(
            ok=False,
            errors=erros,
            message="O valor da diária não foi salvo.",
        )
    if payload.dirty_fields:
        _marcar_servidor_em_preenchimento(ps)
    return autosave_json_response(
        ok=True,
        object_id=relatorio.pk,
        version=_autosave_version(relatorio),
    )


def rt_autosave(request, pk):
    relatorio = get_object_or_404(_relatorio_queryset(), pk=pk)
    try:
        payload = parse_autosave_payload(request, expected_model="relatorio_tecnico")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    allowed_fields = {
        "diaria",
        "translado",
        "combustivel",
        "passagem",
        "translado_outro",
        "combustivel_outro",
        "passagem_outro",
        "motivo",
        "atividade",
        "conclusao",
        "medidas",
        "info_complementares",
    }
    clean_fields = filter_allowed_fields(payload.fields, payload.dirty_fields, allowed_fields)
    _salvar_rt_autosave(relatorio, clean_fields)
    erros = _salvar_diaria_overrides(
        relatorio.prestacao,
        {name: payload.fields.get(name) for name in payload.dirty_fields},
    )
    if erros:
        # O texto do RT já foi salvo acima; o que não entrou foi só o valor
        # recusado. Salvar automaticamente um valor que a regra proíbe seria
        # pior que devolver erro: ninguém revisa o que salvou sozinho.
        return autosave_json_response(
            ok=False,
            errors=erros,
            message="O valor da diária não foi salvo.",
        )
    if payload.dirty_fields:
        _marcar_servidores_pendentes(relatorio.prestacao)
    return autosave_json_response(
        ok=True,
        object_id=relatorio.pk,
        version=_autosave_version(relatorio),
    )


def rt_download_servidor(request, ps_pk, formato="docx"):
    ps = get_object_or_404(
        _prestacao_servidor_queryset().select_related(
            "prestacao__oficio__roteiro", "servidor"
        ),
        pk=ps_pk,
    )
    relatorio, _ = RelatorioTecnico.objects.get_or_create(prestacao=ps.prestacao)
    garantir_campos_padrao_relatorio_tecnico(relatorio)

    inline = _is_inline_request(request)
    formato = (formato or "docx").strip().lower()
    if formato == "pdf":
        try:
            from .assinatura_services import pdf_rt_assinado_ou_gerado
            conteudo = pdf_rt_assinado_ou_gerado(ps)
        except DocumentValidationError as exc:
            if inline:
                return _preview_error_response(exc)
            messages.error(request, str(exc))
            return redirect("prestacoes_contas:rt_servidor", ps_pk=ps.pk)
        content_type = "application/pdf"
    else:
        conteudo = gerar_relatorio_tecnico_docx(relatorio, ps)
        formato = "docx"
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    nome = nome_arquivo_rt(relatorio, ps.servidor, formato=formato)
    disposition = "inline" if inline and formato == "pdf" else "attachment"
    response = HttpResponse(conteudo, content_type=content_type)
    response["Content-Disposition"] = f'{disposition}; filename="{nome}"'
    if disposition == "inline":
        response["X-Frame-Options"] = "SAMEORIGIN"
    return response
