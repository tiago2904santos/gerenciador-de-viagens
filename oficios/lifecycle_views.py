"""Ações de ciclo de vida de um ofício."""

from django.contrib import messages
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from .selectors import get_oficio_by_id
from .services import OficioVinculadoError
from .services import cancelar_oficio
from .services import desfazer_complementar_oficio
from .services import desfazer_retificacao_oficio
from .services import excluir_oficio
from .services import marcar_oficio_complementar
from .services import retificar_oficio
from .view_navigation import oficio_back_url
from .view_navigation import safe_next_url


def _fallback_url(oficio):
    if oficio.evento_id:
        return redirect("eventos:guiado_etapa", pk=oficio.evento_id, etapa=3)
    return redirect("oficios:index")


def excluir(request, pk):
    oficio = get_oficio_by_id(pk)
    if request.method != "POST":
        return redirect(oficio_back_url(oficio))

    next_url = safe_next_url(request, "")
    try:
        excluir_oficio(oficio)
    except OficioVinculadoError:
        messages.error(
            request,
            "Não foi possível excluir o ofício porque ele está vinculado a outros registros.",
        )
        return redirect(next_url) if next_url else _fallback_url(oficio)
    messages.success(request, "Ofício excluído com sucesso.")
    return redirect(next_url) if next_url else _fallback_url(oficio)


@require_POST
def cancelar(request, pk):
    oficio = get_oficio_by_id(pk)
    next_url = safe_next_url(request, "")
    fallback = _fallback_url(oficio)

    if oficio.cancelado:
        messages.error(request, "Este ofício já está cancelado.")
        return redirect(next_url) if next_url else fallback

    motivo = (request.POST.get("motivo") or "").strip()
    if not motivo:
        messages.error(request, "Informe o motivo do cancelamento.")
        return redirect(next_url) if next_url else fallback

    cancelar_oficio(oficio, motivo)
    messages.success(
        request,
        "Ofício cancelado. Ele não gera mais prestação de contas nem pode "
        "ser usado em novas Ordens de Serviço.",
    )
    return redirect(next_url) if next_url else fallback


@require_POST
def retificar(request, pk):
    oficio = get_oficio_by_id(pk)
    next_url = safe_next_url(request, "")

    if oficio.retificado_documento:
        desfazer_retificacao_oficio(oficio)
        messages.success(
            request,
            "Retificação removida. O ofício voltou ao rótulo padrão do documento.",
        )
        return redirect(next_url) if next_url else _fallback_url(oficio)

    retificar_oficio(oficio)
    messages.success(
        request,
        "Ofício marcado como retificado. Edite o que for necessário — o "
        'documento passará a exibir "Retificado" ao lado do número.',
    )
    return redirect("oficios:dados_viajantes", pk=oficio.pk)


@require_POST
def marcar_complementar(request, pk):
    oficio = get_oficio_by_id(pk)
    next_url = safe_next_url(request, "")

    if oficio.complementar_documento:
        desfazer_complementar_oficio(oficio)
        messages.success(request, "Marcação de complementar removida do ofício.")
        return redirect(next_url) if next_url else _fallback_url(oficio)

    marcar_oficio_complementar(oficio)
    messages.success(
        request,
        "Ofício marcado como complementar. Edite o que for necessário — o "
        'documento passará a exibir "Complementar" ao lado do número.',
    )
    return redirect("oficios:dados_viajantes", pk=oficio.pk)
