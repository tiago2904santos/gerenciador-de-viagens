from dataclasses import dataclass
from enum import Enum


class DocumentoFormato(str, Enum):
    DOCX = "docx"
    PDF = "pdf"


class DocumentoTipo(str, Enum):
    OFICIO = "oficio"
    TERMO_AUTORIZACAO = "termo_autorizacao"
    PLANO_TRABALHO = "plano_trabalho"
    ORDEM_SERVICO = "ordem_servico"
    JUSTIFICATIVA = "justificativa"


@dataclass(frozen=True)
class DocumentoTipoDefinicao:
    tipo: DocumentoTipo
    label: str
    descricao: str
    formatos_permitidos: tuple[DocumentoFormato, ...]

    def supports_format(self, formato: DocumentoFormato) -> bool:
        return formato in self.formatos_permitidos
