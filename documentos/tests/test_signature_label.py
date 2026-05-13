import hashlib
import io

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from assinaturas.models import PedidoAssinaturaDocumento
from cadastros.models import AssinaturaConfiguracao
from cadastros.models import Cargo
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Servidor
from documentos.models import DocumentoArtefato
from documentos.services.signing.label_overlay import aplicar_etiqueta_assinatura_pdf
from documentos.services.signing.position import SignaturePositionNormalizada
from documentos.services.signing.position import parse_signature_position_from_post
from documentos.services.signing.workflow import assinar_artefato_pdf
from documentos.services.signing.workflow import contar_paginas_pdf_artefato
from oficios.models import Oficio
from pypdf import PdfReader


def _minimal_valid_pdf_bytes() -> bytes:
    """PDF mínimo válido para o pypdf (uma página)."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R/Resources<<>>>>endobj\n"
        b"4 0 obj<</Length 21>>stream\nBT /F1 12 Tf ET\nendstream\nendobj\n"
        b"xref\n0 5\n0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000214 00000 n \n"
        b"trailer<</Size 5/Root 1 0 R>>\n"
        b"startxref\n310\n"
        b"%%EOF\n"
    )


class SignaturePositionParseTests(TestCase):
    def test_clampa_valores_extremos(self):
        post = {
            "sig_x": "2",
            "sig_y": "-1",
            "sig_w": "0.01",
            "sig_h": "0.99",
            "sig_page": "99",
        }
        p = parse_signature_position_from_post(post, num_pages=3)
        self.assertIsNotNone(p)
        assert p is not None
        self.assertEqual(p.page_index, 2)
        self.assertEqual(p.box_y, 0.0)
        self.assertGreaterEqual(p.box_w, 0.2)
        self.assertLessEqual(p.box_h, 0.22)
        self.assertLessEqual(p.box_x + p.box_w, 1.0001)

    def test_sig_page_menos_um_ultima_pagina(self):
        post = {"sig_x": "0.1", "sig_y": "0.1", "sig_w": "0.3", "sig_h": "0.1", "sig_page": "-1"}
        p = parse_signature_position_from_post(post, num_pages=5)
        self.assertIsNotNone(p)
        assert p is not None
        self.assertEqual(p.page_index, 4)


class LabelOverlayPdfTests(TestCase):
    def test_overlay_contem_texto_institucional(self):
        raw = _minimal_valid_pdf_bytes()
        pos = SignaturePositionNormalizada(0, 0.05, 0.05, 0.5, 0.12)
        out, meta = aplicar_etiqueta_assinatura_pdf(
            raw,
            pos,
            signer_name="Teste",
            verification_url="https://exemplo.invalido/ver",
            code_short="abc123",
        )
        self.assertEqual(meta.get("stamp"), "label_overlay")
        self.assertIn(b"DOCUMENTO ASSINADO", out)

    def test_overlay_nao_exibe_prefixo_sha256_como_codigo(self):
        raw = _minimal_valid_pdf_bytes()
        pos = SignaturePositionNormalizada(0, 0.05, 0.05, 0.55, 0.14)
        digest = "a" * 64
        prefix = digest[:12]
        out, meta = aplicar_etiqueta_assinatura_pdf(
            raw,
            pos,
            signer_name="Teste",
            verification_url="https://exemplo.invalido/assinaturas/verificar/CV-2099-ABCDEF/",
            code_short=prefix,
        )
        self.assertEqual(meta.get("stamp"), "label_overlay")
        text = "".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(out)).pages)
        self.assertNotIn(prefix, text)
        self.assertIn("Validação", text)


@override_settings(DOCUMENTOS_PERSIST_ARTEFATOS=True, SIGNATURE_BACKEND="disabled")
class WizardAssinaturaCamposEtiquetaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="lbl_u", password="p" * 12)
        self.client.force_login(self.user)
        self.cargo = Cargo.objects.create(nome="C")
        self.servidor = Servidor.objects.create(nome="S", cargo=self.cargo, cpf="11122233344")
        cfg = ConfiguracaoSistema.get_singleton()
        AssinaturaConfiguracao.objects.update_or_create(
            configuracao=cfg,
            tipo=AssinaturaConfiguracao.TIPO_OFICIO,
            ordem=1,
            defaults={"servidor": self.servidor, "ativo": True},
        )
        self.oficio = Oficio.objects.create(
            numero=9,
            ano=2026,
            protocolo="1.2.3-4",
            motivo="m",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        self.oficio.servidores.add(self.servidor)
        raw = _minimal_valid_pdf_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        self.art = DocumentoArtefato.objects.create(
            tipo="oficio",
            formato="pdf",
            oficio=self.oficio,
            hash_sha256=digest,
            arquivo=ContentFile(raw, name="lbl.pdf"),
        )

    @staticmethod
    def _validacao_limpa():
        return {"status": "complete", "pendencias": [], "checks": {}}

    def test_get_pagina_e_central_sem_editor_de_assinatura(self):
        from unittest import mock

        with mock.patch("oficios.assinaturas_central.validar_oficio_para_documento", return_value=self._validacao_limpa()):
            url = reverse("oficios:wizard_assinaturas", args=[self.oficio.pk])
            r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Central de assinaturas")
        self.assertNotContains(r, 'name="sig_x"')
        self.assertNotContains(r, "assinatura-pdf.js")
        self.assertNotContains(r, 'id="assinatura-pdf-editor"')
        self.assertNotContains(r, "Arraste a etiqueta")

    def test_post_gera_pedido_sem_assinar_diretamente(self):
        url = reverse("oficios:wizard_assinaturas", args=[self.oficio.pk])
        self.client.post(
            url,
            {"gerar_solicitacao": "1", "artefato_id": str(self.art.pk)},
        )
        pedido = PedidoAssinaturaDocumento.objects.get(artefato=self.art)
        self.assertEqual(pedido.nome_assinante_snapshot, "S")

    def test_assinar_artefato_pdf_embute_texto(self):
        from django.test import RequestFactory

        pos = SignaturePositionNormalizada(0, 0.1, 0.1, 0.45, 0.12)
        rf = RequestFactory()
        request = rf.get("/")
        request.META["HTTP_HOST"] = "testserver"
        request.user = self.user
        out = assinar_artefato_pdf(request, self.art, signature_position=pos)
        self.assertIn("pdf_bytes", out)
        self.assertIn(b"DOCUMENTO ASSINADO", out["pdf_bytes"])

    def test_contar_paginas_antes_de_assinar_nao_esvazia_leitura(self):
        """Mesma ordem da view: contar páginas (read) e depois assinar (read de novo)."""
        from django.test import RequestFactory

        self.assertGreaterEqual(contar_paginas_pdf_artefato(self.art), 1)
        pos = SignaturePositionNormalizada(0, 0.1, 0.1, 0.45, 0.12)
        rf = RequestFactory()
        request = rf.get("/")
        request.META["HTTP_HOST"] = "testserver"
        request.user = self.user
        out = assinar_artefato_pdf(request, self.art, signature_position=pos)
        self.assertIn(b"DOCUMENTO ASSINADO", out["pdf_bytes"])

