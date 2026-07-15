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
