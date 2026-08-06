from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import timedelta
from urllib.parse import unquote

from django.core.files.base import ContentFile
from django.http import FileResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from core.tenancy import filter_queryset_by_area
from documentos.models import DocumentoGeracao
from documentos.services.types import DocumentoFormato

logger = logging.getLogger(__name__)

_ACTIVE_WINDOW = timedelta(minutes=15)
_FILENAME_STAR = re.compile(r"filename\*=UTF-8''([^;]+)", re.IGNORECASE)
_FILENAME = re.compile(r'filename="?([^";]+)"?', re.IGNORECASE)


def _filename_from_response(response, fallback: str) -> str:
    disposition = response.get("Content-Disposition", "")
    encoded = _FILENAME_STAR.search(disposition)
    if encoded:
        return unquote(encoded.group(1).strip("\"'"))
    plain = _FILENAME.search(disposition)
    if plain:
        return plain.group(1).strip()
    return fallback


def _job_key(*, tipo: str, parametros: dict, area_id, usuario_id, disposicao: str) -> str:
    payload = json.dumps(
        {
            "tipo": tipo,
            "parametros": parametros,
            "area_id": area_id,
            "usuario_id": usuario_id,
            "disposicao": disposicao,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _objeto_do_job(model, *, pk, area_id):
    # `BE-09`: `_base_manager`, e não `objects` nem `all_objects`.
    #
    # A área vem do **job** (`area_id`) e é conferida à mão nas duas linhas abaixo,
    # então a leitura aqui tem de ser irrestrita. Depender de `objects` seria
    # depender de o worker do Celery não ter request — verdade hoje, mas não
    # contrato, e `CELERY_TASK_ALWAYS_EAGER` faz a task rodar dentro do request nos
    # testes (`NOVO-20`).
    #
    # E `all_objects` não serve porque esta função é genérica sobre cinco modelos
    # de apps diferentes — `Oficio`, `PlanoTrabalho`, `OrdemServico`,
    # `TermoAutorizacao` e `Servidor`. Os quatro primeiros já têm `all_objects` e
    # `Servidor` ganhou na fatia 5a, mas `PlanoTrabalho` só entra na 6 — e mesmo
    # depois que os cinco tiverem, amarrar código genérico ao nome de um manager
    # de aplicação é o acoplamento errado. `_base_manager` existe em todo modelo,
    # nunca recorta, e é o que o próprio Django usa para ler linha por pk
    # (travessia de FK, `refresh_from_db`).
    obj = model._base_manager.get(pk=pk)
    object_area_id = getattr(obj, "area_id", None)
    if object_area_id != area_id:
        raise model.DoesNotExist
    return obj


def gerar_resposta_do_job(job: DocumentoGeracao):
    """Resolve apenas chaves fechadas; nunca importa/callable vindo do cliente."""

    parametros = job.parametros
    object_id = parametros["object_id"]
    formato_raw = parametros["formato"]

    if job.tipo in {"prestacao_consolidado", "prestacao_rt", "prestacao_diario"}:
        from prestacoes_contas.async_documents import gerar_consolidado_response
        from prestacoes_contas.async_documents import gerar_diario_response
        from prestacoes_contas.async_documents import gerar_rt_response
        from prestacoes_contas.models import DiarioBordo
        from prestacoes_contas.models import PrestacaoServidor

        if job.tipo == "prestacao_diario":
            diario = DiarioBordo.objects.select_related("prestacao").get(pk=object_id)
            if diario.prestacao.area_id != job.area_id:
                raise DiarioBordo.DoesNotExist
            return gerar_diario_response(diario, formato=formato_raw)

        servidor_prestacao = (
            PrestacaoServidor.objects.select_related("prestacao", "servidor")
            .get(pk=object_id)
        )
        if servidor_prestacao.prestacao.area_id != job.area_id:
            raise PrestacaoServidor.DoesNotExist
        if job.tipo == "prestacao_consolidado":
            return gerar_consolidado_response(servidor_prestacao)
        return gerar_rt_response(servidor_prestacao, formato=formato_raw)

    formato = DocumentoFormato(formato_raw)

    if job.tipo in {"oficio", "justificativa", "ordem_servico_oficio"}:
        from oficios.models import Oficio

        oficio = _objeto_do_job(Oficio, pk=object_id, area_id=job.area_id)
        if job.tipo == "oficio":
            from oficios.services import gerar_resposta_documento_oficio

            return gerar_resposta_documento_oficio(oficio, formato)
        if job.tipo == "justificativa":
            from oficios.services import gerar_resposta_justificativa_documento

            return gerar_resposta_justificativa_documento(oficio, formato)
        from ordens_servico.services import gerar_resposta_ordem_servico_documento

        return gerar_resposta_ordem_servico_documento(oficio, formato)

    if job.tipo == "plano_trabalho":
        from planos_trabalho.models import PlanoTrabalho
        from planos_trabalho.services import gerar_resposta_plano_documento
        from planos_trabalho.services import marcar_plano_gerado

        plano = _objeto_do_job(PlanoTrabalho, pk=object_id, area_id=job.area_id)
        response = gerar_resposta_plano_documento(plano, formato)
        marcar_plano_gerado(plano)
        return response

    if job.tipo == "ordem_servico":
        from ordens_servico.models import OrdemServico
        from ordens_servico.services import gerar_os_docx_response
        from ordens_servico.services import gerar_os_pdf_response

        ordem = _objeto_do_job(OrdemServico, pk=object_id, area_id=job.area_id)
        if formato == DocumentoFormato.PDF:
            return gerar_os_pdf_response(ordem)
        return gerar_os_docx_response(ordem)

    if job.tipo == "termo_cadastro":
        from cadastros.models import Servidor
        from termos.async_documents import gerar_termo_cadastro_response
        from termos.models import TermoAutorizacao

        termo = _objeto_do_job(TermoAutorizacao, pk=object_id, area_id=job.area_id)
        servidor_id = parametros.get("servidor_id")
        servidor = (
            _objeto_do_job(Servidor, pk=servidor_id, area_id=job.area_id)
            if servidor_id
            else None
        )
        return gerar_termo_cadastro_response(
            termo,
            formato=formato,
            modo=parametros.get("modo", "todos"),
            servidor=servidor,
        )

    if job.tipo == "termo_oficio":
        from cadastros.models import Servidor
        from oficios.models import Oficio
        from termos.async_documents import gerar_termo_oficio_response

        oficio = _objeto_do_job(Oficio, pk=object_id, area_id=job.area_id)
        servidor_id = parametros.get("servidor_id")
        servidor = (
            _objeto_do_job(Servidor, pk=servidor_id, area_id=job.area_id)
            if servidor_id
            else None
        )
        return gerar_termo_oficio_response(
            oficio,
            formato=formato,
            modo=parametros.get("modo", "todos"),
            servidor=servidor,
        )

    raise ValueError(f"Tipo de geração não suportado: {job.tipo}")


def concluir_job(job: DocumentoGeracao, response) -> None:
    if getattr(response, "streaming", False):
        content = b"".join(response.streaming_content)
    else:
        content = bytes(response.content)
    if getattr(response, "status_code", 200) >= 400:
        raise RuntimeError(f"Gerador retornou HTTP {response.status_code}")
    fallback = f"documento-{job.pk}.{job.parametros.get('formato', 'bin')}"
    filename = _filename_from_response(response, fallback)
    job.arquivo.save(filename, ContentFile(content), save=False)
    job.nome_arquivo = filename
    job.content_type = response.get("Content-Type", "application/octet-stream").split(";", 1)[0]
    job.hash_sha256 = response.get("X-Document-SHA256", "") or hashlib.sha256(content).hexdigest()
    job.status = DocumentoGeracao.STATUS_CONCLUIDO
    job.erro = ""
    job.concluido_em = timezone.now()
    job.save(
        update_fields=[
            "arquivo",
            "nome_arquivo",
            "content_type",
            "hash_sha256",
            "status",
            "erro",
            "concluido_em",
        ],
    )


def falhar_job(job: DocumentoGeracao, exc: BaseException) -> None:
    logger.exception("Falha na geração documental assíncrona %s", job.pk)
    job.status = DocumentoGeracao.STATUS_ERRO
    job.erro = (
        str(exc)[:500]
        if exc.__class__.__module__.startswith(("documentos.", "django."))
        else "Não foi possível gerar o documento."
    )
    job.concluido_em = timezone.now()
    job.save(update_fields=["status", "erro", "concluido_em"])


def _job_payload(job: DocumentoGeracao) -> dict:
    payload = {
        "ok": job.status != DocumentoGeracao.STATUS_ERRO,
        "status": job.status,
        "status_url": reverse("documentos:geracao_status", args=[job.pk]),
        "retry_after_ms": 1000,
    }
    if job.status == DocumentoGeracao.STATUS_CONCLUIDO:
        payload["result_url"] = reverse("documentos:geracao_resultado", args=[job.pk])
        payload["filename"] = job.nome_arquivo
    elif job.status == DocumentoGeracao.STATUS_ERRO:
        payload["error"] = job.erro or "Não foi possível gerar o documento."
    return payload


def _job_do_request(request, pk) -> DocumentoGeracao:
    return get_object_or_404(
        filter_queryset_by_area(DocumentoGeracao.objects.select_related("usuario")),
        pk=pk,
    )


def servir_resultado(request, job: DocumentoGeracao):
    if job.status != DocumentoGeracao.STATUS_CONCLUIDO or not job.arquivo:
        return JsonResponse(_job_payload(job), status=409)
    response = FileResponse(
        job.arquivo.open("rb"),
        as_attachment=job.disposicao != "inline",
        filename=job.nome_arquivo,
        content_type=job.content_type or "application/octet-stream",
    )
    response["Cache-Control"] = "no-store, must-revalidate"
    response["Pragma"] = "no-cache"
    response["X-Document-SHA256"] = job.hash_sha256
    response["X-Content-Type-Options"] = "nosniff"
    if job.disposicao == "inline":
        response["X-Frame-Options"] = "SAMEORIGIN"
    return response


def enfileirar_documento(
    request,
    *,
    tipo: str,
    parametros: dict,
    disposicao: str = "attachment",
):
    area = getattr(request, "area", None)
    user = getattr(request, "user", None)
    usuario = user if getattr(user, "is_authenticated", False) else None
    dedupe_key = _job_key(
        tipo=tipo,
        parametros=parametros,
        area_id=getattr(area, "pk", None),
        usuario_id=getattr(usuario, "pk", None),
        disposicao=disposicao,
    )
    cutoff = timezone.now() - _ACTIVE_WINDOW
    job = (
        DocumentoGeracao.objects.filter(
            dedupe_key=dedupe_key,
            status__in=(
                DocumentoGeracao.STATUS_NA_FILA,
                DocumentoGeracao.STATUS_PROCESSANDO,
            ),
            criado_em__gte=cutoff,
        )
        .order_by("-criado_em")
        .first()
    )
    if job is None:
        job = DocumentoGeracao.objects.create(
            area=area,
            usuario=usuario,
            tipo=tipo,
            parametros=parametros,
            dedupe_key=dedupe_key,
            disposicao=disposicao,
        )
        from documentos.tasks import gerar_documento_assincrono

        try:
            gerar_documento_assincrono.delay(str(job.pk))
        except Exception as exc:
            falhar_job(job, exc)

    job.refresh_from_db()
    if job.status == DocumentoGeracao.STATUS_CONCLUIDO:
        return servir_resultado(request, job)

    payload = _job_payload(job)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(
            payload,
            status=202 if job.status != DocumentoGeracao.STATUS_ERRO else 503,
        )
    template_name = (
        "documentos/geracao_aguarde_embedded.html"
        if request.headers.get("Sec-Fetch-Dest") == "iframe"
        else "documentos/geracao_aguarde.html"
    )
    return render(
        request,
        template_name,
        {
            "page_title": "Preparando documento",
            "geracao": payload,
        },
        status=202 if job.status != DocumentoGeracao.STATUS_ERRO else 503,
    )


def geracao_status(request, pk):
    job = _job_do_request(request, pk)
    return JsonResponse(_job_payload(job))


def geracao_resultado(request, pk):
    job = _job_do_request(request, pk)
    return servir_resultado(request, job)
