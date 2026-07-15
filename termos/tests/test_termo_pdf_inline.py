"""Termo PDF inline por servidor."""

from io import BytesIO
from zipfile import ZipFile
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader

from cadastros.models import Cidade
from cadastros.models import Combustivel
from cadastros.models import Cargo
from cadastros.models import Estado
from cadastros.models import Servidor
from cadastros.models import Unidade
from cadastros.models import Viatura
from documentos.services.types import DocumentoFormato
from oficios.documents import build_termo_payload
from oficios.models import Oficio
from roteiros.models import Roteiro
from roteiros.models import RoteiroDestino
from roteiros.models import RoteiroTrecho
from termos.services import gerar_termo_um
from termos.services import gerar_termo_lote
from termos.services import sha256_bytes


class TermoServidorPdfInlineTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester_termo_inline", password="123456")
        self.client.force_login(self.user)
        self.cargo = Cargo.objects.create(nome="Cargo T")
        self.unidade = Unidade.objects.create(nome="Unidade T", sigla="UT")
        self.servidor_no = Servidor.objects.create(
            nome="Fora do oficio",
            cargo=self.cargo,
            cpf="11111111111",
            unidade=self.unidade,
        )
        self.servidor_ok = Servidor.objects.create(
            nome="No oficio",
            cargo=self.cargo,
            cpf="22222222222",
            rg="1234567",
            telefone="41999998888",
            unidade=self.unidade,
        )
        self.estado = Estado.objects.create(nome="Parana", sigla="PR")
        self.cidade_origem = Cidade.objects.create(nome="Curitiba", estado=self.estado, uf="PR")
        self.cidade_destino = Cidade.objects.create(nome="Londrina", estado=self.estado, uf="PR")
        self.roteiro = Roteiro.objects.create(
            origem_estado=self.estado,
            origem_cidade=self.cidade_origem,
            saida_dt=timezone.make_aware(timezone.datetime(2026, 5, 13, 8, 0)),
            retorno_saida_dt=timezone.make_aware(timezone.datetime(2026, 5, 15, 17, 0)),
            retorno_chegada_dt=timezone.make_aware(timezone.datetime(2026, 5, 15, 21, 0)),
            quantidade_diarias="2,5",
            valor_diarias="1250.00",
            valor_diarias_extenso="mil duzentos e cinquenta reais",
        )
        RoteiroDestino.objects.create(
            roteiro=self.roteiro,
            estado=self.estado,
            cidade=self.cidade_destino,
            ordem=1,
        )
        RoteiroTrecho.objects.create(
            roteiro=self.roteiro,
            tipo=RoteiroTrecho.TIPO_IDA,
            ordem=1,
            origem_estado=self.estado,
            origem_cidade=self.cidade_origem,
            destino_estado=self.estado,
            destino_cidade=self.cidade_destino,
            saida_dt=timezone.make_aware(timezone.datetime(2026, 5, 13, 8, 0)),
            chegada_dt=timezone.make_aware(timezone.datetime(2026, 5, 13, 14, 0)),
        )
        combustivel = Combustivel.objects.create(nome="Gasolina")
        self.viatura = Viatura.objects.create(
            placa="ABC1234",
            modelo="Duster",
            combustivel=combustivel,
            tipo=Viatura.TIPO_CARACTERIZADA,
        )
        self.oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            protocolo="123456781",
            assunto="Viagem institucional",
            motivo="Cumprimento de diligencia policial.",
            solicitante=self.unidade,
            roteiro=self.roteiro,
            viatura=self.viatura,
            motorista=self.servidor_ok,
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        self.oficio.servidores.add(self.servidor_ok)
        self.oficio.servidores_termo_autorizacao.add(self.servidor_ok)

    @mock.patch("termos.views.validar_oficio_para_documento", return_value={"pendencias": ["x"]})
    def test_redirect_quando_oficio_incompleto(self, _m):
        url = reverse("termos:termo_servidor_pdf_inline", args=[self.oficio.pk, self.servidor_ok.pk])
        response = self.client.get(url, follow=False)
        self.assertEqual(response.status_code, 302)

    @mock.patch("termos.views.validar_oficio_para_documento", return_value={"pendencias": []})
    def test_servidor_fora_do_oficio_retorna_404(self, _m_val):
        url = reverse("termos:termo_servidor_pdf_inline", args=[self.oficio.pk, self.servidor_no.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    @mock.patch("termos.views.validar_oficio_para_documento", return_value={"pendencias": []})
    def test_servidor_sem_termo_retorna_404_no_inline(self, _m_val):
        self.oficio.servidores_termo_autorizacao.clear()
        url = reverse("termos:termo_servidor_pdf_inline", args=[self.oficio.pk, self.servidor_ok.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    @mock.patch("termos.views.validar_oficio_para_documento", return_value={"pendencias": []})
    def test_servidor_sem_termo_retorna_404_no_download(self, _m_val):
        self.oficio.servidores_termo_autorizacao.clear()
        url = reverse("termos:baixar_termo_servidor", args=[self.oficio.pk, self.servidor_ok.pk, "pdf"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    @mock.patch("termos.views.validar_oficio_para_documento", return_value={"pendencias": []})
    @mock.patch("termos.views.pdf_termo_oficio_assinado_ou_gerado")
    def test_inline_com_sha256(self, m_gerar, _m_val):
        m_gerar.return_value = b"%PDF-1.4\n"
        url = reverse("termos:termo_servidor_pdf_inline", args=[self.oficio.pk, self.servidor_ok.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("inline", response["Content-Disposition"])
        self.assertEqual(response["X-Document-SHA256"], sha256_bytes(b"%PDF-1.4\n"))
        _ = b"".join(response.streaming_content)

    @mock.patch("termos.views.validar_oficio_para_documento", return_value={"pendencias": []})
    @mock.patch("termos.views.pdf_termo_oficio_assinado_ou_gerado")
    def test_download_pdf_anexo_com_sha256(self, m_gerar, _m_val):
        m_gerar.return_value = b"%PDF-1.4\n"
        url = reverse("termos:baixar_termo_servidor", args=[self.oficio.pk, self.servidor_ok.pk, "pdf"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response["X-Document-SHA256"], sha256_bytes(b"%PDF-1.4\n"))
        m_gerar.assert_called_once_with(self.oficio, self.servidor_ok)

    @mock.patch("termos.views.validar_oficio_para_documento", return_value={"pendencias": []})
    @mock.patch("termos.views.fundir_termos_pdf_bytes")
    @mock.patch("termos.views.pdf_termo_oficio_assinado_ou_gerado")
    def test_download_todos_pdf_usa_arquivo_consolidado(self, m_gerar, m_fundir, _m_val):
        self.oficio.servidores_termo_autorizacao.add(self.servidor_ok)
        m_gerar.return_value = b"%PDF-1.4\n1"
        m_fundir.return_value = b"%PDF-1.4\nmerged"

        url = reverse("termos:baixar_termos_todos_pdf", args=[self.oficio.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("termos_oficio_", response["Content-Disposition"])
        self.assertEqual(response.content, b"%PDF-1.4\nmerged")
        m_fundir.assert_called_once_with([b"%PDF-1.4\n1"])

    def test_template_html_oficial_renderiza_dados_reais(self):
        payload = build_termo_payload(self.oficio, self.servidor_ok)
        html = render_to_string("documentos/pdf/termo_autorizacao.html", payload)
        self.assertIn("TERMO DE AUTORIZAÇÃO", html)
        self.assertIn(self.servidor_ok.nome, html)
        self.assertIn(self.oficio.numero_formatado, html)
        self.assertIn("12.345.678-1", html)
        self.assertIn("LONDRINA/PR", html)
        for forbidden in (
            "[DEMO]",
            "TERMO —",
            "Variante:",
            "completo_com_viatura",
            "completo_sem_viatura",
            "semipreenchido",
        ):
            self.assertNotIn(forbidden, html)

    @override_settings(
        DOCUMENTOS_DEFAULT_PDF_ENGINE="simple_fallback",
        DOCUMENTOS_SIMPLE_PDF_FALLBACK=True,
    )
    def test_pdf_gerado_nao_contem_textos_de_stub(self):
        doc = gerar_termo_um(self.oficio, self.servidor_ok, DocumentoFormato.PDF)
        reader = PdfReader(BytesIO(doc.conteudo))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("TERMO DE AUTORIZACAO", text)
        self.assertIn(self.servidor_ok.nome, text)
        for forbidden in (
            "[DEMO]",
            "TERMO —",
            "Variante:",
            "completo_com_viatura",
            "completo_sem_viatura",
            "semipreenchido",
        ):
            self.assertNotIn(forbidden, text)

    def test_docx_oficial_preenche_placeholders_legados(self):
        doc = gerar_termo_um(self.oficio, self.servidor_ok, DocumentoFormato.DOCX)
        self.assertTrue(doc.conteudo.startswith(b"PK"))
        with ZipFile(BytesIO(doc.conteudo)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
        self.assertIn(self.servidor_ok.nome, xml)
        self.assertIn("222.222.222-22", xml)
        self.assertIn("ABC-1234", xml)
        self.assertNotIn("{{", xml)
        for forbidden in (
            "[DEMO]",
            "TERMO —",
            "Variante:",
            "completo_com_viatura",
            "completo_sem_viatura",
            "semipreenchido",
        ):
            self.assertNotIn(forbidden, xml)

    @mock.patch("termos.services.gerar_termo_um")
    def test_lote_gera_apenas_servidores_selecionados_para_termo(self, m_gerar):
        self.oficio.servidores.add(self.servidor_no)
        self.oficio.servidores_termo_autorizacao.set([self.servidor_ok])
        m_gerar.return_value = SimpleNamespace(
            conteudo=b"x",
            hash_sha256="h",
            content_type="application/pdf",
            nome_arquivo="t.pdf",
        )
        docs = gerar_termo_lote(self.oficio, DocumentoFormato.PDF)
        self.assertEqual(len(docs), 1)
        m_gerar.assert_called_once_with(self.oficio, self.servidor_ok, DocumentoFormato.PDF)
