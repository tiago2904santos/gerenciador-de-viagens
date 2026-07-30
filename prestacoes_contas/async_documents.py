from __future__ import annotations

import hashlib

from django.http import HttpResponse

from .assinatura_services import pdf_db_assinado_ou_gerado
from .assinatura_services import pdf_rt_assinado_ou_gerado
from .diario_services import gerar_diario_bordo_xlsx
from .diario_services import nome_arquivo_diario
from .models import RelatorioTecnico
from .services import garantir_campos_padrao_relatorio_tecnico
from .services import gerar_prestacao_consolidado_pdf
from .services import gerar_relatorio_tecnico_docx
from .services import nome_arquivo_prestacao_consolidado
from .services import nome_arquivo_rt


def _response(content: bytes, *, content_type: str, filename: str) -> HttpResponse:
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Document-SHA256"] = hashlib.sha256(content).hexdigest()
    return response


def gerar_consolidado_response(servidor_prestacao) -> HttpResponse:
    content = gerar_prestacao_consolidado_pdf(servidor_prestacao)
    return _response(
        content,
        content_type="application/pdf",
        filename=nome_arquivo_prestacao_consolidado(servidor_prestacao),
    )


def gerar_rt_response(servidor_prestacao, *, formato: str) -> HttpResponse:
    relatorio, _ = RelatorioTecnico.objects.get_or_create(
        prestacao=servidor_prestacao.prestacao,
    )
    garantir_campos_padrao_relatorio_tecnico(relatorio)
    if formato == "pdf":
        content = pdf_rt_assinado_ou_gerado(servidor_prestacao)
        content_type = "application/pdf"
    else:
        content = gerar_relatorio_tecnico_docx(relatorio, servidor_prestacao)
        formato = "docx"
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return _response(
        content,
        content_type=content_type,
        filename=nome_arquivo_rt(
            relatorio,
            servidor_prestacao.servidor,
            formato=formato,
        ),
    )


def gerar_diario_response(diario, *, formato: str) -> HttpResponse:
    if formato == "pdf":
        content = pdf_db_assinado_ou_gerado(diario.prestacao)
        content_type = "application/pdf"
    else:
        content = gerar_diario_bordo_xlsx(diario)
        formato = "xlsx"
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return _response(
        content,
        content_type=content_type,
        filename=nome_arquivo_diario(diario, formato=formato),
    )
