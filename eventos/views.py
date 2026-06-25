import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from cadastros.models import ConfiguracaoSistema
from cadastros.models import Estado
from roteiros.selectors import listar_cidades_para_select

from oficios.presenters import apresentar_oficio_card
from planos_trabalho.presenters import apresentar_plano_card
from roteiros.presenters import apresentar_roteiro_card

from .forms import EventoForm
from .forms import EventoNovoCadastroForm
from .models import Evento
from .services import build_evento_guided_context


def api_cidades_por_uf(request, uf):
    uf = (uf or "").strip().upper()
    try:
        estado = Estado.objects.get(sigla=uf)
    except Estado.DoesNotExist:
        return JsonResponse([], safe=False)
    cidades = listar_cidades_para_select(estado_id=estado.pk)
    return JsonResponse([{"id": c.nome, "nome": c.nome} for c in cidades], safe=False)


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
    )


def _form_context(form, evento=None):
    is_edit = bool(evento and evento.pk)
    return {
        "page_title": "Editar Evento" if is_edit else "Cadastro de Evento",
        "page_description": "Agrupe documentos, roteiros e anexos sem tornar o evento obrigatório.",
        "form": form,
        "evento": evento,
        "index_url": reverse("eventos:index"),
        "panel_url": reverse("eventos:detalhe", kwargs={"pk": evento.pk}) if is_edit else "",
        "status_label": evento.get_status_display() if is_edit else "Novo",
        "status_variant": "active" if is_edit else "draft",
    }


def _save_destinos_extras(evento, request):
    """Lê destinos_json do POST e salva extras no evento (primeiro = destino_uf/cidade)."""
    raw = request.POST.get("destinos_json", "")
    try:
        destinos = json.loads(raw) if raw else []
    except (ValueError, TypeError):
        destinos = []
    if destinos and isinstance(destinos, list):
        primeiro = destinos[0] if destinos else {}
        evento.destino_uf = primeiro.get("uf", "")
        evento.destino_cidade = primeiro.get("cidade", "")
        evento.destinos_extras = destinos[1:] if len(destinos) > 1 else []
    else:
        evento.destinos_extras = []



@require_http_methods(["GET"])
def novo(request):
    evento = Evento()
    evento.save()
    return redirect("eventos:guiado_etapa", pk=evento.pk, etapa=1)


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


@require_http_methods(["GET", "POST"])
def detalhe(request, pk, etapa=1):
    evento = get_object_or_404(_evento_queryset(), pk=pk)

    # Etapa 1 é o formulário de dados do evento (edição inline)
    if etapa == 1 and request.method == "POST":
        form = EventoNovoCadastroForm(request.POST, instance=evento)
        if form.is_valid():
            evento = form.save(commit=False)
            if not evento.titulo:
                parts = []
                if evento.tipo:
                    label = evento.get_tipo_display()
                    if evento.tipo == "outros" and evento.tipo_outro:
                        label = evento.tipo_outro
                    parts.append(label)
                if evento.destino_cidade:
                    destino = evento.destino_cidade
                    if evento.destino_uf:
                        destino += f"/{evento.destino_uf}"
                    parts.append(destino)
                elif evento.destino_uf:
                    parts.append(evento.destino_uf)
                if evento.data_inicio:
                    parts.append(evento.data_inicio.strftime("%d/%m/%Y"))
                evento.titulo = " - ".join(parts) if parts else "Novo Evento"
            _save_destinos_extras(evento, request)
            evento.save()
            messages.success(request, "Dados do evento atualizados.")
            return redirect("eventos:guiado_etapa", pk=evento.pk, etapa=2)
    else:
        form = EventoNovoCadastroForm(instance=evento) if etapa == 1 else None

    guided_context = build_evento_guided_context(evento, etapa_atual=etapa)
    config = ConfiguracaoSistema.get_singleton()
    from django.urls import reverse as _reverse
    return render(
        request,
        "eventos/detalhe.html",
        {
            "page_title": evento.titulo,
            "evento": evento,
            "evento_form": form,
            "oficio_cards": [apresentar_oficio_card(oficio) for oficio in evento.oficios.all()],
            "roteiro_cards": [apresentar_roteiro_card(roteiro) for roteiro in evento.roteiros.all()],
            "plano_cards": [apresentar_plano_card(plano) for plano in evento.planos_trabalho.all()],
            "ordens": evento.ordens_servico.all(),
            "termos": evento.termos_autorizacao.all(),
            "sede_uf": config.uf if config else "",
            "modelos_motivo_url": _reverse("oficios:modelos_motivo_index"),
            **guided_context,
        },
    )


def guiado_termos(request, pk):
    return detalhe(request, pk, etapa=5)
