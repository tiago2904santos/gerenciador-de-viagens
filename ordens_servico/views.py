from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.parse import urlencode

from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_http_methods

from core.pagination import contexto_paginacao
from documentos.services.async_generation import enfileirar_documento
from documentos.services.types import DocumentoFormato
from eventos.services import build_evento_document_seed
from eventos.services import resolve_evento_from_request

from .forms import OrdemServicoForm
from .models import OrdemServico
from .presenters import apresentar_ordem_servico_card
from .presenters import get_assinante_os
from .selectors import get_ordem_servico_by_id
from .selectors import listar_ordens_servico


# Mesmo tamanho de página das demais listas em cards (Ofícios, Eventos, PT).
ORDENS_POR_PAGINA = 20


def _digits(value):
    return re.sub(r"\D", "", str(value or ""))


def _roteiro_destino_label(item):
    if not item:
        return ""
    if item.cidade_id:
        return str(item.cidade)
    if item.estado_id:
        return str(item.estado)
    return str(item)


def index(request):
    from core import documento_abas as tabs

    q = request.GET.get("q", "").strip()
    aba = tabs.normalizar_aba(request.GET.get("aba", ""))
    viagem_de = request.GET.get("viagem_de", "").strip()
    viagem_ate = request.GET.get("viagem_ate", "").strip()
    sort = request.GET.get("sort", "").strip()

    ordens = listar_ordens_servico(
        q=q or None,
        viagem_de=parse_date(viagem_de) if viagem_de else None,
        viagem_ate=parse_date(viagem_ate) if viagem_ate else None,
        sort=sort or None,
    )

    cancelado_q = Q(cancelado=True)
    date_field = "data_evento_inicio"
    lista = ordens.filter(tabs.q_da_aba(aba, date_field=date_field, cancelado_q=cancelado_q))
    contagem = tabs.contar_por_aba(ordens, date_field=date_field, cancelado_q=cancelado_q)
    abas = tabs.build_abas(
        reverse("ordens_servico:index"), aba, contagem,
        preserved={"q": q, "sort": sort, "viagem_de": viagem_de, "viagem_ate": viagem_ate},
    )

    paginacao = contexto_paginacao(lista, request, ORDENS_POR_PAGINA)
    # Um assinante por pagina, nao um por card (`NOVO-07`).
    assinante = get_assinante_os(area=getattr(request, "area", None))
    cards = [
        apresentar_ordem_servico_card(ordem, assinante=assinante)
        for ordem in paginacao["page_obj"].object_list
    ]
    has_filters = any([q, viagem_de, viagem_ate, sort])

    return render(
        request,
        "ordens_servico/index.html",
        {
            "page_title": "Ordens de Serviço",
            "page_description": "Cadastre e gerencie ordens de serviço.",
            "q": q,
            "aba": aba,
            "abas": abas,
            "viagem_de": viagem_de,
            "viagem_ate": viagem_ate,
            "sort": sort,
            "has_filters": has_filters,
            "cards": cards,
            "nova_url": reverse("ordens_servico:nova"),
            "search_clear_url": f"{reverse('ordens_servico:index')}?aba={aba}",
            "sort_options": [
                {"value": "numero_desc", "label": "Número: maior"},
                {"value": "numero_asc", "label": "Número: menor"},
                {"value": "criacao_desc", "label": "Criação: mais recente"},
                {"value": "criacao_asc", "label": "Criação: mais antiga"},
                {"value": "viagem_asc", "label": "Viagem: mais próxima"},
                {"value": "viagem_desc", "label": "Viagem: mais distante"},
            ],
            "empty_message": "Nenhuma OS encontrada com os filtros aplicados." if has_filters else "Nenhuma OS cadastrada ainda.",
            **paginacao,
        },
    )

def _evento_etapa_url(evento_id):
    if evento_id:
        return reverse("eventos:guiado_etapa", kwargs={"pk": evento_id, "etapa": 4})
    return ""


def _ordem_lista_url(ordem=None, evento=None):
    evento_id = getattr(evento, "pk", None) or getattr(ordem, "evento_id", None)
    return _evento_etapa_url(evento_id) or reverse("ordens_servico:index")


def _ordem_back_label(ordem=None, evento=None):
    return "Dados do evento" if (getattr(evento, "pk", None) or getattr(ordem, "evento_id", None)) else "Voltar a lista"


def _redirect_ordem_lista(ordem):
    if getattr(ordem, "evento_id", None):
        return redirect("eventos:guiado_etapa", pk=ordem.evento_id, etapa=4)
    return redirect("ordens_servico:editar", pk=ordem.pk)


def _build_oficio_summary(oficio):
    data_inicio = ""
    data_fim = ""
    periodo = ""
    cidade_ids = []
    estado_id = ""
    cidade_id = ""
    destino = ""
    roteiro_label = ""
    sede = ""

    roteiro = oficio.roteiro
    if roteiro:
        sede_obj = roteiro.origem_cidade or roteiro.origem_estado
        sede = str(sede_obj) if sede_obj else ""
        destinos = list(roteiro.destinos.select_related("cidade", "estado").order_by("ordem", "pk"))
        destino_obj = destinos[0] if destinos else None
        destino = _roteiro_destino_label(destino_obj)
        destinos_label = ", ".join(_roteiro_destino_label(item) for item in destinos if item)
        roteiro_label = " -> ".join(part for part in [sede, destinos_label or destino] if part)
        if destino_obj:
            estado_id = destino_obj.estado_id or ""
            cidade_id = destino_obj.cidade_id or ""
        cidade_ids = [item.cidade_id for item in destinos if item.cidade_id]
        if roteiro.saida_dt:
            inicio = roteiro.saida_dt.strftime("%d/%m/%Y")
            data_inicio = roteiro.saida_dt.date().isoformat()
            retorno = getattr(roteiro, "retorno_chegada_dt", None) or getattr(roteiro, "retorno_saida_dt", None)
            fim = retorno.strftime("%d/%m/%Y") if retorno else inicio
            data_fim = retorno.date().isoformat() if retorno else data_inicio
            periodo = inicio if fim == inicio else f"{inicio} a {fim}"

    servidores = list(oficio.servidores.all())
    servidor_ids = [s.pk for s in servidores]
    servidores_nomes = [s.nome for s in servidores]
    viatura_id = oficio.viatura_id or ""
    viatura = str(oficio.viatura) if viatura_id else ""
    viatura_modelo = getattr(oficio.viatura, "modelo", "") if viatura_id else ""

    return {
        "id": oficio.pk,
        "label": f"Oficio {oficio.numero_formatado}",
        "numero": oficio.numero_formatado,
        "numero_busca": " ".join(
            part
            for part in [
                str(oficio.numero or ""),
                f"{oficio.numero:02d}" if oficio.numero else "",
                str(oficio.ano or ""),
                _digits(oficio.numero_formatado),
            ]
            if part
        ),
        "protocolo": oficio.protocolo or "",
        "protocolo_busca": _digits(oficio.protocolo),
        "sede": sede,
        "destino": destino,
        "roteiro": roteiro_label,
        "periodo": periodo,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "cidade_ids": cidade_ids,
        "estado_id": estado_id,
        "cidade_id": cidade_id,
        "servidor_ids": servidor_ids,
        "viatura_id": viatura_id,
        "servidores": len(servidor_ids),
        "servidores_nomes": servidores_nomes,
        "servidores_label": ", ".join(servidores_nomes),
        "viatura": viatura,
        "viatura_modelo": viatura_modelo,
        "motivo": oficio.motivo or "",
        "search_text": " ".join(
            part
            for part in [
                oficio.numero_formatado,
                str(oficio.numero or ""),
                f"{oficio.numero:02d}" if oficio.numero else "",
                str(oficio.ano or ""),
                _digits(oficio.numero_formatado),
                oficio.protocolo or "",
                _digits(oficio.protocolo),
                sede,
                destino,
                roteiro_label,
                periodo,
                viatura,
                viatura_modelo,
                " ".join(servidores_nomes),
                oficio.assunto or "",
            ]
            if part
        ),
    }


def _evento_selected_dates_json(form):
    def as_iso(value):
        if not value:
            return ""
        if hasattr(value, "isoformat"):
            return value.isoformat()
        value = str(value).strip()
        if len(value) == 10 and value[4:5] == "-" and value[7:8] == "-":
            return value
        return ""

    if form.is_bound:
        inicio = as_iso(form.data.get("data_evento_inicio"))
        fim = as_iso(form.data.get("data_evento_fim"))
    else:
        inicio = as_iso(getattr(form.instance, "data_evento_inicio", None))
        fim = as_iso(getattr(form.instance, "data_evento_fim", None))

    if not inicio and not fim:
        return "[]"
    if inicio and not fim:
        return json.dumps([inicio], cls=DjangoJSONEncoder)
    if fim and not inicio:
        return json.dumps([fim], cls=DjangoJSONEncoder)
    if inicio == fim:
        return json.dumps([inicio], cls=DjangoJSONEncoder)
    return json.dumps([inicio, fim], cls=DjangoJSONEncoder)


def _evento_display_values(form):
    def as_display(value):
        if not value:
            return ""
        if hasattr(value, "strftime"):
            return value.strftime("%d/%m/%Y")
        value = str(value).strip()
        if len(value) == 10 and value[4:5] == "-" and value[7:8] == "-":
            try:
                parsed = datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                return value
            return parsed.strftime("%d/%m/%Y")
        return value

    if form.is_bound:
        return {
            "inicio": as_display(form.data.get("data_evento_inicio")),
            "fim": as_display(form.data.get("data_evento_fim")),
        }
    return {
        "inicio": as_display(getattr(form.instance, "data_evento_inicio", None)),
        "fim": as_display(getattr(form.instance, "data_evento_fim", None)),
    }


def _ordem_is_completa(form, evento_display):
    if not evento_display.get("inicio") or not evento_display.get("fim"):
        return False

    if not form.initial.get("destino_cidade"):
        return False

    if form.is_bound:
        servidores_ok = bool(form.data.getlist("servidores"))
        tipo = (form.data.get("tipo_necessidade") or "").strip()
        tipo_ok = bool(tipo)
        motivo_ok = bool((form.data.get("motivo") or "").strip())
        if tipo == OrdemServico.TIPO_MICROONIBUS:
            equipe_ok = all(
                bool((form.data.get(field_name) or "").strip())
                for field_name in ("motorista_equipe", "tecnico_equipe", "apoio_montagem", "apoio_escolta")
            )
        elif tipo == OrdemServico.TIPO_CAMINHAO:
            equipe_ok = servidores_ok
        elif tipo == OrdemServico.TIPO_CERIMONIAL_ANTECIPADO:
            equipe_ok = all(
                bool((form.data.get(field_name) or "").strip())
                for field_name in ("coordenador_cerimonial", "apoio_cerimonial", "apoio_preparacao")
            )
        else:
            equipe_ok = servidores_ok
    else:
        if form.instance and form.instance.pk:
            servidores_ok = form.instance.servidores.exists()
        else:
            servidores_ok = bool(form.initial.get("servidores"))
        tipo = (getattr(form.instance, "tipo_necessidade", "") or "").strip()
        tipo_ok = bool(tipo)
        motivo_ok = bool((getattr(form.instance, "motivo", "") or "").strip())
        if tipo == OrdemServico.TIPO_MICROONIBUS:
            equipe_ok = all(
                bool(getattr(form.instance, field_name + "_id", None))
                for field_name in ("motorista_equipe", "tecnico_equipe", "apoio_montagem", "apoio_escolta")
            )
        elif tipo == OrdemServico.TIPO_CAMINHAO:
            equipe_ok = servidores_ok
        elif tipo == OrdemServico.TIPO_CERIMONIAL_ANTECIPADO:
            equipe_ok = all(
                bool(getattr(form.instance, field_name + "_id", None))
                for field_name in ("coordenador_cerimonial", "apoio_cerimonial", "apoio_preparacao")
            )
        else:
            equipe_ok = servidores_ok

    return bool(equipe_ok and tipo_ok and motivo_ok)


def _form_context(*, request, form, ordem=None, evento=None):
    oficios_qs = form.fields["oficios"].queryset.select_related(
        "roteiro",
        "roteiro__origem_cidade",
        "roteiro__origem_estado",
        "viatura",
    ).prefetch_related(
        "roteiro__destinos__cidade",
        "roteiro__destinos__estado",
        "servidores",
    )
    summaries = {}
    for order, oficio in enumerate(oficios_qs):
        s = _build_oficio_summary(oficio)
        s["order"] = order
        summaries[str(s["id"])] = s

    servidor_create_url = (
        f"{reverse('cadastros:servidor_create')}"
        f"?{urlencode({'next': request.get_full_path()})}"
    )

    evento_display = _evento_display_values(form)

    index_url = _ordem_lista_url(ordem=ordem, evento=evento)
    back_label = _ordem_back_label(ordem=ordem, evento=evento)

    return {
        "page_title": "Nova Ordem de Serviço" if ordem is None or not ordem.pk else f"Editar {ordem.numero_formatado}",
        "form": form,
        "ordem": ordem,
        "index_url": index_url,
        "back_label": back_label,
        # `H-02`: contexto do casco único (`components/page/flow_base.html`).
        "flow_eyebrow": "DOCUMENTOS",
        "flow_description": "Cadastro de ordem de serviço",
        "flow_icon_label": "OS",
        "flow_module_label": "Ordens de Serviço",
        "flow_back_label": back_label,
        "flow_back_url": index_url,
        "servidor_create_url": servidor_create_url,
        "modelos_motivo_url": f"{reverse('oficios:modelos_motivo_index')}?{urlencode({'next': request.get_full_path()})}",
        "tem_modelos_motivo": form.fields["modelo_motivo"].queryset.exists(),
        "api_cidades_por_estado_url": reverse("roteiros:api_cidades_por_estado", kwargs={"estado_id": 0}),
        "evento_selected_dates_json": _evento_selected_dates_json(form),
        "evento_display": evento_display,
        "os_oficios_summary": summaries,
        "os_funcoes_servidores": getattr(form.instance, "funcoes_servidores", None) or {},
        "os_is_completa": _ordem_is_completa(form, evento_display),
    }


@require_http_methods(["GET", "POST"])
def nova(request):
    evento = resolve_evento_from_request(request)
    seed = build_evento_document_seed(evento) if evento is not None else {}
    ordem = OrdemServico(
        evento=evento,
        data_evento_inicio=seed.get("data_inicio"),
        data_evento_fim=seed.get("data_fim") or seed.get("data_inicio"),
        motivo=seed.get("motivo") or "",
    )
    initial = {}
    if seed.get("estado"):
        initial["destino_estado"] = seed["estado"].pk
    if seed.get("cidade"):
        initial["destino_cidade"] = seed["cidade"].pk
    if seed.get("servidores"):
        initial["servidores"] = [servidor.pk for servidor in seed["servidores"]]
    if seed.get("oficios"):
        initial["oficios"] = [oficio.pk for oficio in seed["oficios"]]
    if request.method == "POST":
        form = OrdemServicoForm(request.POST, instance=ordem)
        if form.is_valid():
            ordem = form.save()
            messages.success(request, "Ordem de Serviço cadastrada.")
            return _redirect_ordem_lista(ordem)
    else:
        form = OrdemServicoForm(instance=ordem, initial=initial)
    return render(request, "ordens_servico/form.html", _form_context(request=request, form=form, ordem=None, evento=evento))


@require_http_methods(["GET", "POST"])
def editar(request, pk):
    ordem = get_ordem_servico_by_id(pk)
    if request.method == "POST":
        form = OrdemServicoForm(request.POST, instance=ordem)
        if form.is_valid():
            ordem = form.save()
            messages.success(request, "Ordem de Serviço atualizada.")
            return _redirect_ordem_lista(ordem)
    else:
        form = OrdemServicoForm(instance=ordem)
    return render(request, "ordens_servico/form.html", _form_context(request=request, form=form, ordem=ordem))


@require_http_methods(["GET"])
def baixar_docx(request, pk):
    ordem = get_ordem_servico_by_id(pk)
    return enfileirar_documento(
        request,
        tipo="ordem_servico",
        parametros={"object_id": ordem.pk, "formato": DocumentoFormato.DOCX.value},
    )


@require_GET
def baixar_pdf(request, pk):
    ordem = get_ordem_servico_by_id(pk)
    return enfileirar_documento(
        request,
        tipo="ordem_servico",
        parametros={"object_id": ordem.pk, "formato": DocumentoFormato.PDF.value},
    )


@require_GET
def pdf_inline(request, pk):
    ordem = get_ordem_servico_by_id(pk)
    return enfileirar_documento(
        request,
        tipo="ordem_servico",
        parametros={"object_id": ordem.pk, "formato": DocumentoFormato.PDF.value},
        disposicao="inline",
    )


@require_http_methods(["POST"])
def excluir(request, pk):
    ordem = get_ordem_servico_by_id(pk)
    numero = ordem.numero_formatado
    ordem.delete()
    messages.success(request, f"Ordem de Serviço {numero} excluída.")
    return redirect("ordens_servico:index")
