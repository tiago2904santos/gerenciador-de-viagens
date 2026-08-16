from __future__ import annotations

from django.http import HttpResponse

from documentos.services.types import DocumentoFormato

from .services import fundir_termos_docx
from .services import fundir_termos_pdf_bytes
from .services import gerar_termo_cadastro_um
from .services import gerar_termo_lote
from .services import gerar_termos_pdf_consolidado
from .services import gerar_termo_um
from .services import listar_servidores_com_termo
from .services import pdf_termo_cadastro_assinado_ou_gerado
from .services import pdf_termo_oficio_assinado_ou_gerado
from .services import servidores_para_termo_cadastro
from .services import sha256_bytes
from .services import termo_oficio_tem_assinado


def _response(content: bytes, *, content_type: str, filename: str) -> HttpResponse:
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Document-SHA256"] = sha256_bytes(content)
    return response


def gerar_termo_cadastro_response(
    termo,
    *,
    formato: DocumentoFormato,
    modo: str,
    servidor=None,
) -> HttpResponse:
    if modo == "viatura":
        # Gerado direto: a resolucao de "assinado" e por servidor/generico e
        # nao se aplica ao termo da viatura.
        doc = gerar_termo_cadastro_um(termo, None, formato, forcar_viatura=True)
        return _response(
            doc.conteudo,
            content_type=doc.content_type,
            filename=doc.nome_arquivo,
        )

    if formato == DocumentoFormato.PDF:
        if modo == "generico":
            conteudos = [pdf_termo_cadastro_assinado_ou_gerado(termo, None)]
        elif modo == "servidor":
            conteudos = [pdf_termo_cadastro_assinado_ou_gerado(termo, servidor)]
        elif modo == "selecionados":
            conteudos = [
                pdf_termo_cadastro_assinado_ou_gerado(termo, item)
                for item in servidores_para_termo_cadastro(termo)
            ]
        else:
            conteudos = _conteudos_compilados_pdf(termo)
        content = conteudos[0] if len(conteudos) == 1 else fundir_termos_pdf_bytes(conteudos)
        return _response(
            content,
            content_type="application/pdf",
            filename=f"termo_{termo.pk}.pdf",
        )

    if modo == "generico":
        docs = [gerar_termo_cadastro_um(termo, None, formato)]
    elif modo == "servidor":
        docs = [gerar_termo_cadastro_um(termo, servidor, formato)]
    else:
        docs = _documentos_compilados(termo, formato)
    content = docs[0].conteudo if len(docs) == 1 else fundir_termos_docx(docs)
    return _response(
        content,
        content_type=docs[0].content_type,
        filename=f"termo_{termo.pk}.docx",
    )


def _documentos_compilados(termo, formato: DocumentoFormato):
    """Os documentos do termo, na ordem em que o compilado os apresenta.

    GENÉRICO → VIATURA → um por SERVIDOR. É a ordem do próprio termo: primeiro o
    que vale para a viagem toda, depois o veículo que a realiza, e por fim cada
    pessoa que assina. A página da viatura nunca entrou aqui — quem quisesse vê-la
    tinha de pedi-la por fora, e a prévia do formulário mostrava um conjunto
    diferente do que o botão de baixar entregava (2026-08-16).
    """
    docs = [gerar_termo_cadastro_um(termo, None, formato)]
    if termo.viatura_efetiva() is not None:
        # A viatura é gerada direto: a resolução de "assinado" é por
        # servidor/genérico, e não existe termo de viatura assinado.
        docs.append(gerar_termo_cadastro_um(termo, None, formato, forcar_viatura=True))
    docs.extend(
        gerar_termo_cadastro_um(termo, item, formato)
        for item in termo.servidores_efetivos()
    )
    return docs


def _conteudos_compilados_pdf(termo) -> list[bytes]:
    """A mesma ordem de `_documentos_compilados`, mas preferindo o PDF assinado.

    O genérico e cada servidor podem ter uma versão assinada anexada; a viatura
    não, e por isso ela é a única que sai sempre do gerador.
    """
    conteudos = [pdf_termo_cadastro_assinado_ou_gerado(termo, None)]
    if termo.viatura_efetiva() is not None:
        conteudos.append(
            gerar_termo_cadastro_um(
                termo, None, DocumentoFormato.PDF, forcar_viatura=True
            ).conteudo
        )
    conteudos.extend(
        pdf_termo_cadastro_assinado_ou_gerado(termo, item)
        for item in termo.servidores_efetivos()
    )
    return conteudos


def gerar_termo_oficio_response(
    oficio,
    *,
    formato: DocumentoFormato,
    modo: str,
    servidor=None,
) -> HttpResponse:
    if modo == "servidor":
        if formato == DocumentoFormato.PDF:
            content = pdf_termo_oficio_assinado_ou_gerado(oficio, servidor)
            content_type = "application/pdf"
            filename = f"termo_{oficio.numero_formatado.replace('/', '-')}_{servidor.pk}.pdf"
        else:
            doc = gerar_termo_um(oficio, servidor, formato)
            content = doc.conteudo
            content_type = doc.content_type
            filename = doc.nome_arquivo
        return _response(content, content_type=content_type, filename=filename)

    servidores = list(listar_servidores_com_termo(oficio))
    if formato == DocumentoFormato.PDF:
        assinados = [termo_oficio_tem_assinado(oficio, item) for item in servidores]
        if len(servidores) > 1 and not any(assinados):
            content = gerar_termos_pdf_consolidado(oficio)
        else:
            conteudos = [
                pdf_termo_oficio_assinado_ou_gerado(oficio, item)
                for item in servidores
            ]
            content = conteudos[0] if len(conteudos) == 1 else fundir_termos_pdf_bytes(conteudos)
        content_type = "application/pdf"
    else:
        docs = gerar_termo_lote(oficio, formato)
        content = docs[0].conteudo if len(docs) == 1 else fundir_termos_docx(docs)
        content_type = docs[0].content_type
    filename = f"termos_oficio_{oficio.numero_formatado.replace('/', '-')}.{formato.value}"
    return _response(content, content_type=content_type, filename=filename)
