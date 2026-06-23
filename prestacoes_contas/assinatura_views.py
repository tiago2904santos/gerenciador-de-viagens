"""Fluxo público de assinatura (sem login) de RT e Diário de Bordo.

Acessado pelo signatário via link enviado por WhatsApp. Páginas isoladas do chrome do
app (template próprio) e isentas de login (``login_not_required``).
"""

from __future__ import annotations

import base64

from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .assinatura_services import AssinaturaError
from .assinatura_services import aplicar_assinatura
from .assinatura_services import documento_do_link
from .assinatura_services import documentos_do_link
from .assinatura_services import proximo_pendente
from .assinatura_services import validar_identidade
from .models import AssinaturaDocumento


_MAX_TENTATIVAS = getattr(settings, "ASSINATURA_MAX_TENTATIVAS", 5)
_BLOQUEIO_MINUTOS = getattr(settings, "ASSINATURA_BLOQUEIO_MINUTOS", 15)

# Fontes manuscritas oferecidas ao signatário (self-hosted; ver static/css).
FONTES_ASSINATURA = [
    {"key": "dancing", "label": "Dancing Script", "family": "'Dancing Script', cursive"},
    {"key": "greatvibes", "label": "Great Vibes", "family": "'Great Vibes', cursive"},
    {"key": "sacramento", "label": "Sacramento", "family": "'Sacramento', cursive"},
    {"key": "caveat", "label": "Caveat", "family": "'Caveat', cursive"},
]


def _client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


def _ok_key(token, tipo):
    return f"assin_ok_{token}_{tipo}"


def _tries_key(token, tipo):
    return f"assin_tries_{token}_{tipo}"


def _block_key(token, tipo):
    return f"assin_block_{token}_{tipo}"


def _identidade_confirmada(request, token, tipo) -> bool:
    return bool(request.session.get(_ok_key(token, tipo)))


def _erro(request, mensagem, status=410):
    return render(
        request,
        "prestacoes_contas/assinatura/erro.html",
        {"mensagem": mensagem},
        status=status,
    )


def _docs_para_landing(docs):
    info = []
    for doc in docs:
        info.append(
            {
                "tipo": doc.tipo,
                "label": doc.get_tipo_display(),
                "signatario": doc.nome_esperado or (str(doc.signer) if doc.signer_id else ""),
                "assinada": doc.status == AssinaturaDocumento.STATUS_ASSINADA,
                "identidade_url": reverse(
                    "prestacoes_contas:assinatura_identidade", args=[doc.link_token, doc.tipo]
                ),
            }
        )
    return info


@login_not_required
def publico_landing(request, token):
    docs = documentos_do_link(token)
    if not docs:
        return _erro(request, "Este link de assinatura é inválido ou expirou.")
    pendente = proximo_pendente(token)
    if pendente is None:
        return redirect("prestacoes_contas:assinatura_concluido", token=token)
    return render(
        request,
        "prestacoes_contas/assinatura/landing.html",
        {
            "token": token,
            "docs": _docs_para_landing(docs),
            "total": len(docs),
            "continuar_url": reverse(
                "prestacoes_contas:assinatura_identidade", args=[token, pendente.tipo]
            ),
        },
    )


@login_not_required
def publico_identidade(request, token, tipo):
    doc = documento_do_link(token, tipo)
    if doc is None:
        return _erro(request, "Este link de assinatura é inválido ou expirou.")
    if doc.status == AssinaturaDocumento.STATUS_ASSINADA:
        return redirect("prestacoes_contas:assinatura_landing", token=token)

    assinar_url = reverse("prestacoes_contas:assinatura_assinar", args=[token, tipo])
    if _identidade_confirmada(request, token, tipo):
        return redirect(assinar_url)

    bloqueio = request.session.get(_block_key(token, tipo))
    bloqueado = bool(bloqueio and timezone.now().timestamp() < bloqueio)

    erro = ""
    if request.method == "POST" and not bloqueado:
        confirma_nome = request.POST.get("confirma_nome") == "on"
        cpf5 = request.POST.get("cpf5", "")
        if not confirma_nome:
            erro = "Confirme que o nome exibido é o seu para continuar."
        elif validar_identidade(doc, cpf5):
            request.session[_ok_key(token, tipo)] = True
            request.session.pop(_tries_key(token, tipo), None)
            request.session.pop(_block_key(token, tipo), None)
            return redirect(assinar_url)
        else:
            tentativas = int(request.session.get(_tries_key(token, tipo), 0)) + 1
            request.session[_tries_key(token, tipo)] = tentativas
            restantes = _MAX_TENTATIVAS - tentativas
            if restantes <= 0:
                request.session[_block_key(token, tipo)] = (
                    timezone.now() + timezone.timedelta(minutes=_BLOQUEIO_MINUTOS)
                ).timestamp()
                bloqueado = True
                erro = "Muitas tentativas. Tente novamente mais tarde."
            else:
                erro = f"Os dígitos do CPF não conferem. Tentativas restantes: {restantes}."

    return render(
        request,
        "prestacoes_contas/assinatura/identidade.html",
        {
            "token": token,
            "tipo": tipo,
            "doc_label": doc.get_tipo_display(),
            "nome": doc.nome_esperado or (str(doc.signer) if doc.signer_id else ""),
            "erro": erro,
            "bloqueado": bloqueado,
        },
    )


@login_not_required
def publico_assinar(request, token, tipo):
    doc = documento_do_link(token, tipo)
    if doc is None:
        return _erro(request, "Este link de assinatura é inválido ou expirou.")
    if doc.status == AssinaturaDocumento.STATUS_ASSINADA:
        return redirect("prestacoes_contas:assinatura_landing", token=token)
    if not _identidade_confirmada(request, token, tipo):
        return redirect("prestacoes_contas:assinatura_identidade", token=token, tipo=tipo)

    if request.method == "POST":
        png_bytes = _decode_data_url_png(request.POST.get("assinatura_png", ""))
        try:
            aplicar_assinatura(
                doc,
                png_bytes=png_bytes,
                modo=request.POST.get("modo", ""),
                fonte=request.POST.get("fonte", ""),
                pagina=_to_int(request.POST.get("pagina"), 0),
                x=_to_float(request.POST.get("pos_x"), 0.0),
                y=_to_float(request.POST.get("pos_y"), 0.0),
                w=_to_float(request.POST.get("largura"), 0.2),
                h=_to_float(request.POST.get("altura"), 0.08),
                ip=_client_ip(request),
            )
        except AssinaturaError as exc:
            return render(
                request,
                "prestacoes_contas/assinatura/assinar.html",
                {**_assinar_context(request, token, tipo, doc), "erro": str(exc)},
            )
        request.session.pop(_ok_key(token, tipo), None)
        proximo = proximo_pendente(token)
        if proximo is not None:
            return redirect(
                "prestacoes_contas:assinatura_identidade", token=token, tipo=proximo.tipo
            )
        return redirect("prestacoes_contas:assinatura_concluido", token=token)

    return render(
        request,
        "prestacoes_contas/assinatura/assinar.html",
        {**_assinar_context(request, token, tipo, doc), "erro": ""},
    )


def _assinar_context(request, token, tipo, doc):
    docs = documentos_do_link(token)
    ordem = [d.tipo for d in docs]
    indice = ordem.index(tipo) + 1 if tipo in ordem else 1
    return {
        "token": token,
        "tipo": tipo,
        "doc_label": doc.get_tipo_display(),
        "nome": doc.nome_esperado or (str(doc.signer) if doc.signer_id else ""),
        "fontes": FONTES_ASSINATURA,
        "pdf_url": reverse("prestacoes_contas:assinatura_pdf_origem", args=[token, tipo]),
        "post_url": reverse("prestacoes_contas:assinatura_assinar", args=[token, tipo]),
        "worker_src": static("vendor/pdfjs/pdf.worker.min.js"),
        "pdfjs_src": static("vendor/pdfjs/pdf.min.js"),
        "indice": indice,
        "total": len(docs),
    }


@login_not_required
def publico_pdf_origem(request, token, tipo):
    doc = documento_do_link(token, tipo)
    if doc is None or not doc.arquivo_origem:
        return _erro(request, "Documento indisponível.", status=404)
    if not _identidade_confirmada(request, token, tipo):
        return _erro(request, "Confirme sua identidade para visualizar o documento.", status=403)
    with doc.arquivo_origem.open("rb") as f:
        conteudo = f.read()
    response = HttpResponse(conteudo, content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="documento.pdf"'
    response["X-Frame-Options"] = "SAMEORIGIN"
    return response


@login_not_required
def publico_concluido(request, token):
    docs = documentos_do_link(token)
    return render(
        request,
        "prestacoes_contas/assinatura/concluido.html",
        {"docs": _docs_para_landing(docs)},
    )


def _decode_data_url_png(data_url):
    if not data_url or "," not in data_url:
        return None
    header, b64 = data_url.split(",", 1)
    if "image/png" not in header:
        return None
    try:
        return base64.b64decode(b64)
    except Exception:
        return None


def _to_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
