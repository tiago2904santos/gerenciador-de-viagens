# Servicos de agrupamento OPCIONAL de documentos ficam neste modulo.
from __future__ import annotations

import json
from pathlib import Path

from core.deletion import excluir_com_protecao
from urllib.parse import urlencode

from django.core.files.base import ContentFile
from django.db import transaction
from django.urls import reverse


_DOCUMENTOS_VINCULAVEIS = (
    ("oficios_vinculados", "oficios"),
    ("ordens_servico_vinculadas", "ordens_servico"),
    ("planos_trabalho_vinculados", "planos_trabalho"),
    ("termos_vinculados", "termos_autorizacao"),
    ("roteiros_vinculados", "roteiros"),
)


def _aplicar_destinos_extras(evento, destinos_json):
    try:
        destinos = json.loads(destinos_json) if destinos_json else []
    except (TypeError, ValueError):
        destinos = []
    if destinos and isinstance(destinos, list):
        primeiro = destinos[0]
        evento.destino_uf = primeiro.get("uf", "")
        evento.destino_cidade = primeiro.get("cidade", "")
        evento.destinos_extras = destinos[1:]
        return
    evento.destinos_extras = []


def _sincronizar_documentos_vinculados(form, evento):
    for field_name, related_name in _DOCUMENTOS_VINCULAVEIS:
        if field_name not in form.cleaned_data:
            continue
        manager = getattr(evento, related_name)
        selecionados_ids = {obj.pk for obj in form.cleaned_data[field_name]}
        atuais_ids = set(manager.values_list("pk", flat=True))
        para_adicionar = selecionados_ids - atuais_ids
        para_remover = atuais_ids - selecionados_ids
        # A area vem do proprio Evento, não do thread-local. Assim o serviço
        # mantém o recorte também em chamada direta, worker e comando.
        base = manager.model.all_objects.filter(area=evento.area)
        if para_adicionar:
            base.filter(pk__in=para_adicionar).update(evento=evento)
        if para_remover:
            base.filter(pk__in=para_remover).update(evento=None)


@transaction.atomic
def salvar_identificacao_evento(form, *, area, destinos_json):
    """Persiste a etapa 1 inteira ou não persiste nenhuma parte (`BE-14`)."""
    evento = form.save(commit=False)
    if evento.area_id is None:
        evento.area = area
    nomes = [tipo.nome for tipo in form.cleaned_data.get("tipos") or []]
    evento.titulo = " / ".join(nomes) if nomes else "Novo Evento"
    _aplicar_destinos_extras(evento, destinos_json)
    evento.save()
    form.save_m2m()
    _sincronizar_documentos_vinculados(form, evento)
    garantir_termo_automatico(evento)
    return evento


def converter_para_pdf_se_necessario(arquivo):
    """Converte um upload de imagem reconhecido pelo Pillow; PDF passa direto.

    Documentos de solicitação aceitam foto/print como conveniência de upload,
    mas o arquivo guardado (e depois enviado ao Drive) precisa ser sempre PDF,
    para manter o mesmo formato dos demais documentos do evento.
    """
    ext = Path(arquivo.name).suffix.lower().lstrip(".")
    if ext == "pdf":
        return arquivo

    from io import BytesIO

    from PIL import Image

    imagem = Image.open(arquivo)
    if imagem.mode != "RGB":
        imagem = imagem.convert("RGB")
    buffer = BytesIO()
    imagem.save(buffer, format="PDF")
    buffer.seek(0)
    nome_pdf = f"{Path(arquivo.name).stem}.pdf"
    return ContentFile(buffer.read(), name=nome_pdf)


def anexar_documentos_solicitacao(evento, arquivos_pdf) -> None:
    """Guarda os PDFs de solicitacao ja convertidos, preservando o nome original.

    Veio da view junto com o `P-01`: escrita nao e selector, entao desceu para
    servicos em vez de virar consulta.
    """
    from .models import EventoDocumentoSolicitacao

    for arquivo_pdf in arquivos_pdf:
        EventoDocumentoSolicitacao.objects.create(
            evento=evento,
            arquivo=arquivo_pdf,
            nome_original=Path(arquivo_pdf.name).name,
        )


def excluir_documento_solicitacao(anexo) -> None:
    """Apaga o arquivo do disco antes do registro — a ordem importa."""
    anexo.arquivo.delete(save=False)
    anexo.delete()


def garantir_termo_automatico(evento) -> None:
    """Cria um TermoAutorizacao vazio vinculado ao evento se ainda nao existir nenhum."""
    from termos.models import TermoAutorizacao

    from .selectors import existe_termo_do_evento

    if existe_termo_do_evento(evento):
        return

    cidade, estado = resolve_evento_cidade_estado(evento)
    TermoAutorizacao.objects.create(
        evento=evento,
        destino_estado=estado,
        destino_cidade=cidade,
        data_evento_inicio=evento.data_inicio,
        data_evento_fim=evento.data_fim or evento.data_inicio,
    )


@transaction.atomic
def excluir_evento(evento) -> None:
    """Exclui o evento e cascateia a exclusão dos documentos vinculados.

    Todo documento (ofício, roteiro, ordem de serviço, plano de trabalho, termo de
    autorização, justificativa, artefato gerado) que pertence apenas a este evento é
    excluído junto. Exceção: um roteiro deste evento que ainda está em uso por outro
    ofício ou prestação de contas que NÃO pertence a este evento (outro evento, ou
    avulso) não é excluído — apenas desvinculado do evento, preservando o documento
    do outro dono.
    """
    from prestacoes_contas.models import PrestacaoContas

    for roteiro in evento.roteiros.all():
        ainda_em_uso_fora_do_evento = (
            roteiro.oficios.exclude(evento=evento).exists()
            or PrestacaoContas.objects.filter(roteiro_ajustado=roteiro).exclude(oficio__evento=evento).exists()
        )
        if ainda_em_uso_fora_do_evento:
            roteiro.evento = None
            roteiro.save(update_fields=["evento"])

    excluir_com_protecao(evento)


def build_evento_document_context(evento) -> dict:
    """Monta o contexto reaproveitavel de um Evento para pre-preencher documentos.

    Esse dicionario sera usado nas proximas etapas para sugerir valores ao criar
    Oficio, Termo, Plano de Trabalho, Ordem de Servico, Relatorio Tecnico e
    Diario de Bordo a partir de um evento. Ele nao impoe nada: os documentos
    continuam podendo ser criados de forma avulsa e o evento e sempre opcional.

    Os relacionamentos (`unidade_responsavel`, `responsavel`) sao devolvidos como
    instancias (ou None) para que o consumidor escolha usar o pk no pre-preenchimento
    de um ForeignKey ou o texto na exibicao.
    """

    if evento is None:
        return {}

    return {
        "evento_id": evento.pk,
        "titulo": evento.titulo,
        "descricao": evento.descricao,
        "destino_uf": evento.destino_uf,
        "destino_cidade": evento.destino_cidade,
        "data_inicio": evento.data_inicio,
        "data_fim": evento.data_fim,
        "horario_inicio": evento.horario_inicio,
        "horario_fim": evento.horario_fim,
        "unidade_responsavel": evento.unidade_responsavel,
        "responsavel": evento.responsavel,
    }


def evento_querystring(evento) -> str:
    if not evento or not getattr(evento, "pk", None):
        return ""
    return urlencode({"evento": evento.pk})


def evento_document_url(url_name: str, evento, *args, **kwargs) -> str:
    url = reverse(url_name, args=args, kwargs=kwargs)
    query = evento_querystring(evento)
    if query:
        return f"{url}?{query}"
    return url


def resolve_evento_from_request(request):
    raw = (request.GET.get("evento") or request.POST.get("evento") or "").strip()
    if not raw:
        return None
    try:
        evento_id = int(raw)
    except (TypeError, ValueError):
        return None
    from core.tenancy import filter_queryset_by_area

    from .models import Evento

    return (
        filter_queryset_by_area(Evento.objects)
        .filter(pk=evento_id)
        .select_related("unidade_responsavel", "responsavel", "area")
        .first()
    )


def resolve_evento_cidade_estado(evento):
    destinos = resolve_evento_destinos(evento)
    return destinos[0] if destinos else (None, None)


def resolve_evento_destinos(evento):
    """Resolve todos os destinos textuais do evento, preservando a ordem."""
    if evento is None:
        return []

    from cadastros.models import Cidade
    from cadastros.models import Estado

    brutos = [
        {"uf": evento.destino_uf or "", "cidade": evento.destino_cidade or ""},
        *(evento.destinos_extras or []),
    ]
    resolvidos = []
    for bruto in brutos:
        cidade_nome = str(bruto.get("cidade") or "").strip()
        uf = str(bruto.get("uf") or "").strip().upper()
        if not cidade_nome and not uf:
            continue
        estado = Estado.objects.filter(sigla=uf).first() if uf else None
        cidade = None
        if cidade_nome:
            cidades = Cidade.objects.select_related("estado").filter(nome__iexact=cidade_nome)
            if estado:
                cidades = cidades.filter(estado=estado)
            cidade = cidades.order_by("nome").first()
            if cidade and not estado:
                estado = cidade.estado
        if cidade or estado:
            resolvidos.append((cidade, estado))
    return resolvidos


def destinos_seed_para_formulario(seed) -> list[tuple[int, int]]:
    """Pares ``(estado_id, cidade_id)`` de TODOS os destinos do evento.

    `NOVO-20260826-021707-b02175bdd4cd`: `build_evento_document_seed` sempre
    devolveu a lista inteira em ``destinos``, mas Ordem de Serviço, Plano de
    Trabalho e Termo liam apenas ``cidade``/``estado`` — o primeiro destino. Um
    evento com dois destinos abria os documentos das etapas 4 e 5 com um só, e
    o operador tinha de redigitar o que já havia cadastrado na etapa 1.
    """
    pares = []
    for cidade, estado in (seed or {}).get("destinos") or []:
        estado_id = getattr(estado, "pk", None) or getattr(cidade, "estado_id", None)
        cidade_id = getattr(cidade, "pk", None)
        if estado_id and cidade_id:
            pares.append((estado_id, cidade_id))
    return pares


def build_evento_document_seed(evento) -> dict:
    """Consolida valores do evento e dos documentos vinculados para novos cadastros."""

    if evento is None:
        return {}

    destinos = resolve_evento_destinos(evento)
    cidade, estado = destinos[0] if destinos else (None, None)
    seed = {
        "evento": evento,
        "cidade": cidade,
        "estado": estado,
        "destinos": destinos,
        "data_inicio": evento.data_inicio,
        "data_fim": evento.data_fim or evento.data_inicio,
        "motivo": (evento.motivo or evento.descricao or "").strip(),
        "servidores": [],
        "servidores_termo": [],
        "viatura": None,
        "motorista": None,
        "oficio": None,
        "oficios": [],
    }

    oficios = list(
        evento.oficios.select_related(
            "roteiro",
            "viatura",
            "motorista",
            "solicitante",
        )
        .prefetch_related(
            "servidores",
            "servidores_termo_autorizacao",
            "roteiro__destinos__cidade__estado",
        )
        .order_by("-updated_at", "-created_at")[:20]
    )
    seed["oficios"] = oficios
    if oficios:
        oficio = oficios[0]
        seed["oficio"] = oficio
        if not seed["motivo"]:
            seed["motivo"] = (oficio.motivo or "").strip()
        servidores_por_id = {}
        servidores_termo_por_id = {}
        for oficio_selecionado in oficios:
            for servidor in oficio_selecionado.servidores.all():
                servidores_por_id.setdefault(servidor.pk, servidor)
            for servidor in oficio_selecionado.servidores_termo_autorizacao.all():
                servidores_termo_por_id.setdefault(servidor.pk, servidor)
        seed["servidores"] = list(servidores_por_id.values())
        seed["servidores_termo"] = list(servidores_termo_por_id.values())
        seed["viatura"] = oficio.viatura
        seed["motorista"] = oficio.motorista
        roteiro = oficio.roteiro
        if roteiro:
            _apply_roteiro_seed(seed, roteiro)

    roteiro = evento.roteiros.prefetch_related("destinos__cidade__estado").order_by("-updated_at", "-created_at").first()
    if roteiro:
        _apply_roteiro_seed(seed, roteiro)

    plano = (
        evento.planos_trabalho.select_related("destino_cidade__estado", "destino_estado")
        .prefetch_related("efetivos__cargo", "efetivos__unidade")
        .order_by("-updated_at", "-created_at")
        .first()
    )
    if plano:
        if not seed["cidade"] and plano.destino_cidade_id:
            seed["cidade"] = plano.destino_cidade
            seed["estado"] = plano.destino_cidade.estado
        if not seed["estado"] and plano.destino_estado_id:
            seed["estado"] = plano.destino_estado
        seed["data_inicio"] = seed["data_inicio"] or plano.data_evento_inicio
        seed["data_fim"] = seed["data_fim"] or plano.data_evento_fim or plano.data_evento_inicio
        if not seed["motivo"]:
            seed["motivo"] = (plano.contextualizacao or "").strip()

    ordem = (
        evento.ordens_servico.prefetch_related("destinos__estado", "servidores", "oficios")
        .order_by("-updated_at", "-created_at")
        .first()
    )
    if ordem:
        destino = ordem.destinos.select_related("estado").order_by("nome").first()
        if destino and not seed["cidade"]:
            seed["cidade"] = destino
            seed["estado"] = destino.estado
        seed["data_inicio"] = seed["data_inicio"] or ordem.data_evento_inicio
        seed["data_fim"] = seed["data_fim"] or ordem.data_evento_fim or ordem.data_evento_inicio
        if not seed["servidores"]:
            seed["servidores"] = list(ordem.servidores.all())
        if not seed["motivo"]:
            seed["motivo"] = (ordem.motivo or "").strip()

    # `NOVO-08`: `TermoAutorizacao.servidores_efetivos()` passou a consumir o cache
    # do prefetch. Um `prefetch_related("servidores")` cru alimenta o cache sem
    # `cargo`/`unidade`, e cada acesso a eles voltaria a consultar.
    from termos.selectors import prefetch_servidores_efetivos

    termo = (
        evento.termos_autorizacao.select_related("destino_cidade__estado", "destino_estado", "viatura")
        .prefetch_related(prefetch_servidores_efetivos())
        .order_by("-updated_at", "-created_at")
        .first()
    )
    if termo:
        if not seed["cidade"] and termo.destino_cidade_id:
            seed["cidade"] = termo.destino_cidade
            seed["estado"] = termo.destino_cidade.estado
        if not seed["estado"] and termo.destino_estado_id:
            seed["estado"] = termo.destino_estado
        seed["data_inicio"] = seed["data_inicio"] or termo.data_evento_inicio
        seed["data_fim"] = seed["data_fim"] or termo.data_evento_fim or termo.data_evento_inicio
        if not seed["servidores"]:
            seed["servidores"] = list(termo.servidores.all())
        if not seed["servidores_termo"]:
            seed["servidores_termo"] = list(termo.servidores.all())
        seed["viatura"] = seed["viatura"] or termo.viatura

    return seed


def _apply_roteiro_seed(seed: dict, roteiro) -> None:
    destino = roteiro.destinos.select_related("cidade__estado", "estado").order_by("ordem", "pk").first()
    if destino and not seed.get("cidade"):
        seed["cidade"] = destino.cidade
        seed["estado"] = destino.estado or getattr(destino.cidade, "estado", None)
    if roteiro.saida_dt:
        seed["data_inicio"] = seed.get("data_inicio") or roteiro.saida_dt.date()
    retorno = roteiro.retorno_chegada_dt or roteiro.retorno_saida_dt or roteiro.chegada_dt
    if retorno:
        seed["data_fim"] = seed.get("data_fim") or retorno.date()


def build_evento_guided_context(evento, *, etapa_atual: int = 1) -> dict:
    etapa_atual = max(1, min(int(etapa_atual or 1), 5))
    steps_def = [
        (1, "Dados do evento", "eventos:guiado_etapa", _evento_dados_completos(evento)),
        (2, "Roteiros", "eventos:guiado_etapa", evento.roteiros.exists()),
        (3, "Ofícios / Justificativas", "eventos:guiado_etapa", evento.oficios.exists()),
        (
            4,
            "PT / OS",
            "eventos:guiado_etapa",
            evento.planos_trabalho.exists() or evento.ordens_servico.exists(),
        ),
        (5, "Termos", "eventos:guiado_etapa", evento.termos_autorizacao.exists()),
    ]
    page_steps = []
    for number, title, url_name, complete in steps_def:
        is_current = number == etapa_atual
        page_steps.append(
            {
                # Vocabulário do `c-v2.stepper`: `label`, `state` e `url`. O
                # painel do evento é um HUB — as cinco etapas existem ao mesmo
                # tempo —, então cada uma vai como link.
                "url": reverse(url_name, kwargs={"pk": evento.pk, "etapa": number}),
                "label": title,
                "state": "current" if is_current else ("done" if complete else ""),
                "status": "Atual" if is_current else ("Concluída" if complete else "Pendente"),
                # `title` e `aria_current` continuam porque a view lê os dois
                # para montar a descrição do cabeçalho.
                "title": title,
                "aria_current": "step" if is_current else "",
            }
        )

    return {
        "etapa_atual": etapa_atual,
        "evento_page_steps": page_steps,
        "evento_chips": _evento_chips(evento),
        "create_urls": {
            "oficio": evento_document_url("oficios:novo", evento),
            "roteiro": evento_document_url("roteiros:novo", evento),
            "plano": evento_document_url("planos_trabalho:novo", evento),
            "ordem": evento_document_url("ordens_servico:nova", evento),
            "termo": evento_document_url("termos:novo", evento),
        },
    }


def _evento_dados_completos(evento) -> bool:
    return bool(evento.titulo and evento.data_inicio and (evento.destino_cidade or evento.destino_uf))


def _evento_chips(evento) -> list[dict]:
    chips = []
    if evento.data_inicio:
        chips.append({"label": evento.periodo_display, "variant": "entity"})
    if evento.destino_display != "Destino não informado":
        chips.append({"label": evento.destino_display, "variant": "entity"})
    counts = [
        (evento.roteiros.count(), "Roteiro", "Roteiros"),
        (evento.oficios.count(), "Oficio", "Oficios"),
        (evento.planos_trabalho.count(), "Plano de trabalho", "Planos de trabalho"),
        (evento.ordens_servico.count(), "OS", "OS"),
        (evento.termos_autorizacao.count(), "Termo", "Termos"),
    ]
    for count, singular, plural in counts:
        if count:
            chips.append({"label": f"{count} {singular if count == 1 else plural}", "variant": "entity"})
    return chips
