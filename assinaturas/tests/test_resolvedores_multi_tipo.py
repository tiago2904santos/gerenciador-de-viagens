import hashlib

from django.core.files.base import ContentFile
from django.test import TestCase

from assinaturas.services.resolvedores import AssinanteNaoConfiguradoError
from assinaturas.services.resolvedores import resolver_assinante_para_artefato
from cadastros.models import AssinaturaConfiguracao
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Cargo
from cadastros.models import Servidor
from documentos.models import DocumentoArtefato
from documentos.services.types import DocumentoTipo
from oficios.models import Oficio


def _pdf():
    return b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


class ResolverAssinanteArtefatoTests(TestCase):
    def setUp(self):
        self.cargo = Cargo.objects.create(nome="C")
        self.srv_a = Servidor.objects.create(nome="Alice", cargo=self.cargo, cpf="11122233344")
        self.srv_b = Servidor.objects.create(nome="Bob", cargo=self.cargo, cpf="55566677788")
        cfg = ConfiguracaoSistema.get_singleton()
        for tipo in (AssinaturaConfiguracao.TIPO_OFICIO, AssinaturaConfiguracao.TIPO_JUSTIFICATIVA):
            AssinaturaConfiguracao.objects.update_or_create(
                configuracao=cfg,
                tipo=tipo,
                ordem=1,
                defaults={"servidor": self.srv_a, "ativo": True},
            )
        self.oficio = Oficio.objects.create(
            numero=1,
            ano=2026,
            protocolo="p",
            motivo="m",
            custeio=Oficio.CUSTEIO_UNIDADE_DPC,
        )
        raw = _pdf()
        d = hashlib.sha256(raw).hexdigest()
        self.art_oficio = DocumentoArtefato.objects.create(
            tipo=DocumentoTipo.OFICIO.value,
            formato="pdf",
            oficio=self.oficio,
            hash_sha256=d,
            arquivo=ContentFile(raw, name="o.pdf"),
        )
        self.art_just = DocumentoArtefato.objects.create(
            tipo=DocumentoTipo.JUSTIFICATIVA.value,
            formato="pdf",
            oficio=self.oficio,
            hash_sha256=d,
            arquivo=ContentFile(raw, name="j.pdf"),
        )
        self.art_termo = DocumentoArtefato.objects.create(
            tipo=DocumentoTipo.TERMO_AUTORIZACAO.value,
            formato="pdf",
            oficio=self.oficio,
            servidor=self.srv_b,
            hash_sha256=d,
            arquivo=ContentFile(raw, name="t.pdf"),
        )

    def test_oficio_usa_config(self):
        r = resolver_assinante_para_artefato(self.art_oficio)
        self.assertEqual(r.servidor.pk, self.srv_a.pk)

    def test_justificativa_usa_config(self):
        r = resolver_assinante_para_artefato(self.art_just)
        self.assertEqual(r.servidor.pk, self.srv_a.pk)

    def test_termo_usa_servidor_do_artefato(self):
        r = resolver_assinante_para_artefato(self.art_termo)
        self.assertEqual(r.servidor.pk, self.srv_b.pk)

    def test_termo_sem_servidor_erro(self):
        art = DocumentoArtefato.objects.create(
            tipo=DocumentoTipo.TERMO_AUTORIZACAO.value,
            formato="pdf",
            oficio=self.oficio,
            hash_sha256=self.art_oficio.hash_sha256,
            arquivo=ContentFile(_pdf(), name="x.pdf"),
        )
        with self.assertRaises(AssinanteNaoConfiguradoError):
            resolver_assinante_para_artefato(art)
