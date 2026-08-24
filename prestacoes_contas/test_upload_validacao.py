"""QA-04 — a política central de upload precisa valer nos três caminhos de escrita.

``core.uploads.validate_private_document_upload`` é a política do projeto para
anexo privado: limite de tamanho, *magic bytes* de PDF/imagem, bomba de
descompressão e antivírus. Ela estava **declarada** em
``PrestacaoDocumentoAnexo.arquivo`` e nunca executava, porque os três caminhos de
escrita usam ``.objects.create()`` — e validador de campo não roda em ``create()``.

O que estes testes fixam é o contrato pelo ponto de entrada, não pelo modelo:
arquivo que mente sobre o próprio conteúdo é recusado com mensagem, em vez de ser
gravado e sincronizado com o Google Drive.
"""

from __future__ import annotations

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from prestacoes_contas.models import PrestacaoDocumentoAnexo
from prestacoes_contas.test_helpers import PrestacaoFixturesMixin

PDF_VALIDO = b"%PDF-1.4\n%%EOF\n"
NAO_E_PDF = b"nao sou um pdf de verdade, so tenho a extensao"


def arquivo(nome="despacho.pdf", conteudo=PDF_VALIDO):
    return SimpleUploadedFile(nome, conteudo, content_type="application/pdf")


class UploadAssinadoValidacaoTests(PrestacaoFixturesMixin, TestCase):
    """Caminho sem formulário: ``_prestacao_assinado_upload`` via ``request.FILES``."""

    def setUp(self):
        super().setUp()
        self.setUpPrestacaoFixtures()
        self.fixture = self.criar_prestacao(numero=1)
        self.ps = self.fixture.prestacoes_servidor[0]

    def _anexar_despacho(self, arq):
        return self.client.post(
            reverse(
                "prestacoes_contas:prestacao_despacho_assinado_anexar",
                args=[self.fixture.prestacao.pk],
            ),
            {"arquivo": arq},
            follow=True,
        )

    def test_pdf_valido_e_aceito(self):
        self._anexar_despacho(arquivo())

        self.assertEqual(
            PrestacaoDocumentoAnexo.objects.filter(
                prestacao=self.fixture.prestacao,
                tipo=PrestacaoDocumentoAnexo.TIPO_DESPACHO,
            ).count(),
            1,
        )

    def test_varios_arquivos_do_mesmo_tipo_sao_salvos_na_mesma_acao(self):
        response = self.client.post(
            reverse(
                "prestacoes_contas:prestacao_despacho_assinado_anexar",
                args=[self.fixture.prestacao.pk],
            ),
            {"arquivo": [arquivo("parte-1.pdf"), arquivo("parte-2.pdf")]},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            list(
                PrestacaoDocumentoAnexo.objects.filter(
                    prestacao=self.fixture.prestacao,
                    tipo=PrestacaoDocumentoAnexo.TIPO_DESPACHO,
                ).values_list("nome_original", flat=True)
            ),
            ["parte-1.pdf", "parte-2.pdf"],
        )

    def test_extensao_pdf_com_conteudo_que_nao_e_pdf_e_recusada(self):
        response = self._anexar_despacho(arquivo(conteudo=NAO_E_PDF))

        self.assertEqual(PrestacaoDocumentoAnexo.objects.count(), 0)
        mensagens = [str(m) for m in response.context["messages"]]
        self.assertTrue(
            any("PDF" in m for m in mensagens),
            msg=f"esperava mensagem sobre conteúdo inválido, veio: {mensagens}",
        )

    @override_settings(PRIVATE_UPLOAD_MAX_BYTES=8)
    def test_arquivo_acima_do_limite_de_tamanho_e_recusado(self):
        response = self._anexar_despacho(arquivo())

        self.assertEqual(PrestacaoDocumentoAnexo.objects.count(), 0)
        mensagens = [str(m) for m in response.context["messages"]]
        self.assertTrue(
            any("limite" in m.lower() for m in mensagens),
            msg=f"esperava mensagem sobre tamanho, veio: {mensagens}",
        )

    def test_recusa_nao_apaga_os_anexos_ja_existentes(self):
        """A view apaga os anteriores antes de gravar; recusar não pode custar o que já existia."""
        self._anexar_despacho(arquivo("primeiro.pdf"))
        self.assertEqual(PrestacaoDocumentoAnexo.objects.count(), 1)

        self._anexar_despacho(arquivo("segundo.pdf", conteudo=NAO_E_PDF))

        self.assertEqual(PrestacaoDocumentoAnexo.objects.count(), 1)
        self.assertEqual(PrestacaoDocumentoAnexo.objects.get().nome_original, "primeiro.pdf")


class UploadPorFormularioValidacaoTests(PrestacaoFixturesMixin, TestCase):
    """Caminho com formulário: ``PrestacaoServidorDocumentosForm`` (comprovante)."""

    def setUp(self):
        super().setUp()
        self.setUpPrestacaoFixtures()
        self.fixture = self.criar_prestacao(numero=2)
        self.ps = self.fixture.prestacoes_servidor[0]

    def _enviar_comprovante(self, arq):
        return self.client.post(
            reverse(
                "prestacoes_contas:prestacao_servidor_arquivo_autosave",
                args=[self.ps.pk],
            ),
            {f"ps-{self.ps.pk}-comprovante_arquivos": arq},
        )

    def test_pdf_valido_e_aceito(self):
        response = self._enviar_comprovante(arquivo("comprovante.pdf"))

        self.assertTrue(response.json()["ok"])
        self.assertEqual(self.ps.documentos_anexos.count(), 1)

    def test_extensao_pdf_com_conteudo_que_nao_e_pdf_e_recusada(self):
        response = self._enviar_comprovante(arquivo("comprovante.pdf", conteudo=NAO_E_PDF))

        self.assertFalse(response.json()["ok"])
        self.assertEqual(self.ps.documentos_anexos.count(), 0)
