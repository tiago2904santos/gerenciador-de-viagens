from __future__ import annotations

from documentos.models import DocumentoArtefato
from documentos.services.types import DocumentoTipo


def get_latest_artefato_pdf_for_oficio(oficio_id: int, tipo: str) -> DocumentoArtefato | None:
    """Último artefato PDF persistido para o ofício e tipo documental (ex.: `oficio`, `justificativa`)."""
    return (
        DocumentoArtefato.objects.filter(oficio_id=oficio_id, tipo=tipo, formato="pdf")
        .order_by("-criado_em")
        .first()
    )


def get_latest_artefato_pdf_termo(oficio_id: int, servidor_id: int) -> DocumentoArtefato | None:
    """Último PDF persistido do termo de autorização para um viajante específico do ofício."""
    return (
        DocumentoArtefato.objects.filter(
            oficio_id=oficio_id,
            servidor_id=servidor_id,
            tipo=DocumentoTipo.TERMO_AUTORIZACAO.value,
            formato="pdf",
        )
        .order_by("-criado_em")
        .first()
    )


def get_latest_artefato_pdf_termo_cadastro(termo_id: int, servidor_id: int | None) -> DocumentoArtefato | None:
    """Último PDF persistido de um termo de autorização avulso (app `termos`), genérico ou por servidor."""
    return (
        DocumentoArtefato.objects.filter(
            termo_id=termo_id,
            servidor_id=servidor_id,
            tipo=DocumentoTipo.TERMO_AUTORIZACAO.value,
            formato="pdf",
        )
        .order_by("-criado_em")
        .first()
    )


def mapa_artefatos_pdf_termo_cadastro(termo_id: int) -> dict[int | None, DocumentoArtefato]:
    """Todos os últimos PDFs de um termo — genérico e por servidor — em UMA query.

    A versão unitária acima custa uma consulta por linha. A tela de edição de
    Termos monta um bloco por servidor, então o custo crescia com o tamanho da
    equipe (a mesma doença do NOVO-07 em Ordens de Serviço).

    A chave é `servidor_id`, com `None` para o termo genérico. Como a ordenação
    é por `-criado_em`, o primeiro de cada chave é o mais recente — por isso o
    `setdefault`, que ignora os mais antigos sem uma segunda passada.
    """
    mapa: dict[int | None, DocumentoArtefato] = {}
    artefatos = DocumentoArtefato.objects.filter(
        termo_id=termo_id,
        tipo=DocumentoTipo.TERMO_AUTORIZACAO.value,
        formato="pdf",
    ).order_by("-criado_em")
    for artefato in artefatos:
        mapa.setdefault(artefato.servidor_id, artefato)
    return mapa


def mapa_artefatos_pdf_termo_cadastro_em_lote(
    termo_ids,
) -> dict[int, dict[int | None, DocumentoArtefato]]:
    """O mapa acima para vários termos de uma vez — UMA query para a página inteira.

    A lista de Termos chamava a versão unitária uma vez por linha, então o custo
    crescia com o tamanho da página e não com o do banco (`NOVO-08`). A chave
    externa é `termo_id`; a interna é a mesma da versão unitária.
    """
    mapa: dict[int, dict[int | None, DocumentoArtefato]] = {}
    if not termo_ids:
        return mapa
    artefatos = DocumentoArtefato.objects.filter(
        termo_id__in=list(termo_ids),
        tipo=DocumentoTipo.TERMO_AUTORIZACAO.value,
        formato="pdf",
    ).order_by("-criado_em")
    for artefato in artefatos:
        mapa.setdefault(artefato.termo_id, {}).setdefault(artefato.servidor_id, artefato)
    return mapa
