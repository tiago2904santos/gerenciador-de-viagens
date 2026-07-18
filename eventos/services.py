# Servicos de agrupamento OPCIONAL de documentos ficam neste modulo.
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from django.core.files.base import ContentFile
from django.db import transaction
from django.urls import reverse


def converter_para_pdf_se_necessario(arquivo):
    """Converte um upload de imagem (PNG/JPG/JPEG) para PDF; um PDF passa direto.

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

    evento.delete()


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
    from .models import Evento

    return Evento.objects.filter(pk=evento_id).select_related("unidade_responsavel", "responsavel").first()


def resolve_evento_cidade_estado(evento):
    if evento is None:
        return None, None
    cidade_nome = (evento.destino_cidade or "").strip()
    uf = (evento.destino_uf or "").strip().upper()
    if not cidade_nome and not uf:
        return None, None

    from cadastros.models import Cidade
    from cadastros.models import Estado

    estado = Estado.objects.filter(sigla=uf).first() if uf else None
    cidade = None
    if cidade_nome:
        cidades = Cidade.objects.select_related("estado").filter(nome__iexact=cidade_nome)
        if estado:
            cidades = cidades.filter(estado=estado)
        cidade = cidades.order_by("nome").first()
        if cidade and not estado:
            estado = cidade.estado
    return cidade, estado


def build_evento_document_seed(evento) -> dict:
    """Consolida valores do evento e dos documentos vinculados para novos cadastros."""

    if evento is None:
        return {}

    cidade, estado = resolve_evento_cidade_estado(evento)
    seed = {
        "evento": evento,
        "cidade": cidade,
        "estado": estado,
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
        seed["servidores"] = list(oficio.servidores.all())
        seed["servidores_termo"] = list(oficio.servidores_termo_autorizacao.all())
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

    termo = (
        evento.termos_autorizacao.select_related("destino_cidade__estado", "destino_estado", "viatura")
        .prefetch_related("servidores")
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
                "url": reverse(url_name, kwargs={"pk": evento.pk, "etapa": number}),
                "state_class": "is-current" if is_current else ("is-complete" if complete else "is-pending"),
                "step_label": f"Etapa {number}",
                "title": title,
                "status": "Atual" if is_current else ("Concluída" if complete else "Pendente"),
                "marker": str(number),
                "marker_aria_hidden": False,
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
