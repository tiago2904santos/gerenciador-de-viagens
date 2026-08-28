from __future__ import annotations

from io import BytesIO

from django.urls import reverse

from documentos.services.exceptions import DocumentValidationError
from documentos.services.types import DocumentoFormato

from .diario_services import gerar_diario_bordo_pdf
from .models import DiarioBordo
from .models import PrestacaoDocumentoAnexo
from .models import RelatorioTecnico
from .services import _merge_pdf_parts
from .services import _pdf_bytes_from_file_field
from .services import gerar_oficio_prestacao_documento
from .services import gerar_relatorio_tecnico_docx
from .services import gerar_relatorio_tecnico_pdf


# `NOVO-20260828-185303-995fcc0f4b5c`: a ordem dos cinco documentos da prestação,
# num lugar só. Ela existe na tela desde sempre — a etapa Documentos desenha
# ofício e despacho no bloco do ofício, RT, DB e comprovante no bloco do servidor
# — mas cada consumidor remontava a lista à mão e três discordavam dela. Quem
# ordena documento importa este nome; não escreva a sequência de novo.
ORDEM_DOCUMENTOS = ("oficio", "despacho", "rt", "diario", "comprovante")

TIPOS = {
    "oficio": PrestacaoDocumentoAnexo.TIPO_OFICIO_ASSINADO,
    "despacho": PrestacaoDocumentoAnexo.TIPO_DESPACHO,
    "diario": PrestacaoDocumentoAnexo.TIPO_DB_ASSINADO,
    "rt": PrestacaoDocumentoAnexo.TIPO_RT_ASSINADO,
    "comprovante": PrestacaoDocumentoAnexo.TIPO_COMPROVANTE,
}


def em_ordem(ids):
    """Reordena chaves de documento pela ordem canônica, descartando o resto."""
    escolhidas = set(ids)
    return [item_id for item_id in ORDEM_DOCUMENTOS if item_id in escolhidas]


def anexos_por_tipo(ps):
    compartilhados = {
        item.tipo: item
        for item in ps.prestacao.documentos_anexos.filter(servidor_prestacao__isnull=True)
    }
    individuais = {item.tipo: item for item in ps.documentos_anexos.all()}
    return {**compartilhados, **individuais}


def _signed_url(ps, item_id, anexo):
    if not anexo:
        return ""
    return reverse("prestacoes_contas:prestacao_download_assinado", args=[ps.pk, item_id, "pdf"])


def payload_downloads(ps):
    prestacao = ps.prestacao
    oficio = prestacao.oficio
    anexos = anexos_por_tipo(ps)
    try:
        diario = prestacao.diario_bordo
    except DiarioBordo.DoesNotExist:
        diario = None
    oficio_urls = {
        formato: reverse("oficios:baixar_documento", args=[oficio.pk, formato])
        for formato in ("pdf", "docx")
    }
    rt_urls = {
        formato: reverse("prestacoes_contas:rt_download_servidor_formato", args=[ps.pk, formato])
        for formato in ("pdf", "docx")
    }
    diario_urls = (
        {"pdf": reverse("prestacoes_contas:diario_download_formato", args=[diario.pk, "pdf"])}
        if diario else {}
    )
    rotulos = {
        "oficio": ("Ofício", oficio.numero_formatado, oficio_urls),
        "despacho": ("Despacho", "Documento do ofício", {}),
        "rt": ("Relatório técnico", ps.servidor.nome, rt_urls),
        "diario": ("Diário de bordo", oficio.numero_formatado, diario_urls),
        "comprovante": ("Comprovante", ps.servidor.nome, {}),
    }
    definicoes = [(item_id, *rotulos[item_id]) for item_id in ORDEM_DOCUMENTOS]
    itens = []
    for item_id, titulo, subtitulo, originais in definicoes:
        assinado = anexos.get(TIPOS[item_id])
        versoes = {
            "original": originais,
            "assinado": {"pdf": _signed_url(ps, item_id, assinado)} if assinado else {},
        }
        if any(versoes.values()):
            itens.append({"id": item_id, "titulo": titulo, "subtitulo": subtitulo, "versoes": versoes})
    return {
        "itens": itens,
        "compilado": reverse("prestacoes_contas:prestacao_download_compilado", args=[ps.pk]),
        "origens": [
            {"value": "original", "label": "Original do sistema"},
            {"value": "assinado", "label": "Documento assinado"},
        ],
        "sempre_escolher": True,
        "compilado_aceita_itens": True,
    }


def anexo_do_item(ps, item_id):
    tipo = TIPOS.get(item_id)
    return anexos_por_tipo(ps).get(tipo) if tipo else None


def pdf_assinado(ps, item_id):
    anexo = anexo_do_item(ps, item_id)
    if not anexo:
        raise DocumentValidationError("Documento assinado não encontrado.")
    return _pdf_bytes_from_file_field(anexo.arquivo, anexo.get_tipo_display())


def _fundir_docx(conteudos):
    from docx import Document
    from docxcompose.composer import Composer

    base = Document(BytesIO(conteudos[0]))
    composer = Composer(base)
    for conteudo in conteudos[1:]:
        base.add_page_break()
        composer.append(Document(BytesIO(conteudo)))
    output = BytesIO()
    composer.save(output)
    return output.getvalue()


def _original_oficio(ps, formato):
    return (
        "ofício",
        gerar_oficio_prestacao_documento(ps.prestacao, DocumentoFormato(formato)),
    )


def _original_rt(ps, formato):
    relatorio, _ = RelatorioTecnico.objects.get_or_create(prestacao=ps.prestacao)
    gerador = gerar_relatorio_tecnico_pdf if formato == "pdf" else gerar_relatorio_tecnico_docx
    return ("relatório técnico", gerador(relatorio, ps))


def _original_diario(ps, formato):
    if formato != "pdf":
        raise DocumentValidationError("O diário de bordo não possui versão DOCX.")
    try:
        diario = ps.prestacao.diario_bordo
    except DiarioBordo.DoesNotExist as exc:
        raise DocumentValidationError("Diário de bordo não encontrado.") from exc
    return ("diário de bordo", gerar_diario_bordo_pdf(diario))


# Despacho e comprovante não têm original do sistema: só existem assinados.
GERADORES_ORIGINAIS = {
    "oficio": _original_oficio,
    "rt": _original_rt,
    "diario": _original_diario,
}


def _originais(ps, formato, escolhidos):
    return [
        GERADORES_ORIGINAIS[item_id](ps, formato)
        for item_id in em_ordem(escolhidos)
        if item_id in GERADORES_ORIGINAIS
    ]


def compilar_download(ps, *, origem, formato, escolhidos):
    if origem == "assinado":
        if formato != "pdf":
            raise DocumentValidationError("Documentos assinados estão disponíveis em PDF.")
        # `em_ordem` e não `escolhidos`: a query string chega na ordem em que o JS
        # montou as caixas do modal, e o PDF juntado saía nessa ordem.
        partes = [(item_id, pdf_assinado(ps, item_id)) for item_id in em_ordem(escolhidos)]
    else:
        partes = _originais(ps, formato, escolhidos)
    if not partes:
        raise DocumentValidationError("Nenhum documento está disponível nesta combinação.")
    return _merge_pdf_parts(partes) if formato == "pdf" else _fundir_docx([parte[1] for parte in partes])
