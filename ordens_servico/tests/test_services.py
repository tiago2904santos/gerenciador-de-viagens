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

import re
from datetime import date
from io import BytesIO
from unittest import mock
from zipfile import ZipFile

from django.test import TestCase, override_settings

from cadastros.models import Cidade
from cadastros.models import Estado
from cadastros.models import Servidor
from documentos.models import DocumentoArtefato
from documentos.services.facade import DocumentoGerado
from documentos.services.types import DocumentoFormato, DocumentoTipo
from oficios.models import Oficio

from ..models import OrdemServico
from ..services import gerar_os_docx_response
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


class GerarOrdemServicoDocxTests(TestCase):
    def test_caminhao_usa_template_de_modelos(self):
        estado = Estado.objects.create(nome="PARANA", sigla="PR")
        cidade = Cidade.objects.create(nome="CURITIBA", estado=estado, uf="PR")
        motorista = Servidor.objects.create(nome="MOTORISTA TESTE")
        tecnico = Servidor.objects.create(nome="TECNICO TESTE")
        montagem = Servidor.objects.create(nome="APOIO MONTAGEM")
        escolta = Servidor.objects.create(nome="APOIO ESCOLTA")
        ordem = OrdemServico.objects.create(
            tipo_necessidade=OrdemServico.TIPO_CAMINHAO,
            data_evento_inicio=date(2026, 8, 10),
            data_evento_fim=date(2026, 8, 12),
            motivo="evento institucional",
            motorista_equipe=motorista,
            tecnico_equipe=tecnico,
            apoio_montagem=montagem,
            apoio_escolta=escolta,
        )
        ordem.destinos.set([cidade])

        response = gerar_os_docx_response(ordem)

        self.assertEqual(response.status_code, 200)
        with ZipFile(BytesIO(response.content)) as docx:
            xml = docx.read("word/document.xml").decode("utf-8")
        text = re.sub(r"<[^>]+>", "", xml)
        self.assertIn("Deslocamento - Caminhão de apoio", text)
        self.assertIn("dois dias de antecedência", text)
        self.assertIn("Motorista Teste", text)
