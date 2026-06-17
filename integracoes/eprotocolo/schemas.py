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
    """Caminhos relativos à BASE_URL. Confirmar com a documentação oficial."""

    CRIAR_PROTOCOLO = "/protocolo"
    CONSULTAR_PROTOCOLO = "/protocolo/{numero}"
    CONCLUIR_PROTOCOLO = "/protocolo/{numero}/concluir"
    DOCUMENTOS = "/protocolo/{numero}/documentos"
    DOCUMENTOS_VOLUME = "/protocolo/{numero}/volume/documentos"
    PENDENCIAS = "/protocolo/{numero}/pendencias"
    PENDENCIA_CANCELAR = "/protocolo/{numero}/pendencias/{codigo}/cancelar"
    TRAMITACOES = "/protocolo/{numero}/tramitacoes"
    MOVIMENTACOES = "/protocolo/{numero}/movimentacoes"
    ASSINATURAS_DOCUMENTO = "/protocolo/{numero}/documentos/{codigo}/assinaturas"


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
