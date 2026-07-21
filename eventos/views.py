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
from core.tenancy import filter_queryset_by_area
from roteiros.selectors import listar_cidades_para_select

from oficios.presenters import apresentar_oficio_card
from ordens_servico.presenters import apresentar_ordem_servico_card
from planos_trabalho.presenters import apresentar_plano_card
from roteiros.presenters import apresentar_linha_lista_simples_roteiro
from termos.presenters import apresentar_linha_lista_simples_termo

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
from .presenters import build_evento_documentos_context
from .services import build_evento_guided_context
from .services import excluir_evento


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
        tipo = form.save(commit=False)
        tipo.area = getattr(request, "area", None)
        tipo.save()
        messages.success(request, "Tipo de evento criado com sucesso.")
        redirect_url = reverse("eventos:tipos_index")
        if back_url:
            redirect_url = f"{redirect_url}?{urlencode({'next': back_url})}"
        return redirect(redirect_url)
    tipos = filter_queryset_by_area(TipoEvento.objects).all()
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
        },
    )


def tipo_editar(request, pk):
    """Edição inline via quick edit da lista; a página standalone foi removida."""
    tipo = get_object_or_404(filter_queryset_by_area(TipoEvento.objects), pk=pk)
    form = TipoEventoForm(request.POST or None, instance=tipo)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Tipo de evento atualizado com sucesso.")
        else:
            messages.error(request, "Não foi possível salvar o tipo. Verifique os dados informados.")
    return redirect("eventos:tipos_index")


def tipo_excluir(request, pk):
    tipo = get_object_or_404(filter_queryset_by_area(TipoEvento.objects), pk=pk)
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
    from django.db.models import OuterRef
    from core import documento_abas as tabs
    from prestacoes_contas.models import PrestacaoServidor

    q = request.GET.get("q", "").strip()
    aba = tabs.normalizar_aba(request.GET.get("aba", ""))
    viagem_de = request.GET.get("viagem_de", "").strip()
    viagem_ate = request.GET.get("viagem_ate", "").strip()
    sort = request.GET.get("sort", "").strip()

    eventos = filter_queryset_by_area(Evento.objects).select_related("unidade_responsavel", "responsavel").prefetch_related(
        "anexos",
        "oficios",
        "oficios__servidores",
        "oficios__servidores__cargo",
        "oficios__servidores__unidade",
        "oficios__servidores_termo_autorizacao",
        "oficios__viatura",
        "oficios__motorista",
        "oficios__roteiro",
        "oficios__roteiro__origem_cidade",
        "oficios__roteiro__destinos__cidade__estado",
        "oficios__roteiro__trechos",
        "roteiros",
        "roteiros__origem_cidade",
        "planos_trabalho",
        "planos_trabalho__programa",
        "planos_trabalho__destino_cidade__estado",
        "ordens_servico",
        "ordens_servico__destinos__estado",
        "documentos_solicitacao",
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
    eventos = eventos.order_by(*sort_map.get(sort or "criacao_desc", sort_map["criacao_desc"]))

    # Abas: Finalizado = todas as prestações dos ofícios (não cancelados) do
    # evento já finalizadas.
    sub = PrestacaoServidor.objects.filter(prestacao__oficio__evento=OuterRef("pk"), prestacao__oficio__cancelado=False)
    eventos = tabs.anotar_finalizacao(eventos, sub, sub.filter(finalizada=False))
    cancelado_q = Q(status=Evento.STATUS_CANCELADO)
    date_field = "data_inicio"
    lista = eventos.filter(tabs.q_da_aba(aba, date_field=date_field, cancelado_q=cancelado_q))
    contagem = tabs.contar_por_aba(eventos, date_field=date_field, cancelado_q=cancelado_q)
    abas = tabs.build_abas(
        reverse("eventos:index"), aba, contagem,
        preserved={"q": q, "sort": sort, "viagem_de": viagem_de, "viagem_ate": viagem_ate},
    )
    has_filters = any([q, viagem_de, viagem_ate, sort])
    cards = [apresentar_evento_list_card(evento) for evento in lista]

    return render(
        request,
        "eventos/index.html",
        {
            "page_title": "Eventos",
            "page_description": "Agrupadores opcionais para organizar documentos relacionados.",
            "q": q,
            "aba": aba,
            "abas": abas,
            "viagem_de": viagem_de,
            "viagem_ate": viagem_ate,
            "sort": sort,
            "has_filters": has_filters,
            "eventos": lista,
            "cards": cards,
            "novo_url": reverse("eventos:novo"),
            "search_clear_url": f"{reverse('eventos:index')}?aba={aba}",
            "sort_options": [
                {"value": "criacao_desc", "label": "Criação: mais recente"},
                {"value": "criacao_asc", "label": "Criação: mais antiga"},
                {"value": "numero_desc", "label": "Número: maior"},
                {"value": "numero_asc", "label": "Número: menor"},
                {"value": "viagem_asc", "label": "Viagem: mais próxima"},
                {"value": "viagem_desc", "label": "Viagem: mais distante"},
            ],
        },
    )

def _evento_queryset():
    return filter_queryset_by_area(Evento.objects).select_related("unidade_responsavel", "responsavel").prefetch_related(
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
    next_url = reverse("eventos:guiado_etapa", kwargs={"pk": evento.pk, "etapa": 2})
    return [
        apresentar_linha_lista_simples_roteiro(
            r,
            edit_url=f"{reverse('roteiros:editar', args=[r.pk])}?{urlencode({'next': next_url})}",
            delete_url=reverse("roteiros:excluir", args=[r.pk]),
            delete_modal=True,
        )
        for r in roteiros
    ]


def _apresentar_termos_rows(termos_qs):
    from termos.services import termo_cadastro_assinado_info

    return [
        apresentar_linha_lista_simples_termo(
            termo,
            edit_url=reverse("termos:editar", args=[termo.pk]),
            delete_url=reverse("termos:excluir", args=[termo.pk]),
            delete_modal=True,
            pdf_url=reverse("termos:baixar_termo_cadastro_pdf", args=[termo.pk]),
            docx_url=reverse("termos:baixar_termo_cadastro_docx", args=[termo.pk]),
            **termo_cadastro_assinado_info(termo, None),
        )
        for termo in termos_qs
    ]


def _termo_generico_rows_do_evento(evento):
    """Termo(s) genérico(s) do evento (evento.termo direto, sem ofício) — sempre no topo da lista."""
    from termos.models import TermoAutorizacao

    termos = (
        TermoAutorizacao.objects.filter(evento=evento, oficio__isnull=True)
        .select_related("destino_cidade__estado", "destino_estado", "viatura")
        .prefetch_related("servidores")
        .order_by("-created_at")
    )
    return _apresentar_termos_rows(termos)


def _termos_servidor_rows_do_evento(evento):
    """Termos individuais por servidor: um card por servidor efetivo de cada termo do evento."""
    from termos.models import TermoAutorizacao
    from termos.presenters import apresentar_linha_lista_simples_termo_servidor
    from termos.services import termo_cadastro_assinado_info

    termos = (
        TermoAutorizacao.objects.filter(Q(evento=evento) | Q(oficio__evento=evento))
        .select_related("destino_cidade__estado", "destino_estado", "viatura", "oficio")
        .prefetch_related("servidores")
        .order_by("-created_at")
    )
    rows = []
    vistos = set()
    for termo in termos:
        for servidor, oficio_origem in termo.servidores_efetivos_com_oficio():
            chave = (termo.pk, servidor.pk)
            if chave in vistos:
                continue
            vistos.add(chave)
            rows.append(
                apresentar_linha_lista_simples_termo_servidor(
                    termo,
                    servidor,
                    oficio=oficio_origem,
                    edit_url=reverse("termos:editar", args=[termo.pk]),
                    pdf_url=reverse("termos:termo_cadastro_servidor_pdf_inline", args=[termo.pk, servidor.pk]),
                    **termo_cadastro_assinado_info(termo, servidor.pk),
                )
            )
    return rows


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
    evento = Evento(area=getattr(request, "area", None))
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
            if evento.area_id is None:
                evento.area = getattr(request, "area", None)
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
        from PIL import UnidentifiedImageError

        from .services import converter_para_pdf_se_necessario

        arquivos = request.FILES.getlist("solicitacao_arquivos")
        validator = FileExtensionValidator(EVENTO_SOLICITACAO_EXTENSOES)
        erros = False
        convertidos = []
        for arquivo in arquivos:
            try:
                validator(arquivo)
                convertidos.append(converter_para_pdf_se_necessario(arquivo))
            except (ValidationError, UnidentifiedImageError):
                erros = True
                break
        if erros or not arquivos:
            if not arquivos:
                messages.error(request, "Nenhum arquivo selecionado.")
            else:
                messages.error(request, "Formato inválido. Aceita apenas PDF, PNG, JPG ou JPEG.")
        else:
            for arquivo_pdf in convertidos:
                EventoDocumentoSolicitacao.objects.create(
                    evento=evento,
                    arquivo=arquivo_pdf,
                    nome_original=Path(arquivo_pdf.name).name,
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
    current_step = next(
        (step for step in guided_context["evento_page_steps"] if step.get("aria_current") == "step"),
        None,
    )
    evento_header_title = (evento.titulo or "").strip() or "Novo evento"
    evento_header_description = f"Etapa {guided_context['etapa_atual']} de 5"
    if current_step:
        evento_header_description += f" · {current_step['title']}"
    if evento.periodo_display:
        evento_header_description += f" · {evento.periodo_display}"
    config = ConfiguracaoSistema.get_singleton()
    from django.urls import reverse as _reverse
    return render(
        request,
        "eventos/detalhe.html",
        {
            "page_title": evento_header_title,
            "evento": evento,
            "evento_header_title": evento_header_title,
            "evento_header_description": evento_header_description,
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
            "termo_generico_rows": _termo_generico_rows_do_evento(evento),
            "termos_servidor_rows": _termos_servidor_rows_do_evento(evento),
            "sede_uf": config.uf if config else "",
            "modelos_motivo_url": _reverse("oficios:modelos_motivo_index"),
            "tipos_evento_url": f"{_reverse('eventos:tipos_index')}?{urlencode({'next': request.path})}",
            "solicitacao_anexos": solicitacao_anexos,
            "evento_status_variant": "danger" if evento.status == Evento.STATUS_CANCELADO else "active",
            "cancelar_evento_url": _reverse("eventos:cancelar", kwargs={"pk": evento.pk}),
            "reativar_evento_url": _reverse("eventos:reativar", kwargs={"pk": evento.pk}),
            **guided_context,
            **build_evento_documentos_context(form),
        },
    )


@require_POST
def excluir_solicitacao_anexo(request, pk, anexo_pk):
    evento = get_object_or_404(_evento_queryset(), pk=pk)
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
    evento = get_object_or_404(_evento_queryset(), pk=pk)
    titulo = evento.titulo or f"Evento #{pk}"
    excluir_evento(evento)
    messages.success(request, f'Evento "{titulo}" excluído.')
    return redirect("eventos:index")


@require_POST
def cancelar(request, pk):
    evento = get_object_or_404(_evento_queryset(), pk=pk)

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


@require_POST
def reativar(request, pk):
    evento = get_object_or_404(_evento_queryset(), pk=pk)

    if evento.status != Evento.STATUS_CANCELADO:
        messages.error(request, "Este evento não está cancelado.")
        return redirect("eventos:detalhe", pk=pk)

    evento.reativar()
    messages.success(request, "Evento reativado. Os documentos cancelados junto com ele também foram reativados.")
    return redirect("eventos:detalhe", pk=pk)
