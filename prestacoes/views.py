from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from eventos.models import Evento

from .forms import DiarioBordoForm
from .forms import DiarioBordoRegistroForm
from .forms import PrestacaoContasForm
from .forms import RelatorioTecnicoForm
from .models import DiarioBordo
from .models import PrestacaoContas
from .models import RelatorioTecnico
from .services import build_diario_from_evento
from .services import build_prestacao_from_evento
from .services import build_relatorio_from_evento


def _evento_queryset():
    return Evento.objects.select_related("unidade_responsavel", "responsavel").prefetch_related("oficios__servidores")


@require_http_methods(["GET", "POST"])
def criar_relatorio_evento(request, evento_pk):
    evento = get_object_or_404(_evento_queryset(), pk=evento_pk)
    relatorio = build_relatorio_from_evento(evento)
    if request.method == "POST":
        form = RelatorioTecnicoForm(request.POST, instance=relatorio, evento_locked=True)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.evento = evento
            obj.save()
            messages.success(request, "Relatório técnico criado.")
            return redirect("eventos:detalhe", pk=evento.pk)
    else:
        form = RelatorioTecnicoForm(instance=relatorio, evento_locked=True)
    return render(request, "prestacoes/relatorio_form.html", {"form": form, "evento": evento, "relatorio": relatorio})


@require_http_methods(["GET", "POST"])
def editar_relatorio(request, pk):
    relatorio = get_object_or_404(RelatorioTecnico.objects.select_related("evento"), pk=pk)
    if request.method == "POST":
        form = RelatorioTecnicoForm(request.POST, instance=relatorio, evento_locked=bool(relatorio.evento_id))
        if form.is_valid():
            form.save()
            messages.success(request, "Relatório técnico atualizado.")
            return _redirect_documento(relatorio)
    else:
        form = RelatorioTecnicoForm(instance=relatorio, evento_locked=bool(relatorio.evento_id))
    return render(request, "prestacoes/relatorio_form.html", {"form": form, "evento": relatorio.evento, "relatorio": relatorio})


@require_http_methods(["GET", "POST"])
def criar_diario_evento(request, evento_pk):
    evento = get_object_or_404(_evento_queryset(), pk=evento_pk)
    diario = build_diario_from_evento(evento)
    if request.method == "POST":
        form = DiarioBordoForm(request.POST, instance=diario, evento_locked=True)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.evento = evento
            obj.save()
            messages.success(request, "Diário de bordo criado.")
            return redirect("eventos:detalhe", pk=evento.pk)
    else:
        form = DiarioBordoForm(instance=diario, evento_locked=True)
    return render(request, "prestacoes/diario_form.html", {"form": form, "evento": evento, "diario": diario})


@require_http_methods(["GET", "POST"])
def editar_diario(request, pk):
    diario = get_object_or_404(
        DiarioBordo.objects.select_related("evento").prefetch_related("registros"),
        pk=pk,
    )
    if request.method == "POST":
        form = DiarioBordoForm(request.POST, instance=diario, evento_locked=bool(diario.evento_id))
        if form.is_valid():
            form.save()
            messages.success(request, "Diário de bordo atualizado.")
            return _redirect_documento(diario)
    else:
        form = DiarioBordoForm(instance=diario, evento_locked=bool(diario.evento_id))
    return render(request, "prestacoes/diario_form.html", {"form": form, "evento": diario.evento, "diario": diario})


@require_http_methods(["GET", "POST"])
def adicionar_registro_diario(request, diario_pk):
    diario = get_object_or_404(DiarioBordo.objects.select_related("evento"), pk=diario_pk)
    if request.method == "POST":
        form = DiarioBordoRegistroForm(request.POST)
        if form.is_valid():
            registro = form.save(commit=False)
            registro.diario = diario
            registro.save()
            messages.success(request, "Registro adicionado ao diário de bordo.")
            return redirect("prestacoes:editar_diario", pk=diario.pk)
    else:
        form = DiarioBordoRegistroForm(initial={"destino": diario.destino})
    return render(request, "prestacoes/registro_form.html", {"form": form, "diario": diario, "evento": diario.evento})


@require_http_methods(["GET", "POST"])
def criar_ou_editar_prestacao(request, evento_pk):
    evento = get_object_or_404(
        Evento.objects.prefetch_related("relatorios_tecnicos", "diarios_bordo", "prestacoes_contas"),
        pk=evento_pk,
    )
    prestacao = evento.prestacoes_contas.order_by("-criado_em").first() or build_prestacao_from_evento(evento)
    return _prestacao_form(request, prestacao, evento)


@require_http_methods(["GET", "POST"])
def editar_prestacao(request, pk):
    prestacao = get_object_or_404(PrestacaoContas.objects.select_related("evento"), pk=pk)
    return _prestacao_form(request, prestacao, prestacao.evento)


def _prestacao_form(request, prestacao, evento):
    if request.method == "POST":
        form = PrestacaoContasForm(request.POST, instance=prestacao, evento=evento)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.evento = evento
            obj.save()
            messages.success(request, "Prestação de contas salva.")
            return redirect("eventos:detalhe", pk=evento.pk)
    else:
        form = PrestacaoContasForm(instance=prestacao, evento=evento)
    return render(request, "prestacoes/prestacao_form.html", {"form": form, "evento": evento, "prestacao": prestacao})


def _redirect_documento(obj):
    if obj.evento_id:
        return redirect("eventos:detalhe", pk=obj.evento_id)
    if isinstance(obj, DiarioBordo):
        return redirect("prestacoes:editar_diario", pk=obj.pk)
    return redirect("prestacoes:editar_relatorio", pk=obj.pk)
