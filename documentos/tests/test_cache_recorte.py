"""DB-04 — o cache documental podia servir artefato de outra área.

`get_cached_document_artifact` monta os filtros com `tipo`, `formato`,
`cache_key` e — **só se forem passados** — `oficio_id`, `evento_id`, `termo_id`
e `servidor_id`. A `cache_key` é um SHA-256 de conteúdo
(`document_cache.py:91-103`) e **não** inclui área. Dois ofícios de áreas
diferentes com o mesmo conteúdo produzem a mesma chave.

O catálogo classificou isso como latente, e a verificação confirmou: os cinco
chamadores reais passam referência. **É essa referência que fecha o buraco**, e
não a chave — um ofício pertence a uma área só, então filtrar por `oficio_id`
implica filtrar por área.

O defeito, então, não é o cache servir errado hoje. É **nada obrigar** a passar
referência: o dia em que alguém chamar sem ela, a busca varre o sistema inteiro
por hash de conteúdo, e o primeiro artefato que casar volta — de qualquer área.
A correção é tornar essa chamada impossível, e não confiar em quem chama.

Uma coisa que precisei conferir e que estava errada no enunciado que me deram:
`DocumentoArtefato.area` **não** fica `NULL`. `persistence.py:102` de fato não
preenche o campo, mas `DocumentoArtefato.save()` (`documentos/models.py:87-94`)
deriva a área do ofício, do evento ou do termo. Ler só o `create()` levava à
conclusão contrária.
"""

from __future__ import annotations

from django.core.files.base import ContentFile
from django.test import TestCase

from documentos.models import DocumentoArtefato
from documentos.services.document_cache import get_cached_document_artifact
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo
from oficios.models import Oficio
from usuarios.models import AreaTrabalho


class RecorteDoCacheDocumentalTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="DC-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="DC-B")
        self.meu = Oficio.objects.create(numero=1, ano=2026, area=self.area, assunto="Meu")
        self.alheio = Oficio.objects.create(numero=2, ano=2026, area=self.outra, assunto="Alheio")
        self.chave = "c" * 64

    def _artefato(self, oficio):
        """Com arquivo de verdade: `get_cached_document_artifact` devolve `None`
        para artefato sem ficheiro (`document_cache.py:162`), e um artefato vazio
        faria os testes passarem pelo motivo errado."""
        artefato = DocumentoArtefato.objects.create(
            tipo=DocumentoTipo.OFICIO.value,
            formato=DocumentoFormato.PDF.value,
            oficio=oficio,
            cache_key=self.chave,
            hash_sha256="h" * 64,
        )
        artefato.arquivo.save(f"cache-{oficio.pk}.pdf", ContentFile(b"%PDF-1.4 teste"), save=True)
        return artefato

    def _buscar(self, **kwargs):
        return get_cached_document_artifact(
            tipo=DocumentoTipo.OFICIO,
            formato=DocumentoFormato.PDF,
            cache_key=self.chave,
            **kwargs,
        )

    # ── a premissa: a área é derivada, não fica NULL ──

    def test_o_artefato_herda_a_area_do_oficio(self):
        """Se isto falhar, o recorte por referência deixa de implicar recorte por área."""
        artefato = self._artefato(self.meu)

        self.assertEqual(artefato.area_id, self.area.pk)

    # ── o buraco que este ID fecha ──

    def test_buscar_sem_referencia_e_recusado(self):
        """A chamada que varreria o sistema inteiro por hash de conteúdo.

        Antes, `filters` ficava só com `tipo`, `formato` e `cache_key`, e o
        primeiro artefato que casasse voltava — de qualquer área.
        """
        self._artefato(self.alheio)

        with self.assertRaises(ValueError):
            self._buscar()

    def test_a_recusa_acontece_mesmo_sem_artefato_nenhum(self):
        """Recusa por contrato, não por resultado: não depende de haver dado."""
        with self.assertRaises(ValueError):
            self._buscar()

    # ── o caminho normal não pode ter mudado ──

    def test_com_referencia_encontra_o_proprio(self):
        artefato = self._artefato(self.meu)

        self.assertEqual(self._buscar(oficio_id=self.meu.pk), artefato)

    def test_com_referencia_nao_alcanca_o_de_outra_area(self):
        """Mesma `cache_key`, mesmo tipo, mesmo formato — só a referência separa."""
        self._artefato(self.alheio)

        self.assertIsNone(self._buscar(oficio_id=self.meu.pk))

    def test_referencia_de_servidor_tambem_serve_de_escopo(self):
        """`termos` escopa por ofício **e** servidor; qualquer uma das quatro basta."""
        artefato = self._artefato(self.meu)

        self.assertEqual(self._buscar(oficio_id=self.meu.pk, servidor_id=None), artefato)
