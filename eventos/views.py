import json
from pathlib import Path
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST

from cadastros.models import ConfiguracaoSistema
from cadastros.models import Estado
from core.normalizers import remove_accents
from roteiros.selectors import listar_cidades_para_select

from oficios.presenters import apresentar_oficio_card
from ordens_servico.presenters import apresentar_ordem_servico_card
from planos_trabalho.presenters import apresentar_plano_card
from roteiros.presenters import apresentar_linha_lista_simples_roteiro

from prestacoes_contas.forms import PrestacaoMultipleFileField
from prestacoes_contas.forms import PrestacaoMultipleFileInput

from .forms import EventoForm
from .forms import EventoNovoCadastroForm
from .forms import TipoEventoForm
from .models import Evento
from .models import EventoDocumentoSolicitacao
from .models import EVENTO_SOLICITACAO_EXTENSOES
from .models import TipoEvento
from .presenters import apresentar_evento_list_card
from .presenters import apresentar_linha_lista_simples_tipo_evento
from .services import build_evento_guided_context


def _safe_next_url(request, fallback_url):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback_url


def api_cidades_por_uf(request, uf):
    uf = (uf or "").strip().upper()
    try:
        estado = Estado.objects.get(sigla=uf)
    except Estado.DoesNotExist:
        return JsonResponse([], safe=False)
    cidades = listar_cidades_para_select(estado_id=estado.pk)
    return JsonResponse([{"id": c.nome, "nome": c.nome} for c in cidades], safe=False)


def tipos_index(request):
    q = request.GET.get("q", "").strip()
    back_url = _safe_next_url(request, reverse("eventos:index"))
    form = TipoEventoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tipo de evento criado com sucesso.")
        redirect_url = reverse("eventos:tipos_index")
        if back_url:
            redirect_url = f"{redirect_url}?{urlencode({'next': back_url})}"
        return redirect(redirect_url)
    tipos = TipoEvento.objects.all()
    if q:
        query = remove_accents(q)
        tipos = tipos.filter(nome__unaccent__icontains=query)
    rows = [
        apresentar_linha_lista_simples_tipo_evento(
            tipo,
            edit_url=reverse("eventos:tipo_editar", args=[tipo.pk]),
            delete_url=reverse("eventos:tipo_excluir", args=[tipo.pk]),
            delete_modal=True,
        )
        for tipo in tipos
    ]
    return render(
        request,
        "eventos/tipos/index.html",
        {
            "page_title": "Tipos de evento",
            "page_description": "Cadastre os tipos que podem ser selecionados (mais de um por evento).",
            "q": q,
            "rows": rows,
            "quick_add_form": form,
            "quick_add_next_url": back_url,
            "back_url": back_url,
            "new_url": reverse("eventos:tipo_novo"),
        },
    )


def tipo_novo(request):
    form = TipoEventoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tipo de evento criado com sucesso.")
        return redirect("eventos:tipos_index")
    return render(
        request,
        "eventos/tipos/form.html",
        {
            "page_title": "Novo tipo de evento",
            "page_description": "Cadastre um tipo que poderá ser selecionado (mais de um por evento).",
            "form": form,
            "back_url": reverse("eventos:tipos_index"),
            "submit_label": "Salvar tipo",
        },
    )


def tipo_editar(request, pk):
    tipo = get_object_or_404(TipoEvento, pk=pk)
    form = TipoEventoForm(request.POST or None, instance=tipo)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tipo de evento atualizado com sucesso.")
        return redirect("eventos:tipos_index")
    return render(
        request,
        "eventos/tipos/form.html",
        {
            "page_title": "Editar tipo de evento",
            "page_description": "Cadastre um tipo que poderá ser selecionado (mais de um por evento).",
            "form": form,
            "back_url": reverse("eventos:tipos_index"),
            "submit_label": "Salvar alterações",
        },
    )


def tipo_excluir(request, pk):
    tipo = get_object_or_404(TipoEvento, pk=pk)
    if request.method == "POST":
        tipo.delete()
        messages.success(request, "Tipo de evento excluído com sucesso.")
        return redirect("eventos:tipos_index")
    return render(
        request,
        "eventos/tipos/confirm_delete.html",
        {
            "page_title": "Excluir tipo de evento",
            "page_description": "Confirme a remoção deste tipo de evento.",
            "object": tipo,
            "back_url": reverse("eventos:tipos_index"),
        },
    )


def index(request):
    q = request.GET.get("q", "").strip()
    temporal = request.GET.get("temporal", "").strip()
    viagem_de = request.GET.get("viagem_de", "").strip()
    viagem_ate = request.GET.get("viagem_ate", "").strip()
    sort = request.GET.get("sort", "").strip()

    eventos = Evento.objects.select_related("unidade_responsavel", "responsavel").prefetch_related(
        "anexos",
        "oficios",
        "oficios__servidores",
        "oficios__servidores__cargo",
        "oficios__servidores__unidade",
        "oficios__servidores_termo_autorizacao",
        "oficios__viatura",
        "oficios__motorista",
        "oficios__roteiro",
        "oficios__roteiro__destinos__cidade__estado",
        "oficios__roteiro__trechos",
        "planos_trabalho",
        "planos_trabalho__programa",
        "planos_trabalho__destino_cidade__estado",
        "ordens_servico",
        "ordens_servico__destinos__estado",
    )
    if q:
        q_unaccent = remove_accents(q)
        eventos = eventos.filter(
            Q(titulo__unaccent__icontains=q_unaccent)
            | Q(descricao__unaccent__icontains=q_unaccent)
            | Q(motivo__unaccent__icontains=q_unaccent)
            | Q(destino_cidade__unaccent__icontains=q_unaccent)
            | Q(destino_uf__unaccent__icontains=q_unaccent)
            | Q(responsavel__nome__unaccent__icontains=q_unaccent)
            | Q(unidade_responsavel__nome__unaccent__icontains=q_unaccent)
        )

    hoje = timezone.localdate()
    if temporal == "futuro":
        eventos = eventos.filter(data_inicio__gt=hoje)
    elif temporal == "andamento":
        eventos = eventos.filter(data_inicio__lte=hoje, data_fim__gte=hoje)
    elif temporal == "passado":
        eventos = eventos.filter(data_fim__lt=hoje)

    viagem_de_date = parse_date(viagem_de) if viagem_de else None
    viagem_ate_date = parse_date(viagem_ate) if viagem_ate else None
    if viagem_de_date:
        eventos = eventos.filter(Q(data_fim__gte=viagem_de_date) | Q(data_fim__isnull=True))
    if viagem_ate_date:
        eventos = eventos.filter(data_inicio__lte=viagem_ate_date)

    sort_map = {
        "numero_desc": ("-data_inicio", "-criado_em"),
        "numero_asc": ("data_inicio", "criado_em"),
        "criacao_desc": ("-criado_em",),
        "criacao_asc": ("criado_em",),
        "viagem_asc": ("data_inicio", "-criado_em"),
        "viagem_desc": ("-data_inicio", "-criado_em"),
    }
    eventos = eventos.order_by(*sort_map.get(sort or "numero_desc", sort_map["numero_desc"]))
    has_filters = any([q, temporal, viagem_de, viagem_ate, sort])
    cards = [apresentar_evento_list_card(evento) for evento in eventos]

    return render(
        request,
        "eventos/index.html",
        {
            "page_title": "Eventos",
            "page_description": "Agrupadores opcionais para organizar documentos relacionados.",
            "q": q,
            "temporal": temporal,
            "viagem_de": viagem_de,
            "viagem_ate": viagem_ate,
            "sort": sort,
            "has_filters": has_filters,
            "eventos": eventos,
            "cards": cards,
            "novo_url": reverse("eventos:novo"),
            "search_clear_url": reverse("eventos:index"),
            "temporal_options": [
                {"value": "", "label": "Qualquer período"},
                {"value": "futuro", "label": "Futuras"},
                {"value": "andamento", "label": "Em andamento"},
                {"value": "passado", "label": "Passadas"},
            ],
            "sort_options": [
                {"value": "numero_desc", "label": "Número: maior"},
                {"value": "numero_asc", "label": "Número: menor"},
                {"value": "criacao_desc", "label": "Criação: mais recente"},
                {"value": "criacao_asc", "label": "Criação: mais antiga"},
                {"value": "viagem_asc", "label": "Viagem: mais próxima"},
                {"value": "viagem_desc", "label": "Viagem: mais distante"},
            ],
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


def _roteiro_rows_do_evento(evento):
    """Retorna linhas de roteiros do evento: diretos (roteiro.evento) + via oficios."""
    from roteiros.models import Roteiro

    roteiros = (
        Roteiro.objects.filter(Q(evento=evento) | Q(oficios__evento=evento))
        .distinct()
        .order_by("-created_at")
        .prefetch_related("destinos__cidade__estado", "trechos")
    )
    return [
        apresentar_linha_lista_simples_roteiro(
            r,
            edit_url=reverse("roteiros:editar", args=[r.pk]),
            delete_url=reverse("roteiros:excluir", args=[r.pk]),
            delete_modal=True,
        )
        for r in roteiros
    ]


def _termos_do_evento(evento):
    """Retorna termos do evento: diretos (termo.evento) + via oficios vinculados ao evento."""
    from termos.models import TermoAutorizacao

    return (
        TermoAutorizacao.objects.filter(Q(evento=evento) | Q(oficio__evento=evento))
        .distinct()
        .select_related("destino_cidade__estado", "destino_estado", "viatura", "oficio")
        .prefetch_related("servidores")
        .order_by("-created_at")
    )


def _garantir_termo_automatico(evento):
    """Cria um TermoAutorizacao vazio vinculado ao evento se ainda não existir nenhum."""
    from termos.models import TermoAutorizacao

    if TermoAutorizacao.objects.filter(Q(evento=evento) | Q(oficio__evento=evento)).exists():
        return
    from eventos.services import resolve_evento_cidade_estado

    cidade, estado = resolve_evento_cidade_estado(evento)
    TermoAutorizacao.objects.create(
        evento=evento,
        destino_estado=estado,
        destino_cidade=cidade,
        data_evento_inicio=evento.data_inicio,
        data_evento_fim=evento.data_fim or evento.data_inicio,
    )


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
                nomes = [tipo.nome for tipo in form.cleaned_data.get("tipos") or []]
                evento.titulo = " / ".join(nomes) if nomes else "Novo Evento"
            _save_destinos_extras(evento, request)
            evento.save()
            form.save_m2m()
            form.sincronizar_documentos_vinculados(evento)
            _garantir_termo_automatico(evento)
            messages.success(request, "Dados do evento atualizados.")
            return redirect("eventos:guiado_etapa", pk=evento.pk, etapa=2)
    else:
        form = EventoNovoCadastroForm(instance=evento) if etapa == 1 else None

    # — upload de documentos de solicitação (etapa 4) —
    solicitacao_form_errors = []
    if request.method == "POST" and request.POST.get("action") == "upload_solicitacao":
        from django.core.validators import FileExtensionValidator
        from django.core.exceptions import ValidationError

        arquivos = request.FILES.getlist("solicitacao_arquivos")
        validator = FileExtensionValidator(EVENTO_SOLICITACAO_EXTENSOES)
        erros = False
        for arquivo in arquivos:
            try:
                validator(arquivo)
            except ValidationError:
                erros = True
                break
        if erros or not arquivos:
            if not arquivos:
                messages.error(request, "Nenhum arquivo selecionado.")
            else:
                messages.error(request, "Formato inválido. Aceita apenas PDF, PNG, JPG ou JPEG.")
        else:
            for arquivo in arquivos:
                EventoDocumentoSolicitacao.objects.create(
                    evento=evento,
                    arquivo=arquivo,
                    nome_original=Path(arquivo.name).name,
                )
            messages.success(request, "Documentos de solicitação anexados com sucesso.")
        return redirect("eventos:guiado_etapa", pk=evento.pk, etapa=4)

    solicitacao_anexos = [
        {
            "id": a.pk,
            "nome": a.nome_original or a.arquivo.name.split("/")[-1],
            "url": a.arquivo.url,
            "delete_url": reverse("eventos:excluir_solicitacao_anexo", args=[evento.pk, a.pk]),
        }
        for a in evento.documentos_solicitacao.all()
    ]

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
            "oficio_cards": [
                apresentar_oficio_card(
                    oficio,
                    excluir_next_url=_reverse("eventos:guiado_etapa", kwargs={"pk": evento.pk, "etapa": 3}),
                )
                for oficio in evento.oficios.all()
            ],
            "roteiro_rows": _roteiro_rows_do_evento(evento),
            "plano_cards": [apresentar_plano_card(plano) for plano in evento.planos_trabalho.all()],
            "ordem_cards": [apresentar_ordem_servico_card(ordem) for ordem in evento.ordens_servico.all()],
            "termos": _termos_do_evento(evento),
            "sede_uf": config.uf if config else "",
            "modelos_motivo_url": _reverse("oficios:modelos_motivo_index"),
            "tipos_evento_url": f"{_reverse('eventos:tipos_index')}?{urlencode({'next': request.path})}",
            "solicitacao_anexos": solicitacao_anexos,
            "evento_status_variant": "danger" if evento.status == Evento.STATUS_CANCELADO else "active",
            "cancelar_evento_url": _reverse("eventos:cancelar", kwargs={"pk": evento.pk}),
            **guided_context,
        },
    )


@require_POST
def excluir_solicitacao_anexo(request, pk, anexo_pk):
    evento = get_object_or_404(Evento, pk=pk)
    try:
        anexo = EventoDocumentoSolicitacao.objects.get(pk=anexo_pk, evento=evento)
        anexo.arquivo.delete(save=False)
        anexo.delete()
        messages.success(request, "Documento removido.")
    except EventoDocumentoSolicitacao.DoesNotExist:
        messages.error(request, "Documento não encontrado.")
    return redirect("eventos:guiado_etapa", pk=pk, etapa=4)


def guiado_termos(request, pk):
    return detalhe(request, pk, etapa=5)


@require_http_methods(["POST"])
def excluir(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    titulo = evento.titulo or f"Evento #{pk}"
    evento.delete()
    messages.success(request, f'Evento "{titulo}" excluído.')
    return redirect("eventos:index")


@require_POST
def cancelar(request, pk):
    evento = get_object_or_404(Evento, pk=pk)

    if evento.status == Evento.STATUS_CANCELADO:
        messages.error(request, "Este evento já está cancelado.")
        return redirect("eventos:detalhe", pk=pk)

    motivo = (request.POST.get("motivo") or "").strip()
    if not motivo:
        messages.error(request, "Informe o motivo do cancelamento.")
        return redirect("eventos:detalhe", pk=pk)

    evento.cancelar(motivo)
    messages.success(request, "Evento cancelado. Todos os documentos vinculados também foram cancelados.")
    return redirect("eventos:detalhe", pk=pk)
