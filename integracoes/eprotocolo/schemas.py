"""Constantes e estruturas de domínio da integração eProtocolo.

Mantém em um único lugar os caminhos (paths) dos endpoints e pequenas
estruturas de dados. Os paths são propositalmente configuráveis/centralizados
porque a documentação oficial pode ajustar versões — alterar aqui propaga para
todos os services.

NOTA: os paths abaixo seguem o padrão público do barramento do eProtocolo/PR,
mas devem ser confirmados contra a documentação oficial antes do go-live em
produção. Em modo mock eles não são usados para chamadas reais.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field


class Endpoints:
    """Caminhos relativos à BASE_URL do barramento ``spi-servicos`` (v3).

    A BASE_URL (incluindo host e eventual segmento ``spi-servicos``) vem do
    ``.env``; aqui ficam apenas os paths versionados. Confirmar com a
    documentação oficial antes do go-live; em modo mock não são usados.
    """

    # Protocolos
    CRIAR_PROTOCOLO = "/v3/protocolos"
    CONSULTAR_PROTOCOLO = "/v3/protocolos/{numero}"
    CONCLUIR_PROTOCOLO = "/v3/protocolos/{numero}/concluir"
    DOCUMENTOS = "/v3/protocolos/{numero}/documentos"
    DOCUMENTOS_VOLUME = "/v3/volumes/{numero}/documentos"
    PENDENCIAS = "/v3/protocolos/{numero}/pendencias"
    PENDENCIA_CANCELAR = "/v3/protocolos/{numero}/pendencias/{codigo}/cancelar"
    TRAMITACOES = "/v3/protocolos/{numero}/tramitacoes"
    MOVIMENTACOES = "/v3/protocolos/{numero}/movimentacoes"
    ASSINATURAS_DOCUMENTO = "/v3/protocolos/{numero}/documentos/{codigo}/assinaturas"

    # Tabelas auxiliares (consulta — usadas por ping/diagnóstico)
    ORGAOS = "/v3/orgaos"
    LOCAIS = "/v3/locais"
    ASSUNTOS = "/v3/assuntos"
    ESPECIES = "/v3/especies"


# Escopos OAuth2 esperados no ``spi-servicos`` (referência para solicitação à
# Celepar/SEAP). NÃO são hardcoded em chamadas — servem só de documentação e
# para o comando de diagnóstico listar o que precisa ser liberado.
ESCOPOS_ESPERADOS = (
    "spiserv.protocolos.consultar",
    "spiserv.protocolos.incluir",
    "spiserv.protocolos.concluir",
    "spiserv.protocolos.alterar",
    "spiserv.protocolos.documentos.consultar",
    "spiserv.protocolos.documentos.incluir",
    "spiserv.volumes.documentos.consultar",
    "spiserv.protocolos.movimentacoes.consultar",
    "spiserv.protocolos.tramitacoes.consultar",
    "spiserv.protocolos.tramitacoes.incluir",
    "spiserv.protocolos.pendencias.consultar",
    "spiserv.protocolos.pendencias.incluir",
    "spiserv.protocolos.pendencias.cancelar",
    "spiserv.protocolos.documentos.assinaturas.consultar",
    "spiserv.protocolos.documentos.assinaturas.incluir",
    "spiserv.orgaos.consultar",
    "spiserv.locais.consultar",
    "spiserv.assuntos.consultar",
    "spiserv.especies.consultar",
)


@dataclass
class ResultadoOperacao:
    """Resultado normalizado de uma operação de integração.

    Permite que as camadas superiores saibam se a chamada foi real ou mock sem
    inspecionar o payload bruto.
    """

    sucesso: bool
    dados: dict = field(default_factory=dict)
    mock: bool = False
    mensagem: str = ""
