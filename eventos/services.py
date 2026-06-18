# Servicos de agrupamento OPCIONAL de documentos ficam neste modulo.
from __future__ import annotations


def build_evento_document_context(evento) -> dict:
    """Monta o contexto reaproveitavel de um Evento para pre-preencher documentos.

    Esse dicionario sera usado nas proximas etapas para sugerir valores ao criar
    Oficio, Termo, Plano de Trabalho, Ordem de Servico, Relatorio Tecnico e
    Diario de Bordo a partir de um evento. Ele nao impoe nada: os documentos
    continuam podendo ser criados de forma avulsa e o evento e sempre opcional.

    Os relacionamentos (`unidade_responsavel`, `responsavel`) sao devolvidos como
    instancias (ou None) para que o consumidor escolha usar o pk no pre-preenchimento
    de um ForeignKey ou o texto na exibicao.
    """

    if evento is None:
        return {}

    return {
        "evento_id": evento.pk,
        "titulo": evento.titulo,
        "descricao": evento.descricao,
        "destino_uf": evento.destino_uf,
        "destino_cidade": evento.destino_cidade,
        "data_inicio": evento.data_inicio,
        "data_fim": evento.data_fim,
        "horario_inicio": evento.horario_inicio,
        "horario_fim": evento.horario_fim,
        "unidade_responsavel": evento.unidade_responsavel,
        "responsavel": evento.responsavel,
    }
