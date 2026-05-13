from __future__ import annotations

import hashlib
from datetime import timedelta

from django.core.files.base import ContentFile
from django.test import TestCase
from django.utils import timezone

from assinaturas.models import PedidoAssinaturaDocumento
from assinaturas.presenters import assinatura_urls_artefato
from cadastros.models import Servidor
from documentos.models import DocumentoArtefato


def _pdf():
    return b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


class AssinaturaPresentersLinksTests(TestCase):
    def test_urls_reversiveis_sem_assinatura(self):
        raw = _pdf()
        d = hashlib.sha256(raw).hexdigest()
        srv = Servidor.objects.create(nome="S")
        art = DocumentoArtefato.objects.create(
            tipo="t",
            formato="pdf",
            servidor=srv,
            hash_sha256=d,
            arquivo=ContentFile(raw, name="p.pdf"),
        )
        u = assinatura_urls_artefato(art)
        self.assertIn("/assinaturas/artefatos/", u["gerar_link"])
        self.assertEqual(u["assinar"], "")
        self.assertIn("/pdf-original/", u["pdf_original"])

    def test_urls_incluem_pedido_pendente(self):
        raw = _pdf()
        d = hashlib.sha256(raw).hexdigest()
        srv = Servidor.objects.create(nome="S")
        art = DocumentoArtefato.objects.create(
            tipo="oficio",
            formato="pdf",
            servidor=srv,
            hash_sha256=d,
            arquivo=ContentFile(raw, name="p.pdf"),
        )
        pedido = PedidoAssinaturaDocumento.objects.create(
            artefato=art,
            token="tok",
            assinante_servidor=srv,
            nome_assinante_snapshot="S",
            tipo_documento="oficio",
            expira_em=timezone.now() + timedelta(days=1),
        )
        u = assinatura_urls_artefato(art)
        self.assertEqual(u["assinar"], "")
        self.assertIn(f"/assinaturas/assinar/{pedido.token}/", u["pedido"])
        self.assertIn(f"/assinaturas/pedidos/{pedido.token}/revogar/", u["revogar"])
