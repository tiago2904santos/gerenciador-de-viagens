import json
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST

from cadastros.models import Cidade
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Estado
from cadastros.selectors import buscar_estado_por_sigla
from cadastros.selectors import listar_estados
from cadastros.services import resolver_sede_ids_desde_configuracao
from core.private_media import private_file_response
from roteiros.selectors import listar_cidades_para_select

from oficios.presenters import apresentar_oficio_card
from ordens_servico.presenters import apresentar_ordem_servico_card
from ordens_servico.presenters import get_assinante_os
from planos_trabalho.presenters import apresentar_plano_card
from roteiros.presenters import apresentar_linha_lista_simples_roteiro
from termos.presenters import apresentar_linha_lista_simples_termo

from prestacoes_contas.forms import PrestacaoMultipleFileField
from prestacoes_contas.forms import PrestacaoMultipleFileInput

from .forms import EventoForm
from .forms import EventoNovoCadastroForm
from .models import Evento
from .models import EVENTO_SOLICITACAO_EXTENSOES
from .catalogs import tipo_editar  # noqa: F401  (re-export para urls.py)
from .catalogs import tipo_excluir  # noqa: F401
from .catalogs import tipos_index  # noqa: F401
from .presenters import apresentar_evento_list_card
from .presenters import build_evento_documentos_context
from .selectors import buscar_documento_solicitacao
from .selectors import get_documento_solicitacao_by_id
from .selectors import get_evento_anexo_by_id
from .selectors import get_evento_by_id
from .selectors import listar_eventos
from .selectors import listar_roteiros_do_evento
from .selectors import listar_termos_do_evento
from .selectors import listar_termos_genericos_do_evento
from .services import anexar_documentos_solicitacao
from .services import build_evento_guided_context
from .services import excluir_documento_solicitacao
from .services import excluir_evento
from .services import garantir_termo_automatico


def _sede_config_label():
    """Nome da sede das Configurações — origem fixa da prévia de Destinos."""
    estado_id, cidade_id, _aviso = resolver_sede_ids_desde_configuracao()
    if cidade_id:
        cidade = Cidade.objects.filter(pk=cidade_id).only("nome").first()
        if cidade and cidade.nome:
            return cidade.nome
    if estado_id:
        estado = Estado.objects.filter(pk=estado_id).only("sigla", "nome").first()
        if estado:
            return estado.sigla or estado.nome
    return ""


def api_cidades_por_uf(request, uf):
    uf = (uf or "").strip().upper()
    estado = buscar_estado_por_sigla(uf)
    if estado is None:
        return JsonResponse([], safe=False)
    cidades = listar_cidades_para_select(estado_id=estado.pk)
    return JsonResponse([{"id": c.nome, "nome": c.nome} for c in cidades], safe=False)


def index(request):
    from core import documento_abas as tabs

    q = request.GET.get("q", "").strip()
    aba = tabs.normalizar_aba(request.GET.get("aba", ""))
    viagem_de = request.GET.get("viagem_de", "").strip()
    viagem_ate = request.GET.get("viagem_ate", "").strip()
    sort = request.GET.get("sort", "").strip()

    eventos = listar_eventos(
        q=q or None,
        viagem_de=parse_date(viagem_de) if viagem_de else None,
        viagem_ate=parse_date(viagem_ate) if viagem_ate else None,
        sort=sort or None,
    )

    cancelado_q = Q(status=Evento.STATUS_CANCELADO)
    date_field = "data_inicio"
    lista = eventos.filter(tabs.q_da_aba(aba, date_field=date_field, cancelado_q=cancelado_q))
    contagem = tabs.contar_por_aba(eventos, date_field=date_field, cancelado_q=cancelado_q)
    abas = tabs.build_abas(
        reverse("eventos:index"), aba, contagem,
        preserved={"q": q, "sort": sort, "viagem_de": viagem_de, "viagem_ate": viagem_ate},
    )
    has_filters = any([q, viagem_de, viagem_ate, sort])
    page_obj = Paginator(lista, 20).get_page(request.GET.get("page"))
    cards = [apresentar_evento_list_card(evento) for evento in page_obj.object_list]
    page_querystring = request.GET.copy()
    page_querystring.pop("page", None)

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
            "eventos": page_obj.object_list,
            "cards": cards,
            "page_obj": page_obj,
            "page_querystring": page_querystring.urlencode(),
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

def _form_context(form, evento=None):
    is_edit = bool(evento and evento.pk)
    page_description = "Agrupe documentos, roteiros e anexos sem tornar o evento obrigatório."
    index_url = reverse("eventos:index")
    status_label = evento.get_status_display() if is_edit else "Novo"
    status_variant = "active" if is_edit else "draft"
    return {
        "page_title": "Editar Evento" if is_edit else "Cadastro de Evento",
        "page_description": page_description,
        "form": form,
        "evento": evento,
        "index_url": index_url,
        "panel_url": reverse("eventos:detalhe", kwargs={"pk": evento.pk}) if is_edit else "",
        "status_label": status_label,
        "status_variant": status_variant,
        # `H-02`: contexto do casco único (`components/page/flow_base.html`).
        "flow_eyebrow": "EVENTOS",
        "flow_description": page_description,
        "flow_icon_label": "EV",
        "flow_module_label": "Eventos",
        "flow_back_label": "Voltar à lista",
        "flow_back_url": index_url,
        "flow_status_label": status_label,
        "flow_status_variant": status_variant,
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
    roteiros = listar_roteiros_do_evento(evento)
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


def _termo_rows_do_evento(evento):
    """Lista unificada: termos genéricos do evento + termos por servidor."""
    return _termo_generico_rows_do_evento(evento) + _termos_servidor_rows_do_evento(evento)


def _termo_generico_rows_do_evento(evento):
    """Termo(s) genérico(s) do evento (evento.termo direto, sem ofício) — sempre no topo da lista."""
    return _apresentar_termos_rows(listar_termos_genericos_do_evento(evento))


def _termos_servidor_rows_do_evento(evento):
    """Termos individuais por servidor: um card por servidor efetivo de cada termo do evento."""
    from termos.presenters import apresentar_linha_lista_simples_termo_servidor
    from termos.services import termo_cadastro_assinado_info

    termos = listar_termos_do_evento(evento)
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


@require_http_methods(["GET", "POST"])
def novo(request):
    if request.method == "GET":
        return render(
            request,
            "components/create_draft.html",
            {
                "page_title": "Novo evento",
                "page_description": "Confirme para iniciar o cadastro guiado do evento.",
                "confirm_label": "Criar evento",
                "back_url": reverse("eventos:index"),
            },
        )
    area = getattr(request, "area", None)
    if area is None:
        return HttpResponseForbidden(
            "Selecione uma área de trabalho antes de criar o evento.",
        )
    evento = Evento(area=area)
    evento.save()
    return redirect("eventos:guiado_etapa", pk=evento.pk, etapa=1)


@require_http_methods(["GET", "POST"])
def editar(request, pk):
    evento = get_evento_by_id(pk)
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
    evento = get_evento_by_id(pk)

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
            garantir_termo_automatico(evento)
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
            anexar_documentos_solicitacao(evento, convertidos)
            messages.success(request, "Documentos de solicitação anexados com sucesso.")
        return redirect("eventos:guiado_etapa", pk=evento.pk, etapa=4)

    solicitacao_anexos = [
        {
            "id": a.pk,
            "nome": a.nome_original or a.arquivo.name.split("/")[-1],
            "url": reverse("eventos:solicitacao_anexo_conteudo", args=[evento.pk, a.pk]),
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
    # O assinante e o mesmo para todas as OS do evento, entao e resolvido uma
    # vez — mas so quando ha OS. Resolver incondicionalmente custaria consulta
    # em todo evento sem Ordem de Servico, que e a maioria.
    ordens_do_evento = list(evento.ordens_servico.all())
    assinante_os = get_assinante_os() if ordens_do_evento else None
    from django.urls import reverse as _reverse
    return render(
        request,
        "eventos/detalhe.html",
        {
            "page_title": evento_header_title,
            "evento": evento,
            "evento_header_title": evento_header_title,
            "evento_header_description": evento_header_description,
            # `H-02`: contexto do casco único (`components/page/flow_base.html`).
            "flow_eyebrow": "EVENTOS",
            "flow_description": evento_header_description,
            "flow_icon_label": "EV",
            "flow_module_label": "Eventos",
            "flow_back_label": "Voltar para lista",
            "flow_back_url": _reverse("eventos:index"),
            "flow_status_label": evento.get_status_display(),
            "evento_form": form,
            "estados": listar_estados(),
            "oficio_cards": [
                apresentar_oficio_card(
                    oficio,
                    excluir_next_url=_reverse("eventos:guiado_etapa", kwargs={"pk": evento.pk, "etapa": 3}),
                )
                for oficio in evento.oficios.all()
            ],
            "roteiro_rows": _roteiro_rows_do_evento(evento),
            "plano_cards": [apresentar_plano_card(plano) for plano in evento.planos_trabalho.all()],
            "ordem_cards": [
                apresentar_ordem_servico_card(ordem, assinante=assinante_os)
                for ordem in ordens_do_evento
            ],
            "termo_rows": _termo_rows_do_evento(evento),
            "sede_uf": config.uf if config else "",
            "sede_config_label": _sede_config_label(),
            "modelos_motivo_url": _reverse("oficios:modelos_motivo_index"),
            "tipos_evento_url": f"{_reverse('eventos:tipos_index')}?{urlencode({'next': request.path})}",
            "solicitacao_anexos": solicitacao_anexos,
            "evento_status_variant": "danger" if evento.status == Evento.STATUS_CANCELADO else "active",
            "flow_status_variant": "danger" if evento.status == Evento.STATUS_CANCELADO else "active",
            "cancelar_evento_url": _reverse("eventos:cancelar", kwargs={"pk": evento.pk}),
            "reativar_evento_url": _reverse("eventos:reativar", kwargs={"pk": evento.pk}),
            **guided_context,
            **build_evento_documentos_context(form),
        },
    )


@require_POST
def anexar_solicitacao(request, pk):
    """Upload via modal Anexar documento (campo ``arquivo`` do attach-signed)."""
    from django.core.validators import FileExtensionValidator
    from django.core.exceptions import ValidationError
    from PIL import UnidentifiedImageError

    from core.retorno import voltar_para
    from .services import converter_para_pdf_se_necessario

    evento = get_evento_by_id(pk)
    fallback = reverse("eventos:guiado_etapa", kwargs={"pk": pk, "etapa": 4})
    arquivo = request.FILES.get("arquivo")
    if not arquivo:
        messages.error(request, "Nenhum arquivo selecionado.")
        return redirect(voltar_para(request, fallback))

    validator = FileExtensionValidator(EVENTO_SOLICITACAO_EXTENSOES)
    try:
        validator(arquivo)
        convertido = converter_para_pdf_se_necessario(arquivo)
    except (ValidationError, UnidentifiedImageError):
        messages.error(request, "Formato inválido. Aceita apenas PDF, PNG, JPG ou JPEG.")
        return redirect(voltar_para(request, fallback))

    anexar_documentos_solicitacao(evento, [convertido])
    messages.success(request, "Documentos de solicitação anexados com sucesso.")
    return redirect(voltar_para(request, fallback))


@require_POST
def excluir_solicitacao_anexo(request, pk, anexo_pk):
    evento = get_evento_by_id(pk)
    anexo = buscar_documento_solicitacao(evento, anexo_pk)
    if anexo is None:
        messages.error(request, "Documento não encontrado.")
    else:
        excluir_documento_solicitacao(anexo)
        messages.success(request, "Documento removido.")
    return redirect("eventos:guiado_etapa", pk=pk, etapa=4)


def solicitacao_anexo_conteudo(request, pk, anexo_pk):
    evento = get_evento_by_id(pk)
    anexo = get_documento_solicitacao_by_id(evento, anexo_pk)
    return private_file_response(anexo.arquivo)


def evento_anexo_conteudo(request, pk, anexo_pk):
    evento = get_evento_by_id(pk)
    anexo = get_evento_anexo_by_id(evento, anexo_pk)
    return private_file_response(anexo.arquivo)


def guiado_termos(request, pk):
    return detalhe(request, pk, etapa=5)


@require_http_methods(["POST"])
def excluir(request, pk):
    evento = get_evento_by_id(pk)
    titulo = evento.titulo or f"Evento #{pk}"
    excluir_evento(evento)
    messages.success(request, f'Evento "{titulo}" excluído.')
    return redirect("eventos:index")


@require_POST
def cancelar(request, pk):
    evento = get_evento_by_id(pk)

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
    evento = get_evento_by_id(pk)

    if evento.status != Evento.STATUS_CANCELADO:
        messages.error(request, "Este evento não está cancelado.")
        return redirect("eventos:detalhe", pk=pk)

    evento.reativar()
    messages.success(request, "Evento reativado. Os documentos cancelados junto com ele também foram reativados.")
    return redirect("eventos:detalhe", pk=pk)
