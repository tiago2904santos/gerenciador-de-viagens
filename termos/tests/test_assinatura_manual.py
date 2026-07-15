from datetime import date
from unittest import mock

from django.test import TestCase
from django.test import override_settings

from cadastros.models import Cargo
from cadastros.models import Cidade
from cadastros.models import Estado
from cadastros.models import Servidor
from documentos.models import DocumentoArtefato
from documentos.services.facade import DocumentoGerado
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo
from termos.models import TermoAutorizacao
from termos.services import _persistir_termo_cadastro_artefato
from termos.services import resolver_artefato_termo_cadastro


def _fake_doc(hash_sha256: str = "a" * 64) -> DocumentoGerado:
    return DocumentoGerado(
        tipo=DocumentoTipo.TERMO_AUTORIZACAO,
        formato=DocumentoFormato.PDF,
        nome_arquivo="termo.pdf",
        content_type="application/pdf",
        conteudo=b"%PDF-1.4\n%%EOF\n",
        hash_sha256=hash_sha256,
    )


@override_settings(DOCUMENTOS_PERSIST_ARTEFATOS=True)
class PersistirTermoCadastroArtefatoTests(TestCase):
    def setUp(self):
        self.cargo = Cargo.objects.create(nome="Cargo Termo")
        self.estado = Estado.objects.create(nome="Parana", sigla="PR")
        self.cidade = Cidade.objects.create(nome="Curitiba", estado=self.estado, uf="PR")
        self.servidor = Servidor.objects.create(nome="Servidor Termo", cargo=self.cargo, cpf="33333333333")
        self.termo = TermoAutorizacao.objects.create(
            destino_estado=self.estado,
            destino_cidade=self.cidade,
            data_evento_inicio=date(2026, 8, 1),
            data_evento_fim=date(2026, 8, 1),
        )

    def test_persiste_generico_sem_servidor(self):
        _persistir_termo_cadastro_artefato(self.termo, None, _fake_doc())
        art = DocumentoArtefato.objects.get(termo_id=self.termo.pk, servidor_id=None)
        self.assertEqual(art.tipo, DocumentoTipo.TERMO_AUTORIZACAO.value)
        self.assertIsNone(art.oficio_id)

    def test_persiste_por_servidor(self):
        _persistir_termo_cadastro_artefato(self.termo, self.servidor, _fake_doc())
        art = DocumentoArtefato.objects.get(termo_id=self.termo.pk, servidor_id=self.servidor.pk)
        self.assertEqual(art.servidor_id, self.servidor.pk)

    def test_nao_duplica_pelo_mesmo_hash(self):
        doc = _fake_doc(hash_sha256="b" * 64)
        _persistir_termo_cadastro_artefato(self.termo, self.servidor, doc)
        _persistir_termo_cadastro_artefato(self.termo, self.servidor, doc)
        self.assertEqual(
            DocumentoArtefato.objects.filter(termo_id=self.termo.pk, servidor_id=self.servidor.pk).count(), 1
        )

    def test_termos_avulsos_diferentes_nao_colidem_sem_servidor(self):
        """Dois termos genéricos (sem ofício, sem servidor) não devem compartilhar artefato."""
        outro_termo = TermoAutorizacao.objects.create(
            destino_estado=self.estado,
            destino_cidade=self.cidade,
            data_evento_inicio=date(2026, 8, 2),
            data_evento_fim=date(2026, 8, 2),
        )
        _persistir_termo_cadastro_artefato(self.termo, None, _fake_doc(hash_sha256="c" * 64))
        _persistir_termo_cadastro_artefato(outro_termo, None, _fake_doc(hash_sha256="d" * 64))
        self.assertEqual(DocumentoArtefato.objects.filter(termo_id=self.termo.pk).count(), 1)
        self.assertEqual(DocumentoArtefato.objects.filter(termo_id=outro_termo.pk).count(), 1)


@override_settings(DOCUMENTOS_PERSIST_ARTEFATOS=True)
class ResolverArtefatoTermoCadastroTests(TestCase):
    def setUp(self):
        self.cargo = Cargo.objects.create(nome="Cargo Resolver")
        self.estado = Estado.objects.create(nome="Parana", sigla="PR")
        self.cidade = Cidade.objects.create(nome="Curitiba", estado=self.estado, uf="PR")
        self.termo = TermoAutorizacao.objects.create(
            destino_estado=self.estado,
            destino_cidade=self.cidade,
            data_evento_inicio=date(2026, 8, 1),
            data_evento_fim=date(2026, 8, 1),
        )

    def test_reaproveita_artefato_existente_sem_gerar_de_novo(self):
        _persistir_termo_cadastro_artefato(self.termo, None, _fake_doc())
        existente = DocumentoArtefato.objects.get(termo_id=self.termo.pk, servidor_id=None)

        with mock.patch("termos.services.gerar_termo_cadastro_um") as m_gerar:
            artefato = resolver_artefato_termo_cadastro(self.termo, None)

        m_gerar.assert_not_called()
        self.assertEqual(artefato.pk, existente.pk)

    def test_gera_quando_nao_existe(self):
        def fake_gerar(termo, servidor, formato):
            _persistir_termo_cadastro_artefato(termo, servidor, _fake_doc(hash_sha256="e" * 64))

        with mock.patch("termos.services.gerar_termo_cadastro_um", side_effect=fake_gerar) as m_gerar:
            artefato = resolver_artefato_termo_cadastro(self.termo, None)

        m_gerar.assert_called_once()
        self.assertIsNotNone(artefato)
        self.assertEqual(artefato.termo_id, self.termo.pk)
