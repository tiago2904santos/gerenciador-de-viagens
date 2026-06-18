from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from oficios.presenters import apresentar_oficio_card
from planos_trabalho.presenters import apresentar_plano_card
from prestacoes.services import get_prestacao_status
from roteiros.presenters import apresentar_roteiro_card

from .forms import EventoForm
from .models import Evento
from .services import build_evento_guided_context


def index(request):
    eventos = Evento.objects.select_related("unidade_responsavel", "responsavel").prefetch_related("oficios").order_by("-data_inicio", "-criado_em")
    return render(
        request,
        "eventos/index.html",
        {
            "page_title": "Eventos",
            "page_description": "Agrupadores opcionais para organizar documentos relacionados.",
            "eventos": eventos,
            "novo_url": reverse("eventos:novo"),
        },
    )


def _evento_queryset():
    return Evento.objects.select_related("unidade_responsavel", "responsavel").prefetch_related(
        "oficios",
        "oficios__servidores",
        "oficios__servidores_termo_autorizacao",
        "oficios__roteiro__destinos__cidade__estado",
        "oficios__roteiro__trechos",
        "oficios__viatura",
        "oficios__motorista",
        "roteiros",
        "roteiros__destinos__cidade__estado",
        "roteiros__trechos",
        "planos_trabalho",
        "planos_trabalho__programa",
        "planos_trabalho__destino_cidade__estado",
        "planos_trabalho__coordenador_adm__cargo",
        "ordens_servico",
        "ordens_servico__destinos__estado",
        "ordens_servico__servidores",
        "ordens_servico__oficios",
        "termos_autorizacao",
        "termos_autorizacao__oficio",
        "termos_autorizacao__destino_cidade__estado",
        "termos_autorizacao__viatura",
        "termos_autorizacao__servidores",
        "relatorios_tecnicos",
        "diarios_bordo",
        "prestacoes_contas",
    )


def _form_context(form, evento=None):
    is_edit = bool(evento and evento.pk)
    return {
        "page_title": "Editar Evento" if is_edit else "Cadastro de Evento",
        "page_description": "Agrupe documentos, roteiros, anexos e prestação de contas sem tornar o evento obrigatório.",
        "form": form,
        "evento": evento,
        "index_url": reverse("eventos:index"),
        "panel_url": reverse("eventos:detalhe", kwargs={"pk": evento.pk}) if is_edit else "",
        "status_label": evento.get_status_display() if is_edit else "Novo",
        "status_variant": "active" if is_edit else "draft",
    }


@require_http_methods(["GET", "POST"])
def novo(request):
    evento = Evento()
    if request.method == "POST":
        form = EventoForm(request.POST, instance=evento)
        if form.is_valid():
            evento = form.save()
            messages.success(request, "Evento cadastrado.")
            return redirect("eventos:detalhe", pk=evento.pk)
    else:
        form = EventoForm(instance=evento)
    return render(request, "eventos/form.html", _form_context(form, evento))


@require_http_methods(["GET", "POST"])
def editar(request, pk):
    evento = get_object_or_404(_evento_queryset(), pk=pk)
    if request.method == "POST":
        form = EventoForm(request.POST, instance=evento)
        if form.is_valid():
            form.save()
            messages.success(request, "Evento atualizado.")
            return redirect("eventos:detalhe", pk=evento.pk)
    else:
        form = EventoForm(instance=evento)
    return render(request, "eventos/form.html", _form_context(form, evento))


def detalhe(request, pk, etapa=1):
    evento = get_object_or_404(_evento_queryset(), pk=pk)
    prestacao_context = get_prestacao_status(evento)
    guided_context = build_evento_guided_context(evento, etapa_atual=etapa)
    return render(
        request,
        "eventos/detalhe.html",
        {
            "page_title": evento.titulo,
            "evento": evento,
            "prestacao_context": prestacao_context,
            "oficio_cards": [apresentar_oficio_card(oficio) for oficio in evento.oficios.all()],
            "roteiro_cards": [apresentar_roteiro_card(roteiro) for roteiro in evento.roteiros.all()],
            "plano_cards": [apresentar_plano_card(plano) for plano in evento.planos_trabalho.all()],
            "ordens": evento.ordens_servico.all(),
            "termos": evento.termos_autorizacao.all(),
            **guided_context,
        },
    )


def guiado_termos(request, pk):
    return detalhe(request, pk, etapa=5)
