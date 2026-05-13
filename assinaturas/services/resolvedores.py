from __future__ import annotations

from dataclasses import dataclass

from cadastros.models import AssinaturaConfiguracao
from cadastros.models import ConfiguracaoSistema
from documentos.models import DocumentoArtefato
from documentos.services.types import DocumentoTipo


class AssinanteNaoConfiguradoError(ValueError):
    pass


@dataclass(frozen=True)
class AssinanteResolvido:
    servidor: object
    usuario: object | None
    nome: str
    cpf: str
    email: str
    cargo: str
    unidade: str


def _assinante_de_configuracao(tipo_cfg: str, *, mensagem_sem_config: str) -> AssinanteResolvido:
    cfg = ConfiguracaoSistema.get_singleton()
    assinatura = (
        cfg.assinaturas.select_related("servidor", "servidor__cargo", "servidor__unidade")
        .filter(
            tipo=tipo_cfg,
            ordem=1,
            ativo=True,
            servidor__isnull=False,
        )
        .first()
    )
    if not assinatura or not assinatura.servidor_id:
        raise AssinanteNaoConfiguradoError(mensagem_sem_config)
    return _snapshot_servidor(assinatura.servidor)


def _snapshot_servidor(servidor) -> AssinanteResolvido:
    cargo = servidor.cargo.nome if getattr(servidor, "cargo_id", None) and servidor.cargo else ""
    unidade = ""
    if getattr(servidor, "unidade_id", None) and servidor.unidade:
        unidade = servidor.unidade.sigla or servidor.unidade.nome
    return AssinanteResolvido(
        servidor=servidor,
        usuario=None,
        nome=(servidor.nome or "").strip(),
        cpf=(servidor.cpf or "").strip(),
        email="",
        cargo=cargo,
        unidade=unidade,
    )


def resolver_assinante_para_artefato(artefato: DocumentoArtefato) -> AssinanteResolvido:
    tipo = (artefato.tipo or "").strip().lower()
    if tipo == DocumentoTipo.OFICIO.value:
        return _assinante_de_configuracao(
            AssinaturaConfiguracao.TIPO_OFICIO,
            mensagem_sem_config="Nenhum assinante de ofício configurado nas Configurações do Sistema.",
        )
    if tipo == DocumentoTipo.JUSTIFICATIVA.value:
        return _assinante_de_configuracao(
            AssinaturaConfiguracao.TIPO_JUSTIFICATIVA,
            mensagem_sem_config="Nenhum assinante de justificativa configurado nas Configurações do Sistema.",
        )
    if tipo == DocumentoTipo.TERMO_AUTORIZACAO.value:
        srv = getattr(artefato, "servidor", None)
        if srv is None or not getattr(srv, "pk", None):
            raise AssinanteNaoConfiguradoError(
                "Artefato de termo sem servidor vinculado; não é possível determinar o assinante."
            )
        return _snapshot_servidor(srv)

    raise AssinanteNaoConfiguradoError(
        f"Nenhum assinante configurado para o tipo de documento '{artefato.tipo}'."
    )
