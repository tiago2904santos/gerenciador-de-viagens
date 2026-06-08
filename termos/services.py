from __future__ import annotations

import io
import zipfile

from cadastros.models import Servidor

from documentos.services.facade import DocumentoFacade
from documentos.services.facade import DocumentoGerado
from documentos.services.templates import DocumentTemplateDefinition
from documentos.services.templates import DocumentTemplateRegistry
from documentos.services.templates import default_template_registry
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo
from documentos.services.formatters import format_institucional_rodape_linha

from oficios.documents import VarianteTermo
from oficios.documents import build_termo_payload
from oficios.models import Oficio


_TEMPLATE_DOCX_BY_VARIANTE = {
    VarianteTermo.SEMIPREENCHIDO: "termo_autorizacao.docx",
    VarianteTermo.COMPLETO_COM_VIATURA: "termo_autorizacao_automatico.docx",
    VarianteTermo.COMPLETO_SEM_VIATURA: "termo_autorizacao_automatico_sem_viatura.docx",
}


def listar_servidores_com_termo(oficio: Oficio):
    return oficio.servidores_termo_autorizacao.select_related("cargo", "unidade").order_by("nome")


def preview_termo_context(
    oficio: Oficio,
    servidor: Servidor | None = None,
    *,
    modo_semipreenchido: bool = False,
    variante: str | None = None,
) -> dict:
    servidores_termo = listar_servidores_com_termo(oficio)
    srv = servidor or servidores_termo.first()
    if srv is None:
        return {"erro": "Nenhum servidor selecionado para Termo de Autorizacao neste oficio."}
    if not servidores_termo.filter(pk=srv.pk).exists():
        return {"erro": "Servidor nao selecionado para Termo de Autorizacao neste oficio."}
    payload = build_termo_payload(
        oficio,
        srv,
        modo_semipreenchido=modo_semipreenchido,
        variante=variante,
    )
    return {
        "payload": payload,
        "servidor": srv,
        "servidores": list(servidores_termo),
        "variante_efetiva": payload["termo"]["variante"],
    }


def _facade_termo_com_template(template_docx: str) -> DocumentoFacade:
    registry = DocumentTemplateRegistry()
    for definition in default_template_registry.all():
        if definition.tipo == DocumentoTipo.TERMO_AUTORIZACAO and definition.formato == DocumentoFormato.DOCX:
            definition = DocumentTemplateDefinition(
                tipo=definition.tipo,
                formato=definition.formato,
                template_path=template_docx,
                required_placeholders=definition.required_placeholders,
                stylesheet_paths=definition.stylesheet_paths,
            )
        registry.register(definition)
    return DocumentoFacade(template_registry=registry)


def _legacy_docx_context(payload: dict) -> dict:
    institucional = payload.get("institucional") or {}
    termo = payload.get("termo") or {}
    participante = termo.get("participante") or {}
    viagem = termo.get("viagem") or {}
    transporte = termo.get("transporte") or {}

    endereco_partes = [
        institucional.get("logradouro"),
        institucional.get("numero"),
        institucional.get("bairro"),
        institucional.get("cidade_endereco"),
        institucional.get("uf"),
        institucional.get("cep_formatado"),
    ]
    endereco = ", ".join(str(parte).strip() for parte in endereco_partes if str(parte or "").strip())

    return {
        "unidade": institucional.get("unidade") or termo.get("oficio", {}).get("origem") or "",
        "divisao": institucional.get("divisao") or "",
        "endereco": endereco,
        "telefone": institucional.get("telefone_formatado") or institucional.get("telefone") or "",
        "email": institucional.get("email") or "",
        "unidade_rodape": format_institucional_rodape_linha(institucional),
        "data_do_evento": viagem.get("periodo") or viagem.get("saida") or "",
        "destino": viagem.get("destinos_texto") or viagem.get("destino_principal") or "",
        "nome_servidor": participante.get("nome") or "",
        "rg_servidor": participante.get("rg_formatado") or "",
        "cpf_servidor": participante.get("cpf_formatado") or participante.get("cpf") or "",
        "lotacao": participante.get("unidade") or "",
        "viatura": transporte.get("modelo") or "",
        "placa": transporte.get("placa") or "",
        "combustivel": transporte.get("combustivel") or "",
    }


def gerar_termo_um(
    oficio: Oficio,
    servidor: Servidor,
    formato: DocumentoFormato,
    *,
    modo_semipreenchido: bool = False,
    variante: str | None = None,
) -> DocumentoGerado:
    payload = build_termo_payload(
        oficio,
        servidor,
        modo_semipreenchido=modo_semipreenchido,
        variante=variante,
    )
    ref = f"{oficio.numero_formatado.replace('/', '-')}-termo-{servidor.pk}"
    variante_efetiva = payload["termo"]["variante"]
    template_docx = _TEMPLATE_DOCX_BY_VARIANTE.get(variante_efetiva, "termo_autorizacao.docx")
    facade = _facade_termo_com_template(template_docx)
    return facade.gerar(
        tipo=DocumentoTipo.TERMO_AUTORIZACAO,
        formato=formato,
        payload=payload,
        reference=ref,
        docxtpl_context=_legacy_docx_context(payload),
    )


def gerar_termo_lote(oficio: Oficio, formato: DocumentoFormato) -> list[DocumentoGerado]:
    out: list[DocumentoGerado] = []
    for servidor in listar_servidores_com_termo(oficio):
        out.append(gerar_termo_um(oficio, servidor, formato))
    return out


def empacotar_termos_zip(documentos: list[DocumentoGerado]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc in documentos:
            zf.writestr(doc.nome_arquivo, doc.conteudo)
    return buf.getvalue()


def fundir_termos_pdf(documentos: list[DocumentoGerado]) -> bytes:
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for doc in documentos:
        reader = PdfReader(io.BytesIO(doc.conteudo))
        for page in reader.pages:
            writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()
