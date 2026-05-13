import hashlib
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from assinaturas.models import PedidoAssinaturaDocumento
from cadastros.models import AssinaturaConfiguracao
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Cargo
from cadastros.models import Servidor
from documentos.models import DocumentoArtefato
from oficios.models import Oficio


def _minimal_pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _validacao_limpa():
    return {"status": "complete", "pendencias": [], "checks": {}}


@override_settings(DOCUMENTOS_PERSIST_ARTEFATOS=True, SIGNATURE_BACKEND="disabled")
class WizardAssinaturasEtapa6Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="wiz_sign_u", password="w" * 12)
        self.client.force_login(self.user)
        self.cargo = Cargo.objects.create(nome="Cargo WizS")
        self.servidor = Servidor.objects.create(nome="Serv WizS", cargo=self.cargo, cpf="99888777666")
        cfg = ConfiguracaoSistema.get_singleton()
        AssinaturaConfiguracao.objects.update_or_create(
            configuracao=cfg,
            tipo=AssinaturaConfiguracao.TIPO_OFICIO,
            ordem=1,
            defaults={"servidor": self.servidor, "ativo": True},
        )
        AssinaturaConfiguracao.objects.update_or_create(
            configuracao=cfg,
            tipo=AssinaturaConfiguracao.TIPO_JUSTIFICATIVA,
            ordem=1,
            defaults={"servidor": self.servidor, "ativo": True},
        )
        self.oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            protocolo="10.20.30-4",
            motivo="mot",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        self.oficio.servidores.add(self.servidor)
        self.oficio.servidores_termo_autorizacao.add(self.servidor)
        raw = _minimal_pdf_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        self._art_oficio = DocumentoArtefato.objects.create(
            tipo="oficio",
            formato="pdf",
            oficio=self.oficio,
            hash_sha256=digest,
            arquivo=ContentFile(raw, name="oficio_wiz.pdf"),
        )
        self._art_just = DocumentoArtefato.objects.create(
            tipo="justificativa",
            formato="pdf",
            oficio=self.oficio,
            hash_sha256=digest,
            arquivo=ContentFile(raw, name="just_wiz.pdf"),
        )
        self._art_termo = DocumentoArtefato.objects.create(
            tipo="termo_autorizacao",
            formato="pdf",
            oficio=self.oficio,
            servidor=self.servidor,
            hash_sha256=digest,
            arquivo=ContentFile(raw, name="termo_wiz.pdf"),
        )

    @mock.patch("oficios.assinaturas_central.validar_oficio_para_documento", return_value=_validacao_limpa())
    def test_get_etapa_assinaturas_200_sem_attachment(self, _m_val):
        url = reverse("oficios:wizard_assinaturas", args=[self.oficio.pk])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r["Content-Type"])
        disp = r.get("Content-Disposition") or ""
        self.assertNotIn("attachment", disp.lower())
        self.assertContains(r, "Gerar solicitação")
        self.assertContains(r, "Central de assinaturas")
        self.assertNotContains(r, "Confirmar assinatura")
        self.assertNotContains(r, "Arraste a etiqueta")
        self.assertTemplateUsed(r, "oficios/wizard_assinaturas.html")

    @mock.patch("oficios.assinaturas_central.validar_oficio_para_documento", return_value=_validacao_limpa())
    def test_get_lista_documentos_e_iframe_conteudo(self, _m_val):
        url = reverse("oficios:wizard_assinaturas", args=[self.oficio.pk])
        r = self.client.get(url)
        self.assertContains(r, "Ofício (PDF)")
        self.assertContains(r, "Termo de Autorização")
        self.assertContains(r, "Justificativa (PDF)")
        self.assertContains(r, "/documentos/artefatos/")
        self.assertContains(r, "/conteudo/")
        self.assertNotContains(r, "Ver comprovante")
        self.assertNotContains(r, "Visualizar documento original")
        self.assertNotContains(r, "Verificar assinatura")

    @mock.patch("oficios.assinaturas_central.validar_oficio_para_documento", return_value=_validacao_limpa())
    def test_post_gera_pedido_oficio(self, _m_val):
        url = reverse("oficios:wizard_assinaturas", args=[self.oficio.pk])
        r = self.client.post(
            url,
            {"gerar_solicitacao": "1", "artefato_id": str(self._art_oficio.pk)},
            follow=False,
        )
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("oficios:wizard_assinaturas", args=[self.oficio.pk]), r["Location"])
        self._art_oficio.refresh_from_db()
        self.assertFalse((self._art_oficio.hash_sha256_assinado or "").strip())
        pedido = PedidoAssinaturaDocumento.objects.get(artefato=self._art_oficio)
        self.assertEqual(pedido.nome_assinante_snapshot, "SERV WIZS")

    @mock.patch("oficios.assinaturas_central.validar_oficio_para_documento", return_value=_validacao_limpa())
    def test_get_mostra_link_publico_apos_gerar_solicitacao(self, _m_val):
        url = reverse("oficios:wizard_assinaturas", args=[self.oficio.pk])
        self.client.post(url, {"gerar_solicitacao": "1", "artefato_id": str(self._art_oficio.pk)})
        pedido = PedidoAssinaturaDocumento.objects.get(artefato=self._art_oficio)
        r = self.client.get(url)
        self.assertContains(r, "Link para o assinante")
        self.assertContains(r, "Copiar link")
        self.assertContains(r, "/assinaturas/assinar/")
        self.assertContains(r, pedido.token)
        self.assertNotContains(r, "Enviar")

    @mock.patch("oficios.assinaturas_central.validar_oficio_para_documento", return_value=_validacao_limpa())
    def test_post_segundo_pedido_nao_duplica(self, _m_val):
        url = reverse("oficios:wizard_assinaturas", args=[self.oficio.pk])
        self.client.post(url, {"gerar_solicitacao": "1", "artefato_id": str(self._art_oficio.pk)})
        self.client.post(url, {"gerar_solicitacao": "1", "artefato_id": str(self._art_oficio.pk)})
        self.assertEqual(PedidoAssinaturaDocumento.objects.filter(artefato=self._art_oficio).count(), 1)

    @mock.patch("oficios.assinaturas_central.validar_oficio_para_documento", return_value=_validacao_limpa())
    def test_post_legacy_assinar_pdf_oficio_redireciona_etapa6(self, _m_val):
        url = reverse("oficios:wizard_assinar_pdf_oficio", args=[self.oficio.pk])
        r = self.client.post(url, follow=False)
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("oficios:wizard_assinaturas", args=[self.oficio.pk]), r["Location"])

    @mock.patch("oficios.assinaturas_central.validar_oficio_para_documento", return_value=_validacao_limpa())
    def test_get_legacy_assinar_pdf_redireciona_etapa6(self, _m_val):
        url = reverse("oficios:wizard_assinar_pdf_oficio", args=[self.oficio.pk])
        r = self.client.get(url, follow=False)
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("oficios:wizard_assinaturas", args=[self.oficio.pk]), r["Location"])

    @mock.patch("oficios.assinaturas_central.validar_oficio_para_documento", return_value=_validacao_limpa())
    def test_alias_assinar_redireciona_etapa6(self, _m_val):
        url = reverse("oficios:wizard_assinaturas_assinar_alias", args=[self.oficio.pk])
        r = self.client.get(url, follow=False)
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("oficios:wizard_assinaturas", args=[self.oficio.pk]), r["Location"])

    @mock.patch("oficios.views.gerar_resposta_documento_oficio", return_value=HttpResponse(b"x", content_type="application/pdf"))
    @mock.patch("oficios.views.validar_oficio_para_documento", return_value=_validacao_limpa())
    def test_verificar_json_sem_pdf_previo_422(self, _m_val, _m_gerar):
        url = reverse("oficios:wizard_verificar_pdf_oficio", args=[self.oficio.pk])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 422)
        self.assertFalse(r.json().get("ok"))


class WizardDocumentosAssinarPdfLinkTests(TestCase):
    def test_template_link_assinaturas_e_anchor_get(self):
        tpl = Path(settings.BASE_DIR) / "templates" / "oficios" / "wizard_documentos.html"
        s = tpl.read_text(encoding="utf-8")
        idx = s.index("Central de assinaturas")
        window = s[max(0, idx - 500) : idx + 30]
        self.assertIn("href=", window)
        self.assertIn("wizard_assinaturas", window)
        self.assertNotIn("formaction", window)
        self.assertNotIn('type="submit"', window)
