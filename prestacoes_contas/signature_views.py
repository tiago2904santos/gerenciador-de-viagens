from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from documentos.services.exceptions import DocumentValidationError

from .assinatura_services import (
    AssinaturaError,
    assinatura_db,
    assinatura_rt,
    cancelar_assinatura_db,
    cancelar_assinatura_rt,
    emitir_link_db,
    emitir_link_rt,
    signer_db,
    signer_rt,
)
from .models import AssinaturaDocumento
from .view_common import (
    _prestacao_queryset,
    _prestacao_servidor_queryset,
    _primeiro_servidor,
)


def _whatsapp_data(link_absoluto, signer, doc_labels) -> dict:
    """Telefone (com DDI) e mensagem; o front monta a URL por app/aparelho no clique."""
    docs_txt = " e ".join(doc_labels)
    msg = (
        "Olá! Para concluir a prestação de contas, preciso da sua assinatura no "
        f"{docs_txt}. Acesse o link, confirme sua identidade e assine: {link_absoluto}"
    )
    telefone = (getattr(signer, "telefone", "") or "").strip() if signer else ""
    fone = f"55{telefone}" if (len(telefone) == 11 and telefone.isdigit()) else ""
    return {"phone": fone, "msg": msg}


def _assinatura_card(request, *, doc, signer, tipo, label, motivo_sem_signer, gerar_url, cancelar_url) -> dict:
    cpf_ok = bool(signer and len((getattr(signer, "cpf", "") or "").strip()) == 11)
    motivo = ""
    if signer is None:
        motivo = motivo_sem_signer
    elif not cpf_ok:
        quem = "motorista" if tipo == AssinaturaDocumento.TIPO_DB else "servidor"
        motivo = f"Cadastre o CPF do {quem} ({signer}) para gerar o link de assinatura."

    assinada = bool(doc and doc.status == AssinaturaDocumento.STATUS_ASSINADA)
    link_ativo = bool(doc and doc.link_ativo)
    link_abs = ""
    wa = {"phone": "", "msg": ""}
    if link_ativo:
        link_abs = request.build_absolute_uri(
            reverse("prestacoes_contas:assinatura_landing", args=[doc.link_token])
        )
        wa = _whatsapp_data(link_abs, signer, [label])

    return {
        "tipo": tipo,
        "label": label,
        "signatario": str(signer) if signer else "—",
        "assinada": assinada,
        "assinado_em": doc.assinado_em if assinada else None,
        "codigo": doc.codigo_verificacao if assinada else "",
        "pode_assinar": cpf_ok,
        "motivo": motivo,
        "link_ativo": link_ativo,
        "link_absoluto": link_abs,
        "expira_em": doc.link_expira_em if link_ativo else None,
        "whatsapp_phone": wa["phone"],
        "whatsapp_msg": wa["msg"],
        "gerar_url": gerar_url,
        "cancelar_url": cancelar_url,
    }


def _assinatura_rt_card(request, ps) -> dict:
    return _assinatura_card(
        request,
        doc=assinatura_rt(ps),
        signer=signer_rt(ps),
        tipo=AssinaturaDocumento.TIPO_RT,
        label=f"Relatório Técnico — {ps.servidor.nome}",
        motivo_sem_signer="Servidor da prestação não definido.",
        gerar_url=reverse("prestacoes_contas:assinatura_rt_gerar", args=[ps.pk]),
        cancelar_url=reverse("prestacoes_contas:assinatura_rt_cancelar", args=[ps.pk]),
    )


def _assinatura_db_card(request, prestacao) -> dict:
    return _assinatura_card(
        request,
        doc=assinatura_db(prestacao),
        signer=signer_db(prestacao),
        tipo=AssinaturaDocumento.TIPO_DB,
        label="Diário de Bordo",
        motivo_sem_signer="Defina o motorista do ofício para gerar o link.",
        gerar_url=reverse("prestacoes_contas:assinatura_db_gerar", args=[prestacao.pk]),
        cancelar_url=reverse("prestacoes_contas:assinatura_db_cancelar", args=[prestacao.pk]),
    )


def assinatura_rt_gerar(request, ps_pk):
    ps = get_object_or_404(
        _prestacao_servidor_queryset().select_related("prestacao__oficio", "servidor"), pk=ps_pk
    )
    forcar = request.POST.get("forcar") == "1"
    next_url = request.POST.get("next") or reverse(
        "prestacoes_contas:consolidado_servidor", args=[ps.pk]
    )
    try:
        token, _docs = emitir_link_rt(ps, forcar=forcar)
    except (AssinaturaError, DocumentValidationError) as exc:
        messages.error(request, str(exc))
        return redirect(next_url)
    link = request.build_absolute_uri(
        reverse("prestacoes_contas:assinatura_landing", args=[token])
    )
    messages.success(request, f"Link de assinatura gerado. Envie ao signatário: {link}")
    return redirect(next_url)


def assinatura_db_gerar(request, pc_pk):
    prestacao = get_object_or_404(
        _prestacao_queryset().select_related("oficio__motorista"), pk=pc_pk
    )
    forcar = request.POST.get("forcar") == "1"
    next_url = request.POST.get("next")
    if not next_url:
        ps = _primeiro_servidor(prestacao)
        next_url = (
            reverse("prestacoes_contas:consolidado_servidor", args=[ps.pk])
            if ps is not None
            else reverse("prestacoes_contas:index")
        )
    try:
        token, _docs = emitir_link_db(prestacao, forcar=forcar)
    except (AssinaturaError, DocumentValidationError) as exc:
        messages.error(request, str(exc))
        return redirect(next_url)
    link = request.build_absolute_uri(
        reverse("prestacoes_contas:assinatura_landing", args=[token])
    )
    messages.success(request, f"Link de assinatura gerado. Envie ao signatário: {link}")
    return redirect(next_url)


def assinatura_rt_cancelar(request, ps_pk):
    ps = get_object_or_404(_prestacao_servidor_queryset(), pk=ps_pk)
    next_url = request.POST.get("next") or reverse(
        "prestacoes_contas:consolidado_servidor", args=[ps.pk]
    )
    cancelar_assinatura_rt(ps)
    messages.success(request, "Link/assinatura removidos. Você pode gerar um novo link.")
    return redirect(next_url)


def assinatura_db_cancelar(request, pc_pk):
    prestacao = get_object_or_404(_prestacao_queryset(), pk=pc_pk)
    next_url = request.POST.get("next")
    if not next_url:
        ps = _primeiro_servidor(prestacao)
        next_url = (
            reverse("prestacoes_contas:consolidado_servidor", args=[ps.pk])
            if ps is not None
            else reverse("prestacoes_contas:index")
        )
    cancelar_assinatura_db(prestacao)
    messages.success(request, "Link/assinatura removidos. Você pode gerar um novo link.")
    return redirect(next_url)
