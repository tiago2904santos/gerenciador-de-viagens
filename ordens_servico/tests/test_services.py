"""Regressão: OS rascunho (em_elaboracao=True) nunca vira DocumentoArtefato.

Contexto do bug: quando um mesmo OrdemServico cobre 2 ofícios, o backfill do
Drive (``integracoes.google_drive.organizer._garantir_ordens_servico``) só
gera o PDF real (com os servidores certos) para o ofício "âncora" e pula os
demais se eles já tiverem QUALQUER artefato tipo=ordem_servico — inclusive um
rascunho em branco deixado por ``gerar_resposta_ordem_servico_documento``
(rota de pré-visualização do wizard do ofício, que nunca sabe quais
servidores foram designados). Isso fazia a OS do ofício não-âncora ser
enviada em branco pro Drive.
"""

from __future__ import annotations

from unittest import mock

from django.test import TestCase, override_settings

from documentos.models import DocumentoArtefato
from documentos.services.facade import DocumentoGerado
from documentos.services.types import DocumentoFormato, DocumentoTipo
from oficios.models import Oficio

from ..services import gerar_resposta_ordem_servico_documento


def _doc_gerado(**overrides) -> DocumentoGerado:
    defaults = dict(
        tipo=DocumentoTipo.ORDEM_SERVICO,
        formato=DocumentoFormato.PDF,
        nome_arquivo="ordem-servico.pdf",
        content_type="application/pdf",
        conteudo=b"%PDF-1.4\n",
        hash_sha256="abc123",
        pdf_engine_used="simple_fallback",
    )
    defaults.update(overrides)
    return DocumentoGerado(**defaults)


@override_settings(DOCUMENTOS_PERSIST_ARTEFATOS=True, DOCUMENTOS_ARTIFACT_CACHE=False)
class GerarRespostaOrdemServicoDocumentoTests(TestCase):
    def setUp(self):
        self.oficio = Oficio.objects.create(numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC)

    @mock.patch("ordens_servico.services.build_canonical_document_payload")
    @mock.patch("ordens_servico.services.build_default_facade")
    def test_rascunho_em_elaboracao_nao_persiste_artefato(self, m_facade, m_payload):
        m_payload.return_value = {"em_elaboracao": True}
        m_facade.return_value.gerar.return_value = _doc_gerado()

        response = gerar_resposta_ordem_servico_documento(self.oficio, DocumentoFormato.PDF)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            DocumentoArtefato.objects.filter(tipo="ordem_servico", oficio=self.oficio).exists(),
            "rascunho em_elaboracao=True não deveria virar DocumentoArtefato",
        )

    @mock.patch("ordens_servico.services.build_canonical_document_payload")
    @mock.patch("ordens_servico.services.build_default_facade")
    def test_versao_finalizada_persiste_artefato(self, m_facade, m_payload):
        m_payload.return_value = {}
        m_facade.return_value.gerar.return_value = _doc_gerado()

        gerar_resposta_ordem_servico_documento(self.oficio, DocumentoFormato.PDF)

        self.assertTrue(
            DocumentoArtefato.objects.filter(tipo="ordem_servico", oficio=self.oficio).exists()
        )
