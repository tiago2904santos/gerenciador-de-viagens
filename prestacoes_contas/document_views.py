import json
from pathlib import Path

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.autosave import autosave_json_response
from core.private_media import private_file_response
from core.uploads import validate_private_document_upload

from .forms import PrestacaoDespachoForm, PrestacaoServidorDocumentosForm, PrestacaoSolicitacaoForm
from .models import PrestacaoDocumentoAnexo
from .presenters import _anexo_assinado_info
from .presenters import kinds_de_anexo_assinado
from .view_common import (
    _autosave_form_errors,
    _autosave_version,
    _build_identificacao,
    contexto_do_fluxo,
    _marcar_servidor_em_preenchimento,
    _marcar_servidores_pendentes,
    _prestacao_queryset,
    _prestacao_servidor_full,
    _prestacao_servidor_queryset,
    _redirect_primeiro_servidor,
    _servidor_identificacao,
)


def _anexos_rows(prestacao, anexos_qs):
    rows = []
    for anexo in anexos_qs.order_by("criado_em", "pk"):
        rows.append(
            {
                "id": anexo.pk,
                "nome": anexo.nome_original or Path(anexo.arquivo.name).name,
                "url": reverse(
                    "prestacoes_contas:prestacao_documento_conteudo",
                    args=[prestacao.pk, anexo.pk],
                ),
                "delete_url": reverse(
                    "prestacoes_contas:prestacao_documento_excluir",
                    args=[prestacao.pk, anexo.pk],
                ),
            },
        )
    return rows


def prestacao_documento_conteudo(request, pc_pk, anexo_pk):
    prestacao = get_object_or_404(_prestacao_queryset(), pk=pc_pk)
    anexo = get_object_or_404(
        PrestacaoDocumentoAnexo,
        pk=anexo_pk,
        prestacao=prestacao,
    )
    return private_file_response(anexo.arquivo)


def _servidor_documentos_ctx(prestacao, ps):
    form = PrestacaoSolicitacaoForm(instance=ps, prefix=f"ps-{ps.pk}")
    anexos_ps = list(ps.documentos_anexos.all())
    anexos_pc = list(
        prestacao.documentos_anexos.filter(tipo=PrestacaoDocumentoAnexo.TIPO_DB_ASSINADO)
    )
    return {
        "ps": ps,
        "ps_pk": ps.pk,
        "name": ps.servidor.nome,
        "identificacao": _servidor_identificacao(ps),
        "form": form,
        "solicitacao_autosave_url": reverse(
            "prestacoes_contas:prestacao_servidor_solicitacao_autosave", args=[ps.pk]
        ),
        "rt_assinado": _anexo_assinado_info(
            anexos_ps,
            tipo=PrestacaoDocumentoAnexo.TIPO_RT_ASSINADO,
            anexar_url=reverse(
                "prestacoes_contas:prestacao_servidor_assinado_anexar",
                args=[ps.pk, PrestacaoDocumentoAnexo.TIPO_RT_ASSINADO],
            ),
            prestacao_pk=prestacao.pk,
        ),
        "comprovante_anexo": _anexo_assinado_info(
            anexos_ps,
            tipo=PrestacaoDocumentoAnexo.TIPO_COMPROVANTE,
            anexar_url=reverse(
                "prestacoes_contas:prestacao_servidor_assinado_anexar",
                args=[ps.pk, PrestacaoDocumentoAnexo.TIPO_COMPROVANTE],
            ),
            prestacao_pk=prestacao.pk,
        ),
        "diario_assinado": _anexo_assinado_info(
            anexos_pc,
            tipo=PrestacaoDocumentoAnexo.TIPO_DB_ASSINADO,
            anexar_url=reverse(
                "prestacoes_contas:prestacao_servidor_assinado_anexar",
                args=[ps.pk, PrestacaoDocumentoAnexo.TIPO_DB_ASSINADO],
            ),
            prestacao_pk=prestacao.pk,
        ),
    }


def documentos(request, pc_pk):
    """Compatibilidade: redireciona para o primeiro servidor."""
    prestacao = get_object_or_404(_prestacao_queryset(), pk=pc_pk)
    return _redirect_primeiro_servidor(request, prestacao, "prestacoes_contas:documentos_servidor")


def documentos_servidor(request, ps_pk):
    """Etapa 3: despacho compartilhado + documentos do servidor atual."""
    ps = _prestacao_servidor_full(ps_pk)
    prestacao = ps.prestacao
    servidor = _servidor_documentos_ctx(prestacao, ps)
    anexos_compartilhados = list(
        prestacao.documentos_anexos.filter(
            tipo__in=(
                PrestacaoDocumentoAnexo.TIPO_DESPACHO,
                PrestacaoDocumentoAnexo.TIPO_OFICIO_ASSINADO,
            )
        )
    )
    despacho_assinado = _anexo_assinado_info(
        anexos_compartilhados,
        tipo=PrestacaoDocumentoAnexo.TIPO_DESPACHO,
        anexar_url=reverse(
            "prestacoes_contas:prestacao_despacho_assinado_anexar",
            args=[prestacao.pk],
        ),
        prestacao_pk=prestacao.pk,
    )
    oficio_assinado = _anexo_assinado_info(
        anexos_compartilhados,
        tipo=PrestacaoDocumentoAnexo.TIPO_OFICIO_ASSINADO,
        anexar_url=reverse(
            "prestacoes_contas:prestacao_oficio_assinado_anexar",
            args=[prestacao.pk],
        ),
        prestacao_pk=prestacao.pk,
    )
    identificacao = _build_identificacao(prestacao)
    numero = identificacao.get("numero") or ""

    # `H-03`: eram cinco chaves ordinais (`primary`…`quinary`) — nome que dizia a
    # POSIÇÃO, não o documento. Cada uma virava 6 atributos `data-*` planos no
    # gatilho, 30 no total. Ver `kinds_de_anexo_assinado`.
    attach_kinds = kinds_de_anexo_assinado(
        [
            ("despacho", "Despacho", f"o despacho do ofício {numero}", despacho_assinado),
            ("oficio", "Ofício", f"o ofício {numero}", oficio_assinado),
            (
                "rt",
                "RT",
                f"o relatório técnico de {servidor['name']}",
                servidor["rt_assinado"],
            ),
            (
                "diario",
                "DB",
                f"o diário de bordo do ofício {numero}",
                servidor["diario_assinado"],
            ),
            (
                "comprovante",
                "Comprovante",
                (
                    "o comprovante de saque ou transferência de "
                    f"{servidor['name']}"
                ),
                servidor["comprovante_anexo"],
            ),
        ]
    )

    return render(
        request,
        "prestacoes_contas/documentos_form.html",
        {
            "page_title": f"Documentos — {ps.servidor.nome}",
            "prestacao": prestacao,
            "ps": ps,
            "servidor": servidor,
            "servidores": [servidor],
            "identificacao": identificacao,
            "despacho_assinado": despacho_assinado,
            "oficio_assinado": oficio_assinado,
            "attach_kinds": attach_kinds,
            # Um payload só, no gatilho, em vez de 30 atributos planos. Sai como
            # string e o template escapa: quem monta o HTML não é o Python.
            "attach_kinds_json": json.dumps(attach_kinds, ensure_ascii=False),
            # `contexto_do_fluxo` já entrega `wizard_page_steps` junto com os
            # metadados de cabeçalho (H-02).
            **contexto_do_fluxo(ps, "documentos"),
            "back_url": reverse("prestacoes_contas:index"),
            "diario_url": reverse("prestacoes_contas:diario_servidor", args=[ps.pk]),
            "consolidado_url": reverse("prestacoes_contas:consolidado_servidor", args=[ps.pk]),
        },
    )


def prestacao_arquivo_autosave(request, pc_pk):
    """Autosave do despacho (compartilhado)."""
    prestacao = get_object_or_404(_prestacao_queryset(), pk=pc_pk)
    form = PrestacaoDespachoForm(request.POST, request.FILES, instance=prestacao)
    if not form.is_valid():
        return autosave_json_response(
            ok=False,
            message="Alguns anexos ainda precisam de ajuste antes do autosave.",
            errors=_autosave_form_errors(form),
        )
    form.save()
    _marcar_servidores_pendentes(prestacao)
    return autosave_json_response(
        ok=True,
        object_id=prestacao.pk,
        version=_autosave_version(prestacao),
    )


def prestacao_servidor_arquivo_autosave(request, ps_pk):
    """Autosave do comprovante de saque (individual do servidor).

    Salva apenas os anexos — não reescreve o ``numero_solicitacao`` (que tem seu
    próprio autosave), evitando apagá-lo quando o POST traz só o arquivo.
    """
    ps = get_object_or_404(_prestacao_servidor_queryset().select_related("prestacao"), pk=ps_pk)
    form = PrestacaoServidorDocumentosForm(request.POST, request.FILES, instance=ps, prefix=f"ps-{ps.pk}")
    if not form.is_valid():
        return autosave_json_response(
            ok=False,
            message="Alguns anexos ainda precisam de ajuste antes do autosave.",
            errors=_autosave_form_errors(form),
        )
    form.save_anexos(ps)
    _marcar_servidor_em_preenchimento(ps)
    return autosave_json_response(
        ok=True,
        object_id=ps.pk,
        version=_autosave_version(ps),
    )


def _prestacao_upload_next_url(request, fallback_url):
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback_url


def _prestacao_assinado_upload(
    request,
    *,
    prestacao,
    tipo,
    servidor_prestacao=None,
    substituir_todos_do_tipo=False,
):
    fallback_url = reverse("prestacoes_contas:index")
    destino = _prestacao_upload_next_url(request, fallback_url)
    arquivo = request.FILES.get("arquivo")
    if not arquivo:
        messages.error(request, "Selecione um arquivo PDF para anexar.")
        return redirect(destino)

    nome_original = Path(getattr(arquivo, "name", "") or "").name
    # QA-04: a política central (tamanho, magic bytes, bomba de descompressão,
    # antivírus) precisa rodar antes de qualquer escrita. Conferir só o sufixo
    # aceitava arquivo que mente sobre o próprio conteúdo — e ele ainda era
    # sincronizado com o Google Drive depois.
    try:
        validate_private_document_upload(arquivo)
    except ValidationError as exc:
        for mensagem in exc.messages:
            messages.error(request, mensagem)
        return redirect(destino)

    # A validação vem antes da exclusão dos anteriores de propósito: recusar um
    # arquivo novo não pode custar o que já estava anexado.
    anteriores = PrestacaoDocumentoAnexo.objects.filter(prestacao=prestacao, tipo=tipo)
    if not substituir_todos_do_tipo:
        anteriores = anteriores.filter(servidor_prestacao=servidor_prestacao)
    for anexo in anteriores:
        if anexo.arquivo:
            anexo.arquivo.delete(save=False)
    anteriores.delete()

    PrestacaoDocumentoAnexo.objects.create(
        prestacao=prestacao,
        servidor_prestacao=servidor_prestacao,
        tipo=tipo,
        arquivo=arquivo,
        nome_original=nome_original,
    )
    if servidor_prestacao is not None:
        _marcar_servidor_em_preenchimento(servidor_prestacao)
    else:
        _marcar_servidores_pendentes(prestacao)
    messages.success(request, "Documento assinado anexado.")
    return redirect(destino)


def prestacao_despacho_assinado_anexar(request, pc_pk):
    prestacao = get_object_or_404(_prestacao_queryset(), pk=pc_pk)
    return _prestacao_assinado_upload(
        request,
        prestacao=prestacao,
        tipo=PrestacaoDocumentoAnexo.TIPO_DESPACHO,
    )


def prestacao_oficio_assinado_anexar(request, pc_pk):
    prestacao = get_object_or_404(_prestacao_queryset(), pk=pc_pk)
    return _prestacao_assinado_upload(
        request,
        prestacao=prestacao,
        tipo=PrestacaoDocumentoAnexo.TIPO_OFICIO_ASSINADO,
    )


def prestacao_servidor_assinado_anexar(request, ps_pk, tipo):
    servidor_prestacao = get_object_or_404(
        _prestacao_servidor_queryset().select_related("prestacao__oficio"),
        pk=ps_pk,
    )
    tipos_permitidos = {
        PrestacaoDocumentoAnexo.TIPO_RT_ASSINADO,
        PrestacaoDocumentoAnexo.TIPO_COMPROVANTE,
        PrestacaoDocumentoAnexo.TIPO_DB_ASSINADO,
    }
    if tipo not in tipos_permitidos:
        return HttpResponse(status=404)
    diario_compartilhado = tipo == PrestacaoDocumentoAnexo.TIPO_DB_ASSINADO
    return _prestacao_assinado_upload(
        request,
        prestacao=servidor_prestacao.prestacao,
        servidor_prestacao=None if diario_compartilhado else servidor_prestacao,
        tipo=tipo,
        substituir_todos_do_tipo=diario_compartilhado,
    )


def prestacao_documento_excluir(request, pc_pk, anexo_pk):
    prestacao = get_object_or_404(_prestacao_queryset(), pk=pc_pk)
    anexo = get_object_or_404(
        PrestacaoDocumentoAnexo,
        pk=anexo_pk,
        prestacao=prestacao,
    )
    ps_marcar = anexo.servidor_prestacao
    if anexo.arquivo:
        anexo.arquivo.delete(save=False)
    anexo.delete()
    if ps_marcar is not None:
        _marcar_servidor_em_preenchimento(ps_marcar)
    else:
        _marcar_servidores_pendentes(prestacao)
    return autosave_json_response(
        ok=True,
        object_id=prestacao.pk,
        version=_autosave_version(prestacao),
    )
